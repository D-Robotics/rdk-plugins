import struct,unittest
from x5_gamma_band_candidate import candidate
class GammaBand(unittest.TestCase):
 def setUp(self):
  self.b=bytearray(3044);self.b[4]=2;struct.pack_into('=2f',self.b,8,1.,2.)
  for row in range(2):struct.pack_into('=64H',self.b,88+128*row,*[round(92+(1023-92)*i/63) for i in range(64)])
  self.b=bytes(self.b)
 def test_known_profile_preserves_non_table_and_flags(self):
  out,r=candidate(self.b,.8,160,552);self.assertEqual(out[:88],self.b[:88]);self.assertEqual(out[344:],self.b[344:]);self.assertFalse(r['hardwareQualified']);self.assertFalse(r['qualityAccepted']);self.assertEqual(r['curves'][0]['new'][0],92)
 def test_monotone_and_preserve_outside(self):
  out,r=candidate(self.b,.6,160,552)
  for row in r['curves']:
   self.assertTrue(all(b>=a for a,b in zip(row['new'],row['new'][1:])));self.assertTrue(all(a==b for a,b in zip(row['old'],row['new']) if a<=160 or a>=552))
 def test_strength(self):
  for v in [0,1,-1,True,float('nan'),float('inf')]:
   with self.assertRaises(ValueError):candidate(self.b,v,160,552)
 def test_band(self):
  for lo,hi in [(160,160),(-1,552),(160,1024),(True,552),(160.,552)]:
   with self.assertRaises(ValueError):candidate(self.b,.8,lo,hi)
 def test_manual_mode(self):
  b=bytearray(self.b);struct.pack_into('=i',b,0,1)
  with self.assertRaises(ValueError):candidate(b,.8,160,552)
 def test_rows(self):
  for n in [0,21]:
   b=bytearray(self.b);b[4]=n
   with self.assertRaises(ValueError):candidate(b,.8,160,552)
 def test_gain_grid(self):
  b=bytearray(self.b);struct.pack_into('=f',b,12,1.)
  with self.assertRaises(ValueError):candidate(b,.8,160,552)
 def test_endpoint(self):
  b=bytearray(self.b);struct.pack_into('=H',b,88+126,4095)
  with self.assertRaises(ValueError):candidate(b,.8,160,552)
 def test_source_monotonicity(self):
  b=bytearray(self.b);struct.pack_into('=H',b,88,512)
  with self.assertRaises(ValueError):candidate(b,.8,160,552)
if __name__=='__main__':unittest.main()
