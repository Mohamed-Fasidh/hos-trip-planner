import React, { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import {
  MapContainer,
  TileLayer,
  Polyline,
  Marker,
  Popup,
  useMap,
  ZoomControl,
} from 'react-leaflet';
import L from 'leaflet';

import {
  Route,
  Fuel,
  Moon,
  Clock3,
  MapPin,
  Truck,
  ShieldCheck,
  AlertTriangle,
  Download,
} from 'lucide-react';

import 'leaflet/dist/leaflet.css';
import './styles.css';

const API =
  import.meta.env.VITE_API_URL ||
  'http://localhost:8000';

/* =========================================================
   MAP MARKER ICONS
   ========================================================= */

const MARKER_CONFIG = {
  START: {
    label: 'S',
    className: 'marker-start',
  },

  PICKUP: {
    label: 'P',
    className: 'marker-pickup',
  },

  DROPOFF: {
    label: 'D',
    className: 'marker-dropoff',
  },

  FUEL: {
    label: 'F',
    className: 'marker-fuel',
  },

  BREAK_30M: {
    label: 'B',
    className: 'marker-break',
  },

  REST_10H: {
    label: 'R',
    className: 'marker-rest',
  },

  RESTART_34H: {
    label: '34',
    className: 'marker-restart',
  },

  OFF_DUTY: {
    label: 'R',
    className: 'marker-rest',
  },
};

const markerIcon = (type) => {
  const config =
    MARKER_CONFIG[type] ||
    MARKER_CONFIG.OFF_DUTY;

  return L.divIcon({
    className: 'custom-marker',
    html: `
      <div class="${config.className}">
        ${config.label}
      </div>
    `,
    iconSize: [36, 36],
    iconAnchor: [18, 18],
    popupAnchor: [0, -18],
  });
};

/* =========================================================
   MAP BOUNDS
   ========================================================= */

function FitBounds({ legs }) {
  const map = useMap();

  useEffect(() => {
    const points = [];

    (legs || []).forEach((leg) => {
      const coordinates =
        leg?.geometry?.coordinates || [];

      coordinates.forEach(([lon, lat]) => {
        if (
          Number.isFinite(lat) &&
          Number.isFinite(lon)
        ) {
          points.push([lat, lon]);
        }
      });
    });

    if (points.length > 0) {
      map.fitBounds(points, {
        padding: [35, 35],
      });
    }
  }, [legs, map]);

  return null;
}

/* =========================================================
   FORMATTERS
   ========================================================= */

function fmtHours(hours) {
  const numericHours =
    Number(hours) || 0;

  const totalMinutes =
    Math.round(numericHours * 60);

  const hh =
    Math.floor(totalMinutes / 60);

  const mm =
    totalMinutes % 60;

  return `${hh}h ${String(mm).padStart(2, '0')}m`;
}

function fmtDate(value) {
  if (!value) return '';

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString([], {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
}

function fmtDay(value) {
  if (!value) return '';

  const date = new Date(
    `${value}T00:00:00`
  );

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleDateString([], {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
}

/* =========================================================
   MAP LEGEND
   ========================================================= */

function MapLegend() {
  const items = [
    ['START', 'Start'],
    ['PICKUP', 'Pickup'],
    ['FUEL', 'Fuel'],
    ['BREAK_30M', '30-min break'],
    ['REST_10H', '10-hour rest'],
    ['RESTART_34H', '34-hour restart'],
    ['DROPOFF', 'Drop-off'],
  ];

  return (
    <div className="map-legend">
      {items.map(([type, label]) => {
        const config =
          MARKER_CONFIG[type];

        return (
          <div
            className="map-legend-item"
            key={type}
          >
            <span
              className={`legend-marker ${config.className}`}
            >
              {config.label}
            </span>

            <span>{label}</span>
          </div>
        );
      })}
    </div>
  );
}

/* =========================================================
   TURN-BY-TURN ROUTE INSTRUCTIONS
   ========================================================= */

function RouteInstructions({ legs, stops, instructions: topLevelInstructions }) {
  /*
   * The API currently returns turn-by-turn instructions at the
   * top level as `data.instructions`. Some backend versions may
   * also expose them under each route leg. Prefer the top-level
   * response and fall back to the per-leg structure so the UI
   * remains compatible with both shapes.
   */
  const instructions = Array.isArray(
    topLevelInstructions
  )
    ? topLevelInstructions.map(
        (instruction, index) => ({
          ...instruction,
          legIndex:
            instruction?.leg_index ?? 0,
          stepIndex:
            instruction?.step_index ?? index,
        })
      )
    : (legs || []).flatMap(
        (leg, legIndex) =>
          (leg?.instructions || []).map(
            (instruction, stepIndex) => ({
              ...instruction,
              legIndex,
              stepIndex,
            })
          )
      );

  const checkpointStops = (stops || []).filter(
    (stop) =>
      stop?.location === 'Route checkpoint' ||
      stop?.label === 'Route checkpoint' ||
      stop?.type === 'FUEL'
  );

  if (
    instructions.length === 0 &&
    checkpointStops.length === 0
  ) {
    return null;
  }

  return (
    <section className="panel route-instructions">
      <div className="route-instructions-header">
        <div>
          <h2>Turn-by-turn route instructions</h2>
          <p>
            Route instructions and precise route-mile
            checkpoint locations from the generated route.
          </p>
        </div>
      </div>

      {instructions.length > 0 && (
        <div className="route-instructions-list">
          {instructions.map((item, index) => (
            <div
              className="route-instruction"
              key={`route-instruction-${item.legIndex}-${item.stepIndex}-${index}`}
            >
              <div className="route-instruction-number">
                {index + 1}
              </div>

              <div className="route-instruction-content">
                <strong>
                  {item.instruction ||
                    `Continue on ${
                      item.road_name || 'route'
                    }`}
                </strong>

                {item.road_name && (
                  <span>
                    Road: {item.road_name}
                  </span>
                )}

                <div className="route-checkpoint">
                  <span>
                    Route mile:{' '}
                    <strong>
                      {Number(
                        item.route_miles || 0
                      ).toFixed(1)}
                    </strong>
                  </span>

                  {Number.isFinite(
                    Number(item.latitude)
                  ) &&
                    Number.isFinite(
                      Number(item.longitude)
                    ) && (
                      <span className="route-checkpoint-location">
                        {Number(item.latitude).toFixed(5)}
                        {', '}
                        {Number(
                          item.longitude
                        ).toFixed(5)}
                      </span>
                    )}
                </div>
              </div>

              <div className="route-instruction-distance">
                {Number(
                  item.distance_miles || 0
                ).toFixed(1)}{' '}
                mi
              </div>
            </div>
          ))}
        </div>
      )}

      {checkpointStops.length > 0 && (
        <div className="route-instructions-list">
          {checkpointStops.map((stop, index) => (
            <div
              className="route-instruction"
              key={`checkpoint-${stop.start || index}-${index}`}
            >
              <div className="route-instruction-number">
                F
              </div>

              <div className="route-instruction-content">
                <strong>
                  {stop.location_text ||
                    stop.display ||
                    'Route checkpoint'}
                </strong>

                <span>
                  {stop.road ||
                    stop.city ||
                    stop.state
                    ? [
                        stop.road,
                        stop.city,
                        stop.state,
                      ]
                        .filter(Boolean)
                        .join(', ')
                    : 'Precise route checkpoint'}
                </span>

                <div className="route-checkpoint">
                  <span>
                    Route mile:{' '}
                    <strong>
                      {Number(
                        stop.route_miles || 0
                      ).toFixed(1)}
                    </strong>
                  </span>

                  {Number.isFinite(
                    Number(stop.lat)
                  ) &&
                    Number.isFinite(
                      Number(stop.lon)
                    ) && (
                      <span className="route-checkpoint-location">
                        {Number(stop.lat).toFixed(5)}
                        {', '}
                        {Number(
                          stop.lon
                        ).toFixed(5)}
                      </span>
                    )}
                </div>
              </div>

              <div className="route-instruction-distance">
                CHECKPOINT
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/* =========================================================
   DAILY LOG SHEET
   ========================================================= */

function parseLogDateTime(value) {
  if (!value) return null;

  const raw = String(value);
  const localValue = raw
    .replace(/Z$/, "")
    .replace(/[+-]\d{2}:\d{2}$/, "");

  const parsed = new Date(localValue);
  return Number.isNaN(parsed.getTime())
    ? null
    : parsed;
}

function normalizeActivityLocations(
  activities,
  fallbackLocation = ""
) {
  const list = Array.isArray(activities)
    ? activities
    : [];

  return list.map((activity, index) => {
    if (activity?.kind !== "DRIVING") {
      return activity;
    }

    // A driving activity represents movement FROM the
    // previous activity's location TO its destination.
    //
    // Therefore the displayed location for DRIVING
    // should be the location where that driving begins.
    const previousActivity =
      index > 0 ? list[index - 1] : null;

    return {
      ...activity,
      location:
        previousActivity?.location ||
        fallbackLocation ||
        activity.location ||
        "",
    };
  });
}

function LogSheet({
  day,
  index,
  input,
}) {
  if (!day) {
    return (
      <div className="log-card fmcsa-log-card">
        <div className="log-head">
          <strong>No daily log available</strong>
        </div>
      </div>
    );
  }

  const rawActivities = day.activities || [];

const activities = normalizeActivityLocations(
  rawActivities,
  input?.current_location || ""
);

  const dayStart = new Date(
    `${day.date}T00:00:00`
  );

  const segments = activities
    .map((activity) => {
      const start = parseLogDateTime(
        activity.start
      );
      const end = parseLogDateTime(
        activity.end
      );

      if (!start || !end) return null;

      return {
        ...activity,
        startMin:
          (start.getTime() -
            dayStart.getTime()) /
          60000,
        endMin:
          (end.getTime() -
            dayStart.getTime()) /
          60000,
      };
    })
    .filter(
      (activity) =>
        activity &&
        activity.endMin > 0 &&
        activity.startMin < 1440
    )
    .map((activity) => ({
      ...activity,
      startMin: Math.max(
        0,
        activity.startMin
      ),
      endMin: Math.min(
        1440,
        activity.endMin
      ),
    }))
    .filter(
      (activity) =>
        activity.endMin >
        activity.startMin
    );

  const ROWS = {
    OFF_DUTY: 0,
    SLEEPER_BERTH: 1,
    DRIVING: 2,
    ON_DUTY: 3,
  };

  const rowNames = [
    "1. OFF DUTY",
    "2. SLEEPER BERTH",
    "3. DRIVING",
    "4. ON DUTY (NOT DRIVING)",
  ];

  const durationHours = (activity) =>
    Math.max(
      0,
      activity.endMin -
        activity.startMin
    ) / 60;

  const totals = {
    OFF_DUTY: 0,
    SLEEPER_BERTH: 0,
    DRIVING: 0,
    ON_DUTY: 0,
  };

  segments.forEach((activity) => {
    if (
      Object.prototype.hasOwnProperty.call(
        totals,
        activity.kind
      )
    ) {
      totals[activity.kind] +=
        durationHours(activity);
    }
  });

  const drivingHours =
    Number(
      day.driving_hours ??
        totals.DRIVING
    ) || 0;

  const onDutyHours =
    Number(
      day.on_duty_hours ??
        totals.ON_DUTY
    ) || 0;

  const sleeperHours =
    totals.SLEEPER_BERTH;

  const offDutyHours = Math.max(
    0,
    24 -
      drivingHours -
      onDutyHours -
      sleeperHours
  );

  const dailyMiles = activities.reduce(
    (sum, activity) =>
      sum +
      Number(activity.miles || 0),
    0
  );

  const formatHours = (hours) => {
    const totalMinutes = Math.round(
      Number(hours || 0) * 60
    );

    return `${Math.floor(
      totalMinutes / 60
    )}:${String(
      totalMinutes % 60
    ).padStart(2, "0")}`;
  };

  const formatClock = (minutes) => {
    const safe = Math.max(
      0,
      Math.min(
        1440,
        Math.round(minutes)
      )
    );

    if (safe === 1440) {
      return "12:00 AM";
    }

    const hour = Math.floor(
      safe / 60
    );
    const minute = safe % 60;
    const suffix =
      hour >= 12 ? "PM" : "AM";
    const hour12 =
      hour % 12 || 12;

    return `${hour12}:${String(
      minute
    ).padStart(2, "0")} ${suffix}`;
  };

  const formatDate = (value) => {
    const date =
      parseLogDateTime(value);

    if (!date) {
      return String(value || "");
    }

    return date.toLocaleDateString(
      [],
      {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      }
    );
  };

  const statusLabel = (kind) =>
    String(kind || "")
      .replaceAll("_", " ")
      .toLowerCase()
      .replace(/\b\w/g, (letter) =>
        letter.toUpperCase()
      );

  const timeLeft = (minutes) =>
    `${(
      (Math.max(
        0,
        Math.min(1440, minutes)
      ) /
        1440) *
      100
    ).toFixed(5)}%`;

  const graphSegments =
    segments.map(
      (activity, segmentIndex) => {
        const row =
          ROWS[activity.kind] ??
          ROWS.ON_DUTY;

        return (
          <div
            key={`${activity.start}-${activity.end}-${segmentIndex}`}
            className="fmcsa-duty-segment"
            style={{
              left: timeLeft(
                activity.startMin
              ),
              width: `${(
                ((activity.endMin -
                  activity.startMin) /
                  1440) *
                100
              ).toFixed(5)}%`,
              top: `${row * 25 + 12.5}%`,
              transform: "translateY(-50%)",
            }}
            title={`${formatClock(
              activity.startMin
            )} – ${formatClock(
              activity.endMin
            )}: ${statusLabel(
              activity.kind
            )}`}
          />
        );
      }
    );

  const timeTicks = Array.from(
    { length: 97 },
    (_, tick) => {
      const minutes =
        tick * 15;

      return (
        <div
          key={`tick-${minutes}`}
          className={`fmcsa-time-tick ${
            minutes % 60 === 0
              ? "hour"
              : minutes % 30 === 0
              ? "half"
              : ""
          }`}
          style={{
            left: timeLeft(minutes),
          }}
        />
      );
    }
  );

  const hourLabels = Array.from(
    { length: 25 },
    (_, hour) => {
      const label =
        hour === 0 ||
        hour === 24
          ? "12A"
          : hour === 12
          ? "12P"
          : String(
              hour > 12
                ? hour - 12
                : hour
            );

      return (
        <span
          key={`label-${hour}`}
          className="fmcsa-hour-label"
          style={{
            left: timeLeft(
              hour * 60
            ),
          }}
        >
          {label}
        </span>
      );
    }
  );

  const totalHours =
    offDutyHours +
    sleeperHours +
    drivingHours +
    onDutyHours;

  const cycleUsed = Number(
    input?.current_cycle_used || 0
  );

  return (
    <div className="log-card fmcsa-log-card printable-log">
      <div className="log-head">
        <div>
          <strong>
            Daily Log {index + 1}
          </strong>
          <span>
            {formatDate(day.date)}
          </span>
        </div>

        <button
          type="button"
          className="ghost"
          onClick={() => {
            document.body.classList.add(
              "printing-log"
            );

            window.setTimeout(() => {
              window.print();

              window.setTimeout(() => {
                document.body.classList.remove(
                  "printing-log"
                );
              }, 100);
            }, 0);
          }}
        >
          <Download size={15} />
          Print / PDF
        </button>
      </div>

      <div className="fmcsa-sheet">
        <header className="fmcsa-header">
          <div className="fmcsa-header-main">
            <div className="fmcsa-agency">
              U.S. DEPARTMENT OF
              TRANSPORTATION
            </div>

            <h2>
              DRIVER'S DAILY LOG
            </h2>

            <p>
              RECORD OF DUTY STATUS —
              ONE CALENDAR DAY
            </p>
          </div>

          <div className="fmcsa-header-meta">
            <div>
              <b>DATE</b>
              <span>
                {formatDate(day.date)}
              </span>
            </div>

            <div>
              <b>
                TOTAL MILES DRIVING TODAY
              </b>
              <span>
                {dailyMiles.toFixed(1)}
              </span>
            </div>
          </div>
        </header>

        <section className="fmcsa-trip-fields">
          <div>
            <b>FROM</b>
            <span>
              {input?.current_location ||
                "—"}
            </span>
          </div>

          <div>
            <b>TO</b>
            <span>
              {input?.dropoff_location ||
                "—"}
            </span>
          </div>

          <div>
            <b>PICKUP</b>
            <span>
              {input?.pickup_location ||
                "—"}
            </span>
          </div>

          <div>
            <b>TOTAL MILEAGE TODAY</b>
            <span>
              {dailyMiles.toFixed(1)}
            </span>
          </div>

          <div className="wide">
            <b>NAME OF CARRIER</b>
            <span>
              HOS Trip Planner Assessment
            </span>
          </div>

          <div>
            <b>
              TRUCK / TRACTOR / TRAILER NO.
            </b>
            <span>—</span>
          </div>

          <div className="wide">
            <b>MAIN OFFICE ADDRESS</b>
            <span>—</span>
          </div>

          <div>
            <b>
              HOME TERMINAL ADDRESS
            </b>
            <span>—</span>
          </div>
        </section>

        <section className="fmcsa-graph-section">
          <div className="fmcsa-graph-title">
            <strong>
              RECORD OF DUTY STATUS
            </strong>
            <span>
              24-HOUR PERIOD — 15-MINUTE
              GRID
            </span>
          </div>

          <div className="fmcsa-graph">
            <div className="fmcsa-graph-labels">
              {rowNames.map(
                (name) => (
                  <div
                    key={name}
                    className="fmcsa-row-label"
                  >
                    {name}
                  </div>
                )
              )}
            </div>

            <div className="fmcsa-graph-area">
              <div className="fmcsa-hour-labels">
                {hourLabels}
              </div>

              <div className="fmcsa-grid">
                {timeTicks}

                {[0, 1, 2, 3, 4].map(
                  (row) => (
                    <div
                      key={`horizontal-${row}`}
                      className="fmcsa-horizontal-line"
                      style={{
                        top: `${row * 25}%`,
                      }}
                    />
                  )
                )}

                {graphSegments}
              </div>

              <div className="fmcsa-midnight-labels">
                <span>12 AM</span>
                <span>12 PM</span>
                <span>12 AM</span>
              </div>
            </div>

            <div className="fmcsa-total-column">
              <div className="fmcsa-total-heading">
                TOTAL
                <br />
                HOURS
              </div>

              <div>
                {formatHours(
                  offDutyHours
                )}
              </div>

              <div>
                {formatHours(
                  sleeperHours
                )}
              </div>

              <div>
                {formatHours(
                  drivingHours
                )}
              </div>

              <div>
                {formatHours(
                  onDutyHours
                )}
              </div>
            </div>
          </div>
        </section>

        <section className="fmcsa-totals">
          <div>
            <b>OFF DUTY</b>
            <span>
              {formatHours(
                offDutyHours
              )}
            </span>
          </div>

          <div>
            <b>SLEEPER BERTH</b>
            <span>
              {formatHours(
                sleeperHours
              )}
            </span>
          </div>

          <div>
            <b>DRIVING</b>
            <span>
              {formatHours(
                drivingHours
              )}
            </span>
          </div>

          <div>
            <b>ON DUTY</b>
            <span>
              {formatHours(
                onDutyHours
              )}
            </span>
          </div>

          <div>
            <b>24-HOUR TOTAL</b>
            <span>
              {formatHours(
                totalHours
              )}
            </span>
          </div>
        </section>

        <section className="fmcsa-remarks-section">
          <div className="fmcsa-section-title">
            REMARKS
          </div>

          <div className="fmcsa-remarks-header">
            <span>TIME</span>
            <span>PLACE / LOCATION</span>
            <span>DUTY STATUS / ACTIVITY</span>
            <span>MILES</span>
          </div>

          {segments.length === 0 ? (
            <div className="fmcsa-empty-row">
              No recorded activities.
            </div>
          ) : (
            segments.map(
              (activity, remarkIndex) => (
                <div
                  key={`remark-${remarkIndex}`}
                  className="fmcsa-remark-row"
                >
                  <b>
                    {formatClock(
                      activity.startMin
                    )}
                  </b>

                  <span>
                    {activity.location ||
                      "—"}
                  </span>

                  <span>
                    {activity.note ||
                      statusLabel(
                        activity.kind
                      )}
                  </span>

                  <span>
                    {Number(
                      activity.miles || 0
                    ).toFixed(1)}
                  </span>
                </div>
              )
            )
          )}
        </section>

        <section className="fmcsa-document-fields">
          <div>
            <b>SHIPPING DOCUMENTS</b>
            <span>—</span>
          </div>

          <div>
            <b>
              DVL / MANIFEST NO.
            </b>
            <span>—</span>
          </div>

          <div>
            <b>
              SHIPPER & COMMODITY
            </b>
            <span>—</span>
          </div>
        </section>

        <section className="fmcsa-recap">
          <div className="fmcsa-section-title">
            DAILY RECAP / CYCLE INFORMATION
          </div>

          <div className="fmcsa-recap-grid">
            <div>
              <b>
                70/8 CYCLE USED AT START
              </b>
              <span>
                {cycleUsed.toFixed(2)} h
              </span>
            </div>

            <div>
              <b>DRIVING TODAY</b>
              <span>
                {formatHours(
                  drivingHours
                )}
              </span>
            </div>

            <div>
              <b>ON DUTY TODAY</b>
              <span>
                {formatHours(
                  onDutyHours
                )}
              </span>
            </div>

            <div>
              <b>OFF DUTY TODAY</b>
              <span>
                {formatHours(
                  offDutyHours
                )}
              </span>
            </div>

            <div>
              <b>24-HOUR TOTAL</b>
              <span>
                {formatHours(
                  totalHours
                )}
              </span>
            </div>
          </div>
        </section>

        <section className="fmcsa-signatures">
          <div>
            <div className="signature-line" />
            <span>
              DRIVER'S SIGNATURE
            </span>
          </div>

          <div>
            <div className="signature-line" />
            <span>
              VEHICLE / UNIT
            </span>
          </div>

          <div>
            <div className="signature-line" />
            <span>
              TIME ZONE
            </span>
          </div>
        </section>

        <div className="fmcsa-disclaimer">
          Assessment-oriented FMCSA-style
          record. This UI is not an
          official government form.
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   MAIN APP
   ========================================================= */

function App() {
  const [form, setForm] =
    useState({
      current_location:
        'Chicago, IL',

      pickup_location:
        'Indianapolis, IN',

      dropoff_location:
        'Nashville, TN',

      current_cycle_used: '0',

      start_datetime: '',
    });

  const [data, setData] =
    useState(null);

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState('');

  const [openDay, setOpenDay] =
    useState(0);

  const set = (key, value) => {
    setForm((previous) => ({
      ...previous,
      [key]: value,
    }));
  };

  /* =======================================================
     PLAN TRIP
     ======================================================= */

  async function plan(event) {
    event.preventDefault();

    setLoading(true);
    setError('');
    setData(null);
    setOpenDay(0);

    try {
      const response =
        await fetch(
          `${API}/api/plan/`,
          {
            method: 'POST',

            headers: {
              'Content-Type':
                'application/json',
            },

            body: JSON.stringify(
              form
            ),
          }
        );

      const json =
        await response.json();
        
      console.log("FULL PLAN RESPONSE:", json);
      console.log("INSTRUCTIONS:", json.instructions);
      console.log("INSTRUCTIONS COUNT:", json.instructions?.length);

      if (!response.ok) {
        throw new Error(
          json.error ||
            'Planning failed'
        );
      }

      setData(json);
    } catch (err) {
      setError(
        err.message ||
          'Unable to generate trip.'
      );
    } finally {
      setLoading(false);
    }
  }

  /* =======================================================
     ROUTE COORDINATES
     ======================================================= */

  const allCoords = useMemo(
    () =>
      data
        ? data.legs.flatMap(
            (leg) =>
              leg?.geometry
                ?.coordinates || []
          )
        : [],
    [data]
  );

  const center = allCoords.length
    ? [
        allCoords[0][1],
        allCoords[0][0],
      ]
    : [
        39.8283,
        -98.5795,
      ];

  /* =======================================================
     MAP STOPS
     ======================================================= */

  const stops = useMemo(() => {
    if (!data) return [];

    if (
      Array.isArray(data.stops)
    ) {
      return data.stops;
    }

    /*
     * Backward compatibility with
     * the old API response.
     */
    return (data.places || [])
      .map((place, index) => ({
        ...place,

        type:
          index === 0
            ? 'START'
            : index === 1
            ? 'PICKUP'
            : 'DROPOFF',

        label:
          index === 0
            ? 'Start'
            : index === 1
            ? 'Pickup'
            : 'Drop-off',
      }));
  }, [data]);

  /* =======================================================
     RENDER
     ======================================================= */

  return (
    <div className="app">

      {/* ===================================================
          HEADER
      =================================================== */}

      <header className="topbar">

        <div className="brand">

          <div className="brand-mark">
            <Truck size={19} />
          </div>

          <div>
            <b>HOS Trip Planner</b>

            <span>
              ELD route & daily-log generator
            </span>
          </div>

        </div>

        <div className="compliance">
          <ShieldCheck size={17} />

          70/8 · 11h drive · 14h window
        </div>

      </header>

      <main>

        {/* =================================================
            HERO
        ================================================= */}

        <section className="hero">

          <div>

            <div className="eyebrow">
              FMCSA PROPERTY-CARRIER PLANNER
            </div>

            <h1>
              Plan the trip.{' '}
              <em>
                Prove the hours.
              </em>
            </h1>

            <p>
              Build a route, schedule
              compliant stops and
              automatically draw
              multi-day driver logs
              from the assessment rules.
            </p>

          </div>

          <div className="hero-rule">

            <div>
              <strong>
                Scope
              </strong>

              <span>
                70 hours / 8 days
              </span>
            </div>

            <div>
              <strong>
                Break
              </strong>

              <span>
                30 min after 8h driving
              </span>
            </div>

            <div>
              <strong>
                Fuel
              </strong>

              <span>
                ≤ 1000 route miles
              </span>
            </div>

          </div>

        </section>

        {/* =================================================
            PLANNER
        ================================================= */}

        <section className="planner-grid">

          {/* FORM */}

          <form
            className="panel form-panel"
            onSubmit={plan}
          >

            <div className="panel-title">

              <div>

                <span className="step">
                  01
                </span>

                <div>

                  <h2>
                    Trip details
                  </h2>

                  <p>
                    Only the required
                    assessment inputs
                    are needed.
                  </p>

                </div>

              </div>

            </div>

            {[
              [
                'current_location',
                'Current location',
                'e.g. Chicago, IL',
              ],

              [
                'pickup_location',
                'Pickup location',
                'e.g. Indianapolis, IN',
              ],

              [
                'dropoff_location',
                'Dropoff location',
                'e.g. Nashville, TN',
              ],
            ].map(
              ([key, label, placeholder]) => (
                <label key={key}>

                  {label}

                  <div className="input-wrap">

                    <MapPin size={17} />

                    <input
                      value={
                        form[key]
                      }
                      onChange={(event) =>
                        set(
                          key,
                          event.target.value
                        )
                      }
                      placeholder={
                        placeholder
                      }
                      required
                    />

                  </div>

                </label>
              )
            )}

            <label>

              Current cycle used
              (hours)

              <div className="input-wrap">

                <Clock3 size={17} />

                <input
                  type="number"
                  min="0"
                  max="70"
                  step="0.25"
                  value={
                    form.current_cycle_used
                  }
                  onChange={(event) =>
                    set(
                      'current_cycle_used',
                      event.target.value
                    )
                  }
                  required
                />

              </div>

            </label>

            <details className="advanced">

              <summary>
                Advanced: trip start time
              </summary>

              <input
                type="datetime-local"
                value={
                  form.start_datetime
                }
                onChange={(event) =>
                  set(
                    'start_datetime',
                    event.target.value
                  )
                }
              />

              <small>
                Default is 06:00 if
                omitted. All calculations
                use the selected start
                date/time.
              </small>

            </details>

            <div className="assumption-box">

              <strong>
                Locked assessment
                assumptions
              </strong>

              <ul>
                <li>
                  Property-carrying CMV ·
                  70/8 cycle
                </li>

                <li>
                  No adverse driving
                  conditions
                </li>

                <li>
                  1 hour pickup +
                  1 hour drop-off
                </li>

                <li>
                  Fuel stop every
                  1,000 route miles
                </li>
              </ul>

            </div>

            <button
              className="primary"
              disabled={loading}
              type="submit"
            >

              {loading ? (
                <>
                  <span className="spinner" />
                  Planning route…
                </>
              ) : (
                <>
                  <Route size={18} />
                  Generate compliant trip
                </>
              )}

            </button>

            {error && (
              <div className="error">

                <AlertTriangle
                  size={18}
                />

                {error}

              </div>
            )}

          </form>

          {/* MAP */}

          <section className="panel map-panel">

            <div className="panel-title">

              <div>

                <span className="step">
                  02
                </span>

                <div>

                  <h2>
                    Route & stops
                  </h2>

                  <p>
                    OpenStreetMap + OSRM
                    routing.
                  </p>

                </div>

              </div>

            </div>

            <div className="map-wrap">

              <MapContainer
                center={center}
                zoom={5}
                scrollWheelZoom
                zoomControl={false}
                className="map"
              >

                {data && (
                  <FitBounds
                    legs={data.legs}
                  />
                )}

                <ZoomControl
                  position="bottomright"
                />

                <TileLayer
                  attribution="&copy; OpenStreetMap contributors"
                  url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                />

                {data?.legs?.map(
                  (leg, index) => (
                    <Polyline
                      key={index}
                      positions={(
                        leg.geometry
                          ?.coordinates ||
                        []
                      ).map(
                        ([lon, lat]) => [
                          lat,
                          lon,
                        ]
                      )}
                      pathOptions={{
                        weight: 5,
                      }}
                    />
                  )
                )}

                {stops.map(
                  (stop, index) => {

                    if (
                      !Number.isFinite(
                        Number(
                          stop.lat
                        )
                      ) ||
                      !Number.isFinite(
                        Number(
                          stop.lon
                        )
                      )
                    ) {
                      return null;
                    }

                    const type =
                      stop.type ||
                      'OFF_DUTY';

                    return (
                      <Marker
                        key={`${type}-${stop.start || index}-${index}`}
                        position={[
                          Number(
                            stop.lat
                          ),
                          Number(
                            stop.lon
                          ),
                        ]}
                        icon={markerIcon(
                          type
                        )}
                      >

                        <Popup>

                          <strong>
                            {stop.label ||
                              type}
                          </strong>

                          <br />

                          {stop.location_text ||
                            stop.display ||
                            stop.location}

                          {stop.start && (
                            <>
                              <br />
                              Start:{' '}
                              {fmtDate(
                                stop.start
                              )}
                            </>
                          )}

                          {stop.end && (
                            <>
                              <br />
                              End:{' '}
                              {fmtDate(
                                stop.end
                              )}
                            </>
                          )}

                          {stop.note && (
                            <>
                              <br />
                              {stop.note}
                            </>
                          )}

                        </Popup>

                      </Marker>
                    );
                  }
                )}

              </MapContainer>

              {!data && (
                <div className="map-empty">

                  <Route size={30} />

                  <strong>
                    Your route will
                    appear here
                  </strong>

                  <span>
                    Enter the trip details
                    and generate a plan.
                  </span>

                </div>
              )}

            </div>

            {data && (
              <MapLegend />
            )}

            {data && (
              <div className="leg-row">

                {data.legs.map(
                  (leg, index) => (
                    <div key={index}>

                      <span>
                        {index === 0
                          ? 'START → PICKUP'
                          : 'PICKUP → DROP-OFF'}
                      </span>

                      <b>
                        {Number(
                          leg.distance_miles ||
                            0
                        ).toFixed(1)}{' '}
                        mi
                      </b>

                      <small>
                        {fmtHours(
                          leg.duration_hours
                        )}{' '}
                        drive
                      </small>

                    </div>
                  )
                )}

              </div>
            )}

          </section>

        </section>

        <RouteInstructions
          legs={data?.legs || []}
          stops={stops}
          instructions={
            data?.instructions || []
          }
        />

        {/* =================================================
            RESULTS
        ================================================= */}

        {data && (
          <>

            {/* METRICS */}

            <section className="metrics">

              <div>
                <Route />

                <span>
                  <small>
                    Total route
                  </small>

                  <b>
                    {Number(
                      data.schedule
                        ?.summary
                        ?.total_miles || 0
                    ).toFixed(1)}{' '}
                    mi
                  </b>
                </span>
              </div>

              <div>
                <Truck />

                <span>
                  <small>
                    Driving
                  </small>

                  <b>
                    {fmtHours(
                      data.schedule
                        ?.summary
                        ?.driving_hours
                    )}
                  </b>
                </span>
              </div>

              <div>
                <Clock3 />

                <span>
                  <small>
                    Daily logs
                  </small>

                  <b>
                    {
                      data.schedule
                        ?.summary
                        ?.days
                    }
                  </b>
                </span>
              </div>

              <div>
                <Fuel />

                <span>
                  <small>
                    Cycle at end
                  </small>

                  <b>
                    {Number(
                      data.schedule
                        ?.summary
                        ?.cycle_hours_used_at_end ||
                        0
                    ).toFixed(2)}{' '}
                    h
                  </b>
                </span>
              </div>

            </section>

            {/* ITINERARY */}

            <section className="panel itinerary">

              <div className="panel-title">

                <div>

                  <span className="step">
                    03
                  </span>

                  <div>

                    <h2>
                      ELD itinerary
                    </h2>

                    <p>
                      Every activity is
                      timestamped for the
                      generated daily logs.
                    </p>

                  </div>

                </div>

              </div>

              <div className="timeline">

                {normalizeActivityLocations(
    data.schedule?.activities || [],
    form.current_location || ""
  ).map(
                  (activity, index) => (

                    <div
                      className={`timeline-item ${String(
                        activity.kind ||
                          ''
                      ).toLowerCase()}`}
                      key={`${activity.start}-${index}`}
                    >

                      <div className="dot" />

                      <div className="time">

                        {fmtDate(
                          activity.start
                        )}

                        <br />

                        <span>
                          {fmtDate(
                            activity.end
                          )}
                        </span>

                      </div>

                      <div className="activity">

                        <b>
                          {activity.note ||
                            String(
                              activity.kind ||
                                ''
                            ).replace(
                              '_',
                              ' '
                            )}
                        </b>

                        <span>
                          {activity.location}
                        </span>

                      </div>

                      {Number(
                        activity.miles || 0
                      ) > 0 && (
                        <div className="miles">
                          +
                          {Number(
                            activity.miles
                          ).toFixed(1)}{' '}
                          mi
                        </div>
                      )}

                    </div>

                  )
                )}

              </div>

            </section>

            {/* DAILY LOGS */}

            <section className="panel logs">

              <div className="panel-title">

                <div>

                  <span className="step">
                    04
                  </span>

                  <div>

                    <h2>
                      Filled daily log
                      sheets
                    </h2>

                    <p>
                      Generated as
                      multi-day 24-hour
                      RODS-style sheets.
                    </p>

                  </div>

                </div>

              </div>

              <div className="day-tabs">

                {(
                  data.schedule
                    ?.days || []
                ).map(
                  (day, index) => (

                    <button
                      type="button"
                      className={
                        openDay === index
                          ? 'active'
                          : ''
                      }
                      key={day.date}
                      onClick={() =>
                        setOpenDay(
                          index
                        )
                      }
                    >

                      Day {index + 1}

                      <span>
                        {fmtDay(
                          day.date
                        )}
                      </span>

                    </button>

                  )
                )}

              </div>

              <LogSheet
                day={
                  data.schedule
                    ?.days?.[
                    openDay
                  ]
                }
                index={openDay}
                input={form}
              />

            </section>

            {/* COMPLIANCE NOTE */}

            <section className="source-note">

              <ShieldCheck size={18} />

              <div>

                <strong>
                  Compliance basis
                </strong>

                <p>
                  Planner logic is based
                  on the uploaded FMCSA
                  Interstate Truck
                  Driver’s Guide for
                  property carriers and
                  the assessment’s explicit
                  assumptions. It is an
                  assessment tool, not
                  legal advice.
                </p>

              </div>

            </section>

          </>
        )}

      </main>

      <footer>
        HOS Trip Planner · Built for
        the Full Stack Developer
        assessment · Map data ©
        OpenStreetMap contributors
      </footer>

    </div>
  );
}

/* =========================================================
   ROOT
   ========================================================= */

createRoot(
  document.getElementById('root')
).render(
  <App />
)