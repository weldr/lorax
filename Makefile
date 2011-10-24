PYTHON ?= /usr/bin/env python
DESTDIR ?= /

PKGNAME = lorax
VERSION = $(shell awk '/Version:/ { print $$2 }' $(PKGNAME).spec)
RELEASE = $(shell awk '/Release:/ { print $$2 }' $(PKGNAME).spec | sed -e 's|%.*$$||g')
TAG = r$(VERSION)-$(RELEASE)


default: all

src/pylorax/version.py: lorax.spec
	echo "num = '$(VERSION)-$(RELEASE)'" > src/pylorax/version.py

all: src/pylorax/version.py
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install --root=$(DESTDIR)

clean:
	-rm -rf build src/pylorax/version.py

tag:
	git tag -f $(TAG)

archive: tag
	@git archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ $(TAG) > $(PKGNAME)-$(VERSION).tar
	@bzip2 $(PKGNAME)-$(VERSION).tar
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.bz2"

local:
	@rm -rf $(PKGNAME)-$(VERSION).tar.bz2
	@rm -rf /tmp/$(PKGNAME)-$(VERSION)
	@dir=$$PWD; cp -a $$dir /tmp/$(PKGNAME)-$(VERSION)
	@rm -rf /tmp/$(PKGNAME)-$(VERSION)/.git
	@dir=$$PWD; cd /tmp; tar --bzip2 -cSpf $$dir/$(PKGNAME)-$(VERSION).tar.bz2 $(PKGNAME)-$(VERSION)
	@rm -rf /tmp/$(PKGNAME)-$(VERSION)
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.bz2"
