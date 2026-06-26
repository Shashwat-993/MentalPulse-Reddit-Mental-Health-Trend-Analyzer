"""Configuration loader for MentalPulse.

Loads non-secret settings from ``config/config.yaml`` and secrets from the
environment (a local ``.env`` in dev). Two hard rules:

* Secrets are read ONLY from environment variables — never from YAML.
* The loader never logs or prints secret values.

Usage
-----
    from config.loader import load_config

    cfg = load_config()
    cfg.source.subreddits          # ["mentalhealth", "Anxiety", ...]
    cfg.path("bronze")             # absolute Path to the Bronze dir
    cfg.secrets.require("reddit_client_id", "reddit_client_secret")
    client_id = cfg.secrets.reddit_client_id
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


@dataclass(frozen=True)
class Secrets:
    """Secret values, sourced exclusively from environment variables.

    Every field is optional at load time; call :meth:`require` at the point of
    use to fail fast with a clear message when something needed is missing.
    """

    # Reddit (Phase 1)
    reddit_client_id: str | None = None
    reddit_client_secret: str | None = None
    reddit_user_agent: str | None = None
    # Anonymization (Phase 1)
    hash_salt: str | None = None
    # Anthropic / Claude API (Phase 3)
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    # Snowflake (Phase 1/2)
    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_pat: str | None = None  # Programmatic Access Token (sidesteps MFA)
    # Databricks (Phase 1/2)
    databricks_host: str | None = None
    databricks_token: str | None = None
    databricks_http_path: str | None = None

    @classmethod
    def from_env(cls) -> "Secrets":
        return cls(
            reddit_client_id=os.getenv("REDDIT_CLIENT_ID"),
            reddit_client_secret=os.getenv("REDDIT_CLIENT_SECRET"),
            reddit_user_agent=os.getenv("REDDIT_USER_AGENT"),
            hash_salt=os.getenv("MENTALPULSE_HASH_SALT"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL"),
            snowflake_account=os.getenv("SNOWFLAKE_ACCOUNT"),
            snowflake_user=os.getenv("SNOWFLAKE_USER"),
            snowflake_password=os.getenv("SNOWFLAKE_PASSWORD"),
            snowflake_pat=os.getenv("SNOWFLAKE_PAT"),
            databricks_host=os.getenv("DATABRICKS_HOST"),
            databricks_token=os.getenv("DATABRICKS_TOKEN"),
            databricks_http_path=os.getenv("DATABRICKS_HTTP_PATH"),
        )

    def require(self, *names: str) -> None:
        """Raise if any named secret is missing or empty.

        Example: ``cfg.secrets.require("anthropic_api_key", "anthropic_model")``
        """
        missing = [n for n in names if not getattr(self, n, None)]
        if missing:
            raise RuntimeError(
                "Missing required secret(s) — set them in your .env file: "
                + ", ".join(sorted(missing))
            )


def _to_namespace(obj: Any) -> Any:
    """Recursively convert dicts to SimpleNamespace for attribute access."""
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _to_namespace(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_to_namespace(v) for v in obj]
    return obj


class Config:
    """Parsed configuration.

    Top-level YAML sections are reachable as attributes (e.g. ``cfg.reddit``,
    ``cfg.rag``). Secrets are under ``cfg.secrets``. The original dict is
    available as ``cfg.raw``.
    """

    def __init__(
        self,
        raw: dict[str, Any],
        secrets: Secrets,
        repo_root: Path,
        config_path: Path,
    ) -> None:
        self._raw = raw
        self._settings = _to_namespace(raw)
        self.secrets = secrets
        self.repo_root = repo_root
        self.config_path = config_path

    @property
    def raw(self) -> dict[str, Any]:
        return self._raw

    def __getattr__(self, name: str) -> Any:
        # Only invoked when normal attribute lookup fails. Delegate to the
        # parsed YAML namespace; guard against recursion on private names.
        if name.startswith("_"):
            raise AttributeError(name)
        settings = self.__dict__.get("_settings")
        if settings is None:
            raise AttributeError(name)
        try:
            return getattr(settings, name)
        except AttributeError as exc:
            raise AttributeError(
                f"No config section or key named {name!r} in {self.config_path}"
            ) from exc

    def path(self, key: str) -> Path:
        """Resolve a relative path under the ``paths:`` section to an absolute Path."""
        rel = getattr(self._settings.paths, key)
        return (self.repo_root / rel).resolve()


def load_config(config_path: str | Path | None = None) -> Config:
    """Load ``.env`` (if present) and ``config.yaml`` into a :class:`Config`."""
    # Load .env from the repo root; silently a no-op if the file is absent.
    load_dotenv(REPO_ROOT / ".env")

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}

    return Config(
        raw=raw,
        secrets=Secrets.from_env(),
        repo_root=REPO_ROOT,
        config_path=path,
    )


if __name__ == "__main__":
    # Smoke check: prints non-secret config and whether each secret is SET
    # (never the value itself).
    cfg = load_config()
    print(f"Loaded config from: {cfg.config_path}")
    print(f"Project: {cfg.project.name} ({cfg.project.environment})")
    print(f"Subreddits: {cfg.source.subreddits}")
    print(f"Bronze path: {cfg.path('bronze')}")
    print("Secrets present:")
    for field_name in Secrets.__dataclass_fields__:
        present = "set" if getattr(cfg.secrets, field_name) else "MISSING"
        print(f"  - {field_name}: {present}")
