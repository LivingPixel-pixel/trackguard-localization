# Authorship and dependencies

TrackGuard is an authored research prototype developed during and after the SchubKI camera-localization challenge. The portable source adapts the team's local geometry and causal fusion implementation. Code provenance and the portability boundary are described in `docs/ENGINE.md`.

NumPy, OpenCV, Pillow and presentation-generation dependencies retain their own licenses. They are dependencies, not vendored source. The repository license covers the authored code, documentation and original explanatory graphics.

The authorized public replay includes rendered track graphics, rounded display coordinates and derived error series. It grants no license or access to the underlying partner dataset. Raw recordings, world-coordinate trajectories, calibration, labels, weights and caches are not distributed or licensed by this repository.
