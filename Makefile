PYTHON ?= /usr/bin/env python


all:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install

clean:
	-rm -rf build
