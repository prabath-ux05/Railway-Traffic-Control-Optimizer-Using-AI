"""
backend/app/main.py
~~~~~~~~~~~~~~~~~~~
Main entry point for the Railway Traffic Optimization & Decision Support FastAPI service.

Mounts the Phase 20 operational endpoints:
- /api/v1/health
- /api/v1/network
- /api/v1/simulate
- /api/v1/optimize
- /api/v1/what-if
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import router as api_router

app = FastAPI(
    title="Railway Traffic Optimization & Digital Twin Decision Support API",
    description="Operational backend exposing real-time simulation, CP-SAT timetable optimization, and explainable decision support directives for Chennai Division railway traffic controllers.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Enable CORS for future Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount operational API router
app.include_router(api_router)


@app.get("/", tags=["System"])
def root_info():
    return {
        "service": "Railway Traffic Optimization & Decision Support API",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs",
        "endpoints": {
            "health": "/api/v1/health",
            "network": "/api/v1/network",
            "simulate": "/api/v1/simulate",
            "optimize": "/api/v1/optimize",
            "what_if": "/api/v1/what-if",
        },
    }


def main():
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    main()
