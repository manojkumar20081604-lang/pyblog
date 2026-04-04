import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, render_template_string, redirect, url_for, request, flash, abort, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from itsdangerous import URLSafeTimedSerializer as Serializer

# Configuration
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this-in-prod')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blog_database.db')
# Fix for some cloud providers using postgres:// instead of postgresql://
if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# ---------------- MODELS ----------------

post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'), primary_key=True)
)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id')),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id'))
)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    message = db.Column(db.String(255), nullable=False)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(100), nullable=True)
    posts = db.relationship('Post', backref='author', lazy=True)
    comments = db.relationship('Comment', backref='author', lazy=True)
    likes = db.relationship('Like', backref='user', lazy=True)
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', backref='recipient', lazy='dynamic')
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')

    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)

    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_reset_token(self):
        s = Serializer(app.config['SECRET_KEY'])
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')

    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = Serializer(app.config['SECRET_KEY'])
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=True)
    is_published = db.Column(db.Boolean, default=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy=True, cascade="all, delete-orphan")
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                           backref=db.backref('posts', lazy=True))

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

class Like(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- TEMPLATES (HTML) ----------------

BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Blog</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; }
        .card { margin-bottom: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .navbar { margin-bottom: 30px; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="{{ url_for('index') }}">📝 PyBlog</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('index') }}">Home</a></li>
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('contact') }}">Contact</a></li>
                    {% if current_user.is_authenticated %}
                        {% if current_user.is_admin %}
                            <li class="nav-item"><a class="nav-link text-warning" href="{{ url_for('admin_dashboard') }}">Admin Panel</a></li>
                        {% endif %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('create_post') }}">New Post</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('my_drafts') }}">My Drafts</a></li>
                        <li class="nav-item">
                            <a class="nav-link" href="{{ url_for('notifications') }}">
                                🔔
                                {% set unread = current_user.notifications.filter_by(is_read=False).count() %}
                                {% if unread > 0 %}
                                    <span class="badge bg-danger rounded-pill">{{ unread }}</span>
                                {% endif %}
                            </a>
                        </li>
                        <li class="nav-item"><a class="nav-link text-light" href="{{ url_for('profile') }}">Hi, {{ current_user.username }}</a></li>
                        <li class="nav-item"><a class="nav-link btn btn-outline-light btn-sm ms-2" href="{{ url_for('logout') }}">Logout</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('login') }}">Login</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('register') }}">Register</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>

    <div class="container">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-info">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

INDEX_HTML = """
{% extends "base" %}
{% block content %}
    <h1 class="mb-4">{{ title|default('Recent Articles') }}</h1>
    {% if current_user.is_authenticated %}
        <h1 class="mb-4">Posts from Followed Users</h1>
    {% else %}
        <h1 class="mb-4">All Posts</h1>
        <form class="d-flex mb-4" method="GET" action="{{ url_for('index') }}">
        <input class="form-control me-2" type="search" placeholder="Search by title..." name="q" value="{{ request.args.get('q', '') }}">
        <button class="btn btn-outline-success" type="submit">Search</button>
        {% if request.args.get('q') %}
            <a href="{{ url_for('index') }}" class="btn btn-outline-secondary ms-2">Clear</a>
        {% endif %}
        {% if request.args.get('tag') %}
            <span class="ms-2 align-self-center">Tag: <strong>{{ request.args.get('tag') }}</strong></span>
            <a href="{{ url_for('index') }}" class="btn-close ms-2 align-self-center" aria-label="Close"></a>
        {% endif %}
    </form>
    {% endif %}
    {% for post in posts %}
        <div class="card">
            {% if post.image_file %}
                <img src="{{ url_for('uploaded_file', filename=post.image_file) }}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="Post Image">
            {% endif %}
            <div class="card-body">
                <h2 class="card-title"><a href="{{ url_for('view_post', post_id=post.id) }}" class="text-decoration-none text-dark">{{ post.title }}</a></h2>
                <div class="mb-2">
                    {% for tag in post.tags %}
                        <a href="{{ url_for('index', tag=tag.name) }}" class="badge bg-secondary text-decoration-none">{{ tag.name }}</a>
                    {% endfor %}
                </div>
                <h6 class="card-subtitle mb-2 text-muted">
                            By <a href="{{ url_for('user_profile', username=post.author.username) }}" class="text-decoration-none">{{ post.author.username }}</a> | {{ post.timestamp.strftime('%Y-%m-%d') }}
                </h6>
                <p class="card-text">{{ post.content[:200] }}...</p>
                <a href="{{ url_for('view_post', post_id=post.id) }}" class="btn btn-primary btn-sm">Read More &rarr;</a>
                <span class="float-end text-muted">
                    ️ {{ post.views }} | ❤️ {{ post.likes|length }} | 💬 {{ post.comments|length }}
                </span>
            </div>
        </div>
    {% else %}
        <p class="text-center">No posts yet. Be the first to write one!</p>
    {% endfor %}

    {% if pagination and pagination.pages > 1 %}
    <nav aria-label="Page navigation" class="mt-4">
        <ul class="pagination justify-content-center">
            <li class="page-item {% if not pagination.has_prev %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('index', page=pagination.prev_num, q=request.args.get('q', '')) }}">Previous</a>
            </li>
            <li class="page-item disabled">
                <span class="page-link">Page {{ pagination.page }} of {{ pagination.pages }}</span>
            </li>
            <li class="page-item {% if not pagination.has_next %}disabled{% endif %}">
                <a class="page-link" href="{{ url_for('index', page=pagination.next_num, q=request.args.get('q', '')) }}">Next</a>
            </li>
        </ul>
    </nav>
    {% endif %}
{% endblock %}
"""

