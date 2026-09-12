from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.db.database import engine, Base
from backend.api import ingestion, dashboard
from graph.router import router as graph_router

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
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True, reload_excludes=[".venv/*", "*.db", "data/*"])