import re

# ==========================================
# 1. ÚPRAVA HTML ŠABLONY (templates.py)
# ==========================================
with open("templates.py", "r", encoding="utf-8") as f:
    tpl_code = f.read()

NEW_TEAM_NEW_HTML = """<div class="max-w-xl mx-auto py-6 w-full"><div class="flex items-center gap-3 mb-6"><a href="/teams" class="text-slate-500 p-2 -ml-2 hover:bg-white/5 rounded-lg"><i data-lucide="arrow-left"></i></a><h2 class="text-2xl sm:text-3xl font-black italic uppercase tracking-tighter theme-text-main">Nový tým</h2></div><div class="navy-card p-6 shadow-2xl border-white/5 mb-8"><form method="POST" action="/teams/new" class="space-y-6" id="team-form"><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Základní identifikace</h3><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Jméno týmu</label><input name="name" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main"></div><div class="grid grid-cols-2 gap-4"><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Zkratka (Tag)</label><input name="tag" maxlength="4" required class="w-full rounded-xl p-3 text-sm font-bold bg-slate-900/50 theme-text-main uppercase"></div><div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Týmová barva</label><input type="color" name="color" value="#3b82f6" class="w-full h-11 rounded-xl p-0.5 outline-none cursor-pointer bg-slate-900/50 border border-white/5"></div></div></div><div class="space-y-4"><h3 class="text-[10px] font-black uppercase text-blue-500 tracking-widest border-b border-white/5 pb-2">Zdroj loga</h3><div class="flex gap-2"><label class="flex-1 relative"><input type="radio" name="logo_type" value="emoji" class="peer sr-only" checked onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-blue-500 peer-checked:bg-blue-600/10 peer-checked:text-blue-500 transition-all"><i data-lucide="smile" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">Ikona / Znak</span></div></label><label class="flex-1 relative"><input type="radio" name="logo_type" value="ai" class="peer sr-only" onchange="toggleLogoType()"><div class="p-3 text-center rounded-xl border border-white/10 bg-slate-900/30 cursor-pointer peer-checked:border-yellow-500 peer-checked:bg-yellow-500/10 peer-checked:text-yellow-500 transition-all relative overflow-hidden">{% if not current_user.is_pro %}<div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center"><i data-lucide="lock" class="w-4 h-4 text-yellow-500"></i></div>{% endif %}<i data-lucide="sparkles" class="w-5 h-5 mx-auto mb-1 opacity-70"></i><span class="text-[10px] font-black uppercase tracking-widest">AI Studio 👑</span></div></label></div><div id="section-emoji" class="block space-y-2"><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vyber symbol</label><input type="hidden" name="emoji_logo" id="team-logo" value="⚽"><div class="grid grid-cols-5 sm:grid-cols-8 gap-2 p-2 bg-slate-900/50 rounded-xl max-h-40 overflow-y-auto border border-white/5 shadow-inner">{% set emojis = ['⚽','🏒','🏀','🏐','🏈','🎾','🎱','🏓','🥊','🥋','🐅','🦅','🦈','🐺','🐻','🦁','🐉','🐍','⚡','🔥','⭐','☠️','💎','🛡️'] %}{% for e in emojis %}<button type="button" onclick="document.getElementById('team-logo').value='{{ e }}'; document.querySelectorAll('.emoji-btn').forEach(b=>b.style.opacity=0.4); this.style.opacity=1;" class="emoji-btn text-2xl p-2 rounded-xl bg-white/5 hover:bg-white/10 transition-all opacity-40">{{ e }}</button>{% endfor %}</div></div><div id="section-ai" class="hidden space-y-4 pt-2">{% if not current_user.is_pro %}<div class="text-center p-4 bg-yellow-500/10 border border-yellow-500/20 rounded-xl"><p class="text-xs font-bold text-yellow-500 mb-2">Tato funkce vyžaduje PRO Premium</p><a href="/account" class="inline-block bg-yellow-500 text-slate-900 px-4 py-2 rounded-lg font-black text-[10px] uppercase">Aktivovat</a></div>{% else %}<div><label class="text-[9px] font-black uppercase text-slate-500 ml-1">Vizuální Styl loga</label><select name="style" class="w-full rounded-xl p-3 text-xs font-bold bg-slate-900/50 theme-text-main mt-1">{% for k,v in styles.items() %}<option value="{{k}}">{{k}}</option>{% endfor %}</select></div><div class="grid grid-cols-3 gap-2"><div class="text-center cursor-pointer" onclick="openColorPicker('body')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Tělo</label><div id="swatch-body" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #ffffff;"></div><input type="hidden" name="color_body" id="input-body" value="White"></div><div class="text-center cursor-pointer" onclick="openColorPicker('outline')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Obrys</label><div id="swatch-outline" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #020617;"></div><input type="hidden" name="color_outline" id="input-outline" value="Black"></div><div class="text-center cursor-pointer" onclick="openColorPicker('fill')"><label class="text-[9px] font-black uppercase text-slate-500 mb-1 block">Výplň</label><div id="swatch-fill" class="w-full h-10 rounded-xl border border-white/10 shadow-inner" style="background-color: #3b82f6;"></div><input type="hidden" name="color_fill" id="input-fill" value="Blue"></div></div>{% endif %}</div></div><button type="submit" id="submit-btn" class="w-full bg-blue-600 hover:bg-blue-500 transition-colors py-4 rounded-xl text-white font-black uppercase text-[10px] tracking-widest shadow-xl shadow-blue-900/40">Zapsat do registru</button></form></div></div><div id="custom-color-picker" class="fixed inset-0 z-[3000] bg-slate-950/90 backdrop-blur-md hidden flex flex-col items-center justify-center p-4 opacity-0 transition-opacity"><div class="navy-card p-6 w-full max-w-sm shadow-2xl border-white/10 relative"><button type="button" onclick="closeColorPicker()" class="absolute top-4 right-4 text-slate-500 hover:text-white"><i data-lucide="x" class="w-5 h-5"></i></button><h3 class="text-lg font-black uppercase italic mb-4 theme-text-main text-center">Vyber barvu</h3><div class="grid grid-cols-5 gap-3" id="color-grid"></div></div></div><script>function toggleLogoType() { const isAi = document.querySelector('input[name="logo_type"]:checked').value === 'ai'; document.getElementById('section-emoji').style.display = isAi ? 'none' : 'block'; document.getElementById('section-ai').style.display = isAi ? 'block' : 'none'; } document.getElementById('team-form').onsubmit = function(e) { const isAi = document.querySelector('input[name="logo_type"]:checked').value === 'ai'; {% if not current_user.is_pro %} if (isAi) { e.preventDefault(); alert("AI Logo vyžaduje PRO Premium"); return; } {% endif %} const btn = document.getElementById('submit-btn'); if(isAi) { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Generuji AI Logo (až 30s)...'; } else { btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin inline-block mr-2"></i> Ukládám...'; } btn.classList.add('opacity-80', 'pointer-events-none'); lucide.createIcons(); }; const palette = [{name: 'White', hex: '#ffffff'}, {name: 'Silver', hex: '#94a3b8'}, {name: 'Gray', hex: '#475569'}, {name: 'Black', hex: '#020617'}, {name: 'Navy', hex: '#0f172a'},{name: 'Blue', hex: '#3b82f6'}, {name: 'Cyan', hex: '#06b6d4'}, {name: 'Teal', hex: '#14b8a6'}, {name: 'Green', hex: '#22c55e'}, {name: 'Lime', hex: '#84cc16'},{name: 'Yellow', hex: '#eab308'}, {name: 'Orange', hex: '#f97316'}, {name: 'Red', hex: '#ef4444'}, {name: 'Rose', hex: '#f43f5e'}, {name: 'Pink', hex: '#ec4899'},{name: 'Purple', hex: '#a855f7'}, {name: 'Violet', hex: '#8b5cf6'}, {name: 'Indigo', hex: '#6366f1'}, {name: 'Brown', hex: '#78350f'}, {name: 'Gold', hex: '#ca8a04'}]; let currentTarget = null; function openColorPicker(target) { currentTarget = target; const grid = document.getElementById('color-grid'); grid.innerHTML = ''; palette.forEach(c => { const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'w-full aspect-square rounded-full border-2 border-white/10 shadow-lg transition-transform hover:scale-110 active:scale-95'; btn.style.backgroundColor = c.hex; btn.onclick = () => selectCustomColor(c.name, c.hex); grid.appendChild(btn); }); const modal = document.getElementById('custom-color-picker'); modal.classList.remove('hidden'); void modal.offsetWidth; modal.classList.remove('opacity-0'); lucide.createIcons(); } function closeColorPicker() { const modal = document.getElementById('custom-color-picker'); modal.classList.add('opacity-0'); setTimeout(() => modal.classList.add('hidden'), 300); } function selectCustomColor(name, hex) { if(currentTarget) { document.getElementById('swatch-' + currentTarget).style.backgroundColor = hex; document.getElementById('input-' + currentTarget).value = name; } closeColorPicker(); } setTimeout(() => document.querySelector('.emoji-btn').click(), 100);</script>"""

