"""Start the API server.

Development (default): auto-reload on code changes, listening on this machine only.
Production (ENVIRONMENT=production): no reload, WEB_CONCURRENCY worker processes,
and client IPs read from X-Forwarded-For only for proxies in FORWARDED_ALLOW_IPS.
"""
import os

import uvicorn

if __name__ == "__main__":
    production = os.environ.get("ENVIRONMENT", "development") == "production"
    reload = not production and os.environ.get("RELOAD", "true").lower() == "true"
    uvicorn.run(
        "app:app",
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "8080")),
        reload=reload,
        workers=None if reload else int(os.environ.get("WEB_CONCURRENCY", "1")),
        proxy_headers=True,
        forwarded_allow_ips=os.environ.get("FORWARDED_ALLOW_IPS", "127.0.0.1"),
        server_header=False,
    )
