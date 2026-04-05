from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from blog.extensions import db
from blog.models import User, UserRole, Notification
from blog.utils.forms import RegisterForm, LoginForm, PasswordResetRequestForm, PasswordResetForm, ProfileForm
from blog.utils.email import send_welcome_email, send_password_reset_email
from blog.utils.decorators import admin_required, rate_limit

auth = Blueprint('auth', __name__, url_prefix='/auth')


@auth.route('/register', methods=['GET', 'POST'])
@rate_limit("5 per minute")
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = RegisterForm()
    if form.validate_on_submit():
        is_first_user = User.query.count() == 0
        role = UserRole.ADMIN.value if is_first_user else UserRole.USER.value
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role=role
        )
        user.set_password(form.password.data)
        
        db.session.add(user)
        db.session.commit()
        
        send_welcome_email(user)
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
@rate_limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Contact admin.', 'danger')
                return render_template('auth/login.html', form=form)
            
            login_user(user, remember=form.remember.data)
            
            next_page = request.args.get('next')
            flash(f'Welcome back, {user.username}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('main.index'))
        
        flash('Invalid username or password', 'danger')
    
    return render_template('auth/login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/reset_password', methods=['GET', 'POST'])
@rate_limit("3 per hour")
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        
        if user:
            token = user.get_reset_token
            send_password_reset_email(user, token)
        
        flash('If an account exists with that email, you will receive password reset instructions.', 'info')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_request.html', form=form)


@auth.route('/reset_password/<token>', methods=['GET', 'POST'])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    user = User.verify_reset_token(token)
    if not user:
        flash('That is an invalid or expired token', 'warning')
        return redirect(url_for('auth.reset_request'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been updated! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/reset_password.html', form=form)


@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    
    if form.validate_on_submit():
        current_user.bio = form.bio.data
        current_user.profile_pic = form.profile_pic.data
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    if request.method == 'GET':
        form.bio.data = current_user.bio
        form.profile_pic.data = current_user.profile_pic
    
    return render_template('auth/profile.html', form=form)


@auth.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    user_id = current_user.id
    logout_user()
    user = User.query.get(user_id)
    user.soft_delete()
    db.session.commit()
    flash('Your account has been deleted.', 'info')
    return redirect(url_for('main.index'))
