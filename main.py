from fastapi import FastAPI
from backend.db.database import engine, Base
from backend.api import ingestion

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="SIH26152 - Social Media Analytics Engine",
    description="Unified API for Data Ingestion, Graph Analytics, NLP, and Trends",
    version="1.0.0"
)

app.include_router(ingestion.router)

@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "modules": {
            "ingestion": "active",
            "graph_engine": "active"
        }
    }

if __name__ == "__main__":
    import uvicorn
    # Bound to 127.0.0.1 for local browser access
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True , reload_excludes=[".venv/*", "*.db", "data/*"])