# >>> AI_BLOCK:IMPORTS
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify, send_file, send_from_directory, Response
from werkzeug.exceptions import HTTPException
import sqlite3, socket, os, uuid, time, random, io, csv, math, json, requests, shutil
from PIL import Image, ImageDraw, ImageFont
from functools import wraps, cmp_to_key
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
# <<< AI_BLOCK:IMPORTS

# >>> AI_BLOCK:CONFIG
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RUNTIME_DATA_DIR = os.path.abspath(os.environ.get('THE_CUP_DATA_DIR', BASE_DIR))

DB_FILENAME = 'the_cup_v31.db'
BUNDLED_DB_PATH = os.path.join(BASE_DIR, DB_FILENAME)
BUNDLED_LOGO_DIR = os.path.join(BASE_DIR, 'static', 'generated_logos')
BUNDLED_DATA_DIR = os.path.join(BASE_DIR, 'data')

if RUNTIME_DATA_DIR == BASE_DIR:
    DB_PATH = BUNDLED_DB_PATH
    LOGO_DIR = BUNDLED_LOGO_DIR
    DATA_DIR = BUNDLED_DATA_DIR
    BRAND_DIR = os.path.join(BASE_DIR, 'static', 'brand')
else:
    os.makedirs(RUNTIME_DATA_DIR, exist_ok=True)
    DB_PATH = os.path.join(RUNTIME_DATA_DIR, DB_FILENAME)
    LOGO_DIR = os.path.join(RUNTIME_DATA_DIR, 'generated_logos')
    DATA_DIR = os.path.join(RUNTIME_DATA_DIR, 'data')
    BRAND_DIR = os.path.join(RUNTIME_DATA_DIR, 'brand')

    if not os.path.exists(DB_PATH) and os.path.exists(BUNDLED_DB_PATH):
        shutil.copy2(BUNDLED_DB_PATH, DB_PATH)

for directory in (LOGO_DIR, BRAND_DIR, DATA_DIR):
    os.makedirs(directory, exist_ok=True)

if LOGO_DIR != BUNDLED_LOGO_DIR and os.path.isdir(BUNDLED_LOGO_DIR):
    for filename in os.listdir(BUNDLED_LOGO_DIR):
        source_path = os.path.join(BUNDLED_LOGO_DIR, filename)
        target_path = os.path.join(LOGO_DIR, filename)
        if os.path.isfile(source_path) and not os.path.exists(target_path):
            shutil.copy2(source_path, target_path)

META_FILE = os.path.join(DATA_DIR, 'logo_studio_images.json')
BUNDLED_META_FILE = os.path.join(BUNDLED_DATA_DIR, 'logo_studio_images.json')
if META_FILE != BUNDLED_META_FILE and not os.path.exists(META_FILE) and os.path.exists(BUNDLED_META_FILE):
    shutil.copy2(BUNDLED_META_FILE, META_FILE)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev_key_cup_esports_2026')
app.config['DB_NAME'] = DB_FILENAME
app.config['UPLOAD_FOLDER'] = LOGO_DIR

LOGO_PATH = '/static/branding_logo.svg'
WEB_GRAPHIC_PATH = '/static/web_graphic.svg'

STYLES = {
    'clean': 'clean esports logo, flat design, minimal vector',
    'neon': 'neon glowing esports logo, dark background, futuristic lines',
    'retro': 'retro pixel art esports logo, 8-bit, 16-bit championship',
    '3d': '3d rendered premium esports logo, luxury gold and silver',
    'shield': 'glowing shield typography, professional team badge'
}
# <<< AI_BLOCK:CONFIG

# >>> AI_BLOCK:DATABASE
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn
# <<< AI_BLOCK:DATABASE

# >>> AI_BLOCK:ROUTES_MEDIA
@app.route('/static/generated_logos/<path:filename>')
def generated_logo_file(filename):
    return send_from_directory(LOGO_DIR, filename)
# <<< AI_BLOCK:ROUTES_MEDIA

