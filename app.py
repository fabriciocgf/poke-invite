import os
import json
import random
import smtplib
import logging
import re
import secrets
from logging.handlers import SysLogHandler, RotatingFileHandler
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote
import csv
from io import StringIO
from flask import Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, make_response
from werkzeug.security import check_password_hash
from datetime import timedelta
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
# Enable sessions for admin login
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

# --- Session & Security Configuration ---
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
# -----------------------------------

# --- Rate Limiting Configuration ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)
# -----------------------------------

# --- Logging Configuration (Syslog with Fallback) ---
# Create a custom logger
app.logger.handlers.clear() # Clear default handlers
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s [%(levelname)s] %(message)s'))
app.logger.addHandler(stream_handler)

# Try to add SysLogHandler
syslog_addr_env = os.getenv('SYSLOG_ADDRESS')
if syslog_addr_env:
    if ':' in syslog_addr_env:
        try:
            host, port = syslog_addr_env.split(':')
            syslog_address = (host, int(port))
        except ValueError:
            syslog_address = syslog_addr_env
    else:
        syslog_address = syslog_addr_env
else:
    # Default addresses for syslog
    if os.name == 'posix':
        syslog_address = '/dev/log' if os.path.exists('/dev/log') else '/var/run/syslog'
    else:
        syslog_address = ('localhost', 514) # Standard for Windows/Network

try:
    sys_handler = SysLogHandler(address=syslog_address)
    sys_handler.setFormatter(logging.Formatter('%(name)s [%(levelname)s] %(message)s'))
    app.logger.addHandler(sys_handler)
    app.logger.info(f"SysLogHandler initialized at {syslog_address}")
except Exception as e:
    # Requirement RF06: Log critical failure if mandatory syslog is unavailable
    app.logger.critical(f"CRITICAL: SysLogHandler failed to initialize at {syslog_address}. Error: {e}")

# Also add a local file log for persistence/debugging
os.makedirs('logs', exist_ok=True)
file_handler = RotatingFileHandler('logs/app.log', maxBytes=1000000, backupCount=3)
file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.INFO)
# -----------------------------------

# Load the environment variables from the .env file
load_dotenv()

# Filter pokemon data to only include those with existing image files
with open('refined_colors.json', 'r', encoding='utf-8') as f:
    all_pokemon_data = json.load(f)
    
pokemon_data = []
image_dir = 'pokemon_logos'
for p in all_pokemon_data:
    if os.path.exists(os.path.join(image_dir, p.get('filename', ''))):
        pokemon_data.append(p)

if not pokemon_data:
    app.logger.error("No valid pokemon images found! Reverting to all data to prevent crash.")
    pokemon_data = all_pokemon_data

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)
    
def load_lang():
    with open('lang.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def get_contrast_color(hex_color):
    hex_color = hex_color.lstrip('#')
    if len(hex_color) != 6: return "#ffffff"
    r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    luminance = (0.299 * r + 0.587 * g + 0.114 * b)
    return "#222222" if luminance > 140 else "#ffffff"

def is_valid_email(email):
    # Simple regex for email validation
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(regex, email) is not None

def send_confirmation_email(name, email, pokemon_name, color, contrast_color, config, lang, cal_link):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if not sender_email or sender_email == "your_email@gmail.com":
        app.logger.warning(f"Skipping email to {email}: SMTP credentials not set in .env")
        return

    try:
        subject = config.get("email_subject", "Party Invitation!")
        body_template = config.get("email_message", "Thanks for RSVPing, {guest_name}!")
        body_text = body_template.replace("{guest_name}", name)
        
        html = f"""
        <html>
            <body style="font-family: sans-serif; text-align: center; background-color: #1a1a1a; color: white; padding: 20px;">
                <div style="background-color: #242424; border: 4px solid {color}; padding: 30px; border-radius: 15px; max-width: 500px; margin: 0 auto;">
                    <h1 style="color: #ffcb05; text-shadow: 2px 2px 0 #3b4cca;">{config.get('title')}</h1>
                    <p style="font-size: 18px; line-height: 1.5;">{body_text}</p>
                    <div style="background-color: {color}; color: {contrast_color}; padding: 15px; border-radius: 10px; margin-top: 20px;">
                        <strong>{lang.get('date_label')}</strong> {config.get('date')}<br>
                        <strong>{lang.get('location_label')}</strong> {config.get('location')}<br>
                        <strong>{lang.get('time_label')}</strong> {config.get('time')}
                    </div>
                    <div style="margin-top: 25px;">
                        <a href="{cal_link}" style="background-color: {color}; color: {contrast_color}; padding: 12px 20px; text-decoration: none; border-radius: 8px; font-weight: bold; display: inline-block;">{lang.get('btn_add_calendar')}</a>
                    </div>
                </div>
            </body>
        </html>
        """
        
        msg = MIMEMultipart("alternative")
        msg['Subject'] = subject
        msg['From'] = f"{config.get('title')} <{sender_email}>" 
        msg['To'] = email
        msg.attach(MIMEText(html, "html"))
        
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        app.logger.error(f"SMTP Error: Failed to send confirmation email to {email}. Error: {e}")
        raise e

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'pokemon_logos'),
                               'favi_official.ico', mimetype='image/vnd.microsoft.icon')
