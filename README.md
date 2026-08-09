# HOS Trip Planner

A production-oriented full-stack Hours of Service (HOS) trip planning application built with Django and React.

The application calculates HOS-aware trip schedules, including driving periods, mandatory breaks, off-duty resets, fuel stops, pickup and drop-off activities, cycle limits, and multi-day driver's daily logs.

---

## Project Overview

The HOS Trip Planner was developed for a Full Stack Developer assessment focused on building an HOS-aware trip planning system.

The application allows a driver or planner to enter:

- Current location
- Pickup location
- Drop-off location
- Current 70/8 cycle hours

The system then:

1. Geocodes the requested locations.
2. Calculates the driving route.
3. Separates the route into route legs.
4. Applies the configured HOS rules.
5. Schedules driving periods.
6. Inserts mandatory 30-minute breaks.
7. Schedules 10-hour off-duty resets.
8. Tracks the 70-hour / 8-day cycle.
9. Schedules a conservative 34-hour restart when required.
10. Schedules fuel stops before the 1,000-mile assessment limit.
11. Adds pickup and drop-off service time.
12. Generates multi-day daily logs.
13. Displays the generated itinerary.
14. Renders digital RODS-style daily log sheets.
15. Provides print/PDF functionality.

---

## Assessment Scope

The planner follows the assessment assumptions for a property-carrying driver.

The implemented assessment scope includes:

- 70-hour / 8-day cycle
- 11-hour maximum driving limit
- 14-hour driving window
- 30-minute break after 8 cumulative driving hours
- 10-hour off-duty reset
- Fueling at least once every 1,000 route miles
- 1-hour pickup
- 1-hour drop-off
- Multi-day daily logs
- Route calculation
- Current location → pickup → drop-off routing

The planner does not automatically apply HOS exceptions that are outside the assessment assumptions.

---

## HOS Rules

### 1. 11-Hour Driving Limit

The planner limits the driver's driving time to a maximum of 11 hours within an applicable driving window.

Driving time is tracked independently from non-driving activities.

### 2. 14-Hour Driving Window

Driving must occur within the applicable 14-consecutive-hour work window.

A qualifying 10-hour off-duty reset starts a new driving window.

### 3. 30-Minute Break

A 30-minute consecutive break is scheduled after 8 cumulative driving hours.

The scheduler tracks cumulative driving time and inserts the break before additional driving would violate the configured assessment rule.

### 4. 10-Hour Off-Duty Reset

A normal 10-hour off-duty period resets the driver's:

- 11-hour driving allowance
- 14-hour driving window

The planner schedules the reset when the current driving window can no longer safely support continued driving.

### 5. 70-Hour / 8-Day Cycle

The planner accepts the driver's current cycle hours as an input.

Example:

```text
Cycle Limit:          70 hours
Current Cycle Hours:  65 hours
Remaining Cycle:       5 hours
```

The supplied current-cycle hours reduce the driver's available cycle time.

When the remaining cycle cannot support continued driving under the configured assessment rules, the planner schedules a conservative restart.

### 6. 34-Hour Restart

When the remaining cycle cannot support continued driving, the planner can schedule a conservative 34-hour restart.

After the restart:

```text
Cycle Hours = 0
```

The driver can then continue under a new cycle.

### 7. Pickup

Pickup is modeled as:

```text
1 hour of on-duty non-driving time
```

Pickup time is included in the itinerary and daily logs.

### 8. Drop-Off

Drop-off is modeled as:

```text
1 hour of on-duty non-driving time
```

Drop-off time is included in the itinerary and daily logs.

### 9. Fuel Stops

The assessment requires fueling at least once every 1,000 route miles.

The planner intentionally uses an internal threshold of:

```text
1,000 route miles
```

Fuel stops are scheduled so that the route-mile interval never exceeds 1,000 miles.

Fuel stops are therefore scheduled before the route-mile interval reaches 1,000 miles.

### 10. Daily Driver Logs

The planner generates multi-day 24-hour driver's daily logs.

Each daily log contains the driver's activities for a calendar day, including:

- Off-duty periods
- Driving periods
- 30-minute breaks
- Fuel stops
- Pickup
- Drop-off
- 10-hour resets
- 34-hour restart periods
- Daily mileage
- Daily duty hours

