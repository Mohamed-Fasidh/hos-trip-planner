import os
import math
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor

import requests


NOMINATIM = os.getenv(
    "NOMINATIM_URL",
    "https://nominatim.openstreetmap.org/search",
)

# Reverse-geocoding endpoint used only to create human-readable
# descriptions for route-positioned HOS checkpoints.
NOMINATIM_REVERSE = os.getenv(
    "NOMINATIM_REVERSE_URL",
    "https://nominatim.openstreetmap.org/reverse",
)

OSRM = os.getenv(
    "OSRM_URL",
    "https://router.project-osrm.org/route/v1/driving",
)

HEADERS = {
    "User-Agent": "HOSTripPlanner/1.0 (assessment app)"
}


# =============================================================================
# DISTANCE HELPERS
# =============================================================================

def _haversine_miles(lat1, lon1, lat2, lon2):
    """
    Calculate approximate great-circle distance between two coordinates.
    """

    earth_radius_miles = 3958.7613

    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return earth_radius_miles * c


# =============================================================================
# GEOCODING
# =============================================================================

@lru_cache(maxsize=256)
def geocode(query: str):
    response = requests.get(
        NOMINATIM,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": 1,
        },
        headers=HEADERS,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()

    if not data:
        raise ValueError(
            f"Could not find location: {query}"
        )

    return {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "display": data[0].get(
            "display_name",
            query,
        ),
    }


@lru_cache(maxsize=1024)
def reverse_geocode(
    latitude: float,
    longitude: float,
):
    """
    Convert an exact route coordinate into a compact,
    human-readable road/city/state description.

    This is additive only: it does not affect routing,
    HOS calculations, route mileage, or geometry.
    """

    response = requests.get(
        NOMINATIM_REVERSE,
        params={
            "lat": latitude,
            "lon": longitude,
            "format": "jsonv2",
            "zoom": 18,
            "addressdetails": 1,
        },
        headers=HEADERS,
        timeout=15,
    )

    response.raise_for_status()

    data = response.json()
    address = data.get("address") or {}

    # -------------------------------------------------------------------------
    # Prefer a real city/town/village/municipality.
    #
    # Do NOT use county or township as the primary city because HOS Remarks
    # should identify a usable city/town/village location whenever possible.
    # -------------------------------------------------------------------------

    place_candidates = [
        address.get("city"),
        address.get("town"),
        address.get("village"),
        address.get("municipality"),
        address.get("borough"),
    ]

    city = ""

    for candidate in place_candidates:
        candidate = (candidate or "").strip()

        if not candidate:
            continue

        normalized = candidate.lower()

        # Reject administrative areas that are not useful as the
        # primary HOS city/town remark.
        if (
            normalized.endswith(" township")
            or normalized.endswith(" county")
            or normalized.endswith(" parish")
        ):
            continue

        city = candidate
        break

    state = (
        address.get("state")
        or ""
    )

    road = (
        address.get("road")
        or address.get("highway")
        or ""
    )

    return {
        "display": data.get(
            "display_name",
            "",
        ),
        "road": road,
        "city": city,
        "state": state,
    }


def location_at_route_miles(route, route_miles):
    """
    Convert a route-mile position into a human-readable
    city/state location for HOS remarks.
    """

    position = position_at_route_miles(
        route,
        route_miles,
    )

    if not position:
        return {
            "display": "Unknown location",
            "city": "",
            "state": "",
            "road": "",
        }

    latitude = position["latitude"]
    longitude = position["longitude"]

    try:
        location = reverse_geocode(
            latitude,
            longitude,
        )
    except Exception:
        return {
            "display": "Unknown location",
            "city": "",
            "state": "",
            "road": "",
        }

    city = location.get(
        "city",
        "",
    ).strip()

    state = location.get(
        "state",
        "",
    ).strip()

    road = location.get(
        "road",
        "",
    ).strip()

    # -------------------------------------------------------------------------
    # Build a concise HOS-friendly location.
    #
    # Priority:
    #   1. City + state
    #   2. City
    #   3. Road + state
    #   4. Road
    #   5. State
    #   6. Generic route location
    # -------------------------------------------------------------------------

    if city and state:
        display = f"{city}, {state}"

    elif city:
        display = city

    elif road and state:
        display = f"Near {road}, {state}"

    elif road:
        display = f"Near {road}"

    elif state:
        display = state

    else:
        display = "Route location"

    return {
        "display": display,
        "city": city,
        "state": state,
        "road": road,
        "latitude": latitude,
        "longitude": longitude,
        "route_miles": route_miles,
    }


# =============================================================================
# OSRM STEP / INSTRUCTION HELPERS
# =============================================================================

