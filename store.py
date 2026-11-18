"""Shared SQLite storage and server-side role checks for the Streamlit prototype."""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from pathlib import Path

from engine import ModelError, calculate_project, validate_project
from project_ops import add_dm, group_data, record_decision
from workbook_io import import_workbook, scenario_json

ROOT = Path(__file__).resolve().parent
ITERATIONS = 390_000
DEMO_ACCOUNTS = (
    ("admin", "admin", None, "AdminDSS2026!"),
    ("dm1", "dm", "DM1", "DM1DSS2026!"),
    ("dm2", "dm", "DM2", "DM2DSS2026!"),
    ("dm3", "dm", "DM3", "DM3DSS2026!"),
)


class AccessError(ValueError):
    """The signed-in account may not perform this action."""


class ConflictError(ValueError):
    """An administrator tried to overwrite a newer project revision."""


def database_path():
    return Path(os.environ.get("DSS_DB_PATH", ROOT / "data" / "dss.sqlite3"))


def _connect():
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=10000")
    connection.execute("PRAGMA foreign_keys=ON")
    return connection


def initialize(seed_demo=False):
    with _connect() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("""CREATE TABLE IF NOT EXISTS state (
            id INTEGER PRIMARY KEY CHECK (id=1), revision INTEGER NOT NULL,
            project_json TEXT NOT NULL)""")
        connection.execute("""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY, role TEXT NOT NULL CHECK (role IN ('admin','dm')),
            dm_id TEXT, salt BLOB NOT NULL, password_hash BLOB NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,
            CHECK ((role='admin' AND dm_id IS NULL) OR (role='dm' AND dm_id IS NOT NULL)))""")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_user_per_dm ON users(dm_id) WHERE dm_id IS NOT NULL")
        if seed_demo:
            connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM state WHERE id=1").fetchone() is None:
            project = import_workbook()
            group_data(project)
            connection.execute("INSERT INTO state (id,revision,project_json) VALUES (1,0,?)",
                               (scenario_json(project),))
        if seed_demo and connection.execute("SELECT 1 FROM users LIMIT 1").fetchone() is None:
            project, _ = _state(connection)
            dm_ids = {dm["id"] for dm in project["decision_makers"]}
            if not {"DM1", "DM2", "DM3"}.issubset(dm_ids):
                raise ModelError("Data awal tidak memuat DM1, DM2, dan DM3 untuk akun demo.")
            for username, role, dm_id, password in DEMO_ACCOUNTS:
                salt, digest = _new_credentials(password)
                connection.execute(
                    "INSERT INTO users (username,role,dm_id,salt,password_hash) VALUES (?,?,?,?,?)",
                    (username, role, dm_id, salt, digest),
                )


def _hash_password(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)


def _new_credentials(password):
    if not isinstance(password, str) or len(password) < 10:
        raise ModelError("Kata sandi harus minimal 10 karakter.")
    salt = secrets.token_bytes(16)
    return salt, _hash_password(password, salt)


def _username(value):
    username = value.strip().casefold() if isinstance(value, str) else ""
    if not re.fullmatch(r"[a-z0-9_.-]{3,32}", username):
        raise ModelError("Nama pengguna harus 3–32 karakter: huruf kecil, angka, titik, garis bawah, atau tanda minus.")
    return username


def _public_user(row):
    return {"username": row["username"], "role": row["role"],
            "dm_id": row["dm_id"], "active": bool(row["active"])}


def _user(connection, username, role=None):
    row = connection.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if row is None or not row["active"] or (role is not None and row["role"] != role):
        raise AccessError("Akun tidak aktif atau tidak memiliki akses untuk tindakan ini.")
    return row


def admin_exists():
    initialize()
    with _connect() as connection:
        return connection.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone() is not None


def setup_admin(username, password):
    initialize()
    username = _username(username)
    salt, digest = _new_credentials(password)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM users WHERE role='admin' LIMIT 1").fetchone():
            raise AccessError("Admin sudah dibuat. Masuk menggunakan akun yang tersedia.")
        connection.execute("INSERT INTO users (username,role,dm_id,salt,password_hash) VALUES (?,'admin',NULL,?,?)",
                           (username, salt, digest))
    return username


def authenticate(username, password):
    initialize()
    username = _username(username)
    with _connect() as connection:
        row = connection.execute("SELECT * FROM users WHERE username=? AND active=1", (username,)).fetchone()
        if row is None or not hmac.compare_digest(_hash_password(password, row["salt"]), row["password_hash"]):
            raise AccessError("Nama pengguna atau kata sandi salah.")
        return _public_user(row)


def current_user(username):
    with _connect() as connection:
        return _public_user(_user(connection, username))


def _state(connection):
    row = connection.execute("SELECT revision, project_json FROM state WHERE id=1").fetchone()
    return json.loads(row["project_json"]), row["revision"]


