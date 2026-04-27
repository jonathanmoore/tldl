import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    transport: str
    bearer_token: str | None
    webshare_username: str | None
    webshare_password: str | None
    webshare_locations: tuple[str, ...]
    port: int
    log_level: str


def load_settings() -> Settings:
    transport = os.environ.get("TLDL_TRANSPORT", "stdio").strip().lower()
    if transport not in ("stdio", "http"):
        raise SystemExit(
            f"TLDL_TRANSPORT must be 'stdio' or 'http' (got {transport!r})."
        )

    token = os.environ.get("MCP_BEARER_TOKEN", "").strip()
    if transport == "http" and not token:
        raise SystemExit(
            "MCP_BEARER_TOKEN must be set when TLDL_TRANSPORT=http. "
            "Generate one with:\n"
            '  python3 -c "import secrets; print(secrets.token_urlsafe(32))"'
        )

    locs = os.environ.get("WEBSHARE_PROXY_LOCATIONS", "").strip()
    return Settings(
        transport=transport,
        bearer_token=token or None,
        webshare_username=os.environ.get("WEBSHARE_PROXY_USERNAME") or None,
        webshare_password=os.environ.get("WEBSHARE_PROXY_PASSWORD") or None,
        webshare_locations=tuple(x.strip() for x in locs.split(",") if x.strip()),
        port=int(os.environ.get("PORT", "8000")),
        log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    )


settings = load_settings()
