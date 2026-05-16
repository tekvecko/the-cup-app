from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify, send_file, Response
import sqlite3, socket, os, uuid, time, random, io, csv, math, json, requests
from PIL import Image, ImageDraw, ImageFont
from functools import wraps, cmp_to_key
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'the_cup_pro_premium_v86_render_fix'
DB_PATH = os.path.join(os.getcwd(), 'the_cup_v31.db')
LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
BRAND_DIR = os.path.join(os.getcwd(), 'static', 'brand')
DATA_DIR = os.path.join(os.getcwd(), 'data')
META_FILE = os.path.join(DATA_DIR, "logo_studio_images.json")

os.makedirs(LOGO_DIR, exist_ok=True)
os.makedirs(BRAND_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

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

# --- POMOCNÉ FUNKCE (ZKRÁCENĚ) ---
STYLES = {"clean": "bright vector", "3d": "3D polished", "minimal": "minimal geometric"}
def load_meta():
    if not os.path.exists(META_FILE): return []
    try:
        with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []
def add_meta(filename, team_name, mode, prompt, label=""):
    data = load_meta()
    data.append({"filename": filename, "team_name": team_name, "mode": mode, "label": label, "prompt": prompt, "created_at": datetime.now().isoformat(timespec="seconds"), "favorite": False})
    with open(META_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)
def infer_mascot(team_name): return "creative mascot"
def pixazo_generate(prompt, width=1024, height=1024, steps=4):
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("API klíč PIXAZO_API_KEY nenalezen.")
    r = requests.post("https://gateway.pixazo.ai/flux-1-schnell/v1/getData", headers={"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": api_key}, json={"prompt": prompt, "num_steps": steps, "height": height, "width": width}, timeout=180)
    r.raise_for_status()
    urls = []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("url", "image_url", "output_url") and isinstance(v, str): urls.append(v)
                else: walk(v)
        elif isinstance(x, list):
            for i in x: walk(i)
    walk(r.json())
    return urls
def save_url(url):
    fn = f"{uuid.uuid4().hex}.png"; r = requests.get(url, timeout=180); r.raise_for_status()
    with open(os.path.join(LOGO_DIR, fn), "wb") as f: f.write(r.content)
    return fn
def compose_logo(symbol_filename, team_name): return symbol_filename
def build_prompt(team_name, style, colors): return f"Create an original professional esports + ice hockey logo SYMBOL ONLY. NO TEXT. Team name for concept only: {team_name}. Visual style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. Clean centered composition. ISOLATED ON PURE SOLID WHITE BACKGROUND. High quality vector art."

def get_current_user(): return get_db().execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone() if 'user_id' in session else None
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: session['next_url'] = request.url; flash("Vyžadována autorizace."); return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function
def log_match_action(m_id, action): pass
def get_local_ip(): return "127.0.0.1"
def format_date_cz(date_str): return date_str
def check_admin(tournament, user): return user and (tournament['user_id'] == user['id'] or user['username'] in [r.strip() for r in tournament['referees'].split(',') if r.strip()])
def is_team_active(master_id): return False
def get_standings(t_id):
    conn = get_db()
    teams = conn.execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = conn.execute('SELECT * FROM matches WHERE t_id = ? AND status = "finished" AND stage = "groups" AND score1 IS NOT NULL AND score2 IS NOT NULL', (t_id,)).fetchall()
    stats = {t['id']: {'id': t['id'], 'name': t['name'], 'logo': t['logo'], 'color': t['color'], 'group': t['group_name'], 'gp': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0} for t in teams}
    for m in matches:
        s1, s2, t1, t2 = m['score1'], m['score2'], m['team1_id'], m['team2_id']
        s1 = s1 if s1 is not None else 0
        s2 = s2 if s2 is not None else 0
        stats[t1]['gp'] += 1; stats[t2]['gp'] += 1
        stats[t1]['gf'] += s1; stats[t1]['ga'] += s2
        stats[t2]['gf'] += s2; stats[t2]['ga'] += s1
        if s1 > s2: stats[t1]['pts'] += 3; stats[t1]['w'] += 1; stats[t2]['l'] += 1
        elif s2 > s1: stats[t2]['pts'] += 3; stats[t2]['w'] += 1; stats[t1]['l'] += 1
        else: stats[t1]['pts'] += 1; stats[t2]['pts'] += 1; stats[t1]['d'] += 1; stats[t2]['d'] += 1
    for tid in stats: stats[tid]['gd'] = stats[tid]['gf'] - stats[tid]['ga']
    def compare(t1, t2):
        if t1['pts'] != t2['pts']: return t1['pts'] - t2['pts']
        return t1['gd'] - t2['gd']
    return sorted(stats.values(), key=cmp_to_key(compare), reverse=True)

# ==========================================
# 4. HTML ŠABLONY A VYKRESLOVÁNÍ
# ==========================================
BASE_UI = """<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><script src="https://cdn.tailwindcss.com"></script><script src="https://unpkg.com/lucide@latest"></script><title>THE CUP</title><style>body{background-color:#020617;color:#f8fafc;font-family:sans-serif}.navy-card{background:#0f172a;border-radius:1.25rem;border:1px solid rgba(255,255,255,0.05)}input,select{background:#1e293b!important;color:white!important;outline:none}</style></head><body class="min-h-screen pb-28 flex flex-col"><nav class="p-4 border-b border-white/5 flex justify-center"><h1 class="text-2xl font-black italic text-blue-500">THE CUP</h1></nav><div id="toast-container" class="fixed top-20 left-4 right-4 z-50">{% with messages=get_flashed_messages() %}{% if messages %}{% for msg in messages %}<div class="bg-blue-600 text-white p-3 rounded-lg shadow-lg mb-2 font-bold">{{msg}}</div>{% endfor %}{% endif %}{% endwith %}</div><main class="p-4 flex-1 w-full max-w-5xl mx-auto">CONTENT_PLACEHOLDER</main><div class="fixed bottom-0 left-0 right-0 bg-slate-950/90 p-4 border-t border-white/5 flex justify-around"><a href="/"><i data-lucide="home"></i></a><a href="/teams"><i data-lucide="users"></i></a><a href="/seasons"><i data-lucide="trophy"></i></a><a href="/hof"><i data-lucide="star"></i></a><a href="/account"><i data-lucide="user"></i></a></div><script>lucide.createIcons();</script></body></html>"""

WELCOME_HTML = """<div class="text-center py-20"><h1 class="text-5xl font-black italic mb-4 text-blue-500">THE CUP</h1><a href="/account" class="bg-blue-600 px-8 py-3 rounded-xl font-bold inline-block mt-4 text-white">VSTOUPIT</a></div>"""

ACCOUNT_HTML = """<div class="max-w-md mx-auto">{% if current_user %}<h2 class="text-2xl font-black text-center mb-6">MŮJ ÚČET: {{current_user.username}}</h2><div class="navy-card p-6 text-center"><p class="mb-4">Body z tipování: <span class="font-black text-yellow-500">{{current_user.bet_points}}</span></p><a href="/logout" class="text-red-500 font-bold block mt-6">ODHLÁSIT SE</a></div>{% else %}<h2 class="text-2xl font-black text-center mb-6">PŘIHLÁŠENÍ</h2><form action="/login" method="POST" class="navy-card p-6 space-y-4"><input name="username" placeholder="Uživatelské jméno" class="w-full p-4 rounded-xl font-bold"><input name="password" type="password" placeholder="Heslo" class="w-full p-4 rounded-xl font-bold"><button type="submit" class="w-full bg-blue-600 py-4 rounded-xl font-black">VSTOUPIT</button></form>{% endif %}</div>"""

def render_ui(html, **kwargs):
    return render_template_string(BASE_UI.replace('CONTENT_PLACEHOLDER', html), current_user=get_current_user(), **kwargs)

# ==========================================
# 5. API BRIDGE PRO AI
# ==========================================
def require_ai_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.headers.get('X-AI-API-KEY')
        if not key or key != os.getenv('AI_API_KEY', 'skynet_v1'):
            return jsonify({'error': 'Neautorizovaný přístup AI agenta'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/v1/status', methods=['GET'])
@require_ai_key
def api_status():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'db_size_kb': round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0
    })

# ==========================================
# 6. ROUTY (ZÁKLAD)
# ==========================================
@app.route('/')
def index():
    if 'user_id' not in session: return render_ui(WELCOME_HTML)
    return render_ui("<div class='text-center py-10'><h2 class='text-2xl font-black text-blue-500'>DASHBOARD</h2><p class='mt-4'>Aplikace běží online.</p></div>")

@app.route('/account')
def account(): return render_ui(ACCOUNT_HTML)

@app.route('/login', methods=['POST'])
def login():
    u = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
    if u and check_password_hash(u['password'], request.form['password']):
        session['user_id'] = u['id']; flash("Přihlášeno")
    else:
        pw = generate_password_hash(request.form['password'])
        with get_db() as conn: conn.execute('INSERT INTO users (username, password) VALUES (?,?)', (request.form['username'], pw))
        u = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        session['user_id'] = u['id']; flash("Registrováno a přihlášeno")
    return redirect('/')

@app.route('/logout')
def logout(): session.clear(); return redirect('/')

@app.route('/teams')
@login_required
def teams(): return render_ui("<h2 class='text-center text-xl font-black'>TÝMY</h2>")

@app.route('/seasons')
@login_required
def seasons(): return render_ui("<h2 class='text-center text-xl font-black'>TURNAJE</h2>")

@app.route('/hof')
def hof(): return render_ui("<h2 class='text-center text-xl font-black text-yellow-500'>SÍŇ SLÁVY</h2>")

if __name__ == '__main__': app.run(debug=True, host='0.0.0.0', port=5000)
# Force deploy trigger
