"""Causal bias-aware SE(2) telemetry-motion + visual EKF (NumPy only).

Portable package refactor of the authored campaign fusion. Per row: per image the caller supplies the bundle exposure time, its log-arrival
barrier, the NEW telemetry arrival prefix ({source_ns, log_ns, seq, v_mps, wz_radps})
and the cached raw rig visual pose/status/diag. The unchanged camera gate
quality_gate.py (>=3 unique final joint cameras, one row-zero seed, strict
timestamps) is imported from this package and called exactly once per row. Telemetry
admission, control coverage (age <= 0.20 s), buffer, NIS gate, publication and
two-fix recovery rules are copied from v1.

New: six-state [x, y, yaw, b_forward, b_lateral, b_yaw_rate]. x, y, yaw is the BODY
pose. The effective control point C moves with constant twist using body-frame
velocity (v + b_forward, b_lateral) and yaw rate (w + b_yaw_rate); the BODY origin
is recovered with the fixed lever arm r = body_offset_xy:
    p_B = p_C + R(yaw) r   =>   D_body = D_control + (R(theta) - I) r  (start body frame),
the convention of root's FIT-derived effective lever arm. Biases are random-walk
states learned only from past camera-approved visual updates; they reset to zero
with their initial uncertainty at every recovery. No labels, files, future images,
smoothing, map snapping or rewriting of earlier outputs.
"""
from __future__ import annotations

import bisect
import math
import operator
import time
from collections import Counter

import numpy as np
from . import quality_gate

VERSION = 'motion_bias_fusion_v1'
VISUAL_POSITION_STD_M = 0.15            # unmeasured heuristic noise floor (unchanged from v1)
VISUAL_YAW_STD_RAD = math.radians(0.2)  # unmeasured heuristic noise floor (unchanged from v1)
CONTROL_SPEED_STD_MPS = 0.5             # white control error, constant within one image interval
CONTROL_YAW_RATE_STD_RADPS = 0.02
BIAS_INITIAL_STD = (1.0, 1.0, 0.02)     # b_forward m/s, b_lateral m/s, b_yaw_rate rad/s
BIAS_RANDOM_WALK = (0.05, 0.05, 0.002)  # per sqrt(s)
BIAS_BOUND = (10.0, 10.0, 0.5)          # broad sanity bounds: an update beyond them is rejected explicitly
MAX_CONTROL_AGE_NS = 200_000_000
NIS_GATE_3D = 16.26623619623813         # chi-square, 3 dof, p = 0.999
PUBLISH_MAX_POSITION_SD_M = 2.0         # sqrt(Pxx + Pyy)
RECOVERY_MAX_GAP_NS = 650_000_000
BROAD_SPEED_MPS = 60.0
BROAD_POSITION_MARGIN_M = 3.0
BROAD_YAW_RATE_RADPS = 2.0
BROAD_YAW_MARGIN_RAD = math.radians(10.0)
CONTROL_MAX_SPEED_MPS = 60.0
CONTROL_MAX_YAW_RATE_RADPS = 2.0
CONTROL_BUFFER_MAX = 4096
SAMPLE_KEYS = frozenset(('source_ns', 'log_ns', 'seq', 'v_mps', 'wz_radps'))
_JAC_EPS = np.array([1e-4, 1e-4, 1e-6, 1e-4, 1e-4, 1e-6])
ASSUMPTIONS = (
    'v_mps: signed forward speed of the effective control point along body +x (literal sign, FIT witness by root)',
    'wz_radps: counter-clockwise yaw rate about +z up (literal sign, FIT witness by root)',
    'body_offset_xy r: BODY origin relative to the control point in body axes, p_B = p_C + R(yaw) r; '
    'a learned effective calibration from one FIT turn, not proof of publisher semantics',
    'b_forward/b_lateral/b_yaw_rate: slowly varying additive control-point biases (scale error, slip, '
    'reference-point residual) modelled as independent random walks; a heuristic, not a vehicle model',
    'source_ns shares the image exposure clock and log_ns the image log-barrier clock (unverified)',
    'controls piecewise constant from source time to the next record by source time; planar motion',
    'white control error constant within one image interval, independent across intervals and between v and w',
)
_INF = math.inf

