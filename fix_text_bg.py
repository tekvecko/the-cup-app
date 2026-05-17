with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

new_compose_two_phases = '''def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image, ImageDraw
    
    LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
    
    def remove_white_bg_flood(img):
        # Inteligentné Flood Fill zmazanie pozadia zo 4 rohov pro logo maskota
        # (thresh=40 pro zachování detailů očí)
        ImageDraw.floodfill(img, (0, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, 0), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (0, img.height-1), (255, 255, 255, 0), thresh=40)
        ImageDraw.floodfill(img, (img.width-1, img.height-1), (255, 255, 255, 0), thresh=40)
        return img

    def remove_all_white(img):
        # Pro text zmatníme VŠECHNY bílé pixely s tolerancí
        # (protože prompt textu explicitně zakazuje symboly a grafiku)
        datas = img.getdata()
        newData = []
        for item in datas:
            # item je (R, G, B, A)
            r, g, b, a = item
            # Definovat bílou s tolerancí, např. r, g, b > 230
            if r > 230 and g > 230 and b > 230:
                # Udělat transparentní
                newData.append((255, 255, 255, 0))
            else:
                # Zachovat původní barvu
                newData.append(item)
        img.putdata(newData)
        return img

    # 1. Otvoriť, zmazať pozadie pro logo (flood fill) a zmenšiť
    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_logo = remove_white_bg_flood(img_logo)
    img_logo.thumbnail((1024, 1024), Image.LANCZOS)
    
    # 2. Otvoriť, zmazať pozadie pro text (all white) a orezať
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    img_text = remove_all_white(img_text) # NOVÁ METODA PRO TEXT
    w, h = img_text.size
    img_text_cropped = img_text.crop((0, h//2 - 250, w, h//2 + 250))
    
    # 3. Zložiť na seba na priehľadné plátno
    canvas = Image.new("RGBA", (1024, 1500), (0, 0, 0, 0))
    # Zachovat paste s alfa maskou pro text
    canvas.paste(img_logo, ((1024 - img_logo.width) // 2, 0), img_logo)
    canvas.paste(img_text_cropped, (0, 1000), img_text_cropped)
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name
'''

# Bezpečné nahradenie kódu
start_str = "def compose_two_phases(logo_file, text_file):"
end_str = "def build_logo_prompt(team_name, style, colors):"

start_idx = code.find(start_str)
end_idx = code.find(end_str)

if start_idx != -1 and end_idx != -1:
    new_code = code[:start_idx] + new_compose_two_phases + code[end_idx:]
    with open("app.py", "w", encoding="utf-8") as f:
        f.write(new_code)