def _build_instruction(step):
    """
    Convert an OSRM step into a human-readable instruction.
    """

    maneuver = step.get("maneuver") or {}

    maneuver_type = maneuver.get(
        "type",
        "",
    )

    modifier = maneuver.get(
        "modifier",
        "",
    )

    road_name = (
        step.get("name")
        or "unnamed road"
    )

    exit_number = maneuver.get(
        "exit",
    )

    if maneuver_type == "depart":
        return f"Depart onto {road_name}"

    if maneuver_type == "arrive":
        return "Arrive at destination"

    if maneuver_type == "turn":
        if modifier:
            return (
                f"Turn {modifier} onto "
                f"{road_name}"
            )

        return f"Turn onto {road_name}"

    if maneuver_type == "new name":
        return f"Continue onto {road_name}"

    if maneuver_type == "merge":
        return f"Merge onto {road_name}"

    if maneuver_type == "on ramp":
        return f"Take the ramp onto {road_name}"

    if maneuver_type == "off ramp":
        return f"Take the exit onto {road_name}"

    if maneuver_type == "fork":
        if modifier:
            return (
                f"Keep {modifier} at the fork "
                f"onto {road_name}"
            )

        return f"Continue at the fork onto {road_name}"

    if maneuver_type == "roundabout":
        if exit_number:
            return (
                f"Enter roundabout and take "
                f"exit {exit_number} onto {road_name}"
            )

        return f"Enter roundabout onto {road_name}"

    if maneuver_type == "rotary":
        if exit_number:
            return (
                f"Enter rotary and take "
                f"exit {exit_number} onto {road_name}"
            )

        return f"Enter rotary onto {road_name}"

    if maneuver_type == "continue":
        if modifier:
            return (
                f"Continue {modifier} "
                f"onto {road_name}"
            )

        return f"Continue onto {road_name}"

    if maneuver_type == "notification":
        return f"Continue onto {road_name}"

    if road_name:
        return f"Continue on {road_name}"

    return "Continue on route"


def _extract_steps(legs):
    """
    Convert raw OSRM legs/steps into a clean structure
    that can be returned by the API.
    """

    instructions = []

    route_miles = 0.0

    for leg_index, leg in enumerate(legs or []):

        for step_index, step in enumerate(
            leg.get("steps", [])
        ):

            distance_miles = (
                step.get("distance", 0.0)
                / 1609.344
            )

            duration_minutes = (
                step.get("duration", 0.0)
                / 60.0
            )

            maneuver = (
                step.get("maneuver")
                or {}
            )

            location = (
                maneuver.get("location")
                or []
            )

            lon = None
            lat = None

            if len(location) >= 2:
                lon = float(location[0])
                lat = float(location[1])

            route_miles += distance_miles

            instructions.append(
                {
                    "index": len(instructions),
                    "leg_index": leg_index,
                    "step_index": step_index,

                    "instruction": _build_instruction(
                        step
                    ),

                    "road_name": (
                        step.get("name")
                        or ""
                    ),

                    "distance_miles": round(
                        distance_miles,
                        3,
                    ),

                    "duration_minutes": round(
                        duration_minutes,
                        2,
                    ),

                    "route_miles": round(
                        route_miles,
                        3,
                    ),

                    "latitude": lat,
                    "longitude": lon,

                    "maneuver": maneuver.get(
                        "type"
                    ),

                    "modifier": maneuver.get(
                        "modifier"
                    ),
                }
            )

    return instructions


# =============================================================================
# ROUTE GEOMETRY INDEX
# =============================================================================

def _build_geometry_index(
    geometry,
    total_distance_miles,
):
    """
    Build a cumulative-distance index over the
    GeoJSON route geometry.

    This allows the HOS scheduler to ask:

        "Where is 475 miles into this route?"

    and receive a latitude/longitude.
    """

    coordinates = (
        geometry.get("coordinates", [])
        if geometry
        else []
    )

    if not coordinates:
        return []

    points = []

    cumulative_miles = 0.0

    first_lon, first_lat = coordinates[0]

    points.append(
        {
            "route_miles": 0.0,
            "longitude": float(first_lon),
            "latitude": float(first_lat),
        }
    )

    for previous, current in zip(
        coordinates,
        coordinates[1:],
    ):
        previous_lon, previous_lat = previous
        current_lon, current_lat = current

        segment_miles = _haversine_miles(
            float(previous_lat),
            float(previous_lon),
            float(current_lat),
            float(current_lon),
        )

        cumulative_miles += segment_miles

        points.append(
            {
                "route_miles": cumulative_miles,
                "longitude": float(current_lon),
                "latitude": float(current_lat),
            }
        )

    # Geometry distance is an approximation.
    # Scale it to OSRM's authoritative route distance.
    if (
        cumulative_miles > 0
        and total_distance_miles > 0
    ):
        scale = (
            total_distance_miles
            / cumulative_miles
        )

        for point in points:
            point["route_miles"] *= scale

    return points


