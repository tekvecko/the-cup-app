import re

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Definice chybějící šablony TEAM_EDIT_HTML
MISSING_TEMPLATE = r'''
TEAM_EDIT_HTML = """<div class="max-w-xl mx-auto py-6"><div class="flex gap-3 items-center mb-6"><a href="/teams" class="text-slate-500 p-2 -ml-2 hover:bg-white/5 rounded-lg"><i data-lucide="arrow-left"></i></a><h2 class="text-3xl font-black italic uppercase tracking-tighter theme-text-main">Editace</h2></div><div class="navy-card p-6"><div class="flex items-center gap-6 mb-8 bg-slate-900/50 p-4 rounded-2xl border border-white/5"><div class="w-24 h-24 rounded-2xl flex items-center justify-center text-4xl shadow-2xl cursor-pointer hover:scale-105 transition-transform" style="background-color: {{ team.color }}" onclick="openLogoModal('{{ team.logo }}', '{{ team.color }}')">{% if team.logo and 'static' in team.logo %}<img src="{{ team.logo }}" class="w-full h-full object-contain p-2">{% else %}{{ team.logo }}{% endif %}</div><div><h3 class="text-2xl font-black uppercase theme-text-main leading-tight">{{ team.name }}</h3><p class="text-yellow-500 font-black text-sm uppercase tracking-widest mt-1">ELO: {{ team.elo }}</p></div></div><form method="POST" action="/teams/edit/{{ team.id }}" class="space-y-5"><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Jméno</label><input type="text" name="name" value="{{ team.name }}" class="w-full p-4 rounded-xl font-bold bg-slate-900/50 text-white border border-white/10 mt-1" {{ 'disabled' if active }}></div><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Tag (Zkratka)</label><input type="text" name="tag" value="{{ team.tag if team.tag else '' }}" maxlength="4" class="w-full p-4 rounded-xl font-bold bg-slate-900/50 text-white border border-white/10 mt-1 uppercase" {{ 'disabled' if active }}></div><div><label class="text-[10px] font-black uppercase tracking-widest text-slate-500 ml-1">Barva pozadí</label><input type="color" name="color" value="{{ team.color }}" class="w-full h-12 rounded-xl border border-white/10 mt-1" {{ 'disabled' if active }}></div>{% if not active %}<button type="submit" class="w-full bg-blue-600 text-white p-5 rounded-xl font-black uppercase text-xs tracking-widest shadow-xl shadow-blue-900/40">Uložit změny</button>{% endif %}</form><div class="mt-6 border-t border-white/5 pt-6">{% if not active %}<form action="/teams/delete/{{ team.id }}" method="POST" onsubmit="event.preventDefault(); openModal('Opravdu smazat tento tým?', this);"><button type="submit" class="w-full bg-slate-800 text-red-500 p-4 rounded-xl font-black uppercase text-[10px] border border-red-500/20">Odstranit tým</button></form>{% else %}<p class="text-[10px] text-red-500 font-bold uppercase text-center"><i data-lucide="lock" class="w-3 h-3 inline"></i> Blokováno - tým je v turnaji</p>{% endif %}</div></div></div>"""
'''

if "TEAM_EDIT_HTML =" not in app_code:
    # Vložíme šablonu hned za definici TEAM_NEW_HTML uvnitř bloku TEMPLATES_VIEWS
    app_code = re.sub(r'(TEAM_NEW_HTML = """.*?<\/script>""")', r'\1' + MISSING_TEMPLATE, app_code, flags=re.DOTALL)
    
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(app_code)
    print("Šablona TEAM_EDIT_HTML úspěšně vložena.")
else:
    print("Šablona TEAM_EDIT_HTML již existuje.")
