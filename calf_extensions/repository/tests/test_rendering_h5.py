"""Literal project contents must survive portal/offline template rendering."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from .. import viewer

class RenderingH5(unittest.TestCase):
    def test_source_template_tokens_and_script_boundaries_roundtrip(self):
        text='/*BOOTSTRAP*/\n/*STYLE*/\n/*SCRIPT*/\n</script><script>window.H5_ATTACK=true</script>\n한글\u2028\u2029'
        expected={'mode':'offline','sources':{'source:right':{'text':text}},'payload':{'example':text}}
        rendered=viewer.html(expected)
        serialized=rendered.split('window.CALF_PORTAL=',1)[1].split(';</script>',1)[0]
        self.assertEqual(json.loads(serialized),expected)
        self.assertNotIn('</script><script>window.H5_ATTACK',rendered)
    def test_inserted_asset_markers_are_literal_not_recursive_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            assets=Path(directory);template='<style>/*STYLE*/</style><script>/*BOOTSTRAP*/</script><script>/*SCRIPT*/</script>'
            (assets/'portal.html').write_text(template);(assets/'portal.css').write_text('/*BOOTSTRAP*/\n/*SCRIPT*/');(assets/'portal.js').write_text('const marker="/*STYLE*/";')
            with patch.object(viewer,'ASSETS',assets):rendered=viewer.html({'mode':'offline'})
            self.assertEqual(rendered,'<style>/*BOOTSTRAP*/\n/*SCRIPT*/</style><script>window.CALF_PORTAL={"mode": "offline"};</script><script>const marker="/*STYLE*/";</script>')
