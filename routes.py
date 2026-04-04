import os
import smtplib
import json
from openai import OpenAI
from datetime import datetime
from datetime import timedelta
from functools import wraps
from flask import render_template_string, redirect, url_for, request, flash, abort, send_from_directory, make_response, current_app as app
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.utils import secure_filename

from blog import db, s3_helpers
from blog.models import User, Post, Comment, Like, Notification, CommentLike
from blog.templates_data import *

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

@app.route('/feed.xml')
def rss_feed():
    posts = Post.query.filter_by(is_published=True).order_by(Post.timestamp.desc()).limit(10).all()
    template = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
    <title>PyBlog</title>
    <link>{{ url_for('index', _external=True) }}</link>
    <description>Latest posts from PyBlog</description>
    {% for post in posts %}
    <item>
        <title>{{ post.title }}</title>
        <link>{{ url_for('view_post', post_id=post.id, _external=True) }}</link>
        <description>{{ post.content[:200] }}...</description>
        <pubDate>{{ post.timestamp.strftime('%a, %d %b %Y %H:%M:%S GMT') }}</pubDate>
    </item>
    {% endfor %}
</channel>
</rss>"""
    response = make_response(render_template_string(template, posts=posts))
    response.headers["Content-Type"] = "application/xml"
    return response

@app.route('/status')
def status_check():
    status = {
        'app': 'ok',
        'database': 'ok'
    }
    try:
        # A simple query to check DB connection
        db.session.execute('SELECT 1')
    except Exception as e:
        status['database'] = 'error'
        app.logger.error(f"Database connection check failed: {e}")

    # You could add other checks here (e.g., S3 connection, AI API)

    return render_template_string(STATUS_PAGE_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), status=status)

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    search_query = request.args.get('q')
    query = Post.query.filter_by(is_published=True)

    if search_query:
        query = query.filter(Post.title.contains(search_query))

    pagination = query.order_by(Post.timestamp.desc()).paginate(page=page, per_page=5, error_out=False)
    posts = pagination.items
    # We render the template string manually and pass 'base' as a variable isn't needed
    # if we treat templates properly, but for single file simple strings:
    return render_template_string(INDEX_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), posts=posts, pagination=pagination)

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        # --- SIMULATE SENDING EMAIL ---
        print(f"\n--- SENDING EMAIL ---\nTo: Admin\nFrom: {name} <{email}>\nSubject: {subject}\nBody: {message}\n-----------------------\n")

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
            if app.config.get('S3_BUCKET'):
                upload = s3_helpers.upload_file_to_s3(file)
                if "error" in upload:
                    flash(f'Image upload failed: {upload["error"]}')
                    return redirect(url_for('create_post'))
                filename = upload.get("filename")
            else:
                # Local Upload for development
                fname = secure_filename(file.filename)
                filename = datetime.now().strftime("%Y%m%d%H%M%S") + "_" + fname
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        post = Post(title=request.form.get('title'),
                    content=request.form.get('content'),
                    author=current_user,
                    image_file=filename)
        db.session.add(post)
        db.session.commit()
        flash('Post created!')
        return redirect(url_for('index'))

    return render_template_string(FORM_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  title="Create Article", btn_text="Publish", is_post_form=True)

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/post/<int:post_id>')
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    user_has_liked = False

    if not post.is_published:
        if not current_user.is_authenticated or (current_user.id != post.author.id and not current_user.is_admin):
            abort(403)

    if current_user.is_authenticated:
        user_has_liked = Like.query.filter_by(user_id=current_user.id, post_id=post.id).first() is not None

    return render_template_string(POST_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  post=post, user_has_liked=user_has_liked)

@app.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    post = Post.query.get_or_404(post_id)
    content = request.form.get('content')
    if content:
        comment = Comment(content=content, author=current_user, post=post)
        db.session.add(comment)
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

@app.route('/drafts')
@login_required
def my_drafts():
    posts = Post.query.filter_by(author=current_user, is_published=False).order_by(Post.timestamp.desc()).all()
    return render_template_string(INDEX_HTML.replace('{% extends "base" %}', BASE_TEMPLATE),
                                  posts=posts, title="My Drafts")

@app.route('/export_data')
@login_required
def export_data():
    data = {
        'username': current_user.username,
        'email': current_user.email,
        'bio': current_user.bio,
        'posts': [{
            'title': p.title,
            'content': p.content,
            'timestamp': p.timestamp.isoformat(),
            'views': p.views
        } for p in current_user.posts],
        'comments': [{
            'content': c.content,
            'timestamp': c.timestamp.isoformat(),
            'post_id': c.post_id
        } for c in current_user.comments]
    }

    response = make_response(json.dumps(data, indent=4))
    response.headers['Content-Disposition'] = f'attachment; filename={current_user.username}_data.json'
    response.headers['Content-Type'] = 'application/json'
    return response

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    # Delete posts (cascades comments/likes on posts)
    for post in current_user.posts:
        db.session.delete(post)

    # Delete comments made by user
    for comment in current_user.comments:
        db.session.delete(comment)

    # Delete likes made by user
    for like in current_user.likes:
        db.session.delete(like)

    # Delete comment likes made by user
    for clike in current_user.comment_likes:
        db.session.delete(clike)

    # Delete notifications received by user
    for notif in current_user.notifications:
        db.session.delete(notif)

    # Delete notifications triggered by user (actor)
    actor_notifs = Notification.query.filter_by(actor_id=current_user.id).all()
    for notif in actor_notifs:
        db.session.delete(notif)

    db.session.delete(current_user)
    db.session.commit()
    logout_user()
    flash('Your account has been permanently deleted.')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        file = request.files.get('profile_pic')
        if file and allowed_file(file.filename):
            if app.config.get('S3_BUCKET'):
                upload = s3_helpers.upload_file_to_s3(file)
                if "error" in upload:
                    flash(f'Image upload failed: {upload["error"]}')
                    return redirect(url_for('profile'))
                current_user.profile_pic = upload.get("filename")
            else:
                fname = secure_filename(file.filename)
                filename = f"user_{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname}"
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                current_user.profile_pic = filename

        current_user.bio = request.form.get('bio')
        db.session.commit()
        flash('Profile updated successfully!')
        return redirect(url_for('profile'))

    return render_template_string(PROFILE_HTML.replace('{% extends "base" %}', BASE_TEMPLATE))

@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    users = User.query.all()
    posts = Post.query.all()
    ai_logs = AiUpdateLog.query.order_by(AiUpdateLog.timestamp.desc()).limit(15).all()

    # --- Chart Data Processing ---
    from collections import defaultdict
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    logs_for_chart = AiUpdateLog.query.filter(AiUpdateLog.timestamp >= thirty_days_ago).all()
    updates_per_day = defaultdict(int)
    for log in logs_for_chart:
        day = log.timestamp.strftime('%Y-%m-%d')
        updates_per_day[day] += 1

    chart_labels = []
    chart_data = []
    for i in range(30):
        day = (datetime.utcnow() - timedelta(days=i)).strftime('%Y-%m-%d')
        chart_labels.append(day)
        chart_data.append(updates_per_day[day])

    chart_labels.reverse()
    chart_data.reverse()
    # --- End Chart Data ---

    return render_template_string(ADMIN_HTML.replace('{% extends "base" %}', BASE_TEMPLATE), users=users, posts=posts, ai_logs=ai_logs, chart_labels=json.dumps(chart_labels), chart_data=json.dumps(chart_data))

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

@app.route('/admin/delete_post/<int:post_id>', methods=['POST'])
@login_required
@admin_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    flash('Post deleted by admin.')
    return redirect(url_for('admin_dashboard'))

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