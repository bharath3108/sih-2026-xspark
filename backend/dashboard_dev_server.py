"""Standalone dev server for the dashboard composition API.

main.py wires up Person 1's Postgres-backed engine at import time, so it
can't run without a live database. The dashboard composition layer has no
DB dependency (it reads fixtures / other services' HTTP APIs), so this lets
frontend development proceed against real endpoints before Postgres, or any
other module, is wired up — same contracts, same routes, just without
main.py's ingestion/graph routers attached.

    python -m backend.dashboard_dev_server
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api import dashboard

app = FastAPI(title="Dashboard composition API (dev)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "mode": "dashboard-only-dev-server"}


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
