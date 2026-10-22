"""Causal output quality gate for the multi-camera metric PnP rig (pure Python, no NumPy).

Fixed criterion (frozen before later-lap evaluation, not swept):
* row zero only: a raw 'seed' with a finite [x, y, yaw] passes once as 'gate_seed';
* any other finite pose passes only if raw_status is exactly 'rig_joint' or
  'rig_joint_prior_resolved', diag['cameras_joint'] is a finite integer
  >= minimum_joint_cameras (default 3), and diag['joint_cameras'] lists exactly
  that many unique nonempty camera IDs ('+'-joined string as written by
  rig_geometry, or a list/tuple of strings);
* everything else returns None with an explicit 'gate_rejected_<reason>' status.

Output gate only: it never touches the rig, its hint, maps or filter. State is the
previous timestamp, the row index and counters; no smoothing, prediction, pose
holding or future inspection. Reads no files, reference poses or truth.
"""
from __future__ import annotations

import copy
import math
import operator
from collections import Counter

ACCEPTED_STATUSES = ('rig_joint', 'rig_joint_prior_resolved')
SEED_STATUS = 'seed'
DEFAULT_MINIMUM_JOINT_CAMERAS = 3
GATE_VERSION = 'quality_gate_v1'


def _is_bool(value):
    return isinstance(value, bool) or type(value).__name__ in ('bool_', 'bool8')


def _timestamp(value):
    if _is_bool(value):
        raise ValueError('timestamp_ns must be an integer, not bool')
    if isinstance(value, float):
        raise ValueError('timestamp_ns must be an integer, not float')
    try:
        return operator.index(value)
    except TypeError:
        raise ValueError(f'timestamp_ns must be an integer, got {type(value).__name__}') from None


def _pose(pose):
    """Return (values, reason): values is a 3-tuple of finite floats or None."""
    if pose is None:
        return None, 'missing_measurement'
    if isinstance(pose, (str, bytes)):
        return None, 'malformed_pose'
    try:
        values = tuple(float(v) for v in pose)
    except (TypeError, ValueError):
        return None, 'malformed_pose'
    if len(values) != 3:
        return None, 'malformed_pose'
    if not all(math.isfinite(v) for v in values):
        return None, 'nonfinite_pose'
    return values, None


def _camera_count(value):
    """Finite integer camera count (int, integral float, or integer-like scalar) or None."""
    if value is None or _is_bool(value) or isinstance(value, (str, bytes)):
        return None
    if isinstance(value, float):
        return int(value) if math.isfinite(value) and value.is_integer() else None
    try:
        return operator.index(value)
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return int(number) if math.isfinite(number) and number.is_integer() else None


def _camera_ids(value):
    """Return (ids, reason) for a '+'-joined string or list/tuple of nonempty unique strings."""
    if value is None:
        return None, 'joint_cameras_missing'
    if isinstance(value, bytes):
        value = value.decode('utf-8', 'replace')
    if isinstance(value, str):
        parts = value.split('+')
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        return None, 'joint_cameras_malformed'
    ids = []
    for part in parts:
        if isinstance(part, bytes):
            part = part.decode('utf-8', 'replace')
        if not isinstance(part, str) or not part.strip() or part != part.strip():
            return None, 'joint_cameras_malformed'
        ids.append(part)
    if len(set(ids)) != len(ids):
        return None, 'joint_cameras_duplicate'
    return ids, None


def _status_reason(status):
    if status.startswith('rig_single_camera_joint_unstable'):
        return 'status_joint_unstable'
    if status.startswith('rig_single_camera_joint_error'):
        return 'status_joint_error'
    if status.startswith('rig_single_camera'):
        return 'status_single_camera'
    return 'status_not_accepted_joint'


