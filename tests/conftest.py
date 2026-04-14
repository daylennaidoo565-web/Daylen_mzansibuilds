"""
conftest.py — pytest fixtures for MzansiBuilds tests.

Sets up an in-memory SQLite database for every test so the real
mzansibuilds.db is never touched. Every test gets a fresh clean database.
"""

import pytest
from app import app as flask_app
from extensions import db as _db
from models import User, Project, Milestone, Comment
from werkzeug.security import generate_password_hash


@pytest.fixture
def app():
    """
    Configure Flask app for testing.
    Uses in-memory SQLite — isolated from the real database.
    FLASK_DEBUG is set to 1 so hCaptcha is bypassed during tests.
    Without this, login would fail in CI because there is no real captcha token.
    """
    flask_app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'WTF_CSRF_ENABLED': False,
        'SECRET_KEY': 'test-secret-key',
        'FLASK_DEBUG': '1',  # bypasses hCaptcha verification in app.py
    })

    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.drop_all()


@pytest.fixture
def client(app):
    """Flask test client — simulates browser requests in tests."""
    return app.test_client()


@pytest.fixture
def registered_user(app):
    """
    Creates a test user in the in-memory database.
    Returns their credentials so login tests can use them.
    """
    with app.app_context():
        user = User(
            username='testuser',
            email='test@example.com',
            password_hash=generate_password_hash('Password123')
        )
        _db.session.add(user)
        _db.session.commit()

    return {
        'username': 'testuser',
        'email': 'test@example.com',
        'password': 'Password123'
    }


@pytest.fixture
def logged_in_client(app, client, registered_user):
    """
    A test client that is already logged in as testuser.
    Use this fixture for tests that require authentication.
    """
    client.post('/login', data={
        'email': registered_user['email'],
        'password': registered_user['password']
    }, follow_redirects=True)
    return client


@pytest.fixture
def sample_project(app, registered_user):
    """
    Creates a sample project owned by testuser.
    Use alongside logged_in_client for project-related tests.
    """
    with app.app_context():
        user = User.query.filter_by(email=registered_user['email']).first()
        project = Project(
            title='Test Project',
            description='A test project for automated testing.',
            stage='In Progress',
            support_needed='Need help with testing.',
            completed=False,
            user_id=user.id
        )
        _db.session.add(project)
        _db.session.commit()
        return project.id  # return ID — not the object (session may close)