R_VISUAL = np.diag([VISUAL_POSITION_STD_M ** 2, VISUAL_POSITION_STD_M ** 2, VISUAL_YAW_STD_RAD ** 2])
Q_CONTROL = np.diag([CONTROL_SPEED_STD_MPS ** 2, CONTROL_YAW_RATE_STD_RADPS ** 2])
Q_BIAS_RATE = np.diag(np.square(BIAS_RANDOM_WALK))
P0_BIAS = np.diag(np.square(BIAS_INITIAL_STD))
H = np.hstack([np.eye(3), np.zeros((3, 3))])
I6 = np.eye(6)


def _wrap(a):
    return (a + math.pi) % (2.0 * math.pi) - math.pi


def _is_bool(value):
    return isinstance(value, bool) or type(value).__name__ in ('bool_', 'bool8')


def _int(value, name):
    if _is_bool(value) or isinstance(value, float):
        raise ValueError(f'{name} must be an integer')
    try:
        return int(operator.index(value))
    except TypeError:
        raise ValueError(f'{name} must be an integer') from None


def _sinc(u):
    if abs(u) < 1e-4:
        u2 = u * u
        return 1.0 - u2 / 6.0 + u2 * u2 / 120.0
    return math.sin(u) / u


# ---------------------------------------------------------------------------
# six-state transition: constant twist of the control point, lever arm to BODY

def transition(s, v, w, dt_ns, r):
    """One constant-control segment. s = [x, y, yaw, bf, bl, bw] (BODY pose + biases)."""
    x, y, yaw, bf, bl, bw = (float(q) for q in s)
    c, sn = math.cos(yaw), math.sin(yaw)
    cx = x - (c * r[0] - sn * r[1])          # control point p_C = p_B - R(yaw) r
    cy = y - (sn * r[0] + c * r[1])
    dt = dt_ns * 1e-9
    half = 0.5 * (w + bw) * dt
    k = dt * _sinc(half)                      # V(a) = sinc(a/2) R(a/2): stable two-component arc
    phi = yaw + half
    ux, uy = v + bf, bl
    cp, sp = math.cos(phi), math.sin(phi)
    cx += k * (ux * cp - uy * sp)
    cy += k * (ux * sp + uy * cp)
    yaw2 = yaw + 2.0 * half
    c2, s2 = math.cos(yaw2), math.sin(yaw2)
    return np.array([cx + c2 * r[0] - s2 * r[1], cy + s2 * r[0] + c2 * r[1], _wrap(yaw2), bf, bl, bw])


def _jacobian(s, v, w, dt_ns, r):
    """Central-difference 6x6 state Jacobian (yaw differences wrapped)."""
    F = np.empty((6, 6))
    for j in range(6):
        p, m = np.array(s, float), np.array(s, float)
        p[j] += _JAC_EPS[j]
        m[j] -= _JAC_EPS[j]
        d = transition(p, v, w, dt_ns, r) - transition(m, v, w, dt_ns, r)
        d[2] = _wrap(d[2])
        F[:, j] = d / (2.0 * _JAC_EPS[j])
    return F


def _initial(z):
    s = np.array([float(z[0]), float(z[1]), _wrap(float(z[2])), 0.0, 0.0, 0.0])
    P = np.zeros((6, 6))
    P[:3, :3] = R_VISUAL
    P[3:, 3:] = P0_BIAS
    return s, P


def _pos_sd(P):
    return math.sqrt(max(float(P[0, 0] + P[1, 1]), 0.0))


def _state_diag(prefix, s, P):
    c, sn = math.cos(s[2]), math.sin(s[2])
    lon = c * c * P[0, 0] + 2 * c * sn * P[0, 1] + sn * sn * P[1, 1]
    lat = sn * sn * P[0, 0] - 2 * c * sn * P[0, 1] + c * c * P[1, 1]
    sd = np.sqrt(np.clip(np.diag(P), 0.0, None))
    return {prefix + 'x': float(s[0]), prefix + 'y': float(s[1]), prefix + 'yaw': float(s[2]),
            prefix + 'pos_sd_m': _pos_sd(P), prefix + 'lon_sd_m': math.sqrt(max(float(lon), 0.0)),
            prefix + 'lat_sd_m': math.sqrt(max(float(lat), 0.0)), prefix + 'yaw_sd_deg': math.degrees(sd[2]),
            prefix + 'bias_forward_mps': float(s[3]), prefix + 'bias_lateral_mps': float(s[4]),
            prefix + 'bias_yaw_rate_degps': math.degrees(float(s[5])),
            prefix + 'bias_forward_sd_mps': float(sd[3]), prefix + 'bias_lateral_sd_mps': float(sd[4]),
            prefix + 'bias_yaw_rate_sd_degps': math.degrees(float(sd[5]))}


