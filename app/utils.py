from functools import wraps
from flask import abort, current_app
from flask_login import current_user
import telebot, threading

def super_admin_required(f):
    @wraps(f)
    def decorated(*a, **k):
        if not current_user.is_authenticated or not current_user.is_super_admin: abort(403)
        return f(*a, **k)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*a, **k):
        if not current_user.is_authenticated or current_user.role not in ['super_admin', 'sub_admin']: abort(403)
        return f(*a, **k)
    return decorated

def send_telegram_alert(user_name, user_id, email, category, result, success):
    token, admin_id = current_app.config.get('BOT_TOKEN'), current_app.config.get('ADMIN_ID')
    if not token or not admin_id: return
    
    def _send():
        try:
            bot = telebot.TeleBot(token)
            status = "✅ SUCCESS" if success else "❌ FAILED"
            res_txt = "User received the data." if success else str(result)
            msg = f"📝 <b>LOG</b>\n👤 {user_name}\n📧 {email}\n🔧 {category}\n📊 {status}\nℹ️ {res_txt}"
            bot.send_message(admin_id, msg, parse_mode='HTML')
        except: pass
    threading.Thread(target=_send).start()