# TrackGuard delivery

- No em dashes. Keep prose concrete and concise.
- Publish only authored source, synthetic graphics and aggregate metrics explicitly approved for this release.
- No partner images, recordings, maps, per-frame poses, labels, descriptors, caches, credentials, private logs or machine-specific paths.
- Never describe a synthetic visualization as a measured trajectory.
- Preserve same-session development, stress coverage failure and day initialization failure distinctions.
- Only the coordinator performs Git remote writes or sends messages to other conversations.
- Workers own only the files assigned in their task. Do not edit other files or spawn workers.
