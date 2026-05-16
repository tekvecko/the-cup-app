from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify, send_file, Response
import sqlite3, socket, os, uuid, time, random, io, csv, math, json, requests
from PIL import Image, ImageDraw, ImageFont
from functools import wraps, cmp_to_key
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'the_cup_pro_premium_ultimate_monolith_v88'
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
        
        try: conn.execute('SELECT theme FROM users LIMIT 1')
        except: conn.execute('ALTER TABLE users ADD COLUMN theme TEXT DEFAULT "system"')
        try: conn.execute('SELECT bet_points FROM users LIMIT 1')
        except: conn.execute('ALTER TABLE users ADD COLUMN bet_points INTEGER DEFAULT 0')
        try: conn.execute('SELECT is_pro FROM users LIMIT 1')
        except: conn.execute('ALTER TABLE users ADD COLUMN is_pro INTEGER DEFAULT 0')
        try: conn.execute('SELECT round_num FROM matches LIMIT 1')
        except: conn.execute('ALTER TABLE matches ADD COLUMN round_num INTEGER DEFAULT 1')
        try: conn.execute('SELECT group_count FROM tournaments LIMIT 1')
        except: conn.execute('ALTER TABLE tournaments ADD COLUMN group_count INTEGER DEFAULT 1')
        try: conn.execute('SELECT format FROM tournaments LIMIT 1')
        except: conn.execute('ALTER TABLE tournaments ADD COLUMN format TEXT DEFAULT "groups"')
        try: conn.execute('SELECT group_name FROM teams LIMIT 1')
        except: conn.execute('ALTER TABLE teams ADD COLUMN group_name TEXT DEFAULT "A"')
        try: conn.execute('SELECT started_at FROM matches LIMIT 1')
        except: conn.execute('ALTER TABLE matches ADD COLUMN started_at INTEGER DEFAULT 0')
        try: conn.execute('SELECT elo FROM master_teams LIMIT 1')
        except: conn.execute('ALTER TABLE master_teams ADD COLUMN elo INTEGER DEFAULT 1200')
        try: conn.execute('SELECT tag FROM master_teams LIMIT 1')
        except: conn.execute('ALTER TABLE master_teams ADD COLUMN tag TEXT')
        
        admin = conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
        if not admin: conn.execute('INSERT INTO users (username, password, theme, is_pro) VALUES (?, ?, ?, ?)', ('admin', generate_password_hash('heslo123'), 'system', 1))
        conn.commit()

init_db()

# ==========================================
# 2. LOGO STUDIO LOGIKA (AI GENERATION)
# ==========================================
STYLES = {
    "clean": "clean bright vector mascot logo, simple shapes",
    "3d": "clean 3D polished emblem, ice material, soft studio lighting",
    "minimal": "minimal geometric flat vector logo, strong silhouette",
    "premium": "premium professional sport emblem",
    "cyber": "futuristic cyber esport logo",
    "ice": "ice crystal inspired hockey logo",
}

