import distutils
import glob

distutils.core.setup(name='lorax',
                     version='0.1',
                     description='Boot image build tool',
                     author='David Cantrell',
                     author_email='dcantrell@redhat.com',
                     license='GPLv2+',
                     package_dir = {'': 'src'},
                     packages = ['pylorax'],
                     scripts = ['src/bin/lorax.py'],
                     data_files = [('/usr/share/lorax', glob.glob('share/*'),
                                   ('/etc/lorax', glob.glob('etc/*')]
                    )
