# What the numbers establish

The public dashboard reads `data/metrics.json`, a curated aggregate summary of the local campaign measured on 22 October 2026. It contains no per-frame positions, images, feature descriptors, track geometry or hidden labels.

## Accuracy and availability

Position RMSE is the square root of the mean squared planar position error. Lateral RMSE projects that error across the true vehicle heading. Both describe finite published estimates. The local RMSE excludes the run's one initial truth seed.

One-second coverage counts time bins containing at least one output. It is not the percentage of frames published. The combined development run has 94.8% one-second coverage and publishes 411/460 frames, or 89.35%. All 49 unavailable outputs remain in coverage membership.

The same continuous run covers local laps 6 and 7. It has one initial truth seed and no lap 7 reset. These laps have been consumed repeatedly for development. They are not untouched holdouts. Offline map construction uses earlier permitted reference data. Query labels remain evaluator-only after predictions are frozen.

Combined non-seed results: 17.4775 cm position RMSE, 11.4220 cm lateral RMSE, 13.3515 cm median, 31.9454 cm p95 and 58.7450 cm maximum position error. 327 of 459 planned non-seed frames are within 20 cm, or 71.24%, counting unavailable estimates as misses. This makes the distinction between an RMSE target and a per-frame guarantee visible.

The nominal covariance publication threshold is uncalibrated. An estimated standard deviation below 0.20 m does not guarantee that the true error is below 0.20 m.

## Unresolved cases

The separate seeded 131-second stress window gives 18.48 cm position and 9.95 cm lateral RMSE but 72.0% coverage, below the 90% ranking requirement. It does not qualify.

The 73.9-second day recording produced 148/148 complete camera groups at 2 Hz. No three-camera visual fix passed: 145 geometry rejects and 3 single-camera results. Without a supplied initial pose, the disclosed visual-bootstrap variant never initialized. It published 0 poses. No labels are available in the supplied day package, so position/lateral RMSE are null. Day coverage uses 74 camera-time bins and is not an organizer ranking score.

The public portable package is a source portability release. Its synthetic tests validate specified software behaviors. They do not reproduce these real-data scores or establish independent-session accuracy.

## Timing

The earlier raw geometry profile measured 379.491 ms mean and 484.995 ms p95 per seven-camera group, plus 162.451 s offline setup, on a Ryzen AI 7 350 CPU using two numerical threads. This profile predates the full selected R16 output chain. Fusion/publication were separate cached passes. It is not R16 end-to-end latency, a live 10 Hz claim or a 4090 measurement.

## Public release boundary

All course and trajectory graphics in this repo are generated from original synthetic geometry. They are explanatory illustrations, not recordings, benchmark plots or demonstrations of measured precision. The GIF generator has no dataset inputs.

No customer deployment, production safety qualification, measured financial saving, winner comparison or universal 20 cm result is claimed. The next proof is a separately defined customer pilot.