# >>> AI_BLOCK:SCHEMA
def init_db():
    with get_db() as conn:
        conn.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, username TEXT UNIQUE, password TEXT, theme TEXT DEFAULT "system", bet_points INTEGER DEFAULT 0, is_pro INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS tournaments (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, start_date TEXT, is_public INTEGER DEFAULT 0, max_teams INTEGER DEFAULT 8, status TEXT DEFAULT "draft", join_token TEXT UNIQUE, rounds INTEGER DEFAULT 1, stage TEXT DEFAULT "groups", referees TEXT DEFAULT "", group_count INTEGER DEFAULT 1, format TEXT DEFAULT "groups", banner TEXT DEFAULT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS master_teams (id INTEGER PRIMARY KEY, user_id INTEGER, name TEXT, color TEXT, logo TEXT, elo INTEGER DEFAULT 1200, tag TEXT, UNIQUE(user_id, name))')
        conn.execute('CREATE TABLE IF NOT EXISTS teams (id INTEGER PRIMARY KEY, t_id INTEGER, master_id INTEGER, name TEXT, color TEXT, logo TEXT, group_name TEXT DEFAULT "A")')
        conn.execute('CREATE TABLE IF NOT EXISTS matches (id INTEGER PRIMARY KEY, t_id INTEGER, team1_id INTEGER, team2_id INTEGER, score1 INTEGER, score2 INTEGER, status TEXT DEFAULT "planned", stage TEXT DEFAULT "groups", proposed_score1 INTEGER, proposed_score2 INTEGER, proposed_by_team_id INTEGER, is_ot INTEGER DEFAULT 0, match_time TEXT DEFAULT "", pitch TEXT DEFAULT "", round_num INTEGER DEFAULT 1, started_at INTEGER DEFAULT 0)')
        conn.execute('CREATE TABLE IF NOT EXISTS match_comments (id PRIMARY KEY, m_id INTEGER, username TEXT, text TEXT, created_at TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS match_logs (id INTEGER PRIMARY KEY, m_id INTEGER, username TEXT, action TEXT, created_at TEXT)')
        conn.execute('CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY, user_id INTEGER, m_id INTEGER, p_score1 INTEGER, p_score2 INTEGER, UNIQUE(user_id, m_id))')
        conn.execute('CREATE TABLE IF NOT EXISTS tournament_invitations (id INTEGER PRIMARY KEY, t_id INTEGER, user_id INTEGER, status TEXT DEFAULT "pending", UNIQUE(t_id, user_id))')
        
        for col, table, default in [('theme', 'users', '"system"'), ('bet_points', 'users', '0'), ('is_pro', 'users', '0'), ('round_num', 'matches', '1'), ('group_count', 'tournaments', '1'), ('format', 'tournaments', '"groups"'), ('group_name', 'teams', '"A"'), ('started_at', 'matches', '0'), ('elo', 'master_teams', '1200'), ('tag', 'master_teams', 'NULL'), ('banner', 'tournaments', 'NULL')]:
            try: conn.execute(f'SELECT {col} FROM {table} LIMIT 1')
            except: conn.execute(f'ALTER TABLE {table} ADD COLUMN {col} TEXT DEFAULT {default}' if 'TEXT' in default else f'ALTER TABLE {table} ADD COLUMN {col} INTEGER DEFAULT {default}')
            
        admin = conn.execute('SELECT * FROM users WHERE username = "admin"').fetchone()
        if not admin: conn.execute('INSERT INTO users (username, password, theme, is_pro) VALUES (?, ?, ?, ?)', ('admin', generate_password_hash('heslo123'), 'system', 1))
        conn.commit()

init_db()
# <<< AI_BLOCK:SCHEMA

# >>> AI_BLOCK:TEMPLATES_BASE
BASE_UI = """<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0"><link rel="manifest" href="/manifest.json"><meta id="meta-theme-color" name="theme-color" content="#020617"><link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏆</text></svg>"><script src="https://cdn.tailwindcss.com"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js"></script><script src="https://unpkg.com/lucide@latest"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script><title>THE CUP</title><style>
:root {
  color-scheme: dark;
  --app-bg: #020617;
  --app-bg-soft: #071226;
  --surface: rgba(15, 23, 42, 0.88);
  --surface-strong: #0f172a;
  --surface-raised: #17233b;
  --field-bg: #18243b;
  --line: rgba(148, 163, 184, 0.16);
  --line-strong: rgba(96, 165, 250, 0.32);
  --text: #f8fafc;
  --muted: #94a3b8;
  --primary: #3b82f6;
  --primary-strong: #2563eb;
  --primary-soft: rgba(59, 130, 246, 0.14);
  --primary-glow: rgba(59, 130, 246, 0.24);
  --shadow-card: 0 18px 50px rgba(0, 0, 0, 0.22);
  --shadow-nav: 0 12px 36px rgba(0, 0, 0, 0.28);
}
* { box-sizing: border-box; }
html {
  min-width: 320px;
  background: var(--app-bg);
  scroll-behavior: smooth;
  -webkit-tap-highlight-color: transparent;
}
body {
  margin: 0;
  overflow-x: hidden;
  color: var(--text);
  background:
    radial-gradient(circle at 50% -12rem, rgba(59, 130, 246, 0.18), transparent 28rem),
    radial-gradient(circle at 105% 38%, rgba(30, 64, 175, 0.10), transparent 30rem),
    var(--app-bg);
  font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}
button, input, select, textarea { font: inherit; }
button, a { touch-action: manipulation; }
::selection { color: #fff; background: rgba(37, 99, 235, 0.85); }
:focus-visible {
  outline: 3px solid rgba(96, 165, 250, 0.72);
  outline-offset: 3px;
}
.glass {
  background: linear-gradient(180deg, rgba(18, 29, 50, 0.94), rgba(9, 16, 31, 0.90));
  border: 1px solid var(--line);
  -webkit-backdrop-filter: blur(22px) saturate(1.2);
  backdrop-filter: blur(22px) saturate(1.2);
}
.navy-card {
  background: linear-gradient(145deg, rgba(18, 30, 52, 0.96), rgba(10, 18, 34, 0.98));
  border: 1px solid var(--line);
  border-radius: 1.5rem;
  box-shadow: var(--shadow-card);
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease, background-color 180ms ease;
}
.toast {
  color: var(--text);
  background: rgba(23, 35, 59, 0.98);
  border: 1px solid var(--line);
  border-left: 4px solid var(--primary);
  box-shadow: var(--shadow-card);
}
input, select, textarea {
  min-height: 46px;
  color: var(--text) !important;
  background: var(--field-bg) !important;
  border: 1px solid var(--line) !important;
  border-radius: 0.9rem;
  outline: none;
  transition: border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}
input::placeholder, textarea::placeholder { color: #64748b; opacity: 1; }
input:focus, select:focus, textarea:focus {
  border-color: rgba(96, 165, 250, 0.72) !important;
  box-shadow: 0 0 0 4px rgba(59, 130, 246, 0.14);
}
input:disabled, select:disabled, textarea:disabled { cursor: not-allowed; opacity: 0.62; }
.app-header {
  margin-top: 0 !important;
  padding-top: max(0.85rem, env(safe-area-inset-top));
  padding-inline: 1rem;
}
.brand-pill {
  min-width: 10.5rem;
  padding: 0.65rem 1.6rem !important;
  border-color: rgba(96, 165, 250, 0.20) !important;
  box-shadow: 0 14px 40px rgba(2, 6, 23, 0.34), 0 0 28px rgba(59, 130, 246, 0.10);
}
.brand-pill span { letter-spacing: -0.035em; }
.brand-mark {
  display: grid;
  width: 1.65rem;
  height: 1.65rem;
  place-items: center;
  overflow: hidden;
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 0.55rem;
  background: rgba(59, 130, 246, 0.09);
}
.brand-mark img { width: 100%; height: 100%; object-fit: contain; padding: 0.16rem; }
.app-main {
  position: relative;
  padding-inline: clamp(0.9rem, 2.6vw, 1.75rem) !important;
  animation: page-enter 320ms ease-out both;
}
.app-bottom-nav {
  padding: 0.45rem max(0.55rem, env(safe-area-inset-right)) max(0.45rem, env(safe-area-inset-bottom)) max(0.55rem, env(safe-area-inset-left)) !important;
}
.bottom-nav {
  background: rgba(8, 15, 29, 0.91);
  border-top: 1px solid var(--line);
  -webkit-backdrop-filter: blur(20px) saturate(1.25);
  backdrop-filter: blur(20px) saturate(1.25);
  box-shadow: 0 -14px 38px rgba(2, 6, 23, 0.26);
}
.bottom-nav-inner { min-height: 3.85rem; gap: 0.2rem; }
.nav-item {
  position: relative;
  justify-content: center;
  min-width: 3.25rem;
  min-height: 3.1rem;
  padding: 0.35rem 0.5rem;
  border-radius: 1rem;
  transition: color 160ms ease, opacity 160ms ease, background-color 160ms ease, transform 160ms ease;
}
.nav-item svg { width: 1.35rem; height: 1.35rem; stroke-width: 2.2; }
.nav-item span { font-size: 0.55rem !important; letter-spacing: 0.055em; }
.nav-item.opacity-100 {
  color: #60a5fa !important;
  background: var(--primary-soft);
  opacity: 1 !important;
}
.nav-item:active { transform: scale(0.94); }
.nav-create {
  width: 3.55rem !important;
  height: 3.55rem !important;
  margin-top: -1.5rem !important;
  border-color: var(--app-bg) !important;
  border-radius: 1.15rem !important;
  background: linear-gradient(145deg, #3b82f6, #2563eb) !important;
  box-shadow: 0 12px 26px rgba(37, 99, 235, 0.42);
  transition: transform 160ms ease, box-shadow 160ms ease;
}
.nav-create:active { transform: scale(0.92); }
.welcome-card {
  width: 100%;
  max-width: 72rem;
  min-height: clamp(31rem, 64vh, 42rem) !important;
  margin-inline: auto;
  isolation: isolate;
  border-radius: clamp(1.5rem, 3vw, 2.25rem) !important;
}
.welcome-card::after {
  position: absolute;
  z-index: 1;
  inset: 0;
  pointer-events: none;
  content: "";
  border-radius: inherit;
  background: linear-gradient(145deg, rgba(96, 165, 250, 0.08), transparent 35%, rgba(37, 99, 235, 0.04));
}
.welcome-inner { max-width: 48rem; }
.primary-action {
  min-height: 48px;
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.30);
}
.hero-card {
  width: min(100%, 40rem) !important;
  isolation: isolate;
  border-color: rgba(96, 165, 250, 0.16) !important;
}
.hero-media { overflow: hidden; }
.hero-media img {
  transform: scale(1.015);
  filter: saturate(1.08) contrast(1.04);
}
.hero-copy {
  background: linear-gradient(180deg, rgba(15, 23, 42, 0.12), rgba(15, 23, 42, 0.92) 42%);
}
.stats-grid { align-items: stretch; }
.stat-card {
  position: relative;
  min-height: 6.6rem;
  overflow: hidden;
}
.stat-card::after {
  position: absolute;
  top: -2.5rem;
  right: -2.5rem;
  width: 7rem;
  height: 7rem;
  pointer-events: none;
  content: "";
  border-radius: 999px;
  background: radial-gradient(circle, rgba(59, 130, 246, 0.12), transparent 68%);
}
.tournament-card { overflow: hidden; }
.tournament-media { position: relative; background: #07101f; }
.tournament-media::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
  background: linear-gradient(180deg, transparent 48%, rgba(2, 6, 23, 0.35));
}
.tournament-media img { transition: transform 320ms ease, filter 320ms ease; }
.table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; scrollbar-width: thin; }
.live-timer { animation: pulse 1.1s ease-in-out infinite; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.55; } }
@keyframes page-enter { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: none; } }
body.light {
  color-scheme: light;
  --app-bg: #f4f7fb;
  --app-bg-soft: #eaf0f8;
  --surface: rgba(255, 255, 255, 0.90);
  --surface-strong: #ffffff;
  --surface-raised: #f8fafc;
  --field-bg: #f8fafc;
  --line: rgba(15, 23, 42, 0.10);
  --line-strong: rgba(37, 99, 235, 0.26);
  --text: #0f172a;
  --muted: #64748b;
  --primary-soft: rgba(37, 99, 235, 0.10);
  --shadow-card: 0 16px 46px rgba(30, 64, 175, 0.09);
  --shadow-nav: 0 12px 36px rgba(15, 23, 42, 0.12);
  background:
    radial-gradient(circle at 50% -12rem, rgba(59, 130, 246, 0.15), transparent 28rem),
    radial-gradient(circle at 105% 38%, rgba(147, 197, 253, 0.13), transparent 30rem),
    var(--app-bg);
}
body.light .glass {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.91));
  border-color: var(--line);
}
body.light .navy-card {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.98));
  border-color: var(--line);
}
body.light .bottom-nav {
  background: rgba(255, 255, 255, 0.91);
  border-color: var(--line);
  box-shadow: 0 -14px 38px rgba(15, 23, 42, 0.08);
}
body.light input, body.light select, body.light textarea { color: var(--text) !important; }
body.light .theme-text-main { color: var(--text) !important; }
body.light .bg-slate-800.theme-text-main,
body.light .bg-slate-900.theme-text-main {
  color: var(--text) !important;
  background-color: #eef3fa !important;
}
body.light .toast { color: var(--text); background: rgba(255, 255, 255, 0.98); }

/* Esports mobile design */
.esports-dashboard,
.tournament-catalog {
  width: min(100%, 74rem);
  margin-inline: auto;
}
.dashboard-intro,
.catalog-header,
.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.dashboard-intro {
  padding: 0.25rem 0.15rem 0;
}
.screen-eyebrow,
.section-kicker,
.featured-kicker,
.event-status,
.event-visibility {
  font-weight: 900;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}
.screen-eyebrow {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  margin-bottom: 0.35rem;
  color: #60a5fa;
  font-size: 0.66rem;
}
.screen-title {
  max-width: 18ch;
  color: var(--text);
  font-size: clamp(1.85rem, 7vw, 3.4rem);
  font-weight: 950;
  font-style: italic;
  line-height: 0.98;
  letter-spacing: -0.055em;
  text-transform: uppercase;
  text-wrap: balance;
}
.screen-title span {
  color: #60a5fa;
}
.screen-subtitle {
  max-width: 36rem;
  margin-top: 0.65rem;
  color: var(--muted);
  font-size: clamp(0.72rem, 2vw, 0.9rem);
  font-weight: 650;
}
.profile-chip {
  display: grid;
  width: 3.1rem;
  height: 3.1rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(96, 165, 250, 0.28);
  border-radius: 1.05rem;
  color: #fff;
  background: linear-gradient(145deg, #4f46e5, #2563eb);
  box-shadow: 0 12px 30px rgba(37, 99, 235, 0.27);
  font-size: 1rem;
  font-weight: 950;
}
.featured-panel {
  position: relative;
  min-height: clamp(19rem, 52vw, 28rem);
  isolation: isolate;
  overflow: hidden;
  border: 1px solid rgba(129, 140, 248, 0.24);
  border-radius: clamp(1.6rem, 4vw, 2.35rem);
  background: #081025;
  box-shadow: 0 26px 74px rgba(0, 0, 0, 0.34);
}
.featured-media,
.featured-scrim {
  position: absolute;
  inset: 0;
}
.featured-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(1.16) contrast(1.06);
  transform: scale(1.02);
}
.featured-scrim {
  background:
    linear-gradient(90deg, rgba(3, 7, 18, 0.96) 0%, rgba(3, 7, 18, 0.74) 48%, rgba(3, 7, 18, 0.24) 100%),
    linear-gradient(0deg, rgba(3, 7, 18, 0.94), transparent 62%);
}
.featured-panel::after {
  position: absolute;
  z-index: 1;
  top: -7rem;
  right: -5rem;
  width: 19rem;
  height: 19rem;
  pointer-events: none;
  content: "";
  border-radius: 999px;
  background: radial-gradient(circle, rgba(124, 58, 237, 0.34), transparent 68%);
}
.featured-copy {
  position: relative;
  z-index: 2;
  display: flex;
  width: min(100%, 38rem);
  min-height: inherit;
  flex-direction: column;
  align-items: flex-start;
  justify-content: flex-end;
  padding: clamp(1.35rem, 5vw, 3rem);
}
.featured-kicker {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.45rem 0.7rem;
  border: 1px solid rgba(167, 139, 250, 0.32);
  border-radius: 999px;
  color: #c4b5fd;
  background: rgba(76, 29, 149, 0.28);
  font-size: 0.58rem;
}
.featured-title {
  max-width: 12ch;
  margin-top: 0.85rem;
  color: #fff;
  font-size: clamp(2rem, 8vw, 4.25rem);
  font-weight: 950;
  font-style: italic;
  line-height: 0.92;
  letter-spacing: -0.065em;
  text-transform: uppercase;
  text-wrap: balance;
}
.featured-description {
  max-width: 32rem;
  margin-top: 0.85rem;
  color: #b8c3d7;
  font-size: clamp(0.72rem, 2vw, 0.9rem);
  font-weight: 650;
}
.featured-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.65rem;
  margin-top: 1.2rem;
}
.featured-action,
.catalog-create,
.event-manage {
  display: inline-flex;
  min-height: 2.85rem;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
  border-radius: 0.95rem;
  font-size: 0.65rem;
  font-weight: 900;
  letter-spacing: 0.075em;
  text-transform: uppercase;
  transition: transform 160ms ease, border-color 160ms ease, background-color 160ms ease;
}
.featured-action--primary,
.catalog-create {
  padding-inline: 1rem;
  color: #fff;
  background: linear-gradient(145deg, #4f46e5, #2563eb);
  box-shadow: 0 12px 28px rgba(37, 99, 235, 0.32);
}
.featured-action--secondary {
  padding-inline: 1rem;
  border: 1px solid rgba(255, 255, 255, 0.14);
  color: #e2e8f0;
  background: rgba(15, 23, 42, 0.74);
  -webkit-backdrop-filter: blur(12px);
  backdrop-filter: blur(12px);
}
.dashboard-stats {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.75rem;
}
.metric-card {
  position: relative;
  display: flex;
  min-height: 7rem;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  overflow: hidden;
  padding: 1rem;
  border: 1px solid var(--line);
  border-radius: 1.35rem;
  color: var(--text);
  background: linear-gradient(145deg, rgba(18, 30, 52, 0.98), rgba(8, 14, 29, 0.98));
  box-shadow: var(--shadow-card);
}
.metric-card::after {
  position: absolute;
  top: -2.6rem;
  right: -2.4rem;
  width: 8rem;
  height: 8rem;
  pointer-events: none;
  content: "";
  border-radius: 999px;
  background: radial-gradient(circle, rgba(99, 102, 241, 0.2), transparent 70%);
}
.metric-copy {
  position: relative;
  z-index: 1;
}
.metric-label {
  display: block;
  color: var(--muted);
  font-size: 0.58rem;
  font-weight: 900;
  letter-spacing: 0.105em;
  text-transform: uppercase;
}
.metric-value {
  display: block;
  margin-top: 0.25rem;
  font-size: clamp(1.8rem, 6vw, 2.6rem);
  font-weight: 950;
  font-style: italic;
  line-height: 1;
}
.metric-icon {
  position: relative;
  z-index: 1;
  display: grid;
  width: 2.65rem;
  height: 2.65rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 0.9rem;
  color: #60a5fa;
  background: rgba(59, 130, 246, 0.1);
}
.section-heading {
  margin-bottom: 0.85rem;
  padding-inline: 0.1rem;
}
.section-kicker {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  color: #60a5fa;
  font-size: 0.58rem;
}
.section-title {
  margin-top: 0.2rem;
  color: var(--text);
  font-size: clamp(1.15rem, 4vw, 1.55rem);
  font-weight: 950;
  font-style: italic;
  line-height: 1;
  letter-spacing: -0.035em;
  text-transform: uppercase;
}
.section-link {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex: 0 0 auto;
  color: #94a3b8;
  font-size: 0.62rem;
  font-weight: 850;
  text-transform: uppercase;
}
.event-grid {
  display: grid;
  grid-template-columns: repeat(1, minmax(0, 1fr));
  gap: 0.85rem;
}
.event-card {
  position: relative;
  display: flex;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid var(--line);
  border-radius: 1.45rem;
  color: var(--text);
  background: linear-gradient(145deg, rgba(18, 30, 52, 0.98), rgba(8, 14, 29, 0.98));
  box-shadow: var(--shadow-card);
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}
.event-card-media {
  position: relative;
  height: 9.5rem;
  overflow: hidden;
  background: #060b16;
}
.event-card-media::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
  background: linear-gradient(180deg, rgba(2, 6, 23, 0.04), rgba(2, 6, 23, 0.56));
}
.event-card-media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  filter: saturate(1.08) contrast(1.04);
  transition: transform 300ms ease, filter 300ms ease;
}
.event-badges {
  position: absolute;
  z-index: 2;
  top: 0.75rem;
  left: 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}
.event-status,
.event-visibility {
  display: inline-flex;
  min-height: 1.55rem;
  align-items: center;
  gap: 0.3rem;
  padding-inline: 0.55rem;
  border-radius: 999px;
  font-size: 0.5rem;
  -webkit-backdrop-filter: blur(10px);
  backdrop-filter: blur(10px);
}
.event-status {
  border: 1px solid rgba(96, 165, 250, 0.32);
  color: #bfdbfe;
  background: rgba(30, 64, 175, 0.62);
}
.event-status--live {
  border-color: rgba(251, 146, 60, 0.4);
  color: #fed7aa;
  background: rgba(154, 52, 18, 0.66);
}
.event-status--open {
  border-color: rgba(74, 222, 128, 0.38);
  color: #bbf7d0;
  background: rgba(20, 83, 45, 0.68);
}
.event-visibility {
  border: 1px solid rgba(255, 255, 255, 0.13);
  color: #e2e8f0;
  background: rgba(2, 6, 23, 0.65);
}
.event-card-body {
  display: flex;
  min-width: 0;
  flex: 1;
  flex-direction: column;
  padding: 1rem;
}
.event-card-title {
  overflow: hidden;
  color: var(--text);
  font-size: 1rem;
  font-weight: 950;
  line-height: 1.15;
  letter-spacing: -0.025em;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}
.event-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 0.55rem 0.8rem;
  margin-top: 0.65rem;
  color: var(--muted);
  font-size: 0.63rem;
  font-weight: 750;
}
.event-meta span {
  display: inline-flex;
  align-items: center;
  gap: 0.32rem;
}
.event-card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-top: 0.9rem;
  padding-top: 0.85rem;
  border-top: 1px solid var(--line);
}
.event-card-hint {
  color: #60a5fa;
  font-size: 0.58rem;
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.event-card-arrow {
  display: grid;
  width: 2rem;
  height: 2rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.7rem;
  color: #93c5fd;
  background: rgba(59, 130, 246, 0.12);
}
.notification-card,
.next-match-card,
.catalog-summary,
.catalog-empty {
  border: 1px solid var(--line);
  border-radius: 1.35rem;
  background: linear-gradient(145deg, rgba(18, 30, 52, 0.98), rgba(8, 14, 29, 0.98));
  box-shadow: var(--shadow-card);
}
.notification-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.8rem;
  padding: 1rem;
}
.notification-icon {
  display: grid;
  width: 2.7rem;
  height: 2.7rem;
  flex: 0 0 auto;
  place-items: center;
  border: 1px solid rgba(250, 204, 21, 0.25);
  border-radius: 0.9rem;
  color: #facc15;
  background: rgba(234, 179, 8, 0.1);
}
.notification-actions {
  display: flex;
  flex: 0 0 auto;
  gap: 0.4rem;
}
.notification-action {
  display: inline-flex;
  min-height: 2.3rem;
  align-items: center;
  justify-content: center;
  padding-inline: 0.72rem;
  border-radius: 0.75rem;
  font-size: 0.55rem;
  font-weight: 900;
  letter-spacing: 0.07em;
  text-transform: uppercase;
}
.notification-action--accept { color: #052e16; background: #4ade80; }
.notification-action--decline { color: #fca5a5; background: rgba(127, 29, 29, 0.24); }
.next-match-card {
  position: relative;
  overflow: hidden;
  padding: clamp(1rem, 3vw, 1.4rem);
  border-color: rgba(251, 146, 60, 0.22);
}
.next-match-card::after {
  position: absolute;
  top: -6rem;
  right: -4rem;
  width: 15rem;
  height: 15rem;
  pointer-events: none;
  content: "";
  border-radius: 999px;
  background: radial-gradient(circle, rgba(249, 115, 22, 0.16), transparent 70%);
}
.matchup {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
  align-items: center;
  gap: 0.75rem;
  margin-top: 1rem;
}
.match-team {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 0.6rem;
}
.match-team--away {
  flex-direction: row-reverse;
  text-align: right;
}
.team-mark {
  display: grid;
  width: 2.8rem;
  height: 2.8rem;
  flex: 0 0 auto;
  place-items: center;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.13);
  border-radius: 0.9rem;
  box-shadow: 0 8px 20px rgba(2, 6, 23, 0.24);
}
.team-mark img {
  width: 100%;
  height: 100%;
  object-fit: contain;
  padding: 0.25rem;
}
.match-team-name {
  overflow: hidden;
  color: var(--text);
  font-size: 0.7rem;
  font-weight: 950;
  text-overflow: ellipsis;
  text-transform: uppercase;
  white-space: nowrap;
}
.match-versus {
  display: grid;
  width: 2.2rem;
  height: 2.2rem;
  place-items: center;
  border: 1px solid rgba(251, 146, 60, 0.25);
  border-radius: 999px;
  color: #fb923c;
  background: rgba(124, 45, 18, 0.2);
  font-size: 0.58rem;
  font-weight: 950;
}
.match-details {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 0.55rem;
  margin-top: 1rem;
  padding-top: 0.8rem;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 0.6rem;
  font-weight: 800;
}
.catalog-header {
  align-items: flex-end;
}
.catalog-create {
  flex: 0 0 auto;
}
.catalog-summary {
  display: flex;
  align-items: center;
  gap: 0.85rem;
  padding: 0.95rem 1rem;
}
.catalog-summary-icon {
  display: grid;
  width: 2.5rem;
  height: 2.5rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 0.85rem;
  color: #c4b5fd;
  background: rgba(124, 58, 237, 0.14);
}
.capacity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  color: var(--muted);
  font-size: 0.58rem;
  font-weight: 850;
}
.capacity-track {
  height: 0.3rem;
  margin-top: 0.45rem;
  overflow: hidden;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.12);
}
.capacity-fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #6366f1, #3b82f6);
}
.event-card-actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 0.55rem;
  margin-top: 0.95rem;
}
.event-manage {
  color: #fff;
  background: linear-gradient(145deg, #4f46e5, #2563eb);
}
.event-delete {
  display: grid;
  width: 2.85rem;
  min-height: 2.85rem;
  place-items: center;
  border: 1px solid rgba(248, 113, 113, 0.18);
  border-radius: 0.95rem;
  color: #f87171;
  background: rgba(127, 29, 29, 0.14);
}
.catalog-empty {
  display: grid;
  min-height: 18rem;
  place-items: center;
  padding: 2rem;
  text-align: center;
}
body.light .metric-card,
body.light .event-card,
body.light .notification-card,
body.light .next-match-card,
body.light .catalog-summary,
body.light .catalog-empty {
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.99), rgba(245, 248, 253, 0.99));
}
body.light .featured-action--secondary {
  border-color: rgba(255, 255, 255, 0.22);
  color: #f8fafc;
  background: rgba(15, 23, 42, 0.68);
}
@media (hover: hover) and (pointer: fine) {
  .featured-action:hover,
  .catalog-create:hover,
  .event-manage:hover { transform: translateY(-2px); }
  .profile-chip:hover,
  .metric-card:hover,
  .event-card:hover {
    transform: translateY(-3px);
    border-color: rgba(96, 165, 250, 0.34);
  }
  .event-card:hover .event-card-media img {
    transform: scale(1.045);
    filter: saturate(1.15) contrast(1.06);
  }
}
@media (min-width: 680px) {
  .event-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .dashboard-stats { gap: 1rem; }
  .metric-card { padding: 1.25rem; }
}
@media (min-width: 1040px) {
  .event-grid--catalog { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 520px) {
  .dashboard-intro { align-items: flex-start; }
  .screen-title { max-width: 13ch; }
  .featured-panel { min-height: 22rem; }
  .featured-scrim {
    background:
      linear-gradient(0deg, rgba(3, 7, 18, 0.98) 0%, rgba(3, 7, 18, 0.7) 62%, rgba(3, 7, 18, 0.28) 100%),
      linear-gradient(90deg, rgba(3, 7, 18, 0.62), transparent);
  }
  .featured-copy { justify-content: flex-end; }
  .featured-title { max-width: 10ch; }
  .featured-actions { width: 100%; }
  .featured-action { flex: 1; }
  .notification-card { align-items: flex-start; flex-wrap: wrap; }
  .notification-actions { width: 100%; }
  .notification-action { flex: 1; }
  .catalog-header { align-items: flex-start; }
  .catalog-create {
    width: 2.85rem;
    padding-inline: 0;
  }
  .catalog-create span { display: none; }
}

/* Tournament detail */
.tournament-detail-shell {
  width: 100%;
  max-width: 80rem;
  margin-inline: auto;
}
.tournament-overview {
  gap: 1rem !important;
  margin-bottom: 1rem !important;
}
.tournament-hero {
  width: min(100%, 46rem) !important;
  border-color: rgba(96, 165, 250, 0.20) !important;
  border-radius: 1.75rem !important;
}
.tournament-hero-media {
  height: clamp(10.5rem, 32vw, 15rem) !important;
}
.tournament-hero-content {
  padding: 1.25rem clamp(1rem, 4vw, 2rem) !important;
}
.tournament-hero-content--plain {
  display: grid;
  min-height: 11rem;
  place-items: center;
  isolation: isolate;
  overflow: hidden;
}
.tournament-hero-content--plain::after {
  position: absolute;
  z-index: 0;
  inset: 0;
  pointer-events: none;
  content: "";
  background: radial-gradient(circle at 50% 25%, rgba(59, 130, 246, 0.12), transparent 42%), linear-gradient(180deg, rgba(2, 6, 23, 0.02), rgba(2, 6, 23, 0.18));
}
.tournament-hero-backdrop {
  opacity: 0.055 !important;
  filter: saturate(0.72) contrast(0.9);
  transform: scale(1.04);
}
.tournament-hero-body {
  width: 100%;
}
.tournament-hero-icon {
  filter: drop-shadow(0 0 16px rgba(59, 130, 246, 0.32));
}
.tournament-hero-title {
  font-size: clamp(1.85rem, 5vw, 2.55rem);
  text-wrap: balance;
}
.tournament-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 0.45rem;
  color: var(--muted);
  font-size: 0.625rem;
}
.tournament-meta-item,
.tournament-status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 1.75rem;
  gap: 0.35rem;
  padding: 0.28rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.56);
  line-height: 1;
}
.tournament-status {
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.055em;
}
.tournament-status-active { color: #4ade80; border-color: rgba(74, 222, 128, 0.28); background: rgba(22, 101, 52, 0.16); }
.tournament-status-draft { color: #60a5fa; border-color: rgba(96, 165, 250, 0.28); background: rgba(37, 99, 235, 0.14); }
.tournament-status-finished { color: #fbbf24; border-color: rgba(251, 191, 36, 0.28); background: rgba(161, 98, 7, 0.14); }
.tournament-actions {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  width: min(100%, 32rem);
  gap: 0.55rem;
}
.tournament-action {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 0;
  min-height: 3rem;
  gap: 0.45rem;
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--line);
  border-radius: 1rem;
  background: rgba(23, 35, 59, 0.78);
  font-size: 0.625rem;
  font-weight: 900;
  text-transform: uppercase;
  letter-spacing: 0.025em;
  box-shadow: 0 10px 26px rgba(2, 6, 23, 0.18);
  transition: transform 160ms ease, background-color 160ms ease, border-color 160ms ease;
}
.tournament-action--tv { color: #60a5fa; border-color: rgba(96, 165, 250, 0.26); }
.tournament-action--excel { color: #facc15; border-color: rgba(250, 204, 21, 0.24); }
.tournament-action--share { color: #4ade80; border-color: rgba(74, 222, 128, 0.24); }
.tournament-action:active { transform: scale(0.96); }
.match-filter-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  width: fit-content;
  max-width: 100%;
  gap: 0.4rem;
  margin: 0 auto 1rem;
  padding: 0.42rem;
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 1.25rem;
  background: rgba(8, 15, 29, 0.72);
  box-shadow: 0 12px 30px rgba(2, 6, 23, 0.16);
  scrollbar-width: none;
}
.match-filter-bar::-webkit-scrollbar { display: none; }
.match-filter {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  min-height: 2.75rem;
  gap: 0.4rem;
  padding: 0.65rem 0.9rem;
  border-radius: 0.9rem;
  font-size: 0.625rem;
  font-weight: 900;
  text-transform: uppercase;
  white-space: nowrap;
  transition: transform 160ms ease, background-color 160ms ease, border-color 160ms ease;
}
.match-filter--mine { margin-left: 0.3rem; }
.match-filter:active { transform: scale(0.96); }
.tournament-content {
  gap: clamp(1rem, 2.5vw, 2rem) !important;
}
.standings-card {
  border-radius: 1.5rem !important;
}
.standings-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
}
.standings-head { background: rgba(30, 41, 59, 0.72); }
.standings-row:last-child { border-bottom: 0; }
.standings-team-cell { min-width: 11rem; }
.standings-logo {
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.05), 0 8px 18px rgba(2, 6, 23, 0.18);
}
.standings-name { min-width: 0; }
.standings-cell { color: var(--muted); }
.standings-score { letter-spacing: 0.02em; }
.standings-points {
  color: #60a5fa !important;
  background: rgba(59, 130, 246, 0.055);
}
body.light .tournament-meta-item {
  background: rgba(255, 255, 255, 0.76);
}
body.light .tournament-action {
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 10px 26px rgba(30, 64, 175, 0.08);
}
body.light .match-filter-bar {
  background: rgba(255, 255, 255, 0.82);
}
body.light .standings-head {
  background: rgba(226, 232, 240, 0.72);
}
body.light .standings-points {
  color: #2563eb !important;
  background: rgba(37, 99, 235, 0.055);
}
@media (hover: hover) and (pointer: fine) {
  .tournament-action:hover {
    transform: translateY(-2px);
    background: rgba(30, 47, 77, 0.92);
  }
  body.light .tournament-action:hover { background: #fff; }
  .match-filter:hover { border-color: var(--line-strong); }
}
@media (max-width: 640px) {
  .tournament-overview { margin-bottom: 0.8rem !important; }
  .tournament-hero { border-radius: 1.45rem !important; }
  .tournament-hero-content--plain { min-height: 9.5rem; }
  .tournament-hero-content { padding: 1.1rem 0.9rem !important; }
  .tournament-hero-title { font-size: clamp(1.65rem, 8vw, 2.1rem); }
  .tournament-meta { gap: 0.35rem; }
  .tournament-meta-item, .tournament-status { padding-inline: 0.52rem; }
  .tournament-actions { width: 100%; gap: 0.42rem; }
  .tournament-action {
    min-height: 3.1rem;
    gap: 0.32rem;
    padding-inline: 0.35rem;
    font-size: 0.56rem;
  }
  .match-filter-bar {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    width: 100%;
    overflow: visible;
  }
  .match-filter { width: 100%; padding-inline: 0.45rem; }
  .match-filter--mine {
    grid-column: 1 / -1;
    margin-left: 0;
  }
  .standings-card { border-radius: 1.35rem !important; }
  .standings-table { table-layout: fixed; }
  .standings-team-heading, .standings-team-cell { width: 50%; }
  .standings-played-heading, .standings-cell { width: 12%; }
  .standings-score-heading, .standings-score { width: 23%; }
  .standings-points-heading, .standings-points { width: 15%; }
  .standings-team-cell { min-width: 0; padding: 0.75rem 0.8rem !important; }
  .standings-cell, .standings-score, .standings-points { padding: 0.75rem 0.25rem !important; }
  .standings-logo { width: 2.35rem !important; height: 2.35rem !important; }
  .standings-name { max-width: 7.5rem; font-size: 0.68rem !important; }
  .standings-optional { display: none !important; }
}

@media (hover: hover) and (pointer: fine) {
  a.navy-card:hover, .navy-card.group:hover {
    transform: translateY(-2px);
    border-color: var(--line-strong);
    box-shadow: 0 22px 56px rgba(2, 6, 23, 0.28);
  }
  .nav-item:hover { color: #60a5fa; background: var(--primary-soft); opacity: 1; }
  .nav-create:hover { transform: translateY(-2px); box-shadow: 0 16px 34px rgba(37, 99, 235, 0.48); }
  .tournament-card:hover .tournament-media img { transform: scale(1.045); filter: saturate(1.14) contrast(1.05); }
}
@media (max-width: 640px) {
  .app-main { margin-top: 0 !important; }
  .brand-pill { min-width: 9.75rem; }
  .nav-item { min-width: 2.85rem; padding-inline: 0.35rem; }
  .welcome-card { min-height: min(68vh, 36rem) !important; }
  .hero-card { border-radius: 1.4rem !important; }
  .stat-card { min-height: 6.25rem; }
}
@media (max-width: 370px) {
  .nav-item { min-width: 2.55rem; padding-inline: 0.2rem; }
  .nav-item span { font-size: 0.5rem !important; }
}
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after {
    scroll-behavior: auto !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}</style></head><body class="app-body min-h-screen {% if not hide_nav %}pb-28 has-app-nav{% endif %} flex flex-col"><div id="offline-banner" class="hidden fixed top-0 left-0 right-0 bg-red-600 text-white text-[9px] font-black uppercase tracking-widest text-center py-1.5 z-[9999] shadow-lg">Jste v offline režimu - prohlížíte uložená data</div><script>if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js');});}window.addEventListener('online',()=>document.getElementById('offline-banner').classList.add('hidden'));window.addEventListener('offline',()=>document.getElementById('offline-banner').classList.remove('hidden'));if(!navigator.onLine)document.getElementById('offline-banner').classList.remove('hidden');const userTheme='{{current_user.theme if current_user else "system"}}';const themeQuery=window.matchMedia('(prefers-color-scheme: dark)');function applyTheme(){const isLight=userTheme==='light'||(userTheme==='system'&&!themeQuery.matches);document.body.classList.toggle('light',isLight);const themeMeta=document.getElementById('meta-theme-color');if(themeMeta)themeMeta.content=isLight?'#f4f7fb':'#020617';}applyTheme();if(userTheme==='system'){if(themeQuery.addEventListener)themeQuery.addEventListener('change',applyTheme);else themeQuery.addListener(applyTheme);}function vibrate(){if(navigator.vibrate)navigator.vibrate(50);}let lastNotifCount=0;</script><div id="custom-modal" class="fixed inset-0 z-[2000] flex items-center justify-center hidden opacity-0 transition-opacity duration-300"><div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="closeModal()"></div><div class="navy-card relative w-11/12 max-w-sm p-6 transform scale-95 transition-transform duration-300 shadow-2xl" id="custom-modal-content"><div class="w-16 h-16 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center mx-auto mb-4 border border-blue-500/20"><i data-lucide="help-circle" class="w-8 h-8"></i></div><h3 class="text-xl font-black italic uppercase text-center mb-2 theme-text-main">Potvrzení</h3><p id="modal-message" class="text-xs text-slate-400 text-center mb-8"></p><div class="flex gap-3"><button onclick="closeModal()" type="button" class="flex-1 bg-slate-800 hover:bg-slate-700 py-4 rounded-xl font-black uppercase text-[10px] theme-text-main transition-colors">Zrušit</button><button onclick="confirmModalAction()" type="button" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-xl font-black uppercase text-[10px] shadow-lg transition-colors">Potvrdit</button></div></div></div><div id="logo-modal" class="fixed inset-0 z-[4000] bg-slate-950/90 backdrop-blur-md hidden flex items-center justify-center p-4 opacity-0 transition-opacity" onclick="closeLogoModal()"><div class="relative w-full max-w-sm sm:max-w-md flex flex-col items-center justify-center" onclick="event.stopPropagation()"><button type="button" onclick="closeLogoModal()" class="absolute -top-12 right-0 sm:-right-8 text-slate-400 hover:text-white"><i data-lucide="x" class="w-8 h-8"></i></button><div id="logo-modal-content" class="w-64 h-64 sm:w-80 sm:h-80 rounded-full flex items-center justify-center shadow-2xl border-4 border-white/10 overflow-hidden" style="background-color: #0f172a;"></div></div></div><div id="toast-container" class="fixed top-24 right-4 left-4 md:left-auto md:w-80 z-[1000] space-y-2 pointer-events-none">{% with messages=get_flashed_messages() %}{% if messages %}{% for message in messages %}<div class="toast flex items-center justify-between p-4 rounded-xl shadow-2xl"><div class="flex items-center gap-3"><i data-lucide="bell" class="w-4 h-4 text-blue-500 shrink-0"></i><span class="text-xs font-bold">{{ message }}</span></div><button onclick="this.parentElement.remove()" class="text-slate-500 font-bold p-2 shrink-0">&times;</button></div>{% endfor %}{% endif %}{% endwith %}</div>{% if not hide_nav %}<div class="app-header fixed top-0 left-0 right-0 z-50 flex justify-center pointer-events-none mt-4"><a href="/" id="main-nav-tab" class="brand-pill glass px-10 py-2.5 rounded-[2rem] border border-white/10 shadow-2xl pointer-events-auto flex items-center justify-center gap-2.5" aria-label="THE CUP – domů"><span class="brand-mark"><img src="{{ logo }}" alt="" aria-hidden="true"></span><span class="uppercase tracking-tighter font-black italic text-blue-500 text-xl drop-shadow-md">THE CUP</span></a></div>{% endif %}<main class="app-main w-full max-w-[1400px] mx-auto px-3 {% if not hide_nav %}app-main-with-nav pt-24{% endif %} mt-2 flex-1 flex flex-col" id="main-content">CONTENT_PLACEHOLDER</main>{% if not hide_nav %}<div class="app-bottom-nav fixed bottom-0 left-0 right-0 bottom-nav z-50 p-2"><div class="bottom-nav-inner flex justify-between items-center max-w-lg mx-auto"><a href="/" onclick="vibrate()" class="nav-item flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='home' }}"><i data-lucide="home"></i><span class="text-[8px] font-bold uppercase">Domů</span></a>{% if current_user %}<a href="/teams" onclick="vibrate()" class="nav-item flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='teams' }}"><i data-lucide="users"></i><span class="text-[8px] font-bold uppercase">Týmy</span></a><a href="/create" onclick="vibrate()" class="nav-create bg-blue-600 w-10 h-10 flex items-center justify-center rounded-2xl shadow-xl -mt-6 border-4 border-slate-950 active:scale-90" aria-label="Vytvořit turnaj"><i data-lucide="plus" class="text-white"></i></a><a href="/seasons" onclick="vibrate()" class="nav-item flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='seasons' }}"><i data-lucide="trophy"></i><span class="text-[8px] font-bold uppercase">Turnaje</span></a>{% endif %}<a href="/hof" onclick="vibrate()" class="nav-item flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='hof' }}"><i data-lucide="star"></i><span class="text-[8px] font-bold uppercase">Sláva</span></a><a href="/account" onclick="vibrate()" class="nav-item flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='account' }}"><i data-lucide="user"></i><span class="text-[8px] font-bold uppercase">Účet</span></a></div></div>{% endif %}<script>lucide.createIcons();let pendingForm=null;function openLogoModal(content,bgColor){const modal=document.getElementById('logo-modal');const container=document.getElementById('logo-modal-content');container.style.backgroundColor=bgColor;if(content.includes('static/')){container.innerHTML='<img src="'+content+'" class="w-full h-full object-contain p-6">';}else{container.innerHTML='<span class="drop-shadow-xl text-7xl sm:text-9xl">'+content+'</span>';}modal.classList.remove('hidden');void modal.offsetWidth;modal.classList.remove('opacity-0');}function closeLogoModal(){const modal=document.getElementById('logo-modal');modal.classList.add('opacity-0');setTimeout(()=>modal.classList.add('hidden'),300);}function openModal(message,form){document.getElementById('modal-message').innerText=message;pendingForm=form;const modal=document.getElementById('custom-modal');modal.classList.remove('hidden');void modal.offsetWidth;modal.classList.remove('opacity-0');vibrate();}function closeModal(){const modal=document.getElementById('custom-modal');modal.classList.add('opacity-0');setTimeout(()=>{modal.classList.add('hidden');pendingForm=null;},300);}function confirmModalAction(){if(pendingForm)pendingForm.submit();closeModal();vibrate();}document.addEventListener('DOMContentLoaded',()=>{const toasts=document.querySelectorAll('.toast');toasts.forEach(toast=>{setTimeout(()=>{toast.classList.add('hide');setTimeout(()=>toast.remove(),500);},5000);});});function exportImage(elementId){const btn=document.getElementById('export-btn');const origHtml=btn.innerHTML;btn.innerHTML='<i data-lucide="loader" class="w-4 h-4 animate-spin"></i>';lucide.createIcons();setTimeout(()=>{html2canvas(document.getElementById(elementId),{backgroundColor:userTheme==='light'?'#f8fafc':'#020617',scale:2}).then(canvas=>{let a=document.createElement('a');a.href=canvas.toDataURL("image/jpeg");a.download='the_cup_export.jpg';a.click();btn.innerHTML=origHtml;lucide.createIcons();vibrate();});},200);}setInterval(()=>{document.querySelectorAll('.live-timer').forEach(el=>{let start=parseInt(el.dataset.start);if(start>0){let diff=Math.floor(Date.now()/1000)-start;if(diff<0)diff=0;let m=Math.floor(diff/60).toString().padStart(2,'0');let s=(diff%60).toString().padStart(2,'0');el.innerText=`${m}:${s}`;}});},1000);let touchstartX=0;let touchendX=0;const swipeArea=document.getElementById('swipe-area');if(swipeArea){swipeArea.addEventListener('touchstart',e=>{touchstartX=e.changedTouches[0].screenX;},{passive:true});swipeArea.addEventListener('touchend',e=>{touchendX=e.changedTouches[0].screenX;handleSwipe();},{passive:true});}function handleSwipe(){if(!document.getElementById('tab-playoffs'))return;let diff=touchstartX-touchendX;if(diff>60){if(!document.getElementById('content-playoffs').classList.contains('hidden')===false){switchTab('playoffs');vibrate();}}else if(diff<-60){if(!document.getElementById('content-groups').classList.contains('hidden')===false){switchTab('groups');vibrate();}}}</script></body></html>"""
# <<< AI_BLOCK:TEMPLATES_BASE

# >>> AI_BLOCK:TEMPLATES_MACROS
MATCH_MACRO = """{% macro render_match(m, is_admin, current_user, logs_dict={}, pred=None) %}{% set is_t1 = current_user and m.t1_user_id == current_user.id %}{% set is_t2 = current_user and m.t2_user_id == current_user.id %}{% set is_participant = is_t1 or is_t2 %}{% set my_team_id = m.team1_id if is_t1 else (m.team2_id if is_t2 else 0) %}<div class="match-card navy-card p-4 sm:p-5 border-white/5 shadow-lg relative overflow-hidden flex flex-col justify-between h-full" data-round="{{ m.round_num }}" data-team1="{{ m.team1_id }}" data-team2="{{ m.team2_id }}" data-stage="{{ m.stage }}">{% if m.stage == 'playoffs' %}<span class="absolute top-0 right-0 bg-blue-600 text-white text-[7px] font-black px-2 py-1 rounded-bl-xl tracking-widest uppercase">Playoff</span>{% endif %}{% if m.is_ot == 1 %}<span class="absolute top-0 left-0 bg-orange-600 text-white text-[7px] font-black px-2 py-1 rounded-br-xl tracking-widest uppercase">PP/SN</span>{% elif m.is_ot == 2 %}<span class="absolute top-0 left-0 bg-red-600 text-white text-[7px] font-black px-2 py-1 rounded-br-xl tracking-widest uppercase">Kontumace</span>{% endif %}<div class="flex justify-between items-start mb-2 px-1"><div class="text-[8px] text-slate-500 font-bold uppercase tracking-widest flex items-center gap-2">{% if m.stage == 'groups' %}KOLO {{ m.round_num }}{% endif %} {% if m.match_time %}<span class="flex items-center gap-1"><i data-lucide="clock" class="w-3 h-3"></i> {{ m.match_time }}</span>{% endif %} {% if m.pitch %}<span class="flex items-center gap-1"><i data-lucide="flag" class="w-3 h-3"></i> {{ m.pitch }}</span>{% endif %}{% if m.started_at %}<span class="live-timer text-red-500 animate-pulse font-mono ml-1" data-start="{{ m.started_at }}">00:00</span>{% endif %}</div><div class="flex gap-1.5 shrink-0">{% if m.status == 'planned' and is_admin and not m.started_at %}<form action="/match/{{ m.id }}/start_timer" method="POST" onsubmit="vibrate()"><button class="text-green-500 hover:text-green-400 p-1" title="Odstartovat čas"><i data-lucide="timer" class="w-4 h-4"></i></button></form>{% endif %}<button type="button" onclick="document.getElementById('log-{{ m.id }}').classList.toggle('hidden')" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="history" class="w-4 h-4"></i></button><a href="/match/{{ m.id }}/chat" class="text-blue-500 hover:text-blue-400 p-1"><i data-lucide="message-square-text" class="w-4 h-4"></i></a> {% if is_admin %}<button type="button" onclick="document.getElementById('sched-{{ m.id }}').classList.toggle('hidden')" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="calendar-cog" class="w-4 h-4"></i></button>{% endif %}</div></div><div id="log-{{ m.id }}" class="hidden mb-3 bg-slate-900/80 p-2.5 rounded-xl border border-white/5 space-y-1.5 max-h-32 overflow-y-auto"><h4 class="text-[8px] font-black uppercase text-blue-500 tracking-widest mb-1 border-b border-white/10 pb-1">Historie zápasu</h4>{% if m.id in logs_dict and logs_dict[m.id] %}{% for log in logs_dict[m.id] %}<p class="text-[8px] theme-text-main"><span class="opacity-50 font-mono mr-1">{{ log.created_at[-8:-3] }}</span> <span class="font-bold text-blue-400 mr-1">{{ log.username }}:</span> {{ log.action }}</p>{% endfor %}{% else %}<p class="text-[8px] text-slate-500 italic">Zatím žádné záznamy.</p>{% endif %}</div><form id="sched-{{ m.id }}" action="/match/{{ m.id }}/schedule" method="POST" class="hidden mb-4 bg-slate-900/50 p-2 rounded-xl border border-white/5 flex gap-1"><input type="time" name="time" value="{{ m.match_time }}" class="w-full rounded p-1 text-[10px] theme-text-main bg-transparent"><input type="text" name="pitch" placeholder="Hřiště" value="{{ m.pitch }}" class="w-full rounded p-1 text-[10px] theme-text-main bg-transparent"><button class="bg-blue-600 px-2 rounded text-white"><i data-lucide="check" class="w-3 h-3"></i></button></form><div class="grid grid-cols-3 items-center text-center w-full my-auto"><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ m.t1_color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{m.t1_logo}}', '{{m.t1_color}}')"><span class="text-xl sm:text-2xl drop-shadow-md">{% if m.t1_logo and 'static' in m.t1_logo %}<img src="{{m.t1_logo}}" class="w-full h-full object-contain p-1">{% else %}{{m.t1_logo}}{% endif %}</span></div><p class="text-[8px] sm:text-[9px] font-black uppercase truncate w-full theme-text-main">{{ m.t1_name }}</p></div><div class="text-2xl sm:text-3xl font-black italic tracking-tighter theme-text-main">{% if m.status == 'finished' %}{{ m.score1 }}:{{ m.score2 }}{% elif m.status == 'proposed' %}<span class="text-orange-500">{{ m.proposed_score1 }}:{{ m.proposed_score2 }}</span>{% else %}-:-{% endif %}</div><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ m.t2_color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{m.t2_logo}}', '{{m.t2_color}}')"><span class="text-xl sm:text-2xl drop-shadow-md">{% if m.t2_logo and 'static' in m.t2_logo %}<img src="{{m.t2_logo}}" class="w-full h-full object-contain p-1">{% else %}{{m.t2_logo}}{% endif %}</span></div><p class="text-[8px] sm:text-[9px] font-black uppercase truncate w-full theme-text-main">{{ m.t2_name }}</p></div></div><div class="mt-4 border-t border-white/5 pt-3">{% if m.status == 'planned' %}{% if is_participant or is_admin %}<form action="/match/{{ m.id }}/propose" method="POST" class="flex flex-col gap-2" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><input type="number" name="s2" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><button class="bg-blue-600 hover:bg-blue-500 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg"><i data-lucide="check" class="w-4 h-4"></i></button></div>{% if m.stage == 'playoffs' %}<label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center mt-1 font-bold"><input type="checkbox" name="is_ot" value="1" class="w-3 h-3"> Prodloužení / Penalty</label>{% endif %}<input type="hidden" name="team_id" value="{{ my_team_id if not is_admin else 0 }}"></form>{% if is_admin %}<div class="flex gap-2 mt-2"><form action="/match/{{ m.id }}/forfeit/{{ m.team1_id }}" method="POST" class="flex-1" onsubmit="return confirm('Kontumovat tým 1?');"><button class="w-full bg-red-900/50 hover:bg-red-800 text-red-500 py-1.5 rounded-lg text-[8px] font-black uppercase border border-red-500/20 transition-colors">Kontumace T1</button></form><form action="/match/{{ m.id }}/forfeit/{{ m.team2_id }}" method="POST" class="flex-1" onsubmit="return confirm('Kontumovat tým 2?');"><button class="w-full bg-red-900/50 hover:bg-red-800 text-red-500 py-1.5 rounded-lg text-[8px] font-black uppercase border border-red-500/20 transition-colors">Kontumace T2</button></form></div>{% endif %}{% elif current_user %}{% if not pred %}<form action="/match/{{ m.id }}/predict" method="POST" class="flex flex-col gap-1 mt-2" onsubmit="vibrate()"><span class="text-[8px] font-black uppercase text-blue-500 text-center tracking-widest mb-1">Tvoje tipovačka</span><div class="flex gap-2"><input type="number" name="p1" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><input type="number" name="p2" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><button class="bg-slate-700 hover:bg-slate-600 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg">TIP</button></div></form>{% else %}<div class="text-center w-full mt-2"><span class="text-blue-500 text-[9px] font-black uppercase tracking-widest block bg-blue-500/10 py-1.5 rounded-lg border border-blue-500/20">Tvůj tip: {{ pred.p_score1 }} : {{ pred.p_score2 }}</span></div>{% endif %}{% else %}<div class="text-center w-full"><span class="text-slate-500 text-[9px] font-black uppercase w-full block">Neodehráno</span></div>{% endif %}{% elif m.status == 'proposed' %}{% if is_admin or (is_participant and m.proposed_by_team_id != my_team_id) %}<div class="flex flex-col gap-2 w-full"><div class="flex gap-2"><form action="/match/{{ m.id }}/approve" method="POST" class="flex-1" onsubmit="vibrate()"><button class="w-full bg-green-600 hover:bg-green-500 py-2 rounded-lg text-white font-black text-[9px] uppercase tracking-widest shadow-lg">Schválit</button></form><button type="button" onclick="document.getElementById('counter-{{ m.id }}').classList.toggle('hidden'); vibrate();" class="flex-1 bg-red-500/20 text-red-500 py-2 rounded-lg font-black text-[9px] uppercase tracking-widest hover:bg-red-500/30">Odmítnout</button></div><form id="counter-{{ m.id }}" action="/match/{{ m.id }}/propose" method="POST" class="hidden flex flex-col gap-2 mt-1" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><input type="number" name="s2" required class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><button class="bg-orange-600 hover:bg-orange-500 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg"><i data-lucide="check" class="w-4 h-4"></i></button></div><label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center font-bold"><input type="checkbox" name="is_ot" value="1" class="w-3 h-3"> Prodloužení / Penalty</label><input type="hidden" name="team_id" value="{{ my_team_id if not is_admin else 0 }}"></form></div>{% else %}<div class="text-center w-full"><span class="bg-orange-500/10 text-orange-500 py-2 rounded-lg text-[8px] font-black uppercase w-full block border border-orange-500/20">Čeká se na potvrzení soupeřem...</span></div>{% endif %}{% elif m.status == 'finished' and is_admin %}<div class="text-center flex justify-center gap-4"><button type="button" onclick="document.getElementById('edit-{{ m.id }}').classList.toggle('hidden')" class="text-[8px] font-black uppercase text-slate-500 hover:text-slate-300">Upravit výsledek</button><form action="/match/{{ m.id }}/reset" method="POST" onsubmit="return confirm('Opravdu vymazat výsledek a logy zápasu?');"><button type="submit" class="text-[8px] font-black uppercase text-blue-500 hover:text-blue-400">Resetovat zápas</button></form></div><form id="edit-{{ m.id }}" action="/match/{{ m.id }}/update" method="POST" class="hidden flex flex-col gap-2 mt-2" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required value="{{ m.score1 }}" class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><input type="number" name="s2" required value="{{ m.score2 }}" class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><button class="bg-slate-700 hover:bg-slate-600 px-3 rounded-lg text-white font-black text-[9px] uppercase"><i data-lucide="check" class="w-4 h-4"></i></button></div><label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center font-bold"><input type="checkbox" name="is_ot" value="1" {% if m.is_ot %}checked{% endif %} class="w-3 h-3"> Prodloužení / Penalty</label></form>{% endif %}</div></div>{% endmacro %}"""
# <<< AI_BLOCK:TEMPLATES_MACROS

# >>> AI_BLOCK:TEMPLATES_VIEWS
# UX Implementace grafik: Branding Logo na Welcome, Header na main stránkách.

WELCOME_HTML = """<div class="welcome-card relative flex-1 flex flex-col items-center justify-center text-center overflow-hidden min-h-[75vh] rounded-3xl navy-card border border-white/5 shadow-2xl">
    <div class="absolute inset-0 z-0 opacity-10 blur-sm scale-105" style="background-image: url('{{ web_graphic }}'); background-size: cover; background-position: center;"></div>
    <div class="welcome-inner relative z-10 space-y-6 sm:space-y-8 px-4 w-full">
        <div class="inline-block p-1 bg-blue-600/5 rounded-[2rem] border border-blue-500/10 text-blue-500 shadow-2xl shadow-blue-500/10">
            <img src="{{ logo }}" class="w-24 h-24 sm:w-32 sm:h-32 object-contain" alt="THE CUP Logo">
        </div>
        <h1 class="text-5xl sm:text-7xl md:text-8xl font-black italic uppercase tracking-tighter theme-text-main drop-shadow-lg">THE CUP</h1>
        <p class="text-sm sm:text-lg text-slate-500 max-w-lg mx-auto font-bold">Profesionální organizace sportovních turnajů.</p>
        <div class="pt-6"><a href="/account" class="primary-action inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 sm:px-10 py-4 sm:py-5 rounded-xl sm:rounded-2xl font-black uppercase text-xs sm:text-sm tracking-widest shadow-xl active:scale-95 transition-all">Začít <i data-lucide="arrow-right" class="w-4 h-4"></i></a></div>
    </div>
</div>"""

INDEX_HTML = """<div class="esports-dashboard space-y-6 sm:space-y-8">
    <header class="dashboard-intro">
        <div>
            <p class="screen-eyebrow"><i data-lucide="gamepad-2" class="w-3.5 h-3.5"></i> Player hub</p>
            <h1 class="screen-title">Vítej zpět, <span>{{ current_user.username }}</span></h1>
            <p class="screen-subtitle">Turnaje, týmy a další zápasy na jednom místě.</p>
        </div>
        <a href="/account" class="profile-chip" aria-label="Otevřít účet {{ current_user.username }}">{{ current_user.username[0]|upper }}</a>
    </header>

    <section class="featured-panel" aria-labelledby="featured-title">
        <div class="featured-media"><img src="{{ web_graphic }}" alt="" aria-hidden="true"></div>
        <div class="featured-scrim"></div>
        <div class="featured-copy">
            <span class="featured-kicker"><i data-lucide="sparkles" class="w-3 h-3"></i> Tournament creator</span>
            <h2 id="featured-title" class="featured-title">Postav svůj turnaj</h2>
            <p class="featured-description">Vytvoř soutěž, pozvi týmy a spravuj výsledky v jednom rychlém mobilním rozhraní.</p>
            <div class="featured-actions">
                <a href="/create" class="featured-action featured-action--primary"><i data-lucide="plus" class="w-4 h-4"></i> Nový turnaj</a>
                <a href="/seasons" class="featured-action featured-action--secondary">Moje turnaje <i data-lucide="arrow-up-right" class="w-4 h-4"></i></a>
            </div>
        </div>
    </section>

    <section class="dashboard-stats" aria-label="Souhrn účtu">
        <a href="/seasons" class="stat-card metric-card">
            <span class="metric-copy"><span class="metric-label">Moje turnaje</span><strong class="metric-value">{{ stats.total_tournaments }}</strong></span>
            <span class="metric-icon"><i data-lucide="trophy" class="w-5 h-5"></i></span>
        </a>
        <a href="/teams" class="stat-card metric-card">
            <span class="metric-copy"><span class="metric-label">Registrované týmy</span><strong class="metric-value">{{ stats.total_teams }}</strong></span>
            <span class="metric-icon"><i data-lucide="users-round" class="w-5 h-5"></i></span>
        </a>
    </section>

    {% if invitations %}
    <section aria-labelledby="invitations-title">
        <div class="section-heading">
            <div><p class="section-kicker"><i data-lucide="mail-open" class="w-3.5 h-3.5"></i> Čeká na tebe</p><h2 id="invitations-title" class="section-title">Pozvánky</h2></div>
        </div>
        <div class="event-grid">
            {% for inv in invitations %}
            <article class="notification-card">
                <span class="notification-icon"><i data-lucide="ticket-check" class="w-5 h-5"></i></span>
                <div class="min-w-0 flex-1"><h3 class="event-card-title">{{ inv.t_name }}</h3><p class="mt-1 text-[10px] font-bold text-slate-400">Přímá pozvánka od organizátora</p></div>
                <div class="notification-actions">
                    <a href="/join/{{ inv.join_token }}" class="notification-action notification-action--accept">Vstoupit</a>
                    <form action="/invitation/{{ inv.id }}/decline" method="POST"><button type="submit" class="notification-action notification-action--decline">Skrýt</button></form>
                </div>
            </article>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {% if next_match %}
    <section aria-labelledby="next-match-title">
        <div class="section-heading">
            <div><p class="section-kicker" style="color:#fb923c"><i data-lucide="radio" class="w-3.5 h-3.5"></i> Match center</p><h2 id="next-match-title" class="section-title">Další zápas</h2></div>
            <a href="/tournament/{{ next_match.t_id }}" class="section-link">Detail <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i></a>
        </div>
        <article class="next-match-card">
            <div class="matchup">
                <div class="match-team">
                    <button type="button" class="team-mark" style="background-color: {{ next_match.t1_color }}" onclick="openLogoModal('{{ next_match.t1_logo }}', '{{ next_match.t1_color }}')" aria-label="Zobrazit logo týmu {{ next_match.t1_name }}">{% if next_match.t1_logo and 'static' in next_match.t1_logo %}<img src="{{ next_match.t1_logo }}" alt="">{% else %}<span>{{ next_match.t1_logo }}</span>{% endif %}</button>
                    <span class="match-team-name">{{ next_match.t1_name }}</span>
                </div>
                <span class="match-versus">VS</span>
                <div class="match-team match-team--away">
                    <button type="button" class="team-mark" style="background-color: {{ next_match.t2_color }}" onclick="openLogoModal('{{ next_match.t2_logo }}', '{{ next_match.t2_color }}')" aria-label="Zobrazit logo týmu {{ next_match.t2_name }}">{% if next_match.t2_logo and 'static' in next_match.t2_logo %}<img src="{{ next_match.t2_logo }}" alt="">{% else %}<span>{{ next_match.t2_logo }}</span>{% endif %}</button>
                    <span class="match-team-name">{{ next_match.t2_name }}</span>
                </div>
            </div>
            <div class="match-details">
                <a href="/tournament/{{ next_match.t_id }}" class="text-orange-400">{{ next_match.tr_name }}</a>
                <span class="flex items-center gap-3">{% if next_match.match_time %}<span class="flex items-center gap-1"><i data-lucide="clock-3" class="w-3 h-3"></i> {{ next_match.match_time }}</span>{% endif %}{% if next_match.pitch %}<span class="flex items-center gap-1"><i data-lucide="map-pin" class="w-3 h-3"></i> {{ next_match.pitch }}</span>{% endif %}</span>
            </div>
        </article>
    </section>
    {% endif %}

    {% if active_tourneys %}
    <section aria-labelledby="owned-events-title">
        <div class="section-heading">
            <div><p class="section-kicker"><i data-lucide="shield-check" class="w-3.5 h-3.5"></i> Organizuješ</p><h2 id="owned-events-title" class="section-title">Moje turnaje</h2></div>
            <a href="/seasons" class="section-link">Všechny <i data-lucide="chevron-right" class="w-3.5 h-3.5"></i></a>
        </div>
        <div class="event-grid">
            {% for t in active_tourneys %}
            <a href="/tournament/{{ t.id }}" class="tournament-card event-card">
                <div class="event-card-media">
                    <img src="{{ t.banner or web_graphic }}" alt="Banner turnaje {{ t.name }}" loading="lazy" decoding="async" class="object-cover" onerror="this.onerror=null;this.src='{{ web_graphic }}';">
                    <div class="event-badges"><span class="event-status event-status--live"><i data-lucide="circle-dot" class="w-3 h-3"></i> {{ t.status }}</span></div>
                </div>
                <div class="event-card-body">
                    <h3 class="event-card-title">{{ t.name }}</h3>
                    <div class="event-meta"><span><i data-lucide="calendar-days" class="w-3.5 h-3.5"></i> {{ format_date_cz(t.start_date) }}</span><span><i data-lucide="users" class="w-3.5 h-3.5"></i> {{ t.registered_teams }}/{{ t.max_teams }} týmů</span></div>
                    <div class="event-card-footer"><span class="event-card-hint">Spravovat turnaj</span><span class="event-card-arrow"><i data-lucide="arrow-up-right" class="w-4 h-4"></i></span></div>
                </div>
            </a>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {% if participating_tourneys %}
    <section aria-labelledby="participating-events-title">
        <div class="section-heading">
            <div><p class="section-kicker" style="color:#a78bfa"><i data-lucide="swords" class="w-3.5 h-3.5"></i> Soutěžíš</p><h2 id="participating-events-title" class="section-title">Účastním se</h2></div>
        </div>
        <div class="event-grid">
            {% for t in participating_tourneys %}
            <a href="/view/{{ t.id }}" class="tournament-card event-card">
                <div class="event-card-media">
                    <img src="{{ t.banner or web_graphic }}" alt="Banner turnaje {{ t.name }}" loading="lazy" decoding="async" class="object-cover" onerror="this.onerror=null;this.src='{{ web_graphic }}';">
                    <div class="event-badges"><span class="event-status"><i data-lucide="activity" class="w-3 h-3"></i> {{ t.status }}</span></div>
                </div>
                <div class="event-card-body">
                    <h3 class="event-card-title">{{ t.name }}</h3>
                    <div class="event-meta"><span><i data-lucide="user" class="w-3.5 h-3.5"></i> {{ t.username }}</span><span><i data-lucide="users" class="w-3.5 h-3.5"></i> {{ t.registered_teams }}/{{ t.max_teams }} týmů</span></div>
                    <div class="event-card-footer"><span class="event-card-hint">Otevřít turnaj</span><span class="event-card-arrow"><i data-lucide="arrow-up-right" class="w-4 h-4"></i></span></div>
                </div>
            </a>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {% if joinable_public_tourneys %}
    <section aria-labelledby="open-events-title">
        <div class="section-heading">
            <div><p class="section-kicker" style="color:#4ade80"><i data-lucide="radar" class="w-3.5 h-3.5"></i> Open lobby</p><h2 id="open-events-title" class="section-title">Volné turnaje</h2></div>
        </div>
        <div class="event-grid">
            {% for t in joinable_public_tourneys %}
            <a href="/join/{{ t.join_token }}" class="tournament-card event-card">
                <div class="event-card-media">
                    <img src="{{ t.banner or web_graphic }}" alt="Banner turnaje {{ t.name }}" loading="lazy" decoding="async" class="object-cover" onerror="this.onerror=null;this.src='{{ web_graphic }}';">
                    <div class="event-badges"><span class="event-status event-status--open"><i data-lucide="log-in" class="w-3 h-3"></i> Registrace</span></div>
                </div>
                <div class="event-card-body">
                    <h3 class="event-card-title">{{ t.name }}</h3>
                    <div class="event-meta"><span><i data-lucide="user" class="w-3.5 h-3.5"></i> {{ t.username }}</span><span><i data-lucide="calendar-days" class="w-3.5 h-3.5"></i> {{ format_date_cz(t.start_date) }}</span><span><i data-lucide="users" class="w-3.5 h-3.5"></i> {{ t.registered_teams }}/{{ t.max_teams }}</span></div>
                    <div class="event-card-footer"><span class="event-card-hint" style="color:#4ade80">Připojit tým</span><span class="event-card-arrow"><i data-lucide="arrow-up-right" class="w-4 h-4"></i></span></div>
                </div>
            </a>
            {% endfor %}
        </div>
    </section>
    {% endif %}

    {% if not invitations and not next_match and not active_tourneys and not participating_tourneys and not joinable_public_tourneys %}
    <section class="catalog-empty">
        <div><span class="metric-icon mx-auto"><i data-lucide="trophy" class="w-5 h-5"></i></span><h2 class="section-title mt-4">Začni prvním turnajem</h2><p class="screen-subtitle mx-auto">Vytvoření zabere jen chvilku. Týmy můžeš pozvat později.</p><a href="/create" class="featured-action featured-action--primary mt-5"><i data-lucide="plus" class="w-4 h-4"></i> Vytvořit turnaj</a></div>
    </section>
    {% endif %}
</div>"""

ACCOUNT_HTML = """<div class="max-w-md mx-auto w-full">{% if current_user %}
    <div class="text-center mb-6 sm:mb-8 relative p-10 navy-card rounded-3xl border border-white/5 shadow-2xl">
        <div class="absolute inset-0 opacity-10 rounded-3xl" style="background-image: url('{{ web_graphic }}'); background-size: cover; background-position: center;"></div>
        <div class="relative z-10 space-y-4">
            <div class="w-20 h-20 sm:w-24 sm:h-24 bg-blue-600/20 rounded-full flex items-center justify-center mx-auto border border-blue-500/30 text-blue-500 relative"><i data-lucide="user-check" class="w-8 h-8 sm:w-10 sm:h-10"></i>{% if current_user.is_pro %}<div class="absolute -top-2 -right-2 bg-yellow-500 text-slate-900 rounded-full p-1"><i data-lucide="crown" class="w-4 h-4"></i></div>{% endif %}</div>
            <h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter truncate theme-text-main">{{ current_user.username }}</h2>
            <p class="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-widest font-bold">Organizátor / Hráč • Tipovací body: {{ current_user.bet_points }}</p>
        </div>
    </div>
    {% if current_user.is_pro %}<div class="navy-card p-4 border-yellow-500/50 bg-yellow-500/10 mb-6 sm:mb-8 text-center shadow-[0_0_15px_rgba(234,179,8,0.1)]"><h3 class="text-yellow-500 font-black uppercase tracking-widest text-xs flex items-center justify-center gap-2"><i data-lucide="crown" class="w-4 h-4"></i> PRO Premium Aktivní</h3></div>{% else %}<div class="navy-card p-5 border-blue-500/30 mb-6 sm:mb-8 text-center relative overflow-hidden"><div class="absolute inset-0 bg-blue-600/5"></div><h3 class="theme-text-main font-black uppercase tracking-widest text-sm mb-2 relative z-10">Přejít na PRO Premium</h3><p class="text-[10px] text-slate-400 mb-4 font-bold relative z-10">Získejte přístup k modulu AI Logo Studio a dalším profesionálním nástrojům.</p><form action="/upgrade_pro" method="POST" class="relative z-10"><button class="bg-yellow-500 hover:bg-yellow-400 text-slate-900 font-black uppercase text-[10px] py-3 rounded-xl w-full tracking-widest transition-colors shadow-lg">Aktivovat PRO</button></form></div>{% endif %}
    <div class="navy-card p-6 border border-green-500/30 bg-green-500/10 mb-6 sm:mb-8"><h3 class="text-xs font-black uppercase text-green-500 mb-4 flex items-center gap-2"><i data-lucide="wifi-off" class="w-4 h-4"></i> Zero-Internet Host Mode</h3><p class="text-[9px] text-slate-400 mb-4 font-bold">Aktivuj Wi-Fi Hotspot. Ostatní se připojí a naskenují kód:</p><div class="bg-white p-2 inline-block rounded-xl mb-4 shadow-lg"><canvas id="host-qr"></canvas></div><p class="text-[10px] font-mono text-green-400 font-bold block">{{ host_url }}</p></div>
    <div class="flex gap-2 mb-6 sm:mb-8"><a href="/export/db" class="flex-1 bg-slate-800 hover:bg-slate-700 py-3 rounded-xl font-black uppercase text-[9px] sm:text-[10px] text-center flex justify-center items-center gap-2 transition-colors theme-text-main border border-white/5"><i data-lucide="download" class="w-4 h-4"></i> Záloha DB</a></div>
    <div class="navy-card p-5 sm:p-6 mb-6 sm:mb-8"><h3 class="text-base sm:text-lg font-black uppercase text-slate-100 mb-4 sm:mb-6 tracking-tighter flex items-center gap-2"><i data-lucide="palette" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Nastavení vzhledu</h3><form action="/set_theme" method="POST" class="space-y-4"><select name="theme" class="w-full rounded-xl p-3 text-xs sm:text-sm font-bold border-blue-500/30 cursor-pointer theme-text-main" onchange="this.form.submit()"><option value="system" {% if current_user.theme == 'system' %}selected{% endif %}>Dle systému telefonu</option><option value="light" {% if current_user.theme == 'light' %}selected{% endif %}>Světlý motiv</option><option value="dark" {% if current_user.theme == 'dark' %}selected{% endif %}>Tmavý motiv (Navy)</option></select></form></div>
    <div class="navy-card p-5 sm:p-6 mb-6 sm:mb-8"><h3 class="text-base sm:text-lg font-black uppercase text-slate-100 mb-4 sm:mb-6 tracking-tighter flex items-center gap-2"><i data-lucide="key" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Změna hesla</h3><form action="/change_password" method="POST" class="space-y-3 sm:space-y-4"><div><input type="password" name="current_password" placeholder="Stávající heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm theme-text-main"></div><div><input type="password" name="new_password" placeholder="Nové heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm border-blue-500/30 theme-text-main"></div><div><input type="password" name="confirm_password" placeholder="Potvrdit nové heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm border-blue-500/30 theme-text-main"></div><button type="submit" class="w-full bg-slate-800 py-3 rounded-xl font-black uppercase text-[9px] sm:text-[10px] tracking-widest hover:bg-slate-700 transition-colors theme-text-main">Uložit heslo</button></form></div>
    <div class="navy-card p-3 sm:p-4 mb-8 border-red-500/20"><a href="/logout" class="flex items-center justify-between p-3 sm:p-4 bg-red-500/10 rounded-xl hover:bg-red-500/20 transition-colors"><div class="flex items-center gap-3"><i data-lucide="log-out" class="w-4 h-4 sm:w-5 sm:h-5 text-red-500"></i><span class="text-xs sm:text-sm font-bold uppercase text-red-500">Odhlásit se</span></div></a></div>
    <script>setTimeout(()=>{new QRious({element:document.getElementById('host-qr'),value:'{{host_url}}',size:150});},100);</script>
{% else %}<div class="relative p-10 navy-card rounded-3xl border border-white/5 shadow-2xl">
    <div class="absolute inset-0 opacity-10 rounded-3xl" style="background-image: url('{{ web_graphic }}'); background-size: cover; background-position: center;"></div>
    <div class="relative z-10">
        <div class="text-center mb-8 sm:mb-10"><div class="w-16 h-16 sm:w-20 sm:h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 sm:mb-6 shadow-inner border border-white/5"><i data-lucide="lock" class="w-6 h-6 sm:w-8 sm:h-8 text-slate-400"></i></div><h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none mb-2 theme-text-main">Přihlášení</h2><p class="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-widest font-bold">Pro přístup se prosím přihlas</p></div>
        <form action="/login" method="POST" class="space-y-4 sm:space-y-6"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1">Uživatelské jméno</label><input name="username" required class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 mt-1 sm:mt-2 text-sm sm:text-base font-bold theme-text-main"></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1">Heslo</label><input type="password" name="password" required class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 mt-1 sm:mt-2 text-sm sm:text-base font-bold theme-text-main"></div><button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 sm:py-5 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-xs tracking-widest">Přihlásit se</button></form>
        <div class="mt-6 sm:mt-8 pt-6 sm:pt-8 border-t border-white/5 text-center"><p class="text-[10px] sm:text-xs text-slate-500 mb-3 sm:mb-4">Ještě nemáš účet?</p><form action="/register" method="POST" class="flex flex-col sm:flex-row gap-2"><input name="username" placeholder="Nové jméno" required class="flex-1 rounded-xl p-3 text-xs sm:text-sm theme-text-main"><input type="password" name="password" placeholder="Heslo" required class="flex-1 rounded-xl p-3 text-xs sm:text-sm theme-text-main"><button type="submit" class="bg-slate-800 py-3 sm:py-0 px-4 rounded-xl font-bold text-[9px] sm:text-[10px] uppercase hover:bg-slate-700 theme-text-main">Registrovat</button></form></div>
    </div>
</div>{% endif %}</div>"""

TEAMS_HTML = """<div class="flex justify-between items-center mb-6 sm:mb-8"><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter truncate theme-text-main pr-2">Registr Týmů</h2><a href="/teams/new" class="bg-blue-600 px-3 sm:px-4 py-2 sm:py-3 rounded-xl font-black text-[9px] sm:text-[10px] text-white uppercase hover:bg-blue-500 transition-colors shadow-lg shrink-0 flex items-center gap-1"><i data-lucide="plus" class="w-3 h-3 sm:w-4 sm:h-4"></i><span class="hidden sm:inline">Nový tým</span></a></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">{% for team in master_teams %}<a href="/teams/edit/{{ team.id }}" class="navy-card p-3 sm:p-4 flex items-center justify-between border-l-4 group hover:bg-white/5 transition-all" style="border-left-color: {{ team.color }}"><div class="flex items-center gap-3 sm:gap-4 min-w-0 pr-2"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 shadow-inner shrink-0 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ team.color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{team.logo}}', '{{team.color}}')">{% if team.logo and 'static' in team.logo %}<img src="{{team.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-xl sm:text-2xl drop-shadow-md">{{ team.logo }}</span>{% endif %}</div><span class="font-black uppercase text-xs sm:text-sm tracking-tight truncate theme-text-main">{{ team.name }}</span></div><div class="flex items-center gap-2"><span class="text-[8px] font-black text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20 text-center">ELO<br>{{ team.elo }}</span><i data-lucide="chevron-right" class="text-slate-500 shrink-0 w-4 h-4 sm:w-5 sm:h-5"></i></div></a>{% endfor %}</div>"""

TEAM_NEW_HTML = """<div class="max-w-xl mx-auto py-6 w-full"><div class="flex items-center gap-3 mb-6"><a href="/teams" class="text-slate-500 p-2 -ml-2 hover:bg-white/5 rounded-lg"><i data-lucide="arrow-left"></i></a><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter theme-text-main">Nový tým</h2></div><div class="navy-card p-6 shadow-2xl border-white/5 mb-8"><form method="POST" action="/teams/new" class="space-y-6" id="team-form"><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Základní identifikace</h3><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Jméno týmu</label><input name="name" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main" autocomplete="off"></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Zkratka (Tag)</label><input name="tag" maxlength="4" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main uppercase"></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Týmová barva</label><input type="color" name="color" value="#3b82f6" class="w-full h-11 rounded-xl p-0.5 outline-none cursor-pointer bg-slate-900/50 border border-white/5"></div></div></div><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Zdroj loga</h3><div class="flex gap-2"><label class="flex-1 relative"><input type="radio" name="logo_type" value="emoji" class="peer sr-only" checked onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="smile" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Ikona / Znak</span></div></label><label class="flex-1 relative"><input type="radio" name="logo_type" value="ai" class="peer sr-only" onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="sparkles" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Studio 👑</span></div></label></div><div id="section-emoji" class="block space-y-2"><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vyber symbol</label><input type="hidden" name="emoji_logo" id="team-logo" value="⚽"><div class="grid grid-cols-5 sm:grid-cols-8 gap-2 p-2 bg-slate-900/50 rounded-xl max-h-40 overflow-y-auto border border-white/5 shadow-inner">{% set emojis = ['⚽','🏒','🏀','🏐','🏈','🎾','🎱','🏓','🥊','🥋','🐅',' eagles','🦈','🐺','🐻','🦁','🐉','🐍','⚡','🔥','⭐','☠️','💎','🛡️'] %}{% for e in emojis %}<button type="button" onclick="document.getElementById('team-logo').value='{{ e }}'; document.querySelectorAll('.emoji-btn').forEach(b=>b.style.opacity=0.4); this.style.opacity=1;" class="emoji-btn text-2xl p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-all opacity-40">{{ e }}</button>{% endfor %}</div></div><div id="section-ai" class="hidden space-y-4 pt-2">{% if not current_user.is_pro %}<div class="text-center p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl"><p class="text-xs font-bold text-yellow-500 mb-2">Tato funkce vyžaduje PRO Premium</p><a href="/account" class="inline-block bg-yellow-500 text-slate-900 px-4 py-2 rounded-lg font-black text-[10px] uppercase">Aktivovat</a></div>{% else %}<div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vizuální Styl loga</label><select name="style" class="w-full rounded-xl p-3 text-xs font-bold bg-slate-900/50 theme-text-main mt-1">{% for k,v in styles.items() %}<option value="{{k}}">{{k}}</option>{% endfor %}</select></div><div class="grid grid-cols-3 gap-2"><div class="text-center cursor-pointer" onclick="openColorPicker('body')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Tělo</label><div id="swatch-body" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #ffffff;"></div><input type="hidden" name="color_body" id="input-body" value="White"></div><div class="text-center cursor-pointer" onclick="openColorPicker('outline')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Obrys</label><div id="swatch-outline" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #020617;"></div><input type="hidden" name="color_outline" id="input-outline" value="Black"></div><div class="text-center cursor-pointer" onclick="openColorPicker('fill')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Výplň</label><div id="swatch-fill" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #3b82f6;"></div><input type="hidden" name="color_fill" id="input-fill" value="Blue"></div></div><div id="ai-prompts" class="space-y-3 mt-4 border-t border-white/5 pt-4"><p class="text-[10px] font-black uppercase text-blue-500 tracking-widest">Generovací Prompty (Lze upravit)</p><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Fáze 1: Logo Maskota</label><textarea id="prompt_logo" class="w-full rounded-xl p-3 text-xs font-mono bg-slate-900/80 text-blue-300 border border-blue-500/30 h-20 outline-none" oninput="markCustom()"></textarea></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Fáze 2: Typografie</label><textarea id="prompt_text" class="w-full rounded-xl p-3 text-xs font-mono bg-slate-900/80 text-orange-300 border border-orange-500/30 h-20 outline-none" oninput="markCustom()"></textarea></div><button type="button" id="ai-generate-btn" onclick="triggerAiGeneration()" class="w-full bg-yellow-500 hover:bg-yellow-400 text-slate-900 py-4 rounded-xl font-black uppercase text-[10px] tracking-widest shadow-lg mt-2 transition-all">Generovat Náhled v AI</button></div><div id="ai-progress-ui" class="hidden mt-4 bg-slate-900/50 p-4 rounded-xl border border-white/5 text-center"><p class="text-[10px] font-black uppercase text-yellow-500 tracking-widest mb-3" id="progress-text">Zahajuji AI Syntézu...</p><div class="w-full bg-slate-950 rounded-full h-3 mb-2 overflow-hidden border border-white/10"><div id="progress-bar-fill" class="bg-gradient-to-r from-blue-600 to-yellow-500 h-full rounded-full transition-all duration-1000 ease-linear" style="width: 0%"></div></div><p class="text-xs font-mono text-slate-400 font-bold" id="progress-countdown">Odhad: 35 s</p></div><div id="ai-result-ui" class="hidden mt-4 bg-slate-900/50 p-5 rounded-2xl border border-white/5 text-center relative overflow-hidden"><div class="absolute inset-0 bg-green-500/5"></div><p class="text-[10px] font-black uppercase text-green-500 tracking-widest mb-4 relative z-10"><i data-lucide="check-circle" class="w-4 h-4 inline mr-1"></i> Hotový Náhled</p><img id="preview-image" src="" class="w-48 h-48 mx-auto object-contain mb-6 relative z-10 drop-shadow-2xl cursor-pointer hover:scale-110 transition-transform" onclick="openLogoModal(this.src, '#0f172a')"><input type="hidden" name="final_ai_logo" id="final_ai_logo_val"></div>{% endif %}</div></div><button type="submit" id="submit-btn-standard" class="w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest shadow-xl shadow-blue-900/40">Zapsat tým do registru</button><button type="submit" id="submit-btn-ai" class="w-full bg-green-600 hover:bg-green-500 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest shadow-xl shadow-green-900/40 hidden">Potvrdit a uložit tým</button></form></div></div><div id="custom-color-picker" class="fixed inset-0 z-[3000] bg-slate-950/90 backdrop-blur-md hidden flex flex-col items-center justify-center p-4 opacity-0 transition-opacity"><div class="navy-card p-6 w-full max-w-sm shadow-2xl border-white/10 relative"><button type="button" onclick="closeColorPicker()" class="absolute top-4 right-4 text-slate-500 hover:text-white"><i data-lucide="x" class="w-5 h-5"></i></button><h3 class="text-lg font-black uppercase italic mb-4 theme-text-main text-center">Vyber barvu</h3><div class="grid grid-cols-5 gap-3" id="color-grid"></div></div></div><script>let customPrompts = false; function markCustom() { customPrompts = true; } function updatePrompts() { if(customPrompts || !document.getElementById('prompt_logo')) return; let name = document.querySelector('input[name="name"]').value || 'Team'; let style = document.querySelector('select[name="style"]').value || 'clean'; let cBody = document.getElementById('input-body').value || 'White'; let cOut = document.getElementById('input-outline').value || 'Black'; let cFill = document.getElementById('input-fill').value || 'Blue'; let colors = `Main Body: ${cBody}, Outline: ${cOut}, Fill/Accents: ${cFill}`; let mascot = "creative mascot"; let lName = name.toLowerCase(); if(lName.includes('wolf')) mascot = 'ice wolf'; else if(lName.includes('bear')) mascot = 'polar bear'; else if(lName.includes('dragon')) mascot = 'ice dragon'; else if(lName.includes('hawk')) mascot = 'ice hawk'; else if(lName.includes('eagle')) mascot = 'ice eagle'; document.getElementById('prompt_logo').value = `Esports team mascot graphic. Concept: ${mascot} (can be animal, warrior, entity, or object). Style: ${style}. Colors: ${colors}. STRICTLY NO TEXT, NO LETTERS. Centered, solid bold outlines. Blank solid white background.`; document.getElementById('prompt_text').value = `Esports team typography logo. The exact word '${name}' in bold, thick, aggressive 3D esports font. Placed on a solid curved badge or banner background. Colors: ${colors}. STRICTLY NO MASCOTS, NO ANIMALS, ONLY THE TEXT. Blank solid white background.`; } document.querySelector('input[name="name"]').addEventListener('input', updatePrompts); document.body.addEventListener('click', function(e) { if(e.target.closest('#color-grid') || e.target.closest('select')) setTimeout(updatePrompts, 100); }); function toggleLogoType() { const isAi = document.querySelector('input[name="logo_type"]:checked').value === 'ai'; document.getElementById('section-emoji').style.display = isAi ? 'none' : 'block'; document.getElementById('section-ai').style.display = isAi ? 'block' : 'none'; if(isAi && !document.getElementById('ai-result-ui').classList.contains('hidden')) { document.getElementById('submit-btn-standard').classList.add('hidden'); document.getElementById('submit-btn-ai').classList.remove('hidden'); } else { document.getElementById('submit-btn-ai').classList.add('hidden'); document.getElementById('submit-btn-standard').classList.remove('hidden'); } setTimeout(updatePrompts, 100); } async function triggerAiGeneration() { let name = document.querySelector('input[name="name"]').value; if(!name) { alert('Nejprve zadejte název týmu do horního pole!'); return; } document.getElementById('ai-generate-btn').classList.add('hidden'); document.getElementById('submit-btn-standard').classList.add('hidden'); document.getElementById('ai-prompts').classList.add('opacity-50', 'pointer-events-none'); document.getElementById('ai-progress-ui').classList.remove('hidden'); let pLogo = document.getElementById('prompt_logo').value; let pText = document.getElementById('prompt_text').value; let duration = 35; let current = 0; let pBar = document.getElementById('progress-bar-fill'); let pCount = document.getElementById('progress-countdown'); let pTextMsg = document.getElementById('progress-text'); let timer = setInterval(() => { current++; let pct = Math.min((current / duration) * 100, 95); pBar.style.width = pct + '%'; pCount.innerText = `Zbývá cca: ${Math.max(duration - current, 1)} s`; if (current === 5) pTextMsg.innerText = "Fáze 1: Generuji grafiku maskota (Pixazo API)..."; if (current === 16) pTextMsg.innerText = "Fáze 2: Renderuji e-sport typografii..."; if (current === 28) pTextMsg.innerText = "Fáze 3: Čistím pozadí a skládám vrstvy..."; }, 1000); try { let formData = new FormData(); formData.append('team_name', name); formData.append('prompt_logo', pLogo); formData.append('prompt_text', pText); let res = await fetch('/api/v1/teams/generate_two_phase', { method: 'POST', body: formData }); let data = await res.json(); clearInterval(timer); pBar.style.width = '100%'; if(res.ok && data.status === 'success') { pTextMsg.innerText = "Hotovo!"; pCount.innerText = "Skládání dokončeno"; setTimeout(() => { document.getElementById('ai-progress-ui').classList.add('hidden'); document.getElementById('ai-result-ui').classList.remove('hidden'); document.getElementById('preview-image').src = data.logo_url; document.getElementById('final_ai_logo_val').value = data.logo_url; document.getElementById('submit-btn-ai').classList.remove('hidden'); }, 800); } else { throw new Error(data.error || "Neznámá chyba"); } } catch(err) { clearInterval(timer); alert("Chyba: " + err.message); document.getElementById('ai-progress-ui').classList.add('hidden'); document.getElementById('ai-generate-btn').classList.remove('hidden'); document.getElementById('submit-btn-standard').classList.remove('hidden'); document.getElementById('ai-prompts').classList.remove('opacity-50', 'pointer-events-none'); } } const palette = [{name: 'White', hex: '#ffffff'}, {name: 'Silver', hex: '#94a3b8'}, {name: 'Gray', hex: '#475569'}, {name: 'Black', hex: '#020617'}, {name: 'Navy', hex: '#0f172a'},{name: 'Blue', hex: '#3b82f6'}, {name: 'Cyan', hex: '#06b6d4'}, {name: 'Teal', hex: '#14b8a6'}, {name: 'Green', hex: '#22c55e'}, {name: 'Lime', hex: '#84cc16'},{name: 'Yellow', hex: '#eab308'}, {name: 'Orange', hex: '#f97316'}, {name: 'Red', hex: '#ef4444'}, {name: 'Rose', hex: '#f43f5e'}, {name: 'Pink', hex: '#ec4899'},{name: 'Purple', hex: '#a855f7'}, {name: 'Violet', hex: '#8b5cf6'}, {name: 'Indigo', hex: '#6366f1'}, {name: 'Brown', hex: '#78350f'}, {name: 'Gold', hex: '#ca8a04'}]; let currentTarget = null; function openColorPicker(target) { currentTarget = target; const grid = document.getElementById('color-grid'); grid.innerHTML = ''; palette.forEach(c => { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'w-full aspect-square rounded-full border-2 border-white/10 shadow-lg transition-transform hover:scale-110 active:scale-95'; btn.style.backgroundColor = c.hex; btn.onclick = () => selectCustomColor(c.name, c.hex); grid.appendChild(btn); }); const modal = document.getElementById('custom-color-picker'); modal.classList.remove('hidden'); void modal.offsetWidth; modal.classList.remove('opacity-0'); lucide.createIcons(); } function closeColorPicker() { const modal = document.getElementById('custom-color-picker'); modal.classList.add('opacity-0'); setTimeout(() => modal.classList.add('hidden'), 300); } function selectCustomColor(name, hex) { if(currentTarget) { document.getElementById('swatch-' + currentTarget).style.backgroundColor = hex; document.getElementById('input-' + currentTarget).value = name; } closeColorPicker(); } setTimeout(() => document.querySelector('.emoji-btn').click(), 100);</script>"""

CREATE_HTML = """<div class="max-w-xl mx-auto py-6 sm:py-8 text-center w-full">
    <div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">
        <div class="hero-card inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden rounded-[1.5rem] border border-white/5">
            <div class="hero-media w-full border-b border-white/10 h-32 sm:h-40 relative bg-slate-950 flex items-center justify-center">
                <img src="{{ web_graphic }}" class="w-full h-full object-cover opacity-80" alt="Grafika">
                <div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div>
            </div>
            <div class="hero-copy p-4 sm:p-5 relative z-10 -mt-6">
                <h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none text-white drop-shadow-md mb-2">Vytvořit turnaj</h2>
                <p class="text-[10px] sm:text-xs text-slate-400 flex items-center justify-center gap-2 font-bold"><i data-lucide="trophy" class="w-3.5 h-3.5 text-blue-500"></i> Nová Sezóna 2026</p>
            </div>
        </div>
    </div>
    <form method="POST" action="/create" id="tournament-form" class="navy-card p-5 sm:p-8 space-y-4 sm:space-y-6 border border-blue-500/10 shadow-2xl text-left">
        <div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Název turnaje</label><input name="name" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 outline-none text-lg sm:text-xl font-black mt-1 theme-text-main bg-slate-900/50"></div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Datum</label><input type="date" name="start_date" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm mt-1 theme-text-main bg-slate-900/50"></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Kapacita</label><input type="number" name="max_teams" value="8" min="2" max="32" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm font-bold mt-1 theme-text-main bg-slate-900/50"></div></div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Viditelnost</label><select name="is_public" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="0">Privátní (QR)</option><option value="1">Veřejný</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Formát</label><select name="format" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="groups" selected>Skupiny + Playoff</option><option value="knockout">Čistý Pavouk</option></select></div></div>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Skupiny</label><select name="group_count" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>Jedna tabulka</option><option value="2">Dvě skupiny (A, B)</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Počet kol</label><select name="rounds" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>1 Zápas</option><option value="2">2 Zápasy</option><option value="3">3 Zápasy</option></select></div></div>
        <div class="space-y-4">
            <h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Turnajový Banner</h3>
            <div class="flex gap-2">
                <label class="flex-1 relative"><input type="radio" name="banner_type" value="standard" class="peer sr-only" checked><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="type" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Standardní Design</span></div></label>
                <label class="flex-1 relative"><input type="radio" name="banner_type" value="ai" class="peer sr-only"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="image" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Banner 👑</span></div></label>
            </div>
        </div>
        <button type="submit" id="submit-btn" class="primary-action w-full bg-blue-600 hover:bg-blue-500 py-5 sm:py-6 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-sm tracking-widest shadow-xl shadow-blue-900/40 active:scale-95 transition-all flex justify-center items-center gap-2">Vytvořit a naplánovat <i data-lucide="chevron-right" class="w-4 h-4 sm:w-5 sm:h-5"></i></button>
    </form>
</div>
<script>document.getElementById('tournament-form').onsubmit = function(e) { const isAi = document.querySelector('input[name="banner_type"]:checked').value === 'ai'; {% if not current_user.is_pro %} if (isAi) { e.preventDefault(); alert("AI Banner vyžaduje PRO Premium"); return; } {% endif %} const btn = document.getElementById('submit-btn'); if(isAi) { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Generuji AI Banner (až 30s)...'; } else { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Ukládám...'; } btn.classList.add('opacity-80', 'pointer-events-none'); lucide.createIcons(); };</script>"""

SEASONS_HTML = """<div class="tournament-catalog space-y-6 sm:space-y-8">
    <header class="catalog-header">
        <div>
            <p class="screen-eyebrow"><i data-lucide="layers-3" class="w-3.5 h-3.5"></i> Tournament library</p>
            <h1 class="screen-title">Moje <span>turnaje</span></h1>
            <p class="screen-subtitle">Správa všech rozehraných i dokončených sezón.</p>
        </div>
        <a href="/create" class="catalog-create" aria-label="Vytvořit nový turnaj"><i data-lucide="plus" class="w-4 h-4"></i><span>Nový turnaj</span></a>
    </header>

    <div class="catalog-summary">
        <span class="catalog-summary-icon"><i data-lucide="trophy" class="w-5 h-5"></i></span>
        <div><strong class="block text-xl font-black italic leading-none theme-text-main">{{ tournaments|length }}</strong><span class="text-[9px] font-black uppercase tracking-[0.12em] text-slate-500">Turnajů v archivu</span></div>
    </div>

    {% if tournaments %}
    <div class="event-grid event-grid--catalog">
        {% for t in tournaments %}
        <article class="tournament-card event-card">
            <div class="event-card-media">
                <img src="{{ t.banner or web_graphic }}" alt="Banner turnaje {{ t.name }}" loading="lazy" decoding="async" class="object-cover" onerror="this.onerror=null;this.src='{{ web_graphic }}';">
                <div class="event-badges">
                    <span class="event-status {% if t.status == 'active' %}event-status--live{% endif %}"><i data-lucide="{% if t.status == 'active' %}radio{% elif t.status == 'finished' %}check-circle-2{% else %}clock-3{% endif %}" class="w-3 h-3"></i> {{ t.status }}</span>
                    <span class="event-visibility"><i data-lucide="{% if t.is_public %}globe-2{% else %}lock-keyhole{% endif %}" class="w-3 h-3"></i> {% if t.is_public %}Veřejný{% else %}Privátní{% endif %}</span>
                </div>
            </div>
            <div class="event-card-body">
                <h2 class="event-card-title">{{ t.name }}</h2>
                <div class="event-meta"><span><i data-lucide="calendar-days" class="w-3.5 h-3.5"></i> {{ format_date_cz(t.start_date) }}</span><span><i data-lucide="users" class="w-3.5 h-3.5"></i> {{ t.registered_teams }}/{{ t.max_teams }} týmů</span></div>
                <div class="mt-4">
                    <div class="capacity-row"><span>Obsazenost</span><span>{{ t.registered_teams }} / {{ t.max_teams }}</span></div>
                    <div class="capacity-track" role="progressbar" aria-label="Obsazenost turnaje {{ t.name }}" aria-valuemin="0" aria-valuemax="{{ t.max_teams }}" aria-valuenow="{{ t.registered_teams }}"><div class="capacity-fill" style="width: {{ ((t.registered_teams / t.max_teams) * 100)|round|int if t.max_teams else 0 }}%"></div></div>
                </div>
                <div class="event-card-actions">
                    <a href="/tournament/{{ t.id }}" class="event-manage"><i data-lucide="settings-2" class="w-4 h-4"></i> Spravovat</a>
                    <form action="/tournament/{{ t.id }}/delete" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu smazat turnaj ze systému?', this);">
                        <button type="submit" class="event-delete" aria-label="Smazat turnaj {{ t.name }}"><i data-lucide="trash-2" class="w-4 h-4"></i></button>
                    </form>
                </div>
            </div>
        </article>
        {% endfor %}
    </div>
    {% else %}
    <section class="catalog-empty">
        <div><span class="metric-icon mx-auto"><i data-lucide="trophy" class="w-5 h-5"></i></span><h2 class="section-title mt-4">Zatím bez turnajů</h2><p class="screen-subtitle mx-auto">Vytvoř první sezónu a pozvi svoje týmy.</p><a href="/create" class="featured-action featured-action--primary mt-5"><i data-lucide="plus" class="w-4 h-4"></i> Vytvořit turnaj</a></div>
    </section>
    {% endif %}
</div>"""

HOF_HTML = """<div class="max-w-2xl mx-auto">
    <div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">
        <div class="hero-card inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden rounded-[1.5rem] border border-white/5">
            <div class="hero-media w-full border-b border-white/10 h-32 sm:h-40 relative bg-slate-950 flex items-center justify-center">
                <img src="{{ web_graphic }}" class="w-full h-full object-cover opacity-80" alt="Grafika">
                <div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div>
            </div>
            <div class="hero-copy p-4 sm:p-5 relative z-10 -mt-6">
                <h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none text-white drop-shadow-md mb-2">Síň Slávy</h2>
                <p class="text-[10px] sm:text-xs text-slate-400 flex items-center justify-center gap-2 font-bold"><i data-lucide="award" class="w-3.5 h-3.5 text-blue-500"></i> Globální power ranking</p>
            </div>
        </div>
    </div>
    <div class="navy-card overflow-hidden mb-8 shadow-xl"><table class="w-full text-left"><tr class="bg-white/5 text-[9px] uppercase font-black tracking-wider text-slate-400"><th class="p-4">Tým</th><th class="p-4 text-center text-yellow-500">ELO RATING</th></tr>{% for t in teams %}
        <tr class="border-b border-white/5 hover:bg-white/5"><td class="p-4 flex items-center gap-3"><div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border border-white/10 cursor-pointer" style="background-color: {{t.color}}" onclick="openLogoModal('{{t.logo}}', '{{t.color}}')">{% if t.logo and 'static' in t.logo %}<img src="{{t.logo}}" class="w-full h-full object-contain p-1.5">{% else %}<span class="text-sm">{{t.logo}}</span>{% endif %}</div><span class="font-black uppercase text-xs theme-text-main">{{t.name}}</span></td><td class="p-4 text-center font-black text-yellow-500 text-lg">{{t.elo}}</td></tr>
    {% endfor %}</table></div><div class="navy-card p-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest mb-4 text-center">Top 10 Sázkařů (Tipovačka)</h3><div class="space-y-2">{% for b in bettors %}
        <div class="flex justify-between items-center bg-slate-900/40 p-3 rounded-xl border border-white/5"><span class="font-black uppercase text-xs text-slate-300">{{loop.index}}. {{ b.username }}</span><span class="text-blue-400 font-black text-sm">{{ b.bet_points }} b</span></div>
    {% endfor %}</div></div>
</div>"""

DETAIL_UI = MATCH_MACRO + """<div id="live-sync-container" class="tournament-detail-shell" data-tid="{{ tournament.id }}"><div id="export-area" class="w-full pb-4">
<div class="tournament-overview w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">
    <div class="tournament-hero hero-card inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden rounded-[1.5rem] border border-white/5">
        {% if tournament.banner %}
            <div class="tournament-hero-media w-full border-b border-white/10 h-48 sm:h-64 relative bg-slate-950 flex items-center justify-center"><img src="{{ tournament.banner }}" class="w-full h-full object-cover opacity-90" alt="Banner turnaje {{ tournament.name }}" loading="eager" decoding="async"><div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div></div>
            <div class="tournament-hero-content p-4 sm:p-5 relative z-10 -mt-8">
        {% else %}
            <div class="tournament-hero-content tournament-hero-content--plain p-4 sm:p-5 relative z-10">
                <div class="tournament-hero-backdrop absolute inset-0 opacity-10 rounded-2xl" style="background-image: url('{{ web_graphic }}'); background-size: cover; background-position: center;" aria-hidden="true"></div>
                <div class="tournament-hero-body relative z-10 space-y-4">
        {% endif %}
                {% if tournament.status == 'finished' and podium and podium.first %}
                    <i data-lucide="crown" class="w-8 h-8 text-yellow-500 mx-auto mb-1 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]"></i><h3 class="text-[9px] text-yellow-500 font-black uppercase tracking-widest mb-1">Vítěz Turnaje</h3><h2 class="text-2xl font-black italic uppercase tracking-tighter text-yellow-500 mb-2">{{ podium.first.name }}</h2>
                    <div class="flex justify-center items-end gap-6 sm:gap-8 mt-4 border-t border-white/10 pt-4">{% if podium.second %}<div class="flex flex-col items-center opacity-80"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">2. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.second.color }}" onclick="openLogoModal('{{podium.second.logo}}', '{{podium.second.color}}')">{% if podium.second.logo and 'static' in podium.second.logo %}<img src="{{podium.second.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.second.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.second.name }}</span></div>{% endif %}{% if podium.third %}<div class="flex flex-col items-center opacity-70"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">3. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.third.color }}" onclick="openLogoModal('{{podium.third.logo}}', '{{podium.third.color}}')">{% if podium.third.logo and 'static' in podium.third.logo %}<img src="{{podium.third.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.third.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.third.name }}</span></div>{% endif %}</div>
                {% else %}
                    {% if not tournament.banner %}<i data-lucide="award" class="tournament-hero-icon w-8 h-8 sm:w-10 sm:h-10 text-blue-500 mx-auto mb-1 sm:mb-2"></i>{% endif %}
                    <h2 class="tournament-hero-title text-2xl sm:text-3xl font-black italic uppercase tracking-tighter leading-none theme-text-main">{{ tournament.name }}</h2>
                {% endif %}
                <div class="tournament-meta mt-4 font-bold">
                    <span class="tournament-meta-item"><i data-lucide="calendar-days" class="w-3.5 h-3.5 text-blue-500"></i>{{ format_date_cz(tournament.start_date) }}</span>
                    <span class="tournament-meta-item"><i data-lucide="{{ 'globe-2' if tournament.is_public else 'lock-keyhole' }}" class="w-3.5 h-3.5 text-blue-500"></i>{{ 'Veřejný' if tournament.is_public else 'Privátní' }}</span>
                    <span class="tournament-status tournament-status-{{ tournament.status }}">{{ {'draft': 'Připravuje se', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(tournament.status, tournament.status) }}</span>
                </div>
        {% if not tournament.banner %}</div></div>{% endif %}
            </div>
    </div>
    <div class="tournament-actions" data-html2canvas-ignore>
        <a href="/tv/{{ tournament.id }}" target="_blank" rel="noopener" class="tournament-action tournament-action--tv" aria-label="Otevřít TV režim"><i data-lucide="monitor" class="w-4 h-4"></i><span>TV režim</span></a>
        <a href="/export/csv/{{ tournament.id }}" class="tournament-action tournament-action--excel" aria-label="Exportovat tabulku do CSV"><i data-lucide="table-2" class="w-4 h-4"></i><span>Excel</span></a>
        <button type="button" onclick="exportImage('export-area')" id="export-btn" class="tournament-action tournament-action--share" aria-label="Sdílet turnaj jako obrázek"><i data-lucide="camera" class="w-4 h-4"></i><span>Sdílet</span></button>
    </div>
</div>
{% if tournament.status != 'draft' %}
<div class="match-filter-bar" data-html2canvas-ignore id="filter-controls" role="group" aria-label="Filtr zápasů">
    <button type="button" data-filter="all" onclick="filterMatches(this, 'all')" aria-pressed="true" class="match-filter filter-btn active-filter bg-blue-600 text-white shadow-lg border border-blue-500"><i data-lucide="layout-grid" class="w-3.5 h-3.5"></i><span>Vše</span></button>
    {% if not is_knockout_only %}{% for r in range(1, tournament.rounds + 1) %}<button type="button" data-filter="round" data-value="{{ r }}" onclick="filterMatches(this, 'round', {{ r }})" aria-pressed="false" class="match-filter filter-btn bg-slate-900/50 theme-text-main border border-white/5 hover:border-blue-500/50"><i data-lucide="circle-dot" class="w-3.5 h-3.5"></i><span>Kolo {{ r }}</span></button>{% endfor %}{% endif %}
    {% if has_playoffs or is_knockout_only %}<button type="button" data-filter="playoff" onclick="filterMatches(this, 'playoff')" aria-pressed="false" class="match-filter filter-btn bg-slate-900/50 theme-text-main border border-white/5 hover:border-blue-500/50"><i data-lucide="trophy" class="w-3.5 h-3.5"></i><span>Playoff</span></button>{% endif %}
    {% if current_user %}<button type="button" data-filter="mine" onclick="filterMatches(this, 'mine', {{ current_user.id }})" aria-pressed="false" class="match-filter match-filter--mine filter-btn bg-slate-900/50 text-orange-500 border border-orange-500/30 hover:bg-orange-600/20"><i data-lucide="user-round" class="w-3.5 h-3.5"></i><span>Moje zápasy</span></button>{% endif %}
</div>
{% endif %}
<div id="content-main" class="tournament-content flex flex-col lg:flex-row gap-6 sm:gap-8 items-start w-full"><div class="w-full lg:w-[380px] xl:w-[420px] lg:sticky lg:top-24 shrink-0">{% if tournament.status == 'draft' %}<div class="bg-blue-600/10 border border-blue-500/20 p-4 sm:p-5 rounded-2xl mb-6 text-center shadow-lg"><i data-lucide="megaphone" class="w-8 h-8 text-blue-500 mx-auto mb-2"></i><h3 class="text-blue-500 font-black uppercase tracking-widest text-sm mb-1">Fáze: Oznámení turnaje</h3><p class="text-slate-400 text-xs font-bold leading-relaxed">Probíhá nábor hráčů a registrace týmů. Turnaj se automaticky vygeneruje a odstartuje <strong class="text-blue-400">{{ format_date_cz(tournament.start_date) }}</strong>, nebo jej může organizátor kdykoliv spustit manuálně.</p></div>
{% if is_admin %}<div class="flex gap-2 mb-6"><a href="/tournament/{{ tournament.id }}/invite" class="bg-blue-600 px-4 py-4 rounded-xl text-[10px] font-black uppercase flex-1 text-center flex items-center justify-center gap-2 text-white"><i data-lucide="qr-code" class="w-4 h-4"></i> Pozvat Týmy</a>{% if teams|length >= 2 %}<a href="/tournament/{{ tournament.id }}/start" class="bg-green-500 text-white px-4 py-4 rounded-xl text-[10px] font-black uppercase flex-1 text-center"><i data-lucide="play" class="w-4 h-4 inline mr-1"></i> Odstartovat</a>{% endif %}</div>{% endif %}<div class="navy-card p-5 mb-6 shadow-xl relative"><div class="text-[9px] text-slate-500 uppercase font-black absolute top-3 right-4">{{ teams|length }}/{{ tournament.max_teams }}</div><h3 class="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-4">Registrované Týmy</h3><div class="space-y-2">{% for t in teams %}<div class="bg-slate-900/50 p-2.5 rounded-xl flex items-center justify-between border border-white/5"><div class="flex items-center gap-3 min-w-0 pr-2"><div class="w-8 h-8 rounded flex items-center justify-center shrink-0 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ t.color }}" onclick="openLogoModal('{{t.logo}}', '{{t.color}}')">{% if t.logo and 'static' in t.logo %}<img src="{{t.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm drop-shadow-md">{{ t.logo }}</span>{% endif %}</div><span class="text-[10px] font-bold uppercase theme-text-main truncate">{{ t.name }} {% if tournament.group_count > 1 and not is_knockout_only %}<span class="text-[8px] text-blue-500 ml-1">(Sk. {{ t.group_name }})</span>{% endif %}</span></div>{% if is_admin %}<form action="/tournament/{{ tournament.id }}/remove_team/{{ t.id }}" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu vyřadit tým z turnaje?', this);"><button class="text-red-500 hover:bg-red-500/20 p-1.5 rounded-lg transition-colors"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button></form>{% endif %}</div>{% endfor %}</div>
{% if is_admin %}<div class="mt-4 pt-4 border-t border-white/5"><h4 class="text-[9px] font-black text-slate-500 uppercase mb-2">Přidat můj tým</h4><div class="max-h-32 overflow-y-auto space-y-1 pr-1">{% for mt in master_teams %}<form action="/tournament/{{ tournament.id }}/add_existing/{{ mt.id }}" method="POST"><button class="w-full bg-slate-900/50 p-2 rounded-lg flex items-center justify-between border border-white/5 hover:border-blue-500/50"><span class="text-[9px] font-bold uppercase truncate theme-text-main"><span class="mr-1">{% if mt.logo and 'static' in mt.logo %}<img src="{{mt.logo}}" class="w-4 h-4 inline object-contain">{% else %}{{ mt.logo }}{% endif %}</span> {{ mt.name }}</span><span class="text-[10px] text-blue-500 font-bold">＋</span></button></form>{% endfor %}</div></div>{% endif %}</div>{% endif %}
{% if is_admin %}<div class="navy-card p-5 mb-6 shadow-xl" data-html2canvas-ignore><h3 class="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="shield" class="w-3 h-3 text-blue-500"></i> Nastavení Rozhodčích</h3><form action="/tournament/{{ tournament.id }}/referees" method="POST" class="flex flex-col gap-2"><input type="text" name="referees" value="{{ tournament.referees }}" placeholder="Napiš jména (např. Petr, Karel)..." class="w-full rounded-xl p-3 text-xs font-bold theme-text-main bg-slate-900/50"><button class="bg-slate-800 py-2 rounded-xl text-[9px] font-black uppercase theme-text-main border border-white/5">Uložit rozhodčí</button></form></div>{% endif %}
{% if is_admin and tournament.status == 'active' %}<div class="navy-card p-5 mb-6 shadow-xl border border-blue-500/30" data-html2canvas-ignore><h3 class="text-[9px] font-black text-blue-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="settings" class="w-3 h-3"></i> Správa turnaje</h3><div class="flex flex-col gap-2">{% if not is_knockout_only %}<form action="/tournament/{{ tournament.id }}/playoff" method="POST"><button class="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-xl text-white font-black text-[10px] uppercase transition-colors">Vygenerovat Playoff</button></form>{% endif %}<form action="/tournament/{{ tournament.id }}/finish" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu ukončit turnaj?', this);"><button class="w-full bg-slate-800 hover:bg-slate-700 py-3 rounded-xl font-black text-[10px] uppercase text-red-400 border border-red-500/20 transition-colors">Ukončit turnaj</button></form></div></div>{% endif %}
{% if standings and not is_knockout_only %}
<div class="standings-card navy-card overflow-hidden shadow-2xl mb-6 table-responsive bg-slate-900/30 view-carousel view-active" id="view-standings">
    <table class="standings-table w-full text-left whitespace-nowrap">
        <thead><tr class="standings-head bg-slate-800/80 text-[8px] text-slate-400 uppercase font-black border-b border-white/5 cursor-help">
            <th class="standings-team-heading p-3 sm:p-4">Tým</th>
            <th class="standings-played-heading p-3 sm:p-4 text-center" onclick="showLegend(event, 'Zápasy celkem')" aria-label="Zápasy celkem">Z</th>
            <th class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center" onclick="showLegend(event, 'Výhry (3 body)')" aria-label="Výhry">V</th>
            <th class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center" onclick="showLegend(event, 'Remízy (1 bod)')" aria-label="Remízy">R</th>
            <th class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center" onclick="showLegend(event, 'Prohry (0 bodů)')" aria-label="Prohry">P</th>
            <th class="standings-score-heading p-3 sm:p-4 text-center" onclick="showLegend(event, 'Skóre (Vstřelené : Inkasované)')">Skóre</th>
            <th class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center" onclick="showLegend(event, 'Gólový rozdíl')" aria-label="Gólový rozdíl">GR</th>
            <th class="standings-points-heading p-3 sm:p-4 text-center text-blue-500" onclick="showLegend(event, 'Body celkem')" aria-label="Body celkem">B</th>
        </tr></thead>
        <tbody>{% set ns = namespace(last_group='') %}{% for s in standings %}
            {% if tournament.group_count > 1 and s.group != ns.last_group %}<tr class="bg-blue-900/20"><td colspan="8" class="p-2 text-center text-[9px] font-black text-blue-400 uppercase tracking-widest border-b border-white/5">Skupina {{ s.group }}</td></tr>{% set ns.last_group = s.group %}{% endif %}
            <tr class="standings-row border-b border-white/5 hover:bg-white/5">
                <td class="standings-team-cell p-3 sm:p-4"><div class="flex items-center gap-2.5 sm:gap-3 min-w-0"><div class="standings-logo w-9 h-9 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center shrink-0 border border-white/10 cursor-pointer hover:scale-105 transition-transform" style="background-color: {{ s.color }}" onclick="openLogoModal('{{s.logo}}', '{{s.color}}')">{% if s.logo and 'static' in s.logo %}<img src="{{s.logo}}" class="w-full h-full object-contain p-1" alt="Logo {{ s.name }}" loading="lazy" decoding="async">{% else %}<span class="text-sm drop-shadow-md">{{ s.logo }}</span>{% endif %}</div><span class="standings-name font-black uppercase text-[11px] sm:text-xs theme-text-main truncate">{{ s.name }}</span></div></td>
                <td class="standings-cell p-3 sm:p-4 text-center text-[10px] font-bold theme-text-main">{{ s.gp }}</td>
                <td class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center text-[10px] font-bold theme-text-main">{{ s.w }}</td>
                <td class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center text-[10px] font-bold theme-text-main">{{ s.d }}</td>
                <td class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center text-[10px] font-bold theme-text-main">{{ s.l }}</td>
                <td class="standings-score p-3 sm:p-4 text-center text-[10px] font-black theme-text-main">{{ s.gf }}:{{ s.ga }}</td>
                <td class="standings-optional hidden sm:table-cell p-3 sm:p-4 text-center text-[10px] font-bold theme-text-main">{{ s.gd }}</td>
                <td class="standings-points p-3 sm:p-4 text-center text-blue-500 font-black text-base sm:text-lg">{{ s.pts }}</td>
            </tr>
        {% endfor %}</tbody>
    </table>
</div>
{% endif %}</div>
    <div class="flex-1 w-full min-w-0" id="match-container"><div class="grid grid-cols-1 md:grid-cols-2 gap-4 view-carousel" id="groups-grid">{% for m in group_matches %}{{ render_match(m, is_admin, current_user, logs, preds.get(m.id)) }}{% endfor %}</div><div class="w-full overflow-x-auto py-4 sm:py-8 table-responsive view-carousel hidden" id="playoff-bracket"><div class="flex flex-row justify-start lg:justify-center items-stretch gap-12 sm:gap-16 min-w-max px-4">{% set playoff_rounds = [] %}{% for m in playoff_matches %}{% if m.round_num not in playoff_rounds %}{% set _ = playoff_rounds.append(m.round_num) %}{% endif %}{% endfor %}{% set ns2 = namespace(max_round=0) %}{% if playoff_rounds %}{% set ns2.max_round = playoff_rounds | max %}{% endif %}
                {% if playoff_matches|length >= 2 %}<div class="flex flex-col justify-around gap-12 w-64 sm:w-80 shrink-0 relative py-8"><div class="bracket-line-right hidden md:block"></div>{% for m in playoff_matches if m.round_num < 98 %}{{ render_match(m, is_admin, current_user, logs, preds.get(m.id)) }}{% endfor %}</div>{% endif %}
                <div class="flex flex-col justify-center gap-8 w-72 sm:w-[22rem] shrink-0 relative z-10">{% set final_m = playoff_matches | selectattr('round_num', 'equalto', 100) | list %}{% set bronze_m = playoff_matches | selectattr('round_num', 'equalto', 98) | list %}
                    {% if final_m %}<div class="relative"><div class="absolute -inset-1 bg-gradient-to-r from-blue-600 to-cyan-500 rounded-[1.5rem] blur opacity-25"></div><div class="text-center mb-1"><span class="bg-blue-500/20 text-blue-500 text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-widest">Finále</span></div>{{ render_match(final_m[0], is_admin, current_user, logs, preds.get(final_m[0].id)) }}</div>{% endif %}
                    {% if bronze_m %}<div class="relative mt-4"><div class="text-center mb-1"><span class="bg-orange-500/20 text-orange-500 text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-widest">O 3. místo</span></div>{{ render_match(bronze_m[0], is_admin, current_user, logs, preds.get(bronze_m[0].id)) }}</div>{% endif %}
                    {% if not final_m and not bronze_m and is_admin and tournament.status == 'active' and tournament.stage == 'playoffs' %}<div class="navy-card p-6 border-dashed border-2 border-slate-700/50 flex flex-col items-center justify-center text-center bg-slate-900/30"><i data-lucide="server" class="w-8 h-8 text-blue-500 mb-3 opacity-80"></i><span class="text-blue-400 font-bold text-xs uppercase tracking-widest">Generování pavouka</span><form action="/tournament/{{ tournament.id }}/next_round" method="POST" class="mt-4 w-full"><button class="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest shadow-lg shadow-blue-900/30 transition-colors">Vygenerovat další kolo</button></form><form action="/tournament/{{ tournament.id }}/generate_final" method="POST" class="mt-2 w-full"><button class="w-full bg-yellow-500 hover:bg-yellow-400 py-3 rounded-xl text-slate-900 font-black text-[10px] uppercase tracking-widest shadow-lg transition-colors">Vygenerovat Finále & o 3. místo</button></form></div>{% endif %}
                </div>
</div></div></div></div></div></div>
<script>
const currentMyTeams = {{ my_team_ids | tojson | safe if my_team_ids else '[]' }};

function filterMatches(button, type, val = null) {
    document.querySelectorAll('.filter-btn').forEach(candidate => {
        candidate.classList.remove('active-filter', 'bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500', 'bg-orange-600/20', 'text-orange-500', 'border-orange-500/30');
        candidate.classList.add('bg-slate-900/50', 'theme-text-main', 'border-white/5');
        candidate.setAttribute('aria-pressed', 'false');
        if (candidate.dataset.filter === 'mine') {
            candidate.classList.add('text-orange-500', 'border-orange-500/30');
        }
    });

    const currentButton = button || document.querySelector('.filter-btn[data-filter="' + type + '"]');
    if (currentButton) {
        currentButton.classList.add('active-filter');
        currentButton.classList.remove('bg-slate-900/50', 'theme-text-main', 'border-white/5', 'text-orange-500', 'border-orange-500/30');
        currentButton.setAttribute('aria-pressed', 'true');
        if (type === 'mine') {
            currentButton.classList.add('bg-orange-600/20', 'text-orange-500', 'border-orange-500/30');
        } else {
            currentButton.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500');
        }
    }

    const groupsGrid = document.getElementById('groups-grid');
    const playoffBracket = document.getElementById('playoff-bracket');
    const cards = document.querySelectorAll('.match-card');

    if (type === 'playoff') {
        groupsGrid.classList.add('hidden');
        playoffBracket.classList.remove('hidden');
        return;
    }

    playoffBracket.classList.add('hidden');
    groupsGrid.classList.remove('hidden');
    cards.forEach(card => {
        if (card.dataset.stage === 'playoffs') return;
        let show = type === 'all';
        if (type === 'round' && card.dataset.round == val) show = true;
        if (type === 'mine') {
            const teamOne = parseInt(card.dataset.team1);
            const teamTwo = parseInt(card.dataset.team2);
            show = currentMyTeams.includes(teamOne) || currentMyTeams.includes(teamTwo);
        }
        card.style.display = show ? 'flex' : 'none';
    });
}

{% if is_knockout_only and tournament.status != 'draft' %}
document.addEventListener('DOMContentLoaded', () => {
    filterMatches(document.querySelector('.filter-btn[data-filter="playoff"]'), 'playoff');
});
{% endif %}
</script>"""

JOIN_UI = """<div class="max-w-xl mx-auto py-6 sm:py-12 text-center w-full">
    <div class="mb-6 sm:mb-8 flex flex-col items-center">
        <span class="text-[8px] sm:text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2 inline-block tracking-widest">{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t_status, t_status) }}</span>
        <h2 class="text-3xl sm:text-4xl font-black italic uppercase mb-1 tracking-tighter theme-text-main">{{ t_name }}</h2>
        <p class="text-xs sm:text-sm text-slate-500">Pořadatel: {{ t_username }}</p>
        <p class="text-[10px] sm:text-xs text-slate-500 flex items-center gap-1.5 mt-2"><i data-lucide="calendar-days" class="w-3.5 h-3.5 text-blue-500 opacity-70"></i> Zahájení: {{ format_date_cz(t_start_date) }}</p>
        <p class="text-lg sm:text-xl font-bold theme-text-main flex items-center gap-2 sm:gap-2.5 mt-4 p-3 sm:p-4 navy-card border-l-4 border-l-blue-600"><i data-lucide="users" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Registrováno: {{ t_registered_teams }} / {{ t_max_teams }} týmů</p>
    </div>
    <div class="navy-card p-5 sm:p-6 mb-8 sm:mb-10 shadow-2xl text-left">{% if my_teams %}<form method="POST" class="mb-6 sm:mb-8 pb-6 sm:pb-8 border-b border-white/5 space-y-3 sm:space-y-4"><h3 class="text-[9px] sm:text-[10px] font-black uppercase text-blue-500 tracking-widest flex items-center gap-2"><i data-lucide="check-circle" class="w-3 h-3 sm:w-4 sm:h-4"></i> Nasadit existující tým</h3><select name="master_id" class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 text-sm sm:text-base font-bold bg-slate-900/50 cursor-pointer theme-text-main">{% for mt in my_teams %}<option value="{{ mt.id }}">{{ mt.name }}</option>{% endfor %}</select><button class="w-full bg-slate-800 hover:bg-slate-700 py-3 sm:py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs theme-text-main transition-colors flex items-center justify-center gap-1.5">Potvrdit nasazení <i data-lucide="chevron-right" class="w-3 h-3 sm:w-4 sm:h-4"></i></button></form>{% endif %}<h3 class="text-[9px] sm:text-[10px] font-black uppercase text-blue-500 tracking-widest mb-3 sm:mb-4 flex items-center gap-2"><i data-lucide="user-plus" class="w-3 h-3 sm:w-4 sm:h-4"></i> Registrace nového týmu</h3><div class="p-4 bg-slate-900/50 rounded-xl border border-white/5 text-center"><p class="text-xs text-slate-400 font-bold">Pro vytvoření nového týmu jdi do <a href="/teams/new" class="text-blue-500 underline">Týmového Manažera</a> a pak se vrať na tento odkaz.</p></div></div>
</div>"""

INVITE_HTML = """<div class="max-w-xl mx-auto py-8 sm:py-12 px-4 w-full flex flex-col items-center">
    <div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">
        <div class="hero-card inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden rounded-[1.5rem] border border-white/5">
            <div class="hero-media w-full border-b border-white/10 h-32 sm:h-40 relative bg-slate-950 flex items-center justify-center">
                <img src="{{ web_graphic }}" class="w-full h-full object-cover opacity-80" alt="Grafika">
                <div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div>
            </div>
            <div class="hero-copy p-4 sm:p-5 relative z-10 -mt-6">
                <h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none text-white drop-shadow-md mb-2">Pozvánka</h2>
                <p class="text-[10px] sm:text-xs text-slate-400 flex items-center justify-center gap-2 font-bold"><i data-lucide="qr-code" class="w-3.5 h-3.5 text-blue-500"></i> {{ t_name }}</p>
            </div>
        </div>
    </div>
    <div class="bg-white p-4 sm:p-6 inline-block rounded-[2rem] sm:rounded-[3rem] shadow-2xl mb-8 border-4 border-blue-500/20 relative"><canvas id="qr-canvas"></canvas></div><div class="w-full navy-card p-4 sm:p-6 mb-8 relative border border-blue-500/20 shadow-xl"><p class="text-[9px] text-blue-400 uppercase font-black mb-3 tracking-widest">Přístupový odkaz pro hráče</p><div class="flex gap-2 items-center"><input type="text" id="invite-link-input" readonly value="{{ invite_url }}" class="w-full bg-slate-900/50 border border-white/5 rounded-xl p-3 sm:p-4 text-xs font-mono theme-text-main focus:outline-none"><button type="button" onclick="copyToClipboard(event)" class="bg-blue-600 hover:bg-blue-500 text-white p-3 sm:p-4 rounded-xl shadow-lg transition-all active:scale-95 shrink-0" title="Kopírovat"><i data-lucide="copy" class="w-5 h-5"></i></button></div></div><div class="w-full navy-card p-4 sm:p-6 mb-8 relative border border-white/5 shadow-xl"><p class="text-[9px] text-blue-400 uppercase font-black mb-3 tracking-widest">Přímé pozvání uživatele / hráče</p><form action="/tournament/{{ t_id }}/invite_user" method="POST" class="flex gap-2"><input type="text" name="username" required placeholder="Uživatelské jméno hráče" class="w-full bg-slate-900/50 border border-white/5 rounded-xl p-3 sm:p-4 text-xs font-bold theme-text-main focus:outline-none"><button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white px-4 rounded-xl font-black uppercase text-[10px] tracking-widest shrink-0">Pozvat</button></form>{% if invited_players %}<div class="mt-4 pt-4 border-t border-white/5 space-y-2"><p class="text-[8px] text-slate-500 uppercase font-black tracking-widest">Stav odeslaných pozvánek</p>{% for p in invited_players %}<div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-white/5 text-[10px]"><span class="font-bold theme-text-main uppercase">{{ p.username }}</span><span class="px-2 py-0.5 rounded text-[8px] font-black uppercase {% if p.status == 'pending' %}bg-orange-500/10 text-orange-400 border border-orange-500/20{% else %}bg-green-500/10 text-green-400 border border-green-500/20{% endif %}">{{ p.status }}</span></div>{% endfor %}</div>{% endif %}</div><div class="flex flex-col sm:flex-row gap-3 w-full"><button type="button" onclick="shareLink()" class="flex-1 bg-green-600 hover:bg-green-500 text-white py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs shadow-lg flex items-center justify-center gap-2 transition-all active:scale-95 tracking-widest"><i data-lucide="share-2" class="w-4 h-4"></i>'] Sdílet</button><a href="/tournament/{{ t_id }}" class="flex-1 bg-slate-800 hover:bg-slate-700 text-white py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs shadow-lg flex items-center justify-center gap-2 transition-all theme-text-main border border-white/5 tracking-widest"><i data-lucide="arrow-left" class="w-4 h-4"></i> Zpět</a></div>
    <script>setTimeout(() => { new QRious({element: document.getElementById('qr-canvas'), value: '{{ invite_url }}', size: window.innerWidth < 400 ? 200 : 260, padding: 15, level: 'H', foreground: '#0f172a'}); }, 100); function copyToClipboard(e) { var copyText = document.getElementById("invite-link-input"); copyText.select(); copyText.setSelectionRange(0, 99999); navigator.clipboard.writeText(copyText.value).then(() => { const btn = e.currentTarget; const origHtml = btn.innerHTML; btn.innerHTML = '<i data-lucide="check" class="w-5 h-5"></i>'; lucide.createIcons(); setTimeout(() => { btn.innerHTML = origHtml; lucide.createIcons(); }, 2000); }).catch(() => alert('Zkopírujte odkaz manuálně')); } function shareLink() { if (navigator.share) { navigator.share({ title: 'THE CUP', text: 'Připoj se se svým týmem do turnaje {{ t_name }}!', url: '{{ invite_url }}', }).catch(console.error); } else { copyToClipboard({currentTarget: document.querySelector('button[title="Kopírovat"]')}); } }</script>
</div>"""

TEAM_EDIT_HTML = """<div class="max-w-xl mx-auto py-6"><div class="flex gap-3 items-center mb-6"><a href="/teams" class="text-slate-500 p-2 -ml-2 hover:bg-white/5 rounded-lg"><i data-lucide="arrow-left"></i></a><h2 class="text-3xl font-black italic uppercase tracking-tighter theme-text-main">Editace</h2></div><div class="navy-card p-6"><div class="flex items-center gap-6 mb-8 bg-slate-900/50 p-4 rounded-2xl border border-white/5"><div class="w-24 h-24 rounded-2xl flex items-center justify-center text-4xl shadow-2xl cursor-pointer hover:scale-105 transition-transform" style="background-color: {{ team.color }}" onclick="openLogoModal('{{ team.logo }}', '{{ team.color }}')">{% if team.logo and 'static' in team.logo %}<img src="{{ team.logo }}" class="w-full h-full object-contain p-2">{% else %}{{ team.logo }}{% endif %}</div><div><h3 class="text-2xl font-black uppercase theme-text-main leading-tight">{{ team.name }}</h3><p class="text-yellow-500 font-black text-sm uppercase tracking-widest mt-1">ELO: {{ team.elo }}</p></div></div><form method="POST" action="/teams/edit/{{ team.id }}" class="space-y-5"><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Jméno</label><input type="text" name="name" value="{{ team.name }}" class="w-full p-4 rounded-xl font-bold bg-slate-900/50 text-white border border-white/10 mt-1" {{ 'disabled' if active }}></div><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Tag (Zkratka)</label><input type="text" name="tag" value="{{ team.tag if team.tag else '' }}" maxlength="4" class="w-full p-4 rounded-xl font-bold bg-slate-900/50 text-white border border-white/10 mt-1 uppercase" {{ 'disabled' if active }}></div><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Barva pozadí</label><input type="color" name="color" value="{{ team.color }}" class="w-full h-12 rounded-xl border border-white/10 mt-1" {{ 'disabled' if active }}></div>{% if not active %}<button type="submit" class="w-full bg-blue-600 text-white p-5 rounded-xl font-black uppercase text-xs tracking-widest shadow-xl shadow-blue-900/40">Uložit změny</button>{% endif %}</form><div class="mt-6 border-t border-white/5 pt-6">{% if not active %}<form action="/teams/delete/{{ team.id }}" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu smazat tento tým?', this);"><button type="submit" class="w-full bg-slate-800 text-red-500 p-4 rounded-xl font-black uppercase text-[10px] border border-red-500/20">Odstranit tým</button></form>{% else %}<p class="text-[10px] text-red-500 font-bold uppercase text-center"><i data-lucide="lock" class="w-3 h-3 inline"></i> Blokováno - tým je v turnaji</p>{% endif %}</div></div></div>"""

CHAT_HTML = """<div class="max-w-xl mx-auto w-full flex flex-col h-[75vh]"><div class="flex items-center justify-between mb-4"><h2 class="text-xl font-black italic uppercase tracking-tighter text-blue-500">Zápasový Chat</h2></div><div class="navy-card p-4 shadow-2xl border border-white/5 flex-1 overflow-y-auto mb-4 flex flex-col gap-3" id="chat-box">{% for c in comments %}<div class="{% if c.username == current_user.username %}self-end bg-blue-600/10 border-blue-500/30 text-blue-200{% else %}self-start bg-slate-800/40 border-white/5 text-slate-300{% endif %} border p-3 rounded-2xl max-w-[85%] text-xs font-bold"><p class="text-[8px] font-black uppercase tracking-widest opacity-50 mb-1">{{ c.username }} • {{ c.created_at[-8:-3] }}</p><p class="text-sm font-bold">{{ c.text }}</p></div>{% endfor %}</div><form method="POST" class="flex gap-2"><input type="text" name="text" required placeholder="Napiš zprávu..." class="w-full rounded-xl p-4 text-sm font-bold bg-slate-900/50 text-white border border-white/5"><button class="bg-blue-600 px-6 rounded-xl text-white font-black"><i data-lucide="send" class="w-4 h-4"></i></button></form></div><script>window.onload = function() { var b = document.getElementById('chat-box'); b.scrollTop = b.scrollHeight; };</script>"""
# <<< AI_BLOCK:TEMPLATES_VIEWS

# >>> AI_BLOCK:SERVICES_AI_HELPERS
def load_meta():
    import os, json
    if not os.path.exists(META_FILE): return []
    try:
        with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def add_meta(filename, team_name, mode, prompt, label=""):
    import json
    from datetime import datetime
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
    import os, requests
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("API klíč PIXAZO_API_KEY nenalezen na serveru.")
    payload = {"prompt": prompt, "num_steps": int(steps), "height": int(height), "width": int(width)}
    try:
        r = requests.post("https://gateway.pixazo.ai/flux-1-schnell/v1/getData", headers={"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": api_key}, json=payload, timeout=180)
        if r.status_code != 200: raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
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
        if not urls: raise RuntimeError(f"API_PAYLOAD_DEBUG: {data}")
        return urls
    except Exception as e: raise RuntimeError(str(e))

def save_url(url):
    import uuid, requests, os
    fn = f"{uuid.uuid4().hex}.png"; r = requests.get(url, timeout=180); r.raise_for_status()
    with open(os.path.join(LOGO_DIR, fn), "wb") as f: f.write(r.content)
    return fn

def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image, ImageDraw
    def remove_white_bg_flood(img):
        ImageDraw.floodfill(img, (0, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (0, img.height-1), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, img.height-1), (255, 255, 255, 0), thresh=40)
        return img

    def remove_all_white(img):
        datas = img.getdata(); newData = []
        for item in datas:
            r, g, b, a = item
            if r > 230 and g > 230 and b > 230: newData.append((255, 255, 255, 0))
            else: newData.append(item)
        img.putdata(newData)
        return img

    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_logo = remove_white_bg_flood(img_logo)
    img_logo.thumbnail((900, 900), Image.LANCZOS)
    
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    img_text = remove_all_white(img_text)
    bbox = img_text.getbbox()
    if bbox: img_text = img_text.crop(bbox)
    
    text_w = 850
    text_h = int(text_w * (img_text.height / img_text.width))
    img_text = img_text.resize((text_w, text_h), Image.LANCZOS)
    
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    logo_x = (1024 - img_logo.width) // 2
    logo_y = 20
    canvas.paste(img_logo, (logo_x, logo_y), img_logo)
    
    text_x = (1024 - img_text.width) // 2
    text_y = 1024 - img_text.height - 40
    canvas.paste(img_text, (text_x, text_y), img_text)
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name

def build_logo_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"Esports team mascot graphic. Concept: {mascot} (can be animal, warrior, entity, or object). Style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. STRICTLY NO TEXT, NO LETTERS. Centered, solid bold outlines. Blank solid white background."

def build_text_prompt(team_name, style, colors):
    return f"Esports team typography logo. The exact word '{team_name}' in bold, thick, aggressive 3D esports font. Placed on a solid curved badge or banner background. Colors: {colors}. STRICTLY NO MASCOTS, NO ANIMALS, ONLY THE TEXT. Blank solid white background."
# <<< AI_BLOCK:SERVICES_AI_HELPERS


# >>> AI_BLOCK:SERVICES_RUNTIME
def get_current_user():
    if 'user_id' not in session:
        return None
    return get_db().execute(
        'SELECT * FROM users WHERE id = ?',
        (session.get('user_id'),),
    ).fetchone()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            session['next_url'] = request.url
            flash("Vyžadována autorizace.")
            return redirect(url_for('account'))
        return f(*args, **kwargs)

    return decorated_function


def log_match_action(m_id, action):
    user = get_current_user()
    username = user['username'] if user else "Systém"
    with get_db() as conn:
        conn.execute(
            'INSERT INTO match_logs (m_id, username, action, created_at) VALUES (?, ?, ?, ?)',
            (m_id, username, action, datetime.now().strftime("%d.%m. %H:%M:%S")),
        )
        conn.commit()


def get_local_ip():
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        if sock is not None:
            sock.close()


def format_date_cz(date_str):
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').strftime('%d.%m.%Y')
    except (TypeError, ValueError):
        return date_str
# <<< AI_BLOCK:SERVICES_RUNTIME


# >>> AI_BLOCK:SERVICES_CORE
def render_ui(html_content, active_page='home', hide_nav=False, **kwargs):
    kwargs.update({
        'html': html_content,
        'active_page': active_page,
        'hide_nav': hide_nav,
        'current_user': get_current_user(),
        'host_url': request.host_url,
        'styles': STYLES,
        'logo': LOGO_PATH,
        'web_graphic': WEB_GRAPHIC_PATH,
        'format_date_cz': format_date_cz
    })
    return render_template_string(BASE_UI.replace('CONTENT_PLACEHOLDER', html_content), **kwargs)
# <<< AI_BLOCK:SERVICES_CORE

# >>> AI_BLOCK:SERVICES_TOURNAMENT
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
# <<< AI_BLOCK:SERVICES_TOURNAMENT

# >>> AI_BLOCK:SERVICES_MATCH
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
# <<< AI_BLOCK:SERVICES_MATCH

# >>> AI_BLOCK:SERVICES_AI
@app.route('/api/v1/teams/generate_two_phase', methods=['POST'])
@login_required
def api_generate_two_phase():
    user = get_current_user()
    if not user['is_pro']: return jsonify({'error': 'Funkce vyžaduje licenci PRO Premium.'}), 403
    
    team_name = request.form.get('team_name')
    prompt_logo = request.form.get('prompt_logo')
    prompt_text = request.form.get('prompt_text')
    
    if not team_name or not prompt_logo or not prompt_text:
        return jsonify({'error': 'Neplatná payload data.'}), 400
        
    try:
        urls_logo = pixazo_generate(prompt_logo)
        file_logo = save_url(urls_logo[0])
        
        urls_text = pixazo_generate(prompt_text)
        file_text = save_url(urls_text[0])
        
        fn = compose_two_phases(file_logo, file_text)
        add_meta(fn, team_name, "TWO_PHASE", f"Logo: {prompt_logo}")
        
        return jsonify({'status': 'success', 'logo_url': f"/static/generated_logos/{fn}"})
    except Exception as e:
        return jsonify({'error': pixazo_error(e)}), 500
# <<< AI_BLOCK:SERVICES_AI

# >>> AI_BLOCK:ROUTES_PWA
@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException): return e
    import traceback
    return f"<div style='background:#0f172a;color:#ef4444;padding:2rem;font-family:monospace;white-space:pre-wrap;line-height:1.5;margin:1rem;border-radius:1rem;border:2px solid #ef4444;'><h2>Kritická chyba uzlu THE CUP</h2><hr><br>{traceback.format_exc()}</div>", 500

