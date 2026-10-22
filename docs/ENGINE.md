# Portable authored localization engine

TrackGuard ships executable SIFT reference mapping, shared BODY SE3 geometry, a three-camera quality gate and causal six-state motion fusion. It does not ship partner assets, a learned feature backend, a private adapter or a recording decoder.

This is a portability refactor, **not a measured replay and not a turnkey exact R16 reproduction**. The published aggregate R16 metrics belong to the original prepared campaign. Synthetic tests below do not establish 20 cm accuracy, coverage on real recordings, calibrated confidence or live latency.

## Run

From the project root, with Python 3.10 or later:

```powershell
$env:OPENBLAS_NUM_THREADS = '2'
$env:OMP_NUM_THREADS = '2'
$env:MKL_NUM_THREADS = '2'
python -m pip install .
python -m trackguard synthetic
python -m unittest discover -s tests -v
```

Without installing into an existing compatible environment:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m trackguard synthetic
python -m unittest discover -s tests -v
```

`trackguard synthetic` is the installed console entry point. It generates a seeded random texture, renders three calibrated cameras independently, fits nine reference images, then streams one seed and four current camera groups with permitted scalar controls. It prints JSON explicitly marked synthetic. No downloads or data files are needed.

OpenCV threads are capped at two by fitting. Set the BLAS variables before starting Python to cap NumPy numerical threads. Offline map preparation scales with the supplied reference count; spatial partner selection is O(N squared). The historical feature-byte cap is a cap calculation with a per-image feature floor, not a hard process-memory guarantee. Bound your private reference set and process resources externally.

## Python API and precise input contract

```python
from trackguard import Localizer

