"""Independent synthetic geometry and causal regression tests, no private assets."""
import copy
import math
import unittest
import cv2
import numpy as np
from trackguard import Localizer, Gate, Fusion
from trackguard import sift_geometry as sg, rig_geometry as rg
from trackguard import geometry_core as core
from trackguard.motion_bias_fusion import transition
from trackguard.spatial_reference_pairs import spatial_pairs
from trackguard.synthetic import references, render, body_pose

JOINT = dict(cameras_joint=3, joint_cameras='left+front+right')
def sample(t,seq,v=2.,w=0.):
    return dict(source_ns=t,log_ns=t,seq=seq,v_mps=v,wz_radps=w)

class GeometryTests(unittest.TestCase):
    def test_camera_pnp_recovers_body_with_rotated_translated_extrinsic(self):
        # Noncommuting rotations, nonzero lever arm and large world coordinates.
        twb = body_pose(8000.,-1200.,0.6)
        twb[:3,:3] = twb[:3,:3] @ cv2.Rodrigues(np.array([.1,-.08,0.]))[0]
        tbc = np.eye(4)
        tbc[:3,:3] = cv2.Rodrigues(np.array([.2,-.3,.4]))[0]
        tbc[:3,3] = [1.2,-.7,.9]
        twc = twb @ tbc
        origin = np.array([7990.,-1210.,0.])
        rng = np.random.default_rng(24)
        xc = rng.uniform([-3,-2,8],[3,2,25],(70,3))
        world = xc @ twc[:3,:3].T + twc[:3,3]
        k = np.array([[600.,0,376],[0,590,182],[0,0,1.]])
        uv = cv2.projectPoints(xc,np.zeros(3),np.zeros(3),k,np.zeros(5))[0]
        ok,rvec,tvec = cv2.solvePnP(world-origin,uv,k,np.zeros(5),flags=cv2.SOLVEPNP_EPNP)
        self.assertTrue(ok)
        rvec,tvec=cv2.solvePnPRefineLM(world-origin,uv,k,np.zeros(5),rvec,tvec)
        recovered=sg._body_from_local_pnp({'Tbc_inv':np.linalg.inv(tbc)},rvec,tvec,origin)
        np.testing.assert_allclose(recovered,twb,atol=1e-6)
        # This explicitly detects reporting the camera centre as the BODY origin.
        self.assertGreater(np.linalg.norm(recovered[:3,3]-twc[:3,3]),1.)

    def test_joint_body_projection_matches_independent_camera_projection(self):
        rng=np.random.default_rng(2)
        twb=body_pose(4.,-2.,.3)
        tbc=np.eye(4); tbc[:3,:3]=cv2.Rodrigues(np.array([.2,-.1,.15]))[0]
        tbc[:3,3]=[.8,-.3,1.1]
        xc=rng.uniform([-2,-1,5],[2,1,15],(40,3))
        twc=twb@tbc
        world=xc@twc[:3,:3].T+twc[:3,3]
        k=np.array([[500.,0,320],[0,510.,180],[0,0,1]])
        d=np.array([.01,-.002,.001,0.,0.])
        block=dict(X=world,Rbc=tbc[:3,:3],tbc=tbc[:3,3],K=k,D=d)
        _,good,pixels,_=rg._project_block(block,twb[:3,:3],twb[:3,3],.5)
        expected=cv2.projectPoints(xc,np.zeros(3),np.zeros(3),k,d)[0].reshape(-1,2)
        self.assertTrue(good.all())
        np.testing.assert_allclose(pixels,expected,atol=1e-9)

    def test_calibration_scaling_and_reflection_rejection(self):
        cal=dict(K=np.array([[800.,0,600],[0,900.,300],[0,0,1]]),
                 original_size=[1200,600],T_base_camera=np.eye(4))
        k,_,_,_=core._camera_calibration(cal,(300,600))
        np.testing.assert_allclose(k,[[400,0,300],[0,450,150],[0,0,1]])
        cal['T_base_camera'][0,0]=-1
        with self.assertRaisesRegex(ValueError,'proper rigid'):
            core._camera_calibration(cal,(300,600))

    def test_spatial_partners_cross_temporal_gap_without_cross_heading(self):
        p=np.full((45,3),np.nan)
        p[0]=[0,0,0]; p[20]=[7,0,0]; p[40]=[-7,0,0]; p[44]=[7,0,math.pi]
        pairs=spatial_pairs(p,np.isfinite(p).all(axis=1))
        self.assertEqual(pairs[0],[20,40])
        self.assertNotIn(44,pairs[0])

