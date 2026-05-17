with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_functions = '''def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image, ImageDraw
    
    LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
    
    def remove_white_bg(img):
        # Inteligentné Flood Fill zmazanie pozadia zo 4 rohov (tolerancia 40)
        ImageDraw.floodfill(img, (0, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (0, img.height-1), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, img.height-1), (255, 255, 255, 0), thresh=40)
        return img

    # 1. Otvoriť, zmazať pozadie a zmenšiť logo maskota
    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_logo = remove_white_bg(img_logo)
    img_logo.thumbnail((1024, 1024), Image.LANCZOS)
    
    # 2. Otvoriť, zmazať pozadie a orezať čistý text
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    img_text = remove_white_bg(img_text)
    w, h = img_text.size
    img_text_cropped = img_text.crop((0, h//2 - 250, w, h//2 + 250))
    
    # 3. Zložiť na seba na priehľadné plátno
    canvas = Image.new("RGBA", (1024, 1500), (0, 0, 0, 0))
    canvas.paste(img_logo, ((1024 - img_logo.width) // 2, 0), img_logo)
    canvas.paste(img_text_cropped, (0, 1000), img_text_cropped)
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name

def build_logo_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"Esports mascot icon without any letters, {mascot}. Style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. STRICTLY NO TEXT, NO WORDS. Blank solid white background."

def build_text_prompt(team_name, style, colors):
    return f"Typography graphic design, strictly spelling the exact word '{team_name}'. Bold aggressive 3D esports font. Colors: {colors}. NO MASCOTS, NO SYMBOLS. Blank solid white background."

'''

# Bezpečné nahradenie kódu
start_str = "def compose_two_phases(logo_file, text_file):"
end_str = "# ==========================================\n# 3. HTML"

start_idx = code.find(start_str)
end_idx = code.find(end_str)

if start_idx != -1 and end_idx != -1:
    new_code = code[:start_idx] + new_functions + code[end_idx:]
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(new_code)
