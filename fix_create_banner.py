import re

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# 1. Přidání sloupce 'banner' do inicializace databáze
old_cols = "('elo', 'master_teams', '1200'), ('tag', 'master_teams', 'NULL')]"
new_cols = "('elo', 'master_teams', '1200'), ('tag', 'master_teams', 'NULL'), ('banner', 'tournaments', 'NULL')]"
if old_cols in app_code:
    app_code = app_code.replace(old_cols, new_cols)

# 2. Definuje novou CREATE šablonu jako konstantu do app_code (pokud tam není, nebo upraví stávající importovanou)
# Jelikož chceme jistotu, nacpeme novou HTML šablonu rovnou do kódu routy jako lokální proměnnou pro render.
NEW_CREATE_HTML = """<div class="max-w-xl mx-auto py-6 sm:py-8 text-center w-full"><div class="inline-block p-4 sm:p-5 bg-blue-600/10 rounded-2xl sm:rounded-3xl mb-4 sm:mb-6 border border-blue-500/20 text-blue-500 shadow-xl shadow-blue-500/10"><i data-lucide="trophy" class="w-10 h-10 sm:w-12 sm:h-12"></i></div><h2 class="text-3xl sm:text-4xl font-black italic uppercase leading-none mb-8 sm:mb-10 tracking-tighter theme-text-main">Vytvořit turnaj</h2><form method="POST" id="tournament-form" class="navy-card p-5 sm:p-8 space-y-4 sm:space-y-6 border border-blue-500/10 shadow-2xl text-left"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Název turnaje</label><input name="name" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 outline-none text-lg sm:text-xl font-black mt-1 theme-text-main bg-slate-900/50"></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Datum</label><input type="date" name="start_date" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm mt-1 theme-text-main bg-slate-900/50"></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Kapacita</label><input type="number" name="max_teams" value="8" min="2" max="32" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-sm font-bold mt-1 theme-text-main bg-slate-900/50"></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Viditelnost</label><select name="is_public" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="0">Privátní (QR)</option><option value="1">Veřejný</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Formát</label><select name="format" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="groups" selected>Skupiny + Playoff</option><option value="knockout">Čistý Pavouk</option></select></div></div><div class="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4"><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Skupiny</label><select name="group_count" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>Jedna tabulka</option><option value="2">Dvě skupiny (A, B)</option></select></div><div><label class="text-[9px] sm:text-[10px] font-black uppercase text-slate-500 ml-1 tracking-widest">Počet kol</label><select name="rounds" required class="w-full rounded-xl sm:rounded-2xl p-4 sm:p-5 text-xs sm:text-sm font-bold mt-1 cursor-pointer theme-text-main bg-slate-900/50"><option value="1" selected>1 Zápas</option><option value="2">2 Zápasy</option><option value="3">3 Zápasy</option></select></div></div><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Turnajový Banner</h3><div class="flex gap-2"><label class="flex-1 relative"><input type="radio" name="banner_type" value="standard" class="peer sr-only" checked><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="type" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Standardní Text</span></div></label><label class="flex-1 relative"><input type="radio" name="banner_type" value="ai" class="peer sr-only"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="image" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Banner 👑</span></div></label></div></div><button type="submit" id="submit-btn" class="w-full bg-blue-600 hover:bg-blue-500 py-5 sm:py-6 rounded-xl sm:rounded-2xl text-white font-black uppercase text-[10px] sm:text-sm tracking-widest shadow-xl shadow-blue-900/40 active:scale-95 transition-all flex justify-center items-center gap-2">Vytvořit a naplánovat <i data-lucide="chevron-right" class="w-4 h-4 sm:w-5 sm:h-5"></i></button></form></div><script>document.getElementById('tournament-form').onsubmit = function(e) { const isAi = document.querySelector('input[name="banner_type"]:checked').value === 'ai'; {% if not current_user.is_pro %} if (isAi) { e.preventDefault(); alert("AI Banner vyžaduje PRO Premium"); return; } {% endif %} const btn = document.getElementById('submit-btn'); if(isAi) { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Generuji AI Banner (až 30s)...'; } else { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Ukládám...'; } btn.classList.add('opacity-80', 'pointer-events-none'); lucide.createIcons(); };</script>"""

