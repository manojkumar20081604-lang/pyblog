BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Python Blog</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    {% if google_analytics_id %}
    <script async src="https://www.googletagmanager.com/gtag/js?id={{ google_analytics_id }}"></script>
    <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('js', new Date());
        gtag('config', '{{ google_analytics_id }}');
    </script>
    {% endif %}
    <script>
        const savedTheme = localStorage.getItem('theme') || 'light';
        document.documentElement.setAttribute('data-bs-theme', savedTheme);
    </script>
    <style>
        [data-bs-theme="light"] body { background-color: #f8f9fa; }
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
                    <li class="nav-item"><button class="nav-link btn" onclick="toggleTheme()">🌓</button></li>
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('index') }}">Home</a></li>
                    <li class="nav-item"><a class="nav-link" href="{{ url_for('contact') }}">Contact</a></li>
                    {% if current_user.is_authenticated %}
                        {% if current_user.is_admin %}
                            <li class="nav-item"><a class="nav-link text-warning" href="{{ url_for('admin_dashboard') }}">Admin Panel</a></li>
                        {% endif %}
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('create_post') }}">New Post</a></li>
                        <li class="nav-item"><a class="nav-link" href="{{ url_for('my_drafts') }}">My Drafts</a></li>
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

    <!-- AI Chat Widget -->
    <div id="chat-widget" style="position: fixed; bottom: 20px; right: 20px; z-index: 1000;">
        <button id="chat-toggle" class="btn btn-primary rounded-circle p-3 shadow" onclick="toggleChat()">💬</button>
        <div id="chat-window" class="card shadow" style="display: none; width: 300px; height: 400px; position: absolute; bottom: 60px; right: 0;">
            <div class="card-header bg-primary text-white d-flex justify-content-between align-items-center">
                <span>Blog AI Assistant</span>
                <button type="button" class="btn-close btn-close-white" onclick="toggleChat()"></button>
            </div>
            <div class="card-body overflow-auto" id="chat-messages" style="height: 290px; background: #f9f9f9;">
                <div class="text-muted small text-center">Ask me anything about the blog!</div>
            </div>
            <div class="card-footer p-2">
                <div class="input-group">
                    <input type="text" id="chat-input" class="form-control form-control-sm" placeholder="Type..." onkeypress="if(event.key==='Enter') sendChat()">
                    <button class="btn btn-primary btn-sm" onclick="sendChat()">➤</button>
                </div>
            </div>
        </div>
    </div>

    <script>
        function toggleChat() {
            const win = document.getElementById('chat-window');
            win.style.display = win.style.display === 'none' ? 'block' : 'none';
        }
        async function sendChat() {
            const input = document.getElementById('chat-input');
            const msg = input.value;
            if (!msg) return;

            const msgs = document.getElementById('chat-messages');
            msgs.innerHTML += `<div class="text-end mb-2"><span class="bg-primary text-white p-2 rounded d-inline-block">${msg}</span></div>`;
            input.value = '';
            msgs.scrollTop = msgs.scrollHeight;

            const payload = {message: msg};
            if (window.currentPostId) {
                payload.post_id = window.currentPostId;
            }

            const res = await fetch('/api/chat', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            msgs.innerHTML += `<div class="text-start mb-2"><span class="bg-light border p-2 rounded d-inline-block">${data.response}</span></div>`;
            msgs.scrollTop = msgs.scrollHeight;
        }
    </script>
    <script>
        function copyToClipboard(text) {
            navigator.clipboard.writeText(text).then(function() {
                alert('Link copied to clipboard!');
            }, function(err) {
                console.error('Could not copy text: ', err);
            });
        }
        function toggleTheme() {
            const currentTheme = document.documentElement.getAttribute('data-bs-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-bs-theme', newTheme);
            localStorage.setItem('theme', newTheme);
        }
    </script>
</body>
</html>
"""

INDEX_HTML = """
{% extends "base" %}
{% block content %}
    <h1 class="mb-4">{{ title|default('Recent Articles') }}</h1>
    <form class="d-flex mb-4" method="GET" action="{{ url_for('index') }}">
        <input class="form-control me-2" type="search" placeholder="Search by title..." name="q" value="{{ request.args.get('q', '') }}">
        <button class="btn btn-outline-success" type="submit">Search</button>
        {% if request.args.get('q') %}
            <a href="{{ url_for('index') }}" class="btn btn-outline-secondary ms-2">Clear</a>
        {% endif %}
    </form>
    {% for post in posts %}
        <div class="card">
            {% if post.image_file %}
                <img src="{{ url_for('uploaded_file', filename=post.image_file) }}" class="card-img-top" style="height: 200px; object-fit: cover;" alt="Post Image">
            {% endif %}
            <div class="card-body">
                <h2 class="card-title"><a href="{{ url_for('view_post', post_id=post.id) }}" class="text-decoration-none text-dark">{{ post.title }}</a></h2>
                <h6 class="card-subtitle mb-2 text-muted">
                    By {{ post.author.username }} | {{ post.timestamp.strftime('%Y-%m-%d') }}
                </h6>
                <p class="card-text">{{ post.content[:200] }}...</p>
                <a href="{{ url_for('view_post', post_id=post.id) }}" class="btn btn-primary btn-sm">Read More &rarr;</a>
                <div class="btn-group ms-1">
                  <button type="button" class="btn btn-sm btn-outline-secondary dropdown-toggle" data-bs-toggle="dropdown" aria-expanded="false">
                    🚀 Share
                  </button>
                  <ul class="dropdown-menu">
                    <li><a class="dropdown-item" href="https://twitter.com/intent/tweet?text={{ post.title|urlencode }}&url={{ url_for('view_post', post_id=post.id, _external=True)|urlencode }}" target="_blank">Twitter</a></li>
                    <li><a class="dropdown-item" href="https://www.facebook.com/sharer/sharer.php?u={{ url_for('view_post', post_id=post.id, _external=True)|urlencode }}" target="_blank">Facebook</a></li>
                    <li><a class="dropdown-item" href="https://www.linkedin.com/sharing/share-offsite/?url={{ url_for('view_post', post_id=post.id, _external=True)|urlencode }}" target="_blank">LinkedIn</a></li>
                    <li><hr class="dropdown-divider"></li>
                    <li><button class="dropdown-item" onclick="copyToClipboard('{{ url_for('view_post', post_id=post.id, _external=True) }}')">📋 Copy Link</button></li>
                  </ul>
                </div>
                <span class="float-end text-muted">
                    ❤️ {{ post.likes|length }} | 💬 {{ post.comments|length }}
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
        <p class="text-muted">By {{ post.author.username }} on {{ post.timestamp.strftime('%Y-%m-%d %H:%M') }}</p>
        {% if post.summary %}
            <div class="alert alert-light border-start border-4 border-info"><strong>Summary:</strong> {{ post.summary }}</div>
        {% endif %}
        <hr>
        <div class="my-4" style="white-space: pre-wrap;">{{ post.content }}</div>

        <div class="d-flex align-items-center mb-4">
            <form action="{{ url_for('like_post', post_id=post.id) }}" method="POST">
                {% if user_has_liked %}
                    <button type="submit" class="btn btn-danger">❤️ Unlike ({{ post.likes|length }})</button>
                {% else %}
                    <button type="submit" class="btn btn-outline-danger">🤍 Like ({{ post.likes|length }})</button>
                {% endif %}
            </form>
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
                <h5 class="mb-1">About {{ post.author.username }}</h5>
                <p class="mb-0 text-muted">{{ post.author.bio or 'This author has not written a bio yet.' }}</p>
            </div>
        </div>
    </div>

    <div class="mt-5">
        <h3>Comments ({{ post.comments|length }})</h3>
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

        {% for comment in post.comments|reverse %}
            <div class="card mb-2">
                <div class="card-body py-2">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>{{ comment.author.username }}</strong>
                            <small class="text-muted">{{ comment.timestamp.strftime('%Y-%m-%d %H:%M') }}</small>
                        </div>
                        <div class="d-flex align-items-center">
                            <form action="{{ url_for('like_comment', comment_id=comment.id) }}" method="POST" class="me-2">
                                {% set user_has_liked = False %}
                                {% if current_user.is_authenticated %}
                                    {% for like in comment.likes %}
                                        {% if like.user_id == current_user.id %}
                                            {% set user_has_liked = True %}
                                        {% endif %}
                                    {% endfor %}
                                {% endif %}
                                {% if user_has_liked %}
                                    <button type="submit" class="btn btn-sm btn-danger py-0">❤️ {{ comment.likes|length }}</button>
                                {% else %}
                                    <button type="submit" class="btn btn-sm btn-outline-danger py-0">🤍 {{ comment.likes|length }}</button>
                                {% endif %}
                            </form>
                            {% if current_user.is_authenticated and current_user.id == comment.author.id %}
                                <a href="{{ url_for('edit_comment', comment_id=comment.id) }}" class="btn btn-sm btn-outline-primary py-0 me-1">Edit</a>
                                <form action="{{ url_for('delete_comment', comment_id=comment.id) }}" method="POST" class="d-inline" onsubmit="return confirm('Delete comment?');">
                                    <button type="submit" class="btn btn-sm btn-outline-danger py-0">Delete</button>
                                </form>
                            {% endif %}
                        </div>
                    </div>
                    <p class="mb-0 mt-1">{{ comment.content }}</p>
                </div>
            </div>
        {% endfor %}
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
                            <input type="text" name="title" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>Content</label>
                            <textarea name="content" rows="10" class="form-control" required></textarea>
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
                <div class="mt-3">
                    <a href="{{ url_for('export_data') }}" class="btn btn-outline-secondary btn-sm">Export Data (GDPR)</a>
                </div>
                <div class="mt-2">
                    <form action="{{ url_for('delete_account') }}" method="POST" onsubmit="return confirm('Are you sure you want to delete your account? This action cannot be undone.');">
                        <button type="submit" class="btn btn-outline-danger btn-sm">Delete Account</button>
                    </form>
                </div>
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
        <script>
        async function aiSuggest(type) {
            let text = "";
            if (type === 'title') text = document.querySelector('[name="content"]').value;
            else text = document.querySelector('[name="title"]').value;

            if (!text) { alert("Please fill the other field first to get a suggestion."); return; }

            const btn = event.target;
            btn.innerText = "Thinking...";
            const res = await fetch('/api/suggest', {
                method: 'POST', headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({type: type, text: text})
            });
            const data = await res.json();
            if (data.result) {
                if (type === 'title') document.querySelector('[name="title"]').value = data.result.replace(/"/g, '');
                else document.querySelector('[name="content"]').value += "\\n\\n" + data.result;
            }
            btn.innerText = "✨ Suggest " + (type === 'title' ? 'Title' : 'Content');
        }
        </script>
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

STATUS_PAGE_HTML = """
{% extends "base" %}
{% block content %}
    <div class="row justify-content-center">
        <div class="col-md-8">
            <h1 class="mb-4">System Status</h1>
            <div class="card">
                <ul class="list-group list-group-flush">
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        Application Status
                        {% if status.app == 'ok' %}
                            <span class="badge bg-success rounded-pill">OK</span>
                        {% else %}
                            <span class="badge bg-danger rounded-pill">ERROR</span>
                        {% endif %}
                    </li>
                    <li class="list-group-item d-flex justify-content-between align-items-center">
                        Database Connection
                        {% if status.database == 'ok' %}
                            <span class="badge bg-success rounded-pill">OK</span>
                        {% else %}
                            <span class="badge bg-danger rounded-pill">ERROR</span>
                        {% endif %}
                    </li>
                </ul>
            </div>
        </div>
    </div>

    <div class="row mt-4">
        <div class="col-12">
            <div class="card p-3">
                <h3>Recent AI Manager Updates</h3>
                <div class="table-responsive">
                    <table class="table table-sm table-striped">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>File</th>
                                <th>Summary</th>
                            </tr>
                        </thead>
                        <tbody>
                        {% for log in ai_logs %}
                            <tr>
                                <td>{{ log.timestamp.strftime('%Y-%m-%d %H:%M') }}</td>
                                <td>{{ log.filename }}</td>
                                <td>{{ log.summary }}</td>
                            </tr>
                        {% else %}
                            <tr>
                                <td colspan="3" class="text-center text-muted">No AI updates have been logged yet.</td>
                            </tr>
                        {% endfor %}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    <div class="row mt-4">
        <div class="col-12">
            <div class="card p-3">
                <h3>AI Updates (Last 30 Days)</h3>
                <canvas id="aiUpdatesChart"></canvas>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        const ctx = document.getElementById('aiUpdatesChart');
        new Chart(ctx, {
            type: 'bar',
            data: {
                labels: {{ chart_labels|safe }},
                datasets: [{
                    label: '# of AI Updates',
                    data: {{ chart_data|safe }},
                    backgroundColor: 'rgba(54, 162, 235, 0.2)',
                    borderColor: 'rgba(54, 162, 235, 1)',
                    borderWidth: 1
                }]
            },
            options: {
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: { stepSize: 1 }
                    }
                }
            }
        });
    </script>
{% endblock %}
"""

MAINTENANCE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Site Maintenance</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { text-align: center; padding: 150px; }
        h1 { font-size: 50px; }
        body { font: 20px Helvetica, sans-serif; color: #333; }
        article { display: block; text-align: left; width: 650px; margin: 0 auto; }
    </style>
</head>
<body>
    <article>
        <h1>We&rsquo;ll be back soon!</h1>
        <div>
            <p>Sorry for the inconvenience but we&rsquo;re performing some maintenance at the moment. We&rsquo;ll be back online shortly!</p>
            <p>&mdash; The PyBlog Team</p>
        </div>
    </article>
</body>
</html>
"""