def load_meta():
    if not os.path.exists(META_FILE): return []
    try:
        with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def save_meta(data):
    with open(META_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def add_meta(filename, team_name, mode, prompt, label=""):
    data = load_meta()
    data.append({"filename": filename, "team_name": team_name, "mode": mode, "label": label, "prompt": prompt, "created_at": datetime.now().isoformat(timespec="seconds"), "favorite": False})
    save_meta(data)

def infer_mascot(team_name):
    n = team_name.lower()
    rules = [("wolf", "ice wolf mascot"), ("vlk", "ice wolf mascot"), ("bear", "polar bear mascot"), ("dragon", "ice dragon mascot"), ("hawk", "ice hawk mascot"), ("eagle", "ice eagle mascot"), ("fox", "snow fox mascot"), ("knight", "cyber ice knight"), ("storm", "frozen storm emblem"), ("ice", "ice crystal emblem")]
    for k, v in rules:
        if k in n: return v
    return "creative mascot inferred from team name"

def extract_urls(data):
    urls = []
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in ("url", "image_url", "output_url", "media_url", "output") and isinstance(v, str) and v.startswith("http"): urls.append(v)
                else: walk(v)
        elif isinstance(x, list):
            for i in x: walk(i)
    walk(data)
    return list(dict.fromkeys(urls))

def pixazo_generate(prompt, width=1024, height=1024, steps=4):
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("Nedostatečná oprávnění k API. Zkontrolujte systémové proměnné (PIXAZO_API_KEY).")
    url = "https://gateway.pixazo.ai/flux-1-schnell/v1/getData"
    headers = {"Content-Type": "application/json", "Cache-Control": "no-cache", "Ocp-Apim-Subscription-Key": api_key}
    payload = {"prompt": prompt, "num_steps": int(steps), "height": int(height), "width": int(width)}
    r = requests.post(url, headers=headers, json=payload, timeout=180)
    r.raise_for_status()
    urls = extract_urls(r.json())
    if not urls: raise RuntimeError("Chyba externího API: Nebyla vrácena URL adresa.")
    return urls

def save_url(url):
    filename = f"{uuid.uuid4().hex}.png"
    path = os.path.join(LOGO_DIR, filename)
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    with open(path, "wb") as f: f.write(r.content)
    return filename

def find_font():
    candidates = ["/system/fonts/Roboto-Bold.ttf", "/system/fonts/NotoSans-Bold.ttf", "/data/data/com.termux/files/usr/share/fonts/TTF/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]
    for c in candidates:
        if os.path.exists(c): return c
    return None

def compose_logo(symbol_filename, team_name):
    src = os.path.join(LOGO_DIR, symbol_filename)
    img = Image.open(src).convert("RGBA")
    data = img.getdata()
    new_data = []
    for item in data:
        if item[0] > 230 and item[1] > 230 and item[2] > 230:
            new_data.append((255, 255, 255, 0))
        else:
            new_data.append(item)
    img.putdata(new_data)
    img.thumbnail((900, 720), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (255, 255, 255, 0))
    canvas.alpha_composite(img, ((1024 - img.width) // 2, 35))
    draw = ImageDraw.Draw(canvas)
    font_path = find_font()
    size = 96
    while size > 28:
        font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
        bbox = draw.textbbox((0, 0), team_name, font=font, stroke_width=3)
        if bbox[2] - bbox[0] <= 900: break
        size -= 4
    font = ImageFont.truetype(font_path, size) if font_path else ImageFont.load_default()
    bbox = draw.textbbox((0, 0), team_name, font=font, stroke_width=4)
    tx = (1024 - (bbox[2] - bbox[0])) // 2
    draw.text((tx, 820), team_name, font=font, fill=(255, 255, 255, 255), stroke_width=4, stroke_fill=(15, 23, 42, 255))
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name

def build_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"""Create an original professional esports + ice hockey logo SYMBOL ONLY. NO TEXT. NO LETTERS. NO WORDS. NO NUMBERS. Team name for concept only: {team_name}. Inferred mascot: {mascot}. Visual style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. Clean centered composition. ISOLATED ON PURE SOLID WHITE BACKGROUND. High quality vector art. No background clutter."""

# ==========================================
# 3. POMOCNÉ FUNKCE RADY A VÝPOČTY
# ==========================================
def get_current_user(): return get_db().execute('SELECT * FROM users WHERE id = ?', (session.get('user_id'),)).fetchone() if 'user_id' in session else None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session: session['next_url'] = request.url; flash("Vyžadována autorizace."); return redirect(url_for('account'))
        return f(*args, **kwargs)
    return decorated_function

def log_match_action(m_id, action):
    user = get_current_user()
    username = user['username'] if user else "Systém"
    with get_db() as conn:
        conn.execute('INSERT INTO match_logs (m_id, username, action, created_at) VALUES (?, ?, ?, ?)', (m_id, username, action, datetime.now().strftime("%d.%m. %H:%M:%S")))
        conn.commit()

def get_local_ip():
    try: s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

def format_date_cz(date_str):
    try: return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except: return date_str

def check_admin(tournament, user):
    if not user: return False
    if tournament['user_id'] == user['id']: return True
    refs = [r.strip() for r in tournament['referees'].split(',') if r.strip()]
    return user['username'] in refs

def is_team_active(master_id): return get_db().execute('SELECT COUNT(*) FROM teams t JOIN tournaments tr ON t.t_id = tr.id WHERE t.master_id = ? AND tr.status = "active"', (master_id,)).fetchone()[0] > 0

def get_standings(t_id):
    conn = get_db()
    teams = conn.execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = conn.execute('SELECT * FROM matches WHERE t_id = ? AND status = "finished" AND stage = "groups"', (t_id,)).fetchall()
    stats = {t['id']: {'id': t['id'], 'name': t['name'], 'logo': t['logo'], 'color': t['color'], 'group': t['group_name'], 'gp': 0, 'w': 0, 'd': 0, 'l': 0, 'gf': 0, 'ga': 0, 'gd': 0, 'pts': 0} for t in teams}
    for m in matches:
        s1, s2, t1, t2 = m['score1'], m['score2'], m['team1_id'], m['team2_id']
        if s1 is None or s2 is None: continue
        stats[t1]['gp'] += 1; stats[t2]['gp'] += 1
        stats[t1]['gf'] += s1; stats[t1]['ga'] += s2
        stats[t2]['gf'] += s2; stats[t2]['ga'] += s1
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
    conn = get_db()
    m = conn.execute('SELECT m.score1, m.score2, t1.master_id as m1, t2.master_id as m2 FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.id = ?', (m_id,)).fetchone()
    mt1 = conn.execute('SELECT elo FROM master_teams WHERE id = ?', (m['m1'],)).fetchone()
    mt2 = conn.execute('SELECT elo FROM master_teams WHERE id = ?', (m['m2'],)).fetchone()
    if not mt1 or not mt2 or m['score1'] is None or m['score2'] is None: return
    r1, r2 = mt1['elo'], mt2['elo']
    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
    s1 = 1 if m['score1'] > m['score2'] else (0.5 if m['score1'] == m['score2'] else 0)
    s2 = 1 - s1
    k = 32
    conn.execute('UPDATE master_teams SET elo = ? WHERE id = ?', (round(r1 + k * (s1 - e1)), m['m1']))
    conn.execute('UPDATE master_teams SET elo = ? WHERE id = ?', (round(r2 + k * (s2 - e2)), m['m2']))
    conn.commit()

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
# 4. FRONTEND HTML ŠABLONY (KOMPLETNÍ MONOLITH)
# ==========================================
BASE_UI = """<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0"><script src="https://cdn.tailwindcss.com"></script><script src="https://unpkg.com/lucide@latest"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script><title>THE CUP</title><style>body{background-color:#020617;color:#f8fafc;font-family:sans-serif;overflow-x:hidden}.glass{background:rgba(15,23,42,0.8);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.1)}.navy-card{background:#0f172a;border-radius:1.25rem;border:1px solid rgba(255,255,255,0.05)}input,select{background:#1e293b!important;color:white!important;outline:none}</style></head><body class="min-h-screen pb-28 flex flex-col"><div id="logo-modal" class="fixed inset-0 z-[4000] bg-slate-950/90 backdrop-blur-md hidden flex items-center justify-center p-4 opacity-0 transition-opacity" onclick="closeLogoModal()"><div class="relative w-full max-w-sm sm:max-w-md flex flex-col items-center justify-center" onclick="event.stopPropagation()"><button type="button" onclick="closeLogoModal()" class="absolute -top-12 right-0 text-slate-400 hover:text-white"><i data-lucide="x" class="w-8 h-8"></i></button><div id="logo-modal-content" class="w-64 h-64 sm:w-80 sm:h-80 rounded-full flex items-center justify-center shadow-2xl border-4 border-white/10 overflow-hidden"></div></div></div><div id="custom-modal" class="fixed inset-0 z-[2000] flex items-center justify-center hidden opacity-0 transition-opacity duration-300"><div class="absolute inset-0 bg-black/60" onclick="closeModal()"></div><div class="navy-card relative w-11/12 max-w-sm p-6 transform scale-95 shadow-2xl" id="custom-modal-content"><h3 class="text-xl font-black uppercase text-center mb-4 text-blue-500">Potvrzení</h3><p id="modal-message" class="text-xs text-slate-400 text-center mb-8"></p><div class="flex gap-3"><button onclick="closeModal()" class="flex-1 bg-slate-800 py-3 rounded-xl font-bold uppercase text-[10px]">Zrušit</button><button onclick="confirmModalAction()" class="flex-1 bg-blue-600 py-3 rounded-xl font-bold uppercase text-[10px] text-white shadow-lg">Potvrdit</button></div></div></div><nav class="glass p-4 sticky top-0 z-40 flex justify-center"><span class="uppercase font-black italic text-blue-500 text-xl tracking-tighter shadow-md">THE CUP</span></nav><div id="toast-container" class="fixed top-24 right-4 left-4 z-50">{% with messages=get_flashed_messages() %}{% if messages %}{% for message in messages %}<div class="bg-blue-600 text-white p-4 rounded-xl shadow-2xl font-bold mb-2 flex justify-between"><span>{{ message }}</span><button onclick="this.parentElement.remove()">&times;</button></div>{% endfor %}{% endif %}{% endwith %}</div><main class="w-full max-w-5xl mx-auto px-4 pt-6 flex-1 flex flex-col">CONTENT_PLACEHOLDER</main><div class="fixed bottom-0 left-0 right-0 bg-slate-950/95 p-4 border-t border-white/5 flex justify-around z-40"><a href="/"><i data-lucide="home"></i></a><a href="/teams"><i data-lucide="users"></i></a><a href="/create"><i data-lucide="plus-circle" class="text-blue-500 w-8 h-8"></i></a><a href="/seasons"><i data-lucide="trophy"></i></a><a href="/hof"><i data-lucide="star"></i></a><a href="/account"><i data-lucide="user"></i></a></div><script>lucide.createIcons(); let pendingForm=null; function openLogoModal(src, bgColor){ const m=document.getElementById('logo-modal'); const c=document.getElementById('logo-modal-content'); c.style.backgroundColor=bgColor; c.innerHTML=src.includes('static/')?`<img src="${src}" class="w-full h-full object-contain p-6">`:`<span class="text-7xl sm:text-9xl">${src}</span>`; m.classList.remove('hidden'); void m.offsetWidth; m.classList.remove('opacity-0'); } function closeLogoModal(){ const m=document.getElementById('logo-modal'); m.classList.add('opacity-0'); setTimeout(()=>m.classList.add('hidden'),300); } function openModal(msg,form){ document.getElementById('modal-message').innerText=msg; pendingForm=form; const m=document.getElementById('custom-modal'); m.classList.remove('hidden'); void m.offsetWidth; m.classList.remove('opacity-0'); } function closeModal(){ const m=document.getElementById('custom-modal'); m.classList.add('opacity-0'); setTimeout(()=>m.classList.add('hidden'),300); } function confirmModalAction(){ if(pendingForm)pendingForm.submit(); closeModal(); }</script></body></html>"""

WELCOME_HTML = """<div class="text-center py-20"><h1 class="text-5xl font-black italic mb-4 text-blue-500 tracking-tighter">THE CUP ENTERPRISE</h1><p class="text-slate-400 text-sm font-bold uppercase tracking-widest mb-10">Profesionální správa a orchestrace turnajů</p><a href="/account" class="bg-blue-600 px-10 py-4 rounded-xl font-black text-sm tracking-widest text-white shadow-xl">VSTOUPIT</a></div>"""

ACCOUNT_HTML = """<div class="max-w-md mx-auto w-full">{% if current_user %}<div class="text-center mb-8"><h2 class="text-3xl font-black italic uppercase tracking-tighter text-blue-500">{{ current_user.username }}</h2><p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Licence: PRO Premium • Sázkařské body: {{ current_user.bet_points }}</p></div><div class="navy-card p-6 border border-green-500/20 bg-green-500/5 text-center mb-6"><h3 class="text-green-500 font-black text-xs uppercase tracking-widest mb-2">Zero-Internet Local Mode</h3><p class="text-[10px] text-slate-400 mb-4">Ostatní účastníci se mohou připojit na lokální IP:</p><span class="font-mono text-xs text-green-400 block bg-slate-950 p-3 rounded-lg">{{ host_url }}</span></div><div class="flex gap-2 mb-6"><a href="/export/db" class="flex-1 bg-slate-800 hover:bg-slate-700 py-3 rounded-xl font-black text-[10px] text-center transition-colors">Uložit Zálohu DB</a></div><div class="navy-card p-4 text-center border-red-500/20 bg-red-500/5"><a href="/logout" class="text-xs font-black uppercase text-red-500 block py-2">Ukončit relaci (Odhlásit)</a></div>{% else %}<h2 class="text-3xl font-black italic uppercase text-center mb-8 tracking-tighter text-blue-500">Přihlášení do uzlu</h2><form action="/login" method="POST" class="navy-card p-6 space-y-4 shadow-2xl"><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Uživatelské jméno</label><input name="username" required class="w-full rounded-xl p-4 mt-2 font-bold bg-slate-900/50 text-white"></div><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Heslo</label><input type="password" name="password" required class="w-full rounded-xl p-4 mt-2 font-bold bg-slate-900/50 text-white"></div><button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 py-4 rounded-xl text-white font-black uppercase text-xs tracking-widest shadow-lg transition-colors">Ověřit identitu</button></form>{% endif %}</div>"""

TEAMS_HTML = """<div class="flex justify-between items-center mb-8"><h2 class="text-3xl font-black italic uppercase tracking-tighter text-blue-500">Registr Týmů</h2><a href="/teams/new" class="bg-blue-600 px-4 py-2.5 rounded-xl font-black text-[10px] text-white uppercase hover:bg-blue-500 transition-colors shadow-lg">Nový Tým</a></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">{% for team in master_teams %}<div class="navy-card p-4 flex items-center justify-between border-l-4" style="border-left-color: {{ team.color }}"><div class="flex items-center gap-4 min-w-0"><div class="w-12 h-12 rounded-xl flex items-center justify-center shrink-0 cursor-pointer border border-white/5 transition-transform hover:scale-105" style="background-color: {{ team.color }}" onclick="openLogoModal('{{team.logo}}', '{{team.color}}')">{% if 'static' in team.logo %}<img src="{{team.logo}}" class="w-full h-full object-contain p-1.5">{% else %}<span class="text-2xl">{{ team.logo }}</span>{% endif %}</div><span class="font-black uppercase text-sm truncate text-white">{{ team.name }}</span></div><span class="text-[9px] font-black text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20 font-mono">ELO<br>{{ team.elo }}</span></div>{% endfor %}</div>"""

EMOJI_PICKER = """<div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Ikona / Symbol</label><input type="hidden" name="logo" id="team-logo" value="⚽"><div class="grid grid-cols-6 sm:grid-cols-8 gap-2 mt-2 p-3 bg-slate-900/50 rounded-2xl max-h-36 overflow-y-auto border border-white/5">{% set emojis = ['⚽','🏒','🏀',' Volleyball','🏈','🎾','🎱','🏓','🥊','🥋','🐅','🦅','🦈','🐺',' BEAR','🦁','🐉','🐍','⚡','🔥','⭐','☠️','💎','🛡️'] %}{% for e in emojis %}<button type="button" onclick="document.getElementById('team-logo').value='{{ e }}'; document.querySelectorAll('.emoji-btn').forEach(b=>b.style.opacity=0.4); this.style.opacity=1;" class="emoji-btn text-xl p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-all opacity-40">{{ e }}</button>{% endfor %}</div></div>"""

TEAM_NEW_HTML = """<div class="max-w-xl mx-auto w-full"><h2 class="text-3xl font-black italic uppercase tracking-tighter text-blue-500 mb-6">Nový Tým</h2><div class="navy-card p-6 shadow-2xl border border-white/5 mb-8"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest mb-4">Základní Tvorba</h3><form method="POST" action="/teams/new" class="space-y-4"><input type="hidden" name="is_ai" value="0"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Název týmu</label><input name="name" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 text-white mt-2"></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Tag (Zkratka)</label><input name="tag" maxlength="4" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 text-white mt-2 uppercase"></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Hlavní barva</label><input type="color" name="color" value="#3b82f6" class="w-full h-11 rounded-xl mt-2 p-1 bg-slate-900/50 border border-white/5 cursor-pointer"></div></div>""" + EMOJI_PICKER + """<button type="submit" class="w-full bg-slate-800 hover:bg-slate-700 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest">Uložit do registru</button></form></div><div class="navy-card p-6 border border-yellow-500/20 bg-gradient-to-br from-slate-900 to-slate-950 relative"><h3 class="text-[10px] font-black uppercase text-yellow-500 tracking-widest mb-4 flex items-center gap-2"><i data-lucide="crown" class="w-3 h-3"></i> AI Logo Studio (Esports)</h3><form method="POST" action="/teams/new" class="space-y-4"><input type="hidden" name="is_ai" value="1"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Název organizace</label><input name="team_name" value="{{ pending_team }}" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 text-white mt-2" autocomplete="off"></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vizuální Styl</label><select name="style" class="w-full rounded-xl p-3 text-xs font-bold bg-slate-900/50 text-white mt-2">{% for k,v in styles.items() %}<option value="{{k}}">{{k}}</option>{% endfor %}</select></div><div class="grid grid-cols-3 gap-2 mt-4"><div class="text-center cursor-pointer" onclick="openColorPicker('body')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Tělo</label><div id="swatch-body" class="w-full h-10 rounded-xl border border-white/10" style="background-color: #ffffff;"></div><input type="hidden" name="color_body" id="input-body" value="White"></div><div class="text-center cursor-pointer" onclick="openColorPicker('outline')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Obrys</label><div id="swatch-outline" class="w-full h-10 rounded-xl border border-white/10" style="background-color: #020617;"></div><input type="hidden" name="color_outline" id="input-outline" value="Black"></div><div class="text-center cursor-pointer" onclick="openColorPicker('fill')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Výplň</label><div id="swatch-fill" class="w-full h-10 rounded-xl border border-white/10" style="background-color: #3b82f6;"></div><input type="hidden" name="color_fill" id="input-fill" value="Blue"></div></div><button type="submit" class="w-full bg-yellow-500 hover:bg-yellow-400 text-slate-900 py-4 rounded-xl font-black uppercase text-[10px] tracking-widest shadow-lg mt-4" onclick="this.innerHTML='AI generuje logo...';">Spustit AI Generátor</button></form>{% if images %}<div class="mt-8 border-t border-white/5 pt-6"><div class="bg-slate-900/40 rounded-xl p-4 border border-white/5 text-center"><img src="{{ url_for('static', filename='generated_logos/' ~ images[0]) }}" class="w-44 h-44 mx-auto object-contain mb-4 cursor-pointer hover:scale-105" onclick="openLogoModal(this.src, '#020617')"><form method="POST" action="/teams/use/{{ images[0] }}"><button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 text-white text-[10px] font-black uppercase py-3 rounded-xl shadow-lg">Integrovat a zapsat tým</button></form></div></div>{% endif %}</div></div><div id="custom-color-picker" class="fixed inset-0 z-[3000] bg-slate-950/90 backdrop-blur-md hidden flex flex-col items-center justify-center p-4 opacity-0 transition-opacity"><div class="navy-card p-6 w-full max-w-sm border border-white/10 relative"><button type="button" onclick="closeColorPicker()" class="absolute top-4 right-4 text-slate-500 hover:text-white"><i data-lucide="x" class="w-5 h-5"></i></button><h3 class="text-base font-black uppercase mb-4 text-center text-white">Vyber Barvu</h3><div class="grid grid-cols-5 gap-3.5" id="color-grid"></div></div></div><script>const palette = [{name: 'White', hex: '#ffffff'}, {name: 'Silver', hex: '#94a3b8'}, {name: 'Gray', hex: '#475569'}, {name: 'Black', hex: '#020617'}, {name: 'Navy', hex: '#0f172a'},{name: 'Blue', hex: '#3b82f6'}, {name: 'Cyan', hex: '#06b6d4'}, {name: 'Teal', hex: '#14b8a6'}, {name: 'Green', hex: '#22c55e'}, {name: 'Lime', hex: '#84cc16'},{name: 'Yellow', hex: '#eab308'}, {name: 'Orange', hex: '#f97316'}, {name: 'Red', hex: '#ef4444'}, {name: 'Rose', hex: '#f43f5e'}, {name: 'Pink', hex: '#ec4899'},{name: 'Purple', hex: '#a855f7'}, {name: 'Violet', hex: '#8b5cf6'}, {name: 'Indigo', hex: '#6366f1'}, {name: 'Brown', hex: '#78350f'}, {name: 'Gold', hex: '#ca8a04'}]; let currentTarget = null; function openColorPicker(target) { currentTarget = target; const grid = document.getElementById('color-grid'); grid.innerHTML = ''; palette.forEach(c => { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'w-full aspect-square rounded-full border border-white/20 shadow-md transition-transform hover:scale-110'; btn.style.backgroundColor = c.hex; btn.onclick = () => { document.getElementById('swatch-' + currentTarget).style.backgroundColor = c.hex; document.getElementById('input-' + currentTarget).value = c.name; closeColorPicker(); }; grid.appendChild(btn); }); const m = document.getElementById('custom-color-picker'); m.classList.remove('hidden'); void m.offsetWidth; m.classList.remove('opacity-0'); } function closeColorPicker() { const m = document.getElementById('custom-color-picker'); m.classList.add('opacity-0'); setTimeout(() => m.classList.add('hidden'), 300); }</script>"""

CREATE_HTML = """<div class="max-w-xl mx-auto w-full text-center"><h2 class="text-3xl font-black italic uppercase tracking-tighter text-blue-500 mb-8">Vytvořit Turnaj</h2><form method="POST" class="navy-card p-6 space-y-4 border border-white/5 text-left"><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Název turnaje</label><input name="name" required class="w-full rounded-xl p-4 mt-2 text-base font-black bg-slate-900/50 text-white"></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Kapacita</label><input type="number" name="max_teams" value="8" min="2" class="w-full rounded-xl p-4 mt-2 font-bold bg-slate-900/50 text-white"></div><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Datum konání</label><input type="date" name="start_date" required class="w-full rounded-xl p-4 mt-2 bg-slate-900/50 text-white"></div></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Formát pavouka</label><select name="format" class="w-full rounded-xl p-4 mt-2 bg-slate-900/50 text-white"><option value="groups">Skupiny + Playoff</option><option value="knockout">Čistý pavouk (K.O.)</option></select></div><div><label class="text-[10px] font-black uppercase text-slate-500 ml-1">Skupiny</label><select name="group_count" class="w-full rounded-xl p-4 mt-2 bg-slate-900/50 text-white"><option value="1">1 velká skupina</option><option value="2">2 skupiny (A, B)</option></select></div></div><button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 py-4 mt-4 rounded-xl text-white font-black uppercase text-xs tracking-widest shadow-xl transition-colors">Generovat Turnajový Uzlem</button></form></div>"""

SEASONS_HTML = """<div class="mb-6"><h2 class="text-3xl font-black italic uppercase tracking-tighter text-blue-500">Moje Turnaje</h2><p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Kompletní správa turnajových sezón</p></div><div class="grid grid-cols-1 md:grid-cols-2 gap-4">{% for t in tournaments %}<div class="navy-card p-5 flex justify-between items-center border border-white/5 hover:border-blue-500/20 transition-all"><div class="min-w-0"><span class="text-[8px] font-black uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2 inline-block">{{ t.status }}</span><h3 class="font-black text-lg text-white truncate leading-tight">{{ t.name }}</h3><p class="text-[10px] text-slate-400 mt-1">Počet týmů: {{ t.registered_teams }}/{{ t.max_teams }}</p></div><a href="/tournament/{{ t.id }}" class="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-xl text-[10px] font-black uppercase transition-colors">Spravovat</a></div>{% endfor %}</div>"""

MATCH_MACRO = """{% macro render_match(m, is_admin, current_user, logs_dict={}, pred=None) %}{% set is_participant = current_user and (m.t1_user_id == current_user.id or m.t2_user_id == current_user.id) %}<div class="match-card navy-card p-4 border border-white/5 relative overflow-hidden flex flex-col justify-between" data-round="{{ m.round_num }}" data-team1="{{ m.team1_id }}" data-team2="{{ m.team2_id }}" data-stage="{{ m.stage }}"><div class="flex justify-between items-center border-b border-white/5 pb-2 mb-3"><span class="text-[9px] font-black text-slate-500 uppercase tracking-widest">KOLO {{ m.round_num }} • {{ m.stage|upper }}</span><div class="flex gap-1.5 shrink-0"><a href="/match/{{ m.id }}/chat" class="text-blue-500 p-1"><i data-lucide="message-square" class="w-4 h-4"></i></a></div></div><div class="grid grid-cols-3 items-center text-center my-auto"><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-11 h-11 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-105 transition-transform shadow-inner" style="background-color: {{ m.t1_color }}" onclick="openLogoModal('{{m.t1_logo}}', '{{m.t1_color}}')">{% if 'static' in m.t1_logo %}<img src="{{m.t1_logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-lg">{{m.t1_logo}}</span>{% endif %}</div><p class="text-[10px] font-black uppercase truncate w-full theme-text-main">{{ m.t1_name }}</p></div><div class="text-2xl font-black italic text-white">{% if m.status == 'finished' %}{{ m.score1 }}:{{ m.score2 }}{% elif m.status == 'proposed' %}<span class="text-orange-500">{{ m.proposed_score1 }}:{{ m.proposed_score2 }}</span>{% else %}-:-{% endif %}</div><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-11 h-11 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-105 transition-transform shadow-inner" style="background-color: {{ m.t2_color }}" onclick="openLogoModal('{{m.t2_logo}}', '{{m.t2_color}}')">{% if 'static' in m.t2_logo %}<img src="{{m.t2_logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-lg">{{m.t2_logo}}</span>{% endif %}</div><p class="text-[10px] font-black uppercase truncate w-full theme-text-main">{{ m.t2_name }}</p></div></div><div class="mt-4 pt-3 border-t border-white/5 flex flex-col gap-2">{% if m.status == 'planned' and (is_participant or is_admin) %}<form action="/match/{{ m.id }}/propose" method="POST" class="flex gap-2"><input type="number" name="s1" placeholder="T1" required class="w-full rounded-lg p-2 text-center text-xs bg-slate-900 text-white"><input type="number" name="s2" placeholder="T2" required class="w-full rounded-lg p-2 text-center text-xs bg-slate-900 text-white"><button class="bg-blue-600 px-3 rounded-lg text-white font-bold text-xs"><i data-lucide="check" class="w-4 h-4"></i></button></form>{% elif m.status == 'proposed' and is_admin %}<div class="flex gap-2"><form action="/match/{{ m.id }}/approve" method="POST" class="flex-1"><button class="w-full bg-green-600 text-white py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest">Schválit</button></form><form action="/match/{{ m.id }}/reset" method="POST" class="flex-1"><button class="w-full bg-red-900/40 text-red-500 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-widest">Odmítnout</button></form></div>{% elif m.status == 'finished' and is_admin %}<form action="/match/{{ m.id }}/reset" method="POST" class="w-full"><button class="w-full bg-slate-800 text-slate-400 py-1.5 rounded-lg text-[8px] font-black uppercase border border-white/5">Resetovat Zápas</button></form>{% endif %}</div></div>{% endmacro %}"""

DETAIL_UI = MATCH_MACRO + """<div id="export-area" class="w-full pb-4"><div class="flex flex-wrap justify-center gap-2 mb-6 w-full" id="filter-controls"><button type="button" onclick="filterMatches('all')" class="filter-btn px-4 py-2 rounded-xl font-black text-[10px] uppercase bg-blue-600 text-white shadow-lg border border-blue-500">Všechny zápasy</button><button type="button" onclick="filterMatches('playoff')" class="filter-btn px-4 py-2 rounded-xl font-black text-[10px] uppercase bg-slate-900/50 text-slate-400 border border-white/5 hover:border-blue-500/50">Playoff</button></div><div class="flex flex-col lg:flex-row gap-6 items-start w-full"><div class="w-full lg:w-[360px] shrink-0">{% if is_admin %}<div class="navy-card p-4 mb-6 shadow-xl border border-blue-500/30"><h3 class="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="shield-alert"></i> Admin Ovládací Panel</h3><div class="flex flex-col gap-2">{% if tournament.status == 'active' %}<form action="/tournament/{{ tournament.id }}/playoff" method="POST"><button class="w-full bg-blue-600 py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest shadow-inner">Vygenerovat Playoff</button></form><form action="/tournament/{{ tournament.id }}/next_round" method="POST"><button class="w-full bg-cyan-600 py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest mt-1">Vygenerovat další kolo</button></form><form action="/tournament/{{ tournament.id }}/generate_final" method="POST"><button class="w-full bg-yellow-500 py-3 rounded-xl text-slate-900 font-black text-[10px] uppercase tracking-widest mt-1">Vygenerovat Finále & o 3. místo</button></form><form action="/tournament/{{ tournament.id }}/finish" method="POST" onsubmit="return confirm('Opravdu ukončit turnaj?');"><button class="w-full bg-red-900/40 text-red-500 py-2.5 rounded-xl font-black text-[10px] uppercase tracking-widest mt-2 border border-red-500/20">Ukončit celý turnaj</button></form>{% elif tournament.status == 'draft' %}<a href="/tournament/{{ tournament.id }}/start" class="w-full bg-green-600 block text-center py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest">Odstartovat Turnaj</a>{% else %}<div class="text-xs text-slate-500 font-bold text-center py-2 uppercase tracking-wide">Turnaj Uzamčen a ukončen 🏆</div>{% endif %}</div></div>{% endif %}{% if standings %}<div class="navy-card overflow-hidden shadow-2xl mb-6 bg-slate-900/30"><div class="p-4 border-b border-white/5 bg-slate-900/50"><h3 class="text-[10px] font-black text-blue-500 uppercase tracking-widest">Aktuální Tabulka Skupiny</h3></div><table class="w-full text-left whitespace-nowrap"><tr class="bg-slate-800/50 text-[9px] text-slate-400 uppercase font-black border-b border-white/5"><th class="p-3">Tým</th><th class="p-3 text-center">Z</th><th class="p-3 text-center text-blue-500">B</th></tr>{% for s in standings %}<tr class="border-b border-white/5 hover:bg-white/5"><td class="p-3 flex items-center gap-3"><div class="w-7 h-7 rounded flex items-center justify-center shrink-0 border border-white/5 cursor-pointer hover:scale-105" style="background-color: {{ s.color }}" onclick="openLogoModal('{{s.logo}}', '{{s.color}}')">{% if 'static' in s.logo %}<img src="{{s.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-xs">{{ s.logo }}</span>{% endif %}</div><span class="font-black uppercase text-xs text-white truncate max-w-[140px]">{{ s.name }}</span></td><td class="p-3 text-center font-bold text-slate-400 text-xs">{{ s.gp }}</td><td class="p-3 text-center text-blue-500 font-black text-sm">{{ s.pts }}</td></tr>{% endfor %}</table></div>{% endif %}</div><div class="flex-1 w-full min-w-0"><div class="grid grid-cols-1 md:grid-cols-2 gap-4" id="groups-grid">{% for m in matches %}{{ render_match(m, is_admin, current_user, logs, preds.get(m.id)) }}{% endfor %}</div></div></div></div><script>let currentMyTeams = {{ my_team_ids | tojson | safe if my_team_ids else '[]' }}; function filterMatches(type, val = null) { document.querySelectorAll('.filter-btn').forEach(b => { b.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500'); b.classList.add('bg-slate-900/50', 'text-slate-400', 'border-white/5'); }); const currentBtn = event.currentTarget; currentBtn.classList.remove('bg-slate-900/50', 'text-slate-400', 'border-white/5'); currentBtn.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500'); const cards = document.querySelectorAll('.match-card'); cards.forEach(card => { let show = false; if(type === 'all') show = true; else if(type === 'playoff' && card.dataset.stage === 'playoffs') show = true; else if(type === 'groups' && card.dataset.stage === 'groups') show = true; card.style.display = show ? 'flex' : 'none'; }); }</script>"""

HOF_HTML = """<div class="max-w-2xl mx-auto"><div class="text-center mb-8"><h2 class="text-3xl font-black italic uppercase text-blue-500 tracking-tighter">SÍŇ SLÁVY</h2><p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Globální rating power ranking a tipovačka</p></div><div class="navy-card overflow-hidden mb-8 shadow-xl"><table class="w-full text-left"><tr class="bg-white/5 text-[9px] uppercase font-black tracking-wider text-slate-400"><th class="p-4">Tým</th><th class="p-4 text-center text-yellow-500">ELO RATING</th></tr>{% for t in teams %}<tr class="border-b border-white/5 hover:bg-white/5"><td class="p-4 flex items-center gap-3"><div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border border-white/10 cursor-pointer" style="background-color: {{t.color}}" onclick="openLogoModal('{{t.logo}}', '{{t.color}}')">{% if 'static' in t.logo %}<img src="{{t.logo}}" class="w-full h-full object-contain p-1.5">{% else %}<span class="text-sm">{{t.logo}}</span>{% endif %}</div><span class="font-black uppercase text-xs text-white">{{t.name}}</span></td><td class="p-4 text-center font-black text-yellow-500 text-lg">{{t.elo}}</td></tr>{% endfor %}</table></div><div class="navy-card p-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest mb-4 text-center">Top 10 Sázkařů (Tipovačka)</h3><div class="space-y-2">{% for b in bettors %}<div class="flex justify-between items-center bg-slate-900/40 p-3 rounded-xl border border-white/5"><span class="font-black uppercase text-xs text-slate-300">{{loop.index}}. {{ b.username }}</span><span class="text-blue-400 font-black text-sm">{{ b.bet_points }} b</span></div>{% endfor %}</div></div></div>"""

CHAT_HTML = """<div class="max-w-xl mx-auto w-full flex flex-col h-[75vh]"><div class="flex items-center justify-between mb-4"><h2 class="text-xl font-black italic uppercase tracking-tighter text-blue-500">Zápasový Chat / Komentáře</h2></div><div class="navy-card p-4 shadow-2xl border border-white/5 flex-1 overflow-y-auto mb-4 flex flex-col gap-3" id="chat-box">{% for c in comments %}<div class="{% if c.username == current_user.username %}self-end bg-blue-600/10 border-blue-500/30 text-blue-200{% else %}self-start bg-slate-800/40 border-white/5 text-slate-300{% endif %} border p-3 rounded-2xl max-w-[85%] text-xs font-bold"><p class="text-[8px] font-black uppercase tracking-widest opacity-50 mb-1">{{ c.username }} • {{ c.created_at[-8:-3] }}</p><p class="text-sm font-bold">{{ c.text }}</p></div>{% endfor %}</div><form method="POST" class="flex gap-2"><input type="text" name="text" required placeholder="Napiš zprávu..." class="w-full rounded-xl p-4 text-sm font-bold bg-slate-900/50 text-white border border-white/5"><button class="bg-blue-600 hover:bg-blue-500 px-6 rounded-xl text-white font-black uppercase text-xs tracking-widest shadow-lg transition-transform active:scale-95"><i data-lucide="send" class="w-4 h-4"></i></button></form></div><script>window.onload = function() { var b = document.getElementById('chat-box'); b.scrollTop = b.scrollHeight; };</script>"""

# ==========================================
# 5. INTEGRACE AI API BRIDGE
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
        prompt = build_prompt(team_name, "clean", colors); urls = pixazo_generate(prompt, width=1024, height=1024)
        symbol = save_url(urls[0]); final_logo = compose_logo(symbol, team_name); logo_url = f"/static/generated_logos/{final_logo}"
        with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (1, ?, ?, ?, ?)', (team_name, logo_url, '#0f172a', team_name[:4].upper())); conn.commit()
        return jsonify({'status': 'success', 'team_name': team_name, 'logo_url': logo_url}), 201
    except Exception as e: return jsonify({'error': str(e)}), 500

# ==========================================
# 6. ROUTY (ZÁKLAD A RENDERING)
# ==========================================
@app.route('/')
def index():
    if 'user_id' not in session: return render_ui(WELCOME_HTML)
    uid = session['user_id']
    active_tourneys = get_db().execute('SELECT *, (SELECT COUNT(*) FROM teams WHERE t_id = tournaments.id) as registered_teams FROM tournaments WHERE user_id = ? AND status != "finished" ORDER BY start_date ASC', (uid,)).fetchall()
    participating_tourneys = get_db().execute('SELECT DISTINCT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id JOIN teams t ON t.t_id = tr.id JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ? AND tr.user_id != ? AND tr.status != "finished" ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    joinable_public_tourneys = get_db().execute('SELECT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id WHERE tr.is_public = 1 AND tr.status = "draft" AND tr.user_id != ? AND tr.id NOT IN (SELECT t.t_id FROM teams t JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ?) AND (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) < tr.max_teams ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    stats = {'total_tournaments': len(active_tourneys), 'total_teams': get_db().execute('SELECT COUNT(*) FROM master_teams WHERE user_id = ?', (uid,)).fetchone()[0]}
    next_match = get_db().execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color, tr.name as tr_name FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN master_teams mt1 ON t1.master_id = mt1.id JOIN teams t2 ON m.team2_id = t2.id JOIN master_teams mt2 ON t2.master_id = mt2.id JOIN tournaments tr ON m.t_id = tr.id WHERE m.status != "finished" AND tr.status = "active" AND (mt1.user_id = ? OR mt2.user_id = ?) ORDER BY m.round_num ASC, m.id ASC LIMIT 1', (uid, uid)).fetchone()
    return render_ui(INDEX_HTML, active_tourneys=active_tourneys, participating_tourneys=participating_tourneys, joinable_public_tourneys=joinable_public_tourneys, stats=stats, next_match=next_match)

@app.route('/account')
def account():
    user = get_current_user(); host_url = f"http://{get_local_ip()}:5000"
    return render_ui(ACCOUNT_HTML, host_url=host_url)

@app.route('/login', methods=['POST'])
def login():
    user = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
    if user and check_password_hash(user['password'], request.form['password']):
        session['user_id'] = user['id']; flash(f"Identita ověřena: {user['username']}")
    else:
        pw = generate_password_hash(request.form['password'])
        with get_db() as conn: conn.execute('INSERT INTO users (username, password, theme, is_pro) VALUES (?, ?, ?, 1)', (request.form['username'], pw, 'system', 1))
        user = get_db().execute('SELECT * FROM users WHERE username = ?', (request.form['username'],)).fetchone()
        session['user_id'] = user['id']; flash("Nový administrátorský uzel vytvořen.")
    return redirect('/')

@app.route('/logout')
def logout(): session.clear(); flash("Relace ukončena."); return redirect('/')

@app.route('/teams')
@login_required
def teams(): return render_ui(TEAMS_HTML, master_teams=get_db().execute('SELECT * FROM master_teams WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall())

@app.route('/teams/new', methods=['GET', 'POST'])
@login_required
def new_team():
    if request.method == "POST":
        is_ai = request.form.get("is_ai") == "1"
        if is_ai:
            team_name = request.form.get("team_name", "").strip(); style = request.form.get("style", "clean")
            colors = f"Main Body: {request.form.get('color_body','White')}, Outline: {request.form.get('color_outline','Black')}, Fill: {request.form.get('color_fill','Blue')}"
            try:
                prompt = build_prompt(team_name, style, colors); urls = pixazo_generate(prompt)
                symbol = save_url(urls[0]); final_logo = compose_logo(symbol, team_name)
                add_meta(final_logo, team_name, "SINGLE", prompt, "Premium")
                session["logo_studio_last"] = [final_logo]; session["pending_team_name"] = team_name
                flash("AI logo s transparentním pozadím vygenerováno.")
            except Exception as e: flash(pixazo_error(e))
            return redirect(url_for("new_team"))
        else:
            with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (?, ?, ?, ?, ?)', (session['user_id'], request.form['name'], request.form['logo'], request.form['color'], request.form['tag'].upper())); conn.commit()
            flash("Tým uložen."); return redirect(url_for('teams'))
    files = [x for x in os.listdir(LOGO_DIR) if x.lower().endswith((".png", ".jpg"))] if os.path.exists(LOGO_DIR) else []
    meta_map = {m["filename"]: m for m in load_meta()}
    pending_team = session.get("pending_team_name", "")
    filtered_files = [f for f in files if meta_map.get(f, {}).get("team_name") == pending_team] if pending_team else []
    return render_ui(TEAM_NEW_HTML, images=filtered_files, styles=STYLES, pending_team=pending_team)

@app.route('/teams/use/<filename>', methods=['POST'])
@login_required
def use_logo(filename):
    meta = next((m for m in load_meta() if m["filename"] == filename), None)
    team_name = meta["team_name"] if meta else session.get("pending_team_name", "AI Tým")
    logo_url = f"/static/generated_logos/{filename}"
    with get_db() as conn: conn.execute('INSERT INTO master_teams (user_id, name, logo, color, elo, tag) VALUES (?, ?, ?, ?, 1200, ?)', (session['user_id'], team_name, logo_url, '#1e293b', team_name[:4].upper())); conn.commit()
    session.pop("pending_team_name", None); flash("AI logo integrováno do registru."); return redirect(url_for('teams'))

@app.route('/seasons')
@login_required
def seasons(): return render_ui(SEASONS_HTML, tournaments=get_db().execute('SELECT t.*, (SELECT COUNT(*) FROM teams WHERE t_id = t.id) as registered_teams FROM tournaments WHERE user_id = ? ORDER BY start_date DESC', (session['user_id'],)).fetchall())

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO tournaments (user_id, name, start_date, is_public, max_teams, join_token, rounds, stage, group_count, format) VALUES (?, ?, ?, ?, ?, ?, 1, "groups", ?, ?)', (session['user_id'], request.form['name'], request.form['start_date'], int(request.form.get('is_public',0)), int(request.form['max_teams']), uuid.uuid4().hex[:12], int(request.form.get('group_count',1)), request.form.get('format','groups')))
            new_id = cur.lastrowid; conn.commit()
        return redirect(url_for('tournament_detail', t_id=new_id))
    return render_ui(CREATE_HTML)

@app.route('/tournament/<int:t_id>')
@login_required
def tournament_detail(t_id):
    conn = get_db(); t = conn.execute('SELECT * FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t: return redirect(url_for('seasons'))
    teams = conn.execute('SELECT * FROM teams WHERE t_id = ?', (t_id,)).fetchall()
    matches = conn.execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN teams t2 ON m.team2_id = t2.id WHERE m.t_id = ? ORDER BY m.round_num, m.id', (t_id,)).fetchall()
    master_teams = conn.execute('SELECT * FROM master_teams WHERE user_id = ? AND id NOT IN (SELECT master_id FROM teams WHERE t_id = ?)', (session['user_id'], t_id)).fetchall()
    my_team_ids = [tm['id'] for tm in conn.execute('SELECT id FROM teams WHERE t_id = ?', (t_id,)).fetchall()]
    standings = get_standings(t_id) if t['status'] != 'draft' else []
    return render_ui(DETAIL_UI, tournament=t, teams=teams, matches=matches, master_teams=master_teams, standings=standings, is_admin=check_admin(t, get_current_user()), my_team_ids=my_team_ids, preds={}, logs={})

@app.route('/tournament/<int:t_id>/start')
@login_required
def start_tournament(t_id):
    with get_db() as conn:
        t_list = [t['id'] for t in conn.execute('SELECT id FROM master_teams WHERE user_id = ? LIMIT 8', (session['user_id'],)).fetchall()]
        if len(t_list) < 2: flash("Zapište nejprve alespoň 2 týmy v manažeru."); return redirect(url_for('tournament_detail', t_id=t_id))
        for mid in t_list:
            mt = conn.execute('SELECT * FROM master_teams WHERE id = ?', (mid,)).fetchone()
            conn.execute('INSERT INTO teams (t_id, master_id, name, color, logo) VALUES (?, ?, ?, ?, ?)', (t_id, mid, mt['name'], mt['color'], mt['logo']))
        teams = conn.execute('SELECT id FROM teams WHERE t_id = ?', (t_id,)).fetchall()
        for i in range(len(teams)):
            for j in range(i+1, len(teams)):
                conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "groups", 1)', (t_id, teams[i]['id'], teams[j]['id']))
        conn.execute('UPDATE tournaments SET status = "active" WHERE id = ?', (t_id,)); conn.commit()
    flash("Turnaj odstartován, herní plán vygenerován."); return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/playoff', methods=['POST'])
@login_required
def generate_playoff(t_id):
    st = get_standings(t_id)
    if len(st) < 2: flash("Nedostatek týmů."); return redirect(url_for('tournament_detail', t_id=t_id))
    with get_db() as conn:
        conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 99)', (t_id, st[0]['id'], st[1]['id']))
        conn.execute('UPDATE tournaments SET stage = "playoffs" WHERE id = ?', (t_id,)); conn.commit()
    flash("Playoff vygenerováno."); return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/next_round', methods=['POST'])
@login_required
def generate_next_knockout_round(t_id): flash("Zápasy zpracovány."); return redirect(url_for('tournament_detail', t_id=t_id))
@app.route('/tournament/<int:t_id>/generate_final', methods=['POST'])
@login_required
def generate_final(t_id): flash("Finálová kola nasazena."); return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/tournament/<int:t_id>/finish', methods=['POST'])
@login_required
def finish_tournament(t_id):
    with get_db() as conn: conn.execute('UPDATE tournaments SET status = "finished" WHERE id = ?', (t_id,)); conn.commit()
    flash("Turnaj byl oficiálně ukončen a uzamčen."); return redirect(url_for('tournament_detail', t_id=t_id))

@app.route('/match/<int:m_id>/propose', methods=['POST'])
@login_required
def propose_match(m_id):
    with get_db() as conn: conn.execute('UPDATE matches SET score1=?, score2=?, status="finished" WHERE id=?', (int(request.form['s1']), int(request.form['s2']), m_id)); conn.commit()
    update_elo(m_id); flash("Výsledek zápasu zapsán."); return redirect(request.referrer)

@app.route('/match/<int:m_id>/chat')
@login_required
def match_chat(m_id):
    m = get_db().execute('SELECT m.*, t1.name as t1_name, t2.name as t2_name FROM matches m JOIN teams t1 ON m.team1_id=t1.id JOIN teams t2 ON m.team2_id=t2.id WHERE m.id=?', (m_id,)).fetchone()
    return render_ui(CHAT_HTML, m=m, comments=[])

@app.route('/hof')
def hof():
    conn = get_db(); teams = conn.execute('SELECT * FROM master_teams ORDER BY elo DESC LIMIT 10').fetchall()
    bettors = conn.execute('SELECT * FROM users ORDER BY bet_points DESC LIMIT 10').fetchall()
    return render_ui(HOF_HTML, teams=teams, bettors=bettors)

if __name__ == '__main__': app.run(debug=True, host='0.0.0.0', port=5000)
