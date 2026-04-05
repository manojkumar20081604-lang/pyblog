import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, jsonify
from flask_login import current_user
from blog.config import config

db = __import__('blog.extensions', fromlist=['db']).db
login_manager = __import__('blog.extensions', fromlist=['login_manager']).login_manager
migrate = __import__('blog.extensions', fromlist=['migrate']).migrate
csrf = __import__('blog.extensions', fromlist=['csrf']).csrf
cache = __import__('blog.extensions', fromlist=['cache']).cache
limiter = __import__('blog.extensions', fromlist=['limiter']).limiter


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    init_extensions(app)
    init_blueprints(app)
    init_logging(app)
    init_error_handlers(app)
    init_context_processors(app)
    init_sentry(app)
    
    with app.app_context():
        ensure_upload_folder(app)
    
    return app


def init_extensions(app):
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    
    @login_manager.user_loader
    def load_user(user_id):
        from blog.models import User
        return User.query.get(int(user_id))


def init_blueprints(app):
    from blog.blueprints import auth, main, admin
    
    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(admin)


def init_logging(app):
    log_level = app.config.get('LOG_LEVEL', 'INFO')
    logging.basicConfig(level=getattr(logging, log_level))
    
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        file_handler = RotatingFileHandler(
            'logs/app.log',
            maxBytes=10240000,
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(getattr(logging, log_level))
        app.logger.addHandler(file_handler)
        
        app.logger.setLevel(getattr(logging, log_level))
        app.logger.info('Application startup')


def init_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({'error': 'Not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({'error': 'Forbidden'}), 403
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        return jsonify({'error': 'Rate limit exceeded. Please try again later.'}), 429


def init_context_processors(app):
    @app.context_processor
    def inject_user():
        return dict(current_user=current_user)
    
    @app.context_processor
    def inject_cache():
        from blog.extensions import cache
        return dict(cache=cache)


def init_sentry(app):
    if app.config.get('SENTRY_DSN'):
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        
        sentry_sdk.init(
            dsn=app.config['SENTRY_DSN'],
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.1,
            send_default_pii=False
        )


def ensure_upload_folder(app):
    upload_folder = app.config.get('UPLOAD_FOLDER')
    if upload_folder and not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
