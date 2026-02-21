import telebot, threading, time
from app.models import User, AssignedEmail
from app import db

def start_telegram_bot(app):
    token, admin = app.config.get('BOT_TOKEN'), app.config.get('ADMIN_ID')
    if not token or not admin: return
    try: admin_id = int(admin)
    except: return
    
    bot = telebot.TeleBot(token)
    
    def is_admin(m): return m.from_user.id == admin_id

    @bot.message_handler(commands=['start'])
    def welcome(m):
        if is_admin(m): bot.reply_to(m, "Admin Bot Online.\n/users, /emails [user], /add [user] [email], /del [user] [email]")

    @bot.message_handler(commands=['users'])
    def users(m):
        if not is_admin(m): return
        with app.app_context():
            bot.reply_to(m, "\n".join([f"{u.username} ({len(u.assigned_emails)})" for u in User.query.all()]))

    @bot.message_handler(commands=['add'])
    def add(m):
        if not is_admin(m): return
        try: u_name, email = m.text.split()[1], m.text.split()[2].lower()
        except: return
        with app.app_context():
            u = User.query.filter_by(username=u_name).first()
            if u:
                db.session.add(AssignedEmail(user_id=u.id, email_address=email))
                db.session.commit()
                bot.reply_to(m, "Added.")

    def poll():
        while True:
            try: bot.polling(non_stop=True)
            except: time.sleep(5)
    
    threading.Thread(target=poll, daemon=True).start()