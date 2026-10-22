"""Authored SIFT triangulation, local-origin PnP and physical gates, ported to package imports."""
from __future__ import annotations

import time
from collections import Counter, OrderedDict
import cv2
import numpy as np
from . import geometry_core as core
_wrap = core._wrap
_signature = core._signature
_rigid_inverse = core._rigid_inverse
VARIANT = "portable_sift_fullse3_v1"
DEFAULT_CONFIG = dict(
    backend='sift',
    max_features=1000,
    sift_contrast_threshold=0.025,
    sift_octave_layers=3,
    mask_top=8, mask_bottom_fraction=0.90, mask_side=5,
    mask_query=True,
    pair_ratio=0.76, query_ratio=0.80,
    retrieval_candidates=8, solve_candidates=4, early_stop_inliers=30,
    pnp_iterations=80, pnp_reprojection_px=4.0, pnp_confidence=0.99,
    accept_reprojection_px=2.5, accept_reference_distance_m=30.0,
    accept_z_rel_m=2.0, accept_up_deg=12.0, accept_yaw_deg=35.0,
    triangulation_error_px=2.5, min_depth_m=2.0, max_depth_m=180.0, min_parallax_deg=0.7,
    pair_window=16, pair_min_m=3.0, pair_max_m=15.0, pair_target_m=7.0, pair_max_yaw_deg=12.0,
    local_origin=True,
    fuse_references=False, fuse_max_pose_diff_m=2.0,
    map_feature_budget_bytes=900 * 2**20,
    min_features_per_image=300,
    landmark_cache_entries=1024,
    cv_threads=2,
)

_BYTES_PER_FEATURE = {"sift": 136}
_EMPTY_MATCHES = np.zeros((0, 2), np.int64)

def _backend(name, cap, cfg):
    return _OpenCVBackend(name, cap, cfg)

def _ratio_unique(knn, ratio):
    rows = sorted((p[0].distance, p[0].queryIdx, p[0].trainIdx) for p in knn
                  if len(p) == 2 and p[0].distance < ratio * p[1].distance)
    used, out = set(), []
    for _, q, t in rows:
        if t not in used:
            used.add(t)
            out.append((q, t))
    return np.asarray(out, np.int64).reshape(-1, 2)

class _OpenCVBackend:
    def __init__(self, name, cap, cfg):
        self.name = name
        if name != 'sift':
            raise ValueError('portable engine supports SIFT only')
        self.detector = cv2.SIFT_create(nfeatures=int(cap), nOctaveLayers=int(cfg['sift_octave_layers']),
                                        contrastThreshold=float(cfg['sift_contrast_threshold']))
        norm = cv2.NORM_L2
        self.matcher = cv2.BFMatcher(norm)
        self.identity = dict(backend=name, extractor='opencv_'+name, matcher='bf_knn2_ratio_unique_train',
                             descriptor_storage='uint8', opencv_version=cv2.__version__, cap=int(cap))

    def extract(self, image, mask):
        kp, desc = self.detector.detectAndCompute(image, mask)
        pts = np.asarray([p.pt for p in kp], np.float32).reshape(-1, 2)
        if desc is None or not len(desc):
            return pts[:0], None
        if self.name == 'sift':
            # OpenCV SIFT values are saturate_cast<uchar> results: uint8 is exact.
            desc = np.clip(np.rint(desc), 0, 255).astype(np.uint8)
        return pts, np.ascontiguousarray(desc)

    def match(self, a, b, ratio):
        da, db = a[1], b[1]
        if da is None or db is None or len(da) < 8 or len(db) < 8:
            return _EMPTY_MATCHES
        if self.name == 'sift':
            da, db = da.astype(np.float32), db.astype(np.float32)
        return _ratio_unique(self.matcher.knnMatch(da, db, k=2), ratio)

def _mask(shape, cfg):
    mask = np.zeros(shape, np.uint8)
    mask[int(cfg['mask_top']):int(shape[0]*cfg['mask_bottom_fraction']),
         int(cfg['mask_side']):shape[1]-int(cfg['mask_side'])] = 255
    return mask