@app.route('/manifest.json')
def manifest():
    return jsonify({"name": "THE CUP Enterprise", "short_name": "THE CUP", "start_url": "/", "display": "standalone", "background_color": "#020617", "theme_color": "#020617"})

@app.route('/sw.js')
def service_worker():
    return Response("self.addEventListener('fetch', function(event) {});", mimetype='application/javascript')
# <<< AI_BLOCK:ROUTES_PWA

# >>> AI_BLOCK:ROUTES_AUTH
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

@app.route('/account')
def account(): return render_ui(ACCOUNT_HTML, host_url=f"http://{get_local_ip()}:5000", active_page='account')

@app.route('/export/db')
@login_required
def export_db():
    return send_file(DB_PATH, as_attachment=True, download_name='the_cup_zaloha.db')

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

@app.route('/upgrade_pro', methods=['POST'])
@login_required
def upgrade_pro():
    with get_db() as conn: conn.execute('UPDATE users SET is_pro = 1 WHERE id = ?', (session['user_id'],)); conn.commit()
    flash("Modul PRO Premium byl aktivován."); return redirect(url_for('account'))
# <<< AI_BLOCK:ROUTES_AUTH

# >>> AI_BLOCK:ROUTES_TEAMS
@app.route('/teams')
@login_required
def teams(): return render_ui(TEAMS_HTML, master_teams=get_db().execute('SELECT * FROM master_teams WHERE user_id = ? ORDER BY id DESC', (session['user_id'],)).fetchall(), active_page='teams')

