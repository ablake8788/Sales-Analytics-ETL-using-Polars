"""
core/config.py
--------------
Centralised, immutable application configuration.

Design patterns used:
  - Singleton  : AppConfig is instantiated once via AppConfig.load(); subsequent
                 calls return the cached instance.
  - Value Object / dataclass : All fields are read-only after construction.
  - Factory method : AppConfig.load(path) is the only entry point.
"""

from __future__ import annotations

import configparser
import sys
from dataclasses import dataclass
from pathlib import Path


# ──────────────────────────────────────────────
# Path helper
# ──────────────────────────────────────────────
def _base_dir() -> Path:
    if getattr(sys, "frozen", False):           # PyInstaller bundle
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_path(relative: str) -> Path:
    """Resolve a path relative to the project root (script or EXE)."""
    return _base_dir() / relative


# ──────────────────────────────────────────────
# Sub-config value objects
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class SqlConfig:
    driver: str
    server: str
    database: str
    username: str
    password: str
    trust_cert: str
    table_transactions: str = "dbo.SchwabTransactions"
    table_realized_gains: str = "dbo.SchwabSalesAnalytics_RealizedGains"
    table_summary: str = "dbo.SchwabSalesAnalytics_Summary"


# ──────────────────────────────────────────────
# Root config (Singleton)
# ──────────────────────────────────────────────
@dataclass(frozen=True)
class AppConfig:
    sql: SqlConfig

    # class-level cache (not stored on instance to keep frozen=True happy)
    _cache: "AppConfig | None" = None

    @classmethod
    def load(cls, config_file: str = "sales_analytics_etl.ini") -> "AppConfig":
        """
        Factory / Singleton.
        Reads the INI file once and caches the result.  Subsequent calls
        with the same path return the cached instance immediately.
        """
        if cls._cache is not None:
            return cls._cache

        path = resource_path(config_file)
        if not path.exists():
            raise FileNotFoundError(
                f"Config file not found: {path}\n"
                "Copy sales_analytics_etl.ini.template to "
                "sales_analytics_etl.ini and fill in real values."
            )

        parser = configparser.ConfigParser()
        if not parser.read(path):
            raise FileNotFoundError(f"Could not read config file: {path}")

        q = parser["sqlserver"]

        sql = SqlConfig(
            driver=q["driver"],
            server=q["server"],
            database=q["database"],
            username=q["username"],
            password=q["password"],
            trust_cert=q.get("trust_cert", "yes"),
            table_transactions=q.get("table_transactions", "dbo.SchwabTransactions"),
            table_realized_gains=q.get(
                "table_realized_gains", "dbo.SchwabSalesAnalytics_RealizedGains"
            ),
            table_summary=q.get("table_summary", "dbo.SchwabSalesAnalytics_Summary"),
        )

        instance = cls(sql=sql)
        cls._cache = instance      # cache it
        return instance

    @classmethod
    def reset(cls) -> None:
        """Clear cached singleton (useful in unit tests)."""
        cls._cache = None
