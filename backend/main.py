"""
main.py — FastAPI Application Entry Point for Guitar Fretboard Visualizer
Coordinates the SQLite relational database and the C++ algorithm engine.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import DATABASE_PATH, LIB_PATH
from .routers import tuning, scales, chords

app = FastAPI(
    title="Guitar Fretboard Visualizer API",
    version="1.0.0",
    description="High-performance backend bridging SQL music theory models and C++ fretboard algorithms.",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware for Frontend (Vite / React / Vanilla TS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for local interactive visualization
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(tuning.router)
app.include_router(scales.router)
app.include_router(chords.router)


@app.get("/")
def get_root():
    """System health check and engine status."""
    return {
        "status": "online",
        "service": "Guitar Fretboard Visualizer API",
        "database": {
            "status": "connected" if DATABASE_PATH.exists() else "missing",
            "path": str(DATABASE_PATH)
        },
        "engine": {
            "status": "loaded" if LIB_PATH.exists() else "missing",
            "library": str(LIB_PATH)
        },
        "endpoints": {
            "tuning": "/api/tuning",
            "scales": "/api/scales",
            "chords": "/api/chords",
            "docs": "/docs"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
