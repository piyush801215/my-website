from app import create_app, db
from app.models import User
from app.telegram_bot import start_telegram_bot
import os

app = create_app()

def setup_initial_admin():
    with app.app_context():
        if not User.query.filter_by(role='super_admin').first():
            print("Creating initial Super Admin...")
            u = User(username=os.getenv('ADMIN_USER'), role='super_admin')
            u.set_password(os.getenv('ADMIN_PASS'))
            db.session.add(u)
            db.session.commit()
            print("Super Admin Created.")

# Create DB + Admin on startup
with app.app_context():
    db.create_all()
    setup_initial_admin()

@app.route("/")
def home():
    return "Server is working 🚀"

# IMPORTANT FOR RENDER
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)