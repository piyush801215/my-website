from app import create_app, db
from app.models import User
from app.telegram_bot import start_telegram_bot
import os

app = create_app()

with app.app_context():
    db.create_all()

def setup_initial_admin():
            if not User.query.filter_by(role='super_admin').first():
            print("Creating initial Super Admin...")
            u = User(username=os.getenv('ADMIN_USER'), role='super_admin')
            u.set_password(os.getenv('ADMIN_PASS'))
            db.session.add(u)
            db.session.commit()
            print("Super Admin Created.")
@app.route("/")
def home():
    return "Server is working 🚀"