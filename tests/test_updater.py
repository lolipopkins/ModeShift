import sys, tempfile, unittest, hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import updater
class UpdateTests(unittest.TestCase):
    def test_versions(self):
        self.assertTrue(updater.version_parts('0.7')>updater.version_parts(updater.VERSION))
        with self.assertRaises(ValueError):updater.version_parts('v0.6-beta')
    def test_https_only(self):
        for url in ('http://example.com/x','file:///tmp/evil','https://u:p@example.com/a','https://example.com:444/a'):
            with self.assertRaises(ValueError):updater.safe_https(url)
        self.assertEqual(updater.safe_https('https://example.com/update.json'),'https://example.com/update.json')
    def test_replacement_script(self):
        with tempfile.TemporaryDirectory() as d:
            directory=Path(d);app=directory/'ModeShift.exe';stage=directory/'update.exe'
            app.write_bytes(b'MZold');stage.write_bytes(b'MZnew')
            digest=hashlib.sha256(stage.read_bytes()).hexdigest()
            script=updater.make_replacement_script(app,stage,digest,1,directory)
            self.assertIn('Get-FileHash',script.read_text())
            self.assertIn('previous.exe',script.read_text())
if __name__=='__main__':unittest.main()
