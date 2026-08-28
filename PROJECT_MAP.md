# Project Map - THE CUP (AI-SAFE PATCHABLE MONOLITH)
Tento soubor slouží jako přesný index architektonických bloků (`AI_BLOCK`) definovaných uvnitř hlavního monolitického souboru `app.py`. Umožňuje deterministické vyhledávání a bezpečné patchování kódu bez narušení stability aplikace.
## Seznam registrovaných bloků v `app.py`

| Kategorie | Název bloku (AI_BLOCK) | Odpovědnost a součásti |
| :--- | :--- | :--- |
| **Základy** | `IMPORTS` | Správa externích závislostí, knihoven a Flask frameworku. |
| **Základy** | `CONFIG` | Globální nastavení aplikace, tajné klíče, cesty k adresářům a slovník vizuálních stylů log (`STYLES`). |
| **Základy** | `DATABASE` | Správa databázového připojení se zapnutým WAL režimem (`PRAGMA journal_mode=WAL`). |
| **Základy** | `SCHEMA` | Inicializace schématu SQLite databáze, validace existujících sloupců a automatická migrace chybějících polí. |
| **Frontend** | `TEMPLATES_BASE` | Základní HTML/CSS/JS obálka (`BASE_UI`), globální styly, správa tmavého/světlého motivu a PWA skripty. |
| **Frontend** | `TEMPLATES_MACROS` | Opakovaně použitelné Jinja2 makro komponenty, primárně pro vykreslování karet zápasů (`render_match`). |
| **Frontend** | `TEMPLATES_VIEWS` | Statické a dynamické HTML šablony pro jednotlivá zobrazení (`WELCOME_HTML`, `INDEX_HTML`, `ACCOUNT_HTML`, `TEAMS_HTML`, `TEAM_NEW_HTML`, `TEAM_EDIT_HTML`, `CREATE_HTML`, `SEASONS_HTML`, `HOF_HTML`, `CHAT_HTML`, `JOIN_UI`, `INVITE_HTML`). |
| **Logika** | `SERVICES_CORE` | Základní systémová logika, pomocné vykreslovací funkce (`render_ui`), dekorátor autentizace (`login_required`) a formátování. |
| **Logika** | `SERVICES_TOURNAMENT` | Výpočet tabulek turnajů (`get_standings`), validace administrátorských oprávnění (`check_admin`) a detekce aktivních týmů. |
| **Logika** | `SERVICES_MATCH` | Matematika ELO ratingu po zápasech (`update_elo`) a zpracování predikcí/tipovaček uživatelů (`process_predictions`). |
| **Logika** | `SERVICES_AI_HELPERS` | Kompletní motor pro volání Pixazo API, ořezávání transparentnosti, flood-fill odstraňování bílého pozadí a finální 3D e-sport kompozici vrstev. |
| **Endpointy** | `SERVICES_AI` | Asynchronní API endpoint `/api/v1/teams/generate_two_phase` pro zpracování požadavků na pozadí pomocí AJAX. |
| **Endpointy** | `ROUTES_PWA` | Servisní routy pro progresivní webovou aplikaci (`/manifest.json`, `/sw.js`) a globální ošetření výjimek serveru. |
| **Endpointy** | `ROUTES_AUTH` | Autentizační vrstva pro přihlášení, registraci, odhlášení, změnu hesel a aktivaci PRO Premium účtu. |
| **Endpointy** | `ROUTES_TEAMS` | Flask endpointy pro správu, zápis, editaci a odstraňování týmů v registru. |
| **Endpointy** | `ROUTES_TOURNAMENTS` | Hlavní turnajový modul: vykreslení domovské stránky, archivu sezón, detailu turnaje, generování playoff pavouků, schvalování výsledků, zvaní a registrace týmů. |
| **Endpointy** | `ROUTES_MATCHES` | Správa zápasových stavů: časovače, zadávání výsledků, kontumace, resetování zápasů, uživatelské tipování a zápasový chat. |
| **Spuštění** | `SELF_CHECK` | Interní validační systém provádějící sanity check kritických cest a funkcí před spuštěním. |
| **Spuštění** | `MAIN` | Vstupní bod aplikace spouštějící Flask server na definovaném portu. |

