"""Spatial triangulation partners for R2 (sift_geometry.py) reference maps. Pure NumPy.

Portable refactor of the authored replacement for the R2 temporal
_pairs(poses, valid, cfg): instead of searching only +/-pair_window temporal
indices, every valid offline FIT reference is a candidate partner, so views from
other fitted laps (and appended low-rate views with no temporal neighbours) can be
paired spatially. Only offline FIT reference planar poses [x, y, yaw] are used;
no query data, labels or outputs.

Per valid anchor i, candidates j != i must be valid (and in partner_mask if given)
with the R2 gates kept exactly:
    pair_min_m <= |xy_j - xy_i| <= pair_max_m  and  |wrap(yaw_j - yaw_i)| < pair_max_yaw_deg
First partner: smallest |distance - pair_target_m|, tie broken by lower index.
Second partner (distinct): best remaining candidate whose signed longitudinal
displacement dot(xy_j - xy_i, heading_i) has the opposite sign of the first
partner's (replaces R2's opposite temporal index direction). If none exists and
spatial_pair_same_side_fallback is True (default), the next best candidate.
Invalid anchors keep the R2 convention: an empty list. Partner order is
[first, second], which R2 _landmarks uses as triangulation priority.
Memory: O(N) temporary arrays per anchor, O(N^2) total time.
"""
from __future__ import annotations

from collections import Counter, OrderedDict

import numpy as np

VERSION = 'spatial_reference_pairs_v1'
# Same keys and defaults as sift_geometry.DEFAULT_CONFIG; values are read from cfg when present.
R2_PAIR_DEFAULTS = dict(pair_min_m=3.0, pair_max_m=15.0, pair_target_m=7.0, pair_max_yaw_deg=12.0, pair_window=16)
SPATIAL_DEFAULTS = dict(spatial_pair_same_side_fallback=True)


def _wrap(a):
    return (a + np.pi) % (2.0 * np.pi) - np.pi


def _params(cfg):
    cfg = dict(cfg or {})
    p = {k: cfg.get(k, v) for k, v in R2_PAIR_DEFAULTS.items()}
    p.update({k: cfg.get(k, v) for k, v in SPATIAL_DEFAULTS.items()})
    for key in ('pair_min_m', 'pair_max_m', 'pair_target_m', 'pair_max_yaw_deg'):
        value = p[key]
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer, np.floating)) \
                or not np.isfinite(float(value)):
            raise ValueError(f'{key} must be a finite number')
        p[key] = float(value)
    if p['pair_min_m'] < 0 or p['pair_max_m'] < p['pair_min_m'] or p['pair_max_yaw_deg'] <= 0:
        raise ValueError('require 0 <= pair_min_m <= pair_max_m and pair_max_yaw_deg > 0')
    if not isinstance(p['spatial_pair_same_side_fallback'], (bool, np.bool_)):
        raise ValueError('spatial_pair_same_side_fallback must be a bool')
    p['spatial_pair_same_side_fallback'] = bool(p['spatial_pair_same_side_fallback'])
    p['pair_window'] = int(p['pair_window'])
    p['config_keys_from_cfg'] = sorted(k for k in list(R2_PAIR_DEFAULTS) + list(SPATIAL_DEFAULTS) if k in cfg)
    return p


def _bool_mask(value, n, name):
    m = np.asarray(value)
    if m.shape != (n,) or m.dtype.kind != 'b':
        raise ValueError(f'{name} must be a bool array of shape ({n},)')
    return m.astype(bool, copy=False)


