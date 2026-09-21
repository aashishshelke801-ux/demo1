# Ambulance Emergency Response & Coordination System

College-level Smart India Hackathon 2026 MVP. It demonstrates one connected workflow: patient SOS → ETA-based ambulance matching → driver response → coordinator oversight → hospital pre-alert → closure. This is **demo software only**: it has no connection to 108/112, hospitals, traffic providers, or real emergency dispatch infrastructure.

## Stack and structure

- Flask, SQLite, HTML/CSS/vanilla JavaScript
- `app.py` – APIs, schema, seed data, matching and workflow
- `templates/index.html` – single role-based web application
- `static/css/style.css`, `static/js/app.js` – responsive UI and polling
- `database/emergency.db` – generated on first run

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000`.

## Demo accounts

| Role | Email | Password |
|---|---|---|
| Patient | patient@demo.in | patient123 |
| Driver (Rahul) | rahul@demo.in | driver123 |
| Coordinator | coordinator@demo.in | coord123 |

## Exact 2–3 minute demo

1. In **Patient Emergency**, retain Accident / HIGH and click **SOS**. The demo Pune location works without GPS.
2. The matching engine assigns **MH-12-AB-1234** using the lowest simulated ETA.
3. Open **Ambulance Driver**, log in as Rahul, and accept the incoming request.
4. Open **Coordinator**, log in and show the live case, ambulance map, counters and ETA.
5. Return to Driver and click: **Arrived at Patient → Patient Picked Up → Start Hospital Trip → Arrived at Hospital → Complete Case**.
6. Show the hospital pre-alert and the completed case on Coordinator. Use **Reset Demo** before the next presentation.

## Included capabilities

- Pending ambulance registration and coordinator verification
- Verified-only online availability, duplicate registration prevention and password hashing
- Haversine-distance / ETA-first deterministic matching
- Patient, driver and coordinator role checks
- SQLite case workflow, hospital alerts and tracking event records
- Leaflet/OpenStreetMap map when online; all dispatch workflow remains usable if map tiles cannot load

## Prototype limitations and future scope

GPS is optional and movement is represented by demo records/polling rather than a live dispatch feed. There is no production authentication, emergency-service connection, traffic API, clinical workflow, or real hospital integration. Future phases can add verified 108/112 feeds, hospital systems, real traffic routing, analytics, and district/state deployment.
