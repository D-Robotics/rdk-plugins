import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import cv2,numpy as np
from tone_region_observation import analyze
class ToneTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.images=[]
  for i in range(9):
   im=np.full((64,64,3),180,np.uint8);im[:32,:32]=100;cv2.circle(im,(16,16),3,(255,255,255),-1);im[32:52,40:60:2]=80
   if 3<=i<6:im=(im.astype(float)*.8).astype(np.uint8)
   ok,b=cv2.imencode('.png',im);assert ok;name=f'{i}.png';(self.root/name).write_bytes(b);self.images.append({'name':name,'sha256':hashlib.sha256(b).hexdigest(),'frame':{'width':64,'height':64,'frame_id':0,'timestamp_ns':i+1}})
  self.receipt={'resourceReleaseVerified':True,'ispOriginalsRestored':True,'streamObservedAndReleased':True,'images':self.images}
  self.m={'schema':'camera-tone-region-observation-v1','groups':dict(zip(('baseline','candidate','restored'),[[f'{i}.png' for i in range(j,j+3)] for j in (0,3,6)])),'roi':{'paper':dict(x=40,y=0,width=20,height=20),'letters':dict(x=40,y=32,width=20,height=20),'lamp':dict(x=0,y=0,width=32,height=32)},'ringPixels':[1,6],'farPixels':[8,13]};self.bind()
 def bind(self):
  b=json.dumps(self.receipt).encode();(self.root/'receipt.json').write_bytes(b);self.m['receipt']={'file':'receipt.json','sha256':hashlib.sha256(b).hexdigest()}
 def test_observation_not_acceptance(self):
  r=analyze(self.m,self.root);self.assertAlmostEqual(r['changes'][0]['paperMeanRatio'],.8);self.assertEqual(r['changes'][1]['paperMeanRatio'],1);self.assertTrue(all(x['frame']['frame_id']==0 for x in r['frames']));self.assertFalse(r['qualityAccepted']);self.assertFalse(r['opticalHaloFixed'])
 def test_tamper(self):
  (self.root/'0.png').write_bytes(b'tamper')
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_stale_timestamp(self):
  self.images[4]['frame']['timestamp_ns']=4;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_unrestored(self):
  self.receipt['ispOriginalsRestored']=False;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_duplicate(self):
  self.m['groups']['candidate'][0]='0.png'
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_geometry(self):
  self.m['roi']['paper']['width']=80
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_dimensions(self):
  self.images[0]['frame']['width']=63;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_escape(self):
  self.m['receipt']['file']='../receipt.json'
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_missing_lamp(self):
  self.m['lampCoreThreshold']=254;self.m['roi']['lamp']=self.m['roi']['paper']
  with self.assertRaises(ValueError):analyze(self.m,self.root)
if __name__=='__main__':unittest.main()
