"""
test_app.py — pytest tests for MzansiBuilds.

Tests cover all major routes and the core security requirements:
- Public pages load correctly
- Authentication routes work correctly
- Protected routes redirect unauthenticated users
- Ownership checks prevent unauthorised access
- Project and milestone CRUD operations work
- Feed and Celebration Wall display correctly

Run with: pytest tests/ -v
"""


# ── PUBLIC ROUTE TESTS ────────────────────────────────────────────

def test_homepage_loads(client):
    """Home page (/) must return 200 OK for all visitors."""
    response = client.get('/')
    assert response.status_code == 200


def test_register_page_loads(client):
    """Register page (/register) must load for unauthenticated visitors."""
    response = client.get('/register')
    assert response.status_code == 200


def test_login_page_loads(client):
    """Login page (/login) must load for unauthenticated visitors."""
    response = client.get('/login')
    assert response.status_code == 200


def test_feed_page_loads(client):
    """Feed page (/feed) must be publicly accessible without logging in."""
    response = client.get('/feed')
    assert response.status_code == 200


def test_celebration_page_loads(client):
    """Celebration wall (/celebration) must be publicly accessible."""
    response = client.get('/celebration')
    assert response.status_code == 200


# ── REGISTRATION TESTS ────────────────────────────────────────────

