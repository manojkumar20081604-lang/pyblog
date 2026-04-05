from datetime import datetime
from enum import Enum
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from blog.extensions import db


class UserRole(Enum):
    USER = 'user'
    MODERATOR = 'moderator'
    ADMIN = 'admin'


class SoftDeleteMixin:
    deleted_at = db.Column(db.DateTime, nullable=True)
    
    @property
    def is_deleted(self):
        return self.deleted_at is not None
    
    def soft_delete(self):
        self.deleted_at = datetime.utcnow()
    
    def restore(self):
        self.deleted_at = None


post_tags = db.Table('post_tags',
    db.Column('post_id', db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), primary_key=True),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id', ondelete='CASCADE'), primary_key=True)
)

followers = db.Table('followers',
    db.Column('follower_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True),
    db.Column('followed_id', db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), primary_key=True)
)


class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class User(SoftDeleteMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default=UserRole.USER.value, index=True)
    bio = db.Column(db.Text, nullable=True)
    profile_pic = db.Column(db.String(100), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    posts = db.relationship('Post', backref='author', lazy='dynamic', foreign_keys='Post.user_id')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    likes = db.relationship('Like', backref='user', lazy='dynamic')
    notifications = db.relationship('Notification', foreign_keys='Notification.user_id', 
                                   backref='recipient', lazy='dynamic')
    
    followed = db.relationship(
        'User', secondary=followers,
        primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        backref=db.backref('followers', lazy='dynamic'), lazy='dynamic')
    
    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN.value
    
    @property
    def is_moderator(self):
        return self.role in [UserRole.MODERATOR.value, UserRole.ADMIN.value]
    
    @property
    def get_reset_token(self):
        s = URLSafeTimedSerializer(__name__)
        return s.dumps({'user_id': self.id}, salt='password-reset-salt')
    
    @staticmethod
    def verify_reset_token(token, expires_sec=1800):
        s = URLSafeTimedSerializer(__name__)
        try:
            user_id = s.loads(token, salt='password-reset-salt', max_age=expires_sec)['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def follow(self, user):
        if not self.is_following(user):
            self.followed.append(user)
    
    def unfollow(self, user):
        if self.is_following(user):
            self.followed.remove(user)
    
    def is_following(self, user):
        return self.followed.filter(followers.c.followed_id == user.id).count() > 0
    
    def get_notification_count(self):
        return self.notifications.filter_by(is_read=False).count()
    
    def __repr__(self):
        return f'<User {self.username}>'


class Post(SoftDeleteMixin, db.Model):
    __tablename__ = 'post'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    image_file = db.Column(db.String(100), nullable=True)
    slug = db.Column(db.String(220), unique=True, index=True)
    is_published = db.Column(db.Boolean, default=True, index=True)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    comments = db.relationship('Comment', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    likes = db.relationship('Like', backref='post', lazy='dynamic', cascade="all, delete-orphan")
    tags = db.relationship('Tag', secondary=post_tags, lazy='subquery',
                           backref=db.backref('posts', lazy=True))
    
    __table_args__ = (
        db.Index('ix_post_user_published', 'user_id', 'is_published'),
        db.Index('ix_post_created_published', 'created_at', 'is_published'),
    )
    
    @property
    def like_count(self):
        return self.likes.count()
    
    @property
    def comment_count(self):
        return self.comments.count()
    
    @property
    def excerpt(self):
        return self.content[:200] + '...' if len(self.content) > 200 else self.content
    
    def increment_views(self):
        self.views += 1
        db.session.commit()
    
    def __repr__(self):
        return f'<Post {self.title}>'


class Comment(SoftDeleteMixin, db.Model):
    __tablename__ = 'comment'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.Index('ix_comment_post_created', 'post_id', 'created_at'),
    )
    
    def __repr__(self):
        return f'<Comment {self.id}>'


class Like(db.Model):
    __tablename__ = 'like'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_like'),
    )
    
    def __repr__(self):
        return f'<Like user={self.user_id} post={self.post_id}>'


class Notification(db.Model):
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False, index=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id', ondelete='CASCADE'), nullable=True)
    type = db.Column(db.String(50), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    is_read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    actor = db.relationship('User', foreign_keys=[actor_id])
    
    def mark_as_read(self):
        self.is_read = True
        db.session.commit()
    
    def __repr__(self):
        return f'<Notification {self.id}: {self.type}>'


class EmailLog(db.Model):
    __tablename__ = 'email_log'
    
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default='sent')
    error_message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<EmailLog {self.id}: {self.status}>'
