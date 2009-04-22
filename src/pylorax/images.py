#
# pylorax images module
# Install image and tree support data generation tool -- Python module
#

import datetime


class Images():

    def __init__(self, conf, yumconf, arch, imgdir, product, version, bugurl, output, noiso=False):
        self.conf = conf
        self.yumconf = yumconf

        self.arch = arch
        self.imgdir = imgdir
        self.product = product
        self.version = version
        self.bugurl = bugurl

        self.output = output
        self.noiso = noiso

        now = datetime.datetime.now()
        self.imageuuid = now.strftime('%Y%m%d%H%M') + '.' + os.uname()[4]

        self.initrdmods = self.__getModulesList()

        if self.arch == 'sparc64':
            self.basearch = 'sparc'
        else:
            self.basearch = self.arch

        self.libdir = 'lib'
        if self.arch == 'x86_64' or self.arch =='s390x':
            self.libdir = 'lib64'

        # explicit block size setting for some arches
        # FIXME we compose ppc64-ish trees as ppc, so we have to set the "wrong" block size
        # XXX i don't get this :)
        self.crambs = []
        if self.arch == 'sparc64':
            self.crambs = ['--blocksize', '8192']
        elif self.arch == 'sparc':
            self.crambs = ['--blocksize', '4096']

        self.__setUpDirectories()

    def __getModulesList(self):
        modules = set()

        modules_files = []
        modules_files.append(os.path.join(self.conf['confdir'], 'modules'))
        modules_files.append(os.path.join(self.conf['confdir'], self.arch, 'modules'))

        for pfile in modules_files:
            if os.path.isfile(pfile):
                f = open(pfile, 'r')
                for line in f.readlines():
                    line = line.strip()

                    if not line or line.startswith('#'):
                        continue

                    if line.startswith('-'):
                        modules.discard(line[1:])
                    else:
                        modules.add(line)

                f.close()

        modules = list(modules)
        modules.sort()

        return modules

    def __setUpDirectories(self):
        imagepath = os.path.join(self.output, 'images')
        fullmodpath = tempfile.mkdtemp('XXXXXX', 'instimagemods.', self.conf['tmpdir'])
        finalfullmodpath = os.path.join(self.output, 'modules')
        
        kernelbase = tempfile.mkdtemp('XXXXXX', 'updboot.kernel.', self.conf['tmpdir'])
        kernelname = 'vmlinuz'

        kerneldir = '/boot'
        if self.arch == 'ia64':
            kerneldir = os.path.join(kerneldir, 'efi', 'EFI', 'redhat')

        for dir in [imagepath, fullmodpath, finalfullmodpath, kernelbase]:
            if os.path.isdir(dir):
                shutil.rmtree(dir)
                os.makedirs(dir)

        self.imagepath = imagepath
        self.fullmodpath = fullmodpath
        self.finalfullmodpath = finalfullmodpath
        
        self.kernelbase = kernelbase
        self.kernelname = kernelname
        self.kerneldir = kerneldir


