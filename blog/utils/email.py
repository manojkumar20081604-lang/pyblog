import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from blog.models import EmailLog
from blog.extensions import db

logger = logging.getLogger(__name__)


def send_email(recipient, subject, body_html, body_text=None):
    try:
        mail_server = current_blog.config.get('MAIL_SERVER')
        mail_port = current_blog.config.get('MAIL_PORT')
        mail_username = current_blog.config.get('MAIL_USERNAME')
        mail_password = current_blog.config.get('MAIL_PASSWORD')
        mail_use_tls = current_blog.config.get('MAIL_USE_TLS', True)
        
        if not all([mail_server, mail_port, mail_username, mail_password]):
            logger.warning('Email configuration incomplete')
            log_email(recipient, subject, 'skipped', 'Configuration incomplete')
            return False
        
        msg = MIMEMultipart('alternative')
        msg['From'] = current_blog.config.get('MAIL_DEFAULT_SENDER') or mail_username
        msg['To'] = recipient
        msg['Subject'] = subject
        
        if body_text:
            msg.attach(MIMEText(body_text, 'plain'))
        msg.attach(MIMEText(body_html, 'html'))
        
        with smtplib.SMTP(mail_server, mail_port) as server:
            if mail_use_tls:
                server.starttls()
            server.login(mail_username, mail_password)
            server.send_message(msg)
        
        log_email(recipient, subject, 'sent')
        logger.info(f'Email sent to {recipient}: {subject}')
        return True
        
    except Exception as e:
        logger.error(f'Failed to send email to {recipient}: {str(e)}')
        log_email(recipient, subject, 'failed', str(e))
        return False


def log_email(recipient, subject, status, error=None):
    try:
        log = EmailLog(
            recipient=recipient,
            subject=subject,
            status=status,
            error_message=error
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        logger.error(f'Failed to log email: {str(e)}')


def send_welcome_email(user):
    subject = 'Welcome to PyBlog!'
    body_html = f'''
    <html>
    <body>
        <h1>Welcome, {user.username}!</h1>
        <p>Thank you for joining PyBlog. We're excited to have you!</p>
        <p>Start by creating your first post and sharing your thoughts with the world.</p>
        <a href="{get_base_url()}/">Get Started</a>
    </body>
    </html>
    '''
    return send_email(user.email, subject, body_html)


def send_password_reset_email(user, token):
    reset_url = f"{get_base_url()}/reset_password/{token}"
    subject = 'Reset Your Password'
    body_html = f'''
    <html>
    <body>
        <h1>Password Reset Request</h1>
        <p>Hi {user.username},</p>
        <p>You requested a password reset. Click the link below to reset your password:</p>
        <a href="{reset_url}">Reset Password</a>
        <p>This link will expire in 30 minutes.</p>
        <p>If you didn't request this, please ignore this email.</p>
    </body>
    </html>
    '''
    return send_email(user.email, subject, body_html)


def send_notification_email(user, notification_type, message):
    subject = f'New {notification_type} on PyBlog'
    body_html = f'''
    <html>
    <body>
        <h1>{subject}</h1>
        <p>{message}</p>
        <a href="{get_base_url()}/notifications">View Notifications</a>
    </body>
    </html>
    '''
    return send_email(user.email, subject, body_html)


def get_base_url():
    from flask import request
    return request.host_url.rstrip('/')