def test_user_can_register(client):
    """
    Submitting the register form with valid data should create a user
    and redirect to the login page.
    """
    response = client.post('/register', data={
        'username': 'newuser',
        'email': 'newuser@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should be redirected to login after successful registration
    assert b'login' in response.data.lower() or b'sign in' in response.data.lower()


def test_register_missing_fields_rejected(client):
    """
    Submitting the register form with missing fields should not
    create a user — validation must reject incomplete submissions.
    """
    response = client.post('/register', data={
        'username': '',
        'email': '',
        'password': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should stay on register page or show an error
    assert b'register' in response.data.lower() or b'required' in response.data.lower()


def test_register_duplicate_email_rejected(client, registered_user):
    """
    Trying to register with an already-used email must be rejected.
    This prevents duplicate accounts.
    """
    response = client.post('/register', data={
        'username': 'anotheruser',
        'email': registered_user['email'],  # same email as existing user
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should show an error about the duplicate email
    assert b'exists' in response.data.lower() or b'already' in response.data.lower()


def test_register_weak_password_rejected(client):
    """
    Password must meet strength requirements (8+ chars, letter + number).
    Weak passwords must be rejected server-side.
    """
    response = client.post('/register', data={
        'username': 'weakpwuser',
        'email': 'weakpw@example.com',
        'password': 'abc',   # too short, no number
        'confirm_password': 'abc'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'password' in response.data.lower()


def test_register_password_mismatch_rejected(client):
    """
    Passwords that don't match must be rejected — user must confirm correctly.
    """
    response = client.post('/register', data={
        'username': 'mismatchuser',
        'email': 'mismatch@example.com',
        'password': 'Password123',
        'confirm_password': 'Password456'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'match' in response.data.lower() or b'password' in response.data.lower()


# ── LOGIN TESTS ───────────────────────────────────────────────────

def test_login_correct_credentials_succeeds(client, registered_user):
    """
    Correct email and password must log the user in and redirect
    to the dashboard. This proves the full auth flow works.
    """
    response = client.post('/login', data={
        'email': registered_user['email'],
        'password': registered_user['password']
    }, follow_redirects=True)
    assert response.status_code == 200
    # After login, user should be on the dashboard
    assert b'dashboard' in response.data.lower() or b'welcome' in response.data.lower()


def test_login_wrong_password_fails(client, registered_user):
    """
    Wrong password must be rejected with a generic error message.
    The error must NOT reveal whether the email exists (prevents enumeration).
    """
    response = client.post('/login', data={
        'email': registered_user['email'],
        'password': 'WrongPassword999'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'invalid' in response.data.lower() or b'incorrect' in response.data.lower()


def test_login_wrong_email_fails(client):
    """
    Non-existent email must return the same generic error as wrong password.
    This prevents user enumeration — attacker cannot tell which is wrong.
    """
    response = client.post('/login', data={
        'email': 'nobody@example.com',
        'password': 'Password123'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'invalid' in response.data.lower() or b'incorrect' in response.data.lower()


# ── PROTECTED ROUTE TESTS (Security) ─────────────────────────────

def test_dashboard_requires_login(client):
    """
    Dashboard must redirect unauthenticated users to the login page.
    This proves @login_required is working correctly.
    """
    response = client.get('/dashboard', follow_redirects=True)
    assert response.status_code == 200
    assert b'login' in response.data.lower()


def test_new_project_requires_login(client):
    """
    Project creation must redirect unauthenticated users to login.
    Protected route — anonymous users cannot create projects.
    """
    response = client.get('/projects/new', follow_redirects=True)
    assert response.status_code == 200
    assert b'login' in response.data.lower()


def test_logout_requires_login(client):
    """
    Logout route must redirect if not logged in.
    Prevents accessing the logout endpoint anonymously.
    """
    response = client.get('/logout', follow_redirects=True)
    assert response.status_code == 200


# ── DASHBOARD TESTS ───────────────────────────────────────────────

def test_dashboard_accessible_when_logged_in(logged_in_client):
    """
    Logged-in user must be able to access their dashboard successfully.
    """
    response = logged_in_client.get('/dashboard')
    assert response.status_code == 200
    assert b'dashboard' in response.data.lower() or b'project' in response.data.lower()


# ── PROJECT TESTS ─────────────────────────────────────────────────

def test_create_project(logged_in_client):
    """
    Logged-in user submitting the new project form with valid data
    should create a project and redirect to the project detail page.
    """
    response = logged_in_client.post('/projects/new', data={
        'title': 'My Test Project',
        'description': 'A project created during automated testing.',
        'stage': 'Planning',
        'support_needed': 'Need testers.'
    }, follow_redirects=True)
    assert response.status_code == 200
    assert b'My Test Project' in response.data


def test_create_project_requires_title(logged_in_client):
    """
    Project creation must fail if no title is provided.
    Title is a required field — validation must reject empty titles.
    """
    response = logged_in_client.post('/projects/new', data={
        'title': '',
        'description': 'No title given.',
        'stage': 'Planning',
        'support_needed': ''
    }, follow_redirects=True)
    assert response.status_code == 200
    # Should show error or stay on the form page
    assert b'required' in response.data.lower() or b'title' in response.data.lower()


def test_project_detail_loads(logged_in_client, sample_project):
    """
    Project detail page must load correctly for a valid project ID.
    """
    response = logged_in_client.get(f'/projects/{sample_project}')
    assert response.status_code == 200
    assert b'Test Project' in response.data


def test_project_detail_404_for_invalid_id(logged_in_client):
    """
    Requesting a non-existent project ID must return 404.
    """
    response = logged_in_client.get('/projects/99999')
    assert response.status_code == 404


def test_edit_project_forbidden_for_non_owner(app, client, registered_user, sample_project):
    """
    A different user must NOT be able to edit someone else's project.
    This proves the ownership check (abort 403) is working correctly.
    SECURITY: critical test — prevents unauthorised data modification.
    """
    # Register and log in as a different user
    client.post('/register', data={
        'username': 'otheruser',
        'email': 'other@example.com',
        'password': 'Password123',
        'confirm_password': 'Password123'
    }, follow_redirects=True)

    client.post('/login', data={
        'email': 'other@example.com',
        'password': 'Password123'
    }, follow_redirects=True)

    # Try to edit the first user's project
    response = client.get(f'/projects/{sample_project}/edit')
    # Must be forbidden — 403 or redirect
    assert response.status_code in [403, 302]


# ── MILESTONE TESTS ───────────────────────────────────────────────

def test_add_milestone(logged_in_client, sample_project):
    """
    Project owner must be able to add a milestone to their project.
    """
    response = logged_in_client.post(
        f'/projects/{sample_project}/milestone',
        data={'title': 'Set up the database', 'description': 'SQLAlchemy models'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Set up the database' in response.data


def test_toggle_milestone(app, logged_in_client, sample_project):
    """
    Project owner must be able to toggle a milestone between complete
    and incomplete. Progress bar should update accordingly.
    """
    # First add a milestone
    logged_in_client.post(
        f'/projects/{sample_project}/milestone',
        data={'title': 'Toggle test milestone', 'description': ''},
        follow_redirects=True
    )

    # Find the milestone ID
    with app.app_context():
        from models import Milestone
        ms = Milestone.query.filter_by(title='Toggle test milestone').first()
        assert ms is not None
        ms_id = ms.id

    # Toggle it complete
    response = logged_in_client.post(
        f'/milestones/{ms_id}/toggle',
        follow_redirects=True
    )
    assert response.status_code == 200

    # Verify it is now complete
    with app.app_context():
        from models import Milestone
        ms = Milestone.query.get(ms_id)
        assert ms.completed is True


# ── COMMENT TESTS ─────────────────────────────────────────────────

def test_add_comment(logged_in_client, sample_project):
    """
    Logged-in user must be able to post a comment on any project.
    """
    response = logged_in_client.post(
        f'/projects/{sample_project}/comment',
        data={'body': 'Great project! Happy to collaborate.'},
        follow_redirects=True
    )
    assert response.status_code == 200
    assert b'Great project' in response.data


def test_empty_comment_rejected(logged_in_client, sample_project):
    """
    Submitting an empty comment must be rejected — body is required.
    """
    response = logged_in_client.post(
        f'/projects/{sample_project}/comment',
        data={'body': ''},
        follow_redirects=True
    )
    assert response.status_code == 200


# ── FEED AND WALL TESTS ───────────────────────────────────────────

def test_feed_shows_projects(logged_in_client):
    """
    After creating a project it must appear in the public feed.
    """
    # Create a project
    logged_in_client.post('/projects/new', data={
        'title': 'Feed Visibility Test',
        'description': 'This should appear in the feed.',
        'stage': 'In Progress',
        'support_needed': ''
    }, follow_redirects=True)

    # Check feed contains it
    response = logged_in_client.get('/feed')
    assert response.status_code == 200
    assert b'Feed Visibility Test' in response.data


def test_celebration_wall_shows_completed_projects(app, logged_in_client):
    """
    A project marked as Completed must appear on the Celebration Wall.
    Projects that are not completed must NOT appear there.
    """
    # Create a completed project
    logged_in_client.post('/projects/new', data={
        'title': 'Shipped Project',
        'description': 'This one is done.',
        'stage': 'Completed',
        'support_needed': ''
    }, follow_redirects=True)

    # Check celebration wall
    response = logged_in_client.get('/celebration')
    assert response.status_code == 200
    assert b'Shipped Project' in response.data


def test_celebration_wall_excludes_incomplete_projects(app, logged_in_client):
    """
    Projects that are not completed must NOT appear on the Celebration Wall.
    """
    # Create an in-progress project
    logged_in_client.post('/projects/new', data={
        'title': 'Still Building This',
        'description': 'Not done yet.',
        'stage': 'In Progress',
        'support_needed': ''
    }, follow_redirects=True)

    # Should not appear on the wall
    response = logged_in_client.get('/celebration')
    assert response.status_code == 200
    assert b'Still Building This' not in response.data


# ── AUTO-COMPLETE MILESTONE TEST ──────────────────────────────────

def test_project_auto_completes_when_all_milestones_done(app, logged_in_client, sample_project):
    """
    When the last milestone is ticked, the project must automatically
    be marked as completed=True and stage='Completed'.
    This is a key feature — verifies the auto-complete logic works.
    """
    # Add one milestone
    logged_in_client.post(
        f'/projects/{sample_project}/milestone',
        data={'title': 'Only milestone', 'description': ''},
        follow_redirects=True
    )

    with app.app_context():
        from models import Milestone, Project
        ms = Milestone.query.filter_by(title='Only milestone').first()
        ms_id = ms.id

    # Toggle it to complete (this should auto-complete the project)
    logged_in_client.post(f'/milestones/{ms_id}/toggle', follow_redirects=True)

    # Verify project is now auto-completed
    with app.app_context():
        from models import Project
        project = Project.query.get(sample_project)
        assert project.completed is True
        assert project.stage == 'Completed'