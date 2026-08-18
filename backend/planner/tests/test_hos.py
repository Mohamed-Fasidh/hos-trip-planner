from datetime import datetime, timedelta

from django.test import SimpleTestCase

from planner.hos import build_schedule


class HOSPlannerTests(SimpleTestCase):
    """
    Assessment-focused HOS test suite.

    This suite intentionally uses unique behavioral scenarios rather than
    repetitive "variant_01", "variant_02", etc. tests.

    Coverage:
    - 11-hour driving limit per duty window
    - 14-hour duty window
    - 8-hour cumulative-driving break rule
    - 30-minute break duration/type
    - 10-hour reset duration/type
    - 34-hour restart duration/type
    - 70-hour / 8-day cycle handling
    - 1,000-mile fuel interval
    - pickup / drop-off behavior
    - route mileage and time reconciliation
    - activity chronology and integrity
    - daily log completeness
    - multi-leg routes
    - boundary and edge cases
    """

    def setUp(self):
        self.start = datetime(2026, 1, 1, 6, 0)
        self.legs = [
            {
                "start": "A",
                "end": "B",
                "distance_miles": 500,
                "duration_hours": 8,
                "is_pickup": True,
                "is_dropoff": False,
            },
            {
                "start": "B",
                "end": "C",
                "distance_miles": 600,
                "duration_hours": 9.6,
                "is_pickup": False,
                "is_dropoff": True,
            },
        ]

    def build(self, legs=None, cycle=0, start=None):
        return build_schedule(
            legs if legs is not None else self.legs,
            cycle,
            start if start is not None else self.start,
        )

    def as_datetime(self, value):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def duration_hours(self, activity):
        start = self.as_datetime(activity["start"])
        end = self.as_datetime(activity["end"])
        return (end - start).total_seconds() / 3600.0

    def duration_minutes(self, activity):
        return self.duration_hours(activity) * 60.0

    def fuel_stops(self, result):
        return [
            activity
            for activity in result["activities"]
            if activity.get("note", "").startswith("Fuel stop")
        ]

    def breaks(self, result):
        return [
            activity
            for activity in result["activities"]
            if activity.get("kind") == "OFF_DUTY"
            and "30-minute break" in activity.get("note", "")
        ]

    def resets(self, result):
        return [
            activity
            for activity in result["activities"]
            if activity.get("note") == "10-hour off-duty reset"
        ]

    def restarts(self, result):
        return [
            activity
            for activity in result["activities"]
            if activity.get("note") == "34-hour cycle restart"
        ]

    # ------------------------------------------------------------------
    # 1. BASIC INPUT / OUTPUT
    # ------------------------------------------------------------------

    def test_empty_route_returns_empty_schedule(self):
        result = self.build([])
        self.assertEqual(result["activities"], [])
        self.assertEqual(result["days"], [])
        self.assertEqual(result["summary"]["total_miles"], 0.0)
        self.assertEqual(result["summary"]["driving_hours"], 0.0)

    def test_first_activity_starts_at_requested_datetime(self):
        result = self.build()
        self.assertTrue(result["activities"])
        self.assertEqual(
            self.as_datetime(result["activities"][0]["start"]),
            self.start,
        )

    def test_custom_start_datetime_is_preserved(self):
        start = datetime(2026, 2, 14, 7, 17)
        result = self.build(self.legs, start=start)
        self.assertEqual(
            self.as_datetime(result["activities"][0]["start"]),
            start,
        )

    def test_zero_initial_cycle_is_preserved(self):
        result = self.build(self.legs, cycle=0)
        self.assertEqual(result["summary"]["initial_cycle_hours"], 0.0)

    def test_fractional_initial_cycle_is_preserved(self):
        result = self.build(self.legs, cycle=12.5)
        self.assertAlmostEqual(
            result["summary"]["initial_cycle_hours"],
            12.5,
            places=2,
        )

    def test_negative_cycle_input_is_handled_without_exceeding_limit(self):
        result = self.build(self.legs, cycle=-10)
        self.assertLessEqual(
            result["summary"]["cycle_hours_used_at_end"],
            70.0001,
        )

    def test_summary_contains_required_metrics(self):
        result = self.build()
        required = {
            "total_miles",
            "driving_hours",
            "initial_cycle_hours",
            "cycle_hours_used_at_end",
            "cycle_restarts",
            "days",
        }
        self.assertTrue(required.issubset(result["summary"].keys()))

    # ------------------------------------------------------------------
    # 2. ROUTE MILEAGE / TIME RECONCILIATION
    # ------------------------------------------------------------------

    def test_single_leg_mileage_is_preserved(self):
        legs = [{
            "start": "A",
            "end": "B",
            "distance_miles": 800,
            "duration_hours": 12.8,
            "is_pickup": False,
            "is_dropoff": True,
        }]
        result = self.build(legs)
        self.assertAlmostEqual(
            result["summary"]["total_miles"],
            800.0,
            places=1,
        )

    def test_single_leg_driving_time_is_preserved(self):
        legs = [{
            "start": "A",
            "end": "B",
            "distance_miles": 500,
            "duration_hours": 8,
            "is_pickup": False,
            "is_dropoff": True,
        }]
        result = self.build(legs)
        self.assertAlmostEqual(
            result["summary"]["driving_hours"],
            8.0,
            places=2,
        )

    def test_multiple_legs_preserve_total_mileage(self):
        result = self.build([
            {
                "start": "A",
                "end": "B",
                "distance_miles": 400,
                "duration_hours": 6.4,
                "is_pickup": True,
                "is_dropoff": False,
            },
            {
                "start": "B",
                "end": "C",
                "distance_miles": 700,
                "duration_hours": 11.2,
                "is_pickup": False,
                "is_dropoff": False,
            },
            {
                "start": "C",
                "end": "D",
                "distance_miles": 300,
                "duration_hours": 4.8,
                "is_pickup": False,
                "is_dropoff": True,
            },
        ])
        self.assertAlmostEqual(
            result["summary"]["total_miles"],
            1400.0,
            places=1,
        )

    def test_multiple_legs_preserve_total_driving_time(self):
        result = self.build([
            {
                "start": "A",
                "end": "B",
                "distance_miles": 400,
                "duration_hours": 6.4,
                "is_pickup": False,
                "is_dropoff": False,
            },
            {
                "start": "B",
                "end": "C",
                "distance_miles": 500,
                "duration_hours": 8.0,
                "is_pickup": False,
                "is_dropoff": False,
            },
        ])
        self.assertAlmostEqual(
            result["summary"]["driving_hours"],
            14.4,
            places=2,
        )

    def test_fractional_route_distance_is_preserved(self):
        legs = [{
            "start": "A",
            "end": "B",
            "distance_miles": 1234.7,
            "duration_hours": 19.7552,
            "is_pickup": False,
            "is_dropoff": True,
        }]
        result = self.build(legs)
        self.assertAlmostEqual(
            result["summary"]["total_miles"],
            1234.7,
            places=1,
        )

    def test_summary_miles_match_driving_activity_miles(self):
        result = self.build()
        driving_miles = sum(
            float(activity.get("miles", 0.0))
            for activity in result["activities"]
            if activity["kind"] == "DRIVING"
        )
        self.assertAlmostEqual(
            driving_miles,
            result["summary"]["total_miles"],
            places=1,
        )

    def test_summary_driving_hours_match_driving_activities(self):
        result = self.build()
        driving_hours = sum(
            self.duration_hours(activity)
            for activity in result["activities"]
            if activity["kind"] == "DRIVING"
        )
        self.assertAlmostEqual(
            driving_hours,
            result["summary"]["driving_hours"],
            places=2,
        )

    def test_daily_mileage_matches_daily_driving_activities(self):
        result = self.build()
        for day in result["days"]:
            driving_miles = sum(
                float(activity.get("miles", 0.0))
                for activity in day["activities"]
                if activity["kind"] == "DRIVING"
            )
            self.assertAlmostEqual(
                driving_miles,
                day["miles"],
                places=1,
            )

    def test_non_driving_activities_do_not_add_route_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        non_driving_miles = sum(
            float(activity.get("miles", 0.0))
            for activity in result["activities"]
            if activity["kind"] != "DRIVING"
        )
        self.assertEqual(non_driving_miles, 0.0)

    # ------------------------------------------------------------------
    # 3. ACTIVITY INTEGRITY / CHRONOLOGY
    # ------------------------------------------------------------------

    def test_activity_timeline_is_chronological(self):
        result = self.build()
        for previous, current in zip(
            result["activities"],
            result["activities"][1:],
        ):
            self.assertLessEqual(
                self.as_datetime(previous["end"]),
                self.as_datetime(current["start"]),
            )

    def test_activity_intervals_do_not_overlap(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for previous, current in zip(
            result["activities"],
            result["activities"][1:],
        ):
            self.assertLessEqual(
                self.as_datetime(previous["end"]),
                self.as_datetime(current["start"]),
            )

    def test_every_activity_has_positive_duration(self):
        result = self.build()
        for activity in result["activities"]:
            self.assertLess(
                self.as_datetime(activity["start"]),
                self.as_datetime(activity["end"]),
            )

    def test_all_activity_times_are_parseable(self):
        result = self.build()
        for activity in result["activities"]:
            self.assertIsInstance(
                self.as_datetime(activity["start"]),
                datetime,
            )
            self.assertIsInstance(
                self.as_datetime(activity["end"]),
                datetime,
            )

    def test_all_activities_have_required_fields(self):
        result = self.build()
        required = {
            "kind",
            "start",
            "end",
            "location",
            "miles",
            "note",
        }
        for activity in result["activities"]:
            self.assertTrue(
                required.issubset(activity.keys()),
                msg=f"Missing activity fields: {activity}",
            )

    def test_activity_locations_are_present(self):
        result = self.build()
        for activity in result["activities"]:
            self.assertIn("location", activity)
            self.assertIsNotNone(activity["location"])

    def test_activity_miles_are_never_negative(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1800,
            "duration_hours": 28.8,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for activity in result["activities"]:
            self.assertGreaterEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_activity_duration_is_never_negative(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2200,
            "duration_hours": 35.2,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for activity in result["activities"]:
            self.assertGreater(
                self.duration_minutes(activity),
                0.0,
            )

    # ------------------------------------------------------------------
    # 4. 11-HOUR / 14-HOUR / 8-HOUR HOS RULES
    # ------------------------------------------------------------------

    def test_each_duty_window_stays_within_11_driving_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])

        driving_in_window = 0.0

        for activity in result["activities"]:
            if activity["kind"] == "DRIVING":
                driving_in_window += self.duration_hours(activity)
                self.assertLessEqual(
                    driving_in_window,
                    11.0001,
                    msg=(
                        "Driving exceeded 11 hours within one "
                        f"duty window: {driving_in_window:.3f}h"
                    ),
                )
            elif activity.get("note") in {
                "10-hour off-duty reset",
                "34-hour cycle restart",
            }:
                driving_in_window = 0.0

    def test_each_duty_window_stays_within_14_elapsed_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])

        window_start = self.as_datetime(
            result["activities"][0]["start"]
        )

        for activity in result["activities"]:
            activity_start = self.as_datetime(activity["start"])
            activity_end = self.as_datetime(activity["end"])

            if activity.get("note") in {
                "10-hour off-duty reset",
                "34-hour cycle restart",
            }:
                self.assertLessEqual(
                    (activity_start - window_start).total_seconds(),
                    14 * 3600 + 1,
                )
                window_start = activity_end
                continue

            elapsed = (
                activity_end - window_start
            ).total_seconds() / 3600.0

            self.assertLessEqual(
                elapsed,
                14.0001,
                msg=(
                    "14-hour duty window exceeded: "
                    f"{elapsed:.3f}h at {activity}"
                ),
            )

    def test_30_minute_break_is_added_when_driving_reaches_8_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1000,
            "duration_hours": 16,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.breaks(result)), 1)

    def test_30_minute_break_has_exact_duration(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.breaks(result):
            self.assertAlmostEqual(
                self.duration_minutes(activity),
                30.0,
                places=2,
            )

    def test_30_minute_breaks_are_off_duty(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.breaks(result):
            self.assertEqual(activity["kind"], "OFF_DUTY")

    def test_30_minute_break_does_not_add_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.breaks(result):
            self.assertEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_cumulative_driving_resets_after_30_minute_break(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1000,
            "duration_hours": 16,
            "is_pickup": False,
            "is_dropoff": True,
        }])

        breaks = self.breaks(result)
        self.assertGreaterEqual(
            len(breaks),
            1,
            "Expected a 30-minute break after 8 cumulative driving hours.",
        )

        activities = result["activities"]

        # Validate each continuous cumulative-driving period separately.
        # A 10-hour reset or 34-hour restart also begins a fresh period.
        cumulative = 0.0
        saw_break = False

        for activity in activities:
            if activity["kind"] == "DRIVING":
                cumulative += self.duration_hours(activity)

                self.assertLessEqual(
                    cumulative,
                    8.0001,
                    msg=(
                        "Driving exceeded 8 cumulative hours without "
                        f"a qualifying break/reset: {cumulative:.3f}h"
                    ),
                )

            elif (
                activity["kind"] == "OFF_DUTY"
                and "30-minute break" in activity.get("note", "")
            ):
                self.assertAlmostEqual(
                    self.duration_minutes(activity),
                    30.0,
                    places=2,
                )
                saw_break = True
                cumulative = 0.0

            elif activity.get("note") in {
                "10-hour off-duty reset",
                "34-hour cycle restart",
            }:
                cumulative = 0.0

        self.assertTrue(
            saw_break,
            "Expected a mandatory 30-minute break on the 1,000-mile route.",
        )

        # Confirm that driving continues after the qualifying break.
        break_end = self.as_datetime(breaks[0]["end"])
        post_break_driving = [
            activity
            for activity in activities
            if activity["kind"] == "DRIVING"
            and self.as_datetime(activity["start"]) >= break_end
        ]

        self.assertGreater(
            len(post_break_driving),
            0,
            "Expected driving to continue after the 30-minute break.",
        )

    # ------------------------------------------------------------------
    # 5. 10-HOUR RESET
    # ------------------------------------------------------------------

    def test_long_route_requires_10_hour_reset(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.resets(result)), 1)

    def test_10_hour_reset_has_exact_duration(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.resets(result):
            self.assertAlmostEqual(
                self.duration_hours(activity),
                10.0,
                places=2,
            )

    def test_10_hour_reset_is_off_duty(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.resets(result):
            self.assertEqual(activity["kind"], "OFF_DUTY")

    def test_10_hour_reset_does_not_add_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1600,
            "duration_hours": 25.6,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.resets(result):
            self.assertEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_multiple_long_route_resets_are_created(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3500,
            "duration_hours": 56,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.resets(result)), 2)

    # ------------------------------------------------------------------
    # 6. 70-HOUR / 34-HOUR CYCLE
    # ------------------------------------------------------------------

    def test_cycle_usage_does_not_exceed_70_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertLessEqual(
            result["summary"]["cycle_hours_used_at_end"],
            70.0001,
        )

    def test_cycle_at_70_triggers_restart(self):
        result = self.build(self.legs, cycle=70)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_cycle_near_70_triggers_restart_when_work_would_exceed_limit(self):
        result = self.build(self.legs, cycle=69.5)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_cycle_above_70_is_recovered_with_restart(self):
        result = self.build(self.legs, cycle=75)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_34_hour_restart_has_exact_duration(self):
        result = self.build(self.legs, cycle=70)
        restarts = self.restarts(result)
        self.assertGreaterEqual(len(restarts), 1)
        for activity in restarts:
            self.assertAlmostEqual(
                self.duration_hours(activity),
                34.0,
                places=2,
            )

    def test_34_hour_restart_is_off_duty(self):
        result = self.build(self.legs, cycle=70)
        for activity in self.restarts(result):
            self.assertEqual(activity["kind"], "OFF_DUTY")

    def test_34_hour_restart_does_not_add_mileage(self):
        result = self.build(self.legs, cycle=70)
        for activity in self.restarts(result):
            self.assertEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_work_continues_after_cycle_restart(self):
        result = self.build(
            [{
                "start": "A",
                "end": "B",
                "distance_miles": 100,
                "duration_hours": 1.6,
                "is_pickup": False,
                "is_dropoff": True,
            }],
            cycle=70,
        )

        restarts = self.restarts(result)
        self.assertGreaterEqual(len(restarts), 1)

        restart_end = self.as_datetime(restarts[0]["end"])
        post_restart_work = [
            activity
            for activity in result["activities"]
            if self.as_datetime(activity["start"]) >= restart_end
            and activity["kind"] in {"DRIVING", "ON_DUTY"}
        ]
        self.assertGreaterEqual(len(post_restart_work), 1)

    # ------------------------------------------------------------------
    # 7. FUEL INTERVAL
    # ------------------------------------------------------------------

    def test_999_mile_route_needs_no_fuel_stop(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 999,
            "duration_hours": 15.984,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_exact_1000_mile_route_needs_no_post_arrival_fuel_stop(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1000,
            "duration_hours": 16,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_1001_mile_route_requires_fuel_stop(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1001,
            "duration_hours": 16.016,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_2000_mile_route_requires_intermediate_fuel_stop(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2000,
            "duration_hours": 32,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_2500_mile_route_requires_multiple_fuel_stops(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.fuel_stops(result)), 2)

    def test_6000_mile_route_requires_multiple_fuel_stops(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 6000,
            "duration_hours": 96,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.fuel_stops(result)), 5)

    def test_each_fuel_interval_stays_within_1000_miles(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3200,
            "duration_hours": 52,
            "is_pickup": False,
            "is_dropoff": True,
        }])

        miles_since_fuel = 0.0

        for activity in result["activities"]:
            if activity["kind"] == "DRIVING":
                miles_since_fuel += float(
                    activity.get("miles", 0.0)
                )

            if activity.get("note", "").startswith("Fuel stop"):
                self.assertLessEqual(
                    miles_since_fuel,
                    1000.0001,
                    msg=(
                        "Fuel interval exceeded 1,000 miles: "
                        f"{miles_since_fuel:.3f}"
                    ),
                )
                miles_since_fuel = 0.0

        self.assertLessEqual(
            miles_since_fuel,
            1000.0001,
            msg=(
                "Final fuel interval exceeded 1,000 miles: "
                f"{miles_since_fuel:.3f}"
            ),
        )

    def test_fuel_stop_is_on_duty(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1200,
            "duration_hours": 19.2,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.fuel_stops(result):
            self.assertEqual(activity["kind"], "ON_DUTY")

    def test_fuel_stop_duration_is_30_minutes(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1200,
            "duration_hours": 19.2,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.fuel_stops(result):
            self.assertAlmostEqual(
                self.duration_minutes(activity),
                30.0,
                places=2,
            )

    def test_fuel_stop_does_not_add_route_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2200,
            "duration_hours": 35.2,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.fuel_stops(result):
            self.assertEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_fuel_stop_note_is_identifiable(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1500,
            "duration_hours": 24,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in self.fuel_stops(result):
            self.assertTrue(
                activity["note"].startswith("Fuel stop")
            )

    # ------------------------------------------------------------------
    # 8. PICKUP / DROP-OFF
    # ------------------------------------------------------------------

    def test_pickup_and_dropoff_are_created_when_requested(self):
        result = self.build()
        notes = [activity["note"] for activity in result["activities"]]
        self.assertIn("Pickup — 1 hour", notes)
        self.assertIn("Drop-off — 1 hour", notes)

    def test_pickup_and_dropoff_are_exactly_one_hour(self):
        result = self.build()
        services = [
            activity
            for activity in result["activities"]
            if activity.get("note") in {
                "Pickup — 1 hour",
                "Drop-off — 1 hour",
            }
        ]
        self.assertEqual(len(services), 2)
        for activity in services:
            self.assertAlmostEqual(
                self.duration_hours(activity),
                1.0,
                places=2,
            )

    def test_pickup_and_dropoff_are_on_duty(self):
        result = self.build()
        services = [
            activity
            for activity in result["activities"]
            if activity.get("note") in {
                "Pickup — 1 hour",
                "Drop-off — 1 hour",
            }
        ]
        for activity in services:
            self.assertEqual(activity["kind"], "ON_DUTY")

    def test_pickup_only_route_has_no_dropoff(self):
        result = self.build([{
            "start": "A",
            "end": "A",
            "distance_miles": 0,
            "duration_hours": 0,
            "is_pickup": True,
            "is_dropoff": False,
        }])
        notes = [activity["note"] for activity in result["activities"]]
        self.assertIn("Pickup — 1 hour", notes)
        self.assertNotIn("Drop-off — 1 hour", notes)

    def test_dropoff_only_route_has_no_pickup(self):
        result = self.build([{
            "start": "A",
            "end": "A",
            "distance_miles": 0,
            "duration_hours": 0,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        notes = [activity["note"] for activity in result["activities"]]
        self.assertNotIn("Pickup — 1 hour", notes)
        self.assertIn("Drop-off — 1 hour", notes)

    def test_neither_service_flag_creates_no_service_activity(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 500,
            "duration_hours": 8,
            "is_pickup": False,
            "is_dropoff": False,
        }])
        service_notes = {
            "Pickup — 1 hour",
            "Drop-off — 1 hour",
        }
        self.assertFalse(
            any(
                activity["note"] in service_notes
                for activity in result["activities"]
            )
        )

    # ------------------------------------------------------------------
    # 9. DAILY LOGS
    # ------------------------------------------------------------------

    def test_each_daily_log_is_exactly_24_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            self.assertAlmostEqual(
                day["total_hours"],
                24.0,
                places=2,
            )

    def test_daily_status_hours_sum_to_24(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            total = (
                day["driving_hours"]
                + day["on_duty_hours"]
                + day["off_duty_hours"]
            )
            self.assertAlmostEqual(total, 24.0, places=2)

    def test_daily_status_hours_are_nonnegative(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2200,
            "duration_hours": 35.2,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            self.assertGreaterEqual(day["driving_hours"], 0.0)
            self.assertGreaterEqual(day["on_duty_hours"], 0.0)
            self.assertGreaterEqual(day["off_duty_hours"], 0.0)
            self.assertGreaterEqual(day["miles"], 0.0)

    def test_daily_activities_are_chronological(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1800,
            "duration_hours": 28.8,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            for previous, current in zip(
                day["activities"],
                day["activities"][1:],
            ):
                self.assertLessEqual(
                    self.as_datetime(previous["end"]),
                    self.as_datetime(current["start"]),
                )

    def test_daily_dates_are_unique(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 2500,
            "duration_hours": 40,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        dates = [day["date"] for day in result["days"]]
        self.assertEqual(len(dates), len(set(dates)))

    def test_summary_day_count_matches_days_array(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1800,
            "duration_hours": 28.8,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertEqual(
            result["summary"]["days"],
            len(result["days"]),
        )

    def test_long_route_produces_multiple_daily_logs(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 4000,
            "duration_hours": 64,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreater(len(result["days"]), 1)

    # ------------------------------------------------------------------
    # 10. EDGE CASES / ROBUSTNESS
    # ------------------------------------------------------------------

    def test_zero_distance_pickup_and_dropoff_still_create_services(self):
        result = self.build([{
            "start": "A",
            "end": "A",
            "distance_miles": 0,
            "duration_hours": 0,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        notes = [activity["note"] for activity in result["activities"]]
        self.assertIn("Pickup — 1 hour", notes)
        self.assertIn("Drop-off — 1 hour", notes)

    def test_one_mile_route_is_supported(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1,
            "duration_hours": 1 / 60,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertAlmostEqual(
            result["summary"]["total_miles"],
            1.0,
            places=1,
        )

    def test_zero_mileage_with_nonzero_duration_is_nonnegative(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 0,
            "duration_hours": 5,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(
            result["summary"]["total_miles"],
            0.0,
        )
        for activity in result["activities"]:
            self.assertGreaterEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )

    def test_very_long_route_preserves_total_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 6000,
            "duration_hours": 96,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertAlmostEqual(
            result["summary"]["total_miles"],
            6000.0,
            places=1,
        )

    def test_very_long_route_has_multiple_resets(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 6000,
            "duration_hours": 96,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.resets(result)), 2)

    def test_very_long_route_has_multiple_fuel_stops(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 6000,
            "duration_hours": 96,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertGreaterEqual(len(self.fuel_stops(result)), 5)

    def test_activity_locations_exist_for_long_route(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for activity in result["activities"]:
            self.assertIn("location", activity)

    # ------------------------------------------------------------------
    # 11. RECONCILIATION / FINAL INVARIANTS
    # ------------------------------------------------------------------

    def test_final_cycle_usage_is_within_70_hours(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 5000,
            "duration_hours": 80,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        self.assertLessEqual(
            result["summary"]["cycle_hours_used_at_end"],
            70.0001,
        )

    def test_cycle_restart_count_is_nonnegative_integer(self):
        result = self.build(self.legs, cycle=70)
        self.assertIsInstance(
            result["summary"]["cycle_restarts"],
            int,
        )
        self.assertGreaterEqual(
            result["summary"]["cycle_restarts"],
            0,
        )

    def test_each_day_contains_activities(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1800,
            "duration_hours": 28.8,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            self.assertGreater(
                len(day["activities"]),
                0,
            )

    def test_daily_driving_miles_are_nonnegative(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3000,
            "duration_hours": 48,
            "is_pickup": False,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            self.assertGreaterEqual(day["miles"], 0.0)

    def test_services_are_ordered_pickup_before_dropoff(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 100,
            "duration_hours": 1.6,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        services = [
            activity
            for activity in result["activities"]
            if activity["note"] in {
                "Pickup — 1 hour",
                "Drop-off — 1 hour",
            }
        ]
        self.assertEqual(len(services), 2)
        self.assertLessEqual(
            self.as_datetime(services[0]["end"]),
            self.as_datetime(services[1]["start"]),
        )

    def test_route_segment_with_services_preserves_service_order(self):
        result = self.build([
            {
                "start": "A",
                "end": "B",
                "distance_miles": 500,
                "duration_hours": 8,
                "is_pickup": True,
                "is_dropoff": False,
            },
            {
                "start": "B",
                "end": "C",
                "distance_miles": 500,
                "duration_hours": 8,
                "is_pickup": False,
                "is_dropoff": True,
            },
        ])
        notes = [activity["note"] for activity in result["activities"]]
        pickup_index = notes.index("Pickup — 1 hour")
        dropoff_index = notes.index("Drop-off — 1 hour")
        self.assertLess(pickup_index, dropoff_index)

    def test_daily_logs_cover_complete_calendar_days(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 3500,
            "duration_hours": 56,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for day in result["days"]:
            total = (
                day["driving_hours"]
                + day["on_duty_hours"]
                + day["off_duty_hours"]
            )
            self.assertAlmostEqual(total, 24.0, places=2)

    def test_no_activity_has_negative_route_mileage(self):
        result = self.build([{
            "start": "A",
            "end": "B",
            "distance_miles": 1500,
            "duration_hours": 24,
            "is_pickup": True,
            "is_dropoff": True,
        }])
        for activity in result["activities"]:
            self.assertGreaterEqual(
                float(activity.get("miles", 0.0)),
                0.0,
            )


if __name__ == "__main__":
    import unittest

    unittest.main()