The frontend renders each day as a digital RODS-style sheet.

---

## System Architecture

```text
                         React Frontend
                              |
                              | HTTP / JSON
                              v
                       Django REST API
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
          Geocoding        Routing        HOS Planner
          Nominatim         OSRM          Scheduling Engine
              |               |               |
              +---------------+---------------+
                              |
                              v
                     Daily Log Generator
                              |
                              v
                    Digital RODS-style Logs
```

---

## Trip Planning Flow

```text
User Input
    |
    v
Current Location
    |
    v
Geocoding
    |
    v
Pickup Location
    |
    v
Route Calculation
    |
    v
HOS Scheduling
    |
    +---- 11-hour limit
    |
    +---- 14-hour window
    |
    +---- 30-minute break
    |
    +---- 10-hour reset
    |
    +---- 70/8 cycle
    |
    +---- Fuel threshold
    |
    +---- Pickup
    |
    +---- Drop-off
    |
    v
ELD Itinerary
    |
    v
Daily Log Generation
    |
    v
Digital RODS-style Logs
```

---

## Technology Stack

### Frontend

- React
- JavaScript
- Vite
- Responsive CSS
- SVG-based daily log rendering
- Route/map visualization

### Backend

- Python
- Django
- Django REST API

### Mapping

- OpenStreetMap
- Nominatim
- OSRM

### Testing

- Python unittest
- Django test framework

### Deployment

- Docker
- Render
- Vercel

---

## Project Structure

```text
hos-trip-planner/
├── backend/
│   ├── .venv/
│   ├── config/
│   │   ├── __pycache__/
│   │   ├── __init__.py
│   │   ├── settings.py
│   │   ├── urls.py
│   │   └── wsgi.py
│   │
│   ├── planner/
│   │   ├── __pycache__/
│   │   ├── tests/
│   │   │   ├── __pycache__/
│   │   │   ├── __init__.py
│   │   │   └── test_hos.py
│   │   │
│   │   ├── __init__.py
│   │   ├── hos.py
│   │   ├── routing.py
│   │   └── views.py
│   │
│   ├── db.sqlite3
│   ├── Dockerfile
│   ├── manage.py
│   └── requirements.txt
│
├── docs/
│   └── HOS_RULES.md
│
├── frontend/
│   ├── node_modules/
│   ├── src/
│   │   ├── main.jsx
│   │   └── styles.css
│   │
│   ├── .env.example
│   ├── .env.local
│   ├── index.html
│   ├── log-template.png
│   ├── package-lock.json
│   ├── package.json
│   └── vercel.json
│
├── .gitignore
├── render.yaml
└── README.md
```

## Backend API

The Django backend exposes a JSON API for generating an HOS-aware trip plan.

### Example Request

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "current_cycle_used": 65
}
```

### Example Response Structure

```json
{
  "summary": {
    "total_miles": 2022.4,
    "driving_hours": 35.63,
    "daily_logs": 4
  },
  "itinerary": [],
  "daily_logs": []
}
```

The exact response fields depend on the backend implementation.

---

## Route Structure

The application treats the trip as two route legs.

```text
Current Location
       |
       | Route Leg 1
       v
    Pickup
       |
       | Route Leg 2
       v
   Drop-off
```

Example:

```text
Chicago, IL
     |
     v
Dallas, TX
     |
     v
Phoenix, AZ
```

Pickup service time is inserted between the two route legs.

---

## Local Setup

### Clone the Repository

```bash
git clone <YOUR_GITHUB_REPOSITORY_URL>
cd hos-trip-planner
```

---

## Backend Setup

### Create Virtual Environment

#### Windows

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
.venv\Scripts\activate
```

#### macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

### Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### Run Django Backend

```bash
python manage.py runserver 8000
```

The backend will be available at:

```text
http://localhost:8000
```

---

## Frontend Setup

Open another terminal:

```bash
cd frontend
npm install
```

---

## Frontend Environment Configuration

Create:

```text
frontend/.env.local
```

Add:

```dotenv
VITE_API_URL=http://localhost:8000
```

---

## Run Frontend

