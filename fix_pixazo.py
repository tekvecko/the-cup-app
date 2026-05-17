import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_pixazo = """def pixazo_error(e):
    return f"AI API Info: {str(e)}"

def pixazo_generate(prompt, width=1024, height=1024, steps=4):
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("API klíč PIXAZO_API_KEY nenalezen na serveru.")
    payload = {"prompt": prompt, "num_steps": int(steps), "height": int(height), "width": int(width)}
    try:
        r = requests.post("https://gateway.pixazo.ai/flux-1-schnell/v1/getData", headers={"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": api_key}, json=payload, timeout=180)
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
        data = r.json()
        urls = []
        def walk(x):
            if isinstance(x, dict):
                for k, v in x.items():
                    if k in ("url", "image_url", "output_url", "media_url", "output") and isinstance(v, str) and v.startswith("http"): urls.append(v)
                    else: walk(v)
            elif isinstance(x, list):
                for i in x: walk(i)
        walk(data)
        if not urls:
            raise RuntimeError(f"Pixazo odpověď: {data}")
        return urls
    except Exception as e:
        raise RuntimeError(str(e))

def save_url(url):"""

code = re.sub(r'def pixazo_generate\(.*?\ndef save_url\(url\):', new_pixazo, code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
