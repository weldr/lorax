Product and Updates Images
==========================

Lorax now supports creation of product.img and updates.img as part of the build
process. This is implemented using the installimg template command which will
take the contents of a directory and create a compressed archive from it. The
directory must be created by one of the packages installed by
runtime-install.tmpl or by passing ``--installpkgs <pkgname>`` to lorax at
runtime.  The x86, ppc, ppc64le and aarch64 templates all look for
/usr/share/lorax/product/ and /usr/share/lorax/updates/ directories in the
install chroot while creating the final install tree. If there are files in
those directories lorax will create images/product.img and/or
images/updates.img

These archives are just like an anaconda updates image -- their contents are
copied over the top of the filesystem at boot time so that you can drop in
files to add to or replace anything on the filesystem.

Anaconda has several places that it looks for updates, the one for product.img
is in /run/install/product.  So for example, to add an installclass to Anaconda
you would put your custom class here:

``/usr/share/lorax/product/run/install/product/pyanaconda/installclasses/custom.py``

If the packages containing the product/updates files are not included as part
of normal dependencies you can add specific packages with the ``--installpkgs``
command or the installpkgs paramater of :class:`pylorax.treebuilder.RuntimeBuilder`
