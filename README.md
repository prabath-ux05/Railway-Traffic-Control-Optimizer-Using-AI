# Railway Traffic Optimizer (Chennai Division)

An intelligent, real-time railway traffic dispatching and optimization system designed for the Chennai Division suburban and mainline network (Southern Railway, India). The system combines discrete-event simulation, Google OR-Tools CP-SAT constraint programming, explainable decision support, and a Next.js 15 operational dashboard to resolve train conflicts, minimize delays, and reschedule traffic dynamically during disruptions.

A research paper based on this system was accepted at **CICT 2026**.

---

## 1. System Architecture

```
                                  +------------------------------+
                                  |      Next.js 15 Dashboard     |
                                  |   (Server-Sent Events / REST) |
                                  +---------------+--------------+
                                                  |
                                                  | HTTP / SSE
                                                  v
+------------------------------------------------------------------------------------------------+
|                                    FastAPI Backend (:8000)                                     |
|                                                                                                |
|   +-----------------------+   +------------------------+   +-------------------------------+   |
|   |  LiveSimulationEngine  |   |  SimulationStateManager|   |   Decision Support Engine     |   |
|   |  - Real-time ticker   |   |  - Authoritative state |   |   - Explainable actions       |   |
|   |  - Event injection    |   |  - Disk persistence    |   |   - Conflict detection        |   |
|   |  - Proposals lifecycle|   |  - Dynamic snapshots   |   |   - Metric consolidation      |   |
|   +-----------+-----------+   +-----------+------------+   +---------------+---------------+   |
|               |                           |                                |                   |
|               +---------------------------+--------------------------------+                   |
|                                           |                                                    |
|                                           v                                                    |
|                   +-----------------------------------------------+                            |
|                   |        Optimization & Rescheduling Core       |                            |
|                   |        - Google OR-Tools CP-SAT Solver        |                            |
|                   |        - Multi-objective dispatching          |                            |
|                   |        - INFEASIBLE fallback protocol         |                            |
|                   +-----------------------+-----------------------+                            |
|                                           |                                                    |
|                                           v                                                    |
|                   +-----------------------------------------------+                            |
|                   |               Master Datasets                 |                            |
|                   |  - 7 Stations (MAS, BBQ, VJM, PER, PCW, etc.)  |                            |
|                   |  - 40 Active Services (7 Excluded)            |                            |
|                   |  - Verified SHA-256 Integrity Hashes          |                            |
|                   +-----------------------------------------------+                            |
+------------------------------------------------------------------------------------------------+
```

### Key Modules:
- **`backend/app/`**: REST API endpoints, Pydantic schemas, and server-sent event (SSE) streaming (`/api/v1/simulation/stream`).
- **`backend/app/runtime_engine.py`**: Thread-safe `LiveSimulationEngine` managing server-side clock progression, real-time disruption event injection, and re-optimization proposal workflows.
- **`simulation/`**: Discrete-event railway simulation models, conflict detection algorithms, and state management.
- **`optimization/`**: Constraint satisfaction models formulated with Google OR-Tools CP-SAT, including delay penalties, safety headways, line capacities, and junction reservations.
- **`decision_support/`**: Explainable recommendations, root-cause propagation graphs, and dispatching directives.
- **`evaluation/`**: Scenario evaluation, scalability benchmarks, and paper reproduction suites.
- **`frontend/`**: Modern operational dashboard built with Next.js 15, React 19, Lucide icons, and Tailwind CSS.

---

## 2. Prerequisites

- **Python**: 3.12 or 3.13 (64-bit)
- **Node.js**: v18.18+ or v20+ (with `npm`)
- **Git**: For version control and reproduction checks

---

## 3. Installation & Setup

### 3.1 Backend Setup
1. Open a terminal in the project root:
   ```bash
   python -m venv venv
   ```
2. Activate the virtual environment:
   - **Windows**: `.\venv\Scripts\activate`
   - **Linux/macOS**: `source venv/bin/activate`
3. Install pinned Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment template:
   ```bash
   cp .env.example .env
   ```

### 3.2 Frontend Setup
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install frontend dependencies with `npm ci`:
   ```bash
   npm ci
   ```
3. Return to the root directory:
   ```bash
   cd ..
   ```

---

## 4. Running the System

### 4.1 Start the FastAPI Backend
```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
- API Base URL: `http://localhost:8000`
- Interactive Swagger API Docs: `http://localhost:8000/docs`
- Live SSE Stream: `http://localhost:8000/api/v1/simulation/stream`

### 4.2 Start the Next.js Frontend
In a separate terminal:
```bash
cd frontend
npm run dev
```
- Dashboard URL: `http://localhost:3000`

---

## 5. Verification and Testing

### 5.1 Run the Full Test Suite
Run all 676 unit, integration, and regression tests:
```bash
python -m pytest
```
*Expected: 676 passed, 0 failed.*

### 5.2 Reproduce Research Paper Numbers (CICT 2026)
Run the automated verification script:
```bash
python scripts/reproduce_paper.py
```
This script audits:
- **10 Core Reproduction Checks**: Experiment counts (45), delay means (FIFO 331.375m vs CP-SAT 314.386m), max savings (125.5 min), solver times, conflict resolutions (22/22), scalability, and sign distributions across all stored evaluations.
- **Audits of Unverified Paper Text Claims**: Formally cross-references claims (e.g. 183 to 123 min compound scenario, 20.5% 6-core average) against raw simulation logs.
- Outputs detailed reports to `data/evaluation/paper_reproduction/report.json` and `report.md`.

*Expected: 10/10 PASS.*

---

## 6. Master Datasets & Integrity Protection

The network model is grounded in Southern Railway working timetables and track layouts:
- **`data/infrastructure/`**: Stations (`stations.json`), tracks (`tracks.json`), corridors (`corridors.json`), and switches (`switches.json`).
- **`data/trains/`**: Train services (`services.json`), rolling stock (`trains.json`), and scheduled timetable stops (`timetables.json`).
- **`data/track_sections/`**: Discrete spatial track blocks and directional signal headways.

### Dataset Integrity Rules:
1. **Master Datasets are Read-Only**: Master files are protected by SHA-256 hashes verified in `tests/test_dataset_integrity.py`.
2. **Active Service Derivation**: Exactly 40 services have published timetable rows and are marked `active = True`. 7 services lacking timetable evidence (`SRV_40143_01`, `SRV_40144_01`, `SRV_41015_01`, `SRV_41131_01`, `SRV_41132_01`, `SRV_42413_01`, `SRV_42425_01`) are automatically tagged `active = False` with `exclusion_reason = "No published timetable evidence"`.
3. **Runtime State Isolation**: All mutable state generated by playback, event injection, or proposal acceptance is written to `runtime/` (`RAILWAY_RUNTIME_DIR`), preventing mutation of `data/`.

---

## 7. License and Provenance

Accepted at the Conference on Information and Communication Technology (CICT 2026).
All master infrastructure, station, and timetable data reflect the Southern Railway Chennai suburban network.
#   R a i l w a y - T r a f f i c - C o n t r o l - O p t i m i z e r - U s i n g - A I  
 