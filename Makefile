# Makefile for lorax

PYTHON  ?= /usr/bin/python
DESTDIR ?= /

all:
	$(PYTHON) setup.py build

install:
	$(PYTHON) setup.py install --root $(DESTDIR)

clean:
	-rm -rf build
	-git clean -d -x -f
