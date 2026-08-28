import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_SOURCE = ROOT / "app.py"


class RuntimeRegressionTests(unittest.TestCase):
    def test_runtime_helpers_and_export_routes(self):
        probe = textwrap.dedent(
            """
            import importlib.util
            from pathlib import Path

            app_path = Path("app.py").resolve()
            spec = importlib.util.spec_from_file_location("the_cup_test_app", app_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            helper_names = (
                "pixazo_generate",
                "save_url",
                "compose_two_phases",
                "add_meta",
                "pixazo_error",
            )
            assert all(callable(getattr(module, name, None)) for name in helper_names)

            routes = {rule.rule for rule in module.app.url_map.iter_rules()}
            assert "/export/db" in routes
            assert "/export/csv/<int:t_id>" in routes

            client = module.app.test_client()
            unauthenticated = client.get("/export/db", follow_redirects=False)
            assert unauthenticated.status_code == 302

            with client.session_transaction() as flask_session:
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
            result = subprocess.run(
                [sys.executable, "-c", probe],
                cwd=temporary_path,
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