@app.route('/teams/new', methods=['GET', 'POST'])
@login_required
def new_team():
    user = get_current_user()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        tag = request.form.get("tag", "").strip().upper()
        main_color = request.form.get("color", "#3b82f6")
        logo_type = request.form.get("logo_type", "emoji")
        
        if not name:
            flash("Název týmu je vyžadován.")
            return redirect(url_for("new_team"))
            
        if logo_type == "ai":
            logo_val = request.form.get("final_ai_logo")
            if not logo_val:
                flash("Chyba: Nebylo obdrženo žádné vygenerované AI logo z API.")
                return redirect(url_for("new_team"))
        else:
            logo_val = request.form.get("emoji_logo", "⚽")
            
        try:
            with get_db() as conn:
                conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (?, ?, ?, ?, ?)', 
                             (session['user_id'], name, logo_val, main_color, tag))
                conn.commit()
            flash(f"Tým {name} byl úspěšně zapsán do registru.")
            return redirect(url_for('teams'))
        except sqlite3.IntegrityError:
            flash("Tento tým je již v registru zapsán.")
            return redirect(url_for("new_team"))

    return render_ui(TEAM_NEW_HTML, styles=STYLES, active_page='teams')

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
# <<< AI_BLOCK:ROUTES_TEAMS

# >>> AI_BLOCK:ROUTES_TOURNAMENTS
@app.route('/export/csv/<int:t_id>')
@login_required
def export_csv(t_id):
    standings = get_standings(t_id)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Poradi', 'Tym', 'Zapasu', 'Vyhry', 'Remizy', 'Prohry', 'Skore', 'Golovy_rozdil', 'Body'])
    for position, standing in enumerate(standings, 1):
        writer.writerow([
            position,
            standing['name'],
            standing['gp'],
            standing['w'],
            standing['d'],
            standing['l'],
            f"{standing['gf']}:{standing['ga']}",
            standing['gd'],
            standing['pts'],
        ])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment;filename=tabulka_turnaje_{t_id}.csv'},
    )