# 3. Nová routa /create, která renderuje tuto konkrétní novou šablonu
NEW_CREATE_ROUTE = '''@app.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    user = get_current_user()
    
    # Lokální šablona (odolná proti smazání templates.py)
    local_create_html = """''' + NEW_CREATE_HTML + '''"""
    
    if request.method == 'POST':
        if int(request.form['max_teams']) < 2: 
            flash("Minimálně 2 týmy pro inicializaci struktury.")
            return redirect(url_for('create'))
        
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
            if not user['is_pro']:
                flash("AI Banner vyžaduje PRO Premium.")
                return redirect(url_for('create'))
            try:
                prompt = f"Epic professional sports championship tournament wide landscape banner graphics for '{name}'. Dark navy blue background, modern tech aesthetics, luxury premium geometric glowing neon esports lines, elegant styling, championship cup trophy concept artwork. Strictly spelling '{name}'."
                urls = pixazo_generate(prompt, width=1024, height=512)
                fn = save_url(urls[0])
                banner_val = f"/static/generated_logos/{fn}"
            except Exception as e:
                flash(pixazo_error(e))
                return redirect(url_for('create'))
        
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute('INSERT INTO tournaments (user_id, name, start_date, is_public, max_teams, join_token, rounds, stage, group_count, format, banner) VALUES (?, ?, ?, ?, ?, ?, ?, "groups", ?, ?, ?)',
                        (session['user_id'], name, start_date, is_public, max_teams, uuid.uuid4().hex[:12], rounds, group_count, t_format, banner_val))
            new_id = cur.lastrowid
            conn.commit()
        flash("Turnaj úspěšně vytvořen.")
        return redirect(url_for('tournament_detail', t_id=new_id))
        
    return render_ui(local_create_html, active_page='create')'''

# Nahradíme starou funkci (pokud tam je nějaký zbytek) naši novou
if "def create():" in app_code:
    app_code = re.sub(r'@app\.route\(\'/create\', methods=\[\'GET\', \'POST\'\]\)\n@login_required\ndef create\(\):.*?return render_ui\([^)]*\)', NEW_CREATE_ROUTE, app_code, flags=re.DOTALL)
else:
    # Pokud tam funkce úplně chybí (což by vysvětlovalo chybu s neexistující stránkou), přidáme ji
    app_code += "\n\n" + NEW_CREATE_ROUTE

