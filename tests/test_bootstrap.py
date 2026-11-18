"""A fresh clone must be usable with the documented demo accounts."""
import os
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest

from store import AccessError, authenticate, change_password, load_for_user

APP = str(Path(__file__).resolve().parents[1] / "app.py")


class FreshCloneTests(unittest.TestCase):
    def test_demo_accounts_appear_once_and_existing_password_changes_survive(self):
        previous_path = os.environ.get("DSS_DB_PATH")
        try:
            with tempfile.TemporaryDirectory() as directory:
                database = Path(directory) / "dss.sqlite3"
                os.environ["DSS_DB_PATH"] = str(database)

                app = AppTest.from_file(APP, default_timeout=30).run()
                self.assertEqual(len(app.exception), 0)
                self.assertTrue(database.exists())
                self.assertEqual(len(app.get("form")), 1)
                self.assertEqual(app.get("form")[0].key, "login")

                for username, password, role, dm_id in [
                    ("admin", "AdminDSS2026!", "admin", None),
                    ("dm1", "DM1DSS2026!", "dm", "DM1"),
                    ("dm2", "DM2DSS2026!", "dm", "DM2"),
                    ("dm3", "DM3DSS2026!", "dm", "DM3"),
                ]:
                    account = authenticate(username, password)
                    self.assertEqual((account["role"], account["dm_id"]), (role, dm_id))

                dm3_project, _ = load_for_user("dm3")
                self.assertEqual([dm["id"] for dm in dm3_project["decision_makers"]], ["DM3"])

                change_password("dm1", "DM1DSS2026!", "changed-dm1-password")
                AppTest.from_file(APP, default_timeout=30).run()
                self.assertEqual(authenticate("dm1", "changed-dm1-password")["dm_id"], "DM1")
                with self.assertRaises(AccessError):
                    authenticate("dm1", "DM1DSS2026!")
        finally:
            if previous_path is None:
                os.environ.pop("DSS_DB_PATH", None)
            else:
                os.environ["DSS_DB_PATH"] = previous_path


if __name__ == "__main__":
    unittest.main()