def auto_start_tournaments():
    try:
        with get_db() as conn:
            from datetime import datetime
            today = datetime.now().strftime('%Y-%m-%d')
            due = conn.execute('SELECT id, format, rounds, group_count FROM tournaments WHERE status = "draft" AND start_date <= ?', (today,)).fetchall()
            if not due: return
            for t_data in due:
                t_id = t_data['id']
                t_list = [t['id'] for t in conn.execute('SELECT id FROM teams WHERE t_id = ?', (t_id,)).fetchall()]
                if len(t_list) < 2: continue
                import random
                random.shuffle(t_list)
                if t_data['format'] == 'knockout':
                    for i in range(0, len(t_list), 2):
                        if i+1 < len(t_list): conn.execute('INSERT INTO matches (t_id, team1_id, team2_id, stage, round_num) VALUES (?, ?, ?, "playoffs", 1)', (t_id, t_list[i], t_list[i+1]))
                    conn.execute('UPDATE tournaments SET status = "active", stage = "playoffs" WHERE id = ?', (t_id,))
                else:
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
                    conn.execute('UPDATE tournaments SET status = "active", stage = "groups" WHERE id = ?', (t_id,))
            conn.commit()
    except Exception as e: pass

@app.route('/')
def index():
    auto_start_tournaments()
    if 'user_id' not in session: return render_ui(WELCOME_HTML, active_page='home', hide_nav=True)
    uid = session['user_id']
    active_tourneys = get_db().execute('SELECT *, (SELECT COUNT(*) FROM teams WHERE t_id = tournaments.id) as registered_teams FROM tournaments WHERE user_id = ? AND status != "finished" ORDER BY start_date ASC', (uid,)).fetchall()
    participating_tourneys = get_db().execute('SELECT DISTINCT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id JOIN teams t ON t.t_id = tr.id JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ? AND tr.user_id != ? AND tr.status != "finished" ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    joinable_public_tourneys = get_db().execute('SELECT tr.*, u.username, (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) as registered_teams FROM tournaments tr JOIN users u ON tr.user_id = u.id WHERE tr.is_public = 1 AND tr.status = "draft" AND tr.user_id != ? AND tr.id NOT IN (SELECT t.t_id FROM teams t JOIN master_teams mt ON t.master_id = mt.id WHERE mt.user_id = ?) AND (SELECT COUNT(*) FROM teams WHERE t_id = tr.id) < tr.max_teams ORDER BY tr.start_date ASC', (uid, uid)).fetchall()
    stats = {'total_tournaments': len(active_tourneys), 'total_teams': get_db().execute('SELECT COUNT(*) FROM master_teams WHERE user_id = ?', (uid,)).fetchone()[0]}
    next_match = get_db().execute('SELECT m.*, t1.name as t1_name, t1.logo as t1_logo, t1.color as t1_color, t2.name as t2_name, t2.logo as t2_logo, t2.color as t2_color, tr.name as tr_name FROM matches m JOIN teams t1 ON m.team1_id = t1.id JOIN master_teams mt1 ON t1.master_id = mt1.id JOIN teams t2 ON m.team2_id = t2.id JOIN master_teams mt2 ON t2.master_id = mt2.id JOIN tournaments tr ON m.t_id = tr.id WHERE m.status != "finished" AND tr.status = "active" AND (mt1.user_id = ? OR mt2.user_id = ?) ORDER BY m.round_num ASC, m.id ASC LIMIT 1', (uid, uid)).fetchone()
    invitations = get_db().execute('SELECT ti.*, t.name as t_name, t.join_token FROM tournament_invitations ti JOIN tournaments t ON ti.t_id = t.id WHERE ti.user_id = ? AND ti.status = "pending"', (uid,)).fetchall()
    return render_ui(INDEX_HTML, active_tourneys=active_tourneys, participating_tourneys=participating_tourneys, joinable_public_tourneys=joinable_public_tourneys, stats=stats, next_match=next_match, invitations=invitations, active_page='home')

@app.route('/seasons')
@login_required
def seasons():
    auto_start_tournaments()
    return render_ui(SEASONS_HTML, tournaments=get_db().execute('SELECT t.*, (SELECT COUNT(*) FROM teams WHERE t_id = t.id) as registered_teams FROM tournaments t WHERE t.user_id = ? ORDER BY t.start_date DESC', (session['user_id'],)).fetchall(), active_page='seasons')

@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    user = get_current_user()
    if request.method == 'POST':
        if int(request.form['max_teams']) < 2: flash("Minimálně 2 týmy pro inicializaci struktury."); return redirect(url_for('create'))
        name = request.form['name'].strip()
        start_date = request.form['start_date']
        is_public = int(request.form['is_public'])
        max_teams = int(request.form['max_teams'])
        rounds = int(request.form.get('rounds', 1))
        group_count = int(request.form.get('group_count', 1))
        t_format = request.form.get('format', 'groups')
        banner_type = request.form.get('banner_type', 'standard')
        banner_val = None
        if banner_type == 'ai':
            if not user['is_pro']: flash("AI Banner vyžaduje PRO Premium."); return redirect(url_for('create'))
            try:
                prompt = f"Epic professional sports championship tournament wide landscape banner graphics for '{name}'. Dark navy blue background, modern tech aesthetics, luxury premium geometric glowing neon esports lines, elegant styling, championship cup trophy concept artwork. Strictly spelling '{name}'."
                urls = pixazo_generate(prompt, width=1024, height=512)
                fn = save_url(urls[0])
                banner_val = f"/static/generated_logos/{fn}"
            except Exception as e: flash(pixazo_error(e)); return redirect(url_for('create'))
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO tournaments (user_id, name, start_date, is_public, max_teams, join_token, rounds, stage, group_count, format, banner) VALUES (?, ?, ?, ?, ?, ?, ?, "groups", ?, ?, ?)',
                        (session['user_id'], name, start_date, is_public, max_teams, uuid.uuid4().hex[:12], rounds, group_count, t_format, banner_val))
            new_id = cur.lastrowid
            conn.commit()
        flash("Turnaj úspěšně vytvořen.")
        return redirect(url_for('tournament_detail', t_id=new_id))
    return render_ui(CREATE_HTML, active_page='create')

