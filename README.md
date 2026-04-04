# PyBlog 🚀

A fully-featured, AI-powered blogging platform built with Flask. Supports user authentication, CRUD posts, comments, likes, AWS S3 media uploads, OpenAI integration, and automated database backups.

---

## Features

- **Auth** — Register, Login, Logout, Password Reset via email
- **Posts** — Create, Edit, Delete with draft/publish support
- **Social** — Comments, Likes, Follow/Unfollow, Notifications, User Profiles
- **AI** — OpenAI-powered code review and autonomous maintenance agent
- **Media** — Local storage (dev) / AWS S3 (prod)
- **Admin** — Dashboard to manage users and posts
- **Monitoring** — `/healthz` endpoint + email alerts via `monitor.py`
- **Backups** — Automated PostgreSQL → S3 backups via `backup.py`
- **GDPR** — Data export and account deletion
- **Maintenance Mode** — Toggle via environment variable

---

## Tech Stack

| Layer | Tech |
|---|---|
| Backend | Python 3, Flask |
| Database | SQLite (dev), PostgreSQL (prod) |
| ORM | SQLAlchemy + Flask-SQLAlchemy |
| Auth | Flask-Login |
| AI | OpenAI API (gpt-3.5-turbo) |
| Storage | AWS S3 (Boto3) |
| Server | Gunicorn |
| Frontend | Bootstrap 5, Jinja2 |

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/pyblog.git
cd pyblog
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set environment variables

Create a `.env` file in the project root (or set them manually):

```env
SECRET_KEY=your_random_secret_key

# Optional — defaults to SQLite if not set
DATABASE_URL=sqlite:///blog_database.db

# Optional — for AI features
OPENAI_API_KEY=sk-...

# Optional — for S3 media uploads
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
S3_BUCKET_NAME=your-bucket-name

# Optional — for email (password reset, contact form)
EMAIL_USER=your_email@gmail.com
EMAIL_PASS=your_gmail_app_password
```

> **Note:** If `S3_BUCKET_NAME` is not set, images are stored locally in `blog/static/uploads/`.

### 5. Run the app

```bash
python run.py
```

Visit `http://localhost:5000`

---

## Running Tests

```bash
python tests.py
```

Tests use an in-memory SQLite database. No external services needed.

---

## Deploying to Render

### Step 1 — Push to GitHub

Make sure your project is pushed to a GitHub repository.

### Step 2 — Create a new Web Service on Render

1. Go to [render.com](https://render.com) → **New** → **Web Service**
2. Connect your GitHub repo
3. Set the following:

| Field | Value |
|---|---|
| **Environment** | Python 3 |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `gunicorn run:app` |

### Step 3 — Add a PostgreSQL Database

1. On Render → **New** → **PostgreSQL**
2. Copy the **Internal Database URL**
3. Add it as an environment variable: `DATABASE_URL`

> Render provides `postgres://` URLs. The app automatically converts it to `postgresql://` for SQLAlchemy compatibility.

### Step 4 — Set Environment Variables

In your Render Web Service → **Environment** tab, add:

```
SECRET_KEY              = <long random string>
DATABASE_URL            = <your render postgres internal URL>
OPENAI_API_KEY          = sk-...          (optional)
AWS_ACCESS_KEY_ID       = ...             (optional)
AWS_SECRET_ACCESS_KEY   = ...             (optional)
S3_BUCKET_NAME          = ...             (optional)
EMAIL_USER              = ...             (optional)
EMAIL_PASS              = ...             (optional)
MAINTENANCE_MODE        = false
```

### Step 5 — Deploy

Click **Deploy**. Render will build and start the app using Gunicorn.

Your app will be live at `https://your-app-name.onrender.com`.

---

## Project Structure

```
/
├── run.py                  # App entry point
├── requirements.txt        # Python dependencies
├── Procfile                # For Heroku (web: gunicorn run:app)
├── tests.py                # Unit tests
├── ai_manager.py           # AI autonomous code review agent
├── backup.py               # PostgreSQL → S3 backup script
├── monitor.py              # Health check + email alert script
├── status_page.html        # Standalone status page
└── blog/
    ├── __init__.py         # App factory, extensions init
    ├── models.py           # DB models (User, Post, Comment, Like, etc.)
    ├── routes.py           # All routes and view logic
    ├── templates_data.py   # HTML templates as Python strings
    ├── s3_helpers.py       # AWS S3 upload helpers
    └── static/
        └── uploads/        # Local image storage (dev only)
```

---

## Health Check

The app exposes a `/healthz` endpoint that returns:

```json
{
  "app": "ok",
  "database": "ok"
}
```

Used by `monitor.py` and the `status_page.html` for uptime monitoring.

---

## Maintenance Mode

Set `MAINTENANCE_MODE=true` in your environment variables to serve a 503 page to all non-admin users. Admins can still access the site.

---

## Automated Backups

Run `backup.py` manually or schedule it via cron / Render Cron Jobs:

```bash
python backup.py
```

Requires `DATABASE_URL`, `S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` to be set.

---

## License

MIT
