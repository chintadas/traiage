# TRAIAGE

AI-assisted Data Center Alert Telemetry & Triage Console.

TRAIAGE ingests data center alerts (conforming to DMTF Redfish `Event.v1_7_0`), provides real-time search, multi-filtering, and Redfish JSON inspection, and serves as the foundation for automated incident correlation and prioritization.

---

## Features

- **DMTF Redfish Alert Telemetry**: Seeded with 20 realistic hardware and facility events spanning Direct Liquid Cooling, Power/PDU, AI/GPU (HGX H100), ToR Network switches, Compute (ECC, CPU PROCHOT), and Storage.
- **Interactive Operations Console**: Web UI with live KPI metrics, dynamic multi-filtering by severity/subsystem/rack, full-text search, and a slide-out Redfish resource inspector with 1-click JSON export.
- **REST Telemetry API**: FastAPI backend providing filtered query endpoints (`/api/alerts`, `/api/stats`, `/api/alerts/{event_id}`).
- **Automated Test Suite**: 14 unit and integration tests validating dataset schema compliance and API endpoints.

---

## Prerequisites

- Python 3.10+
- Required packages:
  ```bash
  pip install fastapi uvicorn pydantic pytest httpx
  ```

---

## Running the Server

Start the FastAPI server (defaults to port `8088`):

```bash
# Option 1: Direct module execution
python3 src/server.py

# Option 2: Using uvicorn CLI with auto-reload
python3 -m uvicorn src.server:app --host 127.0.0.1 --port 8088 --reload
```

Once started, open your browser and navigate to:

👉 **[http://127.0.0.1:8088/](http://127.0.0.1:8088/)**

### Key Endpoints

- **Web Dashboard**: `http://127.0.0.1:8088/`
- **Telemetry Alerts**: `http://127.0.0.1:8088/api/alerts`
- **Filtered Alerts**: `http://127.0.0.1:8088/api/alerts?severity=Critical&subsystem=Power`
- **Telemetry Statistics**: `http://127.0.0.1:8088/api/stats`
- **Interactive Swagger Docs**: `http://127.0.0.1:8088/docs`

---

## Running the Tests

### 1. Python Backend & Dataset Tests (pytest)
Execute the Python test suite validating Redfish schema compliance and FastAPI endpoints:

```bash
# Run all Python tests with verbose output
python3 -m pytest -v

# Run dataset integrity tests
python3 -m pytest tests/test_dataset.py -v

# Run API endpoint and filter tests
python3 -m pytest tests/test_api.py -v
```

### 2. Frontend Unit Tests (Node.js)
Execute the JavaScript unit test suite validating relative age formatting (`formatRelativeTime`), HTML escaping, filtering, and sorting:

```bash
# Using npm
npm test

# Or directly with Node's built-in test runner
node --test tests/test_app.test.js
```

---

## Project Structure

```
traiage/
├── data/
│   ├── seed_alerts.json          # 20 raw DMTF Redfish alert records
│   ├── DATASET_INSPECTION.md     # Detailed event breakdown and cluster guide
│   └── topology.json             # Multi-plane topological dependency graph
├── public/
│   ├── index.html                # Telemetry dashboard HTML layout
│   ├── styles.css                # Datacenter operations dark aesthetic
│   └── app.js                    # Filter, search, and inspector controller
├── src/
│   ├── models.py                 # Pydantic schemas (RedfishAlert, AlertStats)
│   ├── server.py                 # FastAPI backend & static file server
│   └── graph.py                  # Topological dependency graph engine & RCA
├── tests/
│   ├── test_dataset.py           # Redfish schema and data integrity tests
│   ├── test_api.py               # REST API filtering and sort tests
│   ├── test_graph.py             # Graph traversal, blast radius & path tests
│   └── test_app.test.js          # Frontend unit tests (Node.js test runner)
├── package.json                  # Frontend npm scripts configuration
└── README.md
```
