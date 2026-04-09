# Import the shared db instance from extensions.py to avoid circular imports
from extensions import db

# UserMixin gives the User class the methods Flask-Login needs to manage sessions
from flask_login import UserMixin

# Used to automatically record when records are created and updated
from datetime import datetime


class User(UserMixin, db.Model):
    """
    Developer account on MzansiBuilds.
    UserMixin provides Flask-Login methods: is_authenticated,
    is_active, is_anonymous, get_id.
    Password is never stored — only the pbkdf2:sha256 hash.
    """
    # Unique identifier for each user - auto-increments with each new account
    id = db.Column(db.Integer, primary_key=True)

    # Username must be unique - no two developers can share the same handle
    username = db.Column(db.String(80),  unique=True, nullable=False)

    # Email must be unique - used for login identification
    email = db.Column(db.String(120), unique=True, nullable=False)

    # Only the hash is stored, never the plain text password
    password_hash = db.Column(db.String(256), nullable=False)

    # Automatically records when the account was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # One user can have many projects - cascade means if user is deleted, their projects are too
    projects = db.relationship('Project', backref='author', lazy=True, cascade='all, delete-orphan')

    # One user can have many comments - cascade deletes comments if user is deleted
    comments = db.relationship('Comment', backref='author', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
    # Controls how the User object is displayed when printed - useful for debugging
        return f'<User {self.username}>'


class Project(db.Model):
    """
    A project a developer is building publicly.
    Belongs to one User. Stage tracks development progress.
    completed=True moves the project to the Celebration Wall.
    """
    # Unique identifier for each project
    id = db.Column(db.Integer, primary_key=True)

    # Project title is required - cannot be saved without one
    title = db.Column(db.String(120), nullable=False)

    # Optional longer description of what the project is building
    description = db.Column(db.Text)

    # Tracks where the project is: Planning, In Progress, Needs Help, Completed
    stage = db.Column(db.String(50), default='Planning')

    # Optional field for the developer to describe what help they need
    support_needed = db.Column(db.Text)

    # When True, the project appears on the Celebration Wall
    completed = db.Column(db.Boolean, default=False)

    # Automatically records when the project was first created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Automatically updates whenever the project record is modified
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Foreign key linking this project to the user who created it
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    # One project can have many milestones - deletes milestones if project is deleted
    milestones = db.relationship('Milestone', backref='project', lazy=True, cascade='all, delete-orphan')

    # One project can have many comments - deletes comments if project is deleted
    comments = db.relationship('Comment',   backref='project', lazy=True, cascade='all, delete-orphan')

    @property
    def milestone_progress(self):
        """Returns (completed_count, total_count) for this project's milestones."""
        # Count total milestones and how many are marked complete
        total     = len(self.milestones)
        completed = sum(1 for m in self.milestones if m.completed)
        return completed, total

    @property
    def progress_percent(self):
        """Percentage of milestones completed, 0-100."""
        completed, total = self.milestone_progress
        # Avoid division by zero if no milestones have been added yet
        if total == 0:
            return 0
        # Round to nearest whole number for display in the progress bar
        return round((completed / total) * 100)

    def __repr__(self):
        return f'<Project {self.title}>'


class Milestone(db.Model):
    """
    A milestone within a project.
    Developers mark milestones complete as they progress.
    Provides evidence of active development.
    """
    # Unique identifier for each milestone
    id = db.Column(db.Integer, primary_key=True)

    # Milestone title is required - describes what needs to be done
    title = db.Column(db.String(200), nullable=False)

    # Optional extra detail about what this milestone involves
    description = db.Column(db.Text)

    # False by default - toggled to True when the developer marks it done
    completed = db.Column(db.Boolean, default=False)

    # Records when the milestone was created
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Records when the milestone was completed - nullable because it starts incomplete
    completed_at = db.Column(db.DateTime, nullable=True)

    # Foreign key linking this milestone to its parent project
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

    def __repr__(self):
        return f'<Milestone {self.title} completed={self.completed}>'


class Comment(db.Model):
    """
    A comment on a project from any logged-in developer.
    Used for collaboration requests and feedback.
    """
    # Unique identifier for each comment
    id = db.Column(db.Integer, primary_key=True)

    # The comment text - required, cannot post an empty comment
    body = db.Column(db.Text, nullable=False)

    # Records when the comment was posted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Foreign key to the user who posted the comment
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'),    nullable=False)

    # Foreign key to the project the comment was posted on
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)

    def __repr__(self):
        return f'<Comment by user {self.user_id} on project {self.project_id}>'