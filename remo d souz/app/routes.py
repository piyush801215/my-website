from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import db
from app.models import User, AssignedEmail, SubAdminAssignment, AccessLog, LoginAttempt
from app.services import EmailService
from app.utils import super_admin_required, admin_required, send_telegram_alert
import re, pytz
from datetime import datetime, timedelta

main = Blueprint('main', __name__)

# --- AUTH ---

@main.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role in ['super_admin', 'sub_admin']: return redirect(url_for('main.admin_panel'))
        return redirect(url_for('main.dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')):
            login_user(user)
            return redirect(url_for('main.admin_panel' if user.role in ['super_admin', 'sub_admin'] else 'main.dashboard'))
        flash('Invalid credentials', 'error')
    return render_template('auth.html')

@main.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.role in ['super_admin', 'sub_admin']:
        return redirect(url_for('main.admin_panel'))
        
    if request.method == 'POST':
        # --- BRUTE FORCE CHECK ---
        ip = request.remote_addr
        attempt_record = LoginAttempt.query.filter_by(ip_address=ip).first()
        
        # Check if blocked (5 failures in last 15 mins)
        if attempt_record and attempt_record.attempts >= 5:
            if (datetime.utcnow() - attempt_record.last_attempt).total_seconds() < 900: # 15 mins
                flash('⚠️ Too many failed attempts. Try again in 15 minutes.', 'error')
                return render_template('admin_login.html')
            else:
                # Reset after timeout
                attempt_record.attempts = 0
                db.session.commit()

        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        # --- PASSWORD CHECK ---
        if user and user.check_password(password) and user.role in ['super_admin', 'sub_admin']:
            # Success: Clear attempts
            if attempt_record:
                db.session.delete(attempt_record)
                db.session.commit()
            
            login_user(user)
            return redirect(url_for('main.admin_panel'))
        else:
            # Failure: Increment attempts
            if not attempt_record:
                new_attempt = LoginAttempt(ip_address=ip, attempts=1)
                db.session.add(new_attempt)
            else:
                attempt_record.attempts += 1
                attempt_record.last_attempt = datetime.utcnow()
            db.session.commit()
            
            flash('Invalid Admin ID or Password', 'error')

    return render_template('admin_login.html')

@main.route('/signup', methods=['POST', 'GET'])
def signup():
    if request.method=='POST':
        if User.query.filter_by(username=request.form.get('username')).first(): flash('Exists', 'error')
        else:
            u = User(username=request.form.get('username'), role='user')
            u.set_password(request.form.get('password'))
            db.session.add(u); db.session.commit()
            flash('Created', 'success'); return redirect(url_for('main.login'))
    return render_template('auth.html', is_signup=True)

@main.route('/logout')
def logout(): logout_user(); return redirect(url_for('main.login'))

@main.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', emails=AssignedEmail.query.filter_by(user_id=current_user.id).all())

@main.route('/api/fetch', methods=['POST'])
@login_required
def fetch_code():
    data = request.json
    email, cat = data.get('email', '').strip().lower(), data.get('category')
    
    if not current_user.is_super_admin and not AssignedEmail.query.filter_by(user_id=current_user.id, email_address=email).first():
        return jsonify({'success': False, 'message': 'Not assigned'})
    
    if cat == "Verification Code" and not current_user.is_super_admin: return jsonify({'success': False, 'message': 'Admin only'})

    suc, res, meta = EmailService.fetch_netflix_data(email, cat)
    db.session.add(AccessLog(user_id=current_user.id, username=current_user.username, email_accessed=email, category=cat, result=str(res)[:500]))
    db.session.commit()
    send_telegram_alert(current_user.username, current_user.id, email, cat, res, suc)
    return jsonify({'success': suc, 'message': res, 'meta': meta})

@main.route('/admin')
@admin_required
def admin_panel():
    sub_admins = User.query.filter_by(role='sub_admin').all() if current_user.is_super_admin else []
    if current_user.is_super_admin: users = User.query.all()
    else: 
        assigns = SubAdminAssignment.query.filter_by(sub_admin_id=current_user.id).all()
        users = User.query.filter(User.id.in_([a.managed_user_id for a in assigns])).all()
    
    logs = AccessLog.query.order_by(AccessLog.timestamp.desc()).limit(50).all()
    f_logs = [{'user': l.username, 'email': l.email_accessed, 'category': l.category, 'result': l.result, 'time': l.timestamp.strftime('%H:%M')} for l in logs]
    return render_template('admin.html', users=users, logs=f_logs, sub_admins=sub_admins)

@main.route('/admin/create_user', methods=['POST'])
@admin_required
def create_user():
    u = User(username=request.form.get('username'), role=request.form.get('role', 'user'))
    u.set_password(request.form.get('password'))
    db.session.add(u); db.session.commit()
    if not current_user.is_super_admin: db.session.add(SubAdminAssignment(sub_admin_id=current_user.id, managed_user_id=u.id)); db.session.commit()
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/assign_email', methods=['POST'])
@admin_required
def assign_email():
    uid, text = request.form.get('user_id'), request.form.get('emails')
    for e in re.split(r'[,\s\n]+', text):
        e = e.lower().strip()
        if e and '@' in e and not AssignedEmail.query.filter_by(user_id=uid, email_address=e).first():
            db.session.add(AssignedEmail(user_id=uid, email_address=e))
    db.session.commit()
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/bulk_remove_emails', methods=['POST'])
@admin_required
def bulk_remove_emails():
    for aid in request.form.getlist('assignment_ids'):
        a = AssignedEmail.query.get(aid)
        if a: db.session.delete(a)
    db.session.commit()
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/delete_user/<int:uid>')
@admin_required
def delete_user(uid):
    if uid != current_user.id: User.query.filter_by(id=uid).delete(); db.session.commit()
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/manage_role', methods=['POST'])
@super_admin_required
def manage_role():
    u = User.query.get(request.form.get('user_id'))
    if u and u.id != current_user.id:
        u.role = request.form.get('role')
        db.session.commit()
    return redirect(url_for('main.admin_panel'))

@main.route('/admin/assign_subadmin', methods=['POST'])
@super_admin_required
def assign_subadmin():
    uid, sid = request.form.get('user_id'), request.form.get('sub_admin_id')
    SubAdminAssignment.query.filter_by(managed_user_id=uid).delete()
    if sid: db.session.add(SubAdminAssignment(sub_admin_id=sid, managed_user_id=uid))
    db.session.commit()
    return redirect(url_for('main.admin_panel'))