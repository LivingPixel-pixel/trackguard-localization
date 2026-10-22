"""Authored shared BODY solver and causal retrieval, curated to the SIFT engine."""
from __future__ import annotations

import json
import time
from collections import Counter
import cv2
import numpy as np
from . import sift_geometry as sg
from .quality_gate import _timestamp
VARIANT = 'portable_rig_geometry_v1'
_ZERO3 = np.zeros((3, 1))
_UNIT_Z = np.array([0.0, 0.0, 1.0])
_BEHIND_PENALTY = 50.0
DEFAULT_CONFIG = dict(
    arm='rig_default',
    cameras=('r', 'rl', 'rr'),
    engine='r2',
    backend='sift',
    engine_config=None,
    cv_threads=2,
    rig_landmark_cache_bytes=768 * 2**20,
    # bundle
    bundle_tolerance_ns=1_000_000,
    # retrieval per camera
    per_camera_max_solves=4,
    local_candidates=3,
    global_candidates=1,
    global_candidates_no_prior=4,
    local_radius_m=20.0,
    local_radius_speed_mps=60.0,
    local_yaw_deg=45.0,
    per_camera_early_stop_inliers=None,
    # causal hint (past accepted rig fixes only)
    prior_max_age_s=1.0,
    hint_max_speed_mps=60.0,
    hint_jitter_m=3.0,
    prior_gate_m=4.0,
    prior_gate_speed_mps=15.0,
    prior_gate_yaw_deg=10.0,
    prior_gate_yaw_rate=2.0,
    # consensus
    agree_xy_m=2.0,
    agree_yaw_deg=5.0,
    conflict_quality_ratio=0.5,
    conflict_prior_resolution=True,
    multi_reference_per_camera=True,
    # joint solve
    refine_single_camera=True,
    landmark_weighting=True,
    rig_obs_sigma_px=1.0,
    rig_huber_sigma=1.5,
    rig_refine_iterations=15,
    rig_inlier_px=3.0,
    rig_min_depth_m=0.5,
    camera_balance_power=0.5,
    camera_balance_clip=(0.25, 4.0),
    camera_min_inlier_fraction=0.5,
    camera_min_joint_inliers=6,
    camera_max_median_px=2.5,
    rig_max_joint_shift_m=2.0,
    # optional online copy of the fixed causal Kalman/recovery filter
)


def fit(references, config=None):
    start = time.perf_counter()
    cfg = dict(DEFAULT_CONFIG, **(config or {}))
    cfg['cameras'] = tuple(references)
    cfg['backend'], cfg['engine'] = 'sift', 'r2'
    cams = cfg['cameras']
    if not cams or any(not isinstance(c, str) or not c or '+' in c or c.strip() != c for c in cams):
        raise ValueError('camera IDs must be nonempty strings without + or outer whitespace')
    cv2.setNumThreads(2)
    api = dict(engine='r2', module=sg, extract=sg._extract_query, signature=sg._signature,
               solve=sg._solve_candidate, gate=sg._gate, core=sg.core)
    models = {cam: sg.fit(references[cam], cfg.get('engine_config')) for cam in cams}
    info = {cam: dict(reference_count=len(m['poses']), feature_cap=m['feature_cap'],
                     map_feature_bytes=m['map_feature_bytes'], backend='sift',
                     calibration_info=m['calibration_info']) for cam, m in models.items()}
    return dict(variant=VARIANT, config=cfg, cameras=cams, engine='r2', backend='sift',
                engine_path='trackguard.sift_geometry', models=models, api=api, camera_info=info,
                counts=Counter(), errors=[], hint=None, calls=0, prev_t=None,
                filter=None, filter_path=None, fit_seconds=time.perf_counter()-start)


def _emit(rig, t, pose, status, diag):
    rig['counts']['status_' + status] += 1
    return pose, status, diag

def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi

def summary(rig):
    """JSON-able fit/run summary: config, per-camera info and counters."""
    out = dict(variant=rig['variant'], engine=rig['engine'], backend=rig['backend'], engine_path=rig['engine_path'],
               filter_path=rig['filter_path'], cameras=list(rig['cameras']), fit_seconds=rig['fit_seconds'],
               rig_counts=dict(rig['counts']), errors=list(rig['errors']),
               camera_info=rig['camera_info'],
               camera_counts={c: dict(m.get('counts', {})) for c, m in rig['models'].items()},
               config={k: v for k, v in rig['config'].items()})
    if rig['filter'] is not None:
        out['filter_counts'] = dict(rig['filter'].counts)
    return json.loads(json.dumps(out, default=lambda o: o.tolist() if hasattr(o, 'tolist') else str(o)))

