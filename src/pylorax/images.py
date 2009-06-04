# pylorax/images.py

import sys
import os

from utils.fileutil import cp, mv, rm, touch, replace

import initrd


class Images(object):
    def __init__(self, config, yum):
        self.conf = config
        self.yum = yum

        # XXX don't see this used anywhere... maybe in some other script, have to check...
        #syslinux = os.path.join(self.conf.treedir, 'usr', 'lib', 'syslinux', 'syslinux-nomtools')
        #if not os.path.isfile(syslinux):
        #    print('WARNING: %s does not exist' % syslinux)
        #    syslinux = os.path.join(self.conf.treedir, 'usr', 'bin', 'syslinux')
        #    if not os.path.isfile(syslinux):
        #        print('ERROR: %s does not exist' % syslinux)
        #        sys.exit(1)

    def run(self):
        self.prepareBootTree()

    def prepareBootTree(self):
        i = initrd.InitRD(self.conf, self.yum)
        pkgs = i.getPkgs()

        # install needed packages
        self.yum.addPackages(['anaconda', 'anaconda-runtime', 'kernel', 'syslinux', 'memtest'])
        self.yum.addPackages(pkgs)
        self.yum.install()

        # create the destination directories
        self.imgdir = os.path.join(self.conf.outdir, 'images')
        if os.path.exists(self.imgdir):
            rm(self.imgdir)
        self.pxedir = os.path.join(self.imgdir, 'pxeboot')
        os.makedirs(self.imgdir)
        os.makedirs(self.pxedir)

        # write the images/README
        f = open(os.path.join(self.imgdir, 'README'), 'w')
        f.write('This directory contains image files that can be used to create media\n'
                'capable of starting the %s installation process.\n\n' % self.conf.product)
        f.write('The boot.iso file is an ISO 9660 image of a bootable CD-ROM. It is useful\n'
                'in cases where the CD-ROM installation method is not desired, but the\n'
                'CD-ROM\'s boot speed would be an advantage.\n\n')
        f.write('To use this image file, burn the file onto CD-R (or CD-RW) media as you\n'
                'normally would.\n')
        f.close()

        # write the images/pxeboot/README
        f = open(os.path.join(self.pxedir, 'README'), 'w')
        f.write('The files in this directory are useful for booting a machine via PXE.\n\n')
        f.write('The following files are available:\n')
        f.write('vmlinuz - the kernel used for the installer\n')
        f.write('initrd.img - an initrd with support for all install methods and\n')
        f.write('             drivers supported for installation of %s\n' % self.conf.product)
        f.close()

        # set up some dir variables for further use
        anacondadir = os.path.join(self.conf.treedir, 'usr', 'lib', 'anaconda-runtime')
        bootdiskdir = os.path.join(anacondadir, 'boot')
        syslinuxdir = os.path.join(self.conf.treedir, 'usr', 'lib', 'syslinux')

        isolinuxbin = os.path.join(syslinuxdir, 'isolinux.bin')
        if os.path.isfile(isolinuxbin):
            print('Creating the isolinux directory...')
            self.isodir = os.path.join(self.conf.outdir, 'isolinux')
            if os.path.exists(self.isodir):
                rm(self.isodir)
            os.makedirs(self.isodir)

            # copy the isolinux.bin to isolinux dir
            cp(isolinuxbin, self.isodir)

            # copy the syslinux.cfg to isolinux/isolinux.cfg
            isolinuxcfg = os.path.join(self.isodir, 'isolinux.cfg')
            cp(os.path.join(bootdiskdir, 'syslinux.cfg'), isolinuxcfg)

            # set the product and version in isolinux.cfg
            replace(isolinuxcfg, r'@PRODUCT@', self.conf.product)
            replace(isolinuxcfg, r'@VERSION@', self.conf.version)

            # copy the grub.conf to isolinux dir
            cp(os.path.join(bootdiskdir, 'grub.conf'), self.isodir)

            # create the initrd in isolinux dir
            i.getDeps()
            i.processActions()
            i.create(os.path.join(self.isodir, 'initrd.img'))
            i.cleanUp()

            # copy the vmlinuz to isolinux dir
            vmlinuz = os.path.join(self.conf.treedir, 'boot', 'vmlinuz-*')
            cp(vmlinuz, os.path.join(self.isodir, 'vmlinuz'))

            # copy the splash files to isolinux dir
            vesasplash = os.path.join(anacondadir, 'syslinux-vesa-splash.jpg')
            if os.path.isfile(vesasplash):
                cp(vesasplash, os.path.join(self.isodir, 'splash.jpg'))
                vesamenu = os.path.join(syslinuxdir, 'vesamenu.c32')
                cp(vesamenu, self.isodir)
                replace(isolinuxcfg, r'default linux', r'default vesamenu.c32')
                replace(isolinuxcfg, r'prompt 1', r'#prompt 1')
            else:
                splashtools = os.path.join(anacondadir, 'splashtools.sh')
                splashlss = os.path.join(bootdiskdir, 'splash.lss')
                if os.path.isfile(splashtools):
                    os.system('%s %s %s' % (splashtools,
                                            os.path.join(bootdiskdir, 'syslinux-splash.jpg'),
                                            splashlss))
                if os.path.isfile(splashlss):
                    cp(splashlss, self.isodir)

            # copy the .msg files to isolinux dir
            for file in os.listdir(bootdiskdir):
                if file.endswith('.msg'):
                    cp(os.path.join(bootdiskdir, file), self.isodir)
                    replace(os.path.join(self.isodir, file), r'@VERSION@', self.conf.version)

            # if present, copy the memtest to isolinux dir
            # XXX search for it in bootdiskdir or treedir/install/boot ?
            #cp(os.path.join(bootdiskdir, 'memtest*'), os.path.join(self.isodir, 'memtest'))
            cp(os.path.join(self.conf.treedir, 'boot', 'memtest*'),
                            os.path.join(self.isodir, 'memtest'))
            if os.path.isfile(os.path.join(self.isodir, 'memtest')):
                f = open(isolinuxcfg, 'a')
                f.write('label memtest86\n')
                f.write('  menu label ^Memory test\n')
                f.write('  kernel memtest\n')
                f.write('  append -\n')
                f.close()
        else:
            print('No isolinux binary found, skipping isolinux creation')
