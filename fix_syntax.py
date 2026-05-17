with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# Chybový řádek (přesná kopie z tvého výpisu)
bad_line = "return render_ui(TEAM_NEW_HTML, styles=STYLES, active_page='teams'), styles=STYLES, active_page='teams', pending_team=pending_team)"

# Opravený čistý řádek
good_line = "    return render_ui(TEAM_NEW_HTML, styles=STYLES, active_page='teams', pending_team=pending_team)"

code = code.replace(bad_line, good_line)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
