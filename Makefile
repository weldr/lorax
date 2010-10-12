PYTHON ?= /usr/bin/env python


all:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install

clean:
	-rm -rf build

test:
	/usr/bin/lorax -p FEDORA -v RAWHIDE -r 2010 -s /rawrepo /root/rawhide