def load_for_user(username):
    """Return full data to admins, or only the assigned DM data to DM accounts."""
    with _connect() as connection:
        user = _user(connection, username)
        project, revision = _state(connection)
    if user["role"] == "admin":
        return project, revision
    dm_id = user["dm_id"]
    dm = next((dm for dm in project["decision_makers"] if dm["id"] == dm_id), None)
    if dm is None:
        raise AccessError("Akun ini belum terhubung dengan DM yang aktif.")
    limited = copy.deepcopy(project)
    limited["decision_makers"] = [copy.deepcopy(dm)]
    limited["group"] = {"confirmed": {dm_id: bool(group_data(project)["confirmed"].get(dm_id))},
                        "discussion": [], "history": []}
    return limited, revision


def list_dm_accounts(admin_username):
    with _connect() as connection:
        _user(connection, admin_username, "admin")
        return [_public_user(row) for row in connection.execute(
            "SELECT * FROM users WHERE role='dm' ORDER BY dm_id")]


def create_dm_account(admin_username, dm_id, username, password):
    username = _username(username)
    salt, digest = _new_credentials(password)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _user(connection, admin_username, "admin")
        project, _ = _state(connection)
        if dm_id not in {dm["id"] for dm in project["decision_makers"]}:
            raise ModelError("DM tidak ditemukan.")
        try:
            connection.execute("INSERT INTO users (username,role,dm_id,salt,password_hash) VALUES (?,'dm',?,?,?)",
                               (username, dm_id, salt, digest))
        except sqlite3.IntegrityError as exc:
            raise ModelError("Nama pengguna atau DM sudah memiliki akun.") from exc
    return username


def add_dm_with_account(admin_username, name, username, password):
    """Create the DM and its login together, or change nothing on failure."""
    username = _username(username)
    salt, digest = _new_credentials(password)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _user(connection, admin_username, "admin")
        project, revision = _state(connection)
        candidate, dm_id = add_dm(project, name)
        calculate_project(candidate)
        try:
            connection.execute("INSERT INTO users (username,role,dm_id,salt,password_hash) VALUES (?,'dm',?,?,?)",
                               (username, dm_id, salt, digest))
        except sqlite3.IntegrityError as exc:
            raise ModelError("Nama pengguna sudah dipakai.") from exc
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(candidate),))
    return dm_id


def save_admin_project(admin_username, candidate, expected_revision):
    validate_project(candidate)
    calculate_project(candidate)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _user(connection, admin_username, "admin")
        _, revision = _state(connection)
        if revision != expected_revision:
            raise ConflictError("Proyek telah berubah di browser lain. Muat ulang halaman, lalu ulangi perubahan.")
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(candidate),))
        active_ids = [dm["id"] for dm in candidate["decision_makers"]]
        placeholders = ",".join("?" for _ in active_ids)
        connection.execute(f"DELETE FROM users WHERE role='dm' AND dm_id NOT IN ({placeholders})", active_ids)
    return revision + 1


def save_dm_ratings(username, ratings):
    """Update only the signed-in DM; merge with the latest shared project."""
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = _user(connection, username, "dm")
        project, revision = _state(connection)
        dm = next((dm for dm in project["decision_makers"] if dm["id"] == user["dm_id"]), None)
        if dm is None:
            raise AccessError("DM untuk akun ini tidak ditemukan.")
        dm["ratings"] = ratings
        group_data(project)["confirmed"].pop(user["dm_id"], None)
        validate_project(project)
        calculate_project(project)
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(project),))
    return revision + 1


def confirm_own_ratings(username):
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = _user(connection, username, "dm")
        project, revision = _state(connection)
        group_data(project)["confirmed"][user["dm_id"]] = True
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(project),))
    return revision + 1


def post_message(username, message):
    content = message.strip()
    if not content:
        raise ModelError("Catatan tidak boleh kosong.")
    from datetime import datetime
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = _user(connection, username)
        project, revision = _state(connection)
        group_data(project)["discussion"].append({
            "time": datetime.now().astimezone().isoformat(timespec="seconds"),
            "author": user["dm_id"] or "Admin", "message": content})
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(project),))
    return revision + 1


def save_decision(admin_username, note):
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _user(connection, admin_username, "admin")
        project, revision = _state(connection)
        candidate = record_decision(project, calculate_project(project), note)
        connection.execute("UPDATE state SET project_json=?, revision=revision+1 WHERE id=1",
                           (scenario_json(candidate),))
    return revision + 1


def change_password(username, old_password, new_password):
    salt, digest = _new_credentials(new_password)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        user = _user(connection, username)
        if not hmac.compare_digest(_hash_password(old_password, user["salt"]), user["password_hash"]):
            raise AccessError("Kata sandi lama salah.")
        connection.execute("UPDATE users SET salt=?, password_hash=? WHERE username=?",
                           (salt, digest, username))


def admin_reset_password(admin_username, dm_id, new_password):
    salt, digest = _new_credentials(new_password)
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        _user(connection, admin_username, "admin")
        row = connection.execute("SELECT username FROM users WHERE role='dm' AND dm_id=?", (dm_id,)).fetchone()
        if row is None:
            raise ModelError("DM belum memiliki akun.")
        connection.execute("UPDATE users SET salt=?, password_hash=? WHERE username=?",
                           (salt, digest, row["username"]))
