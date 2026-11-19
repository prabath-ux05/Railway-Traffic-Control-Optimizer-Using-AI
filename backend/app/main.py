"""
backend/app/main.py
~~~~~~~~~~~~~~~~~~~
Main entry point for the Railway Traffic Optimization & Decision Support FastAPI service.

Mounts operational and live simulation endpoints:
- /api/v1/health
- /api/v1/network
- /api/v1/simulate
- /api/v1/optimize
- /api/v1/what-if
- /api/v1/simulation/state
- /api/v1/simulation/control
- /api/v1/simulation/reset
- /api/v1/simulation/stream (SSE)
- /api/v1/simulation/events
- /api/v1/simulation/reoptimize
- /api/v1/simulation/proposals

SECURITY & AUTHENTICATION NOTICE:
--------------------------------
This API operates without authentication or role-based access control (RBAC). It is designed
for deployment within a trusted operations intranet or local development environment.
There is currently no user authentication, token verification, or request signing.
The following state-mutating endpoints can modify the running simulation, inject or remove
disruptions, or apply re-optimized schedules without authentication:
- POST   /api/v1/simulation/control (alters playback state, speed, target minute)
- POST   /api/v1/simulation/reset (resets clock and simulation state to origin)
- POST   /api/v1/simulation/events (injects active track or speed disruption events)
- DELETE /api/v1/simulation/events/{event_id} (cancels/removes disruption events)
- POST   /api/v1/simulation/reoptimize (generates re-optimization dispatch proposals)
- POST   /api/v1/simulation/proposals/{proposal_id}/accept (mutates authoritative schedule)
- POST   /api/v1/simulation/proposals/{proposal_id}/reject (discards dispatch proposal)
- POST   /api/v1/simulate (executes ad-hoc simulation runs)
"""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api import router as api_router
from backend.app.runtime_engine import get_live_engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize LiveSimulationEngine (startup paused guarantee)
    engine = get_live_engine()
    try:
        yield
    finally:
        # Shutdown: Gracefully stop background loop if active
        await engine.stop_background_loop()


app = FastAPI(
    title="Railway Traffic Optimization & Digital Twin Decision Support API",
    description="Operational backend exposing real-time simulation, CP-SAT timetable optimization, and explainable decision support directives for Chennai Division railway traffic controllers.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS restricted to configured frontend origins (defaults to local Next.js frontend)
# Note: allow_credentials is intentionally omitted/False as no cookies or session credentials are used.
cors_origins_env = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
allowed_origins = [origin.strip() for origin in cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
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
