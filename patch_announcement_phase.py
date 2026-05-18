import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Získání stávajícího bloku TEMPLATES_VIEWS a jeho úprava
match_templates = re.search(r'# >>> AI_BLOCK:TEMPLATES_VIEWS.*?# <<< AI_BLOCK:TEMPLATES_VIEWS', code, flags=re.DOTALL)
if match_templates:
    tpl_block = match_templates.group(0)
    
    # Úprava stavů v INDEX_HTML, SEASONS_HTML a JOIN_UI
    tpl_block = tpl_block.replace("{{ t.status }}", "{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t.status, t.status) }}")
    tpl_block = tpl_block.replace("{{ t_status }}", "{{ {'draft': 'Oznámení', 'active': 'Probíhá', 'finished': 'Ukončeno'}.get(t_status, t_status) }}")
    
    # Přidání vysvětlujícího panelu do DETAIL_UI
    draft_panel = """<div class="w-full lg:w-[380px] xl:w-[420px] lg:sticky lg:top-24 shrink-0">
        {% if tournament.status == 'draft' %}
            <div class="bg-blue-600/10 border border-blue-500/20 p-4 sm:p-5 rounded-2xl mb-6 text-center shadow-lg">
                <i data-lucide="megaphone" class="w-8 h-8 text-blue-500 mx-auto mb-2"></i>
                <h3 class="text-blue-500 font-black uppercase tracking-widest text-sm mb-1">Fáze: Oznámení turnaje</h3>
                <p class="text-slate-400 text-xs font-bold leading-relaxed">Probíhá nábor hráčů a registrace týmů. Turnaj se automaticky vygeneruje a odstartuje <strong class="text-blue-400">{{ format_date_cz(tournament.start_date) }}</strong>, nebo jej může organizátor kdykoliv spustit manuálně.</p>
            </div>"""
            
    tpl_block = tpl_block.replace("""<div class="w-full lg:w-[380px] xl:w-[420px] lg:sticky lg:top-24 shrink-0">
        {% if tournament.status == 'draft' %}""", draft_panel)
        
    code = code[:match_templates.start()] + tpl_block + code[match_templates.end():]

# 2. Nahrazení bloku ROUTES_TOURNAMENTS za verzi s auto-startem
NEW_ROUTES_TOURNAMENTS = '''# >>> AI_BLOCK:ROUTES_TOURNAMENTS
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
# <<< AI_BLOCK:ROUTES_TOURNAMENTS'''

code = re.sub(r'# >>> AI_BLOCK:ROUTES_TOURNAMENTS.*?# <<< AI_BLOCK:ROUTES_TOURNAMENTS', NEW_ROUTES_TOURNAMENTS, code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)

