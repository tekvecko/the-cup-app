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
