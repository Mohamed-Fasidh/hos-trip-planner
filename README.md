HOS Trip Planner

Full-Stack HOS Trip Planning Application | Django + React

A production-oriented trip planning application developed for the Full Stack Developer assessment. The system accepts a driver's current location, pickup location, drop-off location, and current 70/8 cycle usage, then generates an HOS-aware itinerary with routing, fueling, rest, pickup/drop-off activities, an interactive map, and multi-day digital RODS-style logs.

Project Highlights

Django REST-style backend

React + Vite frontend

Deterministic HOS scheduling

11-hour driving limit

14-hour consecutive driving window

30-minute break after 8 cumulative driving hours

10-hour off-duty reset

70-hour / 8-day cycle tracking

Conservative 34-hour cycle restart

Fueling at or before every 1,000 route miles

1-hour pickup and drop-off

OpenStreetMap + Nominatim + OSRM

Interactive Leaflet route map

Multi-day 24-hour digital logs

200 automated HOS tests

Docker / Render backend deployment

Vercel frontend deployment

Table of Contents

Project Overview

Assessment Scope

HOS Rules

System Architecture

Technology Stack

Project Structure

API

Local Setup

Running the Application

Testing

Daily Log Generation

External Mapping Services

Production Build

Deployment

Security Considerations

Known Scope Limitations

Assessment Validation

Engineering Design

Assessment Deliverables

Project Overview

The HOS Trip Planner combines trip routing and Hours of Service scheduling into a single full-stack workflow.

User Input

The user provides:

Current location

Pickup location

Drop-off location

Current 70/8 cycle hours

Optional trip start datetime

Processing Pipeline

User Input
    |
    v
Geocoding
(Nominatim)
    |
    v
Road Routing
(OSRM)
    |
    v
Route Segments
    |
    v
HOS Scheduler
    |
    +-- Driving
    +-- Breaks
    +-- Rest
    +-- Fuel
    +-- Pickup
    +-- Drop-off
    +-- Cycle Management
    |
    v
Generated Itinerary
    |
    +-- Interactive Map
    +-- Daily RODS-Style Logs

Assessment Scope

The implementation follows the defined assessment assumptions:

Property-carrying commercial motor vehicle.

70 hours / 8 days.

No adverse driving conditions.

Fueling at least once every 1,000 route miles.

1-hour pickup.

1-hour drop-off.

The scheduler intentionally focuses on these assessment requirements and does not automatically infer additional HOS exceptions that require operational or historical information not provided by the assessment.

HOS Rules

1. 11-Hour Driving Limit

The scheduler limits driving to a maximum of:

11 hours

within the applicable 14-consecutive-hour driving window.

2. 14-Hour Driving Window

The planner tracks the elapsed time within the current:

14-consecutive-hour window

Off-duty time occurring inside the window does not stop the 14-hour clock.

A qualifying 10-hour off-duty reset establishes a new driving window.

3. 30-Minute Break

After:

8 cumulative driving hours

the scheduler inserts:

30-minute OFF_DUTY break

before additional driving continues.

4. 10-Hour Off-Duty Reset

When the current driving window can no longer accommodate the required operation, the planner schedules:

10-hour OFF_DUTY reset

The reset establishes a new driving window and resets the applicable driving counters.

The 10-hour reset does not reset the 70-hour cycle.

5. 70-Hour / 8-Day Cycle

The scheduler uses the current-cycle hours supplied by the user.

For example:

Current cycle used = 65 hours

Remaining cycle = 70 - 65
                = 5 hours

The scheduler prevents additional driving and on-duty work from exceeding the available cycle capacity.

6. 34-Hour Cycle Restart

When the remaining cycle capacity cannot support continued operation, the scheduler can insert a conservative:

34-hour cycle restart

The cycle usage is then reset to:

0 hours

7. Pickup

Pickup is modeled as:

1 hour of ON_DUTY non-driving time

8. Drop-off

Drop-off is modeled as:

1 hour of ON_DUTY non-driving time

9. Fueling

The assessment requires fueling at least once every:

1,000 route miles

The scheduler therefore creates fuel checkpoints at or before every 1,000 route-mile interval.

Example:

Start
  |
  +-- 1,000 miles --> Fuel Stop
  |
  +-- 2,000 miles --> Fuel Stop
  |
  +-- 3,000 miles --> Fuel Stop

System Architecture

