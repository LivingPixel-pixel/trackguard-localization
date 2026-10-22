"""Run an explicitly synthetic SIFT geometry and causal streaming example."""
import argparse
import json
import platform
import cv2
import numpy as np
from . import Localizer
from .synthetic import references, body_pose, render

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['synthetic'])
    args = parser.parse_args()
    refs, texture, cal = references()
    engine = Localizer(refs)
    rows = []
    for i in range(5):
        t = i * 100_000_000
        pose = body_pose(i*0.1)
        images = {c:render(texture,k,pose) for c,k in cal.items()}
        motion = [dict(source_ns=t,log_ns=t,seq=i,v_mps=1.0,wz_radps=0.0)]
        result = engine.step(t,t,images,{c:t for c in images},motion,
                             seed=(0.,0.,0.) if i==0 else None)
        rows.append(dict(timestamp_ns=t,pose=result.pose,status=result.status,
                         raw_geometry=result.diagnostics.get('raw_geometry_status'),
                         joint_cameras=result.diagnostics.get('cameras_joint'),
                         nominal_sd_m=result.diagnostics.get('fusion_pos_sd_m')))
    print(json.dumps(dict(example='SYNTHETIC, not accuracy evidence',
                         python=platform.python_version(),numpy=np.__version__,opencv=cv2.__version__,
                         threads=cv2.getNumThreads(),rows=rows),indent=2,allow_nan=False))

if __name__ == '__main__':
    main()