POST_HTML = """
{% extends "base" %}
{% block content %}
    <div class="card p-4">
        {% if post.image_file %}
            <img src="{{ url_for('uploaded_file', filename=post.image_file) }}" class="img-fluid mb-4 rounded" alt="Post Image">
        {% endif %}
        <h1>{{ post.title }} {% if not post.is_published %}<span class="badge bg-secondary">Draft</span>{% endif %}</h1>
        <p class="text-muted">By <a href="{{ url_for('user_profile', username=post.author.username) }}" class="text-decoration-none">{{ post.author.username }}</a> on {{ post.timestamp.strftime('%Y-%m-%d %H:%M') }} | 👁️ {{ post.views }} Views</p>
        <hr>
        <div class="my-4" style="white-space: pre-wrap;">{{ post.content }}</div>

        <div class="mb-4">
            {% for tag in post.tags %}
                <span class="badge bg-secondary">{{ tag.name }}</span>
            {% endfor %}
        </div>

        <div class="d-flex align-items-center mb-4">
            <form action="{{ url_for('like_post', post_id=post.id) }}" method="POST">
                {% if user_has_liked %}
                    <button type="submit" class="btn btn-danger">❤️ Unlike ({{ post.likes|length }})</button>
                {% else %}
                    <button type="submit" class="btn btn-outline-danger">🤍 Like ({{ post.likes|length }})</button>
                {% endif %}
            </form>
            {% if current_user.is_authenticated and (post.author == current_user or current_user.is_admin) %}
                <a href="{{ url_for('edit_post', post_id=post.id) }}" class="btn btn-secondary ms-2">Edit</a>
                <form action="{{ url_for('delete_post', post_id=post.id) }}" method="POST" class="ms-2" onsubmit="return confirm('Are you sure you want to delete this post?');">
                    <button type="submit" class="btn btn-danger">Delete</button>
                </form>
            {% endif %}
        </div>

        <hr>
        <div class="d-flex mt-4">
            <div class="flex-shrink-0">
                {% if post.author.profile_pic %}
                    <img src="{{ url_for('uploaded_file', filename=post.author.profile_pic) }}" class="rounded-circle" style="width: 64px; height: 64px; object-fit: cover;">
                {% else %}
                    <img src="https://via.placeholder.com/64" class="rounded-circle" style="width: 64px; height: 64px; object-fit: cover;">
                {% endif %}
            </div>
            <div class="flex-grow-1 ms-3">
                <h5 class="mb-1">About <a href="{{ url_for('user_profile', username=post.author.username) }}" class="text-decoration-none text-dark">{{ post.author.username }}</a></h5>
                <p class="mb-0 text-muted">{{ post.author.bio or 'This author has not written a bio yet.' }}</p>
            </div>
        </div>
    </div>

    <div class="mt-5">
        <h3>Comments ({{ comments_pagination.total }})</h3>
        {% if current_user.is_authenticated %}
            <form action="{{ url_for('add_comment', post_id=post.id) }}" method="POST" class="mb-4">
                <div class="mb-3">
                    <textarea class="form-control" name="content" rows="3" placeholder="Write a comment..." required></textarea>
                </div>
                <button type="submit" class="btn btn-secondary">Post Comment</button>
            </form>
        {% else %}
            <p><a href="{{ url_for('login') }}">Login</a> to leave a comment.</p>
        {% endif %}

        {% for comment in comments_pagination.items %}
            <div class="card mb-2">
                <div class="card-body py-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>{{ comment.author.username }}</strong>
                            <small class="text-muted">{{ comment.timestamp.strftime('%Y-%m-%d %H:%M') }}</small>
                        </div>
                        {% if current_user.is_authenticated and current_user.id == comment.author.id %}
                            <div>
                                <a href="{{ url_for('edit_comment', comment_id=comment.id) }}" class="btn btn-sm btn-outline-primary py-0">Edit</a>
                                <form action="{{ url_for('delete_comment', comment_id=comment.id) }}" method="POST" class="d-inline" onsubmit="return confirm('Delete comment?');">
                                    <button type="submit" class="btn btn-sm btn-outline-danger py-0">Delete</button>
                                </form>
                            </div>
                        {% endif %}
                    </div>
                    <p class="mb-0 mt-1">{{ comment.content }}</p>
                </div>
            </div>
        {% endfor %}

        {% if comments_pagination and comments_pagination.pages > 1 %}
        <nav aria-label="Comment navigation" class="mt-4">
            <ul class="pagination justify-content-center">
                <li class="page-item {% if not comments_pagination.has_prev %}disabled{% endif %}">
                    <a class="page-link" href="{{ url_for('view_post', post_id=post.id, comment_page=comments_pagination.prev_num) }}">Previous</a>
                </li>
                <li class="page-item disabled">
                    <span class="page-link">Page {{ comments_pagination.page }} of {{ comments_pagination.pages }}</span>
                </li>
                <li class="page-item {% if not comments_pagination.has_next %}disabled{% endif %}">
                    <a class="page-link" href="{{ url_for('view_post', post_id=post.id, comment_page=comments_pagination.next_num) }}">Next</a>
                </li>
            </ul>
        </nav>
        {% endif %}
    </div>
{% endblock %}
"""

