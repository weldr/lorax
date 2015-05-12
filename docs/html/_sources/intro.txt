Introduction to Lorax
=====================

I am the Lorax.  I speak for the trees [and images].

Lorax is used to build the Anaconda Installer boot.iso, it consists of a
library, pylorax, a set of templates, and the lorax script. Its operation
is driven by a customized set of Mako templates that lists the packages
to be installed, steps to execute to remove unneeded files, and creation
of the iso for all of the supported architectures.






Before Lorax
============

Tree building tools such as pungi and revisor rely on 'buildinstall' in
anaconda/scripts/ to produce the boot images and other such control files
in the final tree.  The existing buildinstall scripts written in a mix of
bash and Python are unmaintainable.  Lorax is an attempt to replace them
with something more flexible.


EXISTING WORKFLOW:

pungi and other tools call scripts/buildinstall, which in turn call other
scripts to do the image building and data generation.  Here's how it
currently looks:

   -> buildinstall
       * process command line options
       * write temporary yum.conf to point to correct repo
       * find anaconda release RPM
       * unpack RPM, pull in those versions of upd-instroot, mk-images,
         maketreeinfo.py, makestamp.py, and buildinstall

       -> call upd-instroot

       -> call maketreeinfo.py

       -> call mk-images (which figures out which mk-images.ARCH to call)

       -> call makestamp.py

       * clean up


PROBLEMS:

The existing workflow presents some problems with maintaining the scripts.
First, almost all knowledge of what goes in to the stage 1 and stage 2
images lives in upd-instroot.  The mk-images* scripts copy things from the
root created by upd-instroot in order to build the stage 1 image, though
it's not completely clear from reading the scripts.


NEW IDEAS:

Create a new central driver with all information living in Python modules.
Configuration files will provide the knowledge previously contained in the
upd-instroot and mk-images* scripts.



