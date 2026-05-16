#!/bin/bash
set -e

echo "[1/3] Aplikuji API Bridge do app.py..."

cp app.py app_backup.py

cat << 'API_CODE' >> app.py

# ==========================================
# 9. AI API BRIDGE (AUTONOMOUS CONTROL)
# ==========================================
def require_ai_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        key = request.headers.get('X-AI-API-KEY')
        if not key or key != os.getenv('AI_API_KEY', 'skynet_v1'):
            return jsonify({'error': 'Neautorizovaný přístup AI agenta'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/api/v1/status', methods=['GET'])
@require_ai_key
def api_status():
    return jsonify({
        'status': 'online',
        'timestamp': datetime.now().isoformat(),
        'db_size_kb': round(os.path.getsize(DB_PATH) / 1024, 2) if os.path.exists(DB_PATH) else 0
    })

@app.route('/api/v1/tournaments/create', methods=['POST'])
@require_ai_key
def api_create_tournament():
    data = request.json
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO tournaments (user_id, name, start_date, max_teams, join_token) VALUES (1, ?, ?, ?, ?)',
                (data['name'], data.get('start_date', datetime.now().strftime('%Y-%m-%d')), data.get('max_teams', 8), uuid.uuid4().hex[:12])
            )
            conn.commit()
            return jsonify({'status': 'success', 'tournament_id': cur.lastrowid}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/v1/teams/generate', methods=['POST'])
@require_ai_key
def api_generate_team():
    data = request.json
    team_name = data.get('team_name')
    colors = data.get('colors', 'navy, white')
    if not team_name: return jsonify({'error': 'Chybí team_name'}), 400
    
    try:
        prompt = build_prompt(team_name, "clean", colors)
        urls = pixazo_generate(prompt, width=1024, height=1024)
        symbol = save_url(urls[0])
        final_logo = compose_logo(symbol, team_name)
        logo_url = f"/static/generated_logos/{final_logo}"
        
        with get_db() as conn:
            conn.execute('INSERT INTO master_teams (user_id, name, logo, color, tag) VALUES (1, ?, ?, ?, ?)', 
                         (team_name, logo_url, '#0f172a', team_name[:4].upper()))
            conn.commit()
        return jsonify({'status': 'success', 'team_name': team_name, 'logo_url': logo_url}), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500
API_CODE

echo "[2/3] Vytvářím lokální AI Wrapper (ai_wrapper.py)..."
cat << 'WRAPPER' > ai_wrapper.py
import subprocess
import time
import sys

def run_and_monitor():
    print("[AI WRAPPER] Startuji THE CUP aplikaci...")
    process = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    crash_log = []
    try:
        for line in process.stdout:
            print(f"[THE CUP] {line}", end='')
            
            if "Traceback" in line or "Error:" in line or "Exception:" in line:
                crash_log.append(line)
            elif crash_log and line.strip().startswith("File"):
                crash_log.append(line)

            if len(crash_log) > 10:
                with open("ai_crash_context.log", "w") as f:
                    f.writelines(crash_log)
                print("\n[AI WRAPPER] ⚠️ Detekován pád! Log uložen pro AI analýzu do ai_crash_context.log")
                crash_log = []

    except KeyboardInterrupt:
        print("\n[AI WRAPPER] Ukončuji proces...")
        process.terminate()

if __name__ == "__main__":
    while True:
        run_and_monitor()
        print("[AI WRAPPER] Aplikace spadla. Restartuji za 5 vteřin...")
        time.sleep(5)
WRAPPER

echo "[3/3] Vytvářím Cloud Watchdog & Auto-Deploy (cloud_watchdog.py)..."
cat << 'WATCHDOG' > cloud_watchdog.py
import os
import subprocess
import requests

RENDER_API_KEY = os.getenv("RENDER_API_KEY", "tvuj_render_klic")
SERVICE_ID = os.getenv("RENDER_SERVICE_ID", "srv-cxxxxxxx")

def check_render_status():
    print("[WATCHDOG] Kontroluji stav Render kontejneru...")
    url = f"https://api.render.com/v1/services/{SERVICE_ID}/deploys"
    headers = {"Authorization": f"Bearer {RENDER_API_KEY}"}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            deploys = response.json()
            if deploys:
                latest = deploys[0]['deploy']
                print(f"[WATCHDOG] Poslední deploy: {latest['status']} (ID: {latest['id']})")
                return latest['status']
    except Exception as e:
        print(f"[WATCHDOG] Chyba při volání Render API: {e}")
    return "unknown"

def auto_deploy_fix(commit_message="AI Autonomous Fix"):
    print(f"[WATCHDOG] Zahajuji Auto-Deploy sekvenci: '{commit_message}'")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", commit_message], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        print("[WATCHDOG] Kód úspěšně odeslán na GitHub. Render zahajuje build.")
    except subprocess.CalledProcessError as e:
        print(f"[WATCHDOG] Chyba při Git operaci. Jsou vůbec nějaké změny k odeslání? Detail: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--deploy":
        msg = sys.argv[2] if len(sys.argv) > 2 else "AI Autonomous Fix"
        auto_deploy_fix(msg)
    else:
        status = check_render_status()
        if status == "build_failed":
            print("[WATCHDOG] 🚨 Render hlásí pád buildu. Čekám na zásah AI agenta...")
WATCHDOG

echo "=========================================="
echo "✅ AI Ekosystém úspěšně inicializován."
echo "=========================================="
