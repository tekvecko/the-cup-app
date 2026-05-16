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
