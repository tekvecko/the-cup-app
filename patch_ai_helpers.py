import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

AI_HELPERS = '''# >>> AI_BLOCK:SERVICES_AI_HELPERS
def load_meta():
    import os, json
    if not os.path.exists(META_FILE): return []
    try:
        with open(META_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return []

def add_meta(filename, team_name, mode, prompt, label=""):
    import json
    from datetime import datetime
    data = load_meta()
    data.append({"filename": filename, "team_name": team_name, "mode": mode, "label": label, "prompt": prompt, "created_at": datetime.now().isoformat(timespec="seconds"), "favorite": False})
    with open(META_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=2)

def infer_mascot(team_name):
    n = team_name.lower()
    for k, v in [("wolf", "ice wolf"), ("bear", "polar bear"), ("dragon", "ice dragon"), ("hawk", "ice hawk"), ("eagle", "ice eagle")]:
        if k in n: return v
    return "creative mascot"

def pixazo_error(e):
    msg = str(e)
    if "401" in msg: return "Pixazo API klíč byl odmítnut. Zkontrolujte systémovou proměnnou PIXAZO_API_KEY na Renderu."
    if "402" in msg: return "Nedostatek kreditů na Pixazo API."
    if "429" in msg: return "Limit požadavků Pixazo API dosažen (příliš mnoho dotazů)."
    if "API_PAYLOAD_DEBUG" in msg: return msg
    return f"AI Generátor selhal: {msg}"

def pixazo_generate(prompt, width=1024, height=1024, steps=4):
    import os, requests
    api_key = (app.config.get("PIXAZO_API_KEY") or os.getenv("PIXAZO_API_KEY", "")).strip()
    if not api_key: raise RuntimeError("API klíč PIXAZO_API_KEY nenalezen na serveru.")
    payload = {"prompt": prompt, "num_steps": int(steps), "height": int(height), "width": int(width)}
    try:
        r = requests.post("https://gateway.pixazo.ai/flux-1-schnell/v1/getData", headers={"Content-Type": "application/json", "Ocp-Apim-Subscription-Key": api_key}, json=payload, timeout=180)
        if r.status_code != 200: raise RuntimeError(f"HTTP {r.status_code}: {r.text}")
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
        if not urls: raise RuntimeError(f"API_PAYLOAD_DEBUG: {data}")
        return urls
    except Exception as e: raise RuntimeError(str(e))

def save_url(url):
    import uuid, requests, os
    fn = f"{uuid.uuid4().hex}.png"; r = requests.get(url, timeout=180); r.raise_for_status()
    with open(os.path.join(LOGO_DIR, fn), "wb") as f: f.write(r.content)
    return fn

def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image, ImageDraw
    def remove_white_bg_flood(img):
        ImageDraw.floodfill(img, (0, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (0, img.height-1), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, img.height-1), (255, 255, 255, 0), thresh=40)
        return img

    def remove_all_white(img):
        datas = img.getdata(); newData = []
        for item in datas:
            r, g, b, a = item
            if r > 230 and g > 230 and b > 230: newData.append((255, 255, 255, 0))
            else: newData.append(item)
        img.putdata(newData)
        return img

    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_logo = remove_white_bg_flood(img_logo)
    img_logo.thumbnail((900, 900), Image.LANCZOS)
    
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    img_text = remove_all_white(img_text)
    bbox = img_text.getbbox()
    if bbox: img_text = img_text.crop(bbox)
    
    text_w = 850
    text_h = int(text_w * (img_text.height / img_text.width))
    img_text = img_text.resize((text_w, text_h), Image.LANCZOS)
    
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    logo_x = (1024 - img_logo.width) // 2
    logo_y = 20
    canvas.paste(img_logo, (logo_x, logo_y), img_logo)
    
    text_x = (1024 - img_text.width) // 2
    text_y = 1024 - img_text.height - 40
    canvas.paste(img_text, (text_x, text_y), img_text)
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name

def build_logo_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"Esports team mascot graphic. Concept: {mascot} (can be animal, warrior, entity, or object). Style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. STRICTLY NO TEXT, NO LETTERS. Centered, solid bold outlines. Blank solid white background."

def build_text_prompt(team_name, style, colors):
    return f"Esports team typography logo. The exact word '{team_name}' in bold, thick, aggressive 3D esports font. Placed on a solid curved badge or banner background. Colors: {colors}. STRICTLY NO MASCOTS, NO ANIMALS, ONLY THE TEXT. Blank solid white background."
# <<< AI_BLOCK:SERVICES_AI_HELPERS
'''

if "def pixazo_generate" not in code:
    code = code.replace("# >>> AI_BLOCK:SERVICES_CORE", AI_HELPERS + "\n\n# >>> AI_BLOCK:SERVICES_CORE")
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(code)
    print("AI Helper funkce uspesne pridany do monolitu.")
else:
    print("Funkce jiz existuji.")
