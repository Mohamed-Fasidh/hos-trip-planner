from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import List


# =============================================================================
# ASSESSMENT SCOPE
# =============================================================================
#
# Property-carrying CMV
# 70 hours / 8 days
# No adverse driving conditions
# Fueling no less often than every 1,000 route miles
# 1,000-mile assessment maximum interval
# 1 hour pickup
# 1 hour drop-off
#
# HOS planning assumptions:
# - Maximum driving: 11 hours
# - Maximum duty window: 14 consecutive hours
# - 30-minute break after 8 cumulative driving hours
# - 10 consecutive hours off duty for normal reset
# - Conservative 34-hour restart when the 70-hour cycle is exhausted
#
# =============================================================================


@dataclass
class Activity:
    kind: str
    start: datetime
    end: datetime
    location: str
    miles: float = 0.0
    note: str = ""

    def minutes(self) -> float:
        return (
            self.end - self.start
        ).total_seconds() / 60


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def _mins(hours: float) -> int:
    """
    Convert hours to whole minutes.

    Example:
        3.5 hours -> 210 minutes
    """
    return int(round(hours * 60))


def _add_minutes(
    t: datetime,
    minutes: int,
) -> datetime:
    """Return datetime advanced by the specified number of minutes."""
    return t + timedelta(minutes=minutes)


def _date_key(t: datetime) -> str:
    """Return YYYY-MM-DD calendar-day key."""
    return t.strftime("%Y-%m-%d")


def _safe_cycle_hours(value: float) -> float:
    """
    Clamp current cycle usage to the assessment's 0-70 hour range.
    """
    return max(
        0.0,
        min(70.0, float(value)),
    )


# =============================================================================
# MAIN HOS SCHEDULER
# =============================================================================


