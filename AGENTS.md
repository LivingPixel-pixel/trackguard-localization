# TrackGuard delivery

- No em dashes. Keep prose concrete and concise.
- Publish authored source and the human-requested measured track replay and changing error metrics.
- The real replay may contain rendered track graphics, rounded display-pixel markers, relative elapsed times and derived error values. No world-coordinate poses, raw labels, calibration assets, recordings, camera images, descriptors, caches, credentials or private paths.
- Label real recorded replay and synthetic software examples accurately. Evaluation-only reference data must never enter inference.
- Preserve same-session development, stress coverage failure and day initialization failure distinctions.
- Only the coordinator performs Git remote writes or sends messages to other conversations.
- Workers own only the files assigned in their task. Do not edit other files or spawn workers.
