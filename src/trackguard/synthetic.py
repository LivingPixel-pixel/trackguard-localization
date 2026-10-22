"""Generated texture and independent pinhole rendering. No external assets."""
from __future__ import annotations
import cv2
import numpy as np

def body_pose(x=0.0, y=0.0, yaw=0.0):
    c, s = np.cos(yaw), np.sin(yaw)
    t = np.eye(4)
    t[:3, :3] = [[c,-s,0],[s,c,0],[0,0,1]]
    t[:3, 3] = [x,y,0]
    return t

def scene():
    cv2.setNumThreads(2)
    rng = np.random.default_rng(47)
    texture = rng.integers(0, 256, (800,1200), dtype=np.uint8)
    texture = cv2.GaussianBlur(texture, (3,3), 0.6)
    for _ in range(250):
        a = tuple(int(x) for x in rng.integers([0,0],[1200,800]))
        cv2.circle(texture, a, int(rng.integers(3,15)), int(rng.integers(0,256)), 2)
    k = np.array([[560.,0,376],[0,560.,182],[0,0,1.]])
    calibrations = {}
    for name, y, yaw in [('left',0.6,0.04),('front',0.,0.),('right',-0.6,-0.04)]:
        tbc = body_pose(0., y, yaw)
        tbc[:3,:3] = tbc[:3,:3] @ np.array([[0,0,1],[-1,0,0],[0,-1,0.]])
        tbc[2,3] = 1.3
        calibrations[name] = dict(K=k.copy(), D=np.zeros(5), T_base_camera=tbc,
                                  original_size=[752,364])
    return texture, calibrations

def render(texture, calibration, twb):
    # A textured plane at world x=40. Projection is independent of the engine.
    corners = np.array([[40,27,16],[40,-27,16],[40,-27,-14],[40,27,-14]],float)
    twc = twb @ calibration['T_base_camera']
    r = twc[:3,:3].T
    t = -r @ twc[:3,3]
    pixels = cv2.projectPoints(corners, cv2.Rodrigues(r)[0], t,
                               calibration['K'], calibration['D'])[0].reshape(4,2)
    h = cv2.getPerspectiveTransform(np.array([[0,0],[1199,0],[1199,799],[0,799]],np.float32),
                                   pixels.astype(np.float32))
    return cv2.warpPerspective(texture,h,(752,364),flags=cv2.INTER_LINEAR)

def references():
    texture, cal = scene()
    poses = np.stack([body_pose(x) for x in (-7.,0.,7.)])
    refs = {c: dict(images=[render(texture,k,t) for t in poses], T_WB=poses.copy(),
                    calibration=k) for c,k in cal.items()}
    return refs, texture, cal
