with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_block = '''def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image, ImageDraw
    
    LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
    
    def remove_white_bg_flood(img):
        ImageDraw.floodfill(img, (0, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (0, img.height-1), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, img.height-1), (255, 255, 255, 0), thresh=40)
        return img

    def remove_all_white(img):
        datas = img.getdata()
        newData = []
        for item in datas:
            r, g, b, a = item
            if r > 230 and g > 230 and b > 230: newData.append((255, 255, 255, 0))
            else: newData.append(item)
        img.putdata(newData)
        return img

    # 1. Zpracovat logo (Zmenšíme ho mírně, aby bylo místo pro překrytí textem)
    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_logo = remove_white_bg_flood(img_logo)
    img_logo.thumbnail((900, 900), Image.LANCZOS)
    
    # 2. Zpracovat text a oříznout ho přesně na okraje nápisu
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    img_text = remove_all_white(img_text)
    bbox = img_text.getbbox()
    if bbox: img_text = img_text.crop(bbox)
    
    # Natáhneme text na šířku 850px, aby dominoval přes celou šířku loga
    text_w = 850
    text_h = int(text_w * (img_text.height / img_text.width))
    img_text = img_text.resize((text_w, text_h), Image.LANCZOS)
    
    # 3. Zložit vrstvy: Plátno 1024x1024, text překrývá spodek loga
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    
    # Vložíme logo mírně nahoru
    logo_x = (1024 - img_logo.width) // 2
    logo_y = 20
    canvas.paste(img_logo, (logo_x, logo_y), img_logo)
    
    # Vložíme text přes spodek loga (cca 40 pixelů od dolního okraje plátna)
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
'''

# Najdeme kde staré funkce začínají a končí
idx1 = code.find("def compose_two_phases(logo_file, text_file):")
idx2 = code.find("# ==========================================\n# 3. HTML", idx1)

if idx1 != -1 and idx2 != -1:
    new_code = code[:idx1] + new_block + "\n" + code[idx2:]
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(new_code)
