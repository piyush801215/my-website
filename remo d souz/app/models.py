from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.Text)
    role = db.Column(db.String(20), default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_emails = db.relationship('AssignedEmail', backref='user', lazy=True, cascade="all, delete-orphan")
    managed_by_assignment = db.relationship('SubAdminAssignment', backref='managed_user', lazy=True, foreign_keys='SubAdminAssignment.managed_user_id', cascade="all, delete-orphan")

    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)
    @property
    def is_super_admin(self): return self.role == 'super_admin'
    @property
    def is_sub_admin(self): return self.role == 'sub_admin'

class AssignedEmail(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email_address = db.Column(db.String(120), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class SubAdminAssignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sub_admin_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    managed_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class AccessLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    username = db.Column(db.String(64))
    email_accessed = db.Column(db.String(120))
    category = db.Column(db.String(50))
    result = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

# --- NEW: BRUTE FORCE PROTECTION ---
class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(50))
    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(db.DateTime, default=datetime.utcnow)