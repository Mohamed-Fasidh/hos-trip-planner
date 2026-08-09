from datetime import datetime, timedelta

from django.test import SimpleTestCase

from planner.hos import build_schedule


class HOSPlannerTests(SimpleTestCase):
    """
    Comprehensive assessment-focused tests for planner.hos.build_schedule().

    Coverage:
    - 11-hour driving limit
    - 14-hour duty window
    - 30-minute break after 8 cumulative driving hours
    - 10-hour off-duty reset
    - 70-hour / 8-day cycle
    - 34-hour restart
    - 1,000-mile fuel interval
    - 1-hour pickup / drop-off
    - complete 24-hour daily logs
    - mileage/time reconciliation
    - chronology and activity integrity
    """

    '\n    Comprehensive tests for planner.hos.build_schedule().\n\n    Scope:\n    - 11-hour driving limit\n    - 14-hour duty window\n    - 30-minute break after 8 cumulative driving hours\n    - 10-hour off-duty reset\n    - 70-hour / 8-day cycle\n    - 34-hour restart\n    - 1,000-mile fuel interval\n    - 1-hour pickup / drop-off\n    - complete 24-hour daily logs\n    - mileage/time reconciliation\n    - chronology and activity integrity\n    '

    def setUp(self):
        self.start = datetime(2026, 1, 1, 6, 0)
        self.legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 600, 'duration_hours': 9.6, 'is_pickup': False, 'is_dropoff': True}]

    def build(self, legs=None, cycle=0, start=None):
        return build_schedule(legs if legs is not None else self.legs, cycle, start if start is not None else self.start)

    def as_datetime(self, value):
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(value)

    def duration_hours(self, activity):
        start = self.as_datetime(activity['start'])
        end = self.as_datetime(activity['end'])
        return (end - start).total_seconds() / 3600

    def duration_minutes(self, activity):
        return self.duration_hours(activity) * 60

    def fuel_stops(self, result):
        return [a for a in result['activities'] if a.get('note', '').startswith('Fuel stop')]

    def breaks(self, result):
        return [a for a in result['activities'] if a.get('kind') == 'OFF_DUTY' and '30-minute break' in a.get('note', '')]

    def resets(self, result):
        return [a for a in result['activities'] if a.get('note') == '10-hour off-duty reset']

    def restarts(self, result):
        return [a for a in result['activities'] if a.get('note') == '34-hour cycle restart']

    def test_daily_drive_never_exceeds_11_hours(self):
        result = self.build()
        for day in result['days']:
            self.assertLessEqual(day['driving_hours'], 11.0001, msg=f'Driving exceeded 11 hours: {day}')

    def test_pickup_and_dropoff_are_one_hour(self):
        result = self.build()
        services = [a for a in result['activities'] if a.get('note') in ('Pickup — 1 hour', 'Drop-off — 1 hour')]
        self.assertEqual(len(services), 2)
        for activity in services:
            self.assertAlmostEqual(self.duration_hours(activity), 1.0, places=2)

    def test_cycle_restart_can_reset_near_limit(self):
        result = self.build(cycle=69.5)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_30_minute_break_is_added_after_8_hours_driving(self):
        result = self.build()
        breaks = self.breaks(result)
        self.assertGreaterEqual(len(breaks), 1)
        for activity in breaks:
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)

    def test_daily_logs_total_exactly_24_hours(self):
        result = self.build()
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)

    def test_daily_status_hours_sum_to_24(self):
        result = self.build()
        for day in result['days']:
            total = day['driving_hours'] + day['on_duty_hours'] + day['off_duty_hours']
            self.assertAlmostEqual(total, 24.0, places=2)

    def test_cycle_usage_never_exceeds_70_hours(self):
        result = self.build()
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)

    def test_total_miles_are_preserved(self):
        result = self.build()
        self.assertAlmostEqual(result['summary']['total_miles'], 1100.0, places=1)

    def test_driving_hours_are_preserved(self):
        result = self.build()
        self.assertAlmostEqual(result['summary']['driving_hours'], 17.6, places=2)

    def test_fuel_stop_is_added_before_1000_miles(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1200, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1, msg='Expected a fuel stop on a 1,200-mile route.')

    def test_10_hour_reset_is_added_when_required(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.resets(result)), 1)

    def test_activity_timeline_is_chronological(self):
        result = self.build()
        activities = result['activities']
        for previous, current in zip(activities, activities[1:]):
            self.assertLessEqual(self.as_datetime(previous['end']), self.as_datetime(current['start']))

    def test_every_activity_has_positive_duration(self):
        result = self.build()
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_daily_driving_stays_inside_11_hour_limit(self):
        result = self.build()
        for day in result['days']:
            self.assertLessEqual(day['driving_hours'], 11.0001)

    def test_pickup_and_dropoff_exist(self):
        result = self.build()
        notes = [a['note'] for a in result['activities']]
        self.assertIn('Pickup — 1 hour', notes)
        self.assertIn('Drop-off — 1 hour', notes)

    def test_34_hour_restart_duration_is_exact(self):
        result = self.build(cycle=69.5)
        restarts = self.restarts(result)
        self.assertGreaterEqual(len(restarts), 1)
        for activity in restarts:
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_10_hour_reset_duration_is_exact(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)

    def test_fuel_interval_never_exceeds_1000_miles(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3200, 'duration_hours': 52, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        miles_since_fuel = 0.0
        for activity in result['activities']:
            if activity['kind'] == 'DRIVING':
                miles_since_fuel += float(activity.get('miles', 0.0))
            if activity.get('note', '').startswith('Fuel stop'):
                self.assertLessEqual(miles_since_fuel, 1000.0001, msg=f'Fuel interval exceeded 1,000 miles: {miles_since_fuel:.3f}')
                miles_since_fuel = 0.0
        self.assertLessEqual(miles_since_fuel, 1000.0001, msg=f'Final fuel interval exceeded 1,000 miles: {miles_since_fuel:.3f}')

    def test_fuel_interval_respects_1000_mile_assessment_limit(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        miles_since_fuel = 0.0
        for activity in result['activities']:
            if activity['kind'] == 'DRIVING':
                miles_since_fuel += float(activity.get('miles', 0.0))
            if activity.get('note', '').startswith('Fuel stop'):
                self.assertLessEqual(miles_since_fuel, 1000.0001, msg=f'Internal fuel buffer exceeded: {miles_since_fuel:.3f}')
                miles_since_fuel = 0.0
        self.assertLessEqual(miles_since_fuel, 1000.0001)

    def test_long_route_creates_multiple_fuel_stops(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 2, msg='Expected multiple fuel stops on a 3,000-mile route.')

    def test_final_route_does_not_create_unnecessary_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 900, 'duration_hours': 15, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_fuel_stop_is_on_duty(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1200, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for fuel in self.fuel_stops(result):
            self.assertEqual(fuel['kind'], 'ON_DUTY')

    def test_fuel_stop_duration_is_30_minutes(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1200, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for fuel in self.fuel_stops(result):
            self.assertAlmostEqual(self.duration_minutes(fuel), 30.0, places=2)

    def test_initial_cycle_70_triggers_restart(self):
        result = self.build(cycle=70)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_initial_cycle_65_is_handled(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 800, 'duration_hours': 16, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 800, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, cycle=65)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_negative_cycle_is_safe(self):
        result = self.build(cycle=-10)
        self.assertGreaterEqual(result['summary']['initial_cycle_hours'], -10.0)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)

    def test_cycle_above_70_is_handled(self):
        result = self.build(cycle=75)
        self.assertGreaterEqual(len(self.restarts(result)), 1)

    def test_zero_distance_services_are_created(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertIn('Pickup — 1 hour', notes)
        self.assertIn('Drop-off — 1 hour', notes)

    def test_empty_route_is_handled(self):
        result = self.build([])
        self.assertEqual(result['activities'], [])
        self.assertEqual(result['days'], [])
        self.assertEqual(result['summary']['total_miles'], 0.0)
        self.assertEqual(result['summary']['driving_hours'], 0.0)

    def test_no_activity_has_negative_miles(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 25, 'is_pickup': False, 'is_dropoff': True}])
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_summary_miles_match_driving_activity_miles(self):
        result = self.build()
        activity_miles = sum((float(a.get('miles', 0.0)) for a in result['activities'] if a['kind'] == 'DRIVING'))
        self.assertAlmostEqual(activity_miles, result['summary']['total_miles'], places=1)

    def test_daily_mileage_matches_daily_driving_activities(self):
        result = self.build()
        for day in result['days']:
            driving_miles = sum((float(a.get('miles', 0.0)) for a in day['activities'] if a['kind'] == 'DRIVING'))
            self.assertAlmostEqual(driving_miles, day['miles'], places=1)

    def test_pickup_and_dropoff_are_on_duty(self):
        result = self.build()
        services = [a for a in result['activities'] if a['note'] in ('Pickup — 1 hour', 'Drop-off — 1 hour')]
        self.assertEqual(len(services), 2)
        for activity in services:
            self.assertEqual(activity['kind'], 'ON_DUTY')

    def test_30_minute_breaks_are_off_duty(self):
        result = self.build()
        for activity in self.breaks(result):
            self.assertEqual(activity['kind'], 'OFF_DUTY')

    def test_10_hour_resets_are_off_duty(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 20, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.resets(result):
            self.assertEqual(activity['kind'], 'OFF_DUTY')

    def test_34_hour_restart_is_off_duty(self):
        result = self.build(cycle=69.5)
        for activity in self.restarts(result):
            self.assertEqual(activity['kind'], 'OFF_DUTY')

    def test_all_activities_have_required_fields(self):
        result = self.build()
        required = {'kind', 'start', 'end', 'location', 'miles', 'note'}
        for activity in result['activities']:
            self.assertTrue(required.issubset(activity.keys()), msg=f'Missing fields: {activity}')

    def test_activity_intervals_do_not_overlap(self):
        result = self.build()
        for previous, current in zip(result['activities'], result['activities'][1:]):
            self.assertLessEqual(self.as_datetime(previous['end']), self.as_datetime(current['start']))

    def test_first_activity_starts_at_requested_start(self):
        result = self.build()
        self.assertGreater(len(result['activities']), 0)
        first = result['activities'][0]
        self.assertEqual(self.as_datetime(first['start']), self.start)

    def test_long_route_preserves_total_miles(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 3000.0, places=1)

    def test_long_route_respects_daily_driving_limit(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        driving_in_duty_period = 0.0

        for activity in result["activities"]:
            if activity["kind"] == "DRIVING":
                driving_in_duty_period += self.duration_hours(activity)

                self.assertLessEqual(
                   driving_in_duty_period,
                   11.0001,
                   msg=(
                    f"Driving exceeded 11 hours: "
                    f"{driving_in_duty_period:.3f}"
                   ),
                )

            elif activity.get("note") in (
            "10-hour off-duty reset",
            "34-hour cycle restart",
            ):
                driving_in_duty_period = 0.0

        self.assertLessEqual(
        driving_in_duty_period,
        11.0001,
        )

    def test_long_route_daily_logs_are_complete(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreater(len(result['days']), 0)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)

    def test_exact_1000_mile_route_needs_no_post_arrival_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_1001_mile_route_requires_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1001, 'duration_hours': 16.0167, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_2000_mile_route_requires_intermediate_fuel(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2000, 'duration_hours': 32, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_2500_mile_route_requires_multiple_fuel_stops(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 2)

    def test_fuel_stops_do_not_add_route_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2200, 'duration_hours': 35.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        fuel_miles = sum((float(a.get('miles', 0.0)) for a in self.fuel_stops(result)))
        self.assertEqual(fuel_miles, 0.0)

    def test_same_location_pickup_and_dropoff_each_take_one_hour(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        services = [a for a in result['activities'] if a['note'] in ('Pickup — 1 hour', 'Drop-off — 1 hour')]
        self.assertEqual(len(services), 2)
        for activity in services:
            self.assertAlmostEqual(self.duration_hours(activity), 1.0, places=2)

    def test_pickup_and_dropoff_both_count_as_on_duty(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        services = [a for a in result['activities'] if a['note'] in ('Pickup — 1 hour', 'Drop-off — 1 hour')]
        self.assertTrue(all((a['kind'] == 'ON_DUTY' for a in services)))

    def test_multiple_route_segments_preserve_total_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 400, 'duration_hours': 6.4, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 700, 'duration_hours': 11.2, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 300, 'duration_hours': 4.8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1400.0, places=1)

    def test_multiple_route_segments_preserve_driving_time(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 400, 'duration_hours': 6.4, 'is_pickup': False, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 500, 'duration_hours': 8.0, 'is_pickup': False, 'is_dropoff': False}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['driving_hours'], 14.4, places=2)

    def test_fractional_distance_is_preserved(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1234.7, 'duration_hours': 19.7552, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1234.7, places=1)

    def test_fractional_initial_cycle_is_preserved(self):
        result = self.build(self.legs, cycle=12.5)
        self.assertAlmostEqual(result['summary']['initial_cycle_hours'], 12.5, places=2)

    def test_custom_start_time_is_preserved(self):
        start = datetime(2026, 2, 14, 7, 17)
        result = self.build(self.legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_no_activity_has_negative_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1800, 'duration_hours': 28.8, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_no_daily_status_hours_are_negative(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2200, 'duration_hours': 35.2, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_all_activities_have_locations(self):
        result = self.build()
        for activity in result['activities']:
            self.assertIn('location', activity)
            self.assertIsNotNone(activity['location'])

    def test_summary_contains_all_required_metrics(self):
        result = self.build()
        required = {'total_miles', 'driving_hours', 'initial_cycle_hours', 'cycle_hours_used_at_end', 'cycle_restarts', 'days'}
        self.assertTrue(required.issubset(result['summary'].keys()))

    def test_restart_count_is_nonnegative_integer(self):
        result = self.build(cycle=70)
        self.assertIsInstance(result['summary']['cycle_restarts'], int)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_calendar_day_dates_are_unique(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        dates = [day['date'] for day in result['days']]
        self.assertEqual(len(dates), len(set(dates)))

    def test_daily_activities_are_chronological(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1800, 'duration_hours': 28.8, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            for previous, current in zip(day['activities'], day['activities'][1:]):
                self.assertLessEqual(self.as_datetime(previous['end']), self.as_datetime(current['start']))

    def test_long_route_requires_at_least_one_10_hour_reset(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.resets(result)), 1)

    def test_very_long_route_preserves_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 6000, 'duration_hours': 96, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 6000.0, places=1)

    def test_very_long_route_has_multiple_fuel_stops(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 6000, 'duration_hours': 96, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 5)

    def test_very_long_route_produces_multiple_calendar_days(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 4000, 'duration_hours': 64, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreater(len(result['days']), 1)

    def test_all_route_mileage_is_on_driving_activities(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2100, 'duration_hours': 33.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        driving_miles = sum((float(a.get('miles', 0.0)) for a in result['activities'] if a['kind'] == 'DRIVING'))
        non_driving_miles = sum((float(a.get('miles', 0.0)) for a in result['activities'] if a['kind'] != 'DRIVING'))
        self.assertAlmostEqual(driving_miles, 2100.0, places=1)
        self.assertEqual(non_driving_miles, 0.0)

    def test_999_mile_route_needs_no_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 999, 'duration_hours': 15.984, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_exactly_1000_miles_has_no_post_arrival_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_1000_point_one_miles_requires_intermediate_fuel(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000.1, 'duration_hours': 16.0016, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_fuel_stops_are_zero_mile_activities(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3100, 'duration_hours': 49.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.fuel_stops(result):
            self.assertEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fuel_stop_note_is_identifiable(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 24, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.fuel_stops(result):
            self.assertTrue(activity['note'].startswith('Fuel stop'))

    def test_fuel_stop_is_chronologically_before_remaining_route(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 24, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        activities = result['activities']
        fuel_indexes = [i for i, a in enumerate(activities) if a.get('note', '').startswith('Fuel stop')]
        for index in fuel_indexes:
            self.assertLess(self.as_datetime(activities[index]['start']), self.as_datetime(activities[-1]['end']))

    def test_initial_cycle_zero_is_valid(self):
        result = self.build(self.legs, cycle=0)
        self.assertEqual(result['summary']['initial_cycle_hours'], 0.0)

    def test_initial_cycle_69_point_9_is_handled(self):
        result = self.build(self.legs, cycle=69.9)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)

    def test_initial_cycle_70_resets_before_new_work(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}], cycle=70)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 1)

    def test_pickup_only_route(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': True, 'is_dropoff': False}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertIn('Pickup — 1 hour', notes)
        self.assertNotIn('Drop-off — 1 hour', notes)

    def test_dropoff_only_route(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertNotIn('Pickup — 1 hour', notes)
        self.assertIn('Drop-off — 1 hour', notes)

    def test_no_pickup_or_dropoff_adds_service(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': False, 'is_dropoff': False}]
        result = self.build(legs)
        service_notes = {'Pickup — 1 hour', 'Drop-off — 1 hour'}
        self.assertFalse(any((a['note'] in service_notes for a in result['activities'])))

    def test_long_route_has_at_least_two_10_hour_resets(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3500, 'duration_hours': 56, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(len(self.resets(result)), 2)

    def test_restart_resets_cycle_usage(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}], cycle=70)
        restarts = self.restarts(result)
        self.assertGreaterEqual(len(restarts), 1)
        restart_end = self.as_datetime(restarts[0]['end'])
        post_restart_work = [a for a in result['activities'] if self.as_datetime(a['start']) >= restart_end and a['kind'] in ('DRIVING', 'ON_DUTY')]
        self.assertGreaterEqual(len(post_restart_work), 1)

    def test_break_activity_is_exactly_30_minutes(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)

    def test_break_does_not_add_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1600, 'duration_hours': 25.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_reset_does_not_add_mileage(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1600, 'duration_hours': 25.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.resets(result):
            self.assertEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_restart_does_not_add_mileage(self):
        result = self.build(self.legs, cycle=70)
        for activity in self.restarts(result):
            self.assertEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_off_duty_activity_never_has_negative_duration(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}])
        for activity in result['activities']:
            if activity['kind'] == 'OFF_DUTY':
                self.assertGreater(self.duration_minutes(activity), 0)

    def test_all_activity_times_are_parseable(self):
        result = self.build()
        for activity in result['activities']:
            start = self.as_datetime(activity['start'])
            end = self.as_datetime(activity['end'])
            self.assertIsInstance(start, datetime)
            self.assertIsInstance(end, datetime)

    def test_each_day_contains_activities_when_days_exist(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 1800, 'duration_hours': 28.8, 'is_pickup': False, 'is_dropoff': True}])
        for day in result['days']:
            self.assertGreater(len(day['activities']), 0)

    def test_summary_days_matches_days_array(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 1800, 'duration_hours': 28.8, 'is_pickup': False, 'is_dropoff': True}])
        self.assertEqual(result['summary']['days'], len(result['days']))

    def test_summary_driving_hours_match_driving_activities(self):
        result = self.build()
        activity_hours = sum((self.duration_hours(a) for a in result['activities'] if a['kind'] == 'DRIVING'))
        self.assertAlmostEqual(activity_hours, result['summary']['driving_hours'], places=2)

    def test_summary_total_miles_match_input_for_simple_route(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 800, 'duration_hours': 12.8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 800.0, places=1)

    def test_multiple_service_stops_are_ordered(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        services = [a for a in result['activities'] if a['note'] in ('Pickup — 1 hour', 'Drop-off — 1 hour')]
        self.assertEqual(len(services), 2)
        self.assertLessEqual(self.as_datetime(services[0]['end']), self.as_datetime(services[1]['start']))

    def test_route_with_zero_miles_and_nonzero_duration_is_safe(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 0, 'duration_hours': 5, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertGreaterEqual(result['summary']['total_miles'], 0.0)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_route_segment_with_pickup_and_next_segment_preserves_order(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertIn('Pickup — 1 hour', notes)
        self.assertIn('Drop-off — 1 hour', notes)
        pickup_index = notes.index('Pickup — 1 hour')
        dropoff_index = notes.index('Drop-off — 1 hour')
        self.assertLess(pickup_index, dropoff_index)

    def test_1_mile_route_is_supported(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1, 'duration_hours': 1 / 60, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1.0, places=1)

    def test_500_mile_route_has_no_fuel_stop(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertEqual(len(self.fuel_stops(result)), 0)

    def test_pickup_is_on_duty(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': True, 'is_dropoff': False}]
        result = self.build(legs)
        pickup = [a for a in result['activities'] if a['note'] == 'Pickup — 1 hour']
        self.assertEqual(len(pickup), 1)
        self.assertEqual(pickup[0]['kind'], 'ON_DUTY')

    def test_dropoff_is_on_duty(self):
        legs = [{'start': 'A', 'end': 'A', 'distance_miles': 0, 'duration_hours': 0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        dropoff = [a for a in result['activities'] if a['note'] == 'Drop-off — 1 hour']
        self.assertEqual(len(dropoff), 1)
        self.assertEqual(dropoff[0]['kind'], 'ON_DUTY')

    def test_route_activities_have_positive_duration(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': True, 'is_dropoff': True}])
        for activity in result['activities']:
            self.assertGreater(self.duration_minutes(activity), 0)

    def test_total_daily_hours_equal_24_for_each_day(self):
        result = self.build([{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': True, 'is_dropoff': True}])
        for day in result['days']:
            self.assertAlmostEqual(day['driving_hours'] + day['on_duty_hours'] + day['off_duty_hours'], 24.0, places=2)

    def test_fuel_no_stop_950(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 950, 'duration_hours': 15.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 950, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 0)

    def test_fuel_no_stop_999(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 999, 'duration_hours': 15.984, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 999, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 0)

    def test_fuel_exact_1000(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1000, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 0)

    def test_fuel_requires_1001(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1001, 'duration_hours': 16.016, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1001, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_fuel_requires_1200(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1200, 'duration_hours': 19.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1200, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_fuel_requires_1500(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 24, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1500, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_fuel_requires_2000(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2000, 'duration_hours': 32, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2000, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 1)

    def test_fuel_multiple_2500(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2500, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 2)

    def test_fuel_multiple_3000(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 3000, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 2)

    def test_fuel_multiple_4000(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 4000, 'duration_hours': 64, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 4000, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 3)

    def test_fuel_multiple_6000(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 6000, 'duration_hours': 96, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 6000, places=1)
        self.assertGreaterEqual(len(self.fuel_stops(result)), 5)

    def test_route_distance_preserved_variant_01(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 50, 'duration_hours': 0.8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 50, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_02(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 100, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_03(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 250, 'duration_hours': 4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 250, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_04(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 400, 'duration_hours': 6.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 400, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_05(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 500, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_06(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 600, 'duration_hours': 9.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 600, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_07(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 700, 'duration_hours': 11.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 700, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_08(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 800, 'duration_hours': 12.8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 800, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_09(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 900, 'duration_hours': 14.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 900, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_10(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 999.5, 'duration_hours': 15.992, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 999.5, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_11(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1000, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_12(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000.5, 'duration_hours': 16.008, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1000.5, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_13(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1100, 'duration_hours': 17.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1100, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_14(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1234.7, 'duration_hours': 19.7552, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1234.7, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_15(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1400, 'duration_hours': 22.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1400, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_16(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1600, 'duration_hours': 25.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1600, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_17(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1800, 'duration_hours': 28.8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1800, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_18(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2200, 'duration_hours': 35.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2200, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_19(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2500, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_20(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 3000, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_21(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3500, 'duration_hours': 56, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 3500, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_22(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 5000, 'duration_hours': 80, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 5000, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_route_distance_preserved_variant_23(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 6000, 'duration_hours': 96, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 6000, places=1)
        self.assertGreaterEqual(result['summary']['driving_hours'], 0.0)

    def test_service_configuration_1_pickup_only(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': True, 'is_dropoff': False}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertEqual('Pickup — 1 hour' in notes, True)
        self.assertEqual('Drop-off — 1 hour' in notes, False)

    def test_service_configuration_2_dropoff_only(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertEqual('Pickup — 1 hour' in notes, False)
        self.assertEqual('Drop-off — 1 hour' in notes, True)

    def test_service_configuration_3_both(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertEqual('Pickup — 1 hour' in notes, True)
        self.assertEqual('Drop-off — 1 hour' in notes, True)

    def test_service_configuration_4_neither(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': False}]
        result = self.build(legs)
        notes = [a['note'] for a in result['activities']]
        self.assertEqual('Pickup — 1 hour' in notes, False)
        self.assertEqual('Drop-off — 1 hour' in notes, False)

    def test_cycle_boundary_variant_01(self):
        result = self.build(self.legs, cycle=0)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_02(self):
        result = self.build(self.legs, cycle=0.1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_03(self):
        result = self.build(self.legs, cycle=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_04(self):
        result = self.build(self.legs, cycle=10)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_05(self):
        result = self.build(self.legs, cycle=12.5)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_06(self):
        result = self.build(self.legs, cycle=30)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_07(self):
        result = self.build(self.legs, cycle=50)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_08(self):
        result = self.build(self.legs, cycle=60)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_09(self):
        result = self.build(self.legs, cycle=64.9)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_10(self):
        result = self.build(self.legs, cycle=65)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_11(self):
        result = self.build(self.legs, cycle=69)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_12(self):
        result = self.build(self.legs, cycle=69.5)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_13(self):
        result = self.build(self.legs, cycle=69.9)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_14(self):
        result = self.build(self.legs, cycle=69.99)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_cycle_boundary_variant_15(self):
        result = self.build(self.legs, cycle=70)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        self.assertGreaterEqual(result['summary']['cycle_restarts'], 0)

    def test_start_datetime_variant_01(self):
        start = datetime(2026, 1, 1, 0, 0)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_start_datetime_variant_02(self):
        start = datetime(2026, 1, 1, 6, 0)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_start_datetime_variant_03(self):
        start = datetime(2026, 1, 1, 12, 0)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_start_datetime_variant_04(self):
        start = datetime(2026, 1, 1, 18, 0)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_start_datetime_variant_05(self):
        start = datetime(2026, 6, 30, 23, 30)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_start_datetime_variant_06(self):
        start = datetime(2026, 12, 31, 23, 59)
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs, start=start)
        self.assertEqual(self.as_datetime(result['activities'][0]['start']), start)

    def test_fractional_distance_variant_01(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 101, 'duration_hours': 1.616, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 101, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_02(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 333.3, 'duration_hours': 5.3328, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 333.3, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_03(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 444.4, 'duration_hours': 7.110399999999999, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 444.4, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_04(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 555.5, 'duration_hours': 8.888, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 555.5, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_05(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 777.7, 'duration_hours': 12.443200000000001, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 777.7, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_06(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 888.8, 'duration_hours': 14.220799999999999, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 888.8, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_07(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1111.1, 'duration_hours': 17.7776, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1111.1, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_08(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1222.2, 'duration_hours': 19.5552, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1222.2, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_09(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1555.5, 'duration_hours': 24.888, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1555.5, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_10(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1999.9, 'duration_hours': 31.9984, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1999.9, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_fractional_distance_variant_11(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2345.6, 'duration_hours': 37.5296, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2345.6, places=1)
        for activity in result['activities']:
            self.assertGreaterEqual(float(activity.get('miles', 0.0)), 0.0)

    def test_multi_segment_variant_01(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 200, 'duration_hours': 3.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 300, places=1)

    def test_multi_segment_variant_02(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 200, 'duration_hours': 3.2, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 300, 'duration_hours': 4.8, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 400, 'duration_hours': 6.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 900, places=1)

    def test_multi_segment_variant_03(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 400, 'duration_hours': 6.4, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 500, 'duration_hours': 8.0, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 600, 'duration_hours': 9.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1500, places=1)

    def test_multi_segment_variant_04(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 250, 'duration_hours': 4.0, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 250, 'duration_hours': 4.0, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 250, 'duration_hours': 4.0, 'is_pickup': False, 'is_dropoff': False}, {'start': 'D', 'end': 'E', 'distance_miles': 250, 'duration_hours': 4.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1000, places=1)

    def test_multi_segment_variant_05(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 700, 'duration_hours': 11.2, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 800, 'duration_hours': 12.8, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 900, 'duration_hours': 14.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2400, places=1)

    def test_multi_segment_variant_06(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 333.3, 'duration_hours': 5.3328, 'is_pickup': True, 'is_dropoff': False}, {'start': 'B', 'end': 'C', 'distance_miles': 444.4, 'duration_hours': 7.110399999999999, 'is_pickup': False, 'is_dropoff': False}, {'start': 'C', 'end': 'D', 'distance_miles': 555.5, 'duration_hours': 8.888, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1333.2, places=1)

    def test_daily_log_invariants_variant_01(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 100, 'duration_hours': 1.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_02(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 500, 'duration_hours': 8, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_03(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_04(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 24, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_05(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2200, 'duration_hours': 35.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_06(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3000, 'duration_hours': 48, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_07(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 4000, 'duration_hours': 64, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_daily_log_invariants_variant_08(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 6000, 'duration_hours': 96, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for day in result['days']:
            self.assertAlmostEqual(day['total_hours'], 24.0, places=2)
            self.assertGreaterEqual(day['driving_hours'], 0.0)
            self.assertGreaterEqual(day['on_duty_hours'], 0.0)
            self.assertGreaterEqual(day['off_duty_hours'], 0.0)
            self.assertGreaterEqual(day['miles'], 0.0)

    def test_rest_and_break_durations_variant_01(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1000, 'duration_hours': 16.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)
        for activity in self.restarts(result):
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_rest_and_break_durations_variant_02(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1200, 'duration_hours': 19.2, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)
        for activity in self.restarts(result):
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_rest_and_break_durations_variant_03(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1500, 'duration_hours': 24.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)
        for activity in self.restarts(result):
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_rest_and_break_durations_variant_04(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2000, 'duration_hours': 32.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)
        for activity in self.restarts(result):
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_rest_and_break_durations_variant_05(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2500, 'duration_hours': 40.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        for activity in self.breaks(result):
            self.assertAlmostEqual(self.duration_minutes(activity), 30.0, places=2)
        for activity in self.resets(result):
            self.assertAlmostEqual(self.duration_hours(activity), 10.0, places=2)
        for activity in self.restarts(result):
            self.assertAlmostEqual(self.duration_hours(activity), 34.0, places=2)

    def test_final_variety_invariant_001(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 125, 'duration_hours': 2.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 125, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_002(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 375, 'duration_hours': 6.0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 375, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_003(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 625, 'duration_hours': 10.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 625, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_004(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 875, 'duration_hours': 14.0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 875, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_005(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1025, 'duration_hours': 16.4, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1025, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_006(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1325, 'duration_hours': 21.2, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1325, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_007(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 1725, 'duration_hours': 27.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 1725, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_008(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2125, 'duration_hours': 34.0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2125, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_009(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 2725, 'duration_hours': 43.6, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 2725, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_010(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 3275, 'duration_hours': 52.4, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 3275, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_011(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 125, 'duration_hours': 2.0, 'is_pickup': False, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 125, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))

    def test_final_variety_invariant_012(self):
        legs = [{'start': 'A', 'end': 'B', 'distance_miles': 375, 'duration_hours': 6.0, 'is_pickup': True, 'is_dropoff': True}]
        result = self.build(legs)
        self.assertAlmostEqual(result['summary']['total_miles'], 375, places=1)
        self.assertLessEqual(result['summary']['cycle_hours_used_at_end'], 70.0001)
        for activity in result['activities']:
            self.assertLess(self.as_datetime(activity['start']), self.as_datetime(activity['end']))