FORM_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card p-4">
                <h2 class="text-center mb-4">{{ title }}</h2>
                <form method="POST" enctype="multipart/form-data">
                    {% if not is_post_form %}
                        <div class="mb-3">
                            <label>Username</label>
                            <input type="text" name="username" class="form-control" required>
                        </div>
                        {% if title == 'Register' %}
                        <div class="mb-3">
                            <label>Email</label>
                            <input type="email" name="email" class="form-control" required>
                        </div>
                        {% endif %}
                        <div class="mb-3">
                            <label>Password</label>
                            <input type="password" name="password" class="form-control" required>
                        </div>
                        {% if title == 'Login' %}
                            <div class="mb-3 text-end">
                                <a href="{{ url_for('reset_request') }}">Forgot Password?</a>
                            </div>
                        {% endif %}
                    {% else %}
                        <div class="mb-3">
                            <label>Title</label>
                            <input type="text" name="title" class="form-control" required value="{{ post.title if post else '' }}">
                        </div>
                        <div class="mb-3">
                            <label>Content</label>
                            <textarea name="content" rows="10" class="form-control" required>{{ post.content if post else '' }}</textarea>
                        </div>
                        <div class="mb-3">
                            <label>Tags (comma separated)</label>
                            <input type="text" name="tags" class="form-control" placeholder="e.g. python, coding, life" value="{{ post.tags|map(attribute='name')|join(', ') if post and post.tags }}">
                        </div>
                        <div class="mb-3">
                            <label>Image (Optional)</label>
                            <input type="file" name="image" class="form-control">
                        </div>
                    {% endif %}
                    <div class="d-flex gap-2">
                        <button type="submit" name="action" value="publish" class="btn btn-primary flex-grow-1">{{ btn_text }}</button>
                        {% if is_post_form %}
                            <button type="submit" name="action" value="draft" class="btn btn-secondary flex-grow-1">Save Draft</button>
                        {% endif %}
                    </div>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

