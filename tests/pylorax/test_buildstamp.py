import io
import unittest
from mock import patch

from pylorax import buildstamp

class BuildStampTestCase(unittest.TestCase):
    def setUp(self):
        self.bstamp = buildstamp.BuildStamp(
            'Lorax Tests',
            '0.1',
            'https://github.com/rhinstaller/lorax/issues',
            True,
            'noarch'
        )

    def test_write_produces_file_with_expected_content(self):
        out_file = io.StringIO()
        # io.StringIO.write accepts unicode,
        # but on Python 2 BuildStamp.write() passes strings to this method
        out_file.orig_write = out_file.write
        out_file.write = lambda s: out_file.orig_write(unicode(s))

        with patch.object(out_file, 'close'):
            with patch('pylorax.buildstamp.open', create=True, return_value=out_file):
                self.bstamp.write('/tmp/stamp.ini')
                self.assertIn("[Main]\nProduct=Lorax Tests\nVersion=0.1\nBugURL=https://github.com/rhinstaller/lorax/issues\nIsFinal=True", out_file.getvalue())
                self.assertIn("[Compose]\nLorax=devel", out_file.getvalue())