+------------------------------------------+
|              React Frontend              |
|                                          |
|  Trip Form | Map | Itinerary | Logs     |
+--------------------+---------------------+
                     |
                     | POST /api/plan/
                     v
+------------------------------------------+
|             Django Backend               |
|                                          |
| API | Validation | Routing | HOS Engine |
+---------------+--------------+-----------+
                |              |
                v              v
        +---------------+  +---------------+
        |   Nominatim   |  |     OSRM      |
        |   Geocoding   |  | Road Routing  |
        +---------------+  +---------------+
                |              |
                +------+-------+
                       |
                       v
              +-----------------+
              |  HOS Scheduler  |
              +--------+--------+
                       |
              +--------+--------+
              v                 v
       +-------------+   +-------------+
       | Daily Logs  |   |  Map Stops  |
       +-------------+   +-------------+

Technology Stack

Layer

Technology

Frontend

React, Vite

Styling

CSS

Mapping UI

Leaflet, React Leaflet

Backend

Python, Django

Geocoding

Nominatim

Routing

OSRM

Map Data

OpenStreetMap

Testing

Django / Python unittest

Containerization

Docker

Backend Deployment

Render

Frontend Deployment

Vercel

Project Structure

hos-trip-planner/
|
+-- backend/
|   +-- config/
|   |   +-- settings.py
|   |   +-- urls.py
|   |   +-- asgi.py
|   |   +-- wsgi.py
|   |
|   +-- planner/
|   |   +-- tests/
|   |   |   +-- test_hos.py
|   |   +-- hos.py
|   |   +-- routing.py
|   |   +-- views.py
|   |   +-- urls.py
|   |
|   +-- manage.py
|   +-- requirements.txt
|   +-- Dockerfile
|
+-- frontend/
|   +-- src/
|   |   +-- main.jsx
|   |   +-- styles.css
|   +-- index.html
|   +-- package.json
|   +-- package-lock.json
|   +-- vercel.json
|
+-- docs/
|   +-- HOS_RULES.md
|
+-- render.yaml
+-- .gitignore
+-- README.md

API

Health Check

Request

GET /api/health/

Response

{
  "status": "ok"
}

Plan Trip

Request

POST /api/plan/

Example Payload

{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 0
}

With Start Datetime

{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 0,
  "start_datetime": "2026-08-09T06:00:00"
}

Response Includes

Input locations

Geocoded coordinates

Route legs

Route distance

Route duration

HOS activity timeline

Driving activities

Break activities

Rest activities

Fuel stops

Pickup activity

Drop-off activity

Cycle information

Daily logs

Map stops

Local Setup

Prerequisites

Install:

Python 3.x

Node.js

npm

Git

1. Clone the Repository

git clone <YOUR_GITHUB_REPOSITORY_URL>
cd hos-trip-planner

Backend Setup

2. Navigate to Backend

cd backend

3. Create Virtual Environment

python -m venv .venv

4. Activate Virtual Environment

Windows PowerShell

.venv\Scripts\Activate.ps1

Windows Command Prompt

.venv\Scriptsctivate

macOS / Linux

source .venv/bin/activate

5. Install Dependencies

pip install -r requirements.txt

6. Run Database Migrations

python manage.py migrate

7. Start Django Backend

python manage.py runserver 8000

Backend:

http://localhost:8000

Health endpoint:

http://localhost:8000/api/health/

Frontend Setup

Open a new terminal.

8. Navigate to Frontend

cd frontend

9. Install Dependencies

npm install

10. Configure Backend URL

Create:

frontend/.env.local

Add:

VITE_API_URL=http://localhost:8000

11. Start React/Vite

npm run dev

Frontend:

http://localhost:5173

Running the Application

Start the backend first:

cd backend
.venv\Scripts\Activate.ps1
python manage.py runserver 8000

Then start the frontend in a second terminal:

cd frontend
npm run dev

Open:

http://localhost:5173

Testing

The project contains 200 unique HOS tests covering the core scheduling requirements and edge cases.

Run HOS Tests

From the backend/ directory:

python manage.py test planner.tests.test_hos -v 2

Run All Django Tests

python manage.py test

Test Coverage Areas

HOS Rules

11-hour driving limit

14-hour driving window

30-minute break

10-hour reset

70-hour / 8-day cycle

34-hour restart

1,000-mile fuel interval

Trip Planning

Short routes

Long routes

Multi-day routes

Multiple route segments

Pickup and drop-off

