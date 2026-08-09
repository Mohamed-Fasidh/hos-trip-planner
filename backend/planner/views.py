import json
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .routing import geocode_many, route_many
from .hos import build_schedule


def health(request):
    return JsonResponse(
        {
            "ok": True,
            "service": "hos-trip-planner",
        }
    )


def _parse_start(value):
    if not value:
        return datetime.now().replace(
            hour=6,
            minute=0,
            second=0,
            microsecond=0,
        )

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).replace(tzinfo=None)

    except ValueError:
        raise ValueError(
            "start_datetime must be ISO-8601"
        )


def _build_location_lookup(labels, places):
    """
    Build a simple lookup from the route location names
    to their geocoded coordinates.

    Example:

        {
            "Chicago, IL": {
                "lat": 41.8781,
                "lon": -87.6298,
                "display": "Chicago, Illinois, USA"
            }
        }

    The HOS scheduler currently stores the activity's
    location as a string. This lets the frontend associate
    those activities with their route coordinates.
    """

    lookup = {}

    for label, place in zip(labels, places):
        if not isinstance(place, dict):
            continue

        lookup[str(label).strip().lower()] = {
            "lat": place.get("lat"),
            "lon": place.get("lon"),
            "display": place.get(
                "display",
                label,
            ),
        }

    return lookup


def _activity_stop_type(activity):
    """
    Convert backend HOS activity types into frontend
    map stop types.

    Returns None for normal driving/on-duty activities.
    """

    kind = str(
        activity.get("kind", "")
    ).upper()

    note = str(
        activity.get("note", "")
    ).lower()

    if "34-hour cycle restart" in note:
        return "RESTART_34H"

    if "fuel" in note:
        return "FUEL"

    if "30-minute break" in note:
        return "BREAK_30M"

    if "10-hour off-duty reset" in note:
        return "REST_10H"

    if "pickup" in note:
        return "PICKUP"

    if "drop-off" in note:
        return "DROPOFF"

    if kind == "OFF_DUTY":
        return "OFF_DUTY"

    return None


def _build_schedule_stops(schedule, location_lookup):
    """
    Convert HOS activities into map-ready stop objects.

    Only activities that represent meaningful stops are
    returned.

    Each stop contains:

        type
        label
        location
        start
        end
        lat
        lon
        note
        miles
    """

    stops = []

    activities = schedule.get(
        "activities",
        [],
    )

    for activity in activities:

        stop_type = _activity_stop_type(
            activity
        )

        if stop_type is None:
            continue

        location = str(
            activity.get("location", "")
        ).strip()

        location_data = location_lookup.get(
            location.lower()
        )

        # If the scheduler's location isn't one of the
        # three known route places, don't invent coordinates.
        if not location_data:
            continue

        lat = location_data.get("lat")
        lon = location_data.get("lon")

        if lat is None or lon is None:
            continue

        label_map = {
            "PICKUP": "Pickup",
            "DROPOFF": "Drop-off",
            "FUEL": "Fuel stop",
            "BREAK_30M": "30-minute break",
            "REST_10H": "10-hour rest",
            "RESTART_34H": "34-hour cycle restart",
            "OFF_DUTY": "Off duty",
        }

        stops.append(
            {
                "type": stop_type,
                "label": label_map.get(
                    stop_type,
                    stop_type,
                ),
                "location": location,
                "display": location_data.get(
                    "display",
                    location,
                ),
                "start": activity.get(
                    "start"
                ),
                "end": activity.get(
                    "end"
                ),
                "lat": lat,
                "lon": lon,
                "note": activity.get(
                    "note",
                    "",
                ),
                "miles": float(
                    activity.get(
                        "miles",
                        0,
                    ) or 0
                ),
            }
        )

    return stops


