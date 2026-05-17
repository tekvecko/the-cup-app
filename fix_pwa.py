import os

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Oprava chybového záchytávače (aby propouštěl HTTP 404 a nechytal je jako 500)
old_handler = '''@app.errorhandler(Exception)
def handle_exception(e):
    import traceback'''

new_handler = '''from werkzeug.exceptions import HTTPException
@app.errorhandler(Exception)
def handle_exception(e):
    if isinstance(e, HTTPException):
        return e
    import traceback'''

code = code.replace(old_handler, new_handler)

# 2. Přidání chybějících PWA rout na konec souboru
pwa_routes = '''
@app.route('/manifest.json')
def manifest():
    return jsonify({
        "name": "THE CUP Enterprise",
        "short_name": "THE CUP",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#020617",
        "theme_color": "#020617"
    })

@app.route('/sw.js')
def service_worker():
    js = "self.addEventListener('fetch', function(event) {});"
    return Response(js, mimetype='application/javascript')
'''

if "def manifest():" not in code:
    code += pwa_routes

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
