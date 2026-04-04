# PyBlog

A modern Flask blog application with security, caching, and deployment ready.

## Features

- User authentication with roles (User/Moderator/Admin)
- Create, edit, delete blog posts
- Comments and likes system
- User follow system
- Notifications
- Image upload with compression
- Rate limiting and CSRF protection
- HTML sanitization
- SEO optimized (sitemap, RSS feed)
- Caching with Redis
- Email notifications
- Admin dashboard

## Deployment on Render

1. Fork/clone this repo
2. Create a new Web Service on [Render](https://render.com)
3. Connect your GitHub repo
4. Add environment variables:
   - `SECRET_KEY` - Generate a secure key
   - `DATABASE_URL` - PostgreSQL connection string
   - `FLASK_ENV=production`
5. Deploy!

Or use `render.yaml` for Blueprint deployment (creates DB automatically).

## Local Development

```bash
# Clone and install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your values

# Initialize database
flask db init
flask db migrate
flask db upgrade

# Run
python run.py
```

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `SECRET_KEY` | Flask secret key |
| `DATABASE_URL` | PostgreSQL connection string |
| `MAIL_*` | SMTP email settings (optional) |

## Tech Stack

- Flask 3.0
- SQLAlchemy
- Flask-Login
- Flask-Migrate
- Bootstrap 5
- PostgreSQL
- Redis (optional)

## License

MIT