ADMIN_HTML = """
{% extends "base" %}
{% block content %}
    <h1 class="mb-4">Admin Dashboard</h1>
    <div class="row">
        <div class="col-md-6">
            <div class="card p-3">
                <h3>Manage Users</h3>
                <ul class="list-group list-group-flush">
                {% for user in users %}
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        <span>{{ user.username }} {% if user.is_admin %}<span class="badge bg-warning text-dark">Admin</span>{% endif %}</span>
                        {% if not user.is_admin %}
                        <form action="{{ url_for('delete_user', user_id=user.id) }}" method="POST" onsubmit="return confirm('Are you sure you want to delete this user?');">
                            <button type="submit" class="btn btn-danger btn-sm">Delete</button>
                        </form>
                        {% endif %}
                    </li>
                {% endfor %}
                </ul>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card p-3">
                <h3>Manage Posts</h3>
                <ul class="list-group list-group-flush">
                {% for post in posts %}
                    <li class="list-group-item">
                        <strong>{{ post.title }}</strong> <small class="text-muted">by {{ post.author.username }}</small>
                        <form action="{{ url_for('delete_post', post_id=post.id) }}" method="POST" class="mt-2" onsubmit="return confirm('Delete this post?');">
                            <button type="submit" class="btn btn-danger btn-sm">Delete Post</button>
                        </form>
                    </li>
                {% endfor %}
                </ul>
            </div>
        </div>
    </div>
{% endblock %}
"""

PROFILE_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row">
        <div class="col-md-4 text-center">
            <div class="card p-3">
                {% if current_user.profile_pic %}
                    <img src="{{ url_for('uploaded_file', filename=current_user.profile_pic) }}" class="img-fluid rounded-circle mb-3" style="width: 150px; height: 150px; object-fit: cover; margin: 0 auto;">
                {% else %}
                    <img src="https://via.placeholder.com/150" class="img-fluid rounded-circle mb-3" style="width: 150px; height: 150px; object-fit: cover; margin: 0 auto;">
                {% endif %}
                <h3>{{ current_user.username }}</h3>
            </div>
        </div>
        <div class="col-md-8">
            <div class="card p-4">
                <h3 class="mb-4">Update Profile</h3>
                <form method="POST" enctype="multipart/form-data">
                    <div class="mb-3">
                        <label>Profile Picture</label>
                        <input type="file" name="profile_pic" class="form-control">
                    </div>
                    <div class="mb-3">
                        <label>Bio</label>
                        <textarea name="bio" class="form-control" rows="5">{{ current_user.bio or '' }}</textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">Save Changes</button>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

