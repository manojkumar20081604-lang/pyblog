from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required
from blog.extensions import db
from blog.models import User, Post, Comment, Notification, EmailLog
from blog.utils.forms import AdminUserForm
from blog.utils.decorators import admin_required, rate_limit

admin = Blueprint('admin', __name__, url_prefix='/admin')


@admin.route('/')
@login_required
@admin_required
def index():
    stats = {
        'total_users': User.query.filter_by(deleted_at=None).count(),
        'total_posts': Post.query.filter_by(deleted_at=None).count(),
        'total_comments': Comment.query.filter_by(deleted_at=None).count(),
        'published_posts': Post.query.filter_by(is_published=True, deleted_at=None).count(),
        'draft_posts': Post.query.filter_by(is_published=False, deleted_at=None).count(),
    }
    recent_users = User.query.filter_by(deleted_at=None).order_by(
        User.created_at.desc()
    ).limit(5).all()
    recent_posts = Post.query.filter_by(deleted_at=None).order_by(
        Post.created_at.desc()
    ).limit(5).all()
    
    return render_template('admin/index.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_posts=recent_posts)


@admin.route('/users')
@login_required
@admin_required
def users():
    page = request.args.get('page', 1, type=int)
    pagination = User.query.filter_by(deleted_at=None).order_by(
        User.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/users.html',
                         users=pagination.items,
                         pagination=pagination)


@admin.route('/users/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    form = AdminUserForm()
    
    if form.validate_on_submit():
        user.role = form.role.data
        user.is_active = form.is_active.data
        db.session.commit()
        flash(f'User {user.username} updated!', 'success')
        return redirect(url_for('admin.users'))
    
    if request.method == 'GET':
        form.role.data = user.role
        form.is_active.data = user.is_active
    
    return render_template('admin/edit_user.html', form=form, user=user)


@admin.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if user.is_admin:
        flash('Cannot delete an admin user!', 'danger')
        return redirect(url_for('admin.users'))
    
    user.soft_delete()
    db.session.commit()
    flash(f'User {user.username} deleted.', 'success')
    return redirect(url_for('admin.users'))


@admin.route('/posts')
@login_required
@admin_required
def posts():
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.filter_by(deleted_at=None).order_by(
        Post.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/posts.html',
                         posts=pagination.items,
                         pagination=pagination)


@admin.route('/comments')
@login_required
@admin_required
def comments():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.filter_by(deleted_at=None).order_by(
        Comment.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    return render_template('admin/comments.html',
                         comments=pagination.items,
                         pagination=pagination)


@admin.route('/notifications')
@login_required
@admin_required
def all_notifications():
    page = request.args.get('page', 1, type=int)
    pagination = Notification.query.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=30, error_out=False)
    
    return render_template('admin/notifications.html',
                         notifications=pagination.items,
                         pagination=pagination)


@admin.route('/logs/email')
@login_required
@admin_required
def email_logs():
    page = request.args.get('page', 1, type=int)
    pagination = EmailLog.query.order_by(
        EmailLog.created_at.desc()
    ).paginate(page=page, per_page=30, error_out=False)
    
    return render_template('admin/email_logs.html',
                         logs=pagination.items,
                         pagination=pagination)


@admin.route('/stats')
@login_required
@admin_required
def stats():
    from sqlalchemy import func
    
    posts_by_month = db.session.query(
        func.strftime('%Y-%m', Post.created_at).label('month'),
        func.count(Post.id).label('count')
    ).filter_by(deleted_at=None).group_by('month').order_by('month desc').limit(12).all()
    
    users_by_role = db.session.query(
        User.role,
        func.count(User.id).label('count')
    ).filter_by(deleted_at=None).group_by(User.role).all()
    
    return render_template('admin/stats.html',
                         posts_by_month=posts_by_month,
                         users_by_role=users_by_role)
