import bleach
import re
from wtforms import StringField, PasswordField, TextAreaField, SubmitField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError, Optional
from flask_wtf import FlaskForm


ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'a', 'img']
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'rel'],
    'img': ['src', 'alt', 'title', 'width', 'height'],
}


def sanitize_html(content):
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)


def generate_slug(title):
    slug = re.sub(r'[^\w\s-]', '', title.lower())
    slug = re.sub(r'[-\s]+', '-', slug)
    return slug.strip('-')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(message='Username is required'),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters')
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    submit = SubmitField('Sign Up')
    
    def validate_username(self, username):
        from blog.models import User
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken')
    
    def validate_email(self, email):
        from blog.models import User
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')


class PostForm(FlaskForm):
    title = StringField('Title', validators=[
        DataRequired(message='Title is required'),
        Length(max=200, message='Title cannot exceed 200 characters')
    ])
    content = TextAreaField('Content', validators=[
        DataRequired(message='Content is required')
    ])
    tags = StringField('Tags (comma separated)', validators=[Optional()])
    image = SelectField('Image', choices=[('', 'No Image')], coerce=str)
    submit_publish = SubmitField('Publish')
    submit_draft = SubmitField('Save Draft')
    
    def validate_title(self, title):
        if len(title.data.strip()) < 5:
            raise ValidationError('Title must be at least 5 characters')


class CommentForm(FlaskForm):
    content = TextAreaField('Comment', validators=[
        DataRequired(message='Comment cannot be empty'),
        Length(max=1000, message='Comment cannot exceed 1000 characters')
    ])
    submit = SubmitField('Post Comment')


class ProfileForm(FlaskForm):
    bio = TextAreaField('Bio', validators=[Optional(), Length(max=500)])
    profile_pic = StringField('Profile Picture URL', validators=[Optional()])
    submit = SubmitField('Update Profile')


class ContactForm(FlaskForm):
    name = StringField('Name', validators=[
        DataRequired(message='Name is required'),
        Length(max=100)
    ])
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email()
    ])
    subject = StringField('Subject', validators=[
        DataRequired(message='Subject is required'),
        Length(max=200)
    ])
    message = TextAreaField('Message', validators=[
        DataRequired(message='Message is required'),
        Length(min=10, max=5000)
    ])
    submit = SubmitField('Send Message')


class PasswordResetRequestForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(),
        Email()
    ])
    submit = SubmitField('Request Password Reset')


class PasswordResetForm(FlaskForm):
    password = PasswordField('New Password', validators=[
        DataRequired(),
        Length(min=8)
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password')
    ])
    submit = SubmitField('Reset Password')


class AdminUserForm(FlaskForm):
    role = SelectField('Role', choices=[
        ('user', 'User'),
        ('moderator', 'Moderator'),
        ('admin', 'Admin')
    ])
    is_active = BooleanField('Active')
    submit = SubmitField('Update User')
