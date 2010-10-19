PYTHON ?= /usr/bin/env python


all:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install

clean:
	-rm -rf build

testlocal:
	/usr/bin/lorax -p FEDORA -v RAWHIDE -r 2010 -s /rawrepo /root/rawhide

test:
	/usr/bin/lorax -p FEDORA -v RAWHIDE -r 2010 -s http://download.englab.brq.redhat.com/pub/fedora/linux/development/rawhide/x86_64/os/ /root/rawhide