def _prior(rig, t):
    cfg, hint = rig['config'], rig['hint']
    if hint is None:
        return None
    dt = (t - hint['t']) * 1e-9
    if dt <= 0 or dt > cfg['prior_max_age_s']:
        return None
    step = min(dt, 0.5)
    if hint['v'] is None:
        xy, radius = hint['pose'][:2].copy(), cfg['prior_gate_m'] + cfg['hint_max_speed_mps'] * dt
    else:
        xy, radius = hint['pose'][:2] + hint['v'] * step, cfg['prior_gate_m'] + cfg['prior_gate_speed_mps'] * dt
    return dict(xy=xy, yaw=float(_wrap(hint['pose'][2] + hint['w'] * step)), dt=dt, radius=radius)

def _within_prior(pose, prior, cfg):
    return bool(np.linalg.norm(pose[:2] - prior['xy']) <= prior['radius'] and
                abs(_wrap(pose[2] - prior['yaw'])) <= np.deg2rad(cfg['prior_gate_yaw_deg']) + cfg['prior_gate_yaw_rate'] * prior['dt'])

def _update_hint(rig, t, pose):
    cfg, hint = rig['config'], rig['hint']
    v, w = None, 0.0
    if hint is not None:
        dt = (t - hint['t']) * 1e-9
        if 0 < dt <= cfg['prior_max_age_s']:
            delta = pose[:2] - hint['pose'][:2]
            if float(np.linalg.norm(delta)) > cfg['hint_max_speed_mps'] * dt + cfg['hint_jitter_m']:
                rig['counts']['hint_update_skipped_physical'] += 1
                return
            v = delta / dt
            speed = float(np.linalg.norm(v))
            if speed > cfg['hint_max_speed_mps']:
                v *= cfg['hint_max_speed_mps'] / speed
            if hint['v'] is not None:
                v = 0.5 * hint['v'] + 0.5 * v
            w = float(np.clip(_wrap(pose[2] - hint['pose'][2]) / dt, -2.0, 2.0))
            w = 0.5 * hint['w'] + 0.5 * w
    rig['hint'] = dict(t=int(t), pose=np.asarray(pose, np.float64).copy(), v=v, w=w)

def _error(rig, where, exc):
    rig['counts']['error_' + type(exc).__name__] += 1
    if len(rig['errors']) < 10:
        text = str(exc).splitlines()[0] if str(exc) else ''
        rig['errors'].append(f'{where}: {type(exc).__name__}: {text}')

def _retrieve(model, sim, prior, cfg):
    n = len(sim)
    max_solves = int(cfg['per_camera_max_solves'])
    local = []
    if prior is not None:
        radius = cfg['local_radius_m'] + cfg['local_radius_speed_mps'] * min(prior['dt'], 1.0)
        with np.errstate(invalid='ignore'):
            d = np.linalg.norm(model['poses'][:, :2] - prior['xy'], axis=1)
            a = np.abs(_wrap(model['poses'][:, 2] - prior['yaw']))
            pool = np.flatnonzero((d <= radius) & (a <= np.deg2rad(cfg['local_yaw_deg'])))
        if len(pool):
            local = [int(i) for i in pool[np.argsort(-sim[pool], kind='stable')][:int(cfg['local_candidates'])]]
    nglobal = int(cfg['global_candidates'] if local else cfg['global_candidates_no_prior'])
    glob = []
    if nglobal > 0 and n:
        top = min(nglobal + len(local), n)
        g = np.argpartition(-sim, top - 1)[:top]
        g = g[np.argsort(-sim[g], kind='stable')]
        glob = [int(i) for i in g if int(i) not in local][:nglobal]
    kept_local = local[:max(0, max_solves - len(glob))]
    return (kept_local + glob)[:max_solves], len(kept_local)

