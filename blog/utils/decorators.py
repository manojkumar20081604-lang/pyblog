import logging
import os
from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_login import current_user
from blog.models import UserRole

logger = logging.getLogger(__name__)


def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_admin:
            logger.warning(f'Unauthorized admin access attempt by user {current_user.id}')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def moderator_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login'))
        if not current_user.is_moderator:
            logger.warning(f'Unauthorized moderator access attempt by user {current_user.id}')
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


def owner_or_admin_required(get_owner_id):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'warning')
                return redirect(url_for('auth.login'))
            
            owner_id = get_owner_id(*args, **kwargs)
            if current_user.id != owner_id and not current_user.is_admin:
                logger.warning(f'Unauthorized access attempt by user {current_user.id} to resource owned by {owner_id}')
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def rate_limit(limit_string):
    from blog.extensions import limiter
    return limiter.limit(limit_string)


def cache_key(*args, **kwargs):
    from flask import request
    return f"{request.path}:{request.args.get('page', 1)}"


def log_action(action):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            if current_user.is_authenticated:
                logger.info(f"User {current_user.id} performed {action}")
            return result
        return decorated_function
    return decorator