```bash
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

---

## Running the Application

### Terminal 1 — Backend

```bash
cd backend
.venv\Scripts\activate
python manage.py runserver 8000
```

### Terminal 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Open the Vite development URL displayed in the terminal.

---

## Testing

The project includes an automated HOS test suite covering a variety of scheduling scenarios.

### Run the Complete Django Test Suite

```bash
cd backend
python manage.py test
```

### Run Only HOS Planner Tests

```bash
python manage.py test planner.tests.test_hos
```

### Run With Verbose Output

```bash
python manage.py test planner.tests.test_hos -v 2
```

---

## Test Coverage

The test suite covers multiple categories.

### Basic Route Tests

- Short routes
- Medium routes
- Long routes
- Very long routes
- Zero-distance routes
- Fractional-distance routes
- Multi-segment routes
- Routes crossing calendar days

### Driving Tests

- 11-hour driving limit
- Multiple driving windows
- Driving after a reset
- Long-distance driving
- Daily driving calculations
- Driving time accumulation

### Break Tests

- 8-hour cumulative driving threshold
- 30-minute break insertion
- Break timing
- Multiple breaks
- Breaks across calendar days

### Reset Tests

- 10-hour off-duty reset
- Reset after driving limit
- Reset across midnight
- Multiple resets
- Driving after reset

### Cycle Tests

- Low remaining cycle hours
- High remaining cycle hours
- Cycle exhaustion
- 34-hour restart
- Cycle reset after restart
- Continued driving after restart

### Fuel Tests

- Routes below 1,000 miles
- Routes close to 1,000 miles
- Routes at the assessment boundary
- Routes above 1,000 miles
- Multiple fuel stops
- Long-distance fuel intervals
- Fuel stops across multiple driving periods
- Fuel stops after resets

### Service Tests

- Pickup duration
- Drop-off duration
- Pickup before route continuation
- Drop-off at trip completion
- Pickup crossing midnight
- Drop-off crossing midnight

### Daily Log Tests

- Single-day trips
- Multi-day trips
- Midnight transitions
- Daily mileage
- Daily driving hours
- Duty-status periods
- Multiple calendar days
- Daily log generation

---

## Running a Specific Test

Example:

```bash
python manage.py test planner.tests.test_hos.HOSPlannerTests.test_fuel_stop_is_added_before_1000_miles
```

Run the complete HOS test module:

```bash
python manage.py test planner.tests.test_hos
```

---

## Daily Log Generation

The planner converts the generated itinerary into multi-day driver's daily logs.

Activities are separated according to calendar dates.

Example:

```text
Day 1
|
+-- Driving
+-- 30-minute break
+-- Driving
+-- 10-hour reset
|
Day 2
|
+-- Driving
+-- Fuel stop
+-- Pickup
+-- Driving
|
Day 3
|
+-- Driving
+-- 30-minute break
+-- Driving
+-- 10-hour reset
|
Day 4
|
+-- Driving
+-- Drop-off
```

---

## Digital RODS-Style Log

The application provides a digital representation of a driver's daily log.

The generated log includes concepts represented in the supplied FMCSA driver's daily log format:

- Date
- Origin
- Destination
- Total miles
- Vehicle information
- Carrier information
- 24-hour duty-status grid
- Remarks
- Daily totals
- Shipping information

The frontend renders the log digitally using SVG-based components.

---

## Mapping and Routing

The application uses free public mapping services.

### Nominatim

Nominatim is used for geocoding location names into coordinates.

```text
Chicago, IL
     |
     v
Latitude / Longitude
```

### OSRM

OSRM is used to calculate driving routes and route distances.

```text
Current Location
       |
       v
Pickup Location
       |
       v
Drop-off Location
```

The total route distance is derived from the route legs.

---

## HOS Scheduling Engine

The scheduler processes the route sequentially.

```text
Route Distance
      |
      v
Available Driving Time
      |
      v
Check 11-Hour Limit
      |
      +---- Limit Reached ----> 10-Hour Reset
      |
      v
Check 14-Hour Window
      |
      +---- Window Reached ---> 10-Hour Reset
      |
      v
Check 8-Hour Break
      |
      +---- Break Required ---> 30-Minute Break
      |
      v
Check Fuel Distance
      |
      +---- 1,000 Miles --------> Fuel Stop
      |
      v
Check Cycle Hours
      |
      +---- Insufficient -----> 34-Hour Restart
      |
      v
Continue Driving
      |
      v
