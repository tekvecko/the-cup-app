import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "app.py"


class RuntimeRegressionTests(unittest.TestCase):
    def test_seasons_template_renders_tournament_banner(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        match = re.search(r'SEASONS_HTML = """(.*?)"""', source, re.DOTALL)

        self.assertIsNotNone(match)
        template = match.group(1)
        self.assertIn("{{ t.banner or web_graphic }}", template)
        self.assertIn("this.onerror=null", template)
        self.assertIn("object-cover", template)

    def test_visual_polish_contract(self):
        source = APP_SOURCE.read_text(encoding="utf-8")

        for marker in (
            'id="meta-theme-color"',
            'class="app-body',
            'class="app-header',
            'class="app-main',
            'class="app-bottom-nav',
            'class="welcome-card',
            'class="hero-card',
            'class="stat-card',
            'class="tournament-card',
            "--shadow-card:",
            "env(safe-area-inset-bottom)",
            "@media (prefers-reduced-motion: reduce)",
        ):
            self.assertIn(marker, source)

        self.assertIn(
            "const swipeArea=document.getElementById('swipe-area');if(swipeArea)",
            source,
        )
        self.assertNotIn(
            "document.getElementById('swipe-area').addEventListener",
            source,
        )

    def test_bundled_database_and_brand_assets(self):
        source = APP_SOURCE.read_text(encoding="utf-8")
        self.assertIn("DB_FILENAME = 'the_cup_v31.db'", source)
        self.assertIn("THE_CUP_DATA_DIR", source)
        self.assertIn("'/static/branding_logo.svg'", source)
        self.assertIn("'/static/web_graphic.svg'", source)

        database_path = ROOT / "the_cup_v31.db"
        self.assertTrue(database_path.is_file())
        self.assertEqual(database_path.read_bytes()[:16], b"SQLite format 3\\x00")

        for filename in ("branding_logo.svg", "web_graphic.svg"):
            asset_path = ROOT / "static" / filename
            self.assertTrue(asset_path.is_file())
            svg_root = ElementTree.parse(asset_path).getroot()
            self.assertTrue(svg_root.tag.endswith("svg"))

    def test_runtime_helpers_and_export_routes(self):
        probe = textwrap.dedent(
            """
            import importlib.util
            import os
            from pathlib import Path

            app_path = Path("app.py").resolve()
            spec = importlib.util.spec_from_file_location("the_cup_test_app", app_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            runtime_root = Path(os.environ["THE_CUP_DATA_DIR"]).resolve()
            assert Path(module.DB_PATH).parent == runtime_root
            assert module.app.config["DB_NAME"] == "the_cup_v31.db"
            assert Path(module.DB_PATH).is_file()
            assert Path(module.LOGO_DIR).parent == runtime_root

            with module.get_db() as database:
                assert database.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert database.execute("SELECT COUNT(*) FROM users").fetchone()[0] >= 8
                assert database.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0] >= 6
                assert database.execute("SELECT COUNT(*) FROM master_teams").fetchone()[0] >= 13

            helper_names = (
                "get_current_user",
                "login_required",
                "log_match_action",
                "get_local_ip",
                "format_date_cz",
                "pixazo_generate",
                "save_url",
                "compose_two_phases",
                "add_meta",
                "pixazo_error",
            )
            assert all(callable(getattr(module, name, None)) for name in helper_names)
            assert module.format_date_cz("2026-08-29") == "29.08.2026"

            routes = {rule.rule for rule in module.app.url_map.iter_rules()}
            assert "/export/db" in routes
            assert "/export/csv/<int:t_id>" in routes
            assert "/static/generated_logos/<path:filename>" in routes

            endpoint, _ = module.app.url_map.bind("localhost").match(
                "/static/generated_logos/probe.png"
            )
            assert endpoint == "generated_logo_file"

            client = module.app.test_client()

            with module.app.test_request_context("/render-probe"):
                rendered = module.render_ui(
                    '<section id="render-probe">{{ probe_value }}</section>',
                    probe_value="page-content-ok",
                    hide_nav=True,
                )
            assert 'id="render-probe"' in rendered
            assert "page-content-ok" in rendered
            assert "CONTENT_PLACEHOLDER" not in rendered

            unauthenticated = client.get("/export/db", follow_redirects=False)
            assert unauthenticated.status_code == 302
            assert unauthenticated.headers["Location"].endswith("/account")

            with client.session_transaction() as flask_session:
                assert flask_session["next_url"].endswith("/export/db")
                flask_session["user_id"] = 1

            database_export = client.get("/export/db")
            assert database_export.status_code == 200
            assert "attachment" in database_export.headers["Content-Disposition"]
            database_export.close()

            csv_export = client.get("/export/csv/999")
            assert csv_export.status_code == 200
            assert csv_export.content_type.startswith("text/csv")
            assert b"Poradi" in csv_export.data

            module.pixazo_generate = lambda *args, **kwargs: [
                "https://example.invalid/image.png"
            ]
            module.save_url = lambda url: "phase.png"
            module.compose_two_phases = lambda logo, text: "final.png"
            module.add_meta = lambda *args, **kwargs: None

            generated = client.post(
                "/api/v1/teams/generate_two_phase",
                data={
                    "team_name": "Regression Team",
                    "prompt_logo": "logo",
                    "prompt_text": "text",
                },
            )
            assert generated.status_code == 200
            assert generated.get_json()["logo_url"].endswith("/final.png")
            """
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            shutil.copy2(APP_SOURCE, temporary_path / "app.py")
            shutil.copy2(ROOT / "the_cup_v31.db", temporary_path / "the_cup_v31.db")
            shutil.copytree(ROOT / "static", temporary_path / "static")
            shutil.copytree(ROOT / "data", temporary_path / "data")

            runtime_root = temporary_path / "runtime"
            environment = os.environ.copy()
            environment["THE_CUP_DATA_DIR"] = str(runtime_root)

            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=temporary_path,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(
            result.returncode,
            0,
            msg=f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )


if __name__ == "__main__":
    unittest.main()