def _process_camera(rig, cam, image, prior):
    cfg, api, model = rig['config'], rig['api'], rig['models'][cam]
    tick = time.perf_counter()
    rec = dict(cam=cam, status='no_query_features', features=0, solves=0, local=0, accepted=[], rejects=Counter())
    try:
        image = np.asarray(image)
        if image.ndim != 2 or image.dtype != np.uint8 or image.shape != tuple(model['shape']):
            rec['status'] = 'query_shape_mismatch'
            return rec
        qpts, qdesc = api['extract'](model, image)
        rec['features'] = int(len(qpts))
        if qdesc is None or len(qdesc) < 8:
            return rec
        sim = np.asarray(model['signatures'] @ api['signature'](image), np.float64)
        sim = np.where(np.isfinite(sim), sim, -np.inf)
        candidates, rec['local'] = _retrieve(model, sim, prior, cfg)
        early = cfg['per_camera_early_stop_inliers'] or model['config'].get('early_stop_inliers', 30)
        for i in candidates:
            try:
                pose, diag = api['solve'](model, int(i), qpts, qdesc)
            except Exception as exc:  # engine errors stay per camera
                _error(rig, f'solve:{cam}:{i}', exc)
                pose, diag = None, dict(reject='solver_error_' + type(exc).__name__)
            rec['solves'] += 1
            fusion = diag.pop('_fusion', None)
            if pose is None or fusion is None or 'T_WB' not in diag:
                rec['rejects'][diag.get('reject', 'unknown_reject')] += 1
                continue
            pose = np.asarray(pose, np.float64)
            quality = float(diag['inliers']) / (1.0 + float(diag['reprojection_px']))
            rec['accepted'].append(dict(cam=cam, ref=int(i), pose=pose, T=np.asarray(diag['T_WB'], np.float64),
                                        inliers=int(diag['inliers']), reproj=float(diag['reprojection_px']),
                                        quality=quality, fusion=fusion, diag=diag))
            if diag['inliers'] >= early and (prior is None or _within_prior(pose, prior, cfg)):
                break
        rec['status'] = 'accepted' if rec['accepted'] else 'geometry_rejected'
    except Exception as exc:
        _error(rig, f'camera:{cam}', exc)
        rec['status'] = 'camera_error_' + type(exc).__name__
    finally:
        rec['ms'] = 1000.0 * (time.perf_counter() - tick)
    return rec

def _agree(a, b, cfg):
    return bool(np.linalg.norm(a[:2] - b[:2]) <= cfg['agree_xy_m'] and
                abs(_wrap(a[2] - b[2])) <= np.deg2rad(cfg['agree_yaw_deg']))

def _hypotheses(cands, cfg):
    hyps = []
    for h, c in enumerate(cands):
        support = {}
        for k, o in enumerate(cands):
            if _agree(o['pose'], c['pose'], cfg):
                cur = support.get(o['cam'])
                if cur is None or o['quality'] > cands[cur]['quality']:
                    support[o['cam']] = k
        hyps.append(dict(h=h, support=support, n=len(support), q=float(sum(cands[k]['quality'] for k in support.values()))))
    hyps.sort(key=lambda x: (-x['n'], -x['q'], -cands[x['h']]['quality']))
    return hyps

def _skew_rows(v):
    s = np.zeros((len(v), 3, 3))
    x, y, z = v[:, 0], v[:, 1], v[:, 2]
    s[:, 0, 1], s[:, 0, 2] = -z, y
    s[:, 1, 0], s[:, 1, 2] = z, -x
    s[:, 2, 0], s[:, 2, 1] = -y, x
    return s

def _cov_full(cov6):
    c = np.asarray(cov6, np.float64)
    out = np.empty((len(c), 3, 3))
    out[:, 0, 0], out[:, 0, 1], out[:, 0, 2] = c[:, 0], c[:, 1], c[:, 2]
    out[:, 1, 0], out[:, 1, 1], out[:, 1, 2] = c[:, 1], c[:, 3], c[:, 4]
    out[:, 2, 0], out[:, 2, 1], out[:, 2, 2] = c[:, 2], c[:, 4], c[:, 5]
    return out

def _project_block(b, R, p, zmin):
    xb = (b['X'] - p) @ R                      # R_WB^T (X_W - p_WB)
    xc = (xb - b['tbc']) @ b['Rbc']            # R_BC^T (X_B - t_BC)
    good = xc[:, 2] > zmin
    xs = np.where(good[:, None], xc, _UNIT_Z)
    proj, jac = cv2.projectPoints(np.ascontiguousarray(xs.reshape(-1, 1, 3)), _ZERO3, _ZERO3, b['K'], b['D'])
    return xb, good, proj.reshape(-1, 2), jac.reshape(len(xs), 2, -1)[:, :, 3:6]

