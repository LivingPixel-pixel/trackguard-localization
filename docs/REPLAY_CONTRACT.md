# Measured replay interface

Human request: replace the illustrative track with the real recorded track and show yaw, position and directional errors changing over time. The source is the sealed continuous R16 later-laps 6+7 run. No new inference or tuning.

Public `data/replay.json` schema:

```json
{
  "schema": "trackguard-measured-replay-v1",
  "metadata": {
    "run": "R16 continuous development laps 6 + 7",
    "frames": 460,
    "published": 411,
    "unavailable": 49,
    "seed_count": 1,
    "duration_s": 229.5,
    "sampling_hz": 2,
    "rolling_window_s": 10,
    "track_image": "assets/track-replay-background.png",
    "track_width": 960,
    "track_height": 640,
    "reference_scope": "Evaluation-only reference after sealed inference",
    "coordinate_scope": "Rounded display pixels only; no world poses or raw labels"
  },
  "rows": [
    {
      "frame": 0,
      "t_s": 0,
      "lap": 6,
      "published": true,
      "seed": true,
      "reference_px": [100, 200],
      "estimate_px": [100, 200],
      "position_error_m": null,
      "lateral_error_m": null,
      "longitudinal_error_m": null,
      "yaw_error_deg": null,
      "rolling_position_rmse_m": null,
      "rolling_frame_publication_percent": 100
    }
  ]
}
```

Example values above describe the schema, not observations. Actual values must be computed from exact timestamp alignment and validated label eligibility. Metadata duration is the measured last minus first timestamp. Marker positions are integer display pixels. Public data excludes absolute timestamps, coordinate transforms, world x/y/yaw, labels and raw private file paths. Null errors mean unscored seed, missing output or invalid label, never zero. The seed is excluded from all local accuracy measures, including lap 6. Lap 7 has no reseed or exclusion.

Error formulas: planar Euclidean position error; signed lateral `-dx*sin(yaw_ref)+dy*cos(yaw_ref)`; signed longitudinal `dx*cos(yaw_ref)+dy*sin(yaw_ref)`; signed yaw degrees `atan2(sin(yaw_est-yaw_ref),cos(yaw_est-yaw_ref))`. Yaw RMSE uses the wrapped signed error. The 10-second rolling RMSE uses published eligible non-seed observations in that trailing window. Rolling frame publication counts every planned row, including unavailable rows, and must be labeled separately from occupied one-second coverage.

The background image renders the actual supplied track bounds and the recorded reference path. The moving reference marker is evaluation-only. During missing estimates it may continue, but there must be no invented estimate, interpolated error or line across an unavailable gap. The track overview cannot resolve centimetre-level differences; the error charts provide that detail.

Dashboard defaults to the complete measured replay with play/pause, speed and a discrete frame scrubber. Position, signed yaw, lateral/longitudinal charts share the same cursor. Current values and rolling metrics follow it. All 460 rows and 49 unavailable states remain in the replay data. Reduced-motion users get a paused replay. The unrelated stress/day aggregate cases must not be presented as this replay's measured trajectory.

GIF assets: `assets/track-replay.gif`, `assets/track-replay-card.gif`, `assets/track-replay-poster.png`. They show the real track with measured errors changing at the same recorded instant, sampled and accelerated for presentation. They must disclose recorded development replay, seed exclusion and acceleration. Source recordings and labels stay local.