USER_PROFILE_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row">
        <div class="col-md-4">
            <div class="card p-3 text-center">
                {% if user.profile_pic %}
                    <img src="{{ url_for('uploaded_file', filename=user.profile_pic) }}" class="img-fluid rounded-circle mb-3" style="width: 150px; height: 150px; object-fit: cover; margin: 0 auto;">
                {% else %}
                    <img src="https://via.placeholder.com/150" class="img-fluid rounded-circle mb-3" style="width: 150px; height: 150px; object-fit: cover; margin: 0 auto;">
                {% endif %}
                <h3>{{ user.username }}</h3>
                <p class="text-muted">{{ user.bio or '' }}</p>

                <div class="d-flex justify-content-around mb-3">
                    <div><strong>{{ user.followers.count() }}</strong><br>Followers</div>
                    <div><strong>{{ user.followed.count() }}</strong><br>Following</div>
                </div>

                {% if current_user.is_authenticated and user != current_user %}
                    {% if current_user.is_following(user) %}
                        <form action="{{ url_for('unfollow_user', username=user.username) }}" method="POST">
                            <button type="submit" class="btn btn-danger">Unfollow</button>
                        </form>
                    {% else %}
                        <form action="{{ url_for('follow_user', username=user.username) }}" method="POST">
                            <button type="submit" class="btn btn-primary">Follow</button>
                        </form>
                    {% endif %}
                {% elif current_user == user %}
                    <a href="{{ url_for('profile') }}" class="btn btn-outline-primary">Edit Profile</a>
                {% endif %}
            </div>
        </div>
        <div class="col-md-8">
            <h3 class="mb-4">Posts by {{ user.username }}</h3>
            {% for post in posts %}
                <div class="card mb-3">
                    <div class="card-body">
                        <h5 class="card-title"><a href="{{ url_for('view_post', post_id=post.id) }}" class="text-decoration-none">{{ post.title }}</a></h5>
                        <h6 class="card-subtitle mb-2 text-muted">{{ post.timestamp.strftime('%Y-%m-%d') }}</h6>
                        <p class="card-text">{{ post.content[:100] }}...</p>
                        <a href="{{ url_for('view_post', post_id=post.id) }}" class="btn btn-sm btn-primary">Read More</a>
                    </div>
                </div>
            {% else %}
                <p>No posts published yet.</p>
            {% endfor %}
        </div>
    </div>
{% endblock %}
"""

COMMENT_EDIT_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card p-4">
                <h3>Edit Comment</h3>
                <form method="POST">
                    <div class="mb-3">
                        <textarea name="content" class="form-control" rows="3" required>{{ comment.content }}</textarea>
                    </div>
                    <button type="submit" class="btn btn-primary">Update Comment</button>
                    <a href="{{ url_for('view_post', post_id=comment.post_id) }}" class="btn btn-secondary">Cancel</a>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

CONTACT_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-8">
            <div class="card p-4">
                <h2 class="text-center mb-4">Contact Us</h2>
                <form method="POST">
                    <div class="row">
                        <div class="col-md-6 mb-3">
                            <label>Name</label>
                            <input type="text" name="name" class="form-control" required>
                        </div>
                        <div class="col-md-6 mb-3">
                            <label>Email</label>
                            <input type="email" name="email" class="form-control" required>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label>Subject</label>
                        <input type="text" name="subject" class="form-control" required>
                    </div>
                    <div class="mb-3">
                        <label>Message</label>
                        <textarea name="message" rows="5" class="form-control" required></textarea>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Send Message</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

NOTIFICATIONS_HTML = """
{% extends "base" %}
{% block content %}
    <h1 class="mb-4">Notifications</h1>
    <div class="list-group">
    {% for notif in notifications %}
        <a href="{{ url_for('view_post', post_id=notif.post_id) }}" class="list-group-item list-group-item-action {% if not notif.is_read %}list-group-item-light{% endif %}">
            <div class="d-flex w-100 justify-content-between">
                <small class="text-muted">{{ notif.timestamp.strftime('%Y-%m-%d %H:%M') }}</small>
            </div>
            <p class="mb-1">{{ notif.message }}</p>
        </a>
    {% else %}
        <p>No notifications.</p>
    {% endfor %}
    </div>
{% endblock %}
"""

RESET_REQUEST_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card p-4">
                <h2 class="text-center mb-4">Reset Password</h2>
                <form method="POST">
                    <div class="mb-3">
                        <label>Enter your email address</label>
                        <input type="email" name="email" class="form-control" required>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Request Password Reset</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

RESET_PASSWORD_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card p-4">
                <h2 class="text-center mb-4">New Password</h2>
                <form method="POST">
                    <div class="mb-3">
                        <label>New Password</label>
                        <input type="password" name="password" class="form-control" required>
                    </div>
                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary">Reset Password</button>
                    </div>
                </form>
            </div>
        </div>
    </div>
{% endblock %}
"""

