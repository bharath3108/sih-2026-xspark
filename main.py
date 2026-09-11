from fastapi import FastAPI
from backend.db.database import engine, Base
from backend.api import ingestion
from graph.router import router as graph_router
from trends.router import router as trends_router

# Initialize database schema
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIH 2026 - Social Media Analytics API",
    description="Unified API Boundary (Ingestion + Graph + Topics/Trends + Audience)",
    version="1.0.0",
)

# Mount Routers across all modules
app.include_router(ingestion.router)
app.include_router(graph_router)
app.include_router(trends_router)


@app.get("/")
def root():
    return {
        "service": "SIH 2026 Social Media Analytics API",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "modules": {
            "ingestion": "mounted",
            "graph_engine": "mounted",
            "topics_trends_audience": "mounted",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        reload_excludes=[".venv/*", "*.db", "data/*"],
    )