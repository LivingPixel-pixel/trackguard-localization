"""Public streaming API. All imagery and calibration are caller supplied."""
from __future__ import annotations
import math
from dataclasses import dataclass
from . import rig_geometry
from .motion_bias_fusion import Fusion
from .spatial_reference_pairs import install_on_rig
from .quality_gate import _timestamp

PUBLICATION_POSITION_SD_M = 0.20

@dataclass(frozen=True)
class Estimate:
    timestamp_ns: int
    pose: tuple[float, float, float] | None
    status: str
    diagnostics: dict

class Localizer:
    """One continuous sequence, one optional first-row seed, no reset API.

    Construction fits an offline SIFT map from reference-only inputs.
    step consumes current images and a NEW motion arrival prefix only.
    body_offset_xy is a user-calibrated control-point-to-BODY lever arm.
    """
    def __init__(self, references: dict, *, body_offset_xy=(0.0, 0.0)):
        self._rig = rig_geometry.fit(references)
        install_on_rig(self._rig)
        self._fusion = Fusion(body_offset_xy=body_offset_xy)
        self._previous_t = self._previous_log = None

    def step(self, timestamp_ns, image_log_ns, images, member_timestamps_ns,
             new_motion_samples=(), *, seed=None):
        t, log = _timestamp(timestamp_ns), _timestamp(image_log_ns)
        if self._previous_t is not None and t <= self._previous_t:
            raise ValueError('bundle timestamps must increase strictly')
        if self._previous_log is not None and log < self._previous_log:
            raise ValueError('image log barriers must be nondecreasing')
        if not isinstance(new_motion_samples, (list, tuple)):
            raise ValueError('new_motion_samples must be a list or tuple')
        if seed is not None and self._previous_t is not None:
            raise ValueError('seed allowed only on the first row; start a new Localizer for a new sequence')
        if seed is not None:
            from .quality_gate import _pose
            if _pose(seed)[0] is None:
                raise ValueError('seed must be finite [x,y,yaw]')
        # Validate scalar member times before either streaming component advances.
        for stamp in (member_timestamps_ns or {}).values():
            _timestamp(stamp)
        raw, status, diag = rig_geometry.predict(self._rig, images, t, member_timestamps_ns, seed)
        pose, fused_status, diag = self._fusion.step(t, log, new_motion_samples, raw, status, diag)
        self._previous_t, self._previous_log = t, log
        # Output-only R16 nominal uncertainty rule. The internal state continues.
        sd = diag.get('fusion_pos_sd_m')
        publish = pose is not None and (fused_status == 'fusion_seed' or
                  (sd is not None and math.isfinite(sd) and sd <= PUBLICATION_POSITION_SD_M))
        diag.update(publication_threshold_m=PUBLICATION_POSITION_SD_M,
                    publication_accepted=int(publish), raw_geometry_status=status,
                    fusion_status=fused_status)
        if pose is not None and not publish:
            fused_status = 'unavailable_nominal_uncertainty'
        return Estimate(t, tuple(pose) if publish else None, fused_status, diag)

    def summary(self):
        return dict(geometry=rig_geometry.summary(self._rig), fusion=self._fusion.summary(),
                    publication_threshold_m=PUBLICATION_POSITION_SD_M,
                    notice='Portable refactor, not a measured replay or exact R16 reproduction')
