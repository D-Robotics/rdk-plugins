import sys,time,threading,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from continuous_frame_pump import FramePump
class Harness:
 def __init__(self):self.n=0;self.owners=[];self.fail=False
 def next(self):
  self.owners.append(threading.get_ident());time.sleep(.003)
  if self.fail:raise ValueError('fixture_native_failed')
  self.n+=1;return {'frame_id':self.n,'timestamp_ns':self.n*1000000}
 def meta(self,stage):return {'frame':self.next(),'stage':stage}
 def picture(self,stage):return b'copied-fixture',self.next()
class Tests(unittest.TestCase):
 def test_continuous_dequeues_during_slow_analysis_and_disk_fixture(self):
  h=Harness();p=FramePump(h.meta,h.picture).start()
  try:
   a=p.take('first')['frame']['frame_id'];before=h.n;time.sleep(.08);after=h.n;self.assertGreaterEqual(after-before,5);blob,info=p.picture();self.assertEqual(blob,b'copied-fixture');self.assertGreater(info['frame_id'],a);b=p.take('after-picture')['frame'];self.assertGreater(b['frame_id'],info['frame_id'])
  finally:r=p.stop()
  self.assertTrue(r['joined']);self.assertEqual(len(set(h.owners)),1);self.assertNotEqual(h.owners[0],threading.get_ident())
 def test_native_failure_propagates_and_stops(self):
  h=Harness();p=FramePump(h.meta,h.picture).start();p.take('first');h.fail=True;time.sleep(.02)
  try:
   with self.assertRaisesRegex(ValueError,'fixture_native_failed'):p.take('fail')
  finally:r=p.stop()
  self.assertIn('fixture_native_failed',r['error'])
 def test_duplicate_identity_is_rejected(self):
  p=FramePump(lambda s:{'frame':{'frame_id':1,'timestamp_ns':1}},lambda s:(b'',{'frame_id':1,'timestamp_ns':1})).start();time.sleep(.02)
  try:
   with self.assertRaisesRegex(ValueError,'identity_not_new'):p.take('duplicate')
  finally:p.stop()
 def test_no_requests_after_join(self):
  h=Harness();p=FramePump(h.meta,h.picture).start();p.take('first');p.stop()
  with self.assertRaisesRegex(RuntimeError,'stopping'):p.picture()
if __name__=='__main__':unittest.main()
