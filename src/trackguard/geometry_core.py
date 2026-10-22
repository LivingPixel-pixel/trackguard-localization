"""Retained calibration and SE3 helpers from authored precision_geometry.py."""
from __future__ import annotations

import cv2
import numpy as np

def _wrap(a):
    return (a + np.pi) % (2 * np.pi) - np.pi

def _signature(image):
    a = cv2.resize(image, (48, 20), interpolation=cv2.INTER_AREA).astype(np.float32)
    a -= cv2.GaussianBlur(a, (0, 0), 2.0)
    a /= max(float(np.linalg.norm(a)), 1.0)
    return a.ravel()

def _rigid_inverse(t):
    out = np.eye(4)
    out[:3, :3] = t[:3, :3].T
    out[:3, 3] = -t[:3, :3].T @ t[:3, 3]
    return out

def _is_rigid(t, tol=1e-5):
    t = np.asarray(t, dtype=np.float64)
    if t.shape != (4, 4) or not np.isfinite(t).all():
        return False
    r = t[:3, :3]
    return bool(np.allclose(t[3], [0, 0, 0, 1], atol=1e-9) and
                np.allclose(r.T @ r, np.eye(3), atol=tol) and
                abs(float(np.linalg.det(r)) - 1.0) < tol)

def _camera_calibration(cal, shape):
    """K for the original JPEG size is rescaled exactly once to `shape`."""
    k = np.asarray(cal['K'], dtype=np.float64).reshape(3, 3).copy()
    d = np.asarray(cal.get('D', []), dtype=np.float64).ravel()
    size = cal.get('original_size', cal.get('image_size',
                   (cal.get('width', 0), cal.get('height', 0))))
    if isinstance(size, dict):
        size = (size['width'], size['height'])
    if min(float(size[0]), float(size[1])) <= 0:
        raise ValueError('calibration requires positive original_size [width, height]')
    sx, sy = shape[1] / float(size[0]), shape[0] / float(size[1])
    k[0] *= sx
    k[1] *= sy
    raw = cal.get('T_base_camera', cal.get('T_bc'))
    frames = {}
    if raw is None and 'extrinsic' in cal:
        ex = cal['extrinsic']
        frames = dict(parent=str(ex.get('parent', '')), child=str(ex.get('child', '')))
        x, y, z, w = np.asarray(ex['quaternion_xyzw'], np.float64)
        qnorm = np.sqrt(x*x+y*y+z*z+w*w)
        x, y, z, w = x/qnorm, y/qnorm, z/qnorm, w/qnorm
        rotation = np.array([
            [1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
            [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
            [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]], np.float64)
        raw = np.eye(4)
        raw[:3, :3] = rotation
        raw[:3, 3] = ex['translation']
    if raw is None:
        raise ValueError('geometry requires T_base_camera optical-to-base 4x4')
    t = np.asarray(raw, dtype=np.float64).reshape(4, 4)
    if not _is_rigid(t):
        raise ValueError('T_BC is not a proper rigid transform')
    info = dict(calibration_size=[float(size[0]), float(size[1])],
                working_size=[int(shape[1]), int(shape[0])],
                intrinsic_scale=[sx, sy], optical_axis_body=t[:3, 2].tolist(),
                camera_translation_body=t[:3, 3].tolist(), **frames)
    return k, d, t, info

def _reference_body(reference):
    """Training-only full-SE3 body transforms; pose3 derived from T_WB."""
    if 'T_WB' not in reference:
        raise ValueError('precision geometry requires training-only T_WB[N,4,4]')
    twb = np.asarray(reference['T_WB'], dtype=np.float64)
    if twb.ndim != 3 or twb.shape[1:] != (4, 4):
        raise ValueError('T_WB must have shape [N,4,4]')
    valid = np.array([_is_rigid(t) for t in twb], dtype=bool)
    poses = np.column_stack((twb[:, 0, 3], twb[:, 1, 3],
                             np.arctan2(twb[:, 1, 0], twb[:, 0, 0])))
    poses[~valid] = np.nan
    info = dict(reference_frames=int(len(twb)), invalid_T_WB=int((~valid).sum()))
    legacy = reference.get('poses')
    if legacy is not None:
        legacy = np.asarray(legacy, dtype=np.float64)
        if legacy.shape == poses.shape:
            ok = valid & np.isfinite(legacy).all(axis=1)
            if ok.any():
                info['legacy_xy_max_diff_m'] = float(np.max(np.linalg.norm(legacy[ok, :2]-poses[ok, :2], axis=1)))
                info['legacy_yaw_max_diff_deg'] = float(np.rad2deg(np.max(np.abs(_wrap(legacy[ok, 2]-poses[ok, 2])))))
    if valid.any():
        info['body_z_min_m'] = float(np.min(twb[valid, 2, 3]))
        info['body_z_max_m'] = float(np.max(twb[valid, 2, 3]))
        info['body_world_up_cos_min'] = float(np.min(twb[valid, 2, 2]))
    return twb, poses, valid, info


def _image(reference, i):
    """Read caller-owned grayscale pixels at their supplied resolution."""
    if 'images' in reference:
        image = np.asarray(reference['images'][i])
    else:
        image = cv2.imread(str(reference['img_paths'][i]), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError('reference image could not be decoded')
    if image.ndim != 2 or image.dtype != np.uint8:
        raise ValueError('reference images must be grayscale uint8 [H,W]')
    return image