engine = Localizer(references, body_offset_xy=(0.0, 0.0))
result = engine.step(
    timestamp_ns=t,
    image_log_ns=arrival_barrier,
    images=current_images,
    member_timestamps_ns=exposure_times,
    new_motion_samples=new_arrivals,
    seed=(x0, y0, yaw0),  # first row only; omit thereafter
)
print(result.timestamp_ns, result.pose, result.status)
```

`references` is a mapping from camera ID to a dictionary:

| Field | Required value |
|---|---|
| `images` | Sequence of grayscale `numpy.uint8[H,W]` arrays, all the same shape for that camera |
| `img_paths` | Alternative to `images`: caller-owned readable image paths, decoded grayscale at their actual size |
| `T_WB` | Float array `[N,4,4]`, metric proper rigid transforms mapping BODY coordinates into world coordinates; one per reference image |
| `calibration.K` | Float `[3,3]` pinhole intrinsics at `original_size` |
| `calibration.D` | OpenCV pinhole distortion coefficients, or an empty sequence for no distortion |
| `calibration.original_size` | Explicit positive `[width,height]` of the calibration image |
| `calibration.T_base_camera` | Proper rigid `[4,4]`, optical CAMERA into BODY, also accepted as `T_bc` |

`images` and `img_paths` are alternatives. There is no implicit resize to the campaign image dimensions. K is rescaled once to the supplied per-camera working size, D stays unchanged. Query images must match their own camera's reference shape. Different cameras may have different intrinsics, extrinsics and shapes. Camera IDs must be nonempty, unique strings without `+` or outer whitespace.

Reference poses and imagery are offline permitted map inputs. Reference validity and train/evaluation separation are the caller's responsibility. The package cannot infer licensing, time splits, map provenance or whether poses were derived from forbidden query labels. It accepts no query ground-truth stream. Invalid reference rigid transforms are excluded; at least one usable image must remain per camera.

A `step` consumes:

- `timestamp_ns`: integer bundle output/exposure clock, strictly increasing. Normally the maximum selected member exposure. Boolean and floating timestamps are rejected.
- `image_log_ns`: integer arrival barrier in the telemetry arrival clock, nondecreasing.
- `images`: `{camera_id: uint8[H,W]}` for this group. Missing members are unavailable.
- `member_timestamps_ns`: `{camera_id: integer exposure_ns}`. A used member must be at or before output time and at most 1,000,000 ns old. Future and stale members are dropped individually before feature extraction. No motion compensation is applied.
- `new_motion_samples`: list/tuple of NEW records, in `(log_ns,seq)` arrival order, each with exactly `source_ns`, `log_ns`, `seq`, `v_mps`, `wz_radps`. The first three are integers; the last two are finite numbers. No duplicate keys or additional fields. Future source or arrival times, repeated/out-of-order arrivals, absolute speed above 60 m/s and absolute yaw rate above 2 rad/s are rejected and counted. Future records are discarded, not queued. Deliver only the arrival prefix available at this row's barrier. Do not resend the full telemetry history.
- `seed`: at most one finite `[x,y,yaw]`, on row zero only. This retained fusion requires that first seed to initialize. Without it, visual diagnostics can run but fused outputs remain uninitialized. There is no later external seed and no reset method. Create a new Localizer only for a genuinely new sequence and account for its initialization separately.

World distances are metres, angles radians. BODY uses +x forward, +y left, +z up. Optical axes follow OpenCV: +x right, +y down, +z forward. Signed `v_mps` is forward speed at the effective control point; `wz_radps` is counter-clockwise yaw rate about +z. `body_offset_xy=r` is BODY origin relative to control point in BODY axes: `p_B = p_C + R(yaw) r`. Zero is an explicit generic default, not the original FIT-calibrated lever arm. Supply your own permitted calibration. Exposure/source clocks and arrival/barrier clocks must be synchronized by your adapter.

`Estimate.pose` is a tuple `[x,y,yaw]` or `None`. Keep every row, including unavailable rows, for coverage accounting. A pose can be a motion prediction rather than a visual measurement. `diagnostics` includes raw geometry status, member rejection reasons, final joint camera IDs, gate approval, fusion stage, NIS, control rejection counts and nominal position SD. `summary()` gives configuration and counters. Diagnostics are caller-owned, potentially sensitive and not automatically persisted. No frame or prediction writer is included. Integrating private file formats or recording replay is an application task.

Low-level `Gate` and `Fusion` are public for existing adapters. `Fusion.step(t, log, new_controls, raw_pose, raw_status, raw_diagnostics)` expects raw geometry diagnostics, not truth masquerading as geometry. Its core can emit up to a 2.0 m nominal position SD. `Localizer` adds the separate R16-style 0.20 m output-only publication rule, allowing the row-zero seed through. That output rule never feeds back into geometry or fusion state. The seed's nominal radial SD is about 0.212 m and is explicitly exempt. Nominal SD is `sqrt(Pxx + Pyy)` from heuristic covariance, not an error bound.

## Retained numerical mechanism

The numerical constants and formulas of the retained SIFT/rig/quality/motion core are unchanged. The curated public wrapper fixes the SIFT backend and spatial pairs; it does not expose threshold sweeps.

- SIFT: 1,000 features before the retained byte-budget calculation, contrast 0.025, three octave layers; static mask top 8 pixels, bottom 90%, sides 5 pixels. Descriptors stored as uint8 and converted to float32 for L2 matching. Unique reference matches with pair/query ratios 0.76/0.80.
- Spatial offline pairs: 3 to 15 m, target 7 m, heading separation below 12 degrees; second partner prefers opposite longitudinal displacement, then the next candidate. No query observations enter pairing.
- Triangulation: raw distorted pixels undistorted only for triangulation, depth strictly 2 to 180 m, parallax above 0.7 degrees, maximum pair reprojection below 2.5 pixels. Local origin improves numerical conditioning.
- PnP: fixed RNG seed 12345, EPNP RANSAC 80 iterations, 4 pixel threshold, 0.99 confidence, at least eight inliers, LM refinement. Accepted median reprojection at most 2.5 pixels; reference distance at most 30 m, relative height at most 2 m, up difference at most 12 degrees and yaw at most 35 degrees.
- Shared BODY consensus: candidates agree within 2 m and 5 degrees. Comparable incompatible hypotheses with equal camera support are rejected unless resolved by the causal past-pose prior. Shared BODY reprojection is `X_C = R_BC^T (R_WB^T (X_W-p_WB)-t_BC)`. Robust LM uses the retained Huber weights, camera balance and inlier reselection. A single-camera fallback cannot pass the output quality gate.
- Quality: only `rig_joint` or `rig_joint_prior_resolved`, at least three distinct final joint camera IDs matching `cameras_joint`. One finite row-zero seed is the only exception. Gate rejection does not reset the raw rig hint.
- Motion state: `[x,y,yaw,b_forward,b_lateral,b_yaw_rate]`. Constant twist at the control point uses a stable sinc arc, then transforms back to BODY. Biases are additive random walks; state Jacobians use central differences. Joseph covariance update, 3D NIS gate 16.26623619623813. Visual floors are 0.15 m and 0.2 degrees; control noise 0.5 m/s and 0.02 rad/s. Initial bias SD `[1,1,0.02]`, random-walk SD `[0.05,0.05,0.002]` per sqrt second, broad bias bounds `[10,10,0.5]`.
- Controls must cover each integration segment with maximum age 0.20 s. Missing/stale controls lose tracking. Recovery requires two camera-approved consistent fixes no more than 0.65 s apart. When controls exist, motion NIS must pass; when unavailable, the retained recovery falls back to broad physical consistency. Recovery resets bias estimates, not an external truth seed. Buffers are capped at 4,096 controls.
- Publication: retained core threshold 2.0 m, wrapper output-only threshold 0.20 m, no smoothing, future images, map snapping or rewriting prior rows.

The exact policy dictionaries and all other retained defaults are inspectable in `sift_geometry.DEFAULT_CONFIG`, `rig_geometry.DEFAULT_CONFIG`, `quality_gate.fixed_criterion()` and `motion_bias_fusion.fixed_policy()`.

## Portability changes and exclusions

Package imports replace all dynamic source-file loaders. Removed learned/ORB backend branches, private adapter integration, prepared-cache ingestion, refined-engine conversion, optional legacy online Kalman wrapper, reset helpers and experimental entry points. The allowed `causal_kalman.py` was inspected but is not bundled: the retained six-state motion fusion supplies the causal filter used here. SIFT mapping and the joint BODY solver are actual authored algorithms, not placeholders.

Reference loading now preserves caller resolution and requires calibration size. It rejects mixed reference shapes. Integer member timestamps are validated instead of silently truncated. Camera IDs come from the supplied references. The localizer attaches spatial partners before any query, wires the actual quality/fusion stages and applies the documented output-only uncertainty gate. It supplies no original prepared map, learned effective lever arm, query recording adapter or fit/query split receipts. Those differences prevent an exact R16 reproduction claim.

A source AST comparison found 9 unchanged top-level SIFT functions, 20 unchanged rig functions and all 11 retained top-level motion functions. Rig differences are fitting/emission/package wiring and timestamp validation; fusion class changes are only gate import construction and removal of source-path reporting. The gate has unchanged parsed Python syntax; file encoding and line endings were normalized. This supports provenance, not numerical replay equivalence.

## Executed verification

Executed on Python 3.12.14, NumPy 2.5.3, `opencv-python-headless` 4.14.0.94 (`cv2.__version__` 4.14.0), setuptools 78.1.0. Python package constraints are compatibility ranges, not a lockfile. No fresh dependency installation was performed. Numerical thread variables were set to two; OpenCV reported two threads.

Commands actually executed in the existing compatible environment, from this project root:

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
python -m trackguard synthetic
python -m unittest discover -s tests -v
```