Pickup / Drop-off
      |
      v
Generate Daily Logs
```

---

## Fuel Scheduling Strategy

The assessment requires fueling at least once every 1,000 route miles.

The planner uses:

```text
Fuel Interval = 1,000 route miles
```

Therefore the intended sequence for a long route is:

```text
Start
  |
  | <= 1,000 miles
  v
Fuel Stop
  |
  | <= 1,000 miles
  v
Fuel Stop
  |
  | <= 1,000 miles
  v
Fuel Stop
  |
  v
Destination
```

The planner follows the assessment's 1,000-mile maximum fuel interval.

---

## Cycle Handling

The planner accepts the current cycle usage.

Example:

```text
70-hour cycle limit
        |
        v
Current cycle = 65 hours
        |
        v
Remaining cycle = 5 hours
```

If the remaining cycle does not provide enough time for continued driving under the configured assessment rules, the planner schedules a conservative restart.

After the restart:

```text
Cycle Hours = 0
```

The scheduler can then continue planning from the new cycle.

---

## Production Build

### Build Frontend

```bash
cd frontend
npm install
npm run build
```

The production build is generated in:

```text
frontend/dist/
```

---

## Docker

### Build Backend Docker Image

```bash
docker build -t hos-trip-planner-backend ./backend
```

### Run the Container

```bash
docker run -p 8000:8000 hos-trip-planner-backend
```

---

## Render Deployment

The `backend/` directory can be deployed as a Docker-based service on Render.

Configure the required environment variables in the Render dashboard.

The deployed API URL should then be supplied to the frontend.

---

## Vercel Deployment

Deploy the `frontend/` directory to Vercel.

### Build Command

```bash
npm run build
```

### Output Directory

```text
dist
```

### Environment Variable

```dotenv
VITE_API_URL=<DEPLOYED_BACKEND_URL>
```

---

## Environment Variables

### Frontend

Local development:

```dotenv
VITE_API_URL=http://localhost:8000
```

Production:

```dotenv
VITE_API_URL=<DEPLOYED_BACKEND_URL>
```

Backend environment variables depend on the deployment configuration.

Secrets and environment-specific configuration should never be committed to Git.

---

## Git Ignore

The project excludes local development files, generated build files, Python caches, Node modules, and environment files.

```gitignore
# Python

backend/.venv/
backend/**/__pycache__/
*.pyc
backend/db.sqlite3
*.env
*.env.*
!.env.example

# Node

frontend/node_modules/
frontend/dist/
frontend/.vite/

# OS / editor

.DS_Store
Thumbs.db
.vscode/
.idea/
```

---

## Security Considerations

The application uses environment variables for environment-specific configuration.

The repository should not contain:

```text
.env
.env.*
API keys
Secret tokens
Database credentials
Private credentials
```

Local virtual environments and generated dependencies are excluded from Git.

---

## Accuracy Scope

The scheduler follows the assessment scope and the supplied FMCSA property-carrier HOS guide.

The application is designed as an assessment-focused trip planner and not as a complete production ELD compliance platform.

The planner intentionally does not silently apply rules outside the stated assessment assumptions.

---

## Rules Not Automatically Applied

The following exceptions are outside the assessment assumptions and are therefore not automatically inferred:

- Sleeper-berth split
- Adverse-driving-condition exception
- CDL short-haul exception
- Non-CDL short-haul exception
- 16-hour short-haul exception
- Other specialized HOS exceptions

These features can be added if they become part of a future requirements scope.

---

## RODS and Daily Log Scope

The supplied FMCSA guide describes a driver's daily log containing concepts such as:

- 24-hour graph grid
- Date
- Miles
- Vehicle information
- Carrier information
- Driver duty status
- Remarks
- Total hours
- Shipping information
- Certification/signature information

The application reproduces the relevant assessment-required concepts through its digital daily log UI.

---

## External Service Considerations

The application uses public:

- OpenStreetMap
- Nominatim
- OSRM

These public services may have:

- Rate limits
- Usage restrictions
- Availability limitations
- No production SLA

For production usage, the application should consider:

- Request caching
- Rate limiting
- Retry handling
- Monitoring
- Service health checks
- Managed geocoding
- Managed routing
- Self-hosted routing infrastructure

---

## Engineering Design

The application follows a separation-of-concerns architecture.

```text
Frontend
   |
   | User interaction
   v
