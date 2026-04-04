import os
import logging
from flask import Flask
from logging import StreamHandler
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Initialize extensions (unbound)
db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'login'

def create_app():
    app = Flask(__name__)

    # Configuration
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this-in-prod')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///blog_database.db')
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
        app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = 'blog/static/uploads' # For local development
    app.config['S3_BUCKET'] = os.environ.get('S3_BUCKET_NAME')
    app.config['S3_LOCATION'] = f"https://{app.config['S3_BUCKET']}.s3.amazonaws.com/" if app.config['S3_BUCKET'] else None

    # Initialize extensions with app
    db.init_app(app)
    login_manager.init_app(app)

    @app.before_request
    def check_for_maintenance():
        from flask import request, render_template_string
        from flask_login import current_user
        from blog.templates_data import MAINTENANCE_HTML

        # Check if maintenance mode is enabled via environment variable
        if os.environ.get('MAINTENANCE_MODE', 'false').lower() == 'true':
            # Define endpoints that should always be accessible
            allowed_endpoints = ['static', 'health_check', 'login']

            # Allow access to allowed endpoints
            if request.endpoint in allowed_endpoints:
                return

            # Allow access for authenticated admins
            if current_user.is_authenticated and hasattr(current_user, 'is_admin') and current_user.is_admin:
                return

            # For all other requests, render the maintenance page
            return render_template_string(MAINTENANCE_HTML), 503

    if not app.debug and not app.testing:
        # Production logging to stdout
        handler = StreamHandler()
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        )
        handler.setFormatter(formatter)
        app.logger.addHandler(handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('PyBlog startup')

    @app.context_processor
    def utility_processor():
        from flask import url_for
        def get_image_url(filename):
            if app.config.get('S3_LOCATION') and filename:
                return app.config['S3_LOCATION'] + filename
            elif filename:
                return url_for('uploaded_file', filename=filename)
            return None
        return dict(get_image_url=get_image_url, google_analytics_id=os.environ.get('GOOGLE_ANALYTICS_ID'))

    # Register blueprints/routes (Import inside function to avoid circular imports)
    with app.app_context():
        from blog import routes, models
        db.create_all()
        # Only create local uploads folder if not using S3
        if not app.config['S3_BUCKET']:
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])

    return app