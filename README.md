# HOS Trip Planner — Full Stack Assessment

A production-oriented Django + React implementation of the Full Stack Developer assessment.

The application accepts the driver's current location, pickup location, drop-off location, and current 70/8 cycle hours. It geocodes the locations, calculates the route, and generates an HOS-compliant trip itinerary with driving, rest, break, fueling, pickup, drop-off, and cycle-restart activities.

The application also visualizes the route on an interactive map and generates multi-day 24-hour RODS-style driver's daily logs.

---

## Features

### Trip Planning

- Current location → pickup → drop-off routing.
- Automatic location geocoding using Nominatim.
- Road routing using OSRM.
- Route distance and estimated driving time.
- Multi-leg route support.
- Fractional route distances are preserved.

### HOS Scheduling

The scheduler follows the assessment's required property-carrying CMV assumptions.

- 11-hour maximum driving limit.
- 14-hour driving window.
- 30-minute break after 8 cumulative driving hours.
- 10-hour off-duty reset.
- 70-hour / 8-day cycle.
- Current cycle usage provided as an input.
- Conservative 34-hour restart when the remaining cycle cannot support continued driving.
- 1-hour pickup service.
- 1-hour drop-off service.
- Fuel stop every 1,000 route miles.
- Multi-day trip scheduling.
- Chronologically ordered activities.
- Preservation of the complete route mileage.

### Route & Map

- OpenStreetMap base map.
- Leaflet interactive map.
- OSRM route geometry.
- Start location marker.
- Pickup marker.
- Drop-off marker.
- HOS activity markers.
- Fuel checkpoints.
- Rest and break activities.
- Route legend.
- Route distance and driving-time summaries.

### Daily Logs

The application generates multi-day 24-hour RODS-style driver's daily logs.

Each daily log includes:

- Date.
- Origin and destination.
- Pickup location.
- Total miles driven.
- Off-duty periods.
- Sleeper berth periods when applicable.
- Driving periods.
- On-duty/not-driving periods.
- 15-minute duty-status grid.
- Total hours by duty status.
- Remarks/activity table.
- Daily mileage.
- Cycle information.
- Print/PDF support.

---

## Technology Stack

### Backend

- Python
- Django
- Django REST-style JSON API
- OSRM
- Nominatim
- OpenStreetMap

### Frontend

- React
- Vite
- Leaflet
- React Leaflet
- Responsive CSS

### Deployment

- Docker
- Render
- Vercel

---

## Project Structure

```text
HOS-Trip-Planner-Assessment/
│
├── backend/
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── wsgi.py
│   │   └── asgi.py
│   │
│   ├── planner/
│   │   ├── tests/
│   │   │   └── test_hos.py
│   │   ├── hos.py
│   │   ├── routing.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── ...
│   │
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── ...
│   │
│   ├── package.json
│   ├── package-lock.json
│   ├── index.html
│   └── vercel.json
│
├── docs/
│   └── HOS_RULES.md
│
├── render.yaml
└── README.md