# ---------------- ROUTES ----------------

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q')
    tag_query = request.args.get('tag')
    query = Post.query.filter_by(is_published=True)

    if search_query:
        query = query.filter(or_(Post.title.contains(search_query), Post.content.contains(search_query)))

    if tag_query:
        query = query.join(Post.tags).filter(Tag.name == tag_query)

    pagination = query.order_by(Post.timestamp.desc()).paginate(page=page, per_page=5, error_out=False)
    posts = pagination.items

    tags = Tag.query.all()
    # We render the template string manually and pass 'base' as a variable isn't needed
    # if we treat templates properly, but for single file simple strings:
    return render_template_string(INDEX_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), posts=posts, pagination=pagination, tags=tags)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # --- SIMULATE SENDING EMAIL ---
        print(f"\n--- SENDING EMAIL ---\nTo: Admin\nFrom: {name} <{email}>\nSubject: {subject}\nBody: {message}\n-----------------------\n")

        # --- REAL EMAIL SENDING CODE ---
        try:
            msg = MIMEMultipart()
            msg['From'] = email
            msg['To'] = os.environ.get('EMAIL_USER', 'your_email@gmail.com')
            msg['Subject'] = f"Contact Form: {subject}"
            msg.attach(MIMEText(message, 'plain'))

            # Setup for Gmail (requires App Password)
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(os.environ.get('EMAIL_USER', 'your_email@gmail.com'),
                             os.environ.get('EMAIL_PASS', 'your_app_password'))
                server.send_message(msg)
        except Exception as e:
            print(f"Error sending email: {e}")

        flash('Message sent successfully! We will get back to you soon.')
        return redirect(url_for('contact'))

    return render_template_string(CONTACT_HTML.replace('{% extends "base" %}', BASE_TEMPLATE))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already registered.')
            return redirect(url_for('register'))

        # Make the first registered user an Admin automatically
        is_admin = User.query.first() is None
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))

    return render_template_string(FORM_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  title="Register", btn_text="Sign Up", is_post_form=False)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid username or password')

    return render_template_string(FORM_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  title="Login", btn_text="Sign In", is_post_form=False)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create_post():
    if request.method == 'POST':
        filename = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            # Prepend timestamp to filename to avoid collisions
            fname = secure_filename(file.filename)
            filename = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + fname
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        # Handle Tags
        tags_input = request.form.get('tags')
        tags = []
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                tags.append(tag)

        action = request.form.get('action')
        is_published = (action == 'publish')
        post = Post(title=request.form.get('title'),
                    content=request.form.get('content'),
                    author=current_user,
                    image_file=filename,
                    tags=tags,
                    is_published=is_published)
        db.session.add(post)
        db.session.commit()
        flash('Post created!')
        return redirect(url_for('index'))

    return render_template_string(FORM_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  title="Create Article", btn_text="Publish", is_post_form=True)

@app.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user and not current_user.is_admin:
        abort(403)

    if request.method == 'POST':
        post.title = request.form.get('title')
        post.content = request.form.get('content')

        file = request.files.get('image')
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            filename = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + fname
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            post.image_file = filename

        tags_input = request.form.get('tags')
        tags = []
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                tags.append(tag)
        post.tags = tags

        db.session.commit()
        flash('Your post has been updated!')
        return redirect(url_for('view_post', post_id=post.id))

    return render_template_string(FORM_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  title="Edit Article", btn_text="Update", is_post_form=True, post=post)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    user_has_liked = False
    comment_page = request.args.get('comment_page', 1, type=int)

    if not post.is_published:
        if not current_user.is_authenticated or (current_user.id != post.author.id and not current_user.is_admin):
            abort(403)

    post.views += 1
    db.session.commit()

    if current_user.is_authenticated:
        user_has_liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None

    comments_pagination = Comment.query.filter_by(post_id=post.id).order_by(Comment.timestamp.desc()).paginate(page=comment_page, per_page=5, error_out=False)

    return render_template_string(POST_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  post=post, user_has_liked=user_has_liked, comments_pagination=comments_pagination)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if content:
        comment = Comment(content=content, author=current_user, post=post)
        db.session.add(comment)

        if post.author.id != current_user.id:
            notif = Notification(user_id=post.author.id, actor_id=current_user.id, post_id=post.id, message=f"{current_user.username} commented on your post: {post.title}")
            db.session.add(notif)

        db.session.commit()
        flash('Comment added!')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    existing_like = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first()

    if existing_like:
        db.session.delete(existing_like)
    else:
        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)

    db.session.commit()
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user and not current_user.is_admin:
        abort(403)
    post_id = comment.post_id
    db.session.delete(comment)
    db.session.commit()
    flash('Comment deleted.')
    return redirect(url_for('view_post', post_id=post_id))

@app.route('/comment/<int:comment_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    if comment.author != current_user:
        abort(403)
    if request.method == 'POST':
        comment.content = request.form.get('content')
        db.session.commit()
        flash('Comment updated.')
        return redirect(url_for('view_post', post_id=comment.post_id))
    return render_template_string(COMMENT_EDIT_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), comment=comment)

@app.route('/notifications')
@login_required
def notifications():
    notifs = current_user.notifications.order_by(Notification.timestamp.desc()).all()
    for n in notifs:
        n.is_read = True
    db.session.commit()
    return render_template_string(NOTIFICATIONS_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), notifications=notifs)

@app.route('/drafts')
@login_required
def my_drafts():
    posts = Post.query.filter_by(author=current_user, is_published=False).order_by(Post.timestamp.desc()).all()
    return render_template_string(INDEX_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  posts=posts, title="My Drafts")

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        file = request.files.get('profile_pic')
        if file and allowed_file(file.filename):
            fname = secure_filename(file.filename)
            # Create unique filename with user ID and timestamp
            filename = f"user_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            current_user.profile_pic = filename

        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))

    return render_template_string(PROFILE_HTML.replace('{% extends "base" %}', BASE_TEMPLATE))