def _block(rig, cam, cands, origin):
    model = rig['models'][cam]
    xs, uvs, covs, seen = [], [], [], set()
    has_cov = all(c['fusion'].get('cov') is not None for c in cands)
    used = []
    for c in cands:
        f = c['fusion']
        q = np.asarray(f['q'], np.int64)
        keep = np.asarray([int(v) not in seen for v in q], bool)
        if not keep.any():
            continue
        seen.update(int(v) for v in q[keep])
        xs.append(np.asarray(f['xyz'], np.float64)[keep] + (np.asarray(f['origin'], np.float64) - origin))
        uvs.append(np.asarray(f['uv'], np.float64)[keep])
        if has_cov:
            covs.append(np.asarray(f['cov'], np.float64)[keep])
        used.append(c['ref'])
    tbc = np.asarray(model['Tbc'], np.float64)
    return dict(cam=cam, X=np.concatenate(xs) if xs else np.zeros((0, 3)),
                uv=np.concatenate(uvs) if uvs else np.zeros((0, 2)),
                cov=np.concatenate(covs) if (has_cov and covs) else None,
                Rbc=tbc[:3, :3].copy(), tbc=tbc[:3, 3].copy(), K=np.asarray(model['K'], np.float64),
                D=np.asarray(model['D'], np.float64), refs=used)

def _cov_weights(b, R, p, cfg):
    n = len(b['X'])
    if b['cov'] is None or not cfg['landmark_weighting'] or not n:
        return np.ones(n)
    _, good, _, jp = _project_block(b, R, p, cfg['rig_min_depth_m'])
    jx = jp @ (b['Rbc'].T @ R.T)               # d uv / d X_W
    tr = np.einsum('nij,njk,nik->n', jx, _cov_full(b['cov']), jx)
    s0 = cfg['rig_obs_sigma_px'] ** 2
    with np.errstate(invalid='ignore', divide='ignore'):
        w = s0 / (s0 + 0.5 * tr)
    return np.where(np.isfinite(w) & good, np.clip(w, 1e-3, 1.0), 1.0)

def _subset(b, mask):
    return dict(b, X=b['X'][mask], uv=b['uv'][mask], wcov=b['wcov'][mask],
                cov=None if b['cov'] is None else b['cov'][mask])

def _rig_refine(blocks, R, p, cfg):
    s0, delta, zmin = float(cfg['rig_obs_sigma_px']), float(cfg['rig_huber_sigma']), float(cfg['rig_min_depth_m'])
    ns = np.asarray([len(b['X']) for b in blocks], np.float64)
    lo, hi = cfg['camera_balance_clip']
    balance = (np.ones(len(blocks)) if len(blocks) < 2 else
               np.clip((np.median(ns) / np.maximum(ns, 1.0)) ** float(cfg['camera_balance_power']), lo, hi))

    def evaluate(R, p):
        res, cost = [], 0.0
        for b, bal in zip(blocks, balance):
            xb, good, proj, jp = _project_block(b, R, p, zmin)
            r = np.where(good[:, None], proj - b['uv'], 0.0)
            e = np.where(good, np.linalg.norm(proj - b['uv'], axis=1), np.inf)
            ehat = np.where(good, np.linalg.norm(r, axis=1) * np.sqrt(b['wcov']) / s0, 0.0)
            hub = np.where(ehat <= delta, 1.0, delta / np.maximum(ehat, 1e-12))
            rho = np.where(good, np.where(ehat <= delta, 0.5 * ehat ** 2, delta * (ehat - 0.5 * delta)), _BEHIND_PENALTY)
            cost += float(bal * rho.sum())
            res.append(dict(xb=xb, r=r, jp=jp, e=e, good=good, w=np.where(good, bal * b['wcov'] * hub, 0.0)))
        return res, cost

    def normal(res):
        h, g = np.zeros((6, 6)), np.zeros(6)
        for b, rr in zip(blocks, res):
            if not len(rr['e']):
                continue
            a = rr['jp'] @ b['Rbc'].T
            j = np.nan_to_num(np.concatenate([a @ _skew_rows(rr['xb']), -a], axis=2))
            wj = j * rr['w'][:, None, None]
            h += np.einsum('nki,nkj->ij', wj, j)
            g += np.einsum('nki,nk->i', wj, rr['r'])
        return h, g

    R, p = np.asarray(R, np.float64).copy(), np.asarray(p, np.float64).copy()
    res, cost = evaluate(R, p)
    lam = 1e-3
    for _ in range(int(cfg['rig_refine_iterations'])):
        h, g = normal(res)
        try:
            step = -np.linalg.solve(h + lam * np.diag(np.diag(h)) + 1e-9 * np.eye(6), g)
        except np.linalg.LinAlgError:
            break
        if not np.isfinite(step).all():
            break
        r2 = R @ cv2.Rodrigues(step[:3].reshape(3, 1))[0]
        p2 = p + R @ step[3:]
        res2, cost2 = evaluate(r2, p2)
        if np.isfinite(cost2) and cost2 <= cost:
            R, p, res, cost = r2, p2, res2, cost2
            lam = max(lam * 0.3, 1e-9)
            if float(np.linalg.norm(step)) < 1e-9:
                break
        else:
            lam *= 10.0
            if lam > 1e6:
                break
    h, _ = normal(res)
    good_n = int(sum(int(rr['good'].sum()) for rr in res))
    num = float(sum(float(np.sum(rr['w'] * np.where(rr['good'], rr['e'], 0.0) ** 2)) for rr in res))
    return R, p, dict(H=h, s2=num / max(1, 2 * good_n - 6), res=res, cost=cost, balance=balance)

