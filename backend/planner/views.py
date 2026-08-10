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



def _distance_miles(point_a, point_b):
    """Approximate distance between two [lon, lat] points in miles."""
    from math import asin, cos, radians, sin, sqrt

    lon1, lat1 = point_a
    lon2, lat2 = point_b

    lat1 = radians(float(lat1))
    lat2 = radians(float(lat2))
    dlat = lat2 - lat1
    dlon = radians(float(lon2) - float(lon1))

    value = (
        sin(dlat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    )

    return 3958.7613 * 2 * asin(
        min(1.0, sqrt(max(0.0, value)))
    )


def _point_on_route(geometry, target_miles):
    """
    Return a [lon, lat] coordinate at target_miles along
    an OSRM GeoJSON LineString.
    """
    if not geometry:
        return None

    coordinates = geometry.get(
        "coordinates",
        geometry,
    )

    if not isinstance(coordinates, list) or len(coordinates) < 2:
        return None

    target = max(0.0, float(target_miles))
    travelled = 0.0

    for index in range(1, len(coordinates)):
        previous = coordinates[index - 1]
        current = coordinates[index]

        if (
            not isinstance(previous, (list, tuple))
            or not isinstance(current, (list, tuple))
            or len(previous) < 2
            or len(current) < 2
        ):
            continue

        segment = _distance_miles(
            previous,
            current,
        )

        if travelled + segment >= target:
            if segment <= 1e-12:
                return [
                    float(current[0]),
                    float(current[1]),
                ]

            ratio = (
                target - travelled
            ) / segment

            ratio = max(
                0.0,
                min(1.0, ratio),
            )

            lon = (
                float(previous[0])
                + (
                    float(current[0])
                    - float(previous[0])
                ) * ratio
            )

            lat = (
                float(previous[1])
                + (
                    float(current[1])
                    - float(previous[1])
                ) * ratio
            )

            return [lon, lat]

        travelled += segment

    last = coordinates[-1]

    if (
        isinstance(last, (list, tuple))
        and len(last) >= 2
    ):
        return [
            float(last[0]),
            float(last[1]),
        ]

    return None


def _build_route_lookup(legs):
    """
    Build cumulative-mile ranges for each route leg.
    """
    lookup = []
    cumulative = 0.0

    for leg in legs:
        distance = max(
            0.0,
            float(
                leg.get(
                    "distance_miles",
                    0.0,
                )
                or 0.0
            ),
        )

        lookup.append(
            {
                "start_miles": cumulative,
                "end_miles": (
                    cumulative + distance
                ),
                "geometry": leg.get(
                    "geometry"
                ),
            }
        )

        cumulative += distance

    return lookup


def _coordinate_for_route_miles(
    route_lookup,
    route_miles,
):
    """
    Convert cumulative route miles into a coordinate
    on the corresponding OSRM route leg.
    """
    if not route_lookup:
        return None

    target = max(
        0.0,
        float(route_miles),
    )

    for leg in route_lookup:
        if (
            target
            <= leg["end_miles"] + 1e-8
        ):
            local_miles = max(
                0.0,
                target
                - leg["start_miles"],
            )

            return _point_on_route(
                leg["geometry"],
                local_miles,
            )

    last = route_lookup[-1]

    return _point_on_route(
        last["geometry"],
        max(
            0.0,
            last["end_miles"]
            - last["start_miles"],
        ),
    )


def _build_schedule_stops(
    schedule,
    location_lookup,
    route_lookup=None,
):
    """
    Convert HOS activities into map-ready stop objects.

    Endpoint activities use their geocoded coordinates.
    Intermediate activities such as fuel, breaks, resets,
    and restarts use cumulative route mileage and the
    actual OSRM route geometry.

    Important:
    Activity.miles is the distance of that individual
    driving activity, not cumulative trip mileage. Therefore
    cumulative route mileage is calculated here by walking
    through the activities in chronological order.
    """
    stops = []

    activities = schedule.get(
        "activities",
        [],
    )

    cumulative_route_miles = 0.0

    label_map = {
        "PICKUP": "Pickup",
        "DROPOFF": "Drop-off",
        "FUEL": "Fuel stop",
        "BREAK_30M": "30-minute break",
        "REST_10H": "10-hour rest",
        "RESTART_34H": "34-hour cycle restart",
        "OFF_DUTY": "Off duty",
    }

    for activity in activities:
        stop_type = _activity_stop_type(
            activity
        )

        activity_miles = float(
            activity.get(
                "miles",
                0.0,
            )
            or 0.0
        )

        if stop_type is None:
            if str(
                activity.get(
                    "kind",
                    "",
                )
            ).upper() == "DRIVING":
                cumulative_route_miles += max(
                    0.0,
                    activity_miles,
                )

            continue

        location = str(
            activity.get(
                "location",
                "",
            )
        ).strip()

        location_data = location_lookup.get(
            location.lower()
        )

        lat = None
        lon = None
        display = location

        # Activity metadata generated by the HOS scheduler is the
        # canonical source for event position. This keeps the ELD
        # itinerary, map markers, and daily logs synchronized.
        activity_route_miles = activity.get(
            "route_miles"
        )

        if activity_route_miles is not None:
            try:
                route_miles = float(
                    activity_route_miles
                )
            except (TypeError, ValueError):
                route_miles = cumulative_route_miles
        else:
            route_miles = cumulative_route_miles

        activity_lat = activity.get(
            "latitude"
        )
        activity_lon = activity.get(
            "longitude"
        )

        if (
            activity_lat is not None
            and activity_lon is not None
        ):
            try:
                lat = float(activity_lat)
                lon = float(activity_lon)
            except (TypeError, ValueError):
                lat = None
                lon = None

        # Pickup/drop-off are real geocoded endpoints.
        # Prefer the scheduler's coordinates when present,
        # otherwise retain the existing endpoint lookup.
        if (
            lat is None
            or lon is None
        ) and location_data:
            lat = location_data.get("lat")
            lon = location_data.get("lon")
            display = location_data.get(
                "display",
                location,
            )

        # Intermediate HOS events should already contain their
        # route position from the scheduler. Use OSRM geometry
        # only as a backward-compatible fallback.
        if (
            lat is None
            or lon is None
        ):
            coordinate = (
                _coordinate_for_route_miles(
                    route_lookup or [],
                    route_miles,
                )
            )

            if coordinate is None:
                # Do not create a fake map coordinate.
                # The HOS activity remains available in
                # the schedule/ELD itinerary.
                continue

            lon, lat = coordinate

        if (
            location.lower()
            == "route checkpoint"
        ):
            display = (
                f"Route checkpoint "
                f"({route_miles:.1f} mi)"
            )

        stops.append(
            {
                "type": stop_type,
                "label": label_map.get(
                    stop_type,
                    stop_type,
                ),
                "location": location,
                "display": display,
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
                # Preserve the activity's own
                # mileage for compatibility.
                "miles": activity_miles,
                # Explicit cumulative mileage used
                # for intermediate map placement.
                "route_miles": route_miles,
            }
        )

        # A stop normally has zero miles, but this keeps
        # cumulative mileage correct if a future service
        # activity carries distance.
        if str(
            activity.get(
                "kind",
                "",
            )
        ).upper() == "DRIVING":
            cumulative_route_miles += max(
                0.0,
                activity_miles,
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

                    # Expose the existing OSRM turn-by-turn
                    # instructions to the frontend.
                    # No routing/HOS parameters are changed.
                    "instructions": route.get(
                        "instructions",
                        []
                    ),

                    "is_pickup": (
                        i == 0
                    ),

                    "is_dropoff": (
                        i == 1
                    ),
                }
            )

        # -------------------------------------------------
        # Flatten turn-by-turn instructions from both legs
        # -------------------------------------------------

        instructions = []

        for leg_index, leg in enumerate(legs):
            leg_instructions = leg.get(
                "instructions",
                []
            )

            for instruction in leg_instructions:
                if not isinstance(instruction, dict):
                    continue

                item = dict(instruction)

                # Preserve which logical trip leg this
                # instruction belongs to.
                item["leg_index"] = leg_index

                instructions.append(item)

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
        # Build route lookup
        # -------------------------------------------------

        route_lookup = _build_route_lookup(
            legs
        )

        # -------------------------------------------------
        # Resolve HOS activity positions on the route
        # -------------------------------------------------

        def position_resolver(route_miles):
            coordinate = _coordinate_for_route_miles(
                route_lookup,
                route_miles,
            )

            if coordinate is None:
                return None

            lon, lat = coordinate

            return {
                "latitude": lat,
                "longitude": lon,
            }

        # -------------------------------------------------
        # Build HOS schedule
        # -------------------------------------------------

        schedule = build_schedule(
            legs,
            cycle,
            start,
            position_resolver=position_resolver,
        )

        # -------------------------------------------------
        # Build map-ready HOS stops
        # -------------------------------------------------

        schedule_stops = (
            _build_schedule_stops(
                schedule,
                location_lookup,
                route_lookup,
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

                # Flattened turn-by-turn route instructions
                # from both route legs for the frontend.
                "instructions": instructions,

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