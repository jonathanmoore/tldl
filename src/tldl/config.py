import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bearer_token: str
    webshare_username: str | None
    webshare_password: str | None
    webshare_locations: tuple[str, ...]
    port: int
    log_level: str


def load_settings() -> Settings:
    token = os.environ.get("MCP_BEARER_TOKEN", "").strip()
    if not token:
        raise SystemExit(
            "MCP_BEARER_TOKEN must be set. Generate one with:\n"
            '  python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
        )
    locs = os.environ.get("WEBSHARE_PROXY_LOCATIONS", "").strip()
    return Settings(
        bearer_token=token,
        webshare_username=os.environ.get("WEBSHARE_PROXY_USERNAME") or None,
        webshare_password=os.environ.get("WEBSHARE_PROXY_PASSWORD") or None,
        webshare_locations=tuple(x.strip() for x in locs.split(",") if x.strip()),
        port=int(os.environ.get("PORT", "8000")),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()