class Gate:
    """Streaming gate. step(timestamp_ns, pose_or_None, raw_status, diag) -> (pose|None, status, diag)."""

    def __init__(self, minimum_joint_cameras=DEFAULT_MINIMUM_JOINT_CAMERAS):
        minimum = _camera_count(minimum_joint_cameras)
        if minimum is None or minimum < 1:
            raise ValueError('minimum_joint_cameras must be an integer >= 1')
        self.minimum_joint_cameras = minimum
        self.previous_timestamp_ns = None
        self.rows = 0
        self.seed_passed = False
        self.counts = Counter()
        self.reasons = Counter()
        self.raw_statuses = Counter()
        self.accepted_camera_counts = Counter()
        self.first_timestamp_ns = None

    def criterion(self):
        return dict(version=GATE_VERSION, accepted_statuses=list(ACCEPTED_STATUSES),
                    minimum_joint_cameras=self.minimum_joint_cameras, seed_status=SEED_STATUS,
                    seed_rule='row zero only, finite pose, passes once',
                    joint_cameras_rule='unique nonempty IDs, count equal to cameras_joint',
                    feedback='none: output gate only, rig state untouched')

    def _reject(self, reason, timestamp, raw_status, out_diag):
        self.reasons[reason] += 1
        self.counts['rejected'] += 1
        out_diag.update(gate_accepted=0, gate_reason=reason)
        return None, 'gate_rejected_' + reason, out_diag

    def step(self, timestamp_ns, pose_or_none, raw_status, diag):
        timestamp = _timestamp(timestamp_ns)
        if self.previous_timestamp_ns is not None and timestamp <= self.previous_timestamp_ns:
            raise ValueError('timestamps must increase strictly; no sorting or repair is performed')
        row = self.rows
        self.rows += 1
        self.previous_timestamp_ns = timestamp
        if self.first_timestamp_ns is None:
            self.first_timestamp_ns = timestamp
        self.counts['rows'] += 1
        status_text = raw_status if isinstance(raw_status, str) else repr(raw_status)
        self.raw_statuses[status_text] += 1
        if isinstance(diag, dict):
            try:
                out_diag = copy.deepcopy(diag)
            except Exception:  # unusual objects: keep references rather than fail the row
                out_diag = dict(diag)
        else:
            out_diag = {}
        out_diag.update(gate_version=GATE_VERSION, gate_row=row, gate_raw_status=status_text,
                        gate_minimum_joint_cameras=self.minimum_joint_cameras)

        if not isinstance(raw_status, str):
            return self._reject('status_malformed', timestamp, status_text, out_diag)
        values, pose_reason = _pose(pose_or_none)

        if raw_status == SEED_STATUS:
            if row != 0 or self.seed_passed:
                return self._reject('seed_not_row_zero', timestamp, status_text, out_diag)
            if values is None:
                return self._reject('seed_' + pose_reason, timestamp, status_text, out_diag)
            self.seed_passed = True
            self.counts['seed_passed'] += 1
            out_diag.update(gate_accepted=1, gate_reason='first_seed')
            return values, 'gate_seed', out_diag

        if values is None:
            return self._reject(pose_reason, timestamp, status_text, out_diag)
        if raw_status not in ACCEPTED_STATUSES:
            return self._reject(_status_reason(raw_status), timestamp, status_text, out_diag)
        if not isinstance(diag, dict):
            return self._reject('diag_missing', timestamp, status_text, out_diag)
        if 'cameras_joint' not in diag:
            return self._reject('cameras_joint_missing', timestamp, status_text, out_diag)
        count = _camera_count(diag['cameras_joint'])
        if count is None:
            return self._reject('cameras_joint_not_integer', timestamp, status_text, out_diag)
        out_diag['gate_cameras_joint'] = count
        ids, id_reason = _camera_ids(diag.get('joint_cameras'))
        if ids is None:
            return self._reject(id_reason, timestamp, status_text, out_diag)
        if len(ids) != count:
            return self._reject('joint_cameras_count_mismatch', timestamp, status_text, out_diag)
        if count < self.minimum_joint_cameras:
            return self._reject('cameras_joint_below_minimum', timestamp, status_text, out_diag)
        self.counts['accepted_joint'] += 1
        self.accepted_camera_counts[count] += 1
        out_diag.update(gate_accepted=1, gate_reason='accepted_joint', gate_joint_camera_ids='+'.join(ids))
        return values, 'gate_accepted_joint', out_diag

    def summary(self):
        rows = self.counts['rows']
        passed = self.counts['accepted_joint'] + self.counts['seed_passed']
        return dict(criterion=self.criterion(), rows=rows, passed=passed,
                    accepted_joint=self.counts['accepted_joint'], seed_passed=self.counts['seed_passed'],
                    rejected=self.counts['rejected'], passed_fraction=(passed / rows) if rows else None,
                    rejection_reasons=dict(sorted(self.reasons.items())),
                    raw_status_counts=dict(sorted(self.raw_statuses.items())),
                    accepted_camera_counts={str(k): v for k, v in sorted(self.accepted_camera_counts.items())},
                    first_timestamp_ns=self.first_timestamp_ns, last_timestamp_ns=self.previous_timestamp_ns,
                    note='passed_fraction is over gated rows only; planned-frame and 1 s coverage '
                         'accounting (including missing rows) is the evaluator\'s')


def fixed_criterion():
    return Gate().criterion()