tpl_code = re.sub(r'TEAM_NEW_HTML = """.*?"""\n', f'TEAM_NEW_HTML = """{NEW_TEAM_NEW_HTML}"""\n', tpl_code, flags=re.DOTALL)

with open("templates.py", "w", encoding="utf-8") as f:
    f.write(tpl_code)

# ==========================================
# 2. ÚPRAVA LOGIKY (app.py)
# ==========================================
with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

NEW_ROUTE_LOGIC = '''@app.route('/teams/new', methods=['GET', 'POST'])
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
            if not user['is_pro']:
                flash("AI generátor vyžaduje PRO Premium.")
                return redirect(url_for('new_team'))
            
            colors = f"Main Body: {request.form.get('color_body','White')}, Outline: {request.form.get('color_outline','Black')}, Fill/Accents: {request.form.get('color_fill','Blue')}"
            style = request.form.get("style", "clean")
            
            try:
                prompt_logo = build_logo_prompt(name, style, colors)
                prompt_text = build_text_prompt(name, style, colors)
                
                urls_logo = pixazo_generate(prompt_logo)
                file_logo = save_url(urls_logo[0])
                
                urls_text = pixazo_generate(prompt_text)
                file_text = save_url(urls_text[0])
                
                fn = compose_two_phases(file_logo, file_text)
                add_meta(fn, name, "TWO_PHASE", f"Logo: {prompt_logo}")
                logo_val = f"/static/generated_logos/{fn}"
                
            except Exception as e:
                flash(pixazo_error(e))
                return redirect(url_for("new_team"))
        else:
            logo_val = request.form.get("emoji_logo", "⚽")
            
        try:
            with get_db() as conn:
                conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (?, ?, ?, ?, ?)', 
                             (session['user_id'], name, logo_val, main_color, tag))
                conn.commit()
            flash("Tým byl úspěšně zapsán do registru.")
            return redirect(url_for('teams'))
        except sqlite3.IntegrityError:
            flash("Tento tým je již v registru zapsán.")
            return redirect(url_for("new_team"))

    return render_ui(TEAM_NEW_HTML, styles=STYLES, active_page='teams')'''

# Nahrazení celé staré routy new_team
app_code = re.sub(r'@app\.route\(\'/teams/new\'.*?return render_ui\(TEAM_NEW_HTML.*?\)', NEW_ROUTE_LOGIC, app_code, flags=re.DOTALL)

# Smazání routy use_logo (už ji nepotřebujeme, vše dělá new_team)
app_code = re.sub(r'@app\.route\(\'/teams/use/<filename>.*?\n\n@app\.route', '\n@app.route', app_code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