@app.route('/')
def index():
    config = load_config()
    lang = load_lang()
    poke_id = request.args.get('id')
    
    if poke_id:
        padded_filename = f"{int(poke_id):04d}.webp" 
        chosen_pokemon = next((p for p in pokemon_data if p['filename'] == padded_filename), None)
        if not chosen_pokemon: chosen_pokemon = random.choice(pokemon_data)
    else:
        chosen_pokemon = random.choice(pokemon_data)
        
    poke_name = chosen_pokemon.get("name", "Pikachu")
    color = chosen_pokemon.get("predominant_color", "#ffcb05")
    
    filename = chosen_pokemon.get("filename", "0025.webp") 

    contrast_color = get_contrast_color(color)
    highlighted_name = f"<span class='highlight-badge' style='background-color: {color}; color: {contrast_color};'>{poke_name}</span>"
    formatted_message = config.get("message_template", "").replace("{name}", highlighted_name)

    return render_template(
        'index.html', 
        pokemon=chosen_pokemon,
        all_pokemon=pokemon_data,
        config=config,
        lang=lang,
        message=formatted_message,
        color=color,
        contrast_color=contrast_color,
        image=filename
    )

@app.route('/rsvp', methods=['POST'])
@limiter.limit("5 per minute")
def rsvp():
    data = request.json
    name = data.get('name', '').strip()
    email = data.get('email', '').strip()
    lang = load_lang() 
    config = load_config()
    
    if not name or not email:
        return jsonify({"success": False, "message": lang.get("msg_error_empty")}), 400

    if not is_valid_email(email):
        return jsonify({"success": False, "message": lang.get("msg_error_invalid_email", "Email inválido!")}), 400

    os.makedirs('guests', exist_ok=True)
    guest_file = 'guests/rsvp_list.json'
    
    guests = []
    if os.path.exists(guest_file):
        try:
            with open(guest_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:  
                    guests = json.loads(content)
        except json.JSONDecodeError:
            guests = []
            
    email_lower = email.lower()
    for guest in guests:
        if guest.get('email', '').strip().lower() == email_lower:
            return jsonify({"success": False, "message": lang.get("msg_error_duplicate")}), 400

    guests.append({
        "name": name, 
        "email": email, 
        "pokemon": data.get('pokemon_name'),
        "color": data.get('color'),                   
        "contrast_color": data.get('contrast_color'), 
        "timestamp": str(datetime.now())
    })
    
    with open(guest_file, 'w', encoding='utf-8') as f:
        json.dump(guests, f, indent=4)
        
    # --- Generate Google Calendar Link ---
    title = quote(config.get('title', 'Party!'))
    dates = f"{config.get('calendar_start', '')}/{config.get('calendar_end', '')}"
    details = quote(lang.get('cal_details', "Mal posso esperar para te ver lá!"))
    location = quote(config.get('location', ''))
    cal_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={dates}&details={details}&location={location}"
    # -------------------------------------

    try:
        send_confirmation_email(name, email, data.get('pokemon_name'), data.get('color'), data.get('contrast_color'), config, lang, cal_link)
        # Send the link back to the browser so the button can use it!
        return jsonify({"success": True, "message": lang.get("msg_success"), "cal_link": cal_link})
    except Exception as e:
        # SMTP error logging is already handled in send_confirmation_email
        # Requirement: Improve visual feedback when email fails
        return jsonify({"success": True, "message": lang.get("msg_success_email_skipped"), "cal_link": cal_link})

@app.route('/pokemon_logos/<path:filename>')
def serve_image(filename):
    # Get the image response from Flask
    response = send_from_directory('pokemon_logos', filename)
    
    # Add aggressive caching headers (Cache for 30 days)
    # This tells Cloudflare's CDN and the user's browser to save the image locally!
    response.headers['Cache-Control'] = 'public, max-age=2592000'
    
    return response

# ==========================================
# ADMIN DASHBOARD ROUTES
# ==========================================

@app.route('/admin', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def admin():
    lang = load_lang()
    config = load_config()
    error = None

    # Handle Login
    if request.method == 'POST':
        password = request.form.get('password')
        stored_hash = os.getenv('ADMIN_PASSWORD_HASH', '')
        
        # Verify the password against the secure hash
        if check_password_hash(stored_hash, password):
            session.permanent = True # Activates the 2-hour expiration
            session['admin_logged_in'] = True
            app.logger.info(f"Admin login successful from IP: {request.remote_addr}")
            return redirect(url_for('admin'))
        else:
            app.logger.warning(f"Failed admin login attempt from IP: {request.remote_addr}")
            error = lang.get('admin_error_password', "Senha incorreta!")

    # If not logged in, show login page
    if not session.get('admin_logged_in'):
        return render_template('admin.html', login_required=True, lang=lang, config=config, error=error)

    # Generate CSRF token for this session if it doesn't exist
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)

    # Load guests for the dashboard
    guests = []
    guest_file = 'guests/rsvp_list.json'
    if os.path.exists(guest_file):
        try:
            with open(guest_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if content:
                    guests = json.loads(content)
        except json.JSONDecodeError:
            pass

    return render_template('admin.html', login_required=False, guests=guests, lang=lang, config=config, csrf_token=session['csrf_token'])

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    lang = load_lang()
    if not session.get('admin_logged_in'):
        app.logger.warning(f"Unauthorized guest deletion attempt from IP: {request.remote_addr}")
        return jsonify({"success": False, "message": lang.get('admin_error_unauthorized')}), 403
    
    # CSRF Verification
    token = request.json.get('csrf_token')
    if not token or token != session.get('csrf_token'):
        app.logger.warning(f"CSRF verification failed for guest deletion from IP: {request.remote_addr}")
        return jsonify({"success": False, "message": lang.get('admin_error_csrf')}), 403

    email_to_delete = request.json.get('email')
    guest_file = 'guests/rsvp_list.json'
    
    if os.path.exists(guest_file):
        with open(guest_file, 'r', encoding='utf-8') as f:
            guests = json.loads(f.read().strip() or "[]")
        
        # Filter out the guest with the matching email
        guests = [g for g in guests if g.get('email', '').lower() != email_to_delete.lower()]
        
        with open(guest_file, 'w', encoding='utf-8') as f:
            json.dump(guests, f, indent=4)
            
    app.logger.info(f"Guest deleted: {email_to_delete} by Admin from IP: {request.remote_addr}")
    return jsonify({"success": True})

@app.route('/admin/export')
def admin_export():
    lang = load_lang()
    if not session.get('admin_logged_in'):
        app.logger.warning(f"Unauthorized guest export attempt from IP: {request.remote_addr}")
        return redirect(url_for('admin'))
    
    guests = []
    if os.path.exists('guests/rsvp_list.json'):
        with open('guests/rsvp_list.json', 'r', encoding='utf-8') as f:
            guests = json.loads(f.read().strip() or "[]")

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow([
        lang.get('csv_col_name', 'Name'), 
        lang.get('csv_col_email', 'Email'), 
        lang.get('csv_col_pokemon', 'Pokemon'), 
        lang.get('csv_col_color', 'Color'), 
        lang.get('csv_col_timestamp', 'Timestamp')
    ])
    for g in guests:
        cw.writerow([g.get('name'), g.get('email'), g.get('pokemon'), g.get('color'), g.get('timestamp')])
    
    app.logger.info(f"Guest list exported to CSV by Admin from IP: {request.remote_addr}")
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=convidados.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    session.pop('csrf_token', None)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
