"""GPU fallback and mixed-capability adapter regressions."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import modeshift as app

class GpuFallbackTests(unittest.TestCase):
    def test_windows_counter_payload(self):
        with patch.object(app,'on_windows',return_value=True), patch.object(app,'run',return_value='{"names":["AMD Radeon RX 7800 XT"],"engine_peak":72.4}'):
            rows=app.windows_gpu_fallback()
        self.assertEqual(rows[0]['name'],'AMD Radeon RX 7800 XT')
        self.assertEqual(rows[0]['utilization'],72.4)
        self.assertIsNone(rows[0]['temp_c'])

    def test_detection_without_counter(self):
        with patch.object(app,'on_windows',return_value=True), patch.object(app,'run',return_value='{"names":"Intel Arc A770","engine_peak":null}'):
            rows=app.windows_gpu_fallback()
        self.assertEqual(rows[0]['name'],'Intel Arc A770')
        self.assertIsNone(rows[0]['utilization'])

    def test_unavailable_vram_does_not_trigger_false_warning(self):
        payload={'ram_percent':50,'ram_available_gib':12,'gpus':[{'name':'Intel Arc','utilization':None,'vram_total_mib':None,'vram_used_mib':None}], 'workloads':[]}
        result=app.recommendations(payload)
        self.assertEqual(result[0][0],'System load overview')

    def test_nvidia_supports_missing_metric(self):
        with patch.object(app.shutil,'which',return_value='nvidia-smi'), patch.object(app,'run',return_value='GeForce RTX 4080, 96, 12000, 16376, N/A'):
            gpu=app.gpu_metrics()
        self.assertEqual(gpu[0]['utilization'],96)
        self.assertIsNone(gpu[0]['temp_c'])

if __name__=='__main__':unittest.main()
