# AI Changelog - THE CUP
Tento soubor dokumentuje historii zásahů, patchů a strukturálních změn provedených umělou inteligencí v rámci architektury AI-SAFE PATCHABLE MONOLITH.

| Datum | Upravený AI_BLOCK | Popis změny / Nová funkcionalita |
| :--- | :--- | :--- |
| 2026-05-17 | *SYSTEM* | Přechod na monolitickou architekturu rozdělenou do striktních `AI_BLOCK` regionů pro bezpečné patchování. |
| 2026-05-17 | `ROUTES_TEAMS`, `SERVICES_AI` | Implementace asynchronního AJAX generování log v AI Studiu s dvoufázovou syntézou (maskot + typografie). |
| 2026-05-17 | `TEMPLATES_VIEWS` | Přidání interaktivního progress baru s prediktivním odpočtem v sekundách a embed náhledem loga. |
| 2026-05-17 | `ROUTES_TOURNAMENTS`, `TEMPLATES_VIEWS` | Integrace turnajových AI bannerů (širokoúhlý poměr stran 1024x512) generovaných přes Pixazo API. |
| 2026-05-18 | `SERVICES_AI_HELPERS` | Oprava NameError chybějících pomocných AI funkcí a kompletní restaurování chybějící administrační logiky v turnajovém detailu. |
| 2026-05-18 | *SYSTEM* | Inicializace podpůrných souborů `PROJECT_MAP.md`, `CHANGELOG_AI.md` a testovací infrastruktury v `tests/`. |

2026-05-18 \| SCHEMA, TEMPLATES_VIEWS, ROUTES_TOURNAMENTS \| Přidána funkce přímého zvaní hráčů podle jména s přehledem pozvánek na hlavní nástěnce.
2026-05-18 | TEMPLATES_VIEWS, ROUTES_TOURNAMENTS | Fáze 'draft' přejmenována na 'Oznámení turnaje'. Přidán infobox do detailu a auto-start skript závislý na datu zahájení.
2026-05-18 | TEMPLATES_VIEWS | Oprava struktury if-else v DETAIL_UI: infobox 'Oznámení turnaje' již neskrývá logiku pro registraci týmů a generování odkazů.
2026-05-18 | TEMPLATES_VIEWS | Oprava NameError chybějící šablony TEAM_EDIT_HTML pro stránku editace týmu.