def _poses(poses):
    p = np.asarray(poses, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError('poses must have shape [N, 3] (x, y, yaw)')
    return p


def spatial_pairs(poses, valid, cfg=None, partner_mask=None):
    """Return list[list[int]] (len N, <= 2 distinct partners each), compatible with R2 model['pairs']."""
    p = _poses(poses)
    n = len(p)
    ok = _bool_mask(valid, n, 'valid') & np.isfinite(p).all(axis=1)
    eligible = ok if partner_mask is None else ok & _bool_mask(partner_mask, n, 'partner_mask')
    prm = _params(cfg)
    dmin, dmax, target = prm['pair_min_m'], prm['pair_max_m'], prm['pair_target_m']
    maxyaw = np.deg2rad(prm['pair_max_yaw_deg'])
    fallback = prm['spatial_pair_same_side_fallback']
    cand_idx = np.flatnonzero(eligible)
    cx, cy, cyaw = p[cand_idx, 0], p[cand_idx, 1], p[cand_idx, 2]
    pairs = []
    for i in range(n):
        if not ok[i]:
            pairs.append([])
            continue
        dx, dy = cx - p[i, 0], cy - p[i, 1]
        dist = np.hypot(dx, dy)
        sel = ((dist >= dmin) & (dist <= dmax) & (np.abs(_wrap(cyaw - p[i, 2])) < maxyaw) & (cand_idx != i))
        if not sel.any():
            pairs.append([])
            continue
        idx = cand_idx[sel]
        order = np.lexsort((idx, np.abs(dist[sel] - target)))      # baseline closeness, then index
        lon = (dx[sel] * np.cos(p[i, 2]) + dy[sel] * np.sin(p[i, 2]))[order]
        idx = idx[order]
        chosen = [int(idx[0])]
        opposite = np.flatnonzero(lon * lon[0] < 0.0)
        if len(opposite):
            chosen.append(int(idx[opposite[0]]))
        elif fallback and len(idx) > 1:
            chosen.append(int(idx[1]))
        pairs.append(chosen)
    return pairs


def _stats(values):
    a = np.asarray(values, dtype=np.float64)
    if not len(a):
        return None
    return dict(min=float(a.min()), median=float(np.median(a)), p95=float(np.percentile(a, 95)), max=float(a.max()))


def summarize_pairs(pairs, poses=None, valid=None, cfg=None, previous_pairs=None):
    """Counts (empty/one/two), and with poses: baselines, opposite/same-side seconds, non-temporal partners."""
    prm = _params(cfg)
    n = len(pairs)
    sizes = Counter(len(x) if x is not None else -1 for x in pairs)
    out = dict(version=VERSION, views=n, empty=sizes.get(0, 0), one=sizes.get(1, 0), two=sizes.get(2, 0),
               more_than_two=int(sum(v for k, v in sizes.items() if k > 2)), none_entries=sizes.get(-1, 0),
               partners_total=int(sum(len(x) for x in pairs if x)),
               config={k: v for k, v in prm.items() if k != 'config_keys_from_cfg'},
               config_keys_from_cfg=prm['config_keys_from_cfg'])
    ok = None
    if valid is not None:
        ok = _bool_mask(valid, n, 'valid')
        out['invalid_views'] = int((~ok).sum())
        out['valid_views_empty'] = int(sum(1 for i, x in enumerate(pairs) if ok[i] and not x))
        out['invalid_views_nonempty'] = int(sum(1 for i, x in enumerate(pairs) if not ok[i] and x))
    if poses is not None:
        p = _poses(poses)
        if len(p) != n:
            raise ValueError('poses and pairs lengths differ')
        if ok is not None:
            ok = ok & np.isfinite(p).all(axis=1)
            out['valid_views_empty'] = int(sum(1 for i, x in enumerate(pairs) if ok[i] and not x))
        base, yawd, second = [], [], Counter()
        outside_window = gate_violations = 0
        for i, x in enumerate(pairs):
            if not x:
                continue
            h = np.array([np.cos(p[i, 2]), np.sin(p[i, 2])])
            lon = []
            for j in x:
                d = p[j, :2] - p[i, :2]
                dist = float(np.hypot(d[0], d[1]))
                ang = float(abs(_wrap(p[j, 2] - p[i, 2])))
                base.append(dist)
                yawd.append(np.rad2deg(ang))
                lon.append(float(d @ h))
                outside_window += int(abs(j - i) > prm['pair_window'])
                gate_violations += int(not (prm['pair_min_m'] <= dist <= prm['pair_max_m'] and
                                            ang < np.deg2rad(prm['pair_max_yaw_deg'])) or j == i)
            if len(x) == 2:
                second['opposite_longitudinal' if lon[0] * lon[1] < 0 else 'same_side'] += 1
        out.update(baseline_m=_stats(base), yaw_difference_deg=_stats(yawd),
                   second_partner_opposite_longitudinal=second['opposite_longitudinal'],
                   second_partner_same_side=second['same_side'],
                   partners_outside_temporal_window=outside_window,
                   partners_outside_temporal_window_fraction=(outside_window / len(base)) if base else None,
                   gate_violations=gate_violations)
    if previous_pairs is not None:
        if len(previous_pairs) != n:
            raise ValueError('previous_pairs and pairs lengths differ')
        same = changed = gained = lost = 0
        for a, b in zip(previous_pairs, pairs):
            a, b = list(a or []), list(b or [])
            same += int(a == b)
            changed += int(a != b)
            gained += int(not a and bool(b))
            lost += int(bool(a) and not b)
        out.update(previous_identical=same, previous_changed=changed, previous_empty_now_paired=gained,
                   previous_paired_now_empty=lost)
    return out


def _partner_mask_from_model(model):
    desc = model.get('desc')
    if desc is None:
        return None
    # R2 backend.match returns no matches when either descriptor set has fewer than 8 entries.
    return np.asarray([d is not None and len(d) >= 8 for d in desc], dtype=bool)


def install_spatial_pairs(model, cfg=None):
    """Replace an R2 sift_geometry model's pairs in place and clear its landmark cache.

    cfg overrides model['config'] pair keys. Install before the first predict: landmarks
    are built lazily from model['pairs'], so the cache is reset to an empty OrderedDict.
    Returns summarize_pairs(..., previous_pairs=<old pairs>).
    """
    if 'pairs' not in model or 'poses' not in model:
        raise ValueError("model has no 'pairs'/'poses': only R2 sift_geometry models use reference pairs")
    merged = dict(model.get('config') or {})
    merged.update(cfg or {})
    poses = np.asarray(model['poses'], dtype=np.float64)
    valid = np.asarray(model['valid'], dtype=bool) if 'valid' in model else np.isfinite(poses).all(axis=1)
    old = [list(x or []) for x in model['pairs']]
    new = spatial_pairs(poses, valid, merged, _partner_mask_from_model(model))
    model['pairs'] = new
    model['cache'] = OrderedDict()
    model['pairs_source'] = VERSION
    summary = summarize_pairs(new, poses, valid, merged, previous_pairs=old)
    model['pairs_summary'] = summary
    return summary


def install_on_rig(rig, cfg=None):
    """Apply install_spatial_pairs to every camera model of an R4 rig with engine 'r2'."""
    if rig.get('engine') != 'r2':
        raise ValueError("spatial pairs apply to engine 'r2' only (refined selects its own spatial neighbours)")
    return {cam: install_spatial_pairs(model, cfg) for cam, model in rig['models'].items()}


def fixed_config():
    return dict(version=VERSION, r2_pair_keys=dict(R2_PAIR_DEFAULTS), spatial=dict(SPATIAL_DEFAULTS),
                ordering='|distance - pair_target_m| then index; second = opposite longitudinal sign, '
                         'else next best if spatial_pair_same_side_fallback',
                max_partners=2)
