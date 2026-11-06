"""Small contract tests; native verification is in verify.py."""
import copy
from pathlib import Path
import unittest
from .common import profile, candidate, MediaError
from .project import name

BASE={'width':320,'height':180,'fps':25,'startMs':0,'durationMs':1000,
      'audio':True,'maxBlackMs':100,'maxSilenceMs':100}

class ContractTests(unittest.TestCase):
    def test_rejects_unbounded_or_ambiguous_profiles(self):
        for field,value in [('width',1920),('height',181),('fps',True),('durationMs',1001),
                            ('durationMs',31000),('startMs',-1),('audio',1),('maxBlackMs',0),
                            ('maxSilenceMs',float('nan'))]:
            with self.subTest(field=field,value=value),self.assertRaises(MediaError):
                p=copy.deepcopy(BASE);p[field]=value;profile(p)
        with self.assertRaises(MediaError):profile({**BASE,'extraFlags':'-y'})
        with self.assertRaises(MediaError):profile({**BASE,'audio':False})
        self.assertEqual(profile(BASE),BASE)

    def test_ids_are_safe_on_supported_desktop_platforms(self):
        for value in ['../scene','a/b','','CON','lpt1','scene:1']:
            with self.subTest(value=value),self.assertRaises(MediaError):name(value)
        self.assertEqual(name('scene-3'),'scene-3')

    def test_candidate_cannot_escape_or_overwrite(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory).resolve()
            for value in ['../outside.mp4','/outside.mp4','a\\b.mp4']:
                with self.subTest(value=value),self.assertRaises(MediaError):candidate(root,value)
            (root/'video.mp4').write_bytes(b'original')
            with self.assertRaises(MediaError):candidate(root,'video.mp4')
            self.assertEqual((root/'video.mp4').read_bytes(),b'original')

if __name__=='__main__':unittest.main()