@csrf_exempt
def plan_trip(request):

    if request.method != "POST":
        return JsonResponse(
            {
                "error": "POST required"
            },
            status=405,
        )

    try:
        payload = json.loads(
            request.body or "{}"
        )

        required = [
            "current_location",
            "pickup_location",
            "dropoff_location",
            "current_cycle_used",
        ]

        missing = [
            key
            for key in required
            if not str(
                payload.get(key, "")
            ).strip()
        ]

        if missing:
            return JsonResponse(
                {
                    "error": (
                        "Missing required fields: "
                        + ", ".join(missing)
                    )
                },
                status=400,
            )

        # -------------------------------------------------
        # Validate cycle hours
        # -------------------------------------------------

        try:
            cycle = float(
                payload[
                    "current_cycle_used"
                ]
            )
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "error": (
                        "Current cycle used "
                        "must be a number."
                    )
                },
                status=400,
            )

        if cycle < 0 or cycle > 70:
            return JsonResponse(
                {
                    "error": (
                        "Current cycle used must "
                        "be between 0 and 70 hours."
                    )
                },
                status=400,
            )

        # -------------------------------------------------
        # Start time
        # -------------------------------------------------

        start = _parse_start(
            payload.get(
                "start_datetime"
            )
        )

        # -------------------------------------------------
        # Geocode the three route locations
        # -------------------------------------------------

        labels = [
            payload["current_location"],
            payload["pickup_location"],
            payload["dropoff_location"],
        ]

        places = geocode_many(
            labels
        )

        if len(places) != 3:
            raise ValueError(
                "Unable to geocode all route locations."
            )

        # -------------------------------------------------
        # Build the two route legs
        # -------------------------------------------------

        routes = route_many(
            [
                places[i : i + 2]
                for i in range(2)
            ]
        )

        if len(routes) != 2:
            raise ValueError(
                "Unable to build both route legs."
            )

        legs = []

        for i, route in enumerate(routes):

            legs.append(
                {
                    "start": labels[i],
                    "end": labels[i + 1],

                    "start_point": places[i],
                    "end_point": places[i + 1],

                    "distance_miles": float(
                        route[
                            "distance_miles"
                        ]
                    ),

                    "duration_hours": float(
                        route[
                            "duration_hours"
                        ]
                    ),

                    "geometry": route[
                        "geometry"
                    ],

                    "is_pickup": (
                        i == 0
                    ),

                    "is_dropoff": (
                        i == 1
                    ),
                }
            )

        # -------------------------------------------------
        # Build HOS schedule
        # -------------------------------------------------

        schedule = build_schedule(
            legs,
            cycle,
            start,
        )

        # -------------------------------------------------
        # Build location lookup
        # -------------------------------------------------

        location_lookup = (
            _build_location_lookup(
                labels,
                places,
            )
        )

        # -------------------------------------------------
        # Build map-ready HOS stops
        # -------------------------------------------------

        schedule_stops = (
            _build_schedule_stops(
                schedule,
                location_lookup,
            )
        )

        # -------------------------------------------------
        # Add route endpoint types
        # -------------------------------------------------

        map_stops = []

        if places:

            first = places[0]

            map_stops.append(
                {
                    "type": "START",
                    "label": "Start",
                    "location": labels[0],
                    "display": first.get(
                        "display",
                        labels[0],
                    ),
                    "lat": first.get("lat"),
                    "lon": first.get("lon"),
                }
            )

        if len(places) > 1:

            pickup = places[1]

            map_stops.append(
                {
                    "type": "PICKUP",
                    "label": "Pickup",
                    "location": labels[1],
                    "display": pickup.get(
                        "display",
                        labels[1],
                    ),
                    "lat": pickup.get("lat"),
                    "lon": pickup.get("lon"),
                }
            )

        if len(places) > 2:

            dropoff = places[2]

            map_stops.append(
                {
                    "type": "DROPOFF",
                    "label": "Drop-off",
                    "location": labels[2],
                    "display": dropoff.get(
                        "display",
                        labels[2],
                    ),
                    "lat": dropoff.get("lat"),
                    "lon": dropoff.get("lon"),
                }
            )

        # -------------------------------------------------
        # Combine endpoint + HOS stops
        # -------------------------------------------------

        for stop in schedule_stops:

            # Avoid duplicating pickup/drop-off
            # markers that already exist above.
            if stop["type"] in (
                "PICKUP",
                "DROPOFF",
            ):
                continue

            map_stops.append(
                stop
            )

        # -------------------------------------------------
        # Response
        # -------------------------------------------------

        return JsonResponse(
            {
                "inputs": payload,

                "places": places,

                "legs": legs,

                "schedule": schedule,

                # New map-ready HOS stop collection.
                "stops": map_stops,

                # Useful frontend metadata.
                "stop_summary": {
                    "start": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "START"
                    ),
                    "pickup": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "PICKUP"
                    ),
                    "dropoff": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "DROPOFF"
                    ),
                    "fuel": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "FUEL"
                    ),
                    "break_30m": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "BREAK_30M"
                    ),
                    "rest_10h": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "REST_10H"
                    ),
                    "restart_34h": sum(
                        1
                        for stop in map_stops
                        if stop["type"]
                        == "RESTART_34H"
                    ),
                },

                "rules": {
                    "cycle": "70 hours / 8 days",
                    "max_driving": 11,
                    "driving_window": 14,
                    "break_after_driving": 8,
                    "break_minutes": 30,
                    "daily_reset_hours": 10,
                    "fuel_interval_miles": 1000,
                    "pickup_dropoff_hours": 1,
                    "adverse_conditions": False,
                },
            }
        )

    except requests_exception_types() as exc:

        return JsonResponse(
            {
                "error": (
                    "External map service error: "
                    f"{exc}"
                )
            },
            status=502,
        )

    except Exception as exc:

        return JsonResponse(
            {
                "error": str(exc)
            },
            status=400,
        )


def requests_exception_types():
    import requests

    return (
        requests.RequestException,
    )