def _projection(twc, origin):
    local = twc.copy()
    local[:3, 3] -= origin
    return _rigid_inverse(local)[:3]

def _pairs(poses, valid, cfg):
    count = len(poses)
    w = int(cfg['pair_window'])
    pairs = []
    for i, p in enumerate(poses):
        if not valid[i]:
            pairs.append([])
            continue
        near = np.arange(max(0, i-w), min(count, i+w+1))
        distance = np.linalg.norm(poses[near, :2]-p[:2], axis=1)
        angle = np.abs(_wrap(poses[near, 2]-p[2]))
        with np.errstate(invalid='ignore'):
            ok = ((distance >= cfg['pair_min_m']) & (distance <= cfg['pair_max_m']) &
                  (angle < np.deg2rad(cfg['pair_max_yaw_deg'])))
        choice = near[ok]
        if not len(choice):
            pairs.append([])
            continue
        ordered = choice[np.argsort(np.abs(distance[ok]-cfg['pair_target_m']))]
        chosen = [int(ordered[0])]
        other = [int(j) for j in ordered if (int(j)-i)*(chosen[0]-i) < 0]
        if other:
            chosen.append(other[0])
        pairs.append(chosen)
    return pairs

def fit(reference: dict, config=None):
    start = time.perf_counter()
    cfg = dict(DEFAULT_CONFIG, **(config or {}))
    cv2.setNumThreads(min(2, max(1, int(cfg['cv_threads']))))
    twb, poses, valid, ref_info = core._reference_body(reference)
    count = len(poses)
    images = reference['images'] if 'images' in reference else reference['img_paths']
    if len(images) != count:
        raise ValueError('reference image and T_WB counts differ')
    name = cfg['backend']
    if name != 'sift':
        raise ValueError('portable engine supports SIFT only')
    if name not in _BYTES_PER_FEATURE:
        raise ValueError(f'unknown backend {name}')
    budget_cap = int(cfg['map_feature_budget_bytes'] // max(1, count * _BYTES_PER_FEATURE[name]))
    cap = max(int(cfg['min_features_per_image']), min(int(cfg['max_features']), budget_cap))
    backend = _backend(name, cap, cfg)
    kps, descs, signatures, shape, mask = [], [], [], None, None
    for i in range(count):
        im = core._image(reference, i) if valid[i] else None
        if im is None:
            kps.append(np.zeros((0, 2), np.float32))
            descs.append(None)
            signatures.append(np.zeros(960, np.float32))
            continue
        if shape is None:
            shape = im.shape
            mask = _mask(shape, cfg)
        if im.shape != shape:
            raise ValueError('reference images within a camera must share shape')
        pts, desc = backend.extract(im, mask)
        kps.append(pts)
        descs.append(desc)
        signatures.append(_signature(im))
        del im
    if shape is None:
        raise ValueError('no reference images decode')
    k, d, tbc, cal_info = core._camera_calibration(reference['calibration'], shape)
    cameras = [twb[i] @ tbc if valid[i] else None for i in range(count)]
    map_bytes = int(sum(p.nbytes + (0 if q is None else q.nbytes) for p, q in zip(kps, descs)))
    return dict(variant=VARIANT, config=cfg, backend=backend, backend_identity=backend.identity,
                poses=poses, T_WB=twb, valid=valid, kp=kps, desc=descs,
                signatures=np.ascontiguousarray(signatures, dtype=np.float32),
                K=k, D=d, Tbc=tbc, Tbc_inv=_rigid_inverse(tbc), cameras=cameras,
                pairs=_pairs(poses, valid, cfg), cache=OrderedDict(), last=None,
                counts=Counter(), reference_info=ref_info, calibration_info=cal_info,
                feature_cap=cap, budget_feature_cap=budget_cap, map_feature_bytes=map_bytes,
                mask=mask, fit_seconds=time.perf_counter()-start, shape=shape)

def _landmarks(model, i):
    cache = model['cache']
    if i in cache:
        cache.move_to_end(i)
        return cache[i]
    cfg = model['config']
    twc1 = model['cameras'][i]
    if twc1 is None or model['desc'][i] is None:
        result = (np.zeros(0, np.int64), np.zeros((0, 3)), np.zeros(3), 0)
        cache[i] = result
        return result
    k, d = model['K'], model['D']
    origin = twc1[:3, 3].copy() if cfg['local_origin'] else np.zeros(3)
    p1 = _projection(twc1, origin)
    r1 = cv2.Rodrigues(p1[:, :3])[0]
    points = model['kp'][i]
    xyz_by_key = {}
    all_matches = 0
    min_cos = np.cos(np.deg2rad(cfg['min_parallax_deg']))
    for j in model['pairs'][i]:
        twc2 = model['cameras'][j]
        if twc2 is None:
            continue
        m = model['backend'].match((points, model['desc'][i]), (model['kp'][j], model['desc'][j]), cfg['pair_ratio'])
        all_matches += len(m)
        if len(m) < 8:
            continue
        a = points[m[:, 0]].astype(np.float64)
        b = model['kp'][j][m[:, 1]].astype(np.float64)
        an = cv2.undistortPoints(a[:, None], k, d).reshape(-1, 2)
        bn = cv2.undistortPoints(b[:, None], k, d).reshape(-1, 2)
        p2 = _projection(twc2, origin)
        hom = cv2.triangulatePoints(p1, p2, an.T, bn.T)
        with np.errstate(divide='ignore', invalid='ignore'):
            xyz = (hom[:3] / hom[3]).T
        finite = np.isfinite(xyz).all(axis=1)
        xyz = np.where(finite[:, None], xyz, 0.0)
        c1 = xyz @ p1[:, :3].T + p1[:, 3]
        c2 = xyz @ p2[:, :3].T + p2[:, 3]
        da = xyz-(twc1[:3, 3]-origin)
        db = xyz-(twc2[:3, 3]-origin)
        parallax = np.sum(da*db, axis=1)/(np.linalg.norm(da, axis=1)*np.linalg.norm(db, axis=1)+1e-12)
        reproj1, _ = cv2.projectPoints(xyz, r1, p1[:, 3], k, d)
        reproj2, _ = cv2.projectPoints(xyz, cv2.Rodrigues(p2[:, :3])[0], p2[:, 3], k, d)
        err = np.maximum(np.linalg.norm(reproj1.reshape(-1, 2)-a, axis=1),
                         np.linalg.norm(reproj2.reshape(-1, 2)-b, axis=1))
        good = (finite & (c1[:, 2] > cfg['min_depth_m']) & (c1[:, 2] < cfg['max_depth_m']) &
                (c2[:, 2] > cfg['min_depth_m']) & (c2[:, 2] < cfg['max_depth_m']) &
                (parallax < min_cos) & (err < cfg['triangulation_error_px']))
        for q, point, ok in zip(m[:, 0], xyz, good):
            if ok and int(q) not in xyz_by_key:
                xyz_by_key[int(q)] = point
    ids = np.fromiter(sorted(xyz_by_key), np.int64, len(xyz_by_key))
    xyz = np.asarray([xyz_by_key[q] for q in ids], np.float64).reshape(-1, 3)
    model['counts']['triangulated_reference_views'] += 1
    model['counts']['reference_pair_matches'] += all_matches
    model['counts']['valid_landmarks'] += len(ids)
    result = (ids, xyz, origin, all_matches)
    cache[i] = result
    if len(cache) > int(cfg['landmark_cache_entries']):
        cache.popitem(last=False)
        model['counts']['landmark_cache_evictions'] += 1
    return result

def _extract_query(model, image_gray):
    mask = model['mask'] if model['config']['mask_query'] else None
    if mask is not None and mask.shape != image_gray.shape:
        mask = _mask(image_gray.shape, model['config'])
    if mask is None:
        mask = np.full(image_gray.shape, 255, np.uint8)
    return model['backend'].extract(image_gray, mask)

def _body_from_local_pnp(model, rvec, tvec, origin):
    tcw = np.eye(4)
    tcw[:3, :3] = cv2.Rodrigues(rvec)[0]
    tcw[:3, 3] = np.asarray(tvec, np.float64).ravel()
    twc = _rigid_inverse(tcw)
    twc[:3, 3] += origin
    return twc @ model['Tbc_inv']

def _gate(model, i, twb_q, error):
    cfg = model['config']
    ref = model['T_WB'][i]
    yaw = float(np.arctan2(twb_q[1, 0], twb_q[0, 0]))
    pose = np.array([twb_q[0, 3], twb_q[1, 3], yaw])
    distance = float(np.linalg.norm(pose[:2]-ref[:2, 3]))
    yaw_delta = float(abs(_wrap(yaw-model['poses'][i, 2])))
    z_rel = float(twb_q[2, 3]-ref[2, 3])
    up_cos = float(twb_q[:3, 2] @ ref[:3, 2])
    diag = dict(reprojection_px=error, reference_distance=distance, base_z=float(twb_q[2, 3]),
                base_z_rel_reference=z_rel, up_cos=up_cos, world_up_cos=float(twb_q[2, 2]),
                reference_yaw_difference_deg=float(np.rad2deg(yaw_delta)), T_WB=twb_q)
    reject = (not np.isfinite(pose).all() or error > cfg['accept_reprojection_px'] or
              distance > cfg['accept_reference_distance_m'] or abs(z_rel) > cfg['accept_z_rel_m'] or
              up_cos < np.cos(np.deg2rad(cfg['accept_up_deg'])) or yaw_delta > np.deg2rad(cfg['accept_yaw_deg']))
    return pose, diag, reject

def _solve_candidate(model, i, qpts, qdesc):
    cfg = model['config']
    ids, lm_xyz, origin, pair_matches = _landmarks(model, i)
    if len(ids) < 8:
        return None, dict(reference=i, map_points=len(ids), pair_matches=pair_matches,
                          reject='insufficient_triangulation')
    lut = np.full(len(model['kp'][i]), -1, np.int64)
    lut[ids] = np.arange(len(ids))
    m = model['backend'].match((qpts, qdesc), (model['kp'][i], model['desc'][i]), cfg['query_ratio'])
    if len(m):
        m = m[lut[m[:, 1]] >= 0]
    n = len(m)
    if n < 8:
        return None, dict(reference=i, map_points=len(ids), matched_points=n,
                          reject='insufficient_query_matches')
    xyz = lm_xyz[lut[m[:, 1]]]
    uv = qpts[m[:, 0]].astype(np.float64)
    k, d = model['K'], model['D']
    cv2.setRNGSeed(12345)
    ok, rvec, tvec, inliers = cv2.solvePnPRansac(
        xyz, uv, k, d, iterationsCount=int(cfg['pnp_iterations']),
        reprojectionError=float(cfg['pnp_reprojection_px']), confidence=float(cfg['pnp_confidence']),
        flags=cv2.SOLVEPNP_EPNP)
    if not ok or inliers is None or len(inliers) < 8:
        return None, dict(reference=i, map_points=len(ids), matched_points=n,
                          inliers=0 if inliers is None else len(inliers), reject='pnp_ransac')
    sel = inliers.ravel()
    rvec, tvec = cv2.solvePnPRefineLM(xyz[sel], uv[sel], k, d, rvec, tvec)
    proj, _ = cv2.projectPoints(xyz[sel], rvec, tvec, k, d)
    error = float(np.median(np.linalg.norm(proj.reshape(-1, 2)-uv[sel], axis=1)))
    twb_q = _body_from_local_pnp(model, rvec, tvec, origin)
    pose, gdiag, reject = _gate(model, i, twb_q, error)
    diag = dict(reference=i, map_points=len(ids), matched_points=n, inliers=len(sel), **gdiag)
    if reject:
        diag['reject'] = 'physical_or_reprojection_gate'
        return None, diag
    diag['_fusion'] = dict(xyz=xyz[sel], uv=uv[sel], q=m[sel, 0], origin=origin, rvec=rvec, tvec=tvec)
    return pose, diag