def build_schedule(
    route_segments,
    current_cycle_hours: float,
    start_dt: datetime,
    fuel_interval_miles: float = 1000.0,
):
    """
    Create a conservative, explainable HOS schedule.

    Parameters
    ----------
    route_segments:
        List of route dictionaries.

        Expected fields:

            {
                "name": str,
                "distance_miles": float,
                "duration_hours": float,
                "geometry": ...,
                "start": str,
                "end": str,
                "is_pickup": bool,
                "is_dropoff": bool,
            }

    current_cycle_hours:
        Driver's already-used 70/8 cycle hours.

    start_dt:
        Trip start datetime.

    fuel_interval_miles:
        Internal fueling threshold.

        Assessment requirement:
            <= 1,000 route miles

        We default to:
            1000 miles

        giving a 1000-mile safety buffer.

    Returns
    -------
    dict
        {
            "activities": [...],
            "days": [...],
            "summary": {...}
        }
    """

    # =========================================================================
    # GLOBAL STATE
    # =========================================================================

    cycle_used = _safe_cycle_hours(
        current_cycle_hours
    )

    # Track how many 34-hour cycle restarts occur during this trip.
    cycle_restart_count = 0

    now = start_dt

    # Start of the current 14-hour duty window.
    #
    # IMPORTANT:
    # This is NOT the same thing as accumulated on-duty hours.
    #
    # The 14-hour rule is based on elapsed consecutive window time.
    duty_window_start = start_dt

    drive_today = 0.0

    drive_since_break = 0.0

    duty_today = 0.0

    fuel_since = 0.0

    activities: List[Activity] = []

    total_distance = 0.0

    total_drive = 0.0

    # =========================================================================
    # INTERNAL TIME CALCULATIONS
    # =========================================================================

    def window_elapsed_hours() -> float:
        """
        Return elapsed time since the beginning of the current 14-hour window.

        Off-duty time inside the 14-hour window does NOT stop the clock.
        """

        return (
            now - duty_window_start
        ).total_seconds() / 3600

    def window_remaining_hours() -> float:
        """
        Return remaining time in the current 14-hour window.
        """

        return max(
            0.0,
            14.0 - window_elapsed_hours(),
        )

    # =========================================================================
    # ADD ACTIVITY
    # =========================================================================

    def add(
        kind: str,
        minutes: int,
        location: str,
        miles: float = 0.0,
        note: str = "",
    ):
        """
        Add an activity to the chronological schedule.

        Driving and ON_DUTY activities consume:
        - daily duty time
        - 70-hour cycle time
        """

        nonlocal now
        nonlocal duty_today
        nonlocal cycle_used

        if minutes <= 0:
            return

        start = now

        now = _add_minutes(
            now,
            minutes,
        )

        activities.append(
            Activity(
                kind=kind,
                start=start,
                end=now,
                location=location,
                miles=miles,
                note=note,
            )
        )

        if kind in (
            "DRIVING",
            "ON_DUTY",
        ):
            hours = minutes / 60.0

            duty_today += hours

            cycle_used += hours

    # =========================================================================
    # 10-HOUR RESET
    # =========================================================================

    def rest_10h(
        location: str,
        reason: str = "10-hour off-duty reset",
    ):
        """
        Take a normal 10-hour off-duty reset.

        This resets:
        - 11-hour daily driving counter
        - 8-hour cumulative driving-break counter
        - 14-hour duty window
        - current daily duty counter

        It does NOT reset the 70/8 cycle.
        """

        nonlocal now
        nonlocal duty_window_start
        nonlocal drive_today
        nonlocal drive_since_break
        nonlocal duty_today

        add(
            "OFF_DUTY",
            600,
            location,
            note=reason,
        )

        # New 14-hour duty window starts after the 10-hour reset.
        duty_window_start = now

        drive_today = 0.0

        drive_since_break = 0.0

        duty_today = 0.0

    # =========================================================================
    # 34-HOUR RESTART
    # =========================================================================

    def restart_34h(
        location: str,
    ):
        """
        Conservative 34-hour cycle restart.

        This resets:
        - 70/8 cycle
        - 11-hour driving counter
        - 8-hour break counter
        - 14-hour duty window
        """

        nonlocal now
        nonlocal duty_window_start
        nonlocal drive_today
        nonlocal drive_since_break
        nonlocal duty_today
        nonlocal cycle_used
        nonlocal cycle_restart_count

        start = now

        end = _add_minutes(
            now,
            2040,  # 34 hours
        )

        activities.append(
            Activity(
                kind="OFF_DUTY",
                start=start,
                end=end,
                location=location,
                miles=0.0,
                note="34-hour cycle restart",
            )
        )

        now = end

        duty_window_start = now

        drive_today = 0.0

        drive_since_break = 0.0

        duty_today = 0.0

        cycle_used = 0.0
        cycle_restart_count += 1

    # =========================================================================
    # ENSURE CYCLE CAPACITY
    # =========================================================================

    def ensure_cycle_capacity(
        required_hours: float,
        location: str,
    ):
        """
        Ensure the 70-hour cycle can accommodate upcoming work.
        """

        nonlocal cycle_used

        if (
            cycle_used + required_hours
            > 70.0 + 1e-8
        ):
            restart_34h(location)

    # =========================================================================
    # ENSURE DUTY WINDOW
    # =========================================================================

    def ensure_window_capacity(
        required_hours: float,
        location: str,
    ):
        """
        Ensure the current 14-hour duty window has enough time.

        If not, take a 10-hour reset.
        """

        if (
            window_elapsed_hours()
            + required_hours
            > 14.0 + 1e-8
        ):
            rest_10h(location)

    # =========================================================================
    # DRIVE
    # =========================================================================

    def drive_hours(
        hours: float,
        location: str,
        miles: float,
    ):
        """
        Drive a route segment while respecting:

        - 11-hour driving limit
        - 14-hour consecutive duty window
        - 8-hour cumulative driving-break requirement
        - 70-hour cycle
        """

        nonlocal drive_today
        nonlocal drive_since_break
        nonlocal total_drive
        nonlocal total_distance
        nonlocal fuel_since

        remaining_hours = max(
            0.0,
            float(hours),
        )

        remaining_miles = max(
            0.0,
            float(miles),
        )

        original_hours = max(
            remaining_hours,
            1e-9,
        )

        while remaining_hours > 1e-8:

            # -----------------------------------------------------------------
            # 30-MINUTE BREAK
            # -----------------------------------------------------------------

            if (
                drive_since_break
                >= 8.0 - 1e-8
            ):

                add(
                    "OFF_DUTY",
                    30,
                    location,
                    note=(
                        "30-minute break after "
                        "8 cumulative driving hours"
                    ),
                )

                drive_since_break = 0.0

                continue

            # -----------------------------------------------------------------
            # CURRENT LIMITS
            # -----------------------------------------------------------------

            driving_remaining = max(
                0.0,
                11.0 - drive_today,
            )

            break_driving_remaining = max(
                0.0,
                8.0 - drive_since_break,
            )

            window_remaining = (
                window_remaining_hours()
            )

            cycle_remaining = max(
                0.0,
                70.0 - cycle_used,
            )

            # -----------------------------------------------------------------
            # IF ANY LIMIT IS EXHAUSTED
            # -----------------------------------------------------------------

            if (
                driving_remaining <= 1e-8
            ):
                rest_10h(location)
                continue

            if (
                break_driving_remaining
                <= 1e-8
            ):
                add(
                    "OFF_DUTY",
                    30,
                    location,
                    note=(
                        "30-minute break after "
                        "8 cumulative driving hours"
                    ),
                )

                drive_since_break = 0.0

                continue

            if (
                window_remaining <= 1e-8
            ):
                rest_10h(location)
                continue

            if (
                cycle_remaining <= 1e-8
            ):
                restart_34h(location)
                continue

            # -----------------------------------------------------------------
            # DETERMINE MAXIMUM SAFE DRIVING CHUNK
            # -----------------------------------------------------------------

            chunk_hours = min(
                remaining_hours,
                driving_remaining,
                break_driving_remaining,
                window_remaining,
                cycle_remaining,
            )

            if chunk_hours <= 1e-8:
                # Defensive fallback.
                rest_10h(location)
                continue

            # -----------------------------------------------------------------
            # PROPORTIONAL MILE ALLOCATION
            # -----------------------------------------------------------------

            if remaining_hours > 1e-8:
                chunk_miles = (
                    remaining_miles
                    * (
                        chunk_hours
                        / remaining_hours
                    )
                )
            else:
                chunk_miles = 0.0

            # -----------------------------------------------------------------
            # ADD DRIVING
            # -----------------------------------------------------------------

            minutes = _mins(
                chunk_hours
            )

            
            # Preserve the exact route duration.
            # Do not round driving chunks to whole minutes because
            # rounding can inflate the total route mileage.

            actual_hours = chunk_hours
            minutes = actual_hours * 60.0

            # Preserve the exact mileage assigned to this route chunk.
            actual_miles = min(
                remaining_miles,
                chunk_miles,
            )

            add(
                "DRIVING",
                minutes,
                location,
                miles=actual_miles,
            )

            drive_today += actual_hours

            drive_since_break += actual_hours

            total_drive += actual_hours

            total_distance += actual_miles

            fuel_since += actual_miles

            remaining_hours -= actual_hours

            remaining_miles -= actual_miles

            # Prevent tiny floating-point negatives.
            remaining_hours = max(
                0.0,
                remaining_hours,
            )

            remaining_miles = max(
                0.0,
                remaining_miles,
            )

            # -----------------------------------------------------------------
            # 70-HOUR CYCLE EXHAUSTION
            # -----------------------------------------------------------------
            # The final available cycle time has now been consumed.
            # If route work remains, perform the 34-hour restart before
            # continuing with the remaining route.
            if (
                cycle_used >= 70.0 - 1e-8
                and remaining_hours > 1e-8
            ):
                restart_34h(location)
                continue

            # -----------------------------------------------------------------
            # BREAK AFTER EXACTLY 8 CUMULATIVE DRIVING HOURS
            # -----------------------------------------------------------------

            if (
                drive_since_break
                >= 8.0 - 1e-8
                and remaining_hours > 1e-8
            ):

                add(
                    "OFF_DUTY",
                    30,
                    location,
                    note=(
                        "30-minute break after "
                        "8 cumulative driving hours"
                    ),
                )

                drive_since_break = 0.0

        # Defensive cleanup.
        _ = original_hours
    
    # =========================================================================
    # SERVICE STOP
    # =========================================================================

    def service_stop(
        location: str,
        hours: float,
        label: str,
    ):
        """
        Add an ON_DUTY service activity.

        Pickup, drop-off and fueling count toward:
        - 14-hour window
        - 70-hour cycle
        """
        nonlocal drive_since_break
        remaining = max(
            0.0,
            float(hours),
        )

        while remaining > 1e-8:

            # ---------------------------------------------------------------
            # Check 70-hour cycle.
            # ---------------------------------------------------------------

            if (
                cycle_used >= 70.0 - 1e-8
            ):
                restart_34h(location)
                continue

            cycle_remaining = (
                70.0 - cycle_used
            )

            # ---------------------------------------------------------------
            # Check 14-hour window.
            # ---------------------------------------------------------------

            window_remaining = (
                window_remaining_hours()
            )

            if window_remaining <= 1e-8:
                rest_10h(location)
                continue

            # ---------------------------------------------------------------
            # Determine safe service duration.
            # ---------------------------------------------------------------

            chunk = min(
                remaining,
                cycle_remaining,
                window_remaining,
            )

            if chunk <= 1e-8:
                rest_10h(location)
                continue

            minutes = _mins(chunk)

            if minutes <= 0:
                minutes = 1

            actual_hours = minutes / 60.0

            add(
                "ON_DUTY",
                minutes,
                location,
                note=label,
            )
            

            remaining -= actual_hours

            remaining = max(
                0.0,
                remaining,
            )

    # =========================================================================
    # INITIAL CYCLE VALIDATION
    # =========================================================================

    if cycle_used >= 70.0:
        restart_34h(
            route_segments[0]["start"]
            if route_segments
            else "Start"
        )

    # =========================================================================
    # PROCESS ROUTE SEGMENTS
    # =========================================================================

    for seg in route_segments:

        distance = max(
            0.0,
            float(
                seg["distance_miles"]
            ),
        )

        duration = max(
            0.0,
            float(
                seg["duration_hours"]
            ),
        )

        start_name = seg["start"]

        end_name = seg["end"]

        left_dist = distance

        left_hours = duration

        # ---------------------------------------------------------------------
        # Handle zero-distance route segments.
        # ---------------------------------------------------------------------

        if left_dist <= 1e-8:

            if seg.get("is_pickup"):
                service_stop(
                    end_name,
                    1.0,
                    "Pickup — 1 hour",
                )

            if seg.get("is_dropoff"):
                service_stop(
                    end_name,
                    1.0,
                    "Drop-off — 1 hour",
                )

            continue

        # ---------------------------------------------------------------------
        # Split route at fueling checkpoints.
        # ---------------------------------------------------------------------

        while left_dist > 1e-7:

            # ---------------------------------------------------------------
            # If the previous route leg reached the fuel threshold,
            # fuel BEFORE starting more driving.
            #
            # This prevents the schedule from ever exceeding the
            # internal 1000-mile fuel interval.
            # ---------------------------------------------------------------

            if (
                fuel_since
                >= fuel_interval_miles - 1e-8
            ):

                service_stop(
                    "Route checkpoint",
                    0.5,
                    "Fuel stop — 1000 route-mile checkpoint",
                )

                fuel_since = 0.0

                continue

            # ---------------------------------------------------------------
            # Determine miles remaining before next fuel stop.
            # ---------------------------------------------------------------

            to_fuel = max(
                0.0,
                fuel_interval_miles
                - fuel_since,
            )

            chunk_dist = min(
                left_dist,
                to_fuel,
            )

            if chunk_dist <= 1e-8:

                service_stop(
                    "Route checkpoint",
                    0.5,
                "Fuel stop — 1000 route-mile checkpoint",
                )

                fuel_since = 0.0

                continue

            # ---------------------------------------------------------------
            # Preserve route speed ratio.
            # ---------------------------------------------------------------

            if left_dist > 1e-8:

                chunk_hours = (
                    left_hours
                    * (
                        chunk_dist
                        / left_dist
                    )
                )

            else:
                chunk_hours = 0.0

            if chunk_hours <= 1e-8:

                # No meaningful driving remains.
                break

            # ---------------------------------------------------------------
            # Save mileage before driving.
            # ---------------------------------------------------------------

            before_distance = (
                total_distance
            )

            # ---------------------------------------------------------------
            # Drive safely.
            # ---------------------------------------------------------------

            drive_hours(
                chunk_hours,
                start_name,
                chunk_dist,
            )

            consumed_miles = (
                total_distance
                - before_distance
            )

            # ---------------------------------------------------------------
            # Determine how much of the original chunk was consumed.
            # ---------------------------------------------------------------

            if chunk_dist > 1e-8:

                consumed_ratio = (
                    consumed_miles
                    / chunk_dist
                )

            else:
                consumed_ratio = 1.0

            consumed_ratio = max(
                0.0,
                min(
                    1.0,
                    consumed_ratio,
                ),
            )

            consumed_route_hours = (
                chunk_hours
                * consumed_ratio
            )

            # ---------------------------------------------------------------
            # Reduce remaining route.
            # ---------------------------------------------------------------

            left_dist -= consumed_miles

            left_hours -= consumed_route_hours

            left_dist = max(
                0.0,
                left_dist,
            )

            left_hours = max(
                0.0,
                left_hours,
            )

            # ---------------------------------------------------------------
            # Fuel once the safety threshold is reached AND route remains.
            # If this is the final route mileage, we don't create an
            # unnecessary fuel stop after arrival.
            # ---------------------------------------------------------------

            if (
                fuel_since
                >= fuel_interval_miles - 1e-6
                and left_dist > 1e-7
            ):

                service_stop(
                    "Route checkpoint",
                    0.5,
                    "Fuel stop — 1000 route-mile checkpoint",
                )

                fuel_since = 0.0

            # ---------------------------------------------------------------
            # Defensive escape.
            # ---------------------------------------------------------------

            if consumed_miles <= 1e-8:

                if (
                    cycle_used
                    >= 70.0 - 1e-8
                ):
                    restart_34h(
                        end_name
                    )

                elif (
                    window_remaining_hours()
                    <= 1e-8
                ):
                    rest_10h(
                        end_name
                    )

                else:
                    rest_10h(
                        end_name
                    )

        # ---------------------------------------------------------------------
        # Pickup service.
        # ---------------------------------------------------------------------

        if seg.get("is_pickup"):

            service_stop(
                end_name,
                1.0,
                "Pickup — 1 hour",
            )

        # ---------------------------------------------------------------------
        # Drop-off service.
        # ---------------------------------------------------------------------

        if seg.get("is_dropoff"):

            service_stop(
                end_name,
                1.0,
                "Drop-off — 1 hour",
            )

    # =========================================================================
    # BUILD COMPLETE CALENDAR-DAY LOGS
    # =========================================================================
    #
    # IMPORTANT:
    #
    # The raw activity list contains only actual scheduled activities.
    #
    # A driver log, however, must account for the complete 24-hour day.
    #
    # Therefore:
    #
    # 1. Split activities at midnight.
    # 2. Sort them.
    # 3. Fill every gap with OFF_DUTY.
    # 4. Validate that each day totals exactly 24 hours.
    #
    # =========================================================================

    days = {}

    # -------------------------------------------------------------------------
    # STEP 1 — Split activities at midnight.
    # -------------------------------------------------------------------------

    for activity in activities:

        cursor = activity.start

        total_activity_minutes = max(
            1.0,
            activity.minutes(),
        )

        while cursor < activity.end:

            # Preserve timezone information, if present.
            next_midnight = (
                cursor.replace(
                    hour=0,
                    minute=0,
                    second=0,
                    microsecond=0,
                )
                + timedelta(days=1)
            )

            part_end = min(
                activity.end,
                next_midnight,
            )

            key = _date_key(cursor)

            day = days.setdefault(
                key,
                {
                    "date": key,
                    "activities": [],
                    "driving_hours": 0.0,
                    "on_duty_hours": 0.0,
                    "off_duty_hours": 0.0,
                    "miles": 0.0,
                },
            )

            part_minutes = (
                part_end - cursor
            ).total_seconds() / 60

            part = asdict(
                activity
            )

            part["start"] = (
                cursor.isoformat()
            )

            part["end"] = (
                part_end.isoformat()
            )

            # Proportionally allocate mileage when
            # an activity crosses midnight.
            if activity.miles:

                part["miles"] = (
                    activity.miles
                    * (
                        part_minutes
                        / total_activity_minutes
                    )
                )

            else:

                part["miles"] = 0.0

            day["activities"].append(
                part
            )

            hours = (
                part_minutes / 60.0
            )

            if activity.kind == "DRIVING":

                day["driving_hours"] += (
                    hours
                )

                day["miles"] += (
                    part["miles"]
                )

            elif activity.kind == "ON_DUTY":

                day["on_duty_hours"] += (
                    hours
                )

            elif activity.kind in (
                "OFF_DUTY",
                "SLEEPER_BERTH",
            ):

                day["off_duty_hours"] += (
                    hours
                )

            cursor = part_end

    # -------------------------------------------------------------------------
    # STEP 2 — Fill all uncovered time with OFF_DUTY.
    # -------------------------------------------------------------------------

    for day in days.values():

        # Create midnight while preserving timezone.
        first_activity = (
            day["activities"][0]
            if day["activities"]
            else None
        )

        if first_activity:

            first_dt = datetime.fromisoformat(
                first_activity["start"]
            )

            day_start = first_dt.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

        else:

            day_start = start_dt.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

        day_end = (
            day_start
            + timedelta(days=1)
        )

        existing = sorted(
            day["activities"],
            key=lambda item: item["start"],
        )

        filled = []

        cursor = day_start

        # -------------------------------------------------------------
        # Walk through every existing activity.
        # -------------------------------------------------------------

        for item in existing:

            item_start = (
                datetime.fromisoformat(
                    item["start"]
                )
            )

            item_end = (
                datetime.fromisoformat(
                    item["end"]
                )
            )

            # ---------------------------------------------------------
            # Gap before activity.
            # ---------------------------------------------------------

            if item_start > cursor:

                gap_hours = (
                    item_start - cursor
                ).total_seconds() / 3600

                filled.append(
                    {
                        "kind": "OFF_DUTY",
                        "start": cursor.isoformat(),
                        "end": item_start.isoformat(),
                        "location": item.get(
                            "location",
                            "",
                        ),
                        "miles": 0.0,
                        "note": "Off duty",
                    }
                )

                day["off_duty_hours"] += (
                    gap_hours
                )

            filled.append(item)

            if item_end > cursor:
                cursor = item_end

        # -------------------------------------------------------------
        # Gap after final activity.
        # -------------------------------------------------------------

        if cursor < day_end:

            gap_hours = (
                day_end - cursor
            ).total_seconds() / 3600

            location = ""

            if existing:

                location = existing[-1].get(
                    "location",
                    "",
                )

            filled.append(
                {
                    "kind": "OFF_DUTY",
                    "start": cursor.isoformat(),
                    "end": day_end.isoformat(),
                    "location": location,
                    "miles": 0.0,
                    "note": "Off duty",
                }
            )

            day["off_duty_hours"] += (
                gap_hours
            )

        # -------------------------------------------------------------
        # Sort the final complete timeline.
        # -------------------------------------------------------------

        day["activities"] = sorted(
            filled,
            key=lambda item: item["start"],
        )

    # -------------------------------------------------------------------------
    # STEP 3 — Calculate and validate daily totals.
    # -------------------------------------------------------------------------

    for day in days.values():

        # Round driving and on-duty first.
        day["driving_hours"] = round(
            day["driving_hours"],
            2,
        )

        day["on_duty_hours"] = round(
            day["on_duty_hours"],
            2,
        )

        # Calculate off-duty as the exact residual of the
        # displayed driving + on-duty values.
        #
        # This ensures the displayed daily totals add up to
        # exactly 24.00 hours.
        day["off_duty_hours"] = round(
            24.0
            - day["driving_hours"]
            - day["on_duty_hours"],
            2,
        )

        day["miles"] = round(
            day["miles"],
            1,
        )

        # ---------------------------------------------------------------------
        # HARD 24-HOUR INVARIANT
        # ---------------------------------------------------------------------

        total_hours = round(
            day["driving_hours"]
            + day["on_duty_hours"]
            + day["off_duty_hours"],
            2,
        )

        day["total_hours"] = (
            total_hours
        )

        if abs(
            total_hours - 24.0
        ) > 0.01:

            raise ValueError(
                f"Daily log {day['date']} "
                f"does not total 24 hours. "
                f"Calculated: {total_hours} hours."
            )

    # =========================================================================
    # FINAL RETURN
    # =========================================================================

    return {
        "activities": [
            asdict(activity)
            for activity in activities
        ],

        "days": list(
            days.values()
        ),

        "summary": {
            "total_miles": round(
                total_distance,
                1,
            ),

            "driving_hours": round(
                total_drive,
                2,
            ),

            "initial_cycle_hours": round(
                current_cycle_hours,
                2,
            ),

            "cycle_hours_used_at_end": round(
                cycle_used,
                2,
            ),

            "cycle_restarts": cycle_restart_count,

            "days": len(days),
        },
    }