Final test result: **13 tests passed in 1.433 seconds** on this runtime.

The synthetic CLI produced one seed and four `fusion_visual_corrected` outputs, all four from three-camera `rig_joint` geometry. Tests exercise independent 3D projection/PnP with a rotated translated camera and large world origin, shared BODY projection, calibration scaling/reflection rejection, non-temporal spatial partners, camera-count/ID integrity, single seed/no reseed, future-member rejection, prefix invariance under injected future telemetry, stale-control loss, closed-form turn/lever-arm motion, two-fix recovery without external reseeding, visual NIS outlier rejection and generated pixels through actual SIFT mapping/joint solve/fusion/publication.

A wheel was built without network using `setuptools.build_meta.build_wheel(tempdir)`, extracted to a temporary directory, then imported and ran the synthetic CLI with `python -I -B` outside the checkout. Both build and isolated wheel run exited 0. This proves package import completeness with installed NumPy/OpenCV, not install success on another operating system or performance on private recordings. No real recording, model inference, training, campaign-budget mutation or external write was performed.

Source provenance (campaign-relative paths, SHA-256 of originals):

- `work/r2/precision_geometry.py`: `30909ca7308753c84660641a592cd3f1edeba743f2298c91bd2e513126f848eb`
- `work/r2/sift_geometry.py`: `95d49462d812672cbe9f8228f653ccd05462a9195f365fe49fcca39fe8e9f57e`
- `work/r4/rig_geometry.py`: `80959013be02da8996f9ddea8f3da08144e43e5c78fe45e7d4b2093c5893d67e`
- `work/r6/quality_gate.py`: `d1e68174b6fe8512676b0c25efb9dc1465b27046628fec71157e138dab98433f`
- `src/motion_bias_fusion.py`: `ef4740f1f9aec5d9815a1892a6e13f8e8d21bbd08b868b1ce8751e3154b4f585`
- `src/spatial_reference_pairs.py`: `d336d2607ea373c34ace69ba91749b9cdfac44942ba3acd6cf8f80e6ee8140f8`
