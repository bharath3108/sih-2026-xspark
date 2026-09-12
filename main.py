from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.database import engine, Base
from backend.api import ingestion, dashboard
from graph.router import router as graph_router
from ml.mainml import app as ml_app

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIH26152 - Social Media Analytics Engine",
    description="Unified API for Data Ingestion, Graph Analytics, NLP, and Trends",
    version="1.0.0"
)

# Dashboard (Next.js) runs on a different origin in dev; the demo has no
# cookie-based auth yet, so an open CORS policy is fine for now.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routers
app.include_router(ingestion.router)
app.include_router(graph_router)
app.include_router(dashboard.router)

# ml_app is a separate FastAPI instance with its own startup lifespan (loads
# the NLP models and connects to Qdrant). include_router() would copy its
# routes but silently skip that lifespan, leaving the model registry empty at
# request time — mount() forwards ASGI lifespan events to it so startup runs.
app.mount("/api/ml", ml_app)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "modules": {
            "ingestion": "active",
            "graph_engine": "active",
            "dashboard": "active"
        }
    }

if __name__ == "__main__":
    import os
    import uvicorn

    # reload=True is opt-in (RELOAD=1) rather than default: without the
    # `watchfiles` package installed, uvicorn's --reload falls back to
    # StatReload, whose subprocess spawn has a reproducible Windows bug
    # where the respawned worker can end up serving a stale/different
    # module than "main:app" (observed serving src/api/main.py instead).
    # Plain `python main.py` should always just work.
    reload_enabled = os.getenv("RELOAD") == "1"
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=reload_enabled,
        reload_excludes=[".venv/*", "*.db", "data/*"] if reload_enabled else None,
    )
