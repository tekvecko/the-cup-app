# >>> AI_BLOCK:IMPORTS
from flask import Flask, render_template_string, request, redirect, url_for, flash, session, make_response, jsonify, send_file, Response
from werkzeug.exceptions import HTTPException
import sqlite3, socket, os, uuid, time, random, io, csv, math, json, requests
from PIL import Image, ImageDraw, ImageFont
from functools import wraps, cmp_to_key
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
# <<< AI_BLOCK:IMPORTS

# >>> AI_BLOCK:CONFIG
app = Flask(__name__)
app.secret_key = 'the_cup_pro_premium_ultimate_v200_ai_safe'
DB_PATH = os.path.join(os.getcwd(), 'the_cup_v31.db')
LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
BRAND_DIR = os.path.join(os.getcwd(), 'static', 'brand')
DATA_DIR = os.path.join(os.getcwd(), 'data')
META_FILE = os.path.join(DATA_DIR, "logo_studio_images.json")

os.makedirs(LOGO_DIR, exist_ok=True)
os.makedirs(BRAND_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

STYLES = {
    "clean": "clean bright vector mascot logo, simple shapes", 
    "3d": "clean 3D polished emblem", 
    "minimal": "minimal geometric flat vector", 
    "premium": "premium professional sport emblem"
}
# <<< AI_BLOCK:CONFIG

# >>> AI_BLOCK:DATABASE
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('PRAGMA journal_mode=WAL;')
    conn.row_factory = sqlite3.Row
    return conn
# <<< AI_BLOCK:DATABASE

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
BASE_UI = """<!DOCTYPE html><html lang="cs"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0"><link rel="manifest" href="/manifest.json"><meta name="theme-color" content="#020617"><link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>🏆</text></svg>"><script src="https://cdn.tailwindcss.com"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/qrious/4.0.2/qrious.min.js"></script><script src="https://unpkg.com/lucide@latest"></script><script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script><title>THE CUP</title><style>body{background-color:#020617;color:#f8fafc;font-family:sans-serif;overflow-x:hidden}.glass{background:rgba(15,23,42,0.8);backdrop-filter:blur(20px);border-bottom:1px solid rgba(255,255,255,0.1)}.navy-card{background:#0f172a;border-radius:1.25rem;border:1px solid rgba(255,255,255,0.05);transition:all 0.2s}.bottom-nav{background:rgba(15,23,42,0.95);backdrop-filter:blur(15px);border-top:1px solid rgba(255,255,255,0.1)}.toast{background:#1e293b;border-left:4px solid #3b82f6}input,select{background:#1e293b!important;color:white!important;outline:none}body.light{background-color:#f8fafc;color:#0f172a}body.light .glass{background:rgba(255,255,255,0.85);border-bottom:1px solid rgba(0,0,0,0.05)}body.light .navy-card{background:#ffffff;border:1px solid rgba(0,0,0,0.05)}body.light input,body.light select{background:#f1f5f9!important;color:#0f172a!important}body.light .theme-text-main{color:#0f172a!important}.live-timer{animation:pulse 1s infinite}@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.5}}.table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch}</style></head><body class="min-h-screen pb-28 flex flex-col"><div id="offline-banner" class="hidden fixed top-0 left-0 right-0 bg-red-600 text-white text-[9px] font-black uppercase tracking-widest text-center py-1.5 z-[9999] shadow-lg">Jste v offline režimu - prohlížíte uložená data</div><script>if('serviceWorker' in navigator){window.addEventListener('load',()=>{navigator.serviceWorker.register('/sw.js');});}window.addEventListener('online',()=>document.getElementById('offline-banner').classList.add('hidden'));window.addEventListener('offline',()=>document.getElementById('offline-banner').classList.remove('hidden'));if(!navigator.onLine)document.getElementById('offline-banner').classList.remove('hidden');const userTheme='{{current_user.theme if current_user else "system"}}';function applyTheme(){let isLight=userTheme==='light'||(userTheme==='system'&&!window.matchMedia('(prefers-color-scheme: dark)').matches);if(isLight){document.body.classList.add('light');document.getElementById('meta-theme-color').content="#f8fafc";}else{document.body.classList.remove('light');document.getElementById('meta-theme-color').content="#020617";}}applyTheme();function vibrate(){if(navigator.vibrate)navigator.vibrate(50);}let lastNotifCount=0;</script><div id="custom-modal" class="fixed inset-0 z-[2000] flex items-center justify-center hidden opacity-0 transition-opacity duration-300"><div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="closeModal()"></div><div class="navy-card relative w-11/12 max-w-sm p-6 transform scale-95 transition-transform duration-300 shadow-2xl" id="custom-modal-content"><div class="w-16 h-16 rounded-full bg-blue-500/10 text-blue-500 flex items-center justify-center mx-auto mb-4 border border-blue-500/20"><i data-lucide="help-circle" class="w-8 h-8"></i></div><h3 class="text-xl font-black italic uppercase text-center mb-2 theme-text-main">Potvrzení</h3><p id="modal-message" class="text-xs text-slate-400 text-center mb-8"></p><div class="flex gap-3"><button onclick="closeModal()" type="button" class="flex-1 bg-slate-800 hover:bg-slate-700 py-4 rounded-xl font-black uppercase text-[10px] theme-text-main transition-colors">Zrušit</button><button onclick="confirmModalAction()" type="button" class="flex-1 bg-blue-600 hover:bg-blue-500 text-white py-4 rounded-xl font-black uppercase text-[10px] shadow-lg transition-colors">Potvrdit</button></div></div></div><div id="logo-modal" class="fixed inset-0 z-[4000] bg-slate-950/90 backdrop-blur-md hidden flex items-center justify-center p-4 opacity-0 transition-opacity" onclick="closeLogoModal()"><div class="relative w-full max-w-sm sm:max-w-md flex flex-col items-center justify-center" onclick="event.stopPropagation()"><button type="button" onclick="closeLogoModal()" class="absolute -top-12 right-0 sm:-right-8 text-slate-400 hover:text-white"><i data-lucide="x" class="w-8 h-8"></i></button><div id="logo-modal-content" class="w-64 h-64 sm:w-80 sm:h-80 rounded-full flex items-center justify-center shadow-2xl border-4 border-white/10 overflow-hidden" style="background-color: #0f172a;"></div></div></div><div id="toast-container" class="fixed top-24 right-4 left-4 md:left-auto md:w-80 z-[1000] space-y-2 pointer-events-none">{% with messages=get_flashed_messages() %}{% if messages %}{% for message in messages %}<div class="toast flex items-center justify-between p-4 rounded-xl shadow-2xl"><div class="flex items-center gap-3"><i data-lucide="bell" class="w-4 h-4 text-blue-500 shrink-0"></i><span class="text-xs font-bold">{{ message }}</span></div><button onclick="this.parentElement.remove()" class="text-slate-500 font-bold p-2 shrink-0">&times;</button></div>{% endfor %}{% endif %}{% endwith %}</div>{% if not hide_nav %}<div class="fixed top-0 left-0 right-0 z-50 flex justify-center pointer-events-none mt-4"><nav id="main-nav-tab" class="glass px-10 py-2.5 rounded-[2rem] border border-white/10 shadow-2xl pointer-events-auto flex flex-col items-center"><span class="uppercase tracking-tighter font-black italic text-blue-500 text-xl drop-shadow-md">THE CUP</span></nav></div>{% endif %}<main class="w-full max-w-[1400px] mx-auto px-3 {% if not hide_nav %}pt-24{% endif %} mt-2 flex-1 flex flex-col" id="main-content">CONTENT_PLACEHOLDER</main>{% if not hide_nav %}<div class="fixed bottom-0 left-0 right-0 bottom-nav z-50 p-2"><div class="flex justify-between items-center max-w-lg mx-auto"><a href="/" onclick="vibrate()" class="flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='home' }}"><i data-lucide="home"></i><span class="text-[8px] font-bold uppercase">Domů</span></a>{% if current_user %}<a href="/teams" onclick="vibrate()" class="flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='teams' }}"><i data-lucide="users"></i><span class="text-[8px] font-bold uppercase">Týmy</span></a><a href="/create" onclick="vibrate()" class="bg-blue-600 w-10 h-10 flex items-center justify-center rounded-2xl shadow-xl -mt-6 border-4 border-slate-950 active:scale-90"><i data-lucide="plus" class="text-white"></i></a><a href="/seasons" onclick="vibrate()" class="flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='seasons' }}"><i data-lucide="trophy"></i><span class="text-[8px] font-bold uppercase">Turnaje</span></a>{% endif %}<a href="/hof" onclick="vibrate()" class="flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='hof' }}"><i data-lucide="star"></i><span class="text-[8px] font-bold uppercase">Sláva</span></a><a href="/account" onclick="vibrate()" class="flex flex-col items-center gap-1 opacity-60 {{ 'text-blue-500 opacity-100' if active_page=='account' }}"><i data-lucide="user"></i><span class="text-[8px] font-bold uppercase">Účet</span></a></div></div>{% endif %}<script>lucide.createIcons();let pendingForm=null;function openLogoModal(content,bgColor){const modal=document.getElementById('logo-modal');const container=document.getElementById('logo-modal-content');container.style.backgroundColor=bgColor;if(content.includes('static/')){container.innerHTML='<img src="'+content+'" class="w-full h-full object-contain p-6">';}else{container.innerHTML='<span class="drop-shadow-xl text-7xl sm:text-9xl">'+content+'</span>';}modal.classList.remove('hidden');void modal.offsetWidth;modal.classList.remove('opacity-0');}function closeLogoModal(){const modal=document.getElementById('logo-modal');modal.classList.add('opacity-0');setTimeout(()=>modal.classList.add('hidden'),300);}function openModal(message,form){document.getElementById('modal-message').innerText=message;pendingForm=form;const modal=document.getElementById('custom-modal');modal.classList.remove('hidden');void modal.offsetWidth;modal.classList.remove('opacity-0');vibrate();}function closeModal(){const modal=document.getElementById('custom-modal');modal.classList.add('opacity-0');setTimeout(()=>{modal.classList.add('hidden');pendingForm=null;},300);}function confirmModalAction(){if(pendingForm)pendingForm.submit();closeModal();vibrate();}document.addEventListener('DOMContentLoaded',()=>{const toasts=document.querySelectorAll('.toast');toasts.forEach(toast=>{setTimeout(()=>{toast.classList.add('hide');setTimeout(()=>toast.remove(),500);},5000);});});function exportImage(elementId){const btn=document.getElementById('export-btn');const origHtml=btn.innerHTML;btn.innerHTML='<i data-lucide="loader" class="w-4 h-4 animate-spin"></i>';lucide.createIcons();setTimeout(()=>{html2canvas(document.getElementById(elementId),{backgroundColor:userTheme==='light'?'#f8fafc':'#020617',scale:2}).then(canvas=>{let a=document.createElement('a');a.href=canvas.toDataURL("image/jpeg");a.download='the_cup_export.jpg';a.click();btn.innerHTML=origHtml;lucide.createIcons();vibrate();});},200);}setInterval(()=>{document.querySelectorAll('.live-timer').forEach(el=>{let start=parseInt(el.dataset.start);if(start>0){let diff=Math.floor(Date.now()/1000)-start;if(diff<0)diff=0;let m=Math.floor(diff/60).toString().padStart(2,'0');let s=(diff%60).toString().padStart(2,'0');el.innerText=`${m}:${s}`;}});},1000);let touchstartX=0;let touchendX=0;document.getElementById('swipe-area').addEventListener('touchstart',e=>{touchstartX=e.changedTouches[0].screenX;},{passive:true});document.getElementById('swipe-area').addEventListener('touchend',e=>{touchendX=e.changedTouches[0].screenX;handleSwipe();},{passive:true});function handleSwipe(){if(!document.getElementById('tab-playoffs'))return;let diff=touchstartX-touchendX;if(diff>60){if(!document.getElementById('content-playoffs').classList.contains('hidden')===false){switchTab('playoffs');vibrate();}}else if(diff<-60){if(!document.getElementById('content-groups').classList.contains('hidden')===false){switchTab('groups');vibrate();}}}</script></body></html>"""
# <<< AI_BLOCK:TEMPLATES_BASE

# >>> AI_BLOCK:TEMPLATES_MACROS
MATCH_MACRO = """{% macro render_match(m, is_admin, current_user, logs_dict={}, pred=None) %}{% set is_t1 = current_user and m.t1_user_id == current_user.id %}{% set is_t2 = current_user and m.t2_user_id == current_user.id %}{% set is_participant = is_t1 or is_t2 %}{% set my_team_id = m.team1_id if is_t1 else (m.team2_id if is_t2 else 0) %}<div class="match-card navy-card p-4 sm:p-5 border-white/5 shadow-lg relative overflow-hidden flex flex-col justify-between h-full" data-round="{{ m.round_num }}" data-team1="{{ m.team1_id }}" data-team2="{{ m.team2_id }}" data-stage="{{ m.stage }}">{% if m.stage == 'playoffs' %}<span class="absolute top-0 right-0 bg-blue-600 text-white text-[7px] font-black px-2 py-1 rounded-bl-xl tracking-widest uppercase">Playoff</span>{% endif %}{% if m.is_ot == 1 %}<span class="absolute top-0 left-0 bg-orange-600 text-white text-[7px] font-black px-2 py-1 rounded-br-xl tracking-widest uppercase">PP/SN</span>{% elif m.is_ot == 2 %}<span class="absolute top-0 left-0 bg-red-600 text-white text-[7px] font-black px-2 py-1 rounded-br-xl tracking-widest uppercase">Kontumace</span>{% endif %}<div class="flex justify-between items-start mb-2 px-1"><div class="text-[8px] text-slate-500 font-bold uppercase tracking-widest flex items-center gap-2">{% if m.stage == 'groups' %}KOLO {{ m.round_num }}{% endif %} {% if m.match_time %}<span class="flex items-center gap-1"><i data-lucide="clock" class="w-3 h-3"></i> {{ m.match_time }}</span>{% endif %} {% if m.pitch %}<span class="flex items-center gap-1"><i data-lucide="flag" class="w-3 h-3"></i> {{ m.pitch }}</span>{% endif %}{% if m.started_at %}<span class="live-timer text-red-500 animate-pulse font-mono ml-1" data-start="{{ m.started_at }}">00:00</span>{% endif %}</div><div class="flex gap-1.5 shrink-0">{% if m.status == 'planned' and is_admin and not m.started_at %}<form action="/match/{{ m.id }}/start_timer" method="POST" onsubmit="vibrate()"><button class="text-green-500 hover:text-green-400 p-1" title="Odstartovat čas"><i data-lucide="timer" class="w-4 h-4"></i></button></form>{% endif %}<button type="button" onclick="document.getElementById('log-{{ m.id }}').classList.toggle('hidden')" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="history" class="w-4 h-4"></i></button><a href="/match/{{ m.id }}/chat" class="text-blue-500 hover:text-blue-400 p-1"><i data-lucide="message-square-text" class="w-4 h-4"></i></a> {% if is_admin %}<button type="button" onclick="document.getElementById('sched-{{ m.id }}').classList.toggle('hidden')" class="text-slate-500 hover:text-slate-300 p-1"><i data-lucide="calendar-cog" class="w-4 h-4"></i></button>{% endif %}</div></div><div id="log-{{ m.id }}" class="hidden mb-3 bg-slate-900/80 p-2.5 rounded-xl border border-white/5 space-y-1.5 max-h-32 overflow-y-auto"><h4 class="text-[8px] font-black uppercase text-blue-500 tracking-widest mb-1 border-b border-white/10 pb-1">Historie zápasu</h4>{% if m.id in logs_dict and logs_dict[m.id] %}{% for log in logs_dict[m.id] %}<p class="text-[8px] theme-text-main"><span class="opacity-50 font-mono mr-1">{{ log.created_at[-8:-3] }}</span> <span class="font-bold text-blue-400 mr-1">{{ log.username }}:</span> {{ log.action }}</p>{% endfor %}{% else %}<p class="text-[8px] text-slate-500 italic">Zatím žádné záznamy.</p>{% endif %}</div><form id="sched-{{ m.id }}" action="/match/{{ m.id }}/schedule" method="POST" class="hidden mb-4 bg-slate-900/50 p-2 rounded-xl border border-white/5 flex gap-1"><input type="time" name="time" value="{{ m.match_time }}" class="w-full rounded p-1 text-[10px] theme-text-main bg-transparent"><input type="text" name="pitch" placeholder="Hřiště" value="{{ m.pitch }}" class="w-full rounded p-1 text-[10px] theme-text-main bg-transparent"><button class="bg-blue-600 px-2 rounded text-white"><i data-lucide="check" class="w-3 h-3"></i></button></form><div class="grid grid-cols-3 items-center text-center w-full my-auto"><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ m.t1_color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{m.t1_logo}}', '{{m.t1_color}}')"><span class="text-xl sm:text-2xl drop-shadow-md">{% if m.t1_logo and 'static' in m.t1_logo %}<img src="{{m.t1_logo}}" class="w-full h-full object-contain p-1">{% else %}{{m.t1_logo}}{% endif %}</span></div><p class="text-[8px] sm:text-[9px] font-black uppercase truncate w-full theme-text-main">{{ m.t1_name }}</p></div><div class="text-2xl sm:text-3xl font-black italic tracking-tighter theme-text-main">{% if m.status == 'finished' %}{{ m.score1 }}:{{ m.score2 }}{% elif m.status == 'proposed' %}<span class="text-orange-500">{{ m.proposed_score1 }}:{{ m.proposed_score2 }}</span>{% else %}-:-{% endif %}</div><div class="flex flex-col items-center gap-1.5 min-w-0"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ m.t2_color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{m.t2_logo}}', '{{m.t2_color}}')"><span class="text-xl sm:text-2xl drop-shadow-md">{% if m.t2_logo and 'static' in m.t2_logo %}<img src="{{m.t2_logo}}" class="w-full h-full object-contain p-1">{% else %}{{m.t2_logo}}{% endif %}</span></div><p class="text-[8px] sm:text-[9px] font-black uppercase truncate w-full theme-text-main">{{ m.t2_name }}</p></div></div><div class="mt-4 border-t border-white/5 pt-3">{% if m.status == 'planned' %}{% if is_participant or is_admin %}<form action="/match/{{ m.id }}/propose" method="POST" class="flex flex-col gap-2" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><input type="number" name="s2" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><button class="bg-blue-600 hover:bg-blue-500 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg"><i data-lucide="check" class="w-4 h-4"></i></button></div>{% if m.stage == 'playoffs' %}<label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center mt-1 font-bold"><input type="checkbox" name="is_ot" value="1" class="w-3 h-3"> Prodloužení / Penalty</label>{% endif %}<input type="hidden" name="team_id" value="{{ my_team_id if not is_admin else 0 }}"></form>{% if is_admin %}<div class="flex gap-2 mt-2"><form action="/match/{{ m.id }}/forfeit/{{ m.team1_id }}" method="POST" class="flex-1" onsubmit="return confirm('Kontumovat tým 1?');"><button class="w-full bg-red-900/50 hover:bg-red-800 text-red-500 py-1.5 rounded-lg text-[8px] font-black uppercase border border-red-500/20 transition-colors">Kontumace T1</button></form><form action="/match/{{ m.id }}/forfeit/{{ m.team2_id }}" method="POST" class="flex-1" onsubmit="return confirm('Kontumovat tým 2?');"><button class="w-full bg-red-900/50 hover:bg-red-800 text-red-500 py-1.5 rounded-lg text-[8px] font-black uppercase border border-red-500/20 transition-colors">Kontumace T2</button></form></div>{% endif %}{% elif current_user %}{% if not pred %}<form action="/match/{{ m.id }}/predict" method="POST" class="flex flex-col gap-1 mt-2" onsubmit="vibrate()"><span class="text-[8px] font-black uppercase text-blue-500 text-center tracking-widest mb-1">Tvoje tipovačka</span><div class="flex gap-2"><input type="number" name="p1" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><input type="number" name="p2" required class="w-full rounded-lg p-2 text-center text-xs font-black theme-text-main bg-slate-900/50"><button class="bg-slate-700 hover:bg-slate-600 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg">TIP</button></div></form>{% else %}<div class="text-center w-full mt-2"><span class="text-blue-500 text-[9px] font-black uppercase tracking-widest block bg-blue-500/10 py-1.5 rounded-lg border border-blue-500/20">Tvůj tip: {{ pred.p_score1 }} : {{ pred.p_score2 }}</span></div>{% endif %}{% else %}<div class="text-center w-full"><span class="text-slate-500 text-[9px] font-black uppercase w-full block">Neodehráno</span></div>{% endif %}{% elif m.status == 'proposed' %}{% if is_admin or (is_participant and m.proposed_by_team_id != my_team_id) %}<div class="flex flex-col gap-2 w-full"><div class="flex gap-2"><form action="/match/{{ m.id }}/approve" method="POST" class="flex-1" onsubmit="vibrate()"><button class="w-full bg-green-600 hover:bg-green-500 py-2 rounded-lg text-white font-black text-[9px] uppercase tracking-widest shadow-lg">Schválit</button></form><button type="button" onclick="document.getElementById('counter-{{ m.id }}').classList.toggle('hidden'); vibrate();" class="flex-1 bg-red-500/20 text-red-500 py-2 rounded-lg font-black text-[9px] uppercase tracking-widest hover:bg-red-500/30">Odmítnout</button></div><form id="counter-{{ m.id }}" action="/match/{{ m.id }}/propose" method="POST" class="hidden flex flex-col gap-2 mt-1" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><input type="number" name="s2" required class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><button class="bg-orange-600 hover:bg-orange-500 px-3 rounded-lg text-white font-black text-[9px] uppercase shadow-lg"><i data-lucide="check" class="w-4 h-4"></i></button></div><label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center font-bold"><input type="checkbox" name="is_ot" value="1" class="w-3 h-3"> Prodloužení / Penalty</label><input type="hidden" name="team_id" value="{{ my_team_id if not is_admin else 0 }}"></form></div>{% else %}<div class="text-center w-full"><span class="bg-orange-500/10 text-orange-500 py-2 rounded-lg text-[8px] font-black uppercase w-full block border border-orange-500/20">Čeká se na potvrzení soupeřem...</span></div>{% endif %}{% elif m.status == 'finished' and is_admin %}<div class="text-center flex justify-center gap-4"><button type="button" onclick="document.getElementById('edit-{{ m.id }}').classList.toggle('hidden')" class="text-[8px] font-black uppercase text-slate-500 hover:text-slate-300">Upravit výsledek</button><form action="/match/{{ m.id }}/reset" method="POST" onsubmit="return confirm('Opravdu vymazat výsledek a logy zápasu?');"><button type="submit" class="text-[8px] font-black uppercase text-blue-500 hover:text-blue-400">Resetovat zápas</button></form></div><form id="edit-{{ m.id }}" action="/match/{{ m.id }}/update" method="POST" class="hidden flex flex-col gap-2 mt-2" onsubmit="vibrate()"><div class="flex gap-2"><input type="number" name="s1" required value="{{ m.score1 }}" class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><input type="number" name="s2" required value="{{ m.score2 }}" class="w-full rounded-lg p-2 text-center text-xs font-black bg-slate-900/50 theme-text-main"><button class="bg-slate-700 hover:bg-slate-600 px-3 rounded-lg text-white font-black text-[9px] uppercase"><i data-lucide="check" class="w-4 h-4"></i></button></div><label class="text-[9px] text-slate-500 flex items-center gap-1.5 justify-center font-bold"><input type="checkbox" name="is_ot" value="1" {% if m.is_ot %}checked{% endif %} class="w-3 h-3"> Prodloužení / Penalty</label></form>{% endif %}</div></div>{% endmacro %}"""
# <<< AI_BLOCK:TEMPLATES_MACROS

# >>> AI_BLOCK:TEMPLATES_VIEWS
WELCOME_HTML = """<div class="relative flex-1 flex flex-col items-center justify-center text-center overflow-hidden min-h-[70vh] rounded-3xl"><div class="absolute inset-0 z-0 pointer-events-none overflow-hidden rounded-3xl"><div class="absolute top-10 left-10 w-32 sm:w-64 h-32 sm:h-64 bg-blue-600/20 rounded-full blur-3xl animate-float"></div><div class="absolute bottom-20 right-10 w-40 sm:w-80 h-40 sm:h-80 bg-cyan-400/20 rounded-full blur-3xl animate-float-delayed"></div></div><div class="relative z-10 space-y-6 sm:space-y-8 px-4 w-full"><div class="inline-block p-4 sm:p-5 bg-blue-600/10 rounded-2xl sm:rounded-3xl border border-blue-500/20 text-blue-500 shadow-2xl shadow-blue-500/20"><i data-lucide="trophy" class="w-12 h-12 sm:w-16 sm:h-16"></i></div><h1 class="text-5xl sm:text-7xl md:text-8xl font-black italic uppercase tracking-tighter theme-text-main drop-shadow-lg">THE CUP</h1><p class="text-sm sm:text-lg text-slate-500 max-w-lg mx-auto font-bold">Profesionální organizace sportovních turnajů.</p><div class="pt-6"><a href="/account" class="inline-flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-8 sm:px-10 py-4 sm:py-5 rounded-xl sm:rounded-2xl font-black uppercase text-xs sm:text-sm tracking-widest shadow-xl active:scale-95 transition-all">Začít <i data-lucide="arrow-right" class="w-4 h-4"></i></a></div></div></div>"""
INDEX_HTML = """<div class="space-y-6 sm:space-y-10">{% if invitations %}<section class="mb-4"><div class="flex items-center gap-2 mb-3 px-1"><i data-lucide="mail-open" class="w-4 h-4 text-yellow-500 shrink-0"></i><h2 class="text-lg sm:text-xl font-black uppercase italic text-yellow-500 tracking-widest">Pozvánky do turnajů</h2></div><div class="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">{% for inv in invitations %}<div class="navy-card p-4 sm:p-5 flex justify-between items-center border border-yellow-500/20 bg-yellow-500/5"><div class="min-w-0 pr-4"><h3 class="font-bold text-base sm:text-lg leading-tight truncate theme-text-main">{{ inv.t_name }}</h3><p class="text-[9px] text-slate-400 mt-1">Byl jsi přímo pozván organizátorem</p></div><div class="flex gap-2 shrink-0"><a href="/join/{{ inv.join_token }}" class="bg-green-600 hover:bg-green-500 text-white px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider">Vstoupit</a><form action="/invitation/{{ inv.id }}/decline" method="POST"><button class="bg-slate-800 hover:bg-slate-700 text-red-400 px-3 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider border border-white/5">Skrýt</button></form></div></div>{% endfor %}</div></section>{% endif %}{% if next_match %}<div class="navy-card p-5 border border-orange-500/30 bg-gradient-to-br from-slate-900 to-slate-950 shadow-2xl relative overflow-hidden mb-6 sm:mb-8"><h3 class="text-[9px] font-black text-orange-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="zap" class="w-3 h-3"></i> Tvůj další zápas</h3><div class="flex justify-between items-center"><div class="flex items-center gap-3"><div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ next_match.t1_color }}" onclick="openLogoModal('{{next_match.t1_logo}}', '{{next_match.t1_color}}')"><span class="text-xl drop-shadow-md">{% if next_match.t1_logo and 'static' in next_match.t1_logo %}<img src="{{next_match.t1_logo}}" class="w-full h-full object-contain p-1">{% else %}{{next_match.t1_logo}}{% endif %}</span></div><span class="font-black uppercase text-xs theme-text-main">{{ next_match.t1_name }}</span></div><div class="text-xs font-black text-slate-500 mx-2">VS</div><div class="flex items-center gap-3 text-right"><span class="font-black uppercase text-xs theme-text-main">{{ next_match.t2_name }}</span><div class="w-10 h-10 rounded-xl flex items-center justify-center shrink-0 border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ next_match.t2_color }}" onclick="openLogoModal('{{next_match.t2_logo}}', '{{next_match.t2_color}}')"><span class="text-xl drop-shadow-md">{% if next_match.t2_logo and 'static' in next_match.t2_logo %}<img src="{{next_match.t2_logo}}" class="w-full h-full object-contain p-1">{% else %}{{next_match.t2_logo}}{% endif %}</span></div></div></div><div class="mt-4 pt-3 border-t border-white/5 flex justify-between items-center text-[10px] text-slate-400 font-bold uppercase tracking-widest"><span><a href="/tournament/{{ next_match.t_id }}" class="text-blue-500 hover:underline">{{ next_match.tr_name }}</a></span><span class="flex items-center gap-2">{% if next_match.match_time %}<i data-lucide="clock" class="w-3 h-3"></i> {{ m_time }}{% endif %} {% if next_match.pitch %}<i data-lucide="flag" class="w-3 h-3 ml-2"></i> {{ next_match.pitch }}{% endif %}</span></div></div>{% endif %}<section class="grid grid-cols-2 gap-3 sm:gap-4"><div class="navy-card p-4 sm:p-5 border-blue-500/20 bg-gradient-to-br from-slate-900 to-slate-950 flex justify-between items-center"><div><p class="text-[9px] sm:text-[10px] font-bold text-blue-400 uppercase tracking-widest mb-1 truncate">Moje turnaje</p><p class="text-2xl sm:text-3xl font-black italic leading-none">{{ stats.total_tournaments }}</p></div><i data-lucide="trophy" class="w-6 h-6 sm:w-8 sm:h-8 text-blue-500 opacity-50"></i></div><div class="navy-card p-4 sm:p-5 bg-slate-900/50 flex justify-between items-center"><div><p class="text-[9px] sm:text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1 truncate">Můj registr týmů</p><p class="text-2xl sm:text-3xl font-black italic leading-none">{{ stats.total_teams }}</p></div><i data-lucide="users" class="w-6 h-6 sm:w-8 sm:h-8 text-slate-500 opacity-50"></i></div></section>{% if participating_tourneys %}<section><div class="flex items-center gap-2 mb-3 sm:mb-4 px-1"><i data-lucide="play-circle" class="w-4 h-4 text-blue-500 shrink-0"></i><h2 class="text-lg sm:text-xl font-black uppercase italic text-blue-500 tracking-widest truncate">Účastním se</h2></div><div class="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">{% for t in participating_tourneys %}<a href="/view/{{ t.id }}" class="navy-card p-4 sm:p-5 flex justify-between items-center border border-white/5 hover:border-blue-500/30 transition-all bg-blue-900/10"><div class="min-w-0 pr-4"><span class="text-[8px] sm:text-[9px] font-bold uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2 inline-block">{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t.status, t.status) }}</span><h3 class="font-bold text-base sm:text-lg leading-tight truncate theme-text-main">{{ t.name }}</h3><p class="text-[9px] sm:text-[10px] text-slate-400 mt-1 flex items-center gap-1.5 truncate"><i data-lucide="user" class="w-3 h-3 shrink-0"></i> Pořádá: {{ t.username }}</p><p class="text-[9px] sm:text-[10px] text-slate-500 mt-0.5 flex items-center gap-1.5"><i data-lucide="users" class="w-3 h-3 shrink-0"></i> Týmy: {{ t.registered_teams }}/{{ t.max_teams }}</p></div><i data-lucide="eye" class="w-5 h-5 text-blue-500 shrink-0"></i></a>{% endfor %}</div></section>{% endif %}{% if active_tourneys %}<section><div class="flex items-center gap-2 mb-3 sm:mb-4 px-1"><i data-lucide="zap" class="w-4 h-4 text-orange-500 shrink-0"></i><h2 class="text-lg sm:text-xl font-black uppercase italic text-orange-500 tracking-widest truncate">Moje Live akce / Drafty</h2></div><div class="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">{% for t in active_tourneys %}<a href="/tournament/{{ t.id }}" class="navy-card p-4 sm:p-5 flex justify-between items-center border border-orange-500/10 hover:border-orange-500/30 transition-all"><div class="min-w-0 pr-4"><span class="text-[8px] sm:text-[9px] font-bold uppercase px-2 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20 mb-2 inline-block">{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t.status, t.status) }}</span><h3 class="font-bold text-base sm:text-lg leading-tight truncate theme-text-main">{{ t.name }}</h3><p class="text-[9px] sm:text-[10px] text-slate-400 mt-1 flex items-center gap-1.5 truncate"><i data-lucide="calendar-days" class="w-3 h-3 shrink-0"></i> {{ format_date_cz(t.start_date) }}</p><p class="text-[9px] sm:text-[10px] text-slate-500 mt-0.5 flex items-center gap-1.5"><i data-lucide="users" class="w-3 h-3 shrink-0"></i> Týmy: {{ t.registered_teams }}/{{ t.max_teams }}</p></div><i data-lucide="chevron-right" class="w-5 h-5 text-orange-500 shrink-0"></i></a>{% endfor %}</div></section>{% endif %}{% if joinable_public_tourneys %}<section><div class="flex items-center gap-2 mb-3 sm:mb-4 px-1"><i data-lucide="search" class="w-4 h-4 text-green-500 shrink-0"></i><h2 class="text-lg sm:text-xl font-black uppercase italic text-green-500 tracking-widest truncate">Volné veřejné turnaje</h2></div><div class="grid grid-cols-1 md:grid-cols-2 gap-3 sm:gap-4">{% for t in joinable_public_tourneys %}<a href="/join/{{ t.join_token }}" class="navy-card p-4 sm:p-5 flex justify-between items-center border-green-500/20 hover:border-green-500/50 bg-green-500/5 transition-all"><div class="min-w-0 pr-4"><h3 class="font-bold text-base sm:text-lg leading-tight truncate theme-text-main">{{ t.name }}</h3><p class="text-[9px] sm:text-[10px] text-slate-400 mt-1 flex items-center gap-1.5 truncate"><i data-lucide="user" class="w-3 h-3 text-green-500 shrink-0"></i> Pořádá: {{ t.username }}</p><p class="text-[9px] sm:text-[10px] text-slate-400 mt-0.5 flex items-center gap-1.5 truncate"><i data-lucide="calendar-days" class="w-3 h-3 text-green-500 shrink-0"></i> Zahájení: {{ format_date_cz(t.start_date) }}</p><p class="text-[9px] sm:text-[10px] text-slate-500 mt-0.5 flex items-center gap-1.5"><i data-lucide="users" class="w-3 h-3 text-green-500 shrink-0"></i> Volno: {{ t.registered_teams }}/{{ t.max_teams }}</p></div><i data-lucide="log-in" class="w-5 h-5 sm:w-6 sm:h-6 text-green-500 opacity-80 shrink-0"></i></a>{% endfor %}</div></section>{% endif %}</div>"""
ACCOUNT_HTML = """<div class="max-w-md mx-auto w-full">{% if current_user %}<div class="text-center mb-6 sm:mb-8"><div class="w-20 h-20 sm:w-24 sm:h-24 bg-blue-600/20 rounded-full flex items-center justify-center mx-auto mb-3 sm:mb-4 border border-blue-500/30 text-blue-500 relative"><i data-lucide="user-check" class="w-8 h-8 sm:w-10 sm:h-10"></i>{% if current_user.is_pro %}<div class="absolute -top-2 -right-2 bg-yellow-500 text-slate-900 rounded-full p-1"><i data-lucide="crown" class="w-4 h-4"></i></div>{% endif %}</div><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter truncate theme-text-main">{{ current_user.username }}</h2><p class="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-widest font-bold">Organizátor / Hráč • Tipovací body: {{ current_user.bet_points }}</p></div>{% if current_user.is_pro %}<div class="navy-card p-4 border-yellow-500/50 bg-yellow-500/10 mb-6 sm:mb-8 text-center shadow-[0_0_15px_rgba(234,179,8,0.1)]"><h3 class="text-yellow-500 font-black uppercase tracking-widest text-xs flex items-center justify-center gap-2"><i data-lucide="crown" class="w-4 h-4"></i> PRO Premium Aktivní</h3></div>{% else %}<div class="navy-card p-5 border-blue-500/30 mb-6 sm:mb-8 text-center relative overflow-hidden"><div class="absolute inset-0 bg-blue-600/5"></div><h3 class="text-white font-black uppercase tracking-widest text-sm mb-2 relative z-10">Přejít na PRO Premium</h3><p class="text-[10px] text-slate-400 mb-4 font-bold relative z-10">Získejte přístup k modulu AI Logo Studio a dalším profesionálním nástrojům.</p><form action="/upgrade_pro" method="POST" class="relative z-10"><button class="bg-yellow-500 hover:bg-yellow-400 text-slate-900 font-black uppercase text-[10px] py-3 rounded-xl w-full tracking-widest transition-colors shadow-lg">Aktivovat PRO</button></form></div>{% endif %}<div class="navy-card p-6 border border-green-500/30 bg-green-500/10 mb-6 sm:mb-8"><h3 class="text-xs font-black uppercase text-green-500 mb-4 flex items-center gap-2"><i data-lucide="wifi-off" class="w-4 h-4"></i> Zero-Internet Host Mode</h3><p class="text-[9px] text-slate-400 mb-4 font-bold">Aktivuj Wi-Fi Hotspot. Ostatní se připojí a naskenují kód:</p><div class="bg-white p-2 inline-block rounded-xl mb-4 shadow-lg"><canvas id="host-qr"></canvas></div><p class="text-[10px] font-mono text-green-400 font-bold block">{{ host_url }}</p></div><div class="flex gap-2 mb-6 sm:mb-8"><a href="/export/db" class="flex-1 bg-slate-800 hover:bg-slate-700 py-3 rounded-xl font-black uppercase text-[9px] sm:text-[10px] text-center flex justify-center items-center gap-2 transition-colors theme-text-main border border-white/5"><i data-lucide="download" class="w-4 h-4"></i> Záloha DB</a></div><div class="navy-card p-5 sm:p-6 mb-6 sm:mb-8"><h3 class="text-base sm:text-lg font-black uppercase text-slate-100 mb-4 sm:mb-6 tracking-tighter flex items-center gap-2"><i data-lucide="palette" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Nastavení vzhledu</h3><form action="/set_theme" method="POST" class="space-y-4"><select name="theme" class="w-full rounded-xl p-3 text-xs sm:text-sm font-bold border-blue-500/30 cursor-pointer theme-text-main" onchange="this.form.submit()"><option value="system" {% if current_user.theme == 'system' %}selected{% endif %}>Dle systému telefonu</option><option value="light" {% if current_user.theme == 'light' %}selected{% endif %}>Světlý motiv</option><option value="dark" {% if current_user.theme == 'dark' %}selected{% endif %}>Tmavý motiv (Navy)</option></select></form></div><div class="navy-card p-5 sm:p-6 mb-6 sm:mb-8"><h3 class="text-base sm:text-lg font-black uppercase text-slate-100 mb-4 sm:mb-6 tracking-tighter flex items-center gap-2"><i data-lucide="key" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Změna hesla</h3><form action="/change_password" method="POST" class="space-y-3 sm:space-y-4"><div><input type="password" name="current_password" placeholder="Stávající heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm theme-text-main"></div><div><input type="password" name="new_password" placeholder="Nové heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm border-blue-500/30 theme-text-main"></div><div><input type="password" name="confirm_password" placeholder="Potvrdit nové heslo" required class="w-full rounded-xl p-3 text-xs sm:text-sm border-blue-500/30 theme-text-main"></div><button type="submit" class="w-full bg-slate-800 py-3 rounded-xl font-black uppercase text-[9px] sm:text-[10px] tracking-widest hover:bg-slate-700 transition-colors theme-text-main">Uložit heslo</button></form></div><div class="navy-card p-3 sm:p-4 mb-8 border-red-500/20"><a href="/logout" class="flex items-center justify-between p-3 sm:p-4 bg-red-500/10 rounded-xl hover:bg-red-500/20 transition-colors"><div class="flex items-center gap-3"><i data-lucide="log-out" class="w-4 h-4 sm:w-5 sm:h-5 text-red-500"></i><span class="text-xs sm:text-sm font-bold uppercase text-red-500">Odhlásit se</span></div></a></div><script>setTimeout(()=>{new QRious({element:document.getElementById('host-qr'),value:'{{host_url}}',size:150});},100);</script>{% else %}{% if session.get('next_url') and '/join/' in session.get('next_url') %}<div class="mb-4 sm:mb-6 p-3 sm:p-4 bg-blue-600/20 border border-blue-500/50 rounded-xl sm:rounded-2xl text-[10px] sm:text-xs text-blue-500 font-bold text-center flex items-center gap-3"><i data-lucide="info" class="w-5 h-5 sm:w-6 sm:h-6 shrink-0"></i><span class="text-left">Byl jsi pozván do turnaje THE CUP! Pro připojení se prosím přihlas nebo zaregistruj.</span></div>{% endif %}<div class="text-center mb-8 sm:mb-10"><div class="w-16 h-16 sm:w-20 sm:h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-4 sm:mb-6 shadow-inner border border-white/5"><i data-lucide="lock" class="w-6 h-6 sm:w-8 sm:h-8 text-slate-400"></i></div><h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none mb-2 theme-text-main">Přihlášení</h2><p class="text-[9px] sm:text-[10px] text-slate-500 uppercase tracking-widest font-bold">Pro přístup se prosím přihlas</p></div><div class="navy-card p-5 sm:p-8 border-blue-500/20 relative overflow-hidden"><form action="/login" method="POST" class="space-y-4 sm:space-y-6"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1">Uživatelské jméno</label><input name="username" required class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 mt-1 sm:mt-2 text-sm sm:text-base font-bold theme-text-main"></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1">Heslo</label><input type="password" name="password" required class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 mt-1 sm:mt-2 text-sm sm:text-base font-bold theme-text-main"></div><button type="submit" class="w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 sm:py-5 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-xs tracking-widest">Přihlásit se</button></form><div class="mt-6 sm:mt-8 pt-6 sm:pt-8 border-t border-white/5 text-center"><p class="text-[10px] sm:text-xs text-slate-500 mb-3 sm:mb-4">Ještě nemáš účet?</p><form action="/register" method="POST" class="flex flex-col sm:flex-row gap-2"><input name="username" placeholder="Nové jméno" required class="flex-1 rounded-xl p-3 text-xs sm:text-sm theme-text-main"><input type="password" name="password" placeholder="Heslo" required class="flex-1 rounded-xl p-3 text-xs sm:text-sm theme-text-main"><button type="submit" class="bg-slate-800 py-3 sm:py-0 px-4 rounded-xl font-bold text-[9px] sm:text-[10px] uppercase hover:bg-slate-700 theme-text-main">Registrovat</button></form></div></div>{% endif %}</div>"""
TEAMS_HTML = """<div class="flex justify-between items-center mb-6 sm:mb-8"><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter truncate theme-text-main pr-2">Registr Týmů</h2><a href="/teams/new" class="bg-blue-600 px-3 sm:px-4 py-2 sm:py-3 rounded-xl font-black text-[9px] sm:text-[10px] text-white uppercase hover:bg-blue-500 transition-colors shadow-lg shrink-0 flex items-center gap-1"><i data-lucide="plus" class="w-3 h-3 sm:w-4 sm:h-4"></i><span class="hidden sm:inline">Nový tým</span></a></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">{% for team in master_teams %}<a href="/teams/edit/{{ team.id }}" class="navy-card p-3 sm:p-4 flex items-center justify-between border-l-4 group hover:bg-white/5 transition-all" style="border-left-color: {{ team.color }}"><div class="flex items-center gap-3 sm:gap-4 min-w-0 pr-2"><div class="w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center border border-white/10 shadow-inner shrink-0 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ team.color }}" onclick="event.preventDefault(); event.stopPropagation(); openLogoModal('{{team.logo}}', '{{team.color}}')">{% if team.logo and 'static' in team.logo %}<img src="{{team.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-xl sm:text-2xl drop-shadow-md">{{ team.logo }}</span>{% endif %}</div><span class="font-black uppercase text-xs sm:text-sm tracking-tight truncate theme-text-main">{{ team.name }}</span></div><div class="flex items-center gap-2"><span class="text-[8px] font-black text-yellow-500 bg-yellow-500/10 px-2 py-1 rounded border border-yellow-500/20 text-center">ELO<br>{{ team.elo }}</span><i data-lucide="chevron-right" class="text-slate-500 shrink-0 w-4 h-4 sm:w-5 sm:h-5"></i></div></a>{% endfor %}</div>"""
TEAM_NEW_HTML = """<div class="max-w-xl mx-auto py-6 w-full"><div class="flex items-center gap-3 mb-6"><a href="/teams" class="text-slate-500 p-2 -ml-2 hover:bg-white/5 rounded-lg"><i data-lucide="arrow-left"></i></a><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter theme-text-main">Nový tým</h2></div><div class="navy-card p-6 shadow-2xl border-white/5 mb-8"><form method="POST" action="/teams/new" class="space-y-6" id="team-form"><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Základní identifikace</h3><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Jméno týmu</label><input name="name" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main" autocomplete="off"></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Zkratka (Tag)</label><input name="tag" maxlength="4" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main uppercase"></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Týmová barva</label><input type="color" name="color" value="#3b82f6" class="w-full h-11 rounded-xl p-0.5 outline-none cursor-pointer bg-slate-900/50 border border-white/5"></div></div></div><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Zdroj loga</h3><div class="flex gap-2"><label class="flex-1 relative"><input type="radio" name="logo_type" value="emoji" class="peer sr-only" checked onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="smile" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Ikona / Znak</span></div></label><label class="flex-1 relative"><input type="radio" name="logo_type" value="ai" class="peer sr-only" onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="sparkles" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Studio 👑</span></div></label></div><div id="section-emoji" class="block space-y-2"><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vyber symbol</label><input type="hidden" name="emoji_logo" id="team-logo" value="⚽"><div class="grid grid-cols-5 sm:grid-cols-8 gap-2 p-2 bg-slate-900/50 rounded-xl max-h-40 overflow-y-auto border border-white/5 shadow-inner">{% set emojis = ['⚽','🏒','🏀','🏐','🏈','🎾','🎱','🏓','🥊','🥋','🐅','🦅','🦈','🐺','🐻','🦁','🐉','🐍','⚡','🔥','⭐','☠️','💎','🛡️'] %}{% for e in emojis %}<button type="button" onclick="document.getElementById('team-logo').value='{{ e }}'; document.querySelectorAll('.emoji-btn').forEach(b=>b.style.opacity=0.4); this.style.opacity=1;" class="emoji-btn text-2xl p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-all opacity-40">{{ e }}</button>{% endfor %}</div></div><div id="section-ai" class="hidden space-y-4 pt-2">{% if not current_user.is_pro %}<div class="text-center p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl"><p class="text-xs font-bold text-yellow-500 mb-2">Tato funkce vyžaduje PRO Premium</p><a href="/account" class="inline-block bg-yellow-500 text-slate-900 px-4 py-2 rounded-lg font-black text-[10px] uppercase">Aktivovat</a></div>{% else %}<div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vizuální Styl loga</label><select name="style" class="w-full rounded-xl p-3 text-xs font-bold bg-slate-900/50 theme-text-main mt-1">{% for k,v in styles.items() %}<option value="{{k}}">{{k}}</option>{% endfor %}</select></div><div class="grid grid-cols-3 gap-2"><div class="text-center cursor-pointer" onclick="openColorPicker('body')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Tělo</label><div id="swatch-body" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #ffffff;"></div><input type="hidden" name="color_body" id="input-body" value="White"></div><div class="text-center cursor-pointer" onclick="openColorPicker('outline')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Obrys</label><div id="swatch-outline" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #020617;"></div><input type="hidden" name="color_outline" id="input-outline" value="Black"></div><div class="text-center cursor-pointer" onclick="openColorPicker('fill')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Výplň</label><div id="swatch-fill" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #3b82f6;"></div><input type="hidden" name="color_fill" id="input-fill" value="Blue"></div></div><div id="ai-prompts" class="space-y-3 mt-4 border-t border-white/5 pt-4"><p class="text-[10px] font-black uppercase text-blue-500 tracking-widest">Generovací Prompty (Lze upravit)</p><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Fáze 1: Logo Maskota</label><textarea id="prompt_logo" class="w-full rounded-xl p-3 text-xs font-mono bg-slate-900/80 text-blue-300 border border-blue-500/30 h-20 outline-none" oninput="markCustom()"></textarea></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Fáze 2: Typografie</label><textarea id="prompt_text" class="w-full rounded-xl p-3 text-xs font-mono bg-slate-900/80 text-orange-300 border border-orange-500/30 h-20 outline-none" oninput="markCustom()"></textarea></div><button type="button" id="ai-generate-btn" onclick="triggerAiGeneration()" class="w-full bg-yellow-500 hover:bg-yellow-400 text-slate-900 py-4 rounded-xl font-black uppercase text-[10px] tracking-widest shadow-lg mt-2 transition-all">Generovat Náhled v AI</button></div><div id="ai-progress-ui" class="hidden mt-4 bg-slate-900/50 p-4 rounded-xl border border-white/5 text-center"><p class="text-[10px] font-black uppercase text-yellow-500 tracking-widest mb-3" id="progress-text">Zahajuji AI Syntézu...</p><div class="w-full bg-slate-950 rounded-full h-3 mb-2 overflow-hidden border border-white/10"><div id="progress-bar-fill" class="bg-gradient-to-r from-blue-600 to-yellow-500 h-full rounded-full transition-all duration-1000 ease-linear" style="width: 0%"></div></div><p class="text-xs font-mono text-slate-400 font-bold" id="progress-countdown">Odhad: 35 s</p></div><div id="ai-result-ui" class="hidden mt-4 bg-slate-900/50 p-5 rounded-2xl border border-white/5 text-center relative overflow-hidden"><div class="absolute inset-0 bg-green-500/5"></div><p class="text-[10px] font-black uppercase text-green-500 tracking-widest mb-4 relative z-10"><i data-lucide="check-circle" class="w-4 h-4 inline mr-1"></i> Hotový Náhled</p><img id="preview-image" src="" class="w-48 h-48 mx-auto object-contain mb-6 relative z-10 drop-shadow-2xl cursor-pointer hover:scale-110 transition-transform" onclick="openLogoModal(this.src, '#0f172a')"><input type="hidden" name="final_ai_logo" id="final_ai_logo_val"></div>{% endif %}</div></div><button type="submit" id="submit-btn-standard" class="w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest shadow-xl shadow-blue-900/40">Zapsat tým do registru</button><button type="submit" id="submit-btn-ai" class="w-full bg-green-600 hover:bg-green-500 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest shadow-xl shadow-green-900/40 hidden">Potvrdit a uložit tým</button></form></div></div><div id="custom-color-picker" class="fixed inset-0 z-[3000] bg-slate-950/90 backdrop-blur-md hidden flex flex-col items-center justify-center p-4 opacity-0 transition-opacity"><div class="navy-card p-6 w-full max-w-sm shadow-2xl border-white/10 relative"><button type="button" onclick="closeColorPicker()" class="absolute top-4 right-4 text-slate-500 hover:text-white"><i data-lucide="x" class="w-5 h-5"></i></button><h3 class="text-lg font-black uppercase italic mb-4 theme-text-main text-center">Vyber barvu</h3><div class="grid grid-cols-5 gap-3" id="color-grid"></div></div></div><script>let customPrompts = false; function markCustom() { customPrompts = true; } function updatePrompts() { if(customPrompts || !document.getElementById('prompt_logo')) return; let name = document.querySelector('input[name="name"]').value || 'Team'; let style = document.querySelector('select[name="style"]').value || 'clean'; let cBody = document.getElementById('input-body').value || 'White'; let cOut = document.getElementById('input-outline').value || 'Black'; let cFill = document.getElementById('input-fill').value || 'Blue'; let colors = `Main Body: ${cBody}, Outline: ${cOut}, Fill/Accents: ${cFill}`; let mascot = "creative mascot"; let lName = name.toLowerCase(); if(lName.includes('wolf')) mascot = 'ice wolf'; else if(lName.includes('bear')) mascot = 'polar bear'; else if(lName.includes('dragon')) mascot = 'ice dragon'; else if(lName.includes('hawk')) mascot = 'ice hawk'; else if(lName.includes('eagle')) mascot = 'ice eagle'; document.getElementById('prompt_logo').value = `Esports team mascot graphic. Concept: ${mascot} (can be animal, warrior, entity, or object). Style: ${style}. Colors: ${colors}. STRICTLY NO TEXT, NO LETTERS. Centered, solid bold outlines. Blank solid white background.`; document.getElementById('prompt_text').value = `Esports team typography logo. The exact word '${name}' in bold, thick, aggressive 3D esports font. Placed on a solid curved badge or banner background. Colors: ${colors}. STRICTLY NO MASCOTS, NO ANIMALS, ONLY THE TEXT. Blank solid white background.`; } document.querySelector('input[name="name"]').addEventListener('input', updatePrompts); document.body.addEventListener('click', function(e) { if(e.target.closest('#color-grid') || e.target.closest('select')) setTimeout(updatePrompts, 100); }); function toggleLogoType() { const isAi = document.querySelector('input[name="logo_type"]:checked').value === 'ai'; document.getElementById('section-emoji').style.display = isAi ? 'none' : 'block'; document.getElementById('section-ai').style.display = isAi ? 'block' : 'none'; if(isAi && !document.getElementById('ai-result-ui').classList.contains('hidden')) { document.getElementById('submit-btn-standard').classList.add('hidden'); document.getElementById('submit-btn-ai').classList.remove('hidden'); } else { document.getElementById('submit-btn-ai').classList.add('hidden'); document.getElementById('submit-btn-standard').classList.remove('hidden'); } setTimeout(updatePrompts, 100); } async function triggerAiGeneration() { let name = document.querySelector('input[name="name"]').value; if(!name) { alert('Nejprve zadejte název týmu do horního pole!'); return; } document.getElementById('ai-generate-btn').classList.add('hidden'); document.getElementById('submit-btn-standard').classList.add('hidden'); document.getElementById('ai-prompts').classList.add('opacity-50', 'pointer-events-none'); document.getElementById('ai-progress-ui').classList.remove('hidden'); let pLogo = document.getElementById('prompt_logo').value; let pText = document.getElementById('prompt_text').value; let duration = 35; let current = 0; let pBar = document.getElementById('progress-bar-fill'); let pCount = document.getElementById('progress-countdown'); let pTextMsg = document.getElementById('progress-text'); let timer = setInterval(() => { current++; let pct = Math.min((current / duration) * 100, 95); pBar.style.width = pct + '%'; pCount.innerText = `Zbývá cca: ${Math.max(duration - current, 1)} s`; if (current === 5) pTextMsg.innerText = "Fáze 1: Generuji grafiku maskota (Pixazo API)..."; if (current === 16) pTextMsg.innerText = "Fáze 2: Renderuji e-sport typografii..."; if (current === 28) pTextMsg.innerText = "Fáze 3: Čistím pozadí a skládám vrstvy..."; }, 1000); try { let formData = new FormData(); formData.append('team_name', name); formData.append('prompt_logo', pLogo); formData.append('prompt_text', pText); let res = await fetch('/api/v1/teams/generate_two_phase', { method: 'POST', body: formData }); let data = await res.json(); clearInterval(timer); pBar.style.width = '100%'; if(res.ok && data.status === 'success') { pTextMsg.innerText = "Hotovo!"; pCount.innerText = "Skládání dokončeno"; setTimeout(() => { document.getElementById('ai-progress-ui').classList.add('hidden'); document.getElementById('ai-result-ui').classList.remove('hidden'); document.getElementById('preview-image').src = data.logo_url; document.getElementById('final_ai_logo_val').value = data.logo_url; document.getElementById('submit-btn-ai').classList.remove('hidden'); }, 800); } else { throw new Error(data.error || "Neznámá chyba"); } } catch(err) { clearInterval(timer); alert("Chyba: " + err.message); document.getElementById('ai-progress-ui').classList.add('hidden'); document.getElementById('ai-generate-btn').classList.remove('hidden'); document.getElementById('submit-btn-standard').classList.remove('hidden'); document.getElementById('ai-prompts').classList.remove('opacity-50', 'pointer-events-none'); } } const palette = [{name: 'White', hex: '#ffffff'}, {name: 'Silver', hex: '#94a3b8'}, {name: 'Gray', hex: '#475569'}, {name: 'Black', hex: '#020617'}, {name: 'Navy', hex: '#0f172a'},{name: 'Blue', hex: '#3b82f6'}, {name: 'Cyan', hex: '#06b6d4'}, {name: 'Teal', hex: '#14b8a6'}, {name: 'Green', hex: '#22c55e'}, {name: 'Lime', hex: '#84cc16'},{name: 'Yellow', hex: '#eab308'}, {name: 'Orange', hex: '#f97316'}, {name: 'Red', hex: '#ef4444'}, {name: 'Rose', hex: '#f43f5e'}, {name: 'Pink', hex: '#ec4899'},{name: 'Purple', hex: '#a855f7'}, {name: 'Violet', hex: '#8b5cf6'}, {name: 'Indigo', hex: '#6366f1'}, {name: 'Brown', hex: '#78350f'}, {name: 'Gold', hex: '#ca8a04'}]; let currentTarget = null; function openColorPicker(target) { currentTarget = target; const grid = document.getElementById('color-grid'); grid.innerHTML = ''; palette.forEach(c => { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'w-full aspect-square rounded-full border-2 border-white/10 shadow-lg transition-transform hover:scale-110 active:scale-95'; btn.style.backgroundColor = c.hex; btn.onclick = () => selectCustomColor(c.name, c.hex); grid.appendChild(btn); }); const modal = document.getElementById('custom-color-picker'); modal.classList.remove('hidden'); void modal.offsetWidth; modal.classList.remove('opacity-0'); lucide.createIcons(); } function closeColorPicker() { const modal = document.getElementById('custom-color-picker'); modal.classList.add('opacity-0'); setTimeout(() => modal.classList.add('hidden'), 300); } function selectCustomColor(name, hex) { if(currentTarget) { document.getElementById('swatch-' + currentTarget).style.backgroundColor = hex; document.getElementById('input-' + currentTarget).value = name; } closeColorPicker(); } setTimeout(() => document.querySelector('.emoji-btn').click(), 100);</script>"""
CREATE_HTML = """<div class="max-w-xl mx-auto py-6 sm:py-8 text-center w-full"><div class="inline-block p-4 sm:p-5 bg-blue-600/10 rounded-2xl sm:rounded-3xl mb-4 sm:mb-6 border border-blue-500/20 text-blue-500 shadow-xl shadow-blue-500/10"><i data-lucide="trophy" class="w-10 h-10 sm:w-12 sm:h-12"></i></div><h2 class="text-3xl sm:text-4xl font-black italic uppercase leading-none mb-8 sm:mb-10 tracking-tighter theme-text-main">Vytvořit turnaj</h2><form method="POST" action="/create" id="tournament-form" class="navy-card p-5 sm:p-8 space-y-4 sm:space-y-6 border border-blue-500/10 shadow-2xl text-left"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Název turnaje</label><input name="name" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 outline-none text-lg sm:text-xl font-black mt-1 theme-text-main bg-slate-900/50"></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Datum</label><input type="date" name="start_date" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm mt-1 theme-text-main bg-slate-900/50"></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Kapacita</label><input type="number" name="max_teams" value="8" min="2" max="32" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm font-bold mt-1 theme-text-main bg-slate-900/50"></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Viditelnost</label><select name="is_public" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="0">Privátní (QR)</option><option value="1">Veřejný</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Formát</label><select name="format" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="groups" selected>Skupiny + Playoff</option><option value="knockout">Čistý Pavouk</option></select></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Skupiny</label><select name="group_count" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>Jedna tabulka</option><option value="2">Dvě skupiny (A, B)</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Počet kol</label><select name="rounds" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>1 Zápas</option><option value="2">2 Zápasy</option><option value="3">3 Zápasy</option></select></div></div><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Turnajový Banner</h3><div class="flex gap-2"><label class="flex-1 relative"><input type="radio" name="banner_type" value="standard" class="peer sr-only" checked><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="type" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Standardní Design</span></div></label><label class="flex-1 relative"><input type="radio" name="banner_type" value="ai" class="peer sr-only"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="image" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Banner 👑</span></div></label></div></div><button type="submit" id="submit-btn" class="w-full bg-blue-600 hover:bg-blue-500 py-5 sm:py-6 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-sm tracking-widest shadow-xl shadow-blue-900/40 active:scale-95 transition-all flex justify-center items-center gap-2">Vytvořit a naplánovat <i data-lucide="chevron-right" class="w-4 h-4 sm:w-5 sm:h-5"></i></button></form></div><script>document.getElementById('tournament-form').onsubmit = function(e) { const isAi = document.querySelector('input[name="banner_type"]:checked').value === 'ai'; {% if not current_user.is_pro %} if (isAi) { e.preventDefault(); alert("AI Banner vyžaduje PRO Premium"); return; } {% endif %} const btn = document.getElementById('submit-btn'); if(isAi) { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Generuji AI Banner (až 30s)...'; } else { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Ukládám...'; } btn.classList.add('opacity-80', 'pointer-events-none'); lucide.createIcons(); };</script>"""
SEASONS_HTML = """<div class="mb-6 sm:mb-10 flex flex-col sm:flex-row sm:items-center gap-3 sm:gap-4"><div class="p-3 bg-blue-600/20 rounded-2xl border border-blue-500/30 text-blue-500 inline-block w-fit"><i data-lucide="archive" class="w-6 h-6 sm:w-8 sm:h-8"></i></div><div><h2 class="text-3xl sm:text-4xl font-black italic uppercase tracking-tighter leading-none theme-text-main">Archiv turnajů</h2><p class="text-[9px] sm:text-[10px] font-bold text-slate-500 uppercase tracking-widest mt-1">Všechny moje sezóny</p></div></div><div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">{% for t in tournaments %}<div class="navy-card p-5 sm:p-6 flex flex-col relative group hover:border-blue-500/30 transition-all"><form action="/tournament/{{ t.id }}/delete" method="POST" class="absolute top-3 right-3 sm:top-4 sm:right-4" onsubmit="event.preventDefault(); openModal('Opravdu smazat turnaj ze systému?', this);"><button type="submit" class="text-red-500 p-2 hover:bg-red-500/10 rounded-lg transition-colors"><i data-lucide="trash-2" class="w-4 h-4"></i></button></form><div class="mb-5 sm:mb-6 pr-6"><span class="text-[8px] sm:text-[9px] font-bold uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 inline-block mb-2">Status: {{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t.status, t.status) }}</span><h3 class="font-black text-lg sm:text-xl leading-tight truncate theme-text-main">{{ t.name }}</h3></div><div class="flex gap-2 border-t border-white/5 pt-4 mt-auto"><a href="/tournament/{{ t.id }}" class="flex-1 bg-slate-800 text-center py-3 rounded-xl text-[9px] sm:text-[10px] font-bold uppercase tracking-widest flex items-center justify-center gap-1.5 sm:gap-2 hover:bg-slate-700 transition-colors theme-text-main"><i data-lucide="shield-check" class="w-3 h-3 sm:w-4 sm:h-4 text-blue-500"></i> Spravovat</a></div></div>{% endfor %}</div>"""
DETAIL_UI = MATCH_MACRO + """<div id="live-sync-container" data-tid="{{ tournament.id }}">
<div id="export-area" class="w-full pb-4">
<div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">
    <div class="inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden">
        {% if tournament.banner %}
            <div class="w-full border-b border-white/10 h-48 sm:h-64 relative bg-slate-950 flex items-center justify-center">
                <img src="{{ tournament.banner }}" class="w-full h-full object-cover opacity-90">
                <div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div>
            </div>
            <div class="p-4 sm:p-5 relative z-10 -mt-8">
        {% else %}
            <div class="p-4 sm:p-5">
        {% endif %}
                {% if tournament.status == 'finished' and podium and podium.first %}
                    <i data-lucide="crown" class="w-8 h-8 text-yellow-500 mx-auto mb-1 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]"></i>
                    <h3 class="text-[9px] text-yellow-500 font-black uppercase tracking-widest mb-1">Vítěz Turnaje</h3>
                    <h2 class="text-2xl font-black italic uppercase tracking-tighter text-yellow-500 mb-2">{{ podium.first.name }}</h2>
                    <div class="flex justify-center items-end gap-6 sm:gap-8 mt-4 border-t border-white/10 pt-4">
                        {% if podium.second %}
                        <div class="flex flex-col items-center opacity-80">
                            <span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">2. místo</span>
                            <div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.second.color }}" onclick="openLogoModal('{{podium.second.logo}}', '{{podium.second.color}}')">
                                {% if podium.second.logo and 'static' in podium.second.logo %}<img src="{{podium.second.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.second.logo }}</span>{% endif %}
                            </div>
                            <span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.second.name }}</span>
                        </div>
                        {% endif %}
                        {% if podium.third %}
                        <div class="flex flex-col items-center opacity-70">
                            <span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">3. místo</span>
                            <div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.third.color }}" onclick="openLogoModal('{{podium.third.logo}}', '{{podium.third.color}}')">
                                {% if podium.third.logo and 'static' in podium.third.logo %}<img src="{{podium.third.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.third.logo }}</span>{% endif %}
                            </div>
                            <span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.third.name }}</span>
                        </div>
                        {% endif %}
                    </div>
                {% else %}
                    {% if not tournament.banner %}<i data-lucide="award" class="w-8 h-8 sm:w-10 sm:h-10 text-blue-500 mx-auto mb-1 sm:mb-2"></i>{% endif %}
                    <h2 class="text-3xl sm:text-5xl font-black italic uppercase tracking-tighter leading-none text-white drop-shadow-md mb-2">{{ tournament.name }}</h2>
                {% endif %}
                <p class="text-[10px] sm:text-xs text-slate-400 flex items-center justify-center gap-2 font-bold"><i data-lucide="calendar" class="w-3.5 h-3.5 text-blue-500"></i> {{ format_date_cz(tournament.start_date) }} | {{ 'Veřejný' if tournament.is_public else 'Privátní' }}</p>
            </div>
    </div>
    <div class="flex gap-2">
        <a href="/tv/{{ tournament.id }}" target="_blank" class="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-xl text-[9px] font-black uppercase text-blue-400 flex items-center gap-1.5 transition-colors border border-blue-500/20"><i data-lucide="monitor" class="w-4 h-4"></i> TV Režim</a>
        <a href="/export/csv/{{ tournament.id }}" class="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-xl text-[9px] font-black uppercase text-yellow-400 flex items-center gap-1.5 transition-colors border border-yellow-500/20"><i data-lucide="table" class="w-4 h-4"></i> Excel</a>
        <button type="button" onclick="exportImage('export-area')" id="export-btn" class="bg-slate-800 hover:bg-slate-700 px-4 py-2 rounded-xl text-[9px] font-black uppercase text-green-400 flex items-center gap-1.5 transition-colors border border-green-500/20"><i data-lucide="camera" class="w-4 h-4"></i> Sdílet</button>
    </div>
</div>

{% if tournament.status != 'draft' %}
<div class="flex flex-wrap justify-center gap-2 mb-6 w-full" data-html2canvas-ignore id="filter-controls">
    <button type="button" onclick="filterMatches('all')" class="filter-btn active-filter px-4 py-2 rounded-xl font-black text-[9px] sm:text-[10px] uppercase transition-all bg-blue-600 text-white shadow-lg border border-blue-500">Vše</button>
    {% if not is_knockout_only %}
        {% for r in range(1, tournament.rounds + 1) %}
            <button type="button" onclick="filterMatches('round', {{ r }})" class="filter-btn px-4 py-2 rounded-xl font-black text-[9px] sm:text-[10px] uppercase transition-all bg-slate-900/50 theme-text-main border border-white/5 hover:border-blue-500/50">Kolo {{ r }}</button>
        {% endfor %}
    {% endif %}
    {% if has_playoffs or is_knockout_only %}
        <button type="button" onclick="filterMatches('playoff')" class="filter-btn px-4 py-2 rounded-xl font-black text-[9px] sm:text-[10px] uppercase transition-all bg-slate-900/50 theme-text-main border border-white/5 hover:border-blue-500/50">Playoff</button>
    {% endif %}
    {% if current_user %}
        <button type="button" onclick="filterMatches('mine', {{ current_user.id }})" class="filter-btn px-4 py-2 rounded-xl font-black text-[9px] sm:text-[10px] uppercase transition-all bg-orange-600/20 text-orange-500 border border-orange-500/30 hover:bg-orange-600/30 ml-2"><i data-lucide="user" class="w-3 h-3 inline"></i> Moje zápasy</button>
    {% endif %}
</div>
{% endif %}

<div id="content-main" class="flex flex-col lg:flex-row gap-6 sm:gap-8 items-start w-full">
    <div class="w-full lg:w-[380px] xl:w-[420px] lg:sticky lg:top-24 shrink-0">
        {% if tournament.status == 'draft' %}
            
            <div class="bg-blue-600/10 border border-blue-500/20 p-4 sm:p-5 rounded-2xl mb-6 text-center shadow-lg">
                <i data-lucide="megaphone" class="w-8 h-8 text-blue-500 mx-auto mb-2"></i>
                <h3 class="text-blue-500 font-black uppercase tracking-widest text-sm mb-1">Fáze: Oznámení turnaje</h3>
                <p class="text-slate-400 text-xs font-bold leading-relaxed">Probíhá nábor hráčů a registrace týmů. Turnaj se automaticky vygeneruje a odstartuje <strong class="text-blue-400">{{ format_date_cz(tournament.start_date) }}</strong>, nebo jej může organizátor kdykoliv spustit manuálně.</p>
            </div>

            {% if is_admin %}
            <div class="flex gap-2 mb-6">
                <a href="/tournament/{{ tournament.id }}/invite" class="bg-blue-600 px-4 py-4 rounded-xl text-[10px] font-black uppercase flex-1 text-center flex items-center justify-center gap-2 text-white"><i data-lucide="qr-code" class="w-4 h-4"></i> Pozvat Týmy</a>
                {% if teams|length >= 2 %}
                    <a href="/tournament/{{ tournament.id }}/start" class="bg-green-500 text-white px-4 py-4 rounded-xl text-[10px] font-black uppercase flex-1 text-center"><i data-lucide="play" class="w-4 h-4 inline mr-1"></i> Odstartovat</a>
                {% endif %}
            </div>
            {% endif %}
            <div class="navy-card p-5 mb-6 shadow-xl relative">
                <div class="text-[9px] text-slate-500 uppercase font-black absolute top-3 right-4">{{ teams|length }}/{{ tournament.max_teams }}</div>
                <h3 class="text-[10px] font-black text-blue-500 uppercase tracking-widest mb-4">Registrované Týmy</h3>
                <div class="space-y-2">
                    {% for t in teams %}
                        <div class="bg-slate-900/50 p-2.5 rounded-xl flex items-center justify-between border border-white/5">
                            <div class="flex items-center gap-3 min-w-0 pr-2">
                                <div class="w-8 h-8 rounded flex items-center justify-center shrink-0 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ t.color }}" onclick="openLogoModal('{{t.logo}}', '{{t.color}}')">
                                    {% if t.logo and 'static' in t.logo %}<img src="{{t.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm drop-shadow-md">{{ t.logo }}</span>{% endif %}
                                </div>
                                <span class="text-[10px] font-bold uppercase theme-text-main truncate">{{ t.name }} {% if tournament.group_count > 1 and not is_knockout_only %}<span class="text-[8px] text-blue-500 ml-1">(Sk. {{ t.group_name }})</span>{% endif %}</span>
                            </div>
                            {% if is_admin %}
                                <form action="/tournament/{{ tournament.id }}/remove_team/{{ t.id }}" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu vyřadit tým z turnaje?', this);">
                                    <button class="text-red-500 hover:bg-red-500/20 p-1.5 rounded-lg transition-colors"><i data-lucide="trash-2" class="w-3.5 h-3.5"></i></button>
                                </form>
                            {% endif %}
                        </div>
                    {% endfor %}
                </div>
                {% if is_admin %}
                    <div class="mt-4 pt-4 border-t border-white/5">
                        <h4 class="text-[9px] font-black text-slate-500 uppercase mb-2">Přidat můj tým</h4>
                        <div class="max-h-32 overflow-y-auto space-y-1 pr-1">
                            {% for mt in master_teams %}
                                <form action="/tournament/{{ tournament.id }}/add_existing/{{ mt.id }}" method="POST">
                                    <button class="w-full bg-slate-900/50 p-2 rounded-lg flex items-center justify-between border border-white/5 hover:border-blue-500/50">
                                        <span class="text-[9px] font-bold uppercase truncate theme-text-main"><span class="mr-1">{% if mt.logo and 'static' in mt.logo %}<img src="{{mt.logo}}" class="w-4 h-4 inline object-contain">{% else %}{{ mt.logo }}{% endif %}</span> {{ mt.name }}</span>
                                        <span class="text-[10px] text-blue-500 font-bold">＋</span>
                                    </button>
                                </form>
                            {% endfor %}
                        </div>
                    </div>
                {% endif %}
            </div>
        {% endif %}
        
        {% if is_admin %}
        <div class="navy-card p-5 mb-6 shadow-xl" data-html2canvas-ignore>
            <h3 class="text-[9px] font-black text-slate-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="shield" class="w-3 h-3 text-blue-500"></i> Nastavení Rozhodčích</h3>
            <form action="/tournament/{{ tournament.id }}/referees" method="POST" class="flex flex-col gap-2">
                <input type="text" name="referees" value="{{ tournament.referees }}" placeholder="Napiš jména (např. Petr, Karel)..." class="w-full rounded-xl p-3 text-xs font-bold theme-text-main bg-slate-900/50">
                <button class="bg-slate-800 py-2 rounded-xl text-[9px] font-black uppercase theme-text-main border border-white/5">Uložit rozhodčí</button>
            </form>
        </div>
        {% endif %}
        
        {% if is_admin and tournament.status == 'active' %}
        <div class="navy-card p-5 mb-6 shadow-xl border border-blue-500/30" data-html2canvas-ignore>
            <h3 class="text-[9px] font-black text-blue-500 uppercase tracking-widest mb-3 flex items-center gap-2"><i data-lucide="settings" class="w-3 h-3"></i> Správa turnaje</h3>
            <div class="flex flex-col gap-2">
                {% if not is_knockout_only %}
                <form action="/tournament/{{ tournament.id }}/playoff" method="POST">
                    <button class="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-xl text-white font-black text-[10px] uppercase transition-colors">Vygenerovat Playoff</button>
                </form>
                {% endif %}
                <form action="/tournament/{{ tournament.id }}/finish" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu ukončit turnaj?', this);">
                    <button class="w-full bg-slate-800 hover:bg-slate-700 py-3 rounded-xl font-black text-[10px] uppercase text-red-400 border border-red-500/20 transition-colors">Ukončit turnaj</button>
                </form>
            </div>
        </div>
        {% endif %}
        
        {% if standings and not is_knockout_only %}
        <div class="navy-card overflow-hidden shadow-2xl mb-6 table-responsive bg-slate-900/30 view-carousel view-active" id="view-standings">
            <table class="w-full text-left whitespace-nowrap">
                <tr class="bg-slate-800/80 text-[8px] text-slate-400 uppercase font-black border-b border-white/5 cursor-help">
                    <th class="p-4">Tým</th><th class="p-4 text-center" onclick="showLegend(event, 'Zápasy celkem')">Z</th><th class="p-4 text-center" onclick="showLegend(event, 'Výhry (3 body)')">V</th><th class="p-4 text-center" onclick="showLegend(event, 'Remízy (1 bod)')">R</th><th class="p-4 text-center" onclick="showLegend(event, 'Prohry (0 bodů)')">P</th><th class="p-4 text-center" onclick="showLegend(event, 'Skóre (Vstřelené : Inkasované)')">Skóre</th><th class="p-4 text-center" onclick="showLegend(event, 'Gólový rozdíl')">GR</th><th class="p-4 text-center text-blue-500" onclick="showLegend(event, 'Body celkem')">B</th>
                </tr>
                {% set ns = namespace(last_group='') %}
                {% for s in standings %}
                    {% if tournament.group_count > 1 and s.group != ns.last_group %}
                        <tr class="bg-blue-900/20"><td colspan="8" class="p-2 text-center text-[9px] font-black text-blue-400 uppercase tracking-widest border-b border-white/5">Skupina {{ s.group }}</td></tr>
                        {% set ns.last_group = s.group %}
                    {% endif %}
                    <tr class="border-b border-white/5 hover:bg-white/5">
                        <td class="p-4 flex items-center gap-3"><div class="w-8 h-8 rounded flex items-center justify-center shrink-0 border border-white/10 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ s.color }}" onclick="openLogoModal('{{s.logo}}', '{{s.color}}')">{% if s.logo and 'static' in s.logo %}<img src="{{s.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm drop-shadow-md">{{ s.logo }}</span>{% endif %}</div><span class="font-black uppercase text-xs theme-text-main truncate max-w-[120px]">{{ s.name }}</span></td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.gp }}</td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.w }}</td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.d }}</td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.l }}</td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.gf }}:{{ s.ga }}</td>
                        <td class="p-4 text-center opacity-70 text-[10px] font-bold theme-text-main">{{ s.gd }}</td>
                        <td class="p-4 text-center text-blue-500 font-black text-lg">{{ s.pts }}</td>
                    </tr>
                {% endfor %}
            </table>
        </div>
        {% endif %}
    </div>
    
    <div class="flex-1 w-full min-w-0" id="match-container">
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4 view-carousel" id="groups-grid">
            {% for m in group_matches %}{{ render_match(m, is_admin, current_user, logs, preds.get(m.id)) }}{% endfor %}
        </div>
        
        <div class="w-full overflow-x-auto py-4 sm:py-8 table-responsive view-carousel hidden" id="playoff-bracket">
            <div class="flex flex-row justify-start lg:justify-center items-stretch gap-12 sm:gap-16 min-w-max px-4">
                {% set playoff_rounds = [] %}
                {% for m in playoff_matches %}{% if m.round_num not in playoff_rounds %}{% set _ = playoff_rounds.append(m.round_num) %}{% endif %}{% endfor %}
                {% set ns2 = namespace(max_round=0) %}
                {% if playoff_rounds %}{% set ns2.max_round = playoff_rounds | max %}{% endif %}
                
                {% if playoff_matches|length >= 2 %}
                    <div class="flex flex-col justify-around gap-12 w-64 sm:w-80 shrink-0 relative py-8">
                        <div class="bracket-line-right hidden md:block"></div>
                        {% for m in playoff_matches if m.round_num < 98 %}
                            {{ render_match(m, is_admin, current_user, logs, preds.get(m.id)) }}
                        {% endfor %}
                    </div>
                {% endif %}
                
                <div class="flex flex-col justify-center gap-8 w-72 sm:w-[22rem] shrink-0 relative z-10">
                    {% set final_m = playoff_matches | selectattr('round_num', 'equalto', 100) | list %}
                    {% set bronze_m = playoff_matches | selectattr('round_num', 'equalto', 98) | list %}
                    
                    {% if final_m %}
                        <div class="relative"><div class="absolute -inset-1 bg-gradient-to-r from-blue-600 to-cyan-500 rounded-[1.5rem] blur opacity-25"></div>
                        <div class="text-center mb-1"><span class="bg-blue-500/20 text-blue-500 text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-widest">Finále</span></div>
                        {{ render_match(final_m[0], is_admin, current_user, logs, preds.get(final_m[0].id)) }}</div>
                    {% endif %}
                    
                    {% if bronze_m %}
                        <div class="relative mt-4">
                        <div class="text-center mb-1"><span class="bg-orange-500/20 text-orange-500 text-[8px] font-black px-2 py-0.5 rounded uppercase tracking-widest">O 3. místo</span></div>
                        {{ render_match(bronze_m[0], is_admin, current_user, logs, preds.get(bronze_m[0].id)) }}</div>
                    {% endif %}
                    
                    {% if not final_m and not bronze_m and is_admin and tournament.status == 'active' and tournament.stage == 'playoffs' %}
                        <div class="navy-card p-6 border-dashed border-2 border-slate-700/50 flex flex-col items-center justify-center text-center bg-slate-900/30">
                            <i data-lucide="server" class="w-8 h-8 text-blue-500 mb-3 opacity-80"></i><span class="text-blue-400 font-bold text-xs uppercase tracking-widest">Generování pavouka</span>
                            <form action="/tournament/{{ tournament.id }}/next_round" method="POST" class="mt-4 w-full"><button class="w-full bg-blue-600 hover:bg-blue-500 py-3 rounded-xl text-white font-black text-[10px] uppercase tracking-widest shadow-lg shadow-blue-900/30 transition-colors">Vygenerovat další kolo</button></form>
                            <form action="/tournament/{{ tournament.id }}/generate_final" method="POST" class="mt-2 w-full"><button class="w-full bg-yellow-500 hover:bg-yellow-400 py-3 rounded-xl text-slate-900 font-black text-[10px] uppercase tracking-widest shadow-lg transition-colors">Vygenerovat Finále & o 3. místo</button></form>
                        </div>
                    {% endif %}
                    
                </div>
            </div>
        </div>
    </div>
</div>
</div>
</div>
<script>
let currentUid = {{ current_user.id if current_user else 0 }};
let currentMyTeams = {{ my_team_ids | tojson | safe if my_team_ids else '[]' }};
function filterMatches(type, val = null) {
    document.querySelectorAll('.filter-btn').forEach(b => {
        b.classList.remove('bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500', 'bg-orange-600/20');
        b.classList.add('bg-slate-900/50', 'theme-text-main', 'border-white/5');
        if(b.innerHTML.includes('Moje zápasy')) b.classList.add('text-orange-500', 'border-orange-500/30');
    });
    const currentBtn = event.currentTarget;
    currentBtn.classList.remove('bg-slate-900/50', 'theme-text-main', 'border-white/5', 'text-orange-500');
    if (type === 'mine') { currentBtn.classList.add('bg-orange-600/20', 'text-orange-500', 'border-orange-500/30'); }
    else { currentBtn.classList.add('bg-blue-600', 'text-white', 'shadow-lg', 'border-blue-500'); }
    const groupsGrid = document.getElementById('groups-grid');
    const playoffBracket = document.getElementById('playoff-bracket');
    const cards = document.querySelectorAll('.match-card');
    if(type === 'playoff') {
        groupsGrid.classList.add('hidden');
        playoffBracket.classList.remove('hidden');
    } else {
        playoffBracket.classList.add('hidden');
        groupsGrid.classList.remove('hidden');
        cards.forEach(card => {
            if(card.dataset.stage === 'playoffs') return;
            let show = false;
            if(type === 'all') show = true;
            else if(type === 'round' && card.dataset.round == val) show = true;
            else if(type === 'mine') {
                let t1 = parseInt(card.dataset.team1);
                let t2 = parseInt(card.dataset.team2);
                if(currentMyTeams.includes(t1) || currentMyTeams.includes(t2)) show = true;
            }
            card.style.display = show ? 'flex' : 'none';
        });
    }
}
{% if is_knockout_only and tournament.status != 'draft' %}
    document.addEventListener('DOMContentLoaded', () => { filterMatches('playoff'); });
{% endif %}
</script>"""
HOF_HTML = """<div class="max-w-2xl mx-auto"><div class="text-center mb-8"><h2 class="text-3xl font-black italic uppercase text-blue-500 tracking-tighter">SÍŇ SLÁVY</h2><p class="text-[10px] text-slate-500 font-bold uppercase tracking-widest mt-1">Globální rating power ranking a tipovačka</p></div><div class="navy-card overflow-hidden mb-8 shadow-xl"><table class="w-full text-left"><tr class="bg-white/5 text-[9px] uppercase font-black tracking-wider text-slate-400"><th class="p-4">Tým</th><th class="p-4 text-center text-yellow-500">ELO RATING</th></tr>{% for t in teams %}<tr class="border-b border-white/5 hover:bg-white/5"><td class="p-4 flex items-center gap-3"><div class="w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border border-white/10 cursor-pointer" style="background-color: {{t.color}}" onclick="openLogoModal('{{t.logo}}', '{{t.color}}')">{% if t.logo and 'static' in t.logo %}<img src="{{t.logo}}" class="w-full h-full object-contain p-1.5">{% else %}<span class="text-sm">{{t.logo}}</span>{% endif %}</div><span class="font-black uppercase text-xs text-white">{{t.name}}</span></td><td class="p-4 text-center font-black text-yellow-500 text-lg">{{t.elo}}</td></tr>{% endfor %}</table></div><div class="navy-card p-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest mb-4 text-center">Top 10 Sázkařů (Tipovačka)</h3><div class="space-y-2">{% for b in bettors %}<div class="flex justify-between items-center bg-slate-900/40 p-3 rounded-xl border border-white/5"><span class="font-black uppercase text-xs text-slate-300">{{loop.index}}. {{ b.username }}</span><span class="text-blue-400 font-black text-sm">{{ b.bet_points }} b</span></div>{% endfor %}</div></div></div>"""
CHAT_HTML = """<div class="max-w-xl mx-auto w-full flex flex-col h-[75vh]"><div class="flex items-center justify-between mb-4"><h2 class="text-xl font-black italic uppercase tracking-tighter text-blue-500">Zápasový Chat</h2></div><div class="navy-card p-4 shadow-2xl border border-white/5 flex-1 overflow-y-auto mb-4 flex flex-col gap-3" id="chat-box">{% for c in comments %}<div class="{% if c.username == current_user.username %}self-end bg-blue-600/10 border-blue-500/30 text-blue-200{% else %}self-start bg-slate-800/40 border-white/5 text-slate-300{% endif %} border p-3 rounded-2xl max-w-[85%] text-xs font-bold"><p class="text-[8px] font-black uppercase tracking-widest opacity-50 mb-1">{{ c.username }} • {{ c.created_at[-8:-3] }}</p><p class="text-sm font-bold">{{ c.text }}</p></div>{% endfor %}</div><form method="POST" class="flex gap-2"><input type="text" name="text" required placeholder="Napiš zprávu..." class="w-full rounded-xl p-4 text-sm font-bold bg-slate-900/50 text-white border border-white/5"><button class="bg-blue-600 px-6 rounded-xl text-white font-black"><i data-lucide="send" class="w-4 h-4"></i></button></form></div><script>window.onload = function() { var b = document.getElementById('chat-box'); b.scrollTop = b.scrollHeight; };</script>"""
JOIN_UI = """<div class="max-w-xl mx-auto py-6 sm:py-12 text-center w-full"><div class="mb-6 sm:mb-8 flex flex-col items-center"><span class="text-[8px] sm:text-[10px] font-bold uppercase px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 mb-2 inline-block tracking-widest">{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t_status, t_status) }}</span><h2 class="text-3xl sm:text-4xl font-black italic uppercase mb-1 tracking-tighter theme-text-main">{{ t_name }}</h2><p class="text-xs sm:text-sm text-slate-500">Pořadatel: {{ t_username }}</p><p class="text-[10px] sm:text-xs text-slate-500 flex items-center gap-1.5 mt-2"><i data-lucide="calendar-days" class="w-3.5 h-3.5 text-blue-500 opacity-70"></i> Zahájení: {{ format_date_cz(t_start_date) }}</p><p class="text-lg sm:text-xl font-bold theme-text-main flex items-center gap-2 sm:gap-2.5 mt-4 p-3 sm:p-4 navy-card border-l-4 border-l-blue-600"><i data-lucide="users" class="w-4 h-4 sm:w-5 sm:h-5 text-blue-500"></i> Registrováno: {{ t_registered_teams }} / {{ t_max_teams }} týmů</p></div><div class="navy-card p-5 sm:p-6 mb-8 sm:mb-10 shadow-2xl text-left">{% if my_teams %}<form method="POST" class="mb-6 sm:mb-8 pb-6 sm:pb-8 border-b border-white/5 space-y-3 sm:space-y-4"><h3 class="text-[9px] sm:text-[10px] font-black uppercase text-blue-500 tracking-widest flex items-center gap-2"><i data-lucide="check-circle" class="w-3 h-3 sm:w-4 sm:h-4"></i> Nasadit existující tým</h3><select name="master_id" class="w-full rounded-xl sm:rounded-2xl p-3 sm:p-4 text-sm sm:text-base font-bold bg-slate-900/50 cursor-pointer theme-text-main">{% for mt in my_teams %}<option value="{{ mt.id }}">{{ mt.name }}</option>{% endfor %}</select><button class="w-full bg-slate-800 hover:bg-slate-700 py-3 sm:py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs theme-text-main transition-colors flex items-center justify-center gap-1.5">Potvrdit nasazení <i data-lucide="chevron-right" class="w-3 h-3 sm:w-4 sm:h-4"></i></button></form>{% endif %}<h3 class="text-[9px] sm:text-[10px] font-black uppercase text-blue-500 tracking-widest mb-3 sm:mb-4 flex items-center gap-2"><i data-lucide="user-plus" class="w-3 h-3 sm:w-4 sm:h-4"></i> Registrace nového týmu</h3><div class="p-4 bg-slate-900/50 rounded-xl border border-white/5 text-center"><p class="text-xs text-slate-400 font-bold">Pro vytvoření nového týmu jdi do <a href="/teams/new" class="text-blue-500 underline">Týmového Manažera</a> a pak se vrať na tento odkaz.</p></div></div></div>"""
INVITE_HTML = """<div class="max-w-xl mx-auto py-8 sm:py-12 px-4 w-full flex flex-col items-center"><h2 class="text-3xl sm:text-4xl font-black italic uppercase mb-2 tracking-tighter theme-text-main text-center">Pozvánka</h2><p class="text-slate-500 text-sm font-bold uppercase tracking-widest text-center mb-8">{{ t_name }}</p><div class="bg-white p-4 sm:p-6 inline-block rounded-[2rem] sm:rounded-[3rem] shadow-2xl mb-8 border-4 border-blue-500/20 relative"><canvas id="qr-canvas"></canvas></div><div class="w-full navy-card p-4 sm:p-6 mb-8 relative border border-blue-500/20 shadow-xl"><p class="text-[9px] text-blue-400 uppercase font-black mb-3 tracking-widest">Přístupový odkaz pro hráče</p><div class="flex gap-2 items-center"><input type="text" id="invite-link-input" readonly value="{{ invite_url }}" class="w-full bg-slate-900/50 border border-white/5 rounded-xl p-3 sm:p-4 text-xs font-mono theme-text-main focus:outline-none"><button type="button" onclick="copyToClipboard(event)" class="bg-blue-600 hover:bg-blue-500 text-white p-3 sm:p-4 rounded-xl shadow-lg transition-all active:scale-95 shrink-0" title="Kopírovat"><i data-lucide="copy" class="w-5 h-5"></i></button></div></div><div class="w-full navy-card p-4 sm:p-6 mb-8 relative border border-white/5 shadow-xl"><p class="text-[9px] text-blue-400 uppercase font-black mb-3 tracking-widest">Přímé pozvání uživatele / hráče</p><form action="/tournament/{{ t_id }}/invite_user" method="POST" class="flex gap-2"><input type="text" name="username" required placeholder="Uživatelské jméno hráče" class="w-full bg-slate-900/50 border border-white/5 rounded-xl p-3 sm:p-4 text-xs font-bold theme-text-main focus:outline-none"><button type="submit" class="bg-blue-600 hover:bg-blue-500 text-white px-4 rounded-xl font-black uppercase text-[10px] tracking-widest shrink-0">Pozvat</button></form>{% if invited_players %}<div class="mt-4 pt-4 border-t border-white/5 space-y-2"><p class="text-[8px] text-slate-500 uppercase font-black tracking-widest">Stav odeslaných pozvánek</p>{% for p in invited_players %}<div class="flex justify-between items-center bg-slate-900/50 p-2 rounded-lg border border-white/5 text-[10px]"><span class="font-bold theme-text-main uppercase">{{ p.username }}</span><span class="px-2 py-0.5 rounded text-[8px] font-black uppercase {% if p.status == 'pending' %}bg-orange-500/10 text-orange-400 border border-orange-500/20{% else %}bg-green-500/10 text-green-400 border border-green-500/20{% endif %}">{{ p.status }}</span></div>{% endfor %}</div>{% endif %}</div><div class="flex flex-col sm:flex-row gap-3 w-full"><button type="button" onclick="shareLink()" class="flex-1 bg-green-600 hover:bg-green-500 text-white py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs shadow-lg flex items-center justify-center gap-2 transition-all active:scale-95 tracking-widest"><i data-lucide="share-2" class="w-4 h-4"></i>'] Sdílet</button><a href="/tournament/{{ t_id }}" class="flex-1 bg-slate-800 hover:bg-slate-700 text-white py-4 rounded-xl font-black uppercase text-[10px] sm:text-xs shadow-lg flex items-center justify-center gap-2 transition-all theme-text-main border border-white/5 tracking-widest"><i data-lucide="arrow-left" class="w-4 h-4"></i> Zpět</a></div><script>setTimeout(() => { new QRious({element: document.getElementById('qr-canvas'), value: '{{ invite_url }}', size: window.innerWidth < 400 ? 200 : 260, padding: 15, level: 'H', foreground: '#0f172a'}); }, 100); function copyToClipboard(e) { var copyText = document.getElementById("invite-link-input"); copyText.select(); copyText.setSelectionRange(0, 99999); navigator.clipboard.writeText(copyText.value).then(() => { const btn = e.currentTarget; const origHtml = btn.innerHTML; btn.innerHTML = '<i data-lucide="check" class="w-5 h-5"></i>'; lucide.createIcons(); setTimeout(() => { btn.innerHTML = origHtml; lucide.createIcons(); }, 2000); }).catch(() => alert('Zkopírujte odkaz manuálně')); } function shareLink() { if (navigator.share) { navigator.share({ title: 'THE CUP', text: 'Připoj se se svým týmem do turnaje {{ t_name }}!', url: '{{ invite_url }}', }).catch(console.error); } else { copyToClipboard({currentTarget: document.querySelector('button[title="Kopírovat"]')}); } }</script></div>"""
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


# >>> AI_BLOCK:SERVICES_CORE
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
