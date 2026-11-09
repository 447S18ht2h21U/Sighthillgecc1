"""Disposable SQLite configuration for isolated document integration tests."""
from config.settings import *

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
        "TEST": {"NAME": ":memory:"},
    }
}

MIGRATION_MODULES = {
    **globals().get("MIGRATION_MODULES", {}),
    "core": None,
}

DATABASE_ROUTERS = []

if DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
    raise RuntimeError("Document integration tests require isolated SQLite.")