import os
import json
import random
import smtplib
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

app = Flask(__name__)
# Enable sessions for admin login
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key")

# --- Session Security Rules ---
# Expire the session automatically after 2 hours
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)
# Prevent JavaScript from reading the cookie (protects against XSS)
app.config['SESSION_COOKIE_HTTPONLY'] = True 
# -----------------------------------

# Load the environment variables from the .env file
load_dotenv()

with open('refined_colors.json', 'r', encoding='utf-8') as f:
    pokemon_data = json.load(f)

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

def send_confirmation_email(name, email, pokemon_name, color, contrast_color, config, lang, cal_link):
    sender_email = os.getenv("SMTP_EMAIL")
    sender_password = os.getenv("SMTP_PASSWORD")
    
    if not sender_email or sender_email == "your_email@gmail.com":
        print(f"Skipping email to {email}: SMTP credentials not set in .env")
        return

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

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'pokemon_logos'),
                               'favi_official.ico', mimetype='image/vnd.microsoft.icon')
@app.route('/')
def index():
    config = load_config()
    lang = load_lang() # Load the language
    poke_id = request.args.get('id')
    
    if poke_id:
        padded_filename = f"{int(poke_id):04d}.png"
        chosen_pokemon = next((p for p in pokemon_data if p['filename'] == padded_filename), None)
        if not chosen_pokemon: chosen_pokemon = random.choice(pokemon_data)
    else:
        chosen_pokemon = random.choice(pokemon_data)
        
    poke_name = chosen_pokemon.get("name", "Pikachu")
    color = chosen_pokemon.get("predominant_color", "#ffcb05")
    filename = chosen_pokemon.get("filename", "0025.png")

    contrast_color = get_contrast_color(color)
    highlighted_name = f"<span class='highlight-badge' style='background-color: {color}; color: {contrast_color};'>{poke_name}</span>"
    formatted_message = config.get("message_template", "").replace("{name}", highlighted_name)

    return render_template(
        'index.html', 
        pokemon=chosen_pokemon,
        all_pokemon=pokemon_data,
        config=config,
        lang=lang, # Pass it to the HTML!
        message=formatted_message,
        color=color,
        contrast_color=contrast_color,
        image=filename
    )

@app.route('/rsvp', methods=['POST'])
def rsvp():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    lang = load_lang() 
    config = load_config()
    
    if not name or not email:
        return jsonify({"success": False, "message": lang.get("msg_error_empty")}), 400

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
            
    email_lower = email.strip().lower()
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
    details = quote("Mal posso esperar para te ver lá!")
    location = quote(config.get('location', ''))
    cal_link = f"https://calendar.google.com/calendar/render?action=TEMPLATE&text={title}&dates={dates}&details={details}&location={location}"
    # -------------------------------------

    try:
        send_confirmation_email(name, email, data.get('pokemon_name'), data.get('color'), data.get('contrast_color'), config, lang, cal_link)
        # Send the link back to the browser so the button can use it!
        return jsonify({"success": True, "message": lang.get("msg_success"), "cal_link": cal_link})
    except Exception as e:
        print(f"Error sending email: {e}")
        return jsonify({"success": True, "message": f'{lang.get("msg_success")} (Email skipped locally)', "cal_link": cal_link})

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
            return redirect(url_for('admin'))
        else:
            error = "Senha incorreta!"

    # If not logged in, show login page
    if not session.get('admin_logged_in'):
        return render_template('admin.html', login_required=True, lang=lang, config=config, error=error)

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

    return render_template('admin.html', login_required=False, guests=guests, lang=lang, config=config)

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if not session.get('admin_logged_in'):
        return jsonify({"success": False, "message": "Unauthorized"}), 403
    
    email_to_delete = request.json.get('email')
    guest_file = 'guests/rsvp_list.json'
    
    if os.path.exists(guest_file):
        with open(guest_file, 'r', encoding='utf-8') as f:
            guests = json.loads(f.read().strip() or "[]")
        
        # Filter out the guest with the matching email
        guests = [g for g in guests if g.get('email', '').lower() != email_to_delete.lower()]
        
        with open(guest_file, 'w', encoding='utf-8') as f:
            json.dump(guests, f, indent=4)
            
    return jsonify({"success": True})

@app.route('/admin/export')
def admin_export():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))
    
    guests = []
    if os.path.exists('guests/rsvp_list.json'):
        with open('guests/rsvp_list.json', 'r', encoding='utf-8') as f:
            guests = json.loads(f.read().strip() or "[]")

    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['Name', 'Email', 'Pokemon', 'Color', 'Timestamp'])
    for g in guests:
        cw.writerow([g.get('name'), g.get('email'), g.get('pokemon'), g.get('color'), g.get('timestamp')])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=convidados.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)