@app.route('/tournament/<int:t_id>')
@login_required
def tournament_detail(t_id):
    auto_start_tournaments()
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
    is_knockout_only = t['format'] == 'knockout'
    has_playoffs = t['stage'] == 'playoffs' or len([m for m in matches if m['stage'] == 'playoffs']) > 0
    playoff_matches = [m for m in matches if m['stage'] == 'playoffs']
    return render_ui(DETAIL_UI, tournament=t, teams=teams, matches=matches, group_matches=group_matches, playoff_matches=playoff_matches, standings=standings, master_teams=master_teams, all_finished=all_finished, active_page='seasons', check_admin=check_admin, logs=logs_dict, my_team_ids=my_team_ids, podium=podium, preds=preds, is_knockout_only=is_knockout_only, has_playoffs=has_playoffs)

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
    
    is_knockout_only = tournament['format'] == 'knockout'
    has_playoffs = tournament['stage'] == 'playoffs' or len([m for m in matches if m['stage'] == 'playoffs']) > 0
    playoff_matches = [m for m in matches if m['stage'] == 'playoffs']
    group_matches = [m for m in matches if m['stage'] == 'groups']
    
    html = "<script>document.addEventListener('DOMContentLoaded', () => { let views = document.querySelectorAll('.view-carousel'); if(views.length === 0) return; let i = 0; setInterval(() => { views.forEach(v => v.classList.add('hidden')); views[i].classList.remove('hidden'); i = (i + 1) % views.length; }, 10000); });</script><meta http-equiv='refresh' content='40'>" + DETAIL_UI
    return render_ui(html, tournament=tournament, teams=teams, standings=standings, matches=matches, playoff_matches=playoff_matches, group_matches=group_matches, check_admin=lambda x,y: False, hide_nav=True, logs=logs_dict, podium=podium, is_knockout_only=is_knockout_only, has_playoffs=has_playoffs)

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
                cur.execute('INSERT INTO teams (t_id, master_id, name, color, logo) VALUES (?, ?, ?, ?, ?)', (tournament['id'], m_id, name, color, logo))
                cur.execute('UPDATE tournament_invitations SET status = "accepted" WHERE t_id = ? AND user_id = ?', (tournament['id'], session['user_id']))
                conn.commit(); return redirect(url_for('success', team_id=cur.lastrowid))
        except Exception as e: flash(f"Nastala chyba: {str(e)}")
    my_teams = conn.execute('SELECT * FROM master_teams WHERE user_id = ? AND id NOT IN (SELECT master_id FROM teams WHERE t_id = ?)', (session['user_id'], tournament['id'])).fetchall()
    return render_ui(JOIN_UI, t_name=tournament['name'], t_username=tournament['username'], t_start_date=tournament['start_date'], t_id=tournament['id'], t_max_teams=tournament['max_teams'], t_registered_teams=tournament['registered_teams'], t_status=tournament['status'], my_teams=my_teams, active_page='none')