Different cycle starting values

Different start times

Mileage

Route-distance preservation

Fractional mileage

1,000-mile boundaries

Multiple fuel checkpoints

Long-distance routes

Activity Validation

Activity chronology

Activity duration

Driving mileage

Break placement

Rest placement

Fuel-stop placement

Pickup duration

Drop-off duration

Daily Logs

Midnight splitting

24-hour daily totals

Daily mileage

Daily driving hours

Daily on-duty hours

Daily off-duty hours

Multi-day schedules

Edge Cases

Zero-distance segments

Very short routes

Very long routes

Cycle near the 70-hour limit

Fractional distances

Midnight crossings

Multiple service activities

Daily Log Generation

For trips spanning multiple calendar days, the backend:

Generates the chronological activity timeline.

Splits activities at midnight.

Allocates mileage proportionally when activities cross midnight.

Fills uncovered periods with off-duty time.

Calculates daily driving hours.

Calculates daily on-duty hours.

Calculates daily off-duty hours.

Calculates daily mileage.

Validates that each generated daily log totals exactly 24 hours.

Returns the logs to the frontend.

The frontend displays the schedule using a:

24-hour x 15-minute duty-status grid

The digital logs are an assessment-oriented visualization and are not represented as a certified production ELD/RODS compliance system.

External Mapping Services

OpenStreetMap

Used as the map-data source for the interactive map.

Nominatim

Used for location geocoding.

OSRM

Used for:

Road routing

Route geometry

Route distance

Estimated driving duration

Production Consideration

Public mapping endpoints are appropriate for an assessment/demo environment but should not be treated as unlimited or SLA-backed production infrastructure.

A production implementation should consider:

Server-side caching

Rate limiting

Request throttling

Retry handling

Monitoring

Managed routing infrastructure

Self-hosted routing infrastructure

Production Build

Build Frontend

From frontend/:

npm run build

The production build is generated at:

frontend/dist/

Deployment

Backend — Render

The repository includes:

render.yaml

and:

backend/Dockerfile

Deploy the backend as a Docker service on Render.

Configure the required environment values in the deployment environment.

Frontend — Vercel

Deploy the frontend/ directory to Vercel.

Build Command

npm run build

Output Directory

dist

Environment Variable

VITE_API_URL=https://<deployed-backend-url>

Security Considerations

The project is configured for an assessment/demo environment.

For production deployment, additionally apply:

Restricted Django ALLOWED_HOSTS

Restricted CORS origins

HTTPS

Secure environment-variable management

API rate limiting

Authentication and authorization where required

Structured application logging

Monitoring and alerting

External-service request limits

Known Scope Limitations

The planner intentionally does not automatically infer:

Split-sleeper provisions

Adverse-driving-condition exceptions

CDL short-haul exceptions

Non-CDL short-haul exceptions

16-hour short-haul exceptions

Personal-conveyance rules

Yard-move rules

Other special HOS exceptions requiring additional historical or operational information

The current_cycle_used input represents the driver's already-used cycle hours supplied by the assessment.

The planner uses that value to calculate remaining cycle capacity. It does not reconstruct historical duty records that were not supplied as input.

Assessment Validation

The implementation validates the following core invariants:

Requirement

Implementation

Maximum driving

11 hours

Driving window

14 consecutive hours

Break threshold

8 cumulative driving hours

Break duration

30 minutes

Normal reset

10 hours off duty

Cycle

70 hours / 8 days

Cycle restart

34 hours

Pickup

1 hour

Drop-off

1 hour

Fuel interval

≤ 1,000 route miles

Daily log

24 hours per calendar day

Automated tests

200 unique tests

Engineering Design

The HOS scheduler is implemented as a deterministic scheduling layer separate from routing and presentation.

This separation allows:

HOS rules to be tested independently.

External routing services to be isolated from scheduling logic.

Route segments to be converted into a chronological activity timeline.

Daily logs to be generated from the same source activity timeline.

Frontend map and log views to consume a consistent backend response.

Assessment Deliverables

The final assessment package should contain:

GitHub repository

Backend source code

React frontend

HOS scheduling engine

Automated HOS test suite

Deployment configuration

Live frontend deployment

Live backend/API deployment

Demonstration of trip planning

Demonstration of HOS itinerary

Demonstration of multi-day daily logs

Assessment walkthrough / Loom video, if required

License

This project was developed for the HOS Trip Planner Full Stack Developer Assessment.