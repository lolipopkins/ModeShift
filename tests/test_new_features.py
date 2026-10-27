import sys, tempfile, unittest, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import updater, modeshift
class NewFeatureTests(unittest.TestCase):
 def test_themes(self):
  self.assertGreaterEqual(len(modeshift.THEMES),5)
  for name in modeshift.THEMES:
   modeshift.use_theme(name)
   self.assertTrue(modeshift.ACC.startswith('#'))
 def test_installer_script(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);exe=root/'ModeShift.exe';setup=root/'ModeShiftSetup.exe'
   exe.write_bytes(b'MZapplication');setup.write_bytes(b'MZsetup')
   sha=hashlib.sha256(setup.read_bytes()).hexdigest()
   text=updater.make_installer_script(exe,setup,sha,123,root).read_text()
   self.assertIn('/VERYSILENT',text)
   self.assertIn('Get-FileHash',text)
   self.assertIn('Start-Process -FilePath $exe',text)
 def test_invalid_installer_hash(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'ModeShift.exe';setup=Path(d)/'setup.exe';exe.touch();setup.touch()
   with self.assertRaises(ValueError):updater.make_installer_script(exe,setup,'bad',3,d)
if __name__=='__main__':unittest.main()
