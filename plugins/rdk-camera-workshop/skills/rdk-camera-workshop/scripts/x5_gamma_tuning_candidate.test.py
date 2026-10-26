import copy,unittest
from x5_gamma_tuning_candidate import tuning_candidate
class TypedGamma(unittest.TestCase):
 def setUp(self):
  curve=[round(92+931*i/63) for i in range(64)];self.source={'kind':'x5-hbn-isp-v2','snapshotId':'a'*32,'layoutHash':'b'*64,'modules':{'gamma':{'mode':0,'auto_attr.auto_level':2,'auto_attr.gain':[1.,2.]+[0.]*18,'auto_attr.curve':curve*2+[0]*1152,'manual_attr.standard':0},'cproc':{'unchanged':7}}}
 def run_candidate(self,s=None,lo=160,hi=552):return tuning_candidate(self.source if s is None else s,.8,lo,hi)
 def test_only_full_auto_array_changes_and_input_untouched(self):
  before=copy.deepcopy(self.source);out,r=self.run_candidate();self.assertEqual(before,self.source);self.assertNotEqual(out['modules']['gamma']['auto_attr.curve'],before['modules']['gamma']['auto_attr.curve']);out['modules']['gamma']['auto_attr.curve']=before['modules']['gamma']['auto_attr.curve'];self.assertEqual(out,before);self.assertFalse(r['candidateRegistered']);self.assertFalse(r['hardwareQualified'])
 def test_readonly_grid_and_inactive_rows_preserved(self):
  out,_=self.run_candidate();self.assertEqual(out['modules']['gamma']['auto_attr.gain'],self.source['modules']['gamma']['auto_attr.gain']);self.assertEqual(out['modules']['gamma']['auto_attr.curve'][128:],self.source['modules']['gamma']['auto_attr.curve'][128:])
 def test_missing_full_descriptor(self):
  s=copy.deepcopy(self.source);del s['modules']['gamma']['auto_attr.curve']
  with self.assertRaises(ValueError):self.run_candidate(s)
 def test_non_common_rows(self):
  s=copy.deepcopy(self.source);s['modules']['gamma']['auto_attr.curve'][65]+=1
  with self.assertRaisesRegex(ValueError,'common_active'):self.run_candidate(s)
 def test_mode_and_binding(self):
  for key,value in [('mode',1),('mode',False),('auto_attr.auto_level',True)]:
   s=copy.deepcopy(self.source);s['modules']['gamma'][key]=value
   with self.assertRaises(ValueError):self.run_candidate(s)
  s=copy.deepcopy(self.source);s['snapshotId']='old'
  with self.assertRaises(ValueError):self.run_candidate(s)
 def test_wrong_count_and_fraction(self):
  for values in [[0]*1279,[.5]*1280]:
   s=copy.deepcopy(self.source);s['modules']['gamma']['auto_attr.curve']=values
   with self.assertRaises(ValueError):self.run_candidate(s)
 def test_endpoint_changed_by_band_is_refused(self):
  with self.assertRaisesRegex(ValueError,'endpoints'):self.run_candidate(lo=0,hi=552)
 def test_nonfinite_untouched_module_refused(self):
  s=copy.deepcopy(self.source);s['modules']['cproc']['unchanged']=float('inf')
  with self.assertRaises(ValueError):self.run_candidate(s)
if __name__=='__main__':unittest.main()