@app.route('/user/<string:username>')
def user_profile(username):
    user = User.query.filter_by(username=username).first_or_404()
    posts = Post.query.filter_by(author=user, is_published=True).order_by(Post.timestamp.desc()).all()
    return render_template_string(USER_PROFILE_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), user=user, posts=posts)

@app.route('/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.')
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot follow yourself!')
        return redirect(url_for('user_profile', username=username))
    current_user.follow(user)
    db.session.commit()
    flash(f'You are now following {username}!')
    return redirect(url_for('user_profile', username=username))

@app.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username).first()
    if not user:
        flash('User not found.')
        return redirect(url_for('index'))
    if user == current_user:
        flash('You cannot unfollow yourself!')
        return redirect(url_for('user_profile', username=username))
    current_user.unfollow(user)
    db.session.commit()
    flash(f'You have unfollowed {username}.')
    return redirect(url_for('user_profile', username=username))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    posts = Post.query.all()
    return render_template_string(ADMIN_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), users=users, posts=posts)

@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if not user.is_admin:
        db.session.delete(user)
        db.session.commit()
        flash('User deleted successfully.')
    return redirect(url_for('admin_dashboard'))

@app.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if post.author != current_user and not current_user.is_admin:
        abort(403)
    db.session.delete(post)
    db.session.commit()
    flash('Your post has been deleted.', 'success')
    if current_user.is_admin and request.referrer and 'admin' in request.referrer:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('index'))

@app.route('/reset_password', methods=['GET', 'POST'])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.get_reset_token()
            # In a real app, send this link via email. Here we print to console.
            reset_url = url_for('reset_token', token=token, _external=True)
            print(f"\n--- PASSWORD RESET ---\nTo: {email}\nLink: {reset_url}\n----------------------\n")
            flash('An email has been sent with instructions to reset your password.', 'info')
            return redirect(url_for('login'))
        else:
            flash('There is no account with that email. You must register first.')
    return render_template_string(RESET_REQUEST_HTML.replace('{% extends "base" %}', BASE_TEMPLATE))

@app.route('/healthz')
def healthz():
    try:
        db.session.execute(db.text('SELECT 1'))
        return {'app': 'ok', 'database': 'ok'}, 200
    except Exception as e:
        return {'app': 'ok', 'database': 'error', 'error': str(e)}, 500

@app.route('/sitemap.xml')
def sitemap():
    posts = Post.query.filter_by(is_published=True).order_by(Post.timestamp.desc()).all()
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'''
    for post in posts:
        url = url_for('view_post', post_id=post.id, _external=True)
        xml += f'''
  <url>
    <loc>{url}</loc>
    <lastmod>{post.timestamp.strftime('%Y-%m-%d')}</lastmod>
  </url>'''
    xml += '''
</urlset>'''
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/feed.xml')
def feed():
    posts = Post.query.filter_by(is_published=True).order_by(Post.timestamp.desc()).limit(20).all()
    xml = '''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>PyBlog</title>
    <link>{link}</link>
    <description>Latest articles from PyBlog</description>
'''.format(link=url_for('index', _external=True))
    for post in posts:
        url = url_for('view_post', post_id=post.id, _external=True)
        xml += f'''
    <item>
      <title>{post.title}</title>
      <link>{url}</link>
      <description>{post.content[:200]}</description>
      <pubDate>{post.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT')}</pubDate>
    </item>'''
    xml += '''
  </channel>
</rss>'''
    return xml, 200, {'Content-Type': 'application/xml'}

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id
    logout_user()
    user = User.query.get(user_id)
    db.session.delete(user)
    db.session.commit()
    flash('Your account has been permanently deleted.', 'info')
    return redirect(url_for('index'))

@app.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('reset_request'))
    if request.method == 'POST':
        password = request.form.get('password')
        user.set_password(password)
        db.session.commit()
        flash('Your password has been updated! You are now able to log in', 'success')
        return redirect(url_for('login'))
    return render_template_string(RESET_PASSWORD_HTML.replace('{% extends "base" %}', BASE_TEMPLATE))

# Initialize database and uploads (Runs on import for Gunicorn/Production)
with app.app_context():
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    db.create_all()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)