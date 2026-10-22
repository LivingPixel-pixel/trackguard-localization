# Release checks

## Portable software

The existing compatible runtime executed 13 synthetic tests in 1.433 seconds. Coverage includes BODY/camera transforms, calibration scaling, member timestamps, spatial partners, camera counts, initial-seed integrity, future-motion prefix invariance, stale-control loss, motion/lever-arm propagation, recovery and visual outlier rejection.

The synthetic CLI sent generated pixels through actual SIFT extraction, map geometry, three-camera BODY solving, causal fusion and publication. It produced four fused visual fixes after one seed. An isolated wheel import and CLI run also passed. These checks establish software behavior on synthetic inputs, not the private benchmark scores.

## Dashboard and assets

The measured replay retains all 460 sealed development rows, 49 unavailable outputs and one unscored seed. The exporter checked input pins, exact timestamp alignment and existing position/lateral RMSE within `1e-9`. New yaw and longitudinal metrics use the same scored poses. No inference was rerun.

Both real-track GIFs contain 72 sampled frames over 7.2 seconds. Every saved frame decoded successfully. The interactive replay uses all rows, with synchronized position, yaw and directional error charts, a discrete scrubber and 10-second rolling metrics. Missing errors stay null. Reference truth is evaluation-only.

Browser checks at 1440 and 390 pixels found no page overflow. Scrubbing covered the seed, unavailable rows, the lap boundary and the final frame; current errors and all three cursors agreed. At 32x, playback advanced and remained stable after pausing. Aggregate window changes left the replay frame unchanged; day RMSE stayed unavailable and stress coverage stayed 72%. An independent review recomputed public row aggregates within `4.79e-10`, checked rolling metrics and gaps, and found no P1/P2 blockers.

## Slides and release boundary

All six PowerPoint slides and PDF pages were rendered for inspection. Automated export checks reported zero text overflow, correct metric values, editable text/tables and no external relationships or private absolute file paths. Browser slides have six-page navigation and no remote asset dependency.

`python scripts/check_release.py` verifies replay/aggregate parity, seed and unavailable membership, directional-error consistency, denominators, required files, local links, slide count and the public data boundary. The repository CI repeats the software and release checks. CI status is reported by GitHub, rather than inferred from the local run.

The original same-session measurements remain documented in `docs/EVIDENCE.md`. Exact R16 inference reproduction through the portable package, independent-session 20 cm accuracy, GPU timing and live vehicle deployment remain unverified.
