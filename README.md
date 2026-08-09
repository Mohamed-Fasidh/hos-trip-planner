HOS Trip Planner

Full-stack HOS trip planning application built for the Full Stack Developer assessment.

The HOS Trip Planner combines a Django backend with a React frontend to plan commercial vehicle trips using the assessment-defined Hours of Service (HOS) rules. Users provide a current location, pickup location, drop-off location, and current 70/8 cycle usage. The application geocodes the locations, calculates road routes, generates an HOS-aware itinerary, visualizes the route and scheduled activities on a map, and produces multi-day digital RODS-style daily logs.

Overview

The planner is designed around the assessment's defined operating assumptions:

Property-carrying commercial motor vehicle.

70 hours / 8 days cycle.

11-hour maximum driving limit.

14-consecutive-hour driving window.

30-minute break after 8 cumulative driving hours.

10-hour off-duty reset.

Conservative 34-hour cycle restart when required.

1-hour pickup.

1-hour drop-off.

Fueling at or before every 1,000 route miles.

No adverse driving conditions.

The implementation intentionally focuses on the assessment scope and does not automatically infer additional HOS exceptions that require information not provided by the assessment.

Key Features

HOS-aware trip scheduling

Enforces the 11-hour driving limit.

Tracks the 14-consecutive-hour driving window.

Inserts 30-minute driving breaks after 8 cumulative driving hours.

Schedules 10-hour off-duty resets.

Tracks the 70-hour / 8-day cycle.

Uses the supplied current-cycle hours as the starting cycle usage.

Supports conservative 34-hour cycle restarts.

Schedules 1-hour pickup and drop-off activities.

Schedules fuel checkpoints at or before 1,000 route miles.

Supports multi-day trips.

Preserves fractional route mileage.

Produces a deterministic chronological activity timeline.

Routing and mapping

Geocodes locations with Nominatim.

Calculates road routes with OSRM.

Uses OpenStreetMap for map data.

Displays route geometry with Leaflet.

Displays start, pickup, drop-off, fuel, break, rest, and restart activities where coordinates are available.

Provides route distance and estimated driving duration.

Digital daily logs

Generates multi-day 24-hour daily logs.

Splits activities at calendar-day boundaries.

Fills uncovered periods with off-duty time.

Calculates daily driving, on-duty, off-duty, and mileage totals.

Provides a 15-minute duty-status grid.

Displays activity timestamps and remarks.

Supports print-to-PDF through the browser.

Testing

The backend includes 200 unique HOS tests covering:

HOS limits.

Break and reset behavior.

Cycle limits and restarts.

1,000-mile fueling.

Pickup and drop-off.

Long and multi-day routes.

Fractional mileage.

Multiple route segments.

Activity chronology.

Daily-log invariants.

Boundary and edge cases.

Architecture

┌──────────────────────────────┐
│        React Frontend        │
│                              │
│  Trip Form • Map • Itinerary │
│  Daily Logs • Print/PDF      │
└──────────────┬───────────────┘
               │
               │ POST /api/plan/
               ▼
┌──────────────────────────────┐
│        Django Backend        │
│                              │
│  API • Validation • Routing  │
│  HOS Scheduling • Daily Logs │
└───────┬───────────┬──────────┘
        │           │
        ▼           ▼
┌────────────┐ ┌──────────────┐
│ Nominatim  │ │     OSRM     │
│ Geocoding  │ │ Road Routing │
└────────────┘ └──────────────┘
               │
               ▼
        ┌───────────────┐
        │ HOS Scheduler │
        └───────┬───────┘
                │
        ┌───────┴────────┐
        ▼                ▼
┌──────────────┐  ┌─────────────┐
│ Daily Logs   │  │ Map Stops   │
└──────────────┘  └─────────────┘

Technology Stack

Layer

Technology

Frontend

React, Vite

Mapping UI

Leaflet, React Leaflet

Backend

Python, Django

Geocoding

Nominatim

Road routing

OSRM

Map data

OpenStreetMap

Deployment

Render, Vercel, Docker

Testing

Django/Python test suite

Project Structure

hos-trip-planner/
│
├── backend/
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── planner/
│   │   ├── tests/
│   │   │   └── test_hos.py
│   │   ├── hos.py
│   │   ├── routing.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── manage.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   └── vercel.json
│
├── docs/
│   └── HOS_RULES.md
│
├── render.yaml
├── .gitignore
└── README.md

HOS Rules

11-Hour Driving Limit

The planner limits driving to a maximum of 11 hours within the applicable 14-consecutive-hour driving window.

The scheduler considers the remaining driving allowance when determining each driving segment.

14-Hour Driving Window

The planner tracks elapsed time from the beginning of the current duty window. Off-duty time occurring inside that window does not stop the 14-hour clock.

A qualifying 10-hour off-duty reset establishes a new driving window.

30-Minute Break

After 8 cumulative driving hours, the planner schedules a consecutive 30-minute off-duty break before additional driving continues.

10-Hour Off-Duty Reset

A normal 10-hour off-duty reset is used to establish a new driving window and reset the applicable driving counters.

The reset does not reset the 70-hour cycle.

70-Hour / 8-Day Cycle

The planner uses the user-supplied current cycle usage to calculate remaining capacity:

remaining cycle hours = 70 - current cycle hours

Driving and on-duty work are constrained by the remaining cycle capacity.

34-Hour Restart

