import imaplib, email, re, pytz
from datetime import datetime, timedelta
from flask import current_app

def clean_url(u): return re.sub(r'[)\]>"\']+$', '', u)
def extract_code(t, d): m = re.search(fr'\b(\d{{{d}}})\b', t); return m.group(1) if m else None

class EmailService:
    @staticmethod
    def fetch_netflix_data(target_email, category):
        user, pwd = current_app.config['EMAIL_USER'], current_app.config['EMAIL_PASS']
        if not user or not pwd: return False, "Config missing", None
        
        try:
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(user, pwd)
            imap.select("inbox")
            
            now = datetime.now(pytz.utc)
            
            # --- NEW TIME LIMITS ---
            deltas = {
                'Login Code': 15,          # 15 Minutes
                'Household': 15,           # 15 Minutes
                'TV Login': 15,            # 15 Minutes
                'Verification Code': 24*60, # 24 Hours (As requested)
                'Reset': 24*60,            # 24 Hours
                'Verify Email': 24*60      # 24 Hours
            }
            
            # Default to 15 min if unknown
            validity_minutes = deltas.get(category, 15)
            time_threshold = now - timedelta(minutes=validity_minutes)
            
            # Search logic
            since_date = time_threshold.strftime("%d-%b-%Y")
            status, msgs = imap.search(None, f'(TO "{target_email}") (SINCE "{since_date}")')
            
            if status != 'OK': return False, "Search failed", None
            
            found_content = None
            email_timestamp = None
            
            # Scan emails (Newest first)
            for eid in reversed(msgs[0].split()):
                _, data = imap.fetch(eid, "(RFC822)")
                msg = email.message_from_bytes(data[0][1])
                
                # Check Date
                date_str = msg.get("Date")
                if date_str:
                    try:
                        email_date = email.utils.parsedate_to_datetime(date_str)
                        if email_date.tzinfo is None:
                            email_date = email_date.replace(tzinfo=pytz.utc)
                        
                        # Strict Filtering: Skip if older than limit
                        if email_date < time_threshold:
                            continue
                            
                        current_timestamp = email_date.timestamp()
                    except:
                        continue
                else:
                    continue

                # Extract Body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type()=="text/plain": 
                            try: body=part.get_payload(decode=True).decode(errors='ignore'); break
                            except: continue
                else: 
                    try: body=msg.get_payload(decode=True).decode(errors='ignore')
                    except: continue
                
                # Extract Data based on Category
                extracted = None
                if category == "Login Code": extracted = extract_code(body, 4)
                elif category == "Verification Code": extracted = extract_code(body, 6)
                elif category == "Reset": 
                    m=re.search(r'(https://www\.netflix\.com/password\?[^\s]+)', body)
                    extracted=clean_url(m.group(1)) if m else None
                elif category == "Household": 
                    extracted = [clean_url(u) for u in re.findall(r'(https://www\.netflix\.com/account/(?:travel|update-primary-location|confirmdevice)[^\s]+)', body)]
                    if not extracted: extracted = None
                elif category == "Verify Email": 
                    m=re.search(r'(https://www\.netflix\.com/verifyemail\?[^\s]+)', body)
                    extracted=clean_url(m.group(1)) if m else None
                elif category == "TV Login": 
                    m=re.search(r'(https://www\.netflix\.com/ilum\?code=[^\s]+)', body)
                    extracted=clean_url(m.group(1)) if m else None
                
                if extracted:
                    found_content = extracted
                    email_timestamp = current_timestamp
                    break # Stop at the first valid recent email
            
            imap.close()
            imap.logout()

            if found_content:
                # Return Success, Content, and Metadata
                return True, found_content, {
                    "timestamp": email_timestamp,
                    "validity_minutes": validity_minutes
                }
            else:
                return False, f"No active {category} found within last {validity_minutes} mins.", None

        except Exception as e:
            return False, f"Error: {str(e)}", None