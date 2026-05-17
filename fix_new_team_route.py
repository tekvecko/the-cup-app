import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# Zcela nová a čistá funkce new_team() s garantovaným 'return' na konci
NEW_ROUTE = '''@app.route('/teams/new', methods=['GET', 'POST'])
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

    # Zajištěný return pro GET metodu
    return render_ui(TEAM_NEW_HTML, styles=STYLES, active_page='teams')'''

# Pomocí RegEx nahradíme starou rozbitou funkci za novou
code = re.sub(r'@app\.route\(\'/teams/new\', methods=\[\'GET\', \'POST\'\]\)\n@login_required\ndef new_team\(\):.*?return render_ui[^\n]*', NEW_ROUTE, code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
