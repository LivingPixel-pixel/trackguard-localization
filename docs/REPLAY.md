# Measured R16 replay

`data/replay.json` implements [REPLAY_CONTRACT.md](REPLAY_CONTRACT.md): all 460 planned rows, 411 published estimates, 49 unavailable estimates and one unscored initial seed. This is consumed same-session development, with no new inference or lap 7 reseed.

The reference trace and moving reference marker use recorded evaluator truth after sealed inference. They never enter inference. Public output contains integer display pixels, relative elapsed seconds and derived errors. World poses, absolute timestamps, labels, calibration and the coordinate transform remain local. The supplied map's four track/pitlane Path topics were decoded in frame `map`; selected payload was 1,190,272 bytes, below the 8 MiB limit. No images or raw recordings were decoded.

## Integration

- `data/replay.json`: schema `trackguard-measured-replay-v1`, `metadata` and 460 `rows`.
- `assets/track-replay-background.png`: actual track bounds and evaluator reference trace, 960 x 640, 8,695 bytes.
- `assets/track-replay.gif`: synchronized real track, current position/yaw/directional errors, position/yaw charts and shared cursor, 960 x 540, 1,268,056 bytes.
- `assets/track-replay-card.gif`: same measured replay at 640 x 360, 1,247,876 bytes.
- `assets/track-replay-poster.png`: measured replay at 116.5 seconds, 960 x 540, 63,643 bytes.
- `data/metrics.json`: existing numeric values preserved; yaw/longitudinal RMSE and error tails appended to `later_laps`, `lap6`, `lap7`. Yaw tail field: `absolute_yaw_p95_deg`.

Rows contain `frame`, `t_s`, `lap`, `published`, `seed`, `reference_px`, `estimate_px`, four derived errors, `rolling_position_rmse_m` and `rolling_frame_publication_percent`. Errors and estimate pixels are null when unavailable; seed errors are null. No estimate interpolation or line across a missing row. The trailing rolling interval is `(current time - 10s, current time]`; accuracy excludes the seed and publication includes every planned row. Rolling RMSE may remain available during a missing current estimate because preceding eligible observations remain in the window.

Use the complete JSON for interactive playback, discrete scrubbing and synchronized charts. GIFs contain 72 sampled frames, including the seed and an unavailable estimate, over 7.2 seconds. Average acceleration is 31.8754x over 229.502952778 recorded seconds. Sampling uses discrete observations and slightly unequal recorded intervals; it does not interpolate. Both chart cursors and current values always refer to the same observation. The overview cannot resolve centimetre accuracy; charts carry that detail. Follow the contract's paused default for reduced-motion users.

## Measured accuracy

All values below exclude only the global first seed and use finite eligible observations. All existing position/lateral RMSE values matched sealed evaluator metrics within `1e-9` before display rounding.

| Slice | Scored | Position RMSE m | Lateral RMSE m | Longitudinal RMSE m | Yaw RMSE deg | Absolute yaw p95 deg |
|---|---:|---:|---:|---:|---:|---:|
| Combined | 410 | 0.174775333 | 0.114219528 | 0.132288761 | 0.106949680 | 0.210447250 |
| Lap 6 | 216 | 0.153388610 | 0.085931583 | 0.127058368 | 0.102998207 | 0.195519707 |
| Lap 7 | 194 | 0.195858785 | 0.139104389 | 0.137879050 | 0.111184154 | 0.224185934 |

Signed lateral and longitudinal errors project estimate-minus-reference displacement across/along the reference heading. Signed yaw wraps estimate-minus-reference to `[-180, 180]` degrees. RMSE and linear-interpolated p95 tails are computed at full precision. Public per-row errors round to nine decimal places; relative seconds round to six. Occupied one-second coverage is the existing organizer measure, distinct from 89.35% frame publication. Stress and day aggregate cases have no trajectory in this replay.

## Build and evidence

`scripts/build_measured_replay.py` is a generic evaluator-only CLI. It needs private sealed predictions, both completion receipts, existing aggregate and lap metrics, the timestamp query bundle, evaluator label arrays with eligibility, and an indexed map MCAP containing the four permitted ROS2 Path topics. It does not supply those private inputs or claim portable exact R16 reproduction. Dependencies used: Python 3.12, NumPy 2.5.3, Pillow 12.3, existing `mcap` and `mcap_ros2`. No installation was needed.

```powershell
& $Python -I -B scripts/build_measured_replay.py `
  --predictions $Predictions --prediction-sha256 $PredictionHash `
  --inference-receipt $InferenceReceipt --inference-complete $InferenceComplete `
  --scored-metrics $ScoredMetrics --scored-laps $ScoredLaps `
  --query $Query --labels $Labels --labels-valid $LabelEligibility `
  --map $MapMcap --output $PublicOutput --private-receipt $NewPrivateReceipt
```

The export completed under a 512 MiB, two-thread guard in 5.687 seconds. Input hashes, sealed receipts and timestamp alignment were checked. All 72 saved GIF frames decoded successfully with a total duration of 7,200 ms. The poster and sampled GIF frames were inspected. Private audit receipts remain local. A later prose/field-name cleanup changed no numerical values or rendered assets.