# =============================================================================
# FIND LOCATION ALONG ROUTE
# =============================================================================

def position_at_route_miles(
    route,
    target_miles,
):
    """
    Return the approximate coordinate at a
    requested mileage along the route.

    Example:

        position_at_route_miles(route, 475)

    returns approximately the location 475
    route miles into the trip.
    """

    index = route.get(
        "geometry_index",
        [],
    )

    if not index:
        return None

    target_miles = max(
        0.0,
        min(
            float(target_miles),
            float(
                route.get(
                    "distance_miles",
                    0.0,
                )
            ),
        ),
    )

    if target_miles <= 0:
        first = index[0]

        return {
            "latitude": first["latitude"],
            "longitude": first["longitude"],
            "route_miles": 0.0,
        }

    if target_miles >= index[-1]["route_miles"]:
        last = index[-1]

        return {
            "latitude": last["latitude"],
            "longitude": last["longitude"],
            "route_miles": route.get(
                "distance_miles",
                last["route_miles"],
            ),
        }

    for previous, current in zip(
        index,
        index[1:],
    ):
        if (
            previous["route_miles"]
            <= target_miles
            <= current["route_miles"]
        ):

            segment_distance = (
                current["route_miles"]
                - previous["route_miles"]
            )

            if segment_distance <= 0:
                ratio = 0.0
            else:
                ratio = (
                    target_miles
                    - previous["route_miles"]
                ) / segment_distance

            latitude = (
                previous["latitude"]
                + (
                    current["latitude"]
                    - previous["latitude"]
                )
                * ratio
            )

            longitude = (
                previous["longitude"]
                + (
                    current["longitude"]
                    - previous["longitude"]
                )
                * ratio
            )

            return {
                "latitude": latitude,
                "longitude": longitude,
                "route_miles": target_miles,
            }

    return None


# =============================================================================
# OSRM ROUTING
# =============================================================================

@lru_cache(maxsize=256)
def _route_cached(coord_string: str):

    response = requests.get(
        f"{OSRM}/{coord_string}",
        params={
            "overview": "full",
            "geometries": "geojson",
            "steps": "true",
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if (
        data.get("code") != "Ok"
        or not data.get("routes")
    ):
        raise ValueError(
            "Routing service could not build "
            "a route for these locations."
        )

    route_data = data["routes"][0]

    distance_miles = (
        route_data["distance"]
        / 1609.344
    )

    duration_hours = (
        route_data["duration"]
        / 3600
    )

    geometry = route_data.get(
        "geometry",
        {},
    )

    legs = route_data.get(
        "legs",
        [],
    )

    # -------------------------------------------------------------------------
    # Build clean turn-by-turn instructions
    # -------------------------------------------------------------------------

    instructions = _extract_steps(
        legs
    )

    # -------------------------------------------------------------------------
    # Build cumulative geometry index
    # -------------------------------------------------------------------------

    geometry_index = _build_geometry_index(
        geometry,
        distance_miles,
    )

    return {
        "distance_miles": round(
            distance_miles,
            3,
        ),

        "duration_hours": round(
            duration_hours,
            3,
        ),

        "geometry": geometry,

        "legs": legs,

        "instructions": instructions,

        "geometry_index": geometry_index,
    }


# =============================================================================
# SINGLE ROUTE
# =============================================================================

def route(points):

    if not points:
        raise ValueError(
            "At least one route point is required."
        )

    coords = ";".join(
        f"{p['lon']},{p['lat']}"
        for p in points
    )

    return _route_cached(coords)


# =============================================================================
# MULTI-GEOCODING
# =============================================================================

def geocode_many(labels):

    if not labels:
        return []

    # Nominatim's policy favors modest request rates.
    # Parallelism is capped at 3.
    #
    # The LRU cache prevents duplicate calls when
    # users submit the same trip again.

    with ThreadPoolExecutor(
        max_workers=min(
            3,
            len(labels),
        )
    ) as executor:

        return list(
            executor.map(
                geocode,
                labels,
            )
        )


# =============================================================================
# MULTI-ROUTE
# =============================================================================

def route_many(pairs):

    if not pairs:
        return []

    with ThreadPoolExecutor(
        max_workers=min(
            2,
            len(pairs),
        )
    ) as executor:

        return list(
            executor.map(
                lambda pair: route(pair),
                pairs,
            )
        )