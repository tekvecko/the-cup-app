from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify, send_file, Response
from werkzeug.exceptions import HTTPException
import sqlite3, socket, os, uuid, time, random, io, csv, math, json, requests
from PIL import Image, ImageDraw, ImageFont
from functools import wraps, cmp_to_key
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'the_cup_pro_premium_ultimate_v101_twophase'
DB_PATH = os.path.join(os.getcwd(), 'the_cup_v31.db')
LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
BRAND_DIR = os.path.join(os.getcwd(), 'static', 'brand')
DATA_DIR = os.path.join(os.getcwd(), 'data')
META_FILE = os.path.join(DATA_DIR, "logo_studio_images.json")

os.makedirs(LOGO_DIR, exist_ok=True)
os.makedirs(BRAND_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

# ==========================================
# 1. DATABÁZE A INICIALIZACE
# ==========================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, theme TEXT DEFAULT "system", bet_points INTEGER DEFAULT 0, is_pro INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, start_date TEXT, is_public INTEGER DEFAULT 0, max_teams INTEGER DEFAULT 8, status TEXT DEFAULT "draft", join_token TEXT UNIQUE, rounds INTEGER DEFAULT 1, stage TEXT DEFAULT "groups", referees TEXT DEFAULT "", group_count INTEGER DEFAULT 1, format TEXT DEFAULT "groups")')
        conn.execute('CREATE TABLE IF NOT EXISTS master_teams (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, color TEXT, logo TEXT, elo INTEGER DEFAULT 1200, tag TEXT, UNIQUE(user_id, name))')
        conn.execute('CREATE TABLE IF NOT EXISTS teams (id INTEGER PRIMARY KEY, t_id INTEGER, master_id INTEGER, name TEXT, color TEXT, logo TEXT, group_name TEXT DEFAULT "A")')
        conn.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY, t_id INTEGER, team1_id INTEGER, team2_id INTEGER, score1 INTEGER, score2 INTEGER, status TEXT DEFAULT "planned", stage TEXT DEFAULT "groups", proposed_score1 INTEGER, proposed_score2 INTEGER, proposed_by_team_id INTEGER, is_ot INTEGER DEFAULT 0, match_time TEXT DEFAULT "", pitch TEXT DEFAULT "", round_num INTEGER DEFAULT 1, started_at INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS match_comments (id INTEGER PRIMARY KEY, m_id INTEGER, username TEXT, text TEXT, created_at TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS match_logs (id INTEGER PRIMARY KEY, m_id INTEGER, username TEXT, action TEXT, created_at TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY, user_id INTEGER, m_id INTEGER, p_score1 INTEGER, p_score2 INTEGER, UNIQUE(user_id, m_id))')
        
        for col, table, default in [('theme', 'users', '"system"'), ('bet_points', 'users', '0'), ('is_pro', 'users', '0'), ('round_num', 'matches', '1'), ('group_count', 'tournaments', '1'), ('format', 'tournaments', '"groups"'), ('group_name', 'teams', '"A"'), ('started_at', 'matches', '0'), ('elo', 'master_teams', '1200'), ('tag', 'master_teams', 'NULL')]:
            try: conn.execute(f'SELECT {col} FROM {table} LIMIT 1')
            except: conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}' if 'TEXT' in default else f'ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT {default}')
            
        admin = conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
        if not admin: conn.execute('INSERT INTO users (username, password, theme, is_pro) VALUES (?, ?, ?, ?)', ('admin', generate_password_hash('heslo123'), 'system', 1))
        conn.commit()

init_db()

# ==========================================
# 2. LOGO STUDIO LOGIKA (AI GENERATION)
# ==========================================
STYLES = {"clean": "clean bright vector mascot logo, simple shapes", "3d": "clean 3D polished emblem", "minimal": "minimal geometric flat vector", "premium": "premium professional sport emblem"}

def load_meta():
    if not os.path.exists(META_FILE): return []
    try:
        with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def add_meta(filename, team_name, mode, prompt, label=""):
    data = load_meta()
    data.append({"filename": filename, "team_name": team_name, "mode": mode, "label": label, "prompt": prompt, "created_at": datetime.now().isoformat(timespec="seconds"), "favorite": False})
    with open(META_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def infer_mascot(team_name):
    n = team_name.lower()
    for k, v in [("wolf", "ice wolf"), ("bear", "polar bear"), ("dragon", "ice dragon"), ("hawk", "ice hawk"), ("eagle", "ice eagle")]:
        if k in n: return v
    return "creative mascot"

def pixazo_error(e):
    msg = str(e)
    if "401" in msg: return "Pixazo API klíč byl odmítnut. Zkontrolujte systémovou proměnnou PIXAZO_API_KEY na Renderu."
    if "402" in msg: return "Nedostatek kreditů na Pixazo API."
    if "429" in msg: return "Limit požadavků Pixazo API dosažen (příliš mnoho dotazů)."
    if "API_PAYLOAD_DEBUG" in msg: return msg
    return f"AI Generátor selhal: {msg}"

def pixazo_generate(prompt, width=1024, height=1024, steps=4):
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("API klíč PIXAZO_API_KEY nenalezen na serveru.")
    payload = {"prompt": prompt, "num_steps": int(steps), "height": int(height), "width": int(width)}
    try:
        r = requests.post("https://gateway.pixazo.ai/flux-1-schnell/v1/getData", headers={"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": api_key}, json=payload, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
        data = r.json()
        urls = []
        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ("url", "image_url", "output_url", "media_url", "output") and isinstance(v, str) and v.startswith("http"): urls.append(v)
                    else: walk(v)
            elif isinstance(x, list):
                for i in x: walk(i)
        walk(data)
        if not urls:
            raise RuntimeError(f"API_PAYLOAD_DEBUG: {data}")
        return urls
    except Exception as e:
        raise RuntimeError(str(e))

def save_url(url):
    fn = f"{uuid.uuid4().hex}.png"; r = requests.get(url, timeout=180); r.raise_for_status()
    with open(os.path.join(LOGO_DIR, fn), "wb") as f: f.write(r.content)
    return fn

def compose_two_phases(logo_file, text_file):
    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    
    img_logo.thumbnail((1024, 1024), Image.LANCZOS)
    
    w, h = img_text.size
    img_text_cropped = img_text.crop((0, h//2 - 250, w, h//2 + 250))
    
    canvas = Image.new("RGBA", (1024, 1500), (0, 0, 0, 0))
    canvas.paste(img_logo, ((1024 - img_logo.width) // 2, 0))
    canvas.paste(img_text_cropped, (0, 1000))
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name

def build_logo_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"Professional esports hockey logo symbol, {mascot}. Style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. NO TEXT, NO WORDS. Clean vector art, isolated on a pure transparent background."

def build_text_prompt(team_name, style, colors):
    return f"Esports typography text logo, strictly spelling the exact word '{team_name}'. Bold, modern, aggressive 3D esports font. Colors: {colors}. NO MASCOTS, NO SYMBOLS, ONLY THE WORD '{team_name}'. Clean vector art, isolated on a pure transparent background."

# ==========================================
# 3. HTML ŠABLONY (SPRÁVNÉ POŘADÍ DEKLARACÍ)
# ==========================================

from templates import *
# ==========================================
# 4. POMOCNÉ FUNKCE A VYKRESLOVÁNÍ
# ==========================================
def get_current_user(): return get_db().execute('SELECT * FROM users WHERE id = ?', (session.get('user_id'),)).fetchone() if 'user_id' in session else None

def render_ui(html_content, **kwargs):
    return render_template_string(BASE_UI.replace('CONTENT_PLACEHOLDER', html_content), current_user=get_current_user(), format_date_cz=format_date_cz, **kwargs)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: session['next_url'] = request.url; flash("Vyžadována autorizace."); return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function

def log_match_action(m_id, action):
    user = get_current_user(); username = user['username'] if user else "Systém"
    with get_db() as conn: conn.execute('INSERT INTO match_logs (m_id, username, action, created_at) VALUES (?, ?, ?, ?)', (m_id, username, action, datetime.now().strftime("%d.%m. %H:%M:%S"))); conn.commit()

def get_local_ip():
    try: s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

def format_date_cz(date_str):
    try: return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return date_str

def check_admin(tournament, user): return user and (tournament['user_id'] == user['id'] or user['username'] in [r.strip() for r in tournament['referees'].split(',') if r.strip()])

def is_team_active(master_id): return get_db().execute('SELECT COUNT(*) FROM teams t JOIN tournaments tr ON t.t_id = tr.id WHERE t.master_id = ? AND tr.status = "active"', (master_id,)).fetchone()[0] > 0

def get_standings(t_id):
    conn = get_db(); teams = conn.execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = conn.execute('SELECT * FROM matches WHERE t_id = ? AND status = "finished" AND stage = "groups"', (t_id,)).fetchall()
    stats = {t['id']: {'id': t['id'], 'name': t['name'], 'logo': t['logo'], 'color': t['color'], 'group': t['group_name'], 'gp': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0} for t in teams}
    for m in matches:
        s1, s2, t1, t2 = m['score1'], m['score2'], m['team1_id'], m['team2_id']
        if s1 is None or s2 is None: continue
        stats[t1]['gp'] += 1; stats[t2]['gp'] += 1; stats[t1]['gf'] += s1; stats[t1]['ga'] += s2; stats[t2]['gf'] += s2; stats[t2]['ga'] += s1
        if s1 > s2: stats[t1]['pts'] += 3; stats[t1]['w'] += 1; stats[t2]['l'] += 1
        elif s2 > s1: stats[t2]['pts'] += 3; stats[t2]['w'] += 1; stats[t1]['l'] += 1
        else: stats[t1]['pts'] += 1; stats[t2]['pts'] += 1; stats[t1]['d'] += 1; stats[t2]['d'] += 1
    for tid in stats: stats[tid]['gd'] = stats[tid]['gf'] - stats[tid]['ga']
    def compare(t1, t2):
        if t1['pts'] != t2['pts']: return t1['pts'] - t2['pts']
        h2h = next((m for m in matches if (m['team1_id']==t1['id'] and m['team2_id']==t2['id']) or (m['team1_id']==t2['id'] and m['team2_id']==t1['id'])), None)
        if h2h and h2h['score1'] is not None and h2h['score2'] is not None and h2h['score1'] != h2h['score2']:
            if h2h['team1_id'] == t1['id']: return 1 if h2h['score1'] > h2h['score2'] else -1
            else: return 1 if h2h['score2'] > h2h['score1'] else -1
        return t1['gd'] - t2['gd']
    return sorted(stats.values(), key=cmp_to_key(compare), reverse=True)

def update_elo(m_id):
    conn = get_db(); m = conn.execute('SELECT m.score1, m.score2, t1.master_id as m1, t2.master_id as m2 FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.id = ?', (m_id,)).fetchone()
    mt1 = conn.execute('SELECT elo FROM master_teams WHERE id = ?', (m['m1'],)).fetchone(); mt2 = conn.execute('SELECT elo FROM master_teams WHERE id = ?', (m['m2'],)).fetchone()
    if not mt1 or not mt2 or m['score1'] is None or m['score2'] is None: return
    r1, r2 = mt1['elo'], mt2['elo']; e1 = 1 / (1 + 10 ** ((r2 - r1) / 400)); e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
    s1 = 1 if m['score1'] > m['score2'] else (0.5 if m['score1'] == m['score2'] else 0); s2 = 1 - s1; k = 32
    conn.execute('UPDATE master_teams SET elo = ? WHERE id = ?', (round(r1 + k * (s1 - e1)), m['m1'])); conn.execute('UPDATE master_teams SET elo = ? WHERE id = ?', (round(r2 + k * (s2 - e2)), m['m2'])); conn.commit()

def process_predictions(m_id):
    conn = get_db()
    m = conn.execute('SELECT score1, score2 FROM matches WHERE id = ?', (m_id,)).fetchone()
    if m['score1'] is None or m['score2'] is None: return
    preds = conn.execute('SELECT * FROM predictions WHERE m_id = ?', (m_id,)).fetchall()
    for p in preds:
        pts = 0
        if p['p_score1'] == m['score1'] and p['p_score2'] == m['score2']: pts = 3
        elif (p['p_score1'] > p['p_score2'] and m['score1'] > m['score2']) or (p['p_score1'] < p['p_score2'] and m['score1'] < m['score2']) or (p['p_score1'] == p['p_score2'] and m['score1'] == m['score2']): pts = 1
        if pts > 0: conn.execute('UPDATE users SET bet_points = bet_points + ? WHERE id = ?', (pts, p['user_id']))
    conn.commit()

# ==========================================
# 5. INTEGRACE AI API BRIDGE A PWA ROUTY
# ==========================================
def require_ai_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.headers.get('X-AI-API-KEY')
        if not key or key != os.getenv('AI_API_KEY', 'skynet_v1'): return jsonify({'error': 'Neautorizovaný přístup AI agenta'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    import traceback
    return f"<div style='background:#0f172a;color:#ef4444;padding:2rem;font-family:monospace;white-space:pre-wrap;line-height:1.5;margin:1rem;border-radius:1rem;border:2px solid #ef4444;'><h2>Kritická chyba uzlu THE CUP</h2><hr><br>{traceback.format_exc()}</div>", 500

@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "THE CUP Enterprise",
        "short_name": "THE CUP",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#020617",
        "theme_color": "#020617"
    })

@app.route('/sw.js')
def service_worker():
    return Response("self.addEventListener('fetch', function(event) {});", mimetype='application/javascript')

@app.route('/api/v1/status', methods=['GET'])
@require_ai_key
def api_status(): return jsonify({'status': 'online', 'timestamp': datetime.now().isoformat(), 'db_size_kb': round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0})

@app.route('/api/v1/tournaments/create', methods=['POST'])
@require_ai_key
def api_create_tournament():
    data = request.json
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO tournaments (user_id, name, start_date, max_teams, join_token) VALUES (1, ?, ?, ?, ?)', (data['name'], data.get('start_date', datetime.now().strftime('%Y-%m-%d')), data.get('max_teams', 8), uuid.uuid4().hex[:12]))
            conn.commit()
            return jsonify({'status': 'success', 'tournament_id': cur.lastrowid}), 201
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route('/api/v1/teams/generate', methods=['POST'])
@require_ai_key
def api_generate_team():
    data = request.json; team_name = data.get('team_name'); colors = data.get('colors', 'navy, white')
    if not team_name: return jsonify({'error': 'Chybí team_name'}), 400
    try:
        prompt = build_logo_prompt(team_name, "clean", colors); urls = pixazo_generate(prompt, width=1024, height=1024)
        symbol = save_url(urls[0]); final_logo = compose_logo(symbol, team_name); logo_url = f"/static/generated_logos/{final_logo}"
        with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (1, ?, ?, ?, ?)', (team_name, logo_url, '#0f172a', team_name[:4].upper())); conn.commit()
        return jsonify({'status': 'success', 'team_name': team_name, 'logo_url': logo_url}), 201
    except Exception as e: return jsonify({'error': str(e)}), 500

# ==========================================
# 6. MAIN ROUTY A APLIKACE
# ==========================================
@app.route('/export/db')
@login_required
def export_db(): return send_file(DB_PATH, as_attachment=True, download_name="the_cup_zaloha.db")

@app.route('/export/csv/<int:t_id>')
@login_required
def export_csv(t_id):
    standings = get_standings(t_id); si = io.StringIO(); cw = csv.writer(si)
    cw.writerow(['Poradi', 'Tym', 'Zapasu', 'Vyhry', 'Remizy', 'Prohry', 'Skore', 'Golovy_rozdil', 'Body'])
    for i, s in enumerate(standings, 1): cw.writerow([i, s['name'], s['gp'], s['w'], s['d'], s['l'], f"{s['gf']}:{s['ga']}", s['gd'], s['pts']])
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=tabulka_turnaje_{t_id}.csv"})

@app.route('/upgrade_pro', methods=['POST'])
@login_required
def upgrade_pro():
    with get_db() as conn: conn.execute('UPDATE users SET is_pro = 1 WHERE id = ?', (session['user_id'],)); conn.commit()
    flash("Modul PRO Premium byl aktivován."); return redirect(url_for('account'))

@app.route('/')
def index():
    if 'user_id' not in session: return render_ui(WELCOME_HTML, active_page='home', hide_nav=True)
    uid = session['user_id']
    active_tourneys = get_db().execute('SELECT *, (SELECT COUNT(*) FROM teams WHERE t_id = tournaments.id) as registered_teams FROM tournaments WHERE user_id = ? AND status != "finished" ORDER BY start_date ASC', (uid,)).fetchall()
    participating_tourneys = get_db().execute('SELECT DISTINCT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id JOIN teams t ON t.t_id = tr.id JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ? AND tr.user_id != ? AND tr.status != "finished" ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    joinable_public_tourneys = get_db().execute('SELECT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id WHERE tr.is_public = 1 AND tr.status = "draft" AND tr.user_id != ? AND tr.id NOT IN (SELECT t.t_id FROM teams t JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ?) AND (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) < tr.max_teams ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    stats = {'total_tournaments': len(active_tourneys), 'total_teams': get_db().execute('SELECT COUNT(*) FROM master_teams WHERE user_id = ?', (uid,)).fetchone()[0]}
    next_match = get_db().execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color, tr.name as tr_name FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN master_teams mt1 ON t1.master_id = mt1.id JOIN teams t2 ON m.team2_id = t2.id JOIN master_teams mt2 ON t2.master_id = mt2.id JOIN tournaments tr ON m.t_id = tr.id WHERE m.status != "finished" AND tr.status = "active" AND (mt1.user_id = ? OR mt2.user_id = ?) ORDER BY m.round_num ASC, m.id ASC LIMIT 1', (uid, uid)).fetchone()
    return render_ui(INDEX_HTML, active_tourneys=active_tourneys, participating_tourneys=participating_tourneys, joinable_public_tourneys=joinable_public_tourneys, stats=stats, next_match=next_match, active_page='home')

@app.route('/account')
def account(): return render_ui(ACCOUNT_HTML, host_url=f"http://{get_local_ip()}:5000", active_page='account')

@app.route('/login', methods=['POST'])
def login():
    user = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
    if user and check_password_hash(user['password'], request.form['password']):
        session['user_id'] = user['id']; flash(f"Identita ověřena: {user['username']}"); return redirect(session.pop('next_url', url_for('index')))
    flash("Nesprávné ověřovací údaje."); return redirect(url_for('account'))

@app.route('/register', methods=['POST'])
def register():
    try:
        with get_db() as conn:
            cur = conn.cursor(); cur.execute('INSERT INTO users (username, password, theme, is_pro) VALUES (?, ?, ?, ?)', (request.form['username'], generate_password_hash(request.form['password']), 'system', 0))
            session['user_id'] = cur.lastrowid; conn.commit(); flash("Profil zapsán do systému.")
            return redirect(session.pop('next_url', url_for('index')))
    except sqlite3.IntegrityError: flash("Uživatelské jméno obsazeno."); return redirect(url_for('account'))

@app.route('/logout')
def logout(): session.pop('user_id', None); flash("Spojení ukončeno."); return redirect(url_for('account'))

@app.route('/set_theme', methods=['POST'])
@login_required
def set_theme():
    with get_db() as conn: conn.execute('UPDATE users SET theme = ? WHERE id = ?', (request.form['theme'], session['user_id'])); conn.commit()
    return redirect(request.referrer or url_for('account'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    user = get_current_user()
    if not check_password_hash(user['password'], request.form['current_password']): flash("Původní heslo není korektní.")
    elif request.form['new_password'] != request.form['confirm_password']: flash("Kontrolní součet hesla nesouhlasí.")
    else:
        with get_db() as conn: conn.execute('UPDATE users SET password = ? WHERE id = ?', (generate_password_hash(request.form['new_password']), user['id'])); conn.commit(); flash("Bezpečnostní klíč modifikován.")
    return redirect(url_for('account'))

@app.route('/teams')
@login_required
def teams(): return render_ui(TEAMS_HTML, master_teams=get_db().execute('SELECT * FROM master_teams WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall(), active_page='teams')

@app.route('/teams/new', methods=['GET', 'POST'])
@login_required
def new_team():
    user = get_current_user()
    if request.method == "POST":
        is_ai = request.form.get("is_ai") == "1"
        if is_ai:
            if not user['is_pro']: flash("Vyžaduje PRO Premium."); return redirect(url_for('new_team'))
            team_name = request.form.get("team_name", "").strip()
            colors = f"Body: {request.form.get('color_body','White')}, Outline: {request.form.get('color_outline','Black')}, Fill: {request.form.get('color_fill','Blue')}"
            try:
                style = request.form.get("style", "clean")
                prompt_logo = build_logo_prompt(team_name, style, colors)
                prompt_text = build_text_prompt(team_name, style, colors)
                
                urls_logo = pixazo_generate(prompt_logo)
                file_logo = save_url(urls_logo[0])
                
                urls_text = pixazo_generate(prompt_text)
                file_text = save_url(urls_text[0])
                
                fn = compose_two_phases(file_logo, file_text)
                add_meta(fn, team_name, "TWO_PHASE", f"Logo: {prompt_logo}")
                
                session["pending_team_name"] = team_name
                flash("Dvoufázové AI logo (Symbol + Text) úspěšně vygenerováno.")
            except Exception as e: flash(pixazo_error(e))
            return redirect(url_for("new_team"))
        else:
            try:
                with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (?, ?, ?, ?, ?)', (session['user_id'], request.form['name'], request.form['logo'], request.form['color'], request.form['tag'].upper())); conn.commit()
                flash("Tým byl ručně zapsán."); return redirect(url_for('teams'))
            except sqlite3.IntegrityError: flash("Tento tým je již v registru zapsán.")

    files = [x for x in os.listdir(LOGO_DIR) if x.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))]
    files = sorted(files, key=lambda x: os.path.getmtime(os.path.join(LOGO_DIR, x)), reverse=True)
    meta_map = {m["filename"]: m for m in load_meta()}
    pending_team = session.get("pending_team_name", "")
    filtered_files = [f for f in files if meta_map.get(f, {}).get("team_name") == pending_team]
    return render_ui(TEAM_NEW_HTML, images=filtered_files, meta_map=meta_map, last_images=session.pop("logo_studio_last", []), styles=STYLES, active_page='teams', pending_team=pending_team)

@app.route('/teams/use/<filename>', methods=['POST'])
@login_required
def use_logo(filename):
    if not os.path.isfile(os.path.join(LOGO_DIR, filename)): flash("Soubor z cache zmizel."); return redirect(url_for("new_team"))
    meta = next((m for m in load_meta() if m["filename"] == filename), None); team_name = meta["team_name"] if meta else session.get("pending_team_name", "Neznámý tým")
    try:
        with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, elo, tag) VALUES (?, ?, ?, ?, ?, ?)', (session['user_id'], team_name, f"/static/generated_logos/{filename}", '#1e293b', 1200, team_name[:4].upper())); conn.commit()
        flash("Tým byl úspěšně integrován s AI logem."); session.pop("pending_team_name", None); return redirect(url_for('teams'))
    except sqlite3.IntegrityError: flash("Duplicitní zápis."); return redirect(url_for("new_team"))

@app.route('/teams/edit/<int:team_id>', methods=['GET', 'POST'])
@login_required
def edit_team(team_id):
    team = get_db().execute('SELECT * FROM master_teams WHERE id = ? AND user_id = ?', (team_id, session['user_id'])).fetchone()
    if not team: return redirect(url_for('teams'))
    active = is_team_active(team_id)
    if request.method == 'POST':
        if active: flash("Aktivní data nelze modifikovat."); return redirect(url_for('teams'))
        with get_db() as conn: conn.execute('UPDATE master_teams SET name=?, color=?, tag=? WHERE id=?', (request.form['name'], request.form['color'], request.form['tag'].upper(), team_id)); conn.commit(); flash("Profil upraven."); return redirect(url_for('teams'))
    return render_ui(TEAM_EDIT_HTML, team=team, active=active, active_page='teams')

@app.route('/teams/delete/<int:team_id>', methods=['POST'])
@login_required
def delete_team(team_id):
    if is_team_active(team_id): flash("Blokováno cizím klíčem."); return redirect(url_for('teams'))
    with get_db() as conn: conn.execute('DELETE FROM master_teams WHERE id = ? AND user_id = ?', (team_id, session['user_id'])); conn.commit(); flash("Záznam vymazán."); return redirect(url_for('teams'))

@app.route('/seasons')
@login_required
def seasons(): return render_ui(SEASONS_HTML, tournaments=get_db().execute('SELECT t.*, (SELECT COUNT(*) FROM teams WHERE t_id = t.id) as registered_teams FROM tournaments t WHERE t.user_id = ? ORDER BY t.start_date DESC', (session['user_id'],)).fetchall(), active_page='seasons')

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        if int(request.form['max_teams']) < 2: flash("Minimálně 2 týmy pro inicializaci struktury."); return redirect(url_for('create'))
        with get_db() as conn:
            cur = conn.cursor(); cur.execute('INSERT INTO tournaments (user_id, name, start_date, is_public, max_teams, join_token, rounds, stage, group_count, format) VALUES (?, ?, ?, ?, ?, ?, ?, "groups", ?, ?)', (session['user_id'], request.form['name'], request.form['start_date'], int(request.form['is_public']), int(request.form['max_teams']), uuid.uuid4().hex[:12], int(request.form.get('rounds', 1)), int(request.form.get('group_count', 1)), request.form.get('format', 'groups')))
            new_id = cur.lastrowid; conn.commit(); flash("Logika vytvořena."); return redirect(url_for('tournament_detail', t_id=new_id))
    return render_ui(CREATE_HTML, active_page='create')

@app.route('/tournament/<int:t_id>')
@login_required
def tournament_detail(t_id):
    t = get_db().execute('SELECT * FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t: return redirect(url_for('seasons'))
    if not check_admin(t, get_current_user()) and not get_db().execute('SELECT 1 FROM teams t JOIN master_teams mt ON t.master_id = mt.id WHERE t.t_id = ? AND mt.user_id = ?', (t_id, session['user_id'])).fetchone(): return redirect(url_for('public_view', t_id=t_id))
    teams = get_db().execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = get_db().execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, mt1.user_id as t1_user_id, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color, mt2.user_id as t2_user_id FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN master_teams mt1 ON t1.master_id = mt1.id JOIN teams t2 ON m.team2_id = t2.id JOIN master_teams mt2 ON t2.master_id = mt2.id WHERE m.t_id = ? ORDER BY m.round_num, m.id', (t_id,)).fetchall()
    master_teams = get_db().execute('SELECT * FROM master_teams WHERE user_id = ? AND id NOT IN (SELECT master_id FROM teams WHERE t_id = ?) ORDER BY name ASC', (session['user_id'], t_id)).fetchall()
    logs_raw = get_db().execute('SELECT * FROM match_logs WHERE m_id IN (SELECT id FROM matches WHERE t_id = ?) ORDER BY id DESC', (t_id,)).fetchall()
    logs_dict = {}
    for lg in logs_raw:
        if lg['m_id'] not in logs_dict: logs_dict[lg['m_id']] = []
        logs_dict[lg['m_id']].append(lg)
    my_team_ids = [tm['id'] for tm in get_db().execute('SELECT t.id FROM teams t JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ? AND t.t_id = ?', (session['user_id'], t_id)).fetchall()]
    preds = {p['m_id']: p for p in get_db().execute('SELECT * FROM predictions WHERE user_id = ?', (session['user_id'],)).fetchall()}
    standings = get_standings(t_id) if t['status'] != 'draft' else []
    group_matches = [m for m in matches if m['stage'] == 'groups']
    all_finished = len(group_matches) > 0 and all(m['status'] == 'finished' for m in group_matches)
    podium = None
    if t['status'] == 'finished':
        podium = {'first': None, 'second': None, 'third': None}
        playoff_matches = [m for m in matches if m['stage'] == 'playoffs']
        if playoff_matches:
            final = next((m for m in reversed(playoff_matches) if m['round_num'] == 100 and m['status'] == 'finished'), None)
            if final:
                if final['score1'] > final['score2']: podium['first'] = {'name': final['t1_name'], 'logo': final['t1_logo'], 'color': final['t1_color']}; podium['second'] = {'name': final['t2_name'], 'logo': final['t2_logo'], 'color': final['t2_color']}
                else: podium['first'] = {'name': final['t2_name'], 'logo': final['t2_logo'], 'color': final['t2_color']}; podium['second'] = {'name': final['t1_name'], 'logo': final['t1_logo'], 'color': final['t1_color']}
            bronze = next((m for m in reversed(playoff_matches) if m['round_num'] == 98 and m['status'] == 'finished'), None)
            if bronze:
                if bronze['score1'] > bronze['score2']: podium['third'] = {'name': bronze['t1_name'], 'logo': bronze['t1_logo'], 'color': bronze['t1_color']}
                else: podium['third'] = {'name': bronze['t2_name'], 'logo': bronze['t2_logo'], 'color': bronze['t2_color']}
        else:
            if standings and len(standings) > 0:
                podium['first'] = standings[0]
                if len(standings) > 1: podium['second'] = standings[1]
                if len(standings) > 2: podium['third'] = standings[2]
    return render_ui(DETAIL_UI, tournament=t, teams=teams, matches=matches, standings=standings, master_teams=master_teams, all_finished=all_finished, active_page='seasons', check_admin=check_admin, logs=logs_dict, my_team_ids=my_team_ids, podium=podium, preds=preds)

@app.route('/tournament/<int:t_id>/start')
@login_required
def start_tournament(t_id):
    with get_db() as conn:
        t_list = [t['id'] for t in conn.execute('SELECT id FROM teams WHERE t_id = ?', (t_id,)).fetchall()]
        t_data = conn.execute('SELECT rounds, group_count, format FROM tournaments WHERE id = ?', (t_id,)).fetchone()
        if len(t_list) < 2: flash("Nedostatečný počet záznamů."); return redirect(url_for('tournament_detail', t_id=t_id))
        random.shuffle(t_list)
        if t_data['format'] == 'knockout':
            for i in range(0, len(t_list), 2):
                if i+1 < len(t_list): conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 1)', (t_id, t_list[i], t_list[i+1]))
            conn.execute('UPDATE tournaments SET status = "active", stage = "playoffs" WHERE id = ?', (t_id,)); conn.commit(); flash("Struktura nasazena.")
            return redirect(url_for('tournament_detail', t_id=t_id))
        rounds = t_data['rounds']
        if t_data['group_count'] == 2 and len(t_list) >= 4:
            mid = len(t_list) // 2; a_teams, b_teams = t_list[:mid], t_list[mid:]
            for t_id_sub in a_teams: conn.execute('UPDATE teams SET group_name = "A" WHERE id = ?', (t_id_sub,))
            for t_id_sub in b_teams: conn.execute('UPDATE teams SET group_name = "B" WHERE id = ?', (t_id_sub,))
            for r in range(rounds):
                for i in range(len(a_teams)):
                    for j in range(i + 1, len(a_teams)):
                        t1, t2 = (a_teams[i], a_teams[j]) if r % 2 == 0 else (a_teams[j], a_teams[i])
                        conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "groups", ?)', (t_id, t1, t2, r+1))
                for i in range(len(b_teams)):
                    for j in range(i + 1, len(b_teams)):
                        t1, t2 = (b_teams[i], b_teams[j]) if r % 2 == 0 else (b_teams[j], b_teams[i])
                        conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "groups", ?)', (t_id, t1, t2, r+1))
        else:
            for r in range(rounds):
                for i in range(len(t_list)):
                    for j in range(i + 1, len(t_list)):
                        t1, t2 = (t_list[i], t_list[j]) if r % 2 == 0 else (t_list[j], t_list[i])
                        conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "groups", ?)', (t_id, t1, t2, r+1))
        conn.execute('UPDATE tournaments SET status = "active", stage = "groups" WHERE id = ?', (t_id,)); conn.commit(); flash("Turnaj odstartován.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/next_round', methods=['POST'])
@login_required
def generate_next_knockout_round(t_id):
    with get_db() as conn:
        max_r = conn.execute('SELECT MAX(round_num) FROM matches WHERE t_id = ? AND stage = "playoffs"', (t_id,)).fetchone()[0]
        if not max_r: max_r = 1
        matches = conn.execute('SELECT * FROM matches WHERE t_id = ? AND stage = "playoffs" AND round_num = ?', (t_id, max_r)).fetchall()
        winners = []
        for m in matches:
            if m['status'] != 'finished' or m['score1'] is None or m['score2'] is None: flash("Nelze generovat. Všechny zápasy aktuálního kola musí být dohrány."); return redirect(url_for('tournament_detail', t_id=t_id))
            w1 = m['team1_id'] if m['score1'] > m['score2'] else m['team2_id']; winners.append(w1)
        target_round = 100 if len(winners) == 2 else max_r + 1
        for i in range(0, len(winners), 2):
            if i+1 < len(winners): conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", ?)', (t_id, winners[i], winners[i+1], target_round))
        conn.commit(); flash("Data převedena.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/finish', methods=['POST'])
@login_required
def finish_tournament(t_id):
    with get_db() as conn: conn.execute('UPDATE tournaments SET status = "finished" WHERE id = ?', (t_id,)); conn.commit(); flash("Data uzamčena.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/playoff', methods=['POST'])
@login_required
def generate_playoff(t_id):
    conn = get_db(); t_data = conn.execute('SELECT group_count FROM tournaments WHERE id = ?', (t_id,)).fetchone(); standings = get_standings(t_id)
    if len(standings) < 2: flash("Nedostatek dat."); return redirect(url_for('tournament_detail', t_id=t_id))
    with get_db() as conn:
        conn.execute('UPDATE tournaments SET stage = "playoffs" WHERE id = ?', (t_id,))
        if t_data['group_count'] == 2 and len(standings) >= 4:
            s_a = [s for s in standings if conn.execute('SELECT group_name FROM teams WHERE id=?',(s['id'],)).fetchone()['group_name'] == 'A']
            s_b = [s for s in standings if conn.execute('SELECT group_name FROM teams WHERE id=?',(s['id'],)).fetchone()['group_name'] == 'B']
            if len(s_a) >= 2 and len(s_b) >= 2:
                conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 99)', (t_id, s_a[0]['id'], s_b[1]['id']))
                conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 99)', (t_id, s_b[0]['id'], s_a[1]['id']))
            else: conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 100)', (t_id, standings[0]['id'], standings[1]['id']))
        elif len(standings) >= 4:
            conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 99)', (t_id, standings[0]['id'], standings[3]['id']))
            conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 99)', (t_id, standings[1]['id'], standings[2]['id']))
        else: conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 100)', (t_id, standings[0]['id'], standings[1]['id']))
        conn.commit(); flash("Struktura vytvořena.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/generate_final', methods=['POST'])
@login_required
def generate_final(t_id):
    with get_db() as conn:
        matches = conn.execute('SELECT * FROM matches WHERE t_id = ? AND stage = "playoffs" AND round_num = 99 ORDER BY id ASC LIMIT 2', (t_id,)).fetchall()
        if len(matches) == 2 and matches[0]['status'] == 'finished' and matches[1]['status'] == 'finished':
            if matches[0]['score1'] is None or matches[1]['score1'] is None: flash("Nelze generovat, chybí bodové ohodnocení."); return redirect(url_for('tournament_detail', t_id=t_id))
            if matches[0]['score1'] == matches[0]['score2'] and not matches[0]['is_ot']: flash("Zápasy nesmí skončit remízou (označ PP)."); return redirect(url_for('tournament_detail', t_id=t_id))
            if matches[1]['score1'] == matches[1]['score2'] and not matches[1]['is_ot']: flash("Zápasy nesmí skončit remízou (označ PP)."); return redirect(url_for('tournament_detail', t_id=t_id))
            w1 = matches[0]['team1_id'] if matches[0]['score1'] > matches[0]['score2'] else matches[0]['team2_id']
            w2 = matches[1]['team1_id'] if matches[1]['score1'] > matches[1]['score2'] else matches[1]['team2_id']
            l1 = matches[0]['team2_id'] if matches[0]['score1'] > matches[0]['score2'] else matches[0]['team1_id']
            l2 = matches[1]['team2_id'] if matches[1]['score1'] > matches[1]['score2'] else matches[1]['team1_id']
            conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 100)', (t_id, w1, w2))
            conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 98)', (t_id, l1, l2))
            conn.commit(); flash("Finální vektor zapsán.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/match/<int:m_id>/start_timer', methods=['POST'])
@login_required
def start_timer(m_id):
    with get_db() as conn:
        ts = int(time.time()); conn.execute('UPDATE matches SET started_at = ? WHERE id = ?', (ts, m_id))
        conn.commit(); log_match_action(m_id, f"Čas spuštěn: {datetime.fromtimestamp(ts).strftime('%H:%M:%S')}")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/update', methods=['POST'])
@login_required
def update_match(m_id):
    s1, s2, is_ot = request.form.get('s1'), request.form.get('s2'), 1 if request.form.get('is_ot') else 0
    if s1 and s2:
        with get_db() as conn:
            conn.execute('UPDATE matches SET score1 = ?, score2 = ?, is_ot = ?, status = "finished", proposed_score1=NULL, proposed_score2=NULL, proposed_by_team_id=NULL, started_at=0 WHERE id = ?', (s1, s2, is_ot, m_id))
            conn.commit(); update_elo(m_id); process_predictions(m_id); log_match_action(m_id, f"Manuální zápis {s1}:{s2}{' (PP/SN)' if is_ot else ''}"); flash("Hodnota modifikována.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/forfeit/<int:w_id>', methods=['POST'])
@login_required
def forfeit_match(m_id, w_id):
    with get_db() as conn:
        m = conn.execute('SELECT * FROM matches WHERE id = ?', (m_id,)).fetchone()
        s1 = 3 if m['team1_id'] == w_id else 0; s2 = 3 if m['team2_id'] == w_id else 0
        conn.execute('UPDATE matches SET score1 = ?, score2 = ?, is_ot = 2, status = "finished", proposed_score1=NULL, proposed_score2=NULL, proposed_by_team_id=NULL, started_at = 0 WHERE id = ?', (s1, s2, m_id))
        conn.commit(); update_elo(m_id); process_predictions(m_id); log_match_action(m_id, f"Zápas kontumován {s1}:{s2}"); flash("Stav: Kontumováno.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/reset', methods=['POST'])
@login_required
def reset_match(m_id):
    with get_db() as conn:
        conn.execute('UPDATE matches SET score1 = NULL, score2 = NULL, is_ot = 0, status = "planned", proposed_score1=NULL, proposed_score2=NULL, proposed_by_team_id=NULL, started_at = 0 WHERE id = ?', (m_id,))
        conn.commit(); log_match_action(m_id, "Vymazána hodnota."); flash("Stav přepsán na nulový.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/propose', methods=['POST'])
@login_required
def propose_match(m_id):
    s1, s2, team_id, is_ot = request.form.get('s1'), request.form.get('s2'), request.form.get('team_id'), 1 if request.form.get('is_ot') else 0
    if s1 and s2:
        with get_db() as conn:
            conn.execute('UPDATE matches SET proposed_score1 = ?, proposed_score2 = ?, proposed_by_team_id = ?, is_ot = ?, status = "proposed" WHERE id = ?', (s1, s2, team_id, is_ot, m_id))
            conn.commit(); log_match_action(m_id, f"Navržen stav {s1}:{s2}{' (PP/SN)' if is_ot else ''}"); flash("Vyžadována autorizace protistrany.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/approve', methods=['POST'])
@login_required
def approve_match(m_id):
    with get_db() as conn:
        m = conn.execute('SELECT * FROM matches WHERE id = ?', (m_id,)).fetchone()
        conn.execute('UPDATE matches SET score1 = ?, score2 = ?, is_ot = ?, status = "finished", proposed_score1=NULL, proposed_score2=NULL, proposed_by_team_id=NULL, started_at=0 WHERE id = ?', (m['proposed_score1'], m['proposed_score2'], m['is_ot'], m_id))
        conn.commit(); update_elo(m_id); process_predictions(m_id); log_match_action(m_id, f"Hodnota zapsána {m['proposed_score1']}:{m['proposed_score2']}"); flash("Příkaz schválen.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/predict', methods=['POST'])
@login_required
def predict(m_id):
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO predictions (user_id, m_id, p_score1, p_score2) VALUES (?, ?, ?, ?)', (session['user_id'], m_id, int(request.form['p1']), int(request.form['p2'])))
            conn.commit(); flash("Hodnota predikce přijata.")
    except: flash("Záznam pro tento uzel již existuje.")
    return redirect(request.referrer)

@app.route('/tournament/<int:t_id>/delete', methods=['POST'])
@login_required
def delete_tournament(t_id):
    with get_db() as conn: conn.execute('DELETE FROM matches WHERE t_id = ?', (t_id,)); conn.execute('DELETE FROM teams WHERE t_id = ?', (t_id,)); conn.execute('DELETE FROM tournaments WHERE id = ? AND user_id = ?', (t_id, session['user_id'])); conn.commit(); flash("Smazáno z databáze.")
    return redirect(url_for('seasons'))

@app.route('/tournament/<int:t_id>/remove_team/<int:team_id>', methods=['POST'])
@login_required
def remove_team_tourney(t_id, team_id):
    conn = get_db(); t = conn.execute('SELECT * FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t or t['status'] != 'draft' or not check_admin(t, get_current_user()): flash("Přístup odepřen."); return redirect(url_for('tournament_detail', t_id=t_id))
    with get_db() as conn: conn.execute('DELETE FROM teams WHERE id = ? AND t_id = ?', (team_id, t_id)); conn.commit(); flash("Odstraněno ze základu.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/add_existing/<int:master_id>', methods=['POST'])
@login_required
def add_existing_team_tourney(t_id, master_id):
    conn = get_db(); tournament = conn.execute('SELECT max_teams FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if conn.execute('SELECT COUNT(*) FROM teams WHERE t_id = ?', (t_id,)).fetchone()[0] >= tournament['max_teams']: flash("Vyčerpána paměť alokace."); return redirect(url_for('tournament_detail', t_id=t_id))
    mt = conn.execute('SELECT * FROM master_teams WHERE id = ? AND user_id = ?', (master_id, session['user_id'])).fetchone()
    if mt: conn.execute('INSERT INTO teams (t_id, master_id, name, color, logo) VALUES (?, ?, ?, ?, ?)', (t_id, master_id, mt['name'], mt['color'], mt['logo'])); conn.commit(); flash("Záznam přenesen.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/referees', methods=['POST'])
@login_required
def update_referees(t_id):
    with get_db() as conn: conn.execute('UPDATE tournaments SET referees = ? WHERE id = ? AND user_id = ?', (request.form['referees'], t_id, session['user_id'])); conn.commit(); flash("Práva zapsána.")
    return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/match/<int:m_id>/schedule', methods=['POST'])
@login_required
def update_schedule(m_id):
    time_str = request.form.get('time', ''); pitch_str = request.form.get('pitch', '')
    with get_db() as conn: 
        m = conn.execute('SELECT team1_id, team2_id, t_id FROM matches WHERE id=?', (m_id,)).fetchone()
        if time_str:
            conflicts = conn.execute('SELECT id FROM matches WHERE t_id=? AND match_time=? AND id!=? AND (team1_id IN (?,?) OR team2_id IN (?,?))', (m['t_id'], time_str, m_id, m['team1_id'], m['team2_id'], m['team1_id'], m['team2_id'])).fetchall()
            if conflicts: flash(f"Detekován kolizní stav v čase {time_str}.")
            if pitch_str:
                p_conflicts = conn.execute('SELECT id FROM matches WHERE t_id=? AND match_time=? AND pitch=? AND id!=?', (m['t_id'], time_str, pitch_str, m_id)).fetchall()
                if p_conflicts: flash(f"Detekován kolizní stav na lokaci {pitch_str}.")
        conn.execute('UPDATE matches SET match_time = ?, pitch = ? WHERE id = ?', (time_str, pitch_str, m_id)); conn.commit()
        log_match_action(m_id, f"Čas/hřiště: {time_str} | {pitch_str}"); flash("Harmonogram přepsán.")
    return redirect(request.referrer)

@app.route('/match/<int:m_id>/chat', methods=['GET', 'POST'])
@login_required
def match_chat(m_id):
    user = get_current_user()
    if request.method == 'POST':
        with get_db() as conn: conn.execute('INSERT INTO match_comments (m_id, username, text, created_at) VALUES (?, ?, ?, ?)', (m_id, user['username'], request.form['text'], datetime.now().strftime("%Y-%m-%d %H:%M:%S"))); conn.commit()
        return redirect(url_for('match_chat', m_id=m_id))
    conn = get_db(); m = conn.execute('SELECT m.*, t1.name as t1_name, t1.master_id as m1_id, t2.name as t2_name, t2.master_id as m2_id FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.id = ?', (m_id,)).fetchone()
    comments = conn.execute('SELECT * FROM match_comments WHERE m_id = ? ORDER BY id ASC', (m_id,)).fetchall()
    all_h2h = conn.execute('SELECT score1, score2, team1_id, team2_id FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.status = "finished" AND ((t1.master_id = ? AND t2.master_id = ?) OR (t1.master_id = ? AND t2.master_id = ?))', (m['m1_id'], m['m2_id'], m['m2_id'], m['m1_id'])).fetchall()
    h2h_stats = {'t1_wins': 0, 't2_wins': 0, 'draws': 0}
    for old_m in all_h2h:
        if old_m['score1'] == old_m['score2']: h2h_stats['draws'] += 1
        elif old_m['team1_id'] == m['team1_id']:
            if old_m['score1'] > old_m['score2']: h2h_stats['t1_wins'] += 1
            else: h2h_stats['t2_wins'] += 1
        else:
            if old_m['score1'] > old_m['score2']: h2h_stats['t2_wins'] += 1
            else: h2h_stats['t1_wins'] += 1
    return render_ui(CHAT_HTML, m=m, comments=comments, h2h_stats=h2h_stats, active_page='none')

@app.route('/tv/<int:t_id>')
def tv_mode(t_id):
    tournament = get_db().execute('SELECT t.*, u.username FROM tournaments t JOIN users u ON t.user_id = u.id WHERE t.id = ?', (t_id,)).fetchone()
    if not tournament: return "404", 404
    teams = get_db().execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = get_db().execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, mt1.user_id as t1_user_id, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color, mt2.user_id as t2_user_id FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN master_teams mt1 ON t1.master_id = mt1.id JOIN teams t2 ON m.team2_id = t2.id JOIN master_teams mt2 ON t2.master_id = mt2.id WHERE m.t_id = ? ORDER BY m.round_num, m.id', (t_id,)).fetchall()
    standings = get_standings(t_id) if tournament['status'] != 'draft' else []
    logs_raw = get_db().execute('SELECT * FROM match_logs WHERE m_id IN (SELECT id FROM matches WHERE t_id = ?) ORDER BY id DESC', (t_id,)).fetchall()
    logs_dict = {}
    for lg in logs_raw:
        if lg['m_id'] not in logs_dict: logs_dict[lg['m_id']] = []
        logs_dict[lg['m_id']].append(lg)
    podium = None
    if tournament['status'] == 'finished':
        podium = {'first': None, 'second': None, 'third': None}; playoff_matches = [m for m in matches if m['stage'] == 'playoffs']
        if playoff_matches:
            final = next((m for m in reversed(playoff_matches) if m['round_num'] == 100 and m['status'] == 'finished'), None)
            if final:
                if final['score1'] > final['score2']: podium['first'] = {'name': final['t1_name'], 'logo': final['t1_logo'], 'color': final['t1_color']}; podium['second'] = {'name': final['t2_name'], 'logo': final['t2_logo'], 'color': final['t2_color']}
                else: podium['first'] = {'name': final['t2_name'], 'logo': final['t2_logo'], 'color': final['t2_color']}; podium['second'] = {'name': final['t1_name'], 'logo': final['t1_logo'], 'color': final['t1_color']}
            bronze = next((m for m in reversed(playoff_matches) if m['round_num'] == 98 and m['status'] == 'finished'), None)
            if bronze:
                if bronze['score1'] > bronze['score2']: podium['third'] = {'name': bronze['t1_name'], 'logo': bronze['t1_logo'], 'color': bronze['t1_color']}
                else: podium['third'] = {'name': bronze['t2_name'], 'logo': bronze['t2_logo'], 'color': bronze['t2_color']}
        else:
            if standings and len(standings) > 0:
                podium['first'] = standings[0]
                if len(standings) > 1: podium['second'] = standings[1]
                if len(standings) > 2: podium['third'] = standings[2]
    html = "<script>document.addEventListener('DOMContentLoaded', () => { let views = document.querySelectorAll('.view-carousel'); if(views.length === 0) return; let i = 0; setInterval(() => { views.forEach(v => v.classList.add('hidden')); views[i].classList.remove('hidden'); i = (i + 1) % views.length; }, 10000); });</script><meta http-equiv='refresh' content='40'>" + DETAIL_UI
    return render_ui(html, tournament=tournament, teams=teams, standings=standings, matches=matches, check_admin=lambda x,y: False, hide_nav=True, logs=logs_dict, podium=podium)

@app.route('/view/<int:t_id>')
def public_view(t_id): return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/join/<token>', methods=['GET', 'POST'])
@login_required
def join(token):
    conn = get_db()
    tournament = conn.execute('SELECT t.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = t.id) as registered_teams FROM tournaments t JOIN users u ON t.user_id = u.id WHERE t.join_token = ?', (token,)).fetchone()
    if not tournament: flash("Poškozená spojka."); return redirect(url_for('index'))
    if tournament['status'] != 'draft': flash("Data zamčena."); return redirect(url_for('tournament_detail', t_id=tournament['id']))
    if tournament['registered_teams'] >= tournament['max_teams']: flash("Kapacita naplněna."); return redirect(url_for('tournament_detail', t_id=tournament['id']))
    if request.method == 'POST':
        try:
            with get_db() as conn:
                cur = conn.cursor()
                master_id = request.form.get('master_id')
                if master_id:
                    mt = cur.execute('SELECT * FROM master_teams WHERE id = ? AND user_id = ?', (master_id, session['user_id'])).fetchone()
                    if not mt: flash("Neautorizováno."); return redirect(url_for('join', token=token))
                    m_id, name, logo, color = mt['id'], mt['name'], mt['logo'], mt['color']
                else:
                    name, logo, color = request.form.get('name'), request.form.get('logo'), request.form.get('color')
                    cur.execute('INSERT OR IGNORE INTO master_teams (user_id, name, color, logo) VALUES (?, ?, ?, ?)', (session['user_id'], name, color, logo))
                    m_id = cur.execute('SELECT id FROM master_teams WHERE user_id = ? AND name = ?', (session['user_id'], name)).fetchone()['id']
                if cur.execute('SELECT COUNT(*) FROM teams WHERE t_id = ?', (tournament['id'],)).fetchone()[0] >= tournament['max_teams']: flash("Uzel zablokován."); return redirect(url_for('index'))
                if cur.execute('SELECT id FROM teams WHERE t_id = ? AND master_id = ?', (tournament['id'], m_id)).fetchone(): flash("Již existuje."); return redirect(url_for('join', token=token))
                cur.execute('INSERT INTO teams (t_id, master_id, name, color, logo) VALUES (?, ?, ?, ?, ?)', (tournament['id'], m_id, name, color, logo)); conn.commit(); return redirect(url_for('success', team_id=cur.lastrowid))
        except Exception as e: flash(f"Nastala chyba: {str(e)}")
    my_teams = conn.execute('SELECT * FROM master_teams WHERE user_id = ? AND id NOT IN (SELECT master_id FROM teams WHERE t_id = ?)', (session['user_id'], tournament['id'])).fetchall()
    return render_ui(JOIN_UI, t_name=tournament['name'], t_username=tournament['username'], t_start_date=tournament['start_date'], t_id=tournament['id'], t_max_teams=tournament['max_teams'], t_registered_teams=tournament['registered_teams'], t_status=tournament['status'], my_teams=my_teams, active_page='none')

@app.route('/tournament/<int:t_id>/invite')
@login_required
def invite(t_id): 
    t = get_db().execute('SELECT name, join_token FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t: flash("Chybí odkazující data."); return redirect(url_for('seasons'))
    invite_url = f"{request.host_url}join/{t['join_token']}"
    return render_ui(INVITE_HTML, invite_url=invite_url, t_id=t_id, t_name=t['name'], active_page='seasons')

@app.route('/success/<int:team_id>')
def success(team_id): return render_ui("""<div class="max-w-xl mx-auto py-8 sm:py-12 text-center px-4 w-full"><h2 class="text-3xl sm:text-4xl font-black italic uppercase mb-6 sm:mb-8 theme-text-main">Vítej v turnaji!</h2><div class="navy-card p-6 sm:p-8 mb-6 sm:mb-8"><div class="w-20 h-20 sm:w-24 sm:h-24 mx-auto rounded-2xl flex items-center justify-center shadow-inner border border-white/10 mb-4" style="background-color: {{ team.color }}">{% if 'static' in team.logo %}<img src="{{team.logo}}" class="w-full h-full object-contain p-2">{% else %}<span class="text-4xl sm:text-5xl drop-shadow-md">{{ team.logo }}</span>{% endif %}</div><h3 class="text-xl sm:text-2xl font-black uppercase theme-text-main truncate">{{ team.name }}</h3></div><a href="/view/{{ team.t_id }}" class="block w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 sm:py-5 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-xs shadow-xl active:scale-95">Přejít na detail turnaje</a></div>""", team=get_db().execute('SELECT * FROM teams WHERE id = ?', (team_id,)).fetchone(), active_page='none')

@app.route('/api/live/<int:t_id>')
def api_live(t_id): return jsonify({'status': 'active'})

@app.route('/hof')
def hof():
    conn = get_db()
    teams = conn.execute('SELECT name, logo, color, elo FROM master_teams ORDER BY elo DESC LIMIT 20').fetchall()
    bettors = conn.execute('SELECT username, bet_points FROM users ORDER BY bet_points DESC LIMIT 10').fetchall()
    return render_ui(HOF_HTML, teams=teams, bettors=bettors, active_page='hof')

if __name__ == '__main__': app.run(debug=True, host='0.0.0.0', port=5000)
