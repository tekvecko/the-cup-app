import subprocess
import sys
import argparse

def run_cmd(cmd):
    result = subprocess.run(cmd, shell=True, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip())

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deploy", type=str, default="Auto deploy", help="Zpráva pro commit")
    args = parser.parse_args()

    print(f"[WATCHDOG] Zahajuji Auto-Deploy sekvenci: '{args.deploy}'")
    
    # Pridani zmen
    run_cmd("git add .")
    
    # Commit
    run_cmd(f'git commit -m "{args.deploy}"')
    
    # Získání aktuální větve
    try:
        branch = subprocess.check_output("git branch --show-current", shell=True).decode().strip()
    except subprocess.CalledProcessError:
        branch = "main"
        
    if not branch:
        branch = "main"
        
    print(f"[WATCHDOG] Odesílám kód do větve: {branch}")
    
    # Push do spravne vetve
    push_result = subprocess.run(f"git push origin {branch}", shell=True, text=True, capture_output=True)
    if push_result.stdout:
        print(push_result.stdout.strip())
    if push_result.stderr:
        print(push_result.stderr.strip())
        
    print(f"[WATCHDOG] Kód úspěšně odeslán na GitHub (větev {branch}). Render zahajuje build (pokud je větev sledována).")