def _block_stats(blocks, info, cfg):
    out = []
    for b, rr, bal in zip(blocks, info['res'], info['balance']):
        e = rr['e']
        m = np.isfinite(e) & (e <= cfg['rig_inlier_px'])
        n, k = len(e), int(m.sum())
        med = float(np.median(e[m])) if k else float('inf')
        frac = k / max(1, n)
        ok = (frac >= cfg['camera_min_inlier_fraction'] and k >= cfg['camera_min_joint_inliers'] and
              med <= cfg['camera_max_median_px'])
        out.append(dict(cam=b['cam'], n=n, inliers=k, fraction=frac, median_px=med, mask=m, ok=ok, balance=float(bal)))
    return out

def _joint(rig, by_cam, anchor):
    cfg = rig['config']
    t0 = anchor['T']
    origin, r0, p0 = t0[:3, 3].copy(), t0[:3, :3].copy(), np.zeros(3)
    blocks = [_block(rig, cam, cands, origin) for cam, cands in by_cam.items()]
    blocks = [b for b in blocks if len(b['X'])]
    for b in blocks:
        b['wcov'] = _cov_weights(b, r0, p0, cfg)
    active, dropped, first_stats = list(blocks), [], {}
    while True:
        R, p, info = _rig_refine(active, r0, p0, cfg)
        stats = _block_stats(active, info, cfg)
        first_stats.update({s['cam']: s for s in stats})
        bad = [k for k, s in enumerate(stats) if s['cam'] != anchor['cam'] and not s['ok']]
        if not bad:
            break
        worst = min(bad, key=lambda k: stats[k]['fraction'])
        dropped.append(active[worst]['cam'])
        del active[worst]
    subs = [_subset(b, s['mask']) for b, s in zip(active, stats) if s['mask'].any()]
    if sum(len(b['X']) for b in subs) >= 8:
        R, p, info = _rig_refine(subs, R, p, cfg)
        final = subs
    else:
        final = active
    final_stats = _block_stats(final, info, cfg)
    t = np.eye(4)
    t[:3, :3], t[:3, 3] = R, p + origin
    return t, info, final, final_stats, first_stats, dropped

def _sigmas(info):
    h = info['H']
    try:
        cov = info['s2'] * np.linalg.inv(h)
        cond = float(np.linalg.cond(h))
    except np.linalg.LinAlgError:
        return dict(pose_condition=float('inf'))
    s = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    return dict(sigma_roll_deg=float(np.rad2deg(s[0])), sigma_pitch_deg=float(np.rad2deg(s[1])),
                sigma_yaw_deg=float(np.rad2deg(s[2])), sigma_lon_m=float(s[3]), sigma_lat_m=float(s[4]),
                sigma_z_m=float(s[5]), sigma_pos_m=float(np.hypot(s[3], s[4])), pose_condition=cond,
                residual_sigma_px=float(np.sqrt(max(info['s2'], 0.0))))

