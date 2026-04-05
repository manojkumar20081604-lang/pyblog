from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, send_from_directory
from flask_login import login_required, current_user
from sqlalchemy import or_, func
from blog.extensions import db, cache
from blog.models import Post, Comment, Like, Tag, User, Notification
from blog.utils.forms import PostForm, CommentForm, ContactForm
from blog.utils.images import save_image, delete_image
from blog.utils.forms import sanitize_html, generate_slug
from blog.utils.decorators import admin_required, rate_limit, log_action

main = Blueprint('main', __name__)


@main.route('/')
@cache.cached(timeout=60, query_string=True)
def index():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search_query = request.args.get('q')
    tag_query = request.args.get('tag')
    
    query = Post.query.filter_by(is_published=True, deleted_at=None)
    
    if search_query:
        query = query.filter(
            or_(
                Post.title.ilike(f'%{search_query}%'),
                Post.content.ilike(f'%{search_query}%')
            )
        )
    
    if tag_query:
        query = query.join(Post.tags).filter(Tag.name == tag_query)
    
    pagination = query.order_by(Post.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    tags = Tag.query.limit(20).all()
    popular_posts = Post.query.filter_by(is_published=True, deleted_at=None)\
        .order_by(Post.views.desc()).limit(5).all()
    
    return render_template('main/index.html',
                         posts=pagination.items,
                         pagination=pagination,
                         tags=tags,
                         popular_posts=popular_posts,
                         search_query=search_query,
                         tag_query=tag_query)


@main.route('/post/<int:post_id>', methods=['GET'])
@cache.cached(timeout=300, query_string=True)
def view_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.deleted_at:
        abort(404)
    
    if not post.is_published:
        if not current_user.is_authenticated or \
           (current_user.id != post.user_id and not current_user.is_admin):
            abort(403)
    
    post.increment_views()
    
    comment_page = request.args.get('comment_page', 1, type=int)
    comments_pagination = Comment.query.filter_by(
        post_id=post.id, deleted_at=None
    ).order_by(Comment.created_at.desc()).paginate(
        page=comment_page, per_page=10, error_out=False
    )
    
    user_has_liked = False
    if current_user.is_authenticated:
        user_has_liked = Like.query.filter_by(
            user_id=current_user.id, post_id=post.id
        ).first() is not None
    
    return render_template('main/post.html',
                         post=post,
                         comments_pagination=comments_pagination,
                         user_has_liked=user_has_liked)


@main.route('/create', methods=['GET', 'POST'])
@login_required
@rate_limit("10 per hour")
def create_post():
    form = PostForm()
    
    if form.validate_on_submit():
        slug = generate_slug(form.title.data)
        
        existing = Post.query.filter_by(slug=slug).first()
        if existing:
            slug = f"{slug}-{Post.query.count()}"
        
        post = Post(
            title=form.title.data,
            content=sanitize_html(form.content.data),
            slug=slug,
            user_id=current_user.id
        )
        
        tags_input = form.tags.data
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                post.tags.append(tag)
        
        action = request.form.get('action')
        post.is_published = (action == 'submit_publish')
        
        db.session.add(post)
        db.session.commit()
        
        flash('Post created successfully!', 'success')
        return redirect(url_for('main.index'))
    
    return render_template('main/create_post.html', form=form)


@main.route('/post/<int:post_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    form = PostForm()
    
    if form.validate_on_submit():
        post.title = form.title.data
        post.content = sanitize_html(form.content.data)
        post.slug = generate_slug(form.title.data)
        
        tags_input = form.tags.data
        post.tags.clear()
        if tags_input:
            tag_names = [t.strip() for t in tags_input.split(',') if t.strip()]
            for name in tag_names:
                tag = Tag.query.filter_by(name=name).first()
                if not tag:
                    tag = Tag(name=name)
                    db.session.add(tag)
                post.tags.append(tag)
        
        action = request.form.get('action')
        post.is_published = (action == 'submit_publish')
        
        db.session.commit()
        flash('Post updated!', 'success')
        return redirect(url_for('main.view_post', post_id=post.id))
    
    if request.method == 'GET':
        form.title.data = post.title
        form.content.data = post.content
        form.tags.data = ', '.join([tag.name for tag in post.tags])
    
    return render_template('main/edit_post.html', form=form, post=post)


@main.route('/post/<int:post_id>/delete', methods=['POST'])
@login_required
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    if post.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    post.soft_delete()
    db.session.commit()
    flash('Post deleted.', 'success')
    return redirect(url_for('main.index'))


@main.route('/post/<int:post_id>/comment', methods=['POST'])
@login_required
def add_comment(post_id):
    form = CommentForm()
    if form.validate_on_submit():
        post = Post.query.get_or_404(post_id)
        
        comment = Comment(
            content=form.content.data,
            user_id=current_user.id,
            post_id=post.id
        )
        db.session.add(comment)
        
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                actor_id=current_user.id,
                post_id=post.id,
                type='comment',
                message=f'{current_user.username} commented on your post: {post.title}'
            )
            db.session.add(notification)
        
        db.session.commit()
        flash('Comment added!', 'success')
    
    return redirect(url_for('main.view_post', post_id=post_id))


@main.route('/comment/<int:comment_id>/delete', methods=['POST'])
@login_required
def delete_comment(comment_id):
    comment = Comment.query.get_or_404(comment_id)
    
    if comment.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    post_id = comment.post_id
    comment.soft_delete()
    db.session.commit()
    flash('Comment deleted.', 'success')
    return redirect(url_for('main.view_post', post_id=post_id))


@main.route('/post/<int:post_id>/like', methods=['POST'])
@login_required
def like_post(post_id):
    post = Post.query.get_or_404(post_id)
    
    existing_like = Like.query.filter_by(
        user_id=current_user.id, post_id=post.id
    ).first()
    
    if existing_like:
        db.session.delete(existing_like)
        message = 'Like removed.'
    else:
        like = Like(user_id=current_user.id, post_id=post.id)
        db.session.add(like)
        
        if post.user_id != current_user.id:
            notification = Notification(
                user_id=post.user_id,
                actor_id=current_user.id,
                post_id=post.id,
                type='like',
                message=f'{current_user.username} liked your post: {post.title}'
            )
            db.session.add(notification)
        
        message = 'Like added!'
    
    db.session.commit()
    flash(message, 'success')
    return redirect(url_for('main.view_post', post_id=post_id))


@main.route('/drafts')
@login_required
def drafts():
    posts = Post.query.filter_by(
        user_id=current_user.id, is_published=False, deleted_at=None
    ).order_by(Post.created_at.desc()).all()
    
    return render_template('main/drafts.html', posts=posts)


@main.route('/user/<string:username>')
@cache.cached(timeout=60)
def user_profile(username):
    user = User.query.filter_by(username=username, deleted_at=None).first_or_404()
    
    page = request.args.get('page', 1, type=int)
    pagination = Post.query.filter_by(
        user_id=user.id, is_published=True, deleted_at=None
    ).order_by(Post.created_at.desc()).paginate(
        page=page, per_page=10, error_out=False
    )
    
    return render_template('main/user_profile.html',
                         user=user,
                         posts=pagination.items,
                         pagination=pagination)


@main.route('/follow/<username>', methods=['POST'])
@login_required
def follow_user(username):
    user = User.query.filter_by(username=username, deleted_at=None).first_or_404()
    
    if user == current_user:
        flash('You cannot follow yourself!', 'warning')
        return redirect(url_for('main.user_profile', username=username))
    
    current_user.follow(user)
    db.session.commit()
    
    notification = Notification(
        user_id=user.id,
        actor_id=current_user.id,
        type='follow',
        message=f'{current_user.username} started following you'
    )
    db.session.add(notification)
    db.session.commit()
    
    flash(f'You are now following {username}!', 'success')
    return redirect(url_for('main.user_profile', username=username))


@main.route('/unfollow/<username>', methods=['POST'])
@login_required
def unfollow_user(username):
    user = User.query.filter_by(username=username, deleted_at=None).first_or_404()
    
    current_user.unfollow(user)
    db.session.commit()
    flash(f'You have unfollowed {username}.', 'info')
    return redirect(url_for('main.user_profile', username=username))


@main.route('/notifications')
@login_required
def notifications():
    page = request.args.get('page', 1, type=int)
    pagination = current_user.notifications.order_by(
        Notification.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    for notif in pagination.items:
        notif.is_read = True
    db.session.commit()
    
    return render_template('main/notifications.html', notifications=pagination.items, pagination=pagination)


@main.route('/contact', methods=['GET', 'POST'])
def contact():
    form = ContactForm()
    
    if form.validate_on_submit():
        flash('Message sent successfully! We will get back to you soon.', 'success')
        return redirect(url_for('main.contact'))
    
    return render_template('main/contact.html', form=form)


@main.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)


@main.route('/sitemap.xml')
def sitemap():
    posts = Post.query.filter_by(is_published=True, deleted_at=None)\
        .order_by(Post.created_at.desc()).all()
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    for post in posts:
        url = url_for('main.view_post', post_id=post.id, _external=True)
        xml += f'  <url><loc>{url}</loc></url>\n'
    
    xml += '</urlset>'
    return xml, 200, {'Content-Type': 'application/xml'}


@main.route('/feed.xml')
def feed():
    posts = Post.query.filter_by(is_published=True, deleted_at=None)\
        .order_by(Post.created_at.desc()).limit(20).all()
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<rss version="2.0">\n'
    xml += '<channel>\n'
    xml += '<title>PyBlog</title>\n'
    xml += f'<link>{url_for("main.index", _external=True)}</link>\n'
    xml += '<description>Latest articles from PyBlog</description>\n'
    
    for post in posts:
        url = url_for('main.view_post', post_id=post.id, _external=True)
        xml += f'<item><title>{post.title}</title><link>{url}</link>'
        xml += f'<description>{post.excerpt}</description></item>\n'
    
    xml += '</channel>\n</rss>'
    return xml, 200, {'Content-Type': 'application/xml'}
