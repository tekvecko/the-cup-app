import os

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

pixazo_error_code = '''
def pixazo_error(e):
    msg = str(e)
    if "401" in msg: return "Pixazo API klíč byl odmítnut. Zkontrolujte systémovou proměnnou PIXAZO_API_KEY na Renderu."
    if "402" in msg: return "Nedostatek kreditů na Pixazo API."
    if "429" in msg: return "Limit požadavků Pixazo API dosažen (příliš mnoho dotazů)."
    if "list index" in msg: return "Pixazo API nevrátilo žádný obrázek (pravděpodobně chybí API klíč nebo služba neodpovídá)."
    return f"AI Generátor selhal: {msg}"
'''

if "def pixazo_error" not in code:
    code = code.replace("def get_current_user():", pixazo_error_code + "\ndef get_current_user():")

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