@app.route('/tournament/<int:t_id>/invite')
@login_required
def invite(t_id): 
    t = get_db().execute('SELECT name, join_token FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t: flash("Chybí odkazující data."); return redirect(url_for('seasons'))
    invite_url = f"{request.host_url}join/{t['join_token']}"
    invited_players = get_db().execute('SELECT ti.*, u.username FROM tournament_invitations ti JOIN users u ON ti.user_id = u.id WHERE ti.t_id = ? ORDER BY ti.id DESC', (t_id,)).fetchall()
    return render_ui(INVITE_HTML, invite_url=invite_url, t_id=t_id, t_name=t['name'], invited_players=invited_players, active_page='seasons')

@app.route('/tournament/<int:t_id>/invite_user', methods=['POST'])
@login_required
def invite_user_to_tournament(t_id):
    t = get_db().execute('SELECT * FROM tournaments WHERE id = ?', (t_id,)).fetchone()
    if not t or not check_admin(t, get_current_user()): flash("Přístup odepřen."); return redirect(url_for('seasons'))
    username = request.form.get('username', '').strip()
    target_user = get_db().execute('SELECT id FROM users WHERE username = ?', (username,)).fetchone()
    if not target_user: flash(f"Uživatel '{username}' nebyl v systému nalezen."); return redirect(url_for('invite', t_id=t_id))
    try:
        with get_db() as conn:
            conn.execute('INSERT INTO tournament_invitations (t_id, user_id, status) VALUES (?, ?, "pending")', (t_id, target_user['id']))
            conn.commit()
        flash(f"Pozvánka pro hráče {username} byla úspěšně odeslána.")
    except sqlite3.IntegrityError:
        flash("Tento hráč již do turnaje pozván byl.")
    return redirect(url_for('invite', t_id=t_id))

@app.route('/invitation/<int:inv_id>/decline', methods=['POST'])
@login_required
def decline_invitation(inv_id):
    user = get_current_user()
    with get_db() as conn:
        conn.execute('UPDATE tournament_invitations SET status = "declined" WHERE id = ? AND user_id = ?', (inv_id, user['id']))
        conn.commit()
    flash("Pozvánka byla odmítnuta."); return redirect(url_for('index'))

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
# <<< AI_BLOCK:ROUTES_TOURNAMENTS

# >>> AI_BLOCK:ROUTES_MATCHES
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
# <<< AI_BLOCK:ROUTES_MATCHES

# >>> AI_BLOCK:SELF_CHECK
def system_check():
    assert os.path.exists(LOGO_DIR)
    assert os.path.exists(BRAND_DIR)
    assert os.path.exists(DATA_DIR)
    assert callable(get_db)
# <<< AI_BLOCK:SELF_CHECK

# >>> AI_BLOCK:MAIN
if __name__ == '__main__':
    system_check()
    app.run(debug=True, host='0.0.0.0', port=5000)
# <<< AI_BLOCK:MAIN
