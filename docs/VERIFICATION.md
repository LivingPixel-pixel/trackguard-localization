# Release checks

## Portable software

The existing compatible runtime executed 13 synthetic tests in 1.433 seconds. Coverage includes BODY/camera transforms, calibration scaling, member timestamps, spatial partners, camera counts, initial-seed integrity, future-motion prefix invariance, stale-control loss, motion/lever-arm propagation, recovery and visual outlier rejection.

The synthetic CLI sent generated pixels through actual SIFT extraction, map geometry, three-camera BODY solving, causal fusion and publication. It produced four fused visual fixes after one seed. An isolated wheel import and CLI run also passed. These checks establish software behavior on synthetic inputs, not the private benchmark scores.

## Dashboard and assets

Browser checks exercised all five evaluation windows, including the null-RMSE day state and the failed stress coverage state. The JSON source and embedded offline snapshot match. Animation pause/play switches between the GIF and static poster. Desktop and 390-pixel layouts showed no global horizontal overflow. Reduced-motion handling and keyboard controls are implemented.

The synthetic GIF contains 80 frames and an explicit unavailable interval. A smaller 40-frame version supports the website card. Neither reads partner data.

## Slides and release boundary

All six PowerPoint slides and PDF pages were rendered for inspection. Automated export checks reported zero text overflow, correct metric values, editable text/tables and no external relationships or private absolute file paths. Browser slides have six-page navigation and no remote asset dependency.

`python scripts/check_release.py` verifies aggregate parity, denominators, required files, local links, slide count and the public data boundary. The repository CI repeats the software and release checks. CI status is reported by GitHub, rather than inferred from the local run.

The original same-session measurements remain documented in `docs/EVIDENCE.md`. A private recording replay, independent-session 20 cm result, GPU timing and live vehicle deployment are outside this release's verification.
