from distutils.core import setup
import glob
import os

main_etc_files = []
for comp in glob.glob(os.path.join(os.getcwd(), 'etc', '*')):
    if os.path.isfile(comp):
        main_etc_files.append(comp)

etc_data_files = [(os.path.join('etc', 'lorax'), main_etc_files)]

for comp in glob.glob(os.path.join(os.getcwd(), 'etc', '*')):
    if os.path.isdir(comp):
        sub_files = glob.glob(os.path.join(comp, '*'))
        etc_path = os.path.join('etc', 'lorax', os.path.basename(comp))
        etc_data_files.append((etc_path, sub_files))

data_files = [(os.path.join('usr', 'share', 'lorax'),
               glob.glob(os.path.join('share', '*')))] + etc_data_files

setup(name='lorax',
      version='0.1',
      description='Boot image build tool',
      author='David Cantrell',
      author_email='dcantrell@redhat.com',
      license='GPLv2+',
      package_dir = {'': 'src'},
      packages = ['pylorax'],
      scripts = ['src/bin/lorax'],
      data_files = data_files
     )
