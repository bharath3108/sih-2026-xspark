from fastapi import FastAPI

from graph.router import router as graph_router
from trends.router import router as trends_router


app = FastAPI(
    title="SIH 2026 - Social Media Analytics API",
    description="Unified API boundary (Graph + Topics/Trends + Audience)",
    version="1.0.0",
)

# Routers (modules)
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
            "graph_engine": "mounted",
            "topics_trends_audience": "mounted",
        },
    }