import copy,json,struct,unittest
from x5_gamma_band_candidate import candidate
from x5_gamma_vendor_candidate import render
class VendorGamma(unittest.TestCase):
 def setUp(self):
  b=bytearray(3044);b[4]=2;struct.pack_into('=2f',b,8,1.,2.)
  self.rows=[]
  for i in range(20):
   row=[round(92+931*j/63) for j in range(64)];self.rows.append(row);struct.pack_into('=64H',b,88+128*i,*row)
  self.source=bytes(b);self.requested=candidate(self.source,.8,160,552)[0]
  self.doc={'header':{'sentinel':'unchanged'},'tuning':{'GC_2':{'sentinel':1},'AGC_2':{'tables':[{'hdr':False,'gains':[1.,2.]+[0.]*18,'curve':self.rows},{'hdr':True,'sentinel':9}]}}}
 def run_render(self,doc=None,source=None,requested=None):return render(json.dumps(self.doc if doc is None else doc).encode(),self.source if source is None else source,self.requested if requested is None else requested)
 def test_only_active_cells_and_false_qualification(self):
  out,r=self.run_render();d=json.loads(out);self.assertNotEqual(d['tuning']['AGC_2']['tables'][0]['curve'][:2],self.rows[:2]);d['tuning']['AGC_2']['tables'][0]['curve']=self.rows;self.assertEqual(d,self.doc);self.assertFalse(r['reloadVerified']);self.assertFalse(r['qualityAccepted'])
 def test_duplicate_keys(self):
  with self.assertRaises(ValueError):render(b'{"tuning":{},"tuning":{}}',self.source,self.requested)
 def test_mismatch_source(self):
  d=copy.deepcopy(self.doc);d['tuning']['AGC_2']['tables'][0]['curve'][0][1]+=1
  with self.assertRaises(ValueError):self.run_render(d)
 def test_HDR(self):
  d=copy.deepcopy(self.doc);d['tuning']['AGC_2']['tables'][0]['hdr']=True
  with self.assertRaises(ValueError):self.run_render(d)
 def test_boolean_gain(self):
  d=copy.deepcopy(self.doc);d['tuning']['AGC_2']['tables'][0]['gains'][0]=True
  with self.assertRaises(ValueError):self.run_render(d)
 def test_gain_mismatch(self):
  d=copy.deepcopy(self.doc);d['tuning']['AGC_2']['tables'][0]['gains'][1]=3
  with self.assertRaises(ValueError):self.run_render(d)
 def test_unrelated_module_byte(self):
  b=bytearray(self.requested);b[-1]=1
  with self.assertRaises(ValueError):self.run_render(requested=bytes(b))
 def test_nonmonotone(self):
  b=bytearray(self.requested);struct.pack_into('=H',b,88,1023)
  with self.assertRaises(ValueError):self.run_render(requested=bytes(b))
 def test_noop(self):
  with self.assertRaises(ValueError):self.run_render(requested=self.source)
 def test_invalid_shape(self):
  d=copy.deepcopy(self.doc);d['tuning']['AGC_2']['tables'][0]['curve'].pop()
  with self.assertRaises(ValueError):self.run_render(d)
if __name__=='__main__':unittest.main()
