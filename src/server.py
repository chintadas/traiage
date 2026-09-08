import json
import os
from pathlib import Path
from typing import List, Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.models import RedfishAlert, AlertStats

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "seed_alerts.json"
PUBLIC_DIR = BASE_DIR / "public"

app = FastAPI(
    title="Data Center Alert Triage API",
    description="Telemetry ingestion and triage API for data center Redfish alerts",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def load_seed_alerts() -> List[dict]:
    if not DATA_PATH.exists():
        return []
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        return data.get("Events", [])

@app.get("/api/alerts")
def get_alerts(
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, Warning, OK"),
    subsystem: Optional[str] = Query(None, description="Filter by subsystem"),
    rack: Optional[str] = Query(None, description="Filter by rack"),
    search: Optional[str] = Query(None, description="Global text search query"),
    sort_by: Optional[str] = Query("Timestamp", description="Field to sort by: Timestamp, Severity, Rack"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc")
):
    raw_events = load_seed_alerts()
    results = raw_events

    # Severity filter
    if severity and severity.lower() != "all":
        results = [e for e in results if e.get("Severity", "").lower() == severity.lower()]

    # Subsystem filter
    if subsystem and subsystem.lower() != "all":
        results = [e for e in results if e.get("Subsystem", "").lower() == subsystem.lower()]

    # Rack filter
    if rack and rack.lower() != "all":
        results = [
            e for e in results 
            if e.get("Location", {}).get("Rack", "").lower() == rack.lower()
        ]

    # Global text search
    if search:
        s = search.lower().strip()
        filtered = []
        for e in results:
            text_corpus = (
                f"{e.get('EventId', '')} "
                f"{e.get('MessageId', '')} "
                f"{e.get('Message', '')} "
                f"{e.get('OriginOfCondition', '')} "
                f"{e.get('Resolution', '')} "
                f"{e.get('Subsystem', '')} "
                f"{e.get('Location', {}).get('Rack', '')} "
                f"{e.get('Location', {}).get('Chassis', '')}"
            ).lower()
            if s in text_corpus:
                filtered.append(e)
        results = filtered

    # Sorting
    severity_rank = {"critical": 3, "warning": 2, "ok": 1}
    if sort_by == "Severity":
        results = sorted(
            results, 
            key=lambda x: severity_rank.get(x.get("Severity", "").lower(), 0), 
            reverse=(order == "desc")
        )
    elif sort_by == "Rack":
        results = sorted(
            results,
            key=lambda x: x.get("Location", {}).get("Rack", ""),
            reverse=(order == "desc")
        )
    else:  # default Timestamp
        results = sorted(
            results,
            key=lambda x: x.get("Timestamp", ""),
            reverse=(order == "desc")
        )

    return {
        "count": len(results),
        "total": len(raw_events),
        "alerts": results
    }

@app.get("/api/alerts/{event_id}")
def get_alert_by_id(event_id: str):
    raw_events = load_seed_alerts()
    for e in raw_events:
        if e.get("EventId") == event_id:
            return e
    raise HTTPException(status_code=404, detail=f"Alert '{event_id}' not found")

@app.get("/api/stats", response_model=AlertStats)
def get_stats():
    raw_events = load_seed_alerts()
    critical = sum(1 for e in raw_events if e.get("Severity") == "Critical")
    warning = sum(1 for e in raw_events if e.get("Severity") == "Warning")
    ok = sum(1 for e in raw_events if e.get("Severity") == "OK")
    
    racks = sorted(list({e.get("Location", {}).get("Rack", "") for e in raw_events if e.get("Location", {}).get("Rack")}))
    subsystems = sorted(list({e.get("Subsystem", "") for e in raw_events if e.get("Subsystem")}))

    return AlertStats(
        total=len(raw_events),
        critical=critical,
        warning=warning,
        ok=ok,
        racks_affected=len(racks),
        subsystems_affected=len(subsystems),
        subsystems=subsystems,
        racks=racks
    )

if PUBLIC_DIR.exists():
    app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8088, reload=True)
