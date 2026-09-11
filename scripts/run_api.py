"""Start the Section D FastAPI server."""

from pathlib import Path

import uvicorn

ROOT = Path(__file__).resolve().parent.parent

if __name__ == "__main__":
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        app_dir=str(ROOT),
        reload_dirs=[str(ROOT / "src")],
    )
