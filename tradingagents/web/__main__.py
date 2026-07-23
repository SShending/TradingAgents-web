"""Production web entry point with local binding defaults."""

from __future__ import annotations

import os


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit('Install the web extra first: pip install -e ".[web]"') from exc
    uvicorn.run(
        "tradingagents.web.app:app",
        host=os.getenv("TRADINGAGENTS_WEB_HOST", "127.0.0.1"),
        port=int(os.getenv("TRADINGAGENTS_WEB_PORT", "8000")),
        access_log=True,
    )


if __name__ == "__main__":
    main()
