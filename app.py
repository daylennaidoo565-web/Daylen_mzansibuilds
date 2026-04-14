import os
# This import is to access environment variables (SECRET_KEY, DATABASE_URL, HCAPTCHA keys)
# This is so sensitive values are never hardcoded in the source code
import re
# For Regular expressions — used to validate email format and password strength
# e.g. checking email contains @ and password has letters and numbers
import requests
# Makes HTTP requests to external APIs
# Used specifically to verify hCaptcha tokens with hcaptcha.com/siteverify
from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
# Flask      - creates the web application instance
# render_template - loads and returns HTML templates from the templates/ folder
# redirect   - sends the user to a different URL (e.g. after login go to dashboard)
# url_for    - generates URLs from route function names instead of hardcoding paths
# flash      - stores one-time messages to show the user (success/error notifications)
# request    - accesses incoming form data, query parameters and HTTP method
# abort      - immediately stops a request and returns an error code (403, 404 etc)
# jsonify    - converts Python dicts to JSON responses (used for API endpoints)
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
# LoginManager   - sets up the Flask-Login extension and configures the login view
# login_user     - starts a user session after successful authentication
# logout_user    - clears the session and logs the user out
# login_required - decorator that blocks unauthenticated users from accessing a route
# current_user   - gives access to the logged-in user object in any route or template
from werkzeug.security import generate_password_hash, check_password_hash
# generate_password_hash - hashes a plain text password using pbkdf2:sha256 so passwords are never stored in plain text in the database
# check_password_hash    - safely compares a plain text password against a stored hash using constant-time comparison to prevent timing attacks
from extensions import db
# Imports the SQLAlchemy database instance from extensions.py
# Kept separate to avoid circular imports between app.py and models.py


# create the app
app = Flask(__name__)

# --------------------------------------------- CONFIG ------------------------------------------------------------
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'change-this-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///mzansibuilds.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

DEBUG_MODE = os.environ.get('FLASK_DEBUG', '1') != '0'

# SITE_KEY goes in the HTML template, identifies the site to hCaptcha. Safe to be visible in the browser. (Used for testing to display security aspects)
HCAPTCHA_SITE_KEY   = os.environ.get('HCAPTCHA_SITE_KEY',   '10000000-ffff-ffff-ffff-000000000001')
# SECRET_KEY stays on the server, used to verify the captcha response with hCaptcha's API. Must never be exposed publicly. Shown below for testing
HCAPTCHA_SECRET_KEY = os.environ.get('HCAPTCHA_SECRET_KEY', '0x0000000000000000000000000000000000000000')

# Railway provides PostgreSQL connection strings starting with 'postgres://' but SQLAlchemy 2.0 requires 'postgresql://' — this fixes that mismatch
# The replace(..., 1) means only replace the first occurrence, not the whole string
if app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgres://'):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace(
        'postgres://', 'postgresql://', 1)

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'

from models import User, Project, Milestone, Comment


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ----------------------------------------- HELPERS -------------------------------------------------

def verify_captcha(token):
    if DEBUG_MODE:
        return True
    if not token:
        return False
    try:
        resp = requests.post(
            'https://hcaptcha.com/siteverify',
            data={'secret': HCAPTCHA_SECRET_KEY, 'response': token},
            timeout=5
        )
        return resp.json().get('success', False)
    except Exception:
        return False


# Strips leading and trailing whitespace from any user input Then enforces a maximum character length to prevent oversized data being saved to the database - defaults to 500 characters
# Returns empty string if no text is provided at all
def sanitize(text, max_length=500):
    if not text:
        return ''
    return text.strip()[:max_length]


