# HOS Rules Used by the Planner

## Assessment Scope

The planner follows the assessment assumptions:

- Property-carrying driver.
- 70 hours / 8 days cycle.
- No adverse driving conditions.
- Fueling at least once every 1,000 route miles.
- One hour for pickup.
- One hour for drop-off.

## Planner Rules

1. **Maximum driving:** 11 total driving hours within a 14-consecutive-hour window.

2. **30-minute break:** A 30-minute consecutive break from driving is inserted after 8 cumulative driving hours.

3. **10-hour off-duty reset:** A normal 10-hour off-duty reset starts a new 11-hour driving allowance and a new 14-consecutive-hour driving window.

4. **70-hour / 8-day cycle:** The planner uses the supplied current-cycle hours to determine the driver's remaining available cycle time within the assessment's 70-hour / 8-day cycle.

5. **34-hour restart:** When the remaining cycle time cannot support the planned continued operation, the planner schedules a conservative 34-hour restart and resets the cycle usage to zero.

6. **Pickup:** Pickup is modeled as one hour of on-duty, non-driving time.

7. **Drop-off:** Drop-off is modeled as one hour of on-duty, non-driving time.

8. **Fueling:** Fuel stops are scheduled at or before every 1,000 route miles, matching the assessment requirement.

9. **Standard off-duty resets:** The planner uses standard off-duty resets. Split-sleeper, adverse-driving-condition, short-haul, personal-conveyance, and other special exceptions are not automatically inferred because they are outside the defined assessment scope.

## Daily RODS-Style Logs

The planner generates multi-day digital RODS-style daily logs.

Each daily log represents a complete 24-hour period and includes the scheduled duty-status timeline.

The UI reproduces the assessment-relevant concepts of a driver's daily log, including:

- 24-hour graph grid.
- Date.
- Total miles driven.
- Duty-status activities.
- Driving periods.
- On-duty/non-driving periods.
- Off-duty/rest periods.
- Activity remarks.
- Total hours by duty status.
- Trip and location information where available.

The digital log is intended to provide an assessment-oriented visualization of the generated HOS schedule.

## Scope Limitations

The planner intentionally does not automatically infer or apply:

- Split-sleeper provisions.
- Adverse-driving-condition exceptions.
- CDL short-haul exceptions.
- Non-CDL short-haul exceptions.
- 16-hour short-haul exceptions.
- Personal-conveyance rules.
- Yard-move rules.
- Other special HOS exceptions requiring additional driver or operational history.

These limitations are intentional and keep the implementation aligned with the defined assessment scope.

## Important Accuracy Note

The planner's current-cycle input represents the driver's already-used hours supplied by the assessment.

The planner uses that value to determine the remaining available 70-hour cycle capacity. It does not attempt to reconstruct historical daily duty records that are not supplied as input.

The routing layer uses free/open mapping services, while the HOS scheduling layer operates deterministically on the route segments returned to it.