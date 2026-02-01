from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import logging

# Handle imports depending on how run (module vs script)
try:
    from .models import RunSummary, ComprehensiveSuiteMetrics
    from .ingest import get_store
    from .routes.suites import router as suites_router
except ImportError:
    from models import RunSummary, ComprehensiveSuiteMetrics
    from ingest import get_store
    from routes.suites import router as suites_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard")

app = FastAPI(
    title="Secure-Tunnel Forensic Dashboard API",
    description="API for accessing forensic benchmark data from GCS logs.",
    version="2.0"
)

# Register API routes
app.include_router(suites_router)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "online", "system": "Secure-Tunnel Forensic Dashboard"}

@app.get("/api/runs", response_model=List[RunSummary])
def list_runs():
    """List all available benchmark runs."""
    store = get_store()
    return store.list_runs()

@app.get("/api/runs/{run_id}/suites", response_model=List[ComprehensiveSuiteMetrics])
def get_run_suites(run_id: str):
    """Get detailed forensic metrics for a run."""
    store = get_store()
    suites = [s for s in store._suites.values() if s.run_context.run_id == run_id]
    if not suites:
        raise HTTPException(status_code=404, detail="Run not found or invalid data")
    return suites
