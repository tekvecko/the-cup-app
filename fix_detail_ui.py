import re

with open("app.py", "r", encoding="utf-8") as f:
    app_code = f.read()

# Zcela nová, kompletní definice DETAIL_UI, obsahující VŠECHNO
FULL_DETAIL_UI = '''DETAIL_UI = MATCH_MACRO + """<div id="live-sync-container" data-tid="{{ tournament.id }}">
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
'''

# Pomocí regulárního výrazu najdeme konec definice MATCH_MACRO
# Z app.py odstraníme veškerý bordel týkající se DETAIL_UI a nahradíme ho tímto čistým blokem
app_code = re.sub(r'DETAIL_UI = MATCH_MACRO \+ """.*?<\/script>"""', '', app_code, flags=re.DOTALL)
app_code = re.sub(r'DETAIL_UI = MATCH_MACRO \+ """.*?<\/script>\n"""', '', app_code, flags=re.DOTALL)

match_macro_def = r'(MATCH_MACRO = """.*?{% endmacro %}""")'
match = re.search(match_macro_def, app_code, flags=re.DOTALL)

if match:
    # Vložíme FULL_DETAIL_UI přímo za MATCH_MACRO
    app_code = app_code[:match.end()] + "\n\n" + FULL_DETAIL_UI + "\n\n" + app_code[match.end():]
else:
    # Pojistka pro případ nouze
    app_code += "\n\n" + FULL_DETAIL_UI

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)

