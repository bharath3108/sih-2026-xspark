from fastapi import FastAPI
from graph.router import router as graph_router

app = FastAPI(
    title="SIH 2026 - Social Media Analytics API",
    description="Person 4 Graph & Propagation Engine Boundary",
    version="1.0.0"
)

# Mount Person 4's Network Router
app.include_router(graph_router)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "module": "graph_engine"}