def _members(rig, images, member_timestamps_ns, t):
    cfg, counts = rig['config'], rig['counts']
    used, state = {}, {}
    for cam in rig['cameras']:
        image = images.get(cam) if images is not None else None
        stamp = member_timestamps_ns.get(cam) if member_timestamps_ns is not None else None
        if image is None or stamp is None:
            state[cam] = 'member_missing'
        elif _timestamp(stamp) > t:
            state[cam] = 'member_future_dropped'
        elif t - _timestamp(stamp) > int(cfg['bundle_tolerance_ns']):
            state[cam] = 'member_outside_tolerance_dropped'
        else:
            used[cam] = (image, int(stamp))
            continue
        counts[f'cam_{cam}_{state[cam]}'] += 1
    return used, state

def predict(rig, images, timestamp_ns, member_timestamps_ns, seed=None):
    """images: {camera: gray uint8 [364,752]}; member_timestamps_ns: {camera: exposure ns}.

    Returns (pose[x, y, yaw] | None, status, diag). timestamp_ns is the bundle output time.
    """
    start = time.perf_counter()
    cfg, counts = rig['config'], rig['counts']
    t = _timestamp(timestamp_ns)
    if rig['prev_t'] is not None and t <= rig['prev_t']:
        raise ValueError('bundle timestamps must increase strictly')
    first = rig['calls'] == 0
    rig['calls'] += 1
    rig['prev_t'] = t
    if seed is not None:
        if not first:
            raise ValueError('only the first predict call may receive the seed')
        pose = np.asarray(seed, np.float64).reshape(3)
        if not np.isfinite(pose).all():
            raise ValueError('seed must be a finite [x, y, yaw]')
        rig['hint'] = dict(t=t, pose=pose.copy(), v=None, w=0.0)
        return _emit(rig, t, pose.copy(), 'seed', dict(core_seconds=time.perf_counter() - start))
    used, member_state = _members(rig, images, member_timestamps_ns, t)
    diag = dict(cameras_configured=len(rig['cameras']), cameras_used=len(used))
    if used:
        stamps = [s for _, s in used.values()]
        diag.update(bundle_span_ms=(max(stamps) - min(stamps)) * 1e-6, output_minus_max_member_ms=(t - max(stamps)) * 1e-6)
    prior = _prior(rig, t)
    diag['prior_available'] = int(prior is not None)
    records = {cam: _process_camera(rig, cam, image, prior) for cam, (image, _) in used.items()}
    cands = [c for rec in records.values() for c in rec['accepted']]
    for cam in rig['cameras']:
        rec = records.get(cam)
        diag[f'cam_{cam}_status'] = member_state.get(cam, rec['status'] if rec else 'unused')
        if rec is not None:
            counts[f'cam_{cam}_{rec["status"]}'] += 1
            diag.update({f'cam_{cam}_features': rec['features'], f'cam_{cam}_solves': rec['solves'],
                         f'cam_{cam}_local_candidates': rec['local'], f'cam_{cam}_fixes': len(rec['accepted']),
                         f'cam_{cam}_ms': rec['ms']})
            if rec['accepted']:
                diag[f'cam_{cam}_best_inliers'] = max(c['inliers'] for c in rec['accepted'])
            for reason, n in rec['rejects'].items():
                counts[f'cam_{cam}_reject_{reason}'] += n
    diag['cameras_with_fix'] = int(sum(1 for rec in records.values() if rec['accepted']))
    if not cands:
        status = ('rig_no_valid_members' if not used else
                  'rig_no_query_features' if all(r['status'] == 'no_query_features' for r in records.values()) else
                  'rig_geometry_rejected')
        diag['core_seconds'] = time.perf_counter() - start
        return _emit(rig, t, None, status, diag)

    hyps = _hypotheses(cands, cfg)
    chosen = hyps[0]
    alt = next((x for x in hyps[1:] if not _agree(cands[x['h']]['pose'], cands[chosen['h']]['pose'], cfg)), None)
    conflict = bool(alt is not None and alt['n'] == chosen['n'] and alt['q'] >= cfg['conflict_quality_ratio'] * chosen['q'])
    diag.update(conflict=int(conflict), hypotheses=len(hyps), support_cameras=chosen['n'],
                alternative_support_cameras=0 if alt is None else alt['n'],
                alternative_quality_ratio=float('nan') if alt is None else alt['q'] / max(chosen['q'], 1e-12))
    suffix = ''
    if conflict:
        counts['conflicts'] += 1
        resolved = None
        if prior is not None and cfg['conflict_prior_resolution']:
            in_c = _within_prior(cands[chosen['h']]['pose'], prior, cfg)
            in_a = _within_prior(cands[alt['h']]['pose'], prior, cfg)
            resolved = chosen if (in_c and not in_a) else alt if (in_a and not in_c) else None
        if resolved is None:
            counts['conflicts_unresolved'] += 1
            diag['core_seconds'] = time.perf_counter() - start
            return _emit(rig, t, None, 'rig_camera_conflict', diag)
        counts['conflicts_prior_resolved'] += 1
        chosen, suffix = resolved, '_prior_resolved'
    hpose = cands[chosen['h']]['pose']
    support = chosen['support']
    anchor = max((cands[k] for k in support.values()), key=lambda c: c['quality'])
    by_cam = {}
    for cam in support:
        mine = sorted((c for c in cands if c['cam'] == cam and _agree(c['pose'], hpose, cfg)),
                      key=lambda c: -c['quality'])
        by_cam[cam] = mine if cfg['multi_reference_per_camera'] else mine[:1]
    dissent = [cam for cam, rec in records.items() if rec['accepted'] and cam not in support]
    diag.update(cameras_dissenting=len(dissent), anchor_camera=anchor['cam'], anchor_reference=anchor['ref'],
                anchor_inliers=anchor['inliers'])
    model = rig['models'][anchor['cam']]
    out_T, status, joint_cams = anchor['T'], 'rig_single_camera', [anchor['cam']]
    if len(by_cam) >= 2 or cfg['refine_single_camera']:
        try:
            T, info, final, fstats, first_stats, dropped = _joint(rig, by_cam, anchor)
            inl = np.concatenate([s['mask'] for s in fstats]) if fstats else np.zeros(0, bool)
            errs = np.concatenate([rr['e'] for rr in info['res']]) if info['res'] else np.zeros(0)
            med = float(np.median(errs[inl])) if inl.any() else float('inf')
            _, gdiag, reject = rig['api']['gate'](model, anchor['ref'], T, med)
            shift = float(np.linalg.norm(T[:2, 3] - anchor['T'][:2, 3]))
            diag.update(joint_inliers=int(inl.sum()), joint_median_px=med, joint_shift_m=shift,
                        cameras_dropped_joint=len(dropped), joint_gate_reject=int(bool(reject)))
            for cam in dropped:
                counts[f'cam_{cam}_dropped_joint_inconsistent'] += 1
            for cam, s in first_stats.items():
                diag.update({f'cam_{cam}_joint_fraction': s['fraction'], f'cam_{cam}_balance': s['balance']})
            for s in fstats:
                diag.update({f'cam_{s["cam"]}_joint_inliers': s['inliers'], f'cam_{s["cam"]}_joint_median_px': s['median_px']})
            if reject or shift > cfg['rig_max_joint_shift_m'] or int(inl.sum()) < 8:
                counts['joint_unstable'] += 1
                status = 'rig_single_camera_joint_unstable'
            else:
                out_T = T
                joint_cams = [b['cam'] for b in final]
                status = 'rig_joint' if len(joint_cams) >= 2 else 'rig_single_camera'
                diag.update(_sigmas(info))
        except Exception as exc:
            _error(rig, 'joint', exc)
            status = 'rig_single_camera_joint_error'
    status += suffix
    out_T = np.asarray(out_T, np.float64)
    pose = np.array([out_T[0, 3], out_T[1, 3], np.arctan2(out_T[1, 0], out_T[0, 0])])
    for cam, rec in records.items():
        if rec['accepted']:
            best = max(rec['accepted'], key=lambda c: c['quality'])
            diag[f'cam_{cam}_agrees'] = int(cam in joint_cams)
            diag[f'cam_{cam}_shift_m'] = float(np.linalg.norm(best['pose'][:2] - pose[:2]))
    diag.update(cameras_joint=len(joint_cams), joint_cameras='+'.join(joint_cams), T_WB=out_T,
                body_z=float(out_T[2, 3]), core_seconds=time.perf_counter() - start)
    counts[f'joint_cameras_{len(joint_cams)}'] += 1
    _update_hint(rig, t, pose)
    return _emit(rig, t, pose, status, diag)
