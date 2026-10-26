import copy,hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from raw_isp_edge_observation import analyze
class EdgeTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.frames=[]
  profile=np.clip(110+(np.arange(64)-24)*9,110,200).astype('<u2');raw=np.tile(profile,(32,1)).tobytes();nv=(np.tile((profile//2).astype('u1'),(32,1)).tobytes()+bytes([128])*(64*16))
  for i in range(3):
   meta={'width':64,'height':32,'stride_y':128,'stride_uv':0,'size_y':4096,'size_uv':0,'bit_depth':10,'bayer':0xffffffff,'packing':0,'alignment':0,'frame_id':0,'timestamp_ns':10*(i+1)}
   isp={**meta,'stride_y':64,'stride_uv':64,'size_y':2048,'size_uv':1024,'bit_depth':8,'bayer':0,'packing':3}
   name=f'{i}.raw';pair=f'{i}.nv12';(self.root/name).write_bytes(raw);(self.root/pair).write_bytes(nv)
   c={n:{'sdkCode':0,'values':{'mode':1,'fixtureValue':1.}} for n in ['exposure','awb']}
   self.frames.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'nativeCode':0,'frame':meta,'ispPair':{'name':pair,'sha256':hashlib.sha256(nv).hexdigest(),'frame':isp,'sdkTimestampMatched':True},'controlReadbackBefore':copy.deepcopy(c),'controlReadbackAfter':copy.deepcopy(c)})
  self.receipt={**{k:True for k in ['rawBytesPersisted','resourceReleaseVerified','ispOriginalsRestored','diagnosticRawSnapshotsComplete','streamObservedAndReleased']},'rawTransportVerified':False,'rawBayerQualified':False,'rawCalls':3,'rawFrames':self.frames}
  self.m={'schema':'camera-raw-isp-edge-observation-v1','rawNames':[f'{i}.raw' for i in range(3)],'edges':[{'name':'synthetic-ramp','x':[16,44],'y':[0,32],'dark':[20,24],'bright':[36,42]}]};self.bind()
 def bind(self):
  b=json.dumps(self.receipt).encode();(self.root/'receipt.json').write_bytes(b);self.m['receipt']={'file':'receipt.json','sha256':hashlib.sha256(b).hexdigest()}
 def test_profiles_without_acceptance(self):
  a=analyze(self.m,self.root);self.assertAlmostEqual(a['summary'][0]['medianObservedCodeWidth'],8.);self.assertEqual(len(a['profiles']),12);self.assertEqual(a['selectedEvidence'][0]['rawFrame']['frame_id'],0);self.assertFalse(a['mtfQualified']);self.assertFalse(a['qualityAccepted']);self.assertFalse(a['opticalFocusCauseQualified'])
 def test_no_recovery(self):
  self.receipt['ispOriginalsRestored']=False;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_timestamp_offset(self):
  self.frames[1]['ispPair']['frame']['timestamp_ns']+=1;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_stale_actual_timestamp(self):
  self.frames[1]['frame']['timestamp_ns']=10;self.frames[1]['ispPair']['frame']['timestamp_ns']=10;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_hash_tamper(self):
  (self.root/'0.raw').write_bytes(bytes(4096))
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_roi_outside(self):
  self.m['edges'][0]['y']=[0,34]
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_control_drift(self):
  self.frames[1]['controlReadbackAfter']['exposure']['values']['fixtureValue']=2.;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_layout(self):
  self.frames[0]['frame']['alignment']=1;self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_sample_range(self):
  f=self.root/'0.raw';a=np.frombuffer(f.read_bytes(),'<u2').copy();a[0]=1024;f.write_bytes(a.tobytes());self.frames[0]['sha256']=hashlib.sha256(f.read_bytes()).hexdigest();self.bind()
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_escape(self):
  self.m['receipt']['file']='../receipt.json'
  with self.assertRaises(ValueError):analyze(self.m,self.root)
 def test_too_few_plateau_samples(self):
  self.m['edges'][0]['dark']=[20,22]
  with self.assertRaises(ValueError):analyze(self.m,self.root)
if __name__=='__main__':unittest.main()
