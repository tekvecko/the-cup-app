import re

with open("app.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Nahrazení starých generovacích a kompozičních funkcí za nové 2-fázové
old_helpers_regex = r'def compose_logo\(symbol_filename, team_name\):.*?def build_prompt\(team_name, style, colors\):.*?(?=\n# ==========================================)'

new_helpers = '''def build_logo_prompt(team_name, style, colors):
    mascot = infer_mascot(team_name)
    return f"Professional esports hockey logo symbol, {mascot}. Style: {STYLES.get(style, STYLES['clean'])}. Colors: {colors}. NO TEXT, NO WORDS. Clean vector art, isolated on a pure transparent background."

def build_text_prompt(team_name, style, colors):
    return f"Esports typography text logo, strictly spelling the exact word '{team_name}'. Bold, modern, aggressive 3D esports font. Colors: {colors}. NO MASCOTS, NO SYMBOLS, ONLY THE WORD '{team_name}'. Clean vector art, isolated on a pure transparent background."

def compose_two_phases(logo_file, text_file):
    import os, uuid
    from PIL import Image
    
    LOGO_DIR = os.path.join(os.getcwd(), 'static', 'generated_logos')
    img_logo = Image.open(os.path.join(LOGO_DIR, logo_file)).convert("RGBA")
    img_text = Image.open(os.path.join(LOGO_DIR, text_file)).convert("RGBA")
    
    img_logo.thumbnail((1024, 1024), Image.LANCZOS)
    
    # Oříznutí pouze středu s textem (odstraní přebytečné pozadí nad/pod nápisem)
    w, h = img_text.size
    img_text_cropped = img_text.crop((0, h//2 - 250, w, h//2 + 250))
    
    # Složení na vertikální plátno (Bez jakéhokoliv mazání barev Pythonem!)
    canvas = Image.new("RGBA", (1024, 1500), (0, 0, 0, 0))
    canvas.paste(img_logo, ((1024 - img_logo.width) // 2, 0))
    canvas.paste(img_text_cropped, (0, 1000))
    
    final_name = f"{uuid.uuid4().hex}.png"
    canvas.save(os.path.join(LOGO_DIR, final_name))
    return final_name
'''

code = re.sub(old_helpers_regex, new_helpers, code, flags=re.DOTALL)

# 2. Úprava try/except bloku v routě new_team tak, aby zavolal API dvakrát
old_try_regex = r'try:\n\s+prompt = build_prompt\(.*?\n\s+except Exception as e: flash\(pixazo_error\(e\)\)'

new_try = '''try:
                style = request.form.get("style", "clean")
                prompt_logo = build_logo_prompt(team_name, style, colors)
                prompt_text = build_text_prompt(team_name, style, colors)
                
                urls_logo = pixazo_generate(prompt_logo)
                file_logo = save_url(urls_logo[0])
                
                urls_text = pixazo_generate(prompt_text)
                file_text = save_url(urls_text[0])
                
                fn = compose_two_phases(file_logo, file_text)
                add_meta(fn, team_name, "TWO_PHASE", f"Logo: {prompt_logo}")
                
                session["pending_team_name"] = team_name
                flash("Dvoufázové AI logo (Symbol + Text) úspěšně vygenerováno.")
            except Exception as e: flash(pixazo_error(e))'''

code = re.sub(old_try_regex, new_try, code, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(code)