def is_valid_email(email):
    return bool(re.match(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', email))


def is_strong_password(password):
    if len(password) < 8:
        return False, 'Password must be at least 8 characters.'
    if not re.search(r'[A-Za-z]', password):
        return False, 'Password must contain at least one letter.'
    if not re.search(r'[0-9]', password):
        return False, 'Password must contain at least one number.'
    return True, ''


# -------------------------------------------- PUBLIC ROUTES -------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html')

# Checks done when adding a new user
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = sanitize(request.form.get('username', ''), max_length=80)
        email    = sanitize(request.form.get('email', ''), max_length=120).lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        captcha  = request.form.get('h-captcha-response', '')

        if not verify_captcha(captcha):
            flash('Please complete the captcha verification.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if not username or not email or not password or not confirm:
            flash('All fields are required.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if len(username) < 3:
            flash('Username must be at least 3 characters.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            flash('Username can only contain letters, numbers and underscores.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if not is_valid_email(email):
            flash('Please enter a valid email address.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        valid, msg = is_strong_password(password)
        if not valid:
            flash(msg, 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if password != confirm:
            flash('Passwords do not match.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if User.query.filter_by(email=email).first():
            flash('An account with that email already exists.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        if User.query.filter_by(username=username).first():
            flash('That username is already taken.', 'danger')
            return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

        new_user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(
                password, method='pbkdf2:sha256', salt_length=16)
        )
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login'))

    return render_template('register.html', site_key=HCAPTCHA_SITE_KEY)

# Login verifications below
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email    = sanitize(request.form.get('email', ''), max_length=120).lower()
        password = request.form.get('password', '')
        captcha  = request.form.get('h-captcha-response', '')

        if not verify_captcha(captcha):
            flash('Please complete the captcha verification.', 'danger')
            return render_template('login.html', site_key=HCAPTCHA_SITE_KEY)

        if not email or not password:
            flash('Please enter your email and password.', 'danger')
            return render_template('login.html', site_key=HCAPTCHA_SITE_KEY)

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'danger')
            return render_template('login.html', site_key=HCAPTCHA_SITE_KEY)

        login_user(user, remember=False)

        next_page = request.args.get('next')
        if next_page and next_page.startswith('/'):
            return redirect(next_page)
        return redirect(url_for('dashboard'))

    return render_template('login.html', site_key=HCAPTCHA_SITE_KEY)

#Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))


# -------------------------------------------- PROTECTED ROUTES --------------------------------------------------------

@app.route('/dashboard')
@login_required     # blocks unauthenticated users — redirects to login page
def dashboard():
    # Fetch only the current user's projects, newest first
    projects         = Project.query.filter_by(user_id=current_user.id).order_by(Project.created_at.desc()).all()
    total_comments   = sum(len(p.comments)   for p in projects)
    total_milestones = sum(len(p.milestones) for p in projects)
    done_milestones  = sum(sum(1 for m in p.milestones if m.completed) for p in projects)

    # Pass all stats to the dashboard template for display
    return render_template('dashboard.html',
                           projects=projects,
                           total_comments=total_comments,
                           total_milestones=total_milestones,
                           done_milestones=done_milestones)


# Project page setup
@app.route('/projects/new', methods=['GET', 'POST'])
@login_required
def new_project():
    if request.method == 'POST':
        title          = sanitize(request.form.get('title', ''),          max_length=120)
        description    = sanitize(request.form.get('description', ''),    max_length=1000)
        stage          = sanitize(request.form.get('stage', 'Planning'),  max_length=50)
        support_needed = sanitize(request.form.get('support_needed', ''), max_length=500)

        if not title:
            flash('Project title is required.', 'danger')
            return render_template('project_form.html', action='new', project=None)

        valid_stages = ['Planning', 'In Progress', 'Needs Help', 'Completed']
        if stage not in valid_stages:
            stage = 'Planning'

        project = Project(
            title=title,
            description=description,
            stage=stage,
            support_needed=support_needed,
            user_id=current_user.id,
            completed=(stage == 'Completed')
        )
        db.session.add(project)
        db.session.commit()
        return redirect(url_for('project_detail', project_id=project.id))

    return render_template('project_form.html', action='new', project=None)


@app.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    project       = Project.query.get_or_404(project_id)
    milestones    = Milestone.query.filter_by(project_id=project_id).order_by(Milestone.created_at.asc()).all()
    comments      = Comment.query.filter_by(project_id=project_id).order_by(Comment.created_at.asc()).all()
    user_projects = Project.query.filter_by(user_id=current_user.id).all()

    # Check if we should show the completion popup
    just_completed = request.args.get('just_completed') == '1'

    return render_template('project_detail.html',
                           project=project,
                           milestones=milestones,
                           comments=comments,
                           user_projects=user_projects,
                           just_completed=just_completed)


@app.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        project.title          = sanitize(request.form.get('title', ''),          max_length=120)
        project.description    = sanitize(request.form.get('description', ''),    max_length=1000)
        project.stage          = sanitize(request.form.get('stage', 'Planning'),  max_length=50)
        project.support_needed = sanitize(request.form.get('support_needed', ''), max_length=500)

        valid_stages = ['Planning', 'In Progress', 'Needs Help', 'Completed']
        if project.stage not in valid_stages:
            project.stage = 'Planning'

        project.completed = (project.stage == 'Completed')
        db.session.commit()
        return redirect(url_for('project_detail', project_id=project.id))

    user_projects = Project.query.filter_by(user_id=current_user.id).all()
    return render_template('project_form.html', action='edit', project=project, user_projects=user_projects)


@app.route('/projects/<int:project_id>/milestone', methods=['POST'])
@login_required
def add_milestone(project_id):
    project = Project.query.get_or_404(project_id)
    if project.user_id != current_user.id:
        abort(403)

    title       = sanitize(request.form.get('title', ''),       max_length=200)
    description = sanitize(request.form.get('description', ''), max_length=500)

    if not title:
        return redirect(url_for('project_detail', project_id=project_id))

    milestone = Milestone(title=title, description=description,
                          project_id=project_id, completed=False)
    db.session.add(milestone)
    db.session.commit()
    return redirect(url_for('project_detail', project_id=project_id))


@app.route('/milestones/<int:milestone_id>/toggle', methods=['POST'])
@login_required
def toggle_milestone(milestone_id):
    """
    Toggle milestone complete/incomplete.
    If this tick completes the LAST milestone, automatically marks
    the project as Completed and redirects with just_completed = 1 so the frontend shows the celebration popup.
    """
    milestone = Milestone.query.get_or_404(milestone_id)
    project   = Project.query.get_or_404(milestone.project_id)

    if project.user_id != current_user.id:
        abort(403)

    # Toggle this milestone
    milestone.completed = not milestone.completed
    db.session.commit()

    # Check if ALL milestones are now complete
    all_milestones = Milestone.query.filter_by(project_id=project.id).all()
    all_done = len(all_milestones) > 0 and all(m.completed for m in all_milestones)

    if all_done and not project.completed:
        # Auto-complete the project
        project.completed = True
        project.stage     = 'Completed'
        db.session.commit()
        # Redirect with flag to trigger celebration popup
        return redirect(url_for('project_detail',
                                project_id=project.id,
                                just_completed='1'))

    return redirect(url_for('project_detail', project_id=project.id))


@app.route('/projects/<int:project_id>/comment', methods=['POST'])
@login_required
def add_comment(project_id):
    Project.query.get_or_404(project_id)
    body = sanitize(request.form.get('body', ''), max_length=1000)

    if not body:
        return redirect(url_for('project_detail', project_id=project_id))

    comment = Comment(body=body, user_id=current_user.id, project_id=project_id)
    db.session.add(comment)
    db.session.commit()
    return redirect(url_for('project_detail', project_id=project_id))


# ---------------------------------------- PUBLIC ROUTES -------------------------------------------------------

@app.route('/feed')
def feed():
    stage = request.args.get('stage')
    if stage:
        projects = Project.query.filter_by(stage=stage).order_by(Project.created_at.desc()).all()
    else:
        projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('feed.html', projects=projects)


@app.route('/celebration')
def celebration():
    completed = Project.query.filter_by(completed=True).order_by(Project.created_at.desc()).all()
    return render_template('celebration.html', projects=completed)


# ------------------------------------------- ERROR HANDLERS ----------------------------------------------------

@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html', code=403,
                           message="You don't have permission to access this."), 403

@app.errorhandler(404)
def not_found(e):
    return render_template('error.html', code=404,
                           message="Page not found."), 404

@app.errorhandler(500)
def server_error(e):
    return render_template('error.html', code=500,
                           message="Something went wrong on our end."), 500

with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)