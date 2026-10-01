import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
INSERT OR IGNORE INTO schema_version VALUES(1);
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
 password_hash TEXT NOT NULL, profile TEXT NOT NULL, created_at TEXT NOT NULL,
 demo INTEGER NOT NULL DEFAULT 0, demo_expires TEXT);
CREATE TABLE IF NOT EXISTS sessions(
 token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 expires_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checkins(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 day TEXT NOT NULL, data TEXT NOT NULL, UNIQUE(user_id,day));
CREATE TABLE IF NOT EXISTS goals(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, domain TEXT NOT NULL, target_date TEXT NOT NULL,
 next_step TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS habits(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, domain TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS habit_logs(
 habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
 day TEXT NOT NULL, PRIMARY KEY(habit_id,day));
CREATE TABLE IF NOT EXISTS ledger(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 day TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN ('income','expense')),
 amount_cents INTEGER NOT NULL CHECK(amount_cents>0), category TEXT NOT NULL, note TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS budgets(
 user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 category TEXT NOT NULL, amount_cents INTEGER NOT NULL CHECK(amount_cents>=0), PRIMARY KEY(user_id,category));
CREATE TABLE IF NOT EXISTS actions(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 day TEXT NOT NULL, key TEXT NOT NULL, domain TEXT NOT NULL, title TEXT NOT NULL,
 reason TEXT NOT NULL, minutes INTEGER NOT NULL, confidence TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', helpful INTEGER,
 UNIQUE(user_id,day,key));
CREATE TABLE IF NOT EXISTS experiments(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 title TEXT NOT NULL, option_a TEXT NOT NULL, option_b TEXT NOT NULL,
 start_date TEXT NOT NULL, days INTEGER NOT NULL, schedule TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active');
CREATE TABLE IF NOT EXISTS experiment_logs(
 experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
 day TEXT NOT NULL, focus INTEGER NOT NULL, completed INTEGER NOT NULL,
 minutes INTEGER NOT NULL, note TEXT NOT NULL, PRIMARY KEY(experiment_id,day));
CREATE TABLE IF NOT EXISTS notifications(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 key TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL,
 read INTEGER NOT NULL DEFAULT 0, UNIQUE(user_id,key));
CREATE TABLE IF NOT EXISTS feedback(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
 rating INTEGER NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS auth_attempts(key TEXT NOT NULL, at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS checkins_user_day ON checkins(user_id,day);
CREATE INDEX IF NOT EXISTS actions_user_day ON actions(user_id,day);
CREATE INDEX IF NOT EXISTS ledger_user_day ON ledger(user_id,day);
CREATE INDEX IF NOT EXISTS sessions_expiry ON sessions(expires_at);
CREATE INDEX IF NOT EXISTS auth_attempts_key ON auth_attempts(key,at);
"""


def path():
    return Path(os.getenv("EVOLVE_DB", "data/evolve.db"))


@contextmanager
def connect():
    target = path()
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    try:
        with con:
            yield con
    finally:
        con.close()


def initialize():
    with connect() as con:
        con.execute("PRAGMA journal_mode=WAL")
        con.executescript(SCHEMA)
