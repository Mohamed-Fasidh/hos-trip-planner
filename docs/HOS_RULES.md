# HOS rules used by the planner

Assessment scope: property-carrying driver, 70 hours / 8 days, no adverse driving conditions, fueling at least once every 1,000 miles, and one hour for pickup/drop-off.

Planner rules:

1. Maximum driving: 11 total driving hours within a 14-consecutive-hour window.
2. A 30-minute consecutive break from driving is inserted after 8 cumulative driving hours.
3. A normal 10-hour off-duty reset restarts the 11-hour and 14-hour limits.
4. The 70-hour / 8-day limit is treated as a rolling cycle; the supplied current-cycle hours reduce available cycle time.
5. When the remaining cycle cannot support continued driving, the planner schedules an optional 34-hour restart and resets the cycle to zero.
6. Pickup and drop-off are modeled as one hour of on-duty non-driving time each.
7. Fuel is scheduled at 950 route miles, intentionally below the assessment's 1,000-mile maximum interval.
8. Standard off-duty resets are used. Split sleeper, adverse-condition and short-haul exceptions are not automatically inferred.

The source guide also specifies that a daily RODS/log contains a 24-hour graph grid, date, miles, vehicle information, carrier information, signature/certification, remarks, total hours, and shipping information. The UI reproduces these concepts in a digital SVG sheet.