class GateTests(unittest.TestCase):
    def test_single_seed_no_later_reseed_and_no_single_camera_bypass(self):
        g=Gate()
        self.assertEqual(g.step(0,[0,0,0],'seed',{})[1],'gate_seed')
        self.assertIsNone(g.step(1,[99,99,0],'seed',{})[0])
        self.assertIsNone(g.step(2,[0,0,0],'rig_single_camera',JOINT)[0])
        self.assertIsNone(g.step(3,[0,0,0],'rig_joint',dict(cameras_joint=3,joint_cameras='a+a+b'))[0])
        self.assertIsNone(g.step(4,[0,0,0],'rig_joint',dict(cameras_joint=4,joint_cameras='a+b+c'))[0])
        self.assertIsNotNone(g.step(5,[0,0,0],'rig_joint',JOINT)[0])
        self.assertEqual(g.summary()['seed_passed'],1)
        with self.assertRaises(ValueError): g.step(5,[0,0,0],'rig_joint',JOINT)

    def test_late_seed_cannot_initialize_after_missing_row_zero(self):
        f=Fusion()
        self.assertIsNone(f.step(0,0,[],None,'rig_geometry_rejected',{})[0])
        self.assertIsNone(f.step(1,1,[],[0,0,0],'seed',{})[0])
        self.assertFalse(f.initialized)

class MotionTests(unittest.TestCase):
    def test_constant_turn_lever_arm_matches_closed_form(self):
        # Start BODY at [2,0]; control point at [0,0]. Quarter-circle motion.
        duration=1_000_000_000
        angle=math.pi/2
        out=transition(np.array([2.,0,0,0,0,0]),math.pi,angle,duration,(2.,0.))
        np.testing.assert_allclose(out[:3],[2.,4.,angle],atol=1e-10)
        reverse=transition(np.zeros(6),-3.,0.,duration,(0.,0.))
        np.testing.assert_allclose(reverse[:3],[-3,0,0],atol=1e-12)

    def run_prefix(self,extra_future=False):
        f=Fusion(); rows=[]
        for i in range(8):
            t=i*100_000_000
            controls=[sample(t,i)]
            if extra_future:
                controls.append(dict(source_ns=t+1_000_000_000,log_ns=t+1_000_000_000,
                                     seq=100+i,v_mps=-50.,wz_radps=1.9))
            pose=[t*1e-9*2,0,0]
            rows.append(f.step(t,t,controls,pose,'seed' if i==0 else 'rig_joint',{} if i==0 else JOINT))
        return rows,f

    def test_future_motion_cannot_change_published_prefix(self):
        a,fa=self.run_prefix(); b,fb=self.run_prefix(True)
        for aa,bb in zip(a,b):
            np.testing.assert_array_equal(aa[0],bb[0]); self.assertEqual(aa[1],bb[1])
        np.testing.assert_array_equal(fa.state[1],fb.state[1])
        np.testing.assert_array_equal(fa.state[2],fb.state[2])
        self.assertEqual(fb.samples['rejected_future_log'],8)

    def test_future_source_and_duplicate_rejected_stale_motion_loses_tracking(self):
        f=Fusion()
        f.step(0,0,[sample(0,0)],[0,0,0],'seed',{})
        future=sample(150_000_000,2); future['log_ns']=100_000_000
        _,_,d=f.step(100_000_000,100_000_000,[sample(0,0),future],None,'rig_geometry_rejected',{})
        self.assertEqual(d['fusion_samples_rejected_out_of_order'],1)
        self.assertEqual(d['fusion_samples_rejected_future_source'],1)
        p,status,_=f.step(400_000_000,400_000_000,[],None,'rig_geometry_rejected',{})
        self.assertIsNone(p); self.assertIn('lost',status)
        self.assertIsNone(f.state)
        self.assertEqual(f.loss['stale_control'],1)

    def test_lost_tracking_recovers_from_two_visual_fixes_without_truth_reseed(self):
        f=Fusion()
        f.step(0,0,[sample(0,0)],[0,0,0],'seed',{})
        f.step(800_000_000,800_000_000,[],None,'rig_geometry_rejected',{})
        self.assertIsNone(f.state)
        p,status,_=f.step(1_000_000_000,1_000_000_000,[],[2.,0,0],'rig_joint',JOINT)
        self.assertIsNone(p); self.assertEqual(status,'fusion_lost_recovery_pending')
        p,status,d=f.step(1_100_000_000,1_100_000_000,[],[2.2,0,0],'rig_joint',JOINT)
        self.assertEqual(status,'fusion_recovered')
        np.testing.assert_allclose(p,[2.2,0,0],atol=1e-12)
        self.assertTrue(d['fusion_recovery_motion_check'].startswith('unavailable_'))
        self.assertEqual(f.gate.summary()['seed_passed'],1)
        self.assertEqual(f.counts['bias_resets'],1)

    def test_visual_outlier_is_rejected_without_resetting_motion_state(self):
        f=Fusion()
        f.step(0,0,[sample(0,0)],[0,0,0],'seed',{})
        pose,status,diag=f.step(100_000_000,100_000_000,[sample(100_000_000,1)],
                                [20.,0,0],'rig_joint',JOINT)
        self.assertEqual(diag['fusion_visual_reject_reason'],'nis')
        self.assertIn('motion_predicted',status)
        np.testing.assert_allclose(pose,[.2,0,0],atol=1e-12)
        self.assertEqual(f.counts['bias_resets'],0)

class ImageIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.refs,cls.texture,cls.cal=references()
    def frames(self,x):
        return {c:render(self.texture,k,body_pose(x)) for c,k in self.cal.items()}

    def test_sift_map_to_joint_body_to_fusion_and_output_gate(self):
        engine=Localizer(copy.deepcopy(self.refs))
        engine.step(0,0,self.frames(0),{c:0 for c in self.cal},[sample(0,0,1.)],seed=[0,0,0])
        t=100_000_000
        row=engine.step(t,t,self.frames(.1),{c:t for c in self.cal},[sample(t,1,1.)])
        self.assertEqual(row.diagnostics['raw_geometry_status'],'rig_joint')
        self.assertEqual(row.diagnostics['cameras_joint'],3)
        self.assertEqual(row.diagnostics['fusion_visual_used'],1)
        np.testing.assert_allclose(row.pose,[.1,0,0],atol=.03)
        self.assertGreater(sum(m['counts']['valid_landmarks'] for m in engine._rig['models'].values()),30)
        self.assertLessEqual(row.diagnostics['fusion_pos_sd_m'],.20)
        # A long missing-image interval is unavailable, even if a motion estimate exists.
        for i in range(2,5):
            t=i*100_000_000
            row=engine.step(t,t,{}, {},[sample(t,i,1.)])
        self.assertGreater(row.diagnostics['fusion_pos_sd_m'],.20)
        self.assertIsNone(row.pose)
        self.assertEqual(row.status,'unavailable_nominal_uncertainty')
        self.assertIsNotNone(engine._fusion.state)  # withholding does not reset tracking
        with self.assertRaisesRegex(ValueError,'first row'):
            engine.step(500_000_000,500_000_000,{}, {},[],seed=[99,99,0])
        self.assertEqual(engine._fusion.gate.summary()['seed_passed'],1)

    def test_member_time_rejects_future_and_stale_camera_before_geometry(self):
        engine=Localizer(copy.deepcopy(self.refs)); t=100_000_000
        # No first seed: raw geometry may run but fusion must stay uninitialized.
        row=engine.step(t,t,self.frames(0),dict(left=t+1,front=t-1_000_001,right=t))
        self.assertEqual(row.diagnostics['cam_left_status'],'member_future_dropped')
        self.assertEqual(row.diagnostics['cam_front_status'],'member_outside_tolerance_dropped')
        self.assertEqual(row.diagnostics['cameras_used'],1)
        self.assertIsNone(row.pose)
        self.assertFalse(engine._fusion.initialized)
        with self.assertRaises(ValueError): engine.step(t,t,{}, {})
        with self.assertRaises(ValueError): engine.step(t+1,t+1,{}, {'right':1.5})

if __name__=='__main__': unittest.main()