# 4. Úprava DETAIL_UI šablony uvnitř renderování detailu turnaje pro zobrazení banneru
NEW_DETAIL_HEADER_CODE = """<div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4"><div class="inline-block p-0 navy-card shadow-2xl relative w-full sm:w-auto min-w-[300px] overflow-hidden">{% if tournament.banner %}<div class="w-full border-b border-white/10 h-48 sm:h-64 relative bg-slate-950 flex items-center justify-center"><img src="{{ tournament.banner }}" class="w-full h-full object-cover opacity-90"><div class="absolute inset-0 bg-gradient-to-t from-slate-900 to-transparent"></div></div><div class="p-4 sm:p-5 relative z-10 -mt-8">{% if tournament.status == 'finished' and podium and podium.first %}<i data-lucide="crown" class="w-8 h-8 text-yellow-500 mx-auto mb-1 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]"></i><h3 class="text-[9px] text-yellow-500 font-black uppercase tracking-widest mb-1">Vítěz Turnaje</h3><h2 class="text-2xl font-black italic uppercase tracking-tighter text-yellow-500 mb-2">{{ podium.first.name }}</h2><div class="flex justify-center items-end gap-6 sm:gap-8 mt-4 border-t border-white/10 pt-4">{% if podium.second %}<div class="flex flex-col items-center opacity-80"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">2. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.second.color }}" onclick="openLogoModal('{{podium.second.logo}}', '{{podium.second.color}}')">{% if podium.second.logo and 'static' in podium.second.logo %}<img src="{{podium.second.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.second.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.second.name }}</span></div>{% endif %}{% if podium.third %}<div class="flex flex-col items-center opacity-70"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">3. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.third.color }}" onclick="openLogoModal('{{podium.third.logo}}', '{{podium.third.color}}')">{% if podium.third.logo and 'static' in podium.third.logo %}<img src="{{podium.third.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.third.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.third.name }}</span></div>{% endif %}</div>{% endif %}<p class="text-[10px] sm:text-xs text-slate-400 flex items-center justify-center gap-2 font-bold"><i data-lucide="calendar" class="w-3.5 h-3.5 text-blue-500"></i> {{ format_date_cz(tournament.start_date) }} | {{ 'Veřejný' if tournament.is_public else 'Privátní' }}</p></div>{% else %}<div class="p-4 sm:p-5">{% if tournament.status == 'finished' and podium and podium.first %}<i data-lucide="crown" class="w-12 h-12 sm:w-16 sm:h-16 text-yellow-500 mx-auto mb-2 drop-shadow-[0_0_15px_rgba(234,179,8,0.5)]"></i><h3 class="text-[10px] text-yellow-500 font-black uppercase tracking-widest mb-1">Vítěz Turnaje</h3><h2 class="text-3xl sm:text-5xl font-black italic uppercase tracking-tighter leading-none text-yellow-500 drop-shadow-md mb-4">{{ podium.first.name }}</h2><div class="flex justify-center items-end gap-6 sm:gap-8 mt-4 border-t border-white/10 pt-4">{% if podium.second %}<div class="flex flex-col items-center opacity-80"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">2. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.second.color }}" onclick="openLogoModal('{{podium.second.logo}}', '{{podium.second.color}}')">{% if podium.second.logo and 'static' in podium.second.logo %}<img src="{{podium.second.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.second.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.second.name }}</span></div>{% endif %}{% if podium.third %}<div class="flex flex-col items-center opacity-70"><span class="text-[9px] text-slate-400 font-black uppercase tracking-widest mb-1">3. místo</span><div class="w-8 h-8 rounded-lg flex items-center justify-center border border-white/10 mb-1 cursor-pointer hover:scale-110 transition-transform" style="background-color: {{ podium.third.color }}" onclick="openLogoModal('{{podium.third.logo}}', '{{podium.third.color}}')">{% if podium.third.logo and 'static' in podium.third.logo %}<img src="{{podium.third.logo}}" class="w-full h-full object-contain p-1">{% else %}<span class="text-sm">{{ podium.third.logo }}</span>{% endif %}</div><span class="text-[10px] font-black uppercase theme-text-main truncate max-w-[100px]">{{ podium.third.name }}</span></div>{% endif %}</div>{% else %}<i data-lucide="award" class="w-8 h-8 sm:w-10 sm:h-10 text-blue-500 mx-auto mb-1 sm:mb-2"></i><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter leading-none theme-text-main">{{ tournament.name }}</h2>{% endif %}<p class="text-[10px] sm:text-xs text-slate-500 flex items-center justify-center gap-2 mt-4 font-bold"><i data-lucide="calendar" class="w-3.5 h-3.5 text-blue-500"></i> {{ format_date_cz(tournament.start_date) }} | {{ 'Veřejný' if tournament.is_public else 'Privátní' }}</p></div>{% endif %}</div>"""

# Safely inject this header block back into DETAIL_UI in app.py if it exists there, or we can just ensure DETAIL_UI string gets replaced
if 'DETAIL_UI =' in app_code:
    app_code = re.sub(r'<div class="w-full text-center mb-6 sm:mb-8 flex flex-col items-center gap-4">.*?</div>\n"""', f'{NEW_DETAIL_HEADER_CODE}"""', app_code, flags=re.DOTALL)


with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

