import os
import sys
def test_blocks_sanity():
    app_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app.py')
    if not os.path.exists(app_path):
        print("Chyba: app.py nebyl nalezen.")
        sys.exit(1)
        
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    required_blocks = [
        "IMPORTS", "CONFIG", "DATABASE", "SCHEMA", "TEMPLATES_BASE", 
        "TEMPLATES_MACROS", "TEMPLATES_VIEWS", "SERVICES_CORE", 
        "SERVICES_TOURNAMENT", "SERVICES_MATCH", "SERVICES_AI_HELPERS", 
        "SERVICES_AI", "ROUTES_PWA", "ROUTES_AUTH", "ROUTES_TEAMS", 
        "ROUTES_TOURNAMENTS", "ROUTES_MATCHES", "SELF_CHECK", "MAIN"
    ]
    
    missing = []
    for block in required_blocks:
        start_marker = f">>> AI_BLOCK:{block}"
        end_marker = f"<<< AI_BLOCK:{block}"
        if start_marker not in content or end_marker not in content:
            missing.append(block)
            
    if missing:
        print(f"Kritická chyba: V app.py chybí značky pro bloky: {', '.join(missing)}")
        sys.exit(1)
    else:
        print("Sanity Check OK: Všechny kritické AI_BLOCK regiony jsou přítomny a správně ohraničeny.")
        sys.exit(0)
if __name__ == '__main__':
    test_blocks_sanity()
