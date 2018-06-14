import io
import unittest
from unittest.mock import patch

from pylorax import buildstamp

class BuildStampTestCase(unittest.TestCase):
    def setUp(self):
        self.bstamp = buildstamp.BuildStamp(
            'Lorax Tests',
            '0.1',
            'https://github.com/rhinstaller/lorax/issues',
            True,
            'noarch',
            'Server'
        )

    def test_write_produces_file_with_expected_content(self):
        out_file = io.StringIO()
        with patch.object(out_file, 'close'):
            with patch.object(buildstamp, 'open', return_value=out_file):
                self.bstamp.write('/tmp/stamp.ini')
                self.assertIn("[Main]\nProduct=Lorax Tests\nVersion=0.1\nBugURL=https://github.com/rhinstaller/lorax/issues\nIsFinal=True\n", out_file.getvalue())
                # Skip UUID which is between IsFinal and Variant
                try:
                    import pylorax.version
                except ImportError:
                    self.assertIn("Variant=Server\n[Compose]\nLorax=devel", out_file.getvalue())
                else:
                    self.assertIn("Variant=Server\n[Compose]\nLorax=" + pylorax.version.num, out_file.getvalue())
