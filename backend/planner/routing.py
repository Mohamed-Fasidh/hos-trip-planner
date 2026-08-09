import os
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
import requests

NOMINATIM = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
OSRM = os.getenv("OSRM_URL", "https://router.project-osrm.org/route/v1/driving")
HEADERS = {"User-Agent": "HOSTripPlanner/1.0 (assessment app)"}

@lru_cache(maxsize=256)
def geocode(query: str):
    r = requests.get(NOMINATIM, params={"q": query, "format": "jsonv2", "limit": 1}, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    if not data:
        raise ValueError(f"Could not find location: {query}")
    return {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"]), "display": data[0].get("display_name", query)}

@lru_cache(maxsize=256)
def _route_cached(coord_string: str):
    r = requests.get(f"{OSRM}/{coord_string}", params={"overview": "full", "geometries": "geojson", "steps": "true"}, timeout=30)
    r.raise_for_status()
    data = r.json()
    if data.get("code") != "Ok" or not data.get("routes"):
        raise ValueError("Routing service could not build a route for these locations.")
    rt = data["routes"][0]
    return {"distance_miles": rt["distance"] / 1609.344, "duration_hours": rt["duration"] / 3600, "geometry": rt["geometry"], "legs": rt.get("legs", [])}

def route(points):
    coords = ";".join(f"{p['lon']},{p['lat']}" for p in points)
    return _route_cached(coords)

def geocode_many(labels):
    # Nominatim's policy favors modest request rates; parallelism is capped at 3 and
    # the LRU cache prevents duplicate calls when users submit the same trip again.
    with ThreadPoolExecutor(max_workers=min(3, len(labels))) as ex:
        return list(ex.map(geocode, labels))

def route_many(pairs):
    with ThreadPoolExecutor(max_workers=min(2, len(pairs))) as ex:
        return list(ex.map(lambda pair: route(pair), pairs))