API Layer
   |
   | Request validation
   v
Geocoding / Routing
   |
   v
HOS Scheduling Engine
   |
   +---- Driving
   +---- Breaks
   +---- Resets
   +---- Cycle
   +---- Fuel
   +---- Pickup
   +---- Drop-off
   |
   v
Itinerary
   |
   v
Daily Log Generator
   |
   v
Frontend Visualization
```

---

## Design Principles

The implementation emphasizes:

- Deterministic scheduling
- Explicit HOS rules
- Separation of routing and scheduling
- Testable backend logic
- Multi-day itinerary generation
- Clear frontend/backend separation
- Conservative fuel safety buffer
- Reproducible test scenarios
- Environment-based configuration
- Assessment-focused behavior

---

## Assessment Validation

The implementation includes automated tests covering the primary assessment requirements and generated itinerary validation.

| Requirement | Implementation |
|---|---|
| Current location input | Implemented |
| Pickup location input | Implemented |
| Drop-off location input | Implemented |
| Current cycle hours input | Implemented |
| Route calculation | Implemented |
| Current → Pickup → Drop-off routing | Implemented |
| Maximum driving | **11 hours** |
| Driving window | **14 consecutive hours** |
| Break threshold | **8 cumulative driving hours** |
| Break duration | **30 minutes** |
| Normal reset | **10 hours off duty** |
| Cycle | **70 hours / 8 days** |
| Cycle restart | **34 hours** |
| Pickup | **1 hour** |
| Drop-off | **1 hour** |
| Fuel interval | **≤ 1,000 route miles** |
| Multi-day itinerary | Implemented |
| Daily log | **24 hours per calendar day** |
| Digital RODS-style sheet | Implemented |
| Route visualization | Implemented |
| Print/PDF | Implemented |
| Automated tests | **200 unique tests** |

---
## Future Improvements

Potential future improvements include:

- Full sleeper-berth split support
- Adverse-condition handling
- Short-haul exception handling
- Real-time traffic-aware routing
- Route caching
- Offline routing
- Driver profiles
- Fleet management
- Persistent trip history
- User authentication
- Database-backed trip storage
- ELD device integration
- Advanced compliance reporting
- Automated regulatory rule updates
- Routing-service health monitoring
- Geocoding-service fallback providers

---

## Example Assessment Input

```json
{
  "current_location": "Chicago, IL",
  "pickup_location": "Dallas, TX",
  "dropoff_location": "Phoenix, AZ",
  "cycle_hours": 65
}
```

The planner uses the input to generate:

```text
Chicago, IL
    |
    | Driving
    v
Dallas, TX
    |
    | 1-hour Pickup
    |
    | Driving
    v
Phoenix, AZ
    |
    v
1-hour Drop-off
```

The scheduler automatically inserts applicable:

```text
30-minute breaks
10-hour resets
Fuel stops
Cycle handling
34-hour restart
```

according to the configured assessment rules.

---

## Example ELD Itinerary

```text
Aug 9, 6:00 AM
    |
    +-- DRIVING
    |
Aug 9, 2:00 PM
    |
    +-- 30-minute break
    |
Aug 9, 2:30 PM
    |
    +-- DRIVING
    |
Aug 9, 5:30 PM
    |
    +-- 10-hour off-duty reset
    |
Aug 10, 3:30 AM
    |
    +-- DRIVING
    |
    +-- Fuel stop
    |
    +-- Pickup
    |
    +-- DRIVING
    |
    +-- 30-minute break
    |
    +-- 10-hour reset
    |
    +-- DRIVING
    |
    +-- Drop-off
```

---

## Project Goals

The primary goals of the project are:

1. Produce an HOS-aware trip itinerary.
2. Prevent violations of the configured driving limits.
3. Keep fuel intervals within the assessment requirement.
4. Correctly account for pickup and drop-off service time.
5. Track the 70/8 cycle.
6. Generate multi-day driver logs.
7. Provide a clear and usable React interface.
8. Maintain deterministic and testable scheduling logic.

---

## License

This project was developed for the Full Stack Developer HOS Trip Planner assessment.

It should be used according to the requirements and terms associated with the assessment.
