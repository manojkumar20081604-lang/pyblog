import unittest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blog_app import app, db, User, Post, Comment, Like

class BlogTestCase(unittest.TestCase):
    def setUp(self):
        """Set up a temporary database before each test."""
        self.app = app
        self.app.config['TESTING'] = True
        self.app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for easier testing
        self.app.config['SECRET_KEY'] = 'test-secret' # Needed for password reset tokens

        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create all tables in the in-memory database
        db.create_all()

        # Create some users for tests
        self.user1 = self._create_user('user1', 'user1@test.com', 'pass1')
        self.user2 = self._create_user('user2', 'user2@test.com', 'pass2')
        self.admin = self._create_user('admin', 'admin@test.com', 'adminpass', is_admin=True)

    def tearDown(self):
        """Clean up the database after each test."""
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    # --- HELPER METHODS ---
    def _create_user(self, username, email, password, is_admin=False):
        user = User(username=username, email=email, is_admin=is_admin)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    def _login(self, username, password):
        return self.client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)

    def _logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def _create_post(self, user_id, title, content):
        post = Post(title=title, content=content, author_id=user_id)
        db.session.add(post)
        db.session.commit()
        return post

    def test_index_page(self):
        """Test that the homepage loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PyBlog', response.data)

    def test_user_registration(self):
        """Test user registration."""
        response = self.client.post('/register', data={
            'username': 'newuser',
            'email': 'new@example.com',
            'password': 'password123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Registration successful', response.data)

        user = User.query.filter_by(username='newuser').first()
        self.assertIsNotNone(user)

    def test_login_logout(self):
        """Test login and logout functionality."""
        response = self._login('user1', 'pass1')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Hi, user1', response.data)

        response = self._logout()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)
        self.assertNotIn(b'Hi, user1', response.data)

    def test_create_and_edit_post(self):
        """Test creating and editing a post."""
        self._login('user1', 'pass1')

        # Create post
        response = self.client.post('/create', data={
            'title': 'Original Title',
            'content': 'Original content.',
            'action': 'publish'
        }, follow_redirects=True)
        post = Post.query.filter_by(title='Original Title').first()
        self.assertIsNotNone(post)

        # Edit post
        response = self.client.post(f'/post/{post.id}/edit', data={
            'title': 'Edited Title',
            'content': 'Edited content.'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your post has been updated!', response.data)
        self.assertIn(b'Edited Title', response.data)
        self.assertNotIn(b'Original Title', response.data)

    # --- NEW COMPREHENSIVE TESTS ---

    def test_commenting_and_liking(self):
        """Test commenting on and liking a post."""
        post = self._create_post(self.user1.id, 'A Post to Comment On', 'Some content')
        self._login('user2', 'pass2')

        # Comment
        self.client.post(f'/post/{post.id}/comment', data={'content': 'A test comment'}, follow_redirects=True)
        comment = Comment.query.filter_by(post_id=post.id).first()
        self.assertIsNotNone(comment)
        self.assertEqual(comment.content, 'A test comment')

        # Like post
        self.client.post(f'/post/{post.id}/like', follow_redirects=True)
        like = Like.query.filter_by(post_id=post.id, user_id=self.user2.id).first()
        self.assertIsNotNone(like)

        # Unlike post
        self.client.post(f'/post/{post.id}/like', follow_redirects=True)
        like = Like.query.filter_by(post_id=post.id, user_id=self.user2.id).first()
        self.assertIsNone(like)

    def test_admin_permissions(self):
        """Test admin permissions and restrictions for normal users."""
        # Login as admin
        self._login('admin', 'adminpass')
        response = self.client.get('/admin', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Admin Dashboard', response.data)
        self._logout()

        # Login as normal user
        self._login('user1', 'pass1')
        response = self.client.get('/admin')
        self.assertEqual(response.status_code, 403) # Forbidden

    def test_sitemap_rss_health_endpoints(self):
        """Test the XML and health check endpoints."""
        # Sitemap
        response = self.client.get('/sitemap.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/xml')

        # RSS
        response = self.client.get('/feed.xml')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, 'application/xml')

        # Health Check
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['app'], 'ok')
        self.assertEqual(response.json['database'], 'ok')

    def test_account_deletion(self):
        """Test that a user can delete their own account."""
        user_to_delete = self._create_user('deleteme', 'delete@me.com', 'password')
        user_id = user_to_delete.id
        self._login('deleteme', 'password')

        response = self.client.post('/delete_account', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your account has been permanently deleted.', response.data)

        # Verify user is gone from DB
        deleted_user = User.query.get(user_id)
        self.assertIsNone(deleted_user)

if __name__ == '__main__':
    unittest.main()