When the remaining cycle capacity cannot support continued operation, the planner can schedule a conservative 34-hour cycle restart and reset the internal cycle usage to zero.

Pickup and Drop-off

Pickup and drop-off are each modeled as 1 hour of on-duty, non-driving time.

Fueling

The assessment requires fueling at least once every 1,000 route miles.

The planner schedules fuel checkpoints at or before each 1,000-mile route interval.

API

Health Check

GET /api/health/

Example response:

{
  "status": "ok"
}

Plan Trip

POST /api/plan/

Example request:

{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 0
}

Optional start datetime:

{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 0,
  "start_datetime": "2026-08-09T06:00:00"
}

The planning response contains the generated route, schedule, activity information, cycle information, fuel stops, map stops, and daily logs.

Local Development

Prerequisites

Install:

Python 3.x

Node.js and npm

Git

Backend

From the project root:

cd backend
python -m venv .venv

Windows

.venv\Scripts\activate

macOS / Linux

source .venv/bin/activate

Install Python dependencies:

pip install -r requirements.txt

Start Django:

python manage.py runserver 8000

The backend runs at:

http://localhost:8000

Health check:

http://localhost:8000/api/health/

Frontend

Open a second terminal:

cd frontend
npm install

Create .env.local when required:

VITE_API_URL=http://localhost:8000

Start the Vite development server:

npm run dev

The frontend normally runs at:

http://localhost:5173

Testing

Run the HOS test suite from the backend directory:

python manage.py test planner.tests.test_hos -v 2

Or run the complete Django test suite:

python manage.py test

The HOS test suite contains 200 unique test cases covering the core assessment requirements and important edge cases.

Production Build

Build the React frontend:

npm run build

The production build is generated in:

frontend/dist/

Deployment

Backend — Render

The repository includes:

render.yaml

and:

backend/Dockerfile

The backend can be deployed as a Docker service on Render.

Configure the frontend API URL using:

VITE_API_URL=https://<deployed-backend-url>

Frontend — Vercel

Deploy the frontend/ directory to Vercel.

Build command:

npm run build

Output directory:

dist

Set the production environment variable:

VITE_API_URL=https://<deployed-backend-url>

Daily Log Generation

For trips spanning multiple calendar days, the backend:

Generates the chronological activity timeline.

Splits activities at midnight boundaries.

Allocates mileage proportionally when an activity crosses midnight.

Fills uncovered periods with off-duty time.

Calculates daily driving, on-duty, off-duty, and mileage totals.

Validates that each daily log represents exactly 24 hours.

Returns the generated logs to the frontend.

The frontend renders the generated schedule using a 15-minute duty-status grid.

The daily logs are intended as an assessment-oriented digital visualization of the generated HOS schedule and are not represented as a certified production ELD/RODS compliance system.

Accuracy and Scope

The planner is intentionally aligned with the assessment's defined assumptions.

It does not automatically infer additional HOS exceptions that require operational or historical information not provided by the assessment.

The following are outside the defined assessment scope:

Split-sleeper provisions.

Adverse-driving-condition exceptions.

CDL short-haul exceptions.

Non-CDL short-haul exceptions.

16-hour short-haul exceptions.

Personal-conveyance rules.

Yard-move rules.

Other special HOS exceptions requiring additional driver or operational history.

The current_cycle_used input represents the driver's already-used cycle hours supplied to the planner. The system uses that value to determine remaining cycle capacity rather than reconstructing historical duty records that were not provided.

External Services

The project uses the following open mapping services:

OpenStreetMap

Provides map data for the interactive map.

Nominatim

Provides location geocoding.

OSRM

Provides road routing, route geometry, distance, and estimated duration.

These public services are appropriate for the assessment/demo environment. They are not treated as unlimited or SLA-backed production infrastructure.

For production use, consider:

Server-side caching.

Request throttling.

Rate limiting.

Retry handling.

Monitoring.

A managed routing provider.

A self-hosted routing service where appropriate.

Security Considerations

The project is configured for an assessment/demo environment.

A production deployment should additionally consider:

Restricting Django ALLOWED_HOSTS.

Restricting CORS origins.

Secure environment-variable management.

HTTPS-only deployment.

API rate limiting.

Authentication and authorization where required.

Structured logging.

Monitoring and alerting.

External-service request limits.

Validation Invariants

The scheduler validates important invariants throughout trip generation.

Driving

Driving within an applicable duty window <= 11 hours

Break

Cumulative driving is constrained to the 8-hour break threshold

Fuel

Fuel interval <= 1,000 route miles

Daily logs

Each generated calendar-day log = 24 hours

Route mileage

Generated mileage preserves the routed distance

Activity chronology

Activity start < Activity end

These invariants are also covered by the automated HOS test suite.

Assessment Deliverables

For final assessment submission, the project should be accompanied by:

GitHub repository containing the source code.

Live deployed frontend.

Live deployed backend/API.

Working route planning flow.

HOS itinerary demonstration.

Multi-day daily-log demonstration.

3–5 minute Loom walkthrough, as requested by the assessment.

Engineering Notes

The project is intentionally designed as a focused assessment implementation rather than a complete commercial ELD platform.

The core scheduling engine is kept deterministic and independently testable from the routing and presentation layers. This allows HOS scheduling behavior to be validated without depending on external map-service responses.

Routing and geocoding are separated from HOS calculations so that external-service failures can be handled independently from the scheduling logic.

License

This project was developed for the HOS Trip Planner Full Stack Developer assessment.