def _broad(a, b):
    """Broad physical pair check from earlier (t, pose) a to later b (same bounds as the R8 gate)."""
    dt = (b[0] - a[0]) * 1e-9
    disp = math.hypot(b[1][0] - a[1][0], b[1][1] - a[1][1])
    dyaw = abs(_wrap(b[1][2] - a[1][2]))
    d_lim = BROAD_SPEED_MPS * dt + BROAD_POSITION_MARGIN_M
    y_lim = BROAD_YAW_RATE_RADPS * dt + BROAD_YAW_MARGIN_RAD
    metrics = dict(pair_dt_s=dt, displacement_m=disp, displacement_limit_m=d_lim,
                   yaw_change_deg=math.degrees(dyaw), yaw_change_limit_deg=math.degrees(y_lim))
    reason = 'physical_displacement' if disp > d_lim else 'physical_yaw' if dyaw > y_lim else None
    return reason, metrics





# ---------------------------------------------------------------------------
# streaming bias-aware fusion

class Fusion:
    """step(timestamp_ns, image_log_ns, new_motion_samples, visual_pose_or_None, visual_status, visual_diag)
    -> (pose | None, status, diag); summary()."""

    def __init__(self, body_offset_xy=(0.0, 0.0)):
        try:
            r = tuple(float(v) for v in body_offset_xy)
        except (TypeError, ValueError):
            raise ValueError('body_offset_xy must be two finite numbers') from None
        if len(r) != 2 or not all(math.isfinite(v) for v in r):
            raise ValueError('body_offset_xy must be two finite numbers')
        self.r = r
        self.gate = quality_gate.Gate()
        self.state = None          # (t_ns, s[6], P[6x6]) of the last published state while tracking
        self.initialized = False
        self.last_fix = None       # (t_ns, (x, y, yaw), 'accepted' | 'pending' | 'rejected')
        self.controls = []         # (source_ns, log_ns, seq, v, w) sorted by source time
        self.prune_cut = None
        self.last_key = None
        self.prev_t = self.prev_log = None
        self.rows = 0
        self.counts, self.loss, self.samples, self.recovery = Counter(), Counter(), Counter(), Counter()
        self.nis = dict(accepted=0, accepted_sum=0.0, accepted_max=0.0, rejected=0, singular=0, bias_bound=0)
        self.max_published_sd = 0.0
        self.max_abs_bias = [0.0, 0.0, 0.0]

    # -- telemetry (copied from v1) --------------------------------------------
    def _admit(self, s, t, lg):
        if not isinstance(s, dict) or set(s) != SAMPLE_KEYS:
            return 'rejected_malformed_keys'
        try:
            src, log, seq = _int(s['source_ns'], 'source_ns'), _int(s['log_ns'], 'log_ns'), _int(s['seq'], 'seq')
        except ValueError:
            return 'rejected_malformed_id'
        vals = []
        for name in ('v_mps', 'wz_radps'):
            value = s[name]
            if _is_bool(value) or isinstance(value, (str, bytes)):
                return 'rejected_malformed_value'
            try:
                value = float(value)
            except (TypeError, ValueError):
                return 'rejected_malformed_value'
            if not math.isfinite(value):
                return 'rejected_nonfinite_value'
            vals.append(value)
        if log > lg:
            return 'rejected_future_log'
        key = (log, seq)
        if self.last_key is not None and key <= self.last_key:
            return 'rejected_out_of_order'
        self.last_key = key
        if src > t:
            return 'rejected_future_source'   # never queued for a later interval
        v, w = vals
        if abs(v) > CONTROL_MAX_SPEED_MPS:
            return 'rejected_speed_out_of_range'
        if abs(w) > CONTROL_MAX_YAW_RATE_RADPS:
            return 'rejected_yaw_rate_out_of_range'
        c = self.controls
        if c and self.prune_cut is not None and c[0][0] <= self.prune_cut and src < c[0][0]:
            return 'rejected_superseded_old'
        if src > log:
            self.samples['note_source_after_log'] += 1
        if v < 0:
            self.samples['note_negative_speed'] += 1
        bisect.insort(c, (src, log, seq, v, w))
        if len(c) > CONTROL_BUFFER_MAX:
            del c[0]
            self.samples['buffer_overflow_dropped'] += 1
        return 'admitted'

    def _ingest(self, samples, t, lg, out):
        row = Counter()
        for s in samples:
            row['delivered'] += 1
            row[self._admit(s, t, lg)] += 1
        self.samples.update(row)
        out.update(fusion_samples_delivered=row['delivered'], fusion_samples_admitted=row['admitted'])
        out.update({'fusion_samples_' + k: v for k, v in row.items() if k.startswith('rejected_')})

    def _prune(self, t):
        cut = t - RECOVERY_MAX_GAP_NS
        k = bisect.bisect_right(self.controls, (cut, _INF)) - 1
        if k > 0:
            del self.controls[:k]
        self.prune_cut = cut

    def _segments(self, t0, t1):
        c = self.controls
        i = bisect.bisect_right(c, (t0, _INF)) - 1
        info = dict(segments=0, start_control_age_s=None, max_control_age_s=None)
        if i < 0:
            return None, 'no_prior_control', info
        info['start_control_age_s'] = (t0 - c[i][0]) * 1e-9
        segs, a, worst = [], t0, 0
        while True:
            j = i + 1
            nxt = c[j] if j < len(c) and c[j][0] <= t1 else None
            b = nxt[0] if nxt is not None else t1
            age = b - c[i][0]
            worst = max(worst, age)
            if age > MAX_CONTROL_AGE_NS:
                info['max_control_age_s'] = worst * 1e-9
                return None, 'stale_control', info
            if b > a:
                segs.append((b - a, c[i][3], c[i][4]))
                a = b
            if nxt is None:
                break
            i = j
        info.update(segments=len(segs), max_control_age_s=worst * 1e-9)
        return segs, None, info

    # -- propagation and update ------------------------------------------------
    def _propagate(self, s, P, segs):
        s, P = np.array(s, float), np.array(P, float)
        Gc = np.zeros((6, 2))
        dist = yaw_change = 0.0
        dur = 0
        for dt_ns, v, w in segs:
            F = _jacobian(s, v, w, dt_ns, self.r)
            G = F[:, [3, 5]].copy()     # d/dv == d/db_forward, d/dw == d/db_yaw_rate on the pose rows
            G[3:] = 0.0
            s = transition(s, v, w, dt_ns, self.r)
            P = F @ P @ F.T
            P[3:, 3:] += Q_BIAS_RATE * (dt_ns * 1e-9)
            Gc = F @ Gc + G
            dist += v * dt_ns * 1e-9
            yaw_change += w * dt_ns * 1e-9
            dur += dt_ns
        P = P + Gc @ Q_CONTROL @ Gc.T
        P = 0.5 * (P + P.T)
        if not (np.isfinite(s).all() and np.isfinite(P).all()):
            raise ValueError('nonfinite propagated state or covariance')
        info = dict(interval_s=dur * 1e-9, interval_distance_m=dist, interval_yaw_change_deg=math.degrees(yaw_change),
                    interval_mean_speed_mps=dist / (dur * 1e-9) if dur else float('nan'))
        return s, P, info

    def _nis(self, s, P, z):
        nu = np.array([z[0] - s[0], z[1] - s[1], _wrap(z[2] - s[2])])
        Si = np.linalg.inv(P[:3, :3] + R_VISUAL)
        if not np.isfinite(Si).all():
            raise np.linalg.LinAlgError('nonfinite innovation inverse')
        return nu, Si, float(nu @ Si @ nu)

    def _update(self, s, P, z, out):
        """Returns (s, P, None) on success or (None, None, reason)."""
        try:
            nu, Si, nis = self._nis(s, P, z)
        except np.linalg.LinAlgError:
            self.nis['singular'] += 1
            out['fusion_visual_used'] = 0
            return None, None, 'singular'
        c, sn = math.cos(s[2]), math.sin(s[2])
        out.update(fusion_nis=nis, fusion_nis_gate=NIS_GATE_3D, fusion_innov_m=math.hypot(nu[0], nu[1]),
                   fusion_innov_lon_m=float(c * nu[0] + sn * nu[1]), fusion_innov_lat_m=float(-sn * nu[0] + c * nu[1]),
                   fusion_innov_yaw_deg=math.degrees(float(nu[2])))
        if not math.isfinite(nis) or nis > NIS_GATE_3D:
            self.nis['rejected'] += 1
            out['fusion_visual_used'] = 0
            return None, None, 'nis'
        K = P[:, :3] @ Si
        su = s + K @ nu
        su[2] = _wrap(su[2])
        IKH = I6 - K @ H
        Pu = IKH @ P @ IKH.T + K @ R_VISUAL @ K.T
        Pu = 0.5 * (Pu + Pu.T)
        bias_ok = np.isfinite(su).all() and np.isfinite(Pu).all() and all(
            abs(su[3 + k]) <= BIAS_BOUND[k] for k in range(3))
        if not bias_ok:
            self.nis['bias_bound'] += 1
            out.update(fusion_visual_used=0, fusion_bias_bound_violation=1)
            return None, None, 'bias_out_of_bounds'
        self.nis['accepted'] += 1
        self.nis['accepted_sum'] += nis
        self.nis['accepted_max'] = max(self.nis['accepted_max'], nis)
        out.update(fusion_visual_used=1, fusion_correction_m=math.hypot(su[0] - s[0], su[1] - s[1]),
                   fusion_correction_yaw_deg=math.degrees(_wrap(float(su[2] - s[2]))),
                   fusion_bias_correction_forward_mps=float(su[3] - s[3]),
                   fusion_bias_correction_lateral_mps=float(su[4] - s[4]),
                   fusion_bias_correction_yaw_rate_degps=math.degrees(float(su[5] - s[5])))
        return su, Pu, None

    # -- outputs -----------------------------------------------------------------
    def _publish(self, out, s, P, kind, status):
        out.update(_state_diag('fusion_', s, P))
        out.update(fusion_published=1, fusion_stage=kind, fusion_output_kind=kind,
                   fusion_visual_measurement_used=int(kind in ('visual_corrected', 'recovered_visual')))
        self.counts['published_' + kind] += 1
        self.max_published_sd = max(self.max_published_sd, _pos_sd(P))
        for k in range(3):
            self.max_abs_bias[k] = max(self.max_abs_bias[k], abs(float(s[3 + k])))
        return (float(s[0]), float(s[1]), float(_wrap(s[2]))), status

    def _lost(self, out, reason):
        out.update(fusion_published=0, fusion_stage='lost', fusion_lost_reason=reason)
        return None, 'fusion_lost_' + reason

    def _recover(self, t, z, out):
        p = self.last_fix
        reason = None
        if p is None or p[2] not in ('accepted', 'pending'):
            reason = 'no_partner'
        elif t - p[0] > RECOVERY_MAX_GAP_NS:
            reason = 'gap'
            out['fusion_recovery_partner_age_s'] = (t - p[0]) * 1e-9
        else:
            out.update(fusion_recovery_partner_age_s=(t - p[0]) * 1e-9, fusion_recovery_partner_kind=p[2])
            reason, metrics = _broad(p, (t, z))
            out.update({'fusion_recovery_' + k: v for k, v in metrics.items()})
            if reason is None:
                segs, creason, _ = self._segments(p[0], t)
                if segs is None:
                    self.recovery['motion_check_unavailable_' + creason] += 1
                    out['fusion_recovery_motion_check'] = 'unavailable_' + creason
                else:
                    try:
                        sp, Pp, _ = self._propagate(*_initial(p[1]), segs)
                        nis = self._nis(sp, Pp, z)[2]
                    except (ValueError, np.linalg.LinAlgError, ZeroDivisionError, OverflowError):
                        nis = _INF
                    ok = math.isfinite(nis) and nis <= NIS_GATE_3D
                    out.update(fusion_recovery_motion_nis=nis, fusion_recovery_motion_check='passed' if ok else 'failed')
                    self.recovery['motion_check_' + ('passed' if ok else 'failed')] += 1
                    if not ok:
                        reason = 'motion_inconsistent'
        if reason is None:
            s, P = _initial(z)       # biases reset to zero with their initial uncertainty; not a GT reseed
            self.state = (t, s, P)
            self.last_fix = (t, tuple(float(v) for v in s[:3]), 'accepted')
            self.recovery['recovered'] += 1
            self.counts['bias_resets'] += 1
            return self._publish(out, s, P, 'recovered_visual', 'fusion_recovered')
        self.recovery['pending_' + reason] += 1
        self.last_fix = (t, tuple(float(v) for v in z), 'pending')
        out.update(fusion_published=0, fusion_stage='recovery_pending', fusion_recovery_reason=reason)
        return None, 'fusion_lost_recovery_pending'

    def _fuse(self, t, z, cam_status, out):
        approved = z is not None
        if cam_status == 'gate_seed':
            s, P = _initial(z)
            self.state = (t, s, P)
            self.initialized = True
            self.last_fix = (t, tuple(float(v) for v in s[:3]), 'accepted')
            return self._publish(out, s, P, 'seed', 'fusion_seed')
        if cam_status == 'gate_rejected_seed_not_row_zero':
            self.counts['later_seed_rejected'] += 1
        if not self.initialized:
            return self._lost(out, 'uninitialized')
        loss = None
        if self.state is not None:
            t0, s, P = self.state
            segs, reason, cinfo = self._segments(t0, t)
            out.update({'fusion_' + k: v for k, v in cinfo.items()})
            if segs is None:
                loss = reason
            else:
                tick = time.perf_counter()
                try:
                    sp, Pp, pinfo = self._propagate(s, P, segs)
                except (ValueError, np.linalg.LinAlgError, ZeroDivisionError, OverflowError):
                    loss = 'propagation_error'
                else:
                    out['fusion_propagate_ms'] = 1000.0 * (time.perf_counter() - tick)
                    out.update({'fusion_' + k: v for k, v in pinfo.items()})
                    out.update(_state_diag('fusion_pred_', sp, Pp))
                    reject = None
                    if approved:
                        tick = time.perf_counter()
                        su, Pu, reject = self._update(sp, Pp, z, out)
                        out['fusion_update_ms'] = 1000.0 * (time.perf_counter() - tick)
                        if su is not None:
                            self.state = (t, su, Pu)
                            self.last_fix = (t, tuple(float(v) for v in z), 'accepted')
                            return self._publish(out, su, Pu, 'visual_corrected', 'fusion_visual_corrected')
                        out['fusion_visual_reject_reason'] = reject
                    if _pos_sd(Pp) <= PUBLISH_MAX_POSITION_SD_M:
                        self.state = (t, sp, Pp)
                        if reject is not None:
                            self.last_fix = (t, tuple(float(v) for v in z), 'rejected')
                            return self._publish(out, sp, Pp, 'motion_prediction',
                                                 'fusion_visual_rejected_motion_predicted')
                        return self._publish(out, sp, Pp, 'motion_prediction', 'fusion_motion_predicted')
                    loss = 'uncertain'
            self.state = None
            self.loss[loss] += 1
            self.counts['loss_transitions'] += 1
            out['fusion_loss_reason'] = loss
        if not approved:
            return self._lost(out, loss or 'awaiting_visual')
        return self._recover(t, z, out)

    # -- API -----------------------------------------------------------------------
    def step(self, timestamp_ns, image_log_ns, new_motion_samples, visual_pose_or_none, visual_status, visual_diag):
        start = time.perf_counter()
        t = _int(timestamp_ns, 'timestamp_ns')
        lg = _int(image_log_ns, 'image_log_ns')
        if self.prev_t is not None and t <= self.prev_t:
            raise ValueError('image timestamps must increase strictly')
        if self.prev_log is not None and lg < self.prev_log:
            raise ValueError('image log barriers must be nondecreasing')
        if not isinstance(new_motion_samples, (list, tuple)):
            raise ValueError('new_motion_samples must be a list of sample dicts')
        cam_pose, cam_status, out = self.gate.step(t, visual_pose_or_none, visual_status, visual_diag)
        row = self.rows
        self.rows += 1
        self.prev_t, self.prev_log = t, lg
        if lg < t:
            self.samples['note_image_log_before_exposure'] += 1
        out.update(fusion_version=VERSION, fusion_row=row, fusion_raw_status=str(visual_status),
                   fusion_camera_gate_status=cam_status, fusion_camera_approved=int(cam_pose is not None),
                   fusion_image_log_minus_exposure_ms=(lg - t) * 1e-6,
                   fusion_body_offset_x_m=self.r[0], fusion_body_offset_y_m=self.r[1])
        self._ingest(new_motion_samples, t, lg, out)
        pose, status = self._fuse(t, cam_pose, cam_status, out)
        self._prune(t)
        self.counts['status_' + status] += 1
        out.update(fusion_status=status, fusion_tracking=int(self.state is not None),
                   fusion_controls_buffered=len(self.controls), fusion_core_seconds=time.perf_counter() - start)
        return pose, status, out

    def summary(self):
        published = {k[len('published_'):]: v for k, v in self.counts.items() if k.startswith('published_')}
        n = self.nis['accepted']
        final = None
        if self.state is not None:
            final = _state_diag('', self.state[1], self.state[2])
        return dict(version=VERSION, policy=fixed_policy(), body_offset_xy=list(self.r),
                    assumptions=list(ASSUMPTIONS), rows=self.rows, published=sum(published.values()),
                    published_by_kind=published,
                    status_counts={k[len('status_'):]: v for k, v in sorted(self.counts.items()) if k.startswith('status_')},
                    loss_transitions=self.counts['loss_transitions'], loss_reasons=dict(sorted(self.loss.items())),
                    bias_resets=self.counts['bias_resets'], later_seed_rejected=self.counts['later_seed_rejected'],
                    recovery=dict(sorted(self.recovery.items())), samples=dict(sorted(self.samples.items())),
                    nis=dict(accepted=n, accepted_mean=self.nis['accepted_sum'] / n if n else None,
                             accepted_max=self.nis['accepted_max'] if n else None, rejected=self.nis['rejected'],
                             bias_bound_rejected=self.nis['bias_bound'], singular=self.nis['singular']),
                    max_published_position_sd_m=self.max_published_sd,
                    max_abs_published_bias=dict(forward_mps=self.max_abs_bias[0], lateral_mps=self.max_abs_bias[1],
                                                yaw_rate_degps=math.degrees(self.max_abs_bias[2])),
                    final_state=dict(initialized=self.initialized, tracking=self.state is not None,
                                     controls_buffered=len(self.controls), estimate=final),
                    camera_gate=self.gate.summary(),
                    note='motion_prediction rows are predictions, not visual measurements; '
                         'root scores every finite published pose')


def fixed_policy():
    return dict(version=VERSION, visual_position_std_m=VISUAL_POSITION_STD_M,
                visual_yaw_std_deg=math.degrees(VISUAL_YAW_STD_RAD), control_speed_std_mps=CONTROL_SPEED_STD_MPS,
                control_yaw_rate_std_radps=CONTROL_YAW_RATE_STD_RADPS,
                bias_initial_std=dict(forward_mps=BIAS_INITIAL_STD[0], lateral_mps=BIAS_INITIAL_STD[1],
                                      yaw_rate_radps=BIAS_INITIAL_STD[2]),
                bias_random_walk_per_sqrt_s=dict(forward_mps=BIAS_RANDOM_WALK[0], lateral_mps=BIAS_RANDOM_WALK[1],
                                                 yaw_rate_radps=BIAS_RANDOM_WALK[2]),
                bias_bound=dict(forward_mps=BIAS_BOUND[0], lateral_mps=BIAS_BOUND[1], yaw_rate_radps=BIAS_BOUND[2]),
                max_control_age_s=MAX_CONTROL_AGE_NS * 1e-9, nis_gate_3d=NIS_GATE_3D,
                publish_max_position_sd_m=PUBLISH_MAX_POSITION_SD_M, recovery_max_gap_s=RECOVERY_MAX_GAP_NS * 1e-9,
                broad_speed_mps=BROAD_SPEED_MPS, broad_position_margin_m=BROAD_POSITION_MARGIN_M,
                broad_yaw_rate_radps=BROAD_YAW_RATE_RADPS, broad_yaw_margin_deg=math.degrees(BROAD_YAW_MARGIN_RAD),
                control_max_speed_mps=CONTROL_MAX_SPEED_MPS, control_max_yaw_rate_radps=CONTROL_MAX_YAW_RATE_RADPS,
                control_buffer_max=CONTROL_BUFFER_MAX, jacobian='central differences of the 6-state transition',
                seed_covariance='visual noise floor + initial bias covariance',
                recovery_reset='biases zero with initial covariance', feedback='none: output fusion only')
