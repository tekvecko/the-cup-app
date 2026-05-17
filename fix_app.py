with open('app.py', 'r') as f:
    code = f.read()

# 1. Oprava NULL hodnot u log
code = code.replace("if 'static' in t.logo", "if t.logo and 'static' in t.logo")
code = code.replace("if 'static' in team.logo", "if team.logo and 'static' in team.logo")
code = code.replace("if 'static' in s.logo", "if s.logo and 'static' in s.logo")
code = code.replace("if 'static' in m.t1_logo", "if m.t1_logo and 'static' in m.t1_logo")
code = code.replace("if 'static' in m.t2_logo", "if m.t2_logo and 'static' in m.t2_logo")
code = code.replace("if 'static' in podium.first.logo", "if podium.first and podium.first.logo and 'static' in podium.first.logo")
code = code.replace("if 'static' in podium.second.logo", "if podium.second and podium.second.logo and 'static' in podium.second.logo")
code = code.replace("if 'static' in podium.third.logo", "if podium.third and podium.third.logo and 'static' in podium.third.logo")

# 2. Diagnostický Error Handler, který přepíše defaultní chování Flasku
error_handler = '''
@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    return f"<div style='background:#0f172a;color:#ef4444;padding:2rem;font-family:monospace;white-space:pre-wrap;line-height:1.5;margin:1rem;border-radius:1rem;border:2px solid #ef4444;'><h2>Kritická chyba uzlu THE CUP</h2><hr><br>{traceback.format_exc()}</div>", 500

if __name__ == '__main__':'''

code = code.replace("if __name__ == '__main__':", error_handler)

with open('app.py', 'w') as f:
    f.write(code)
