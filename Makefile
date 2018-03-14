PYTHON ?= /usr/bin/python
DESTDIR ?= /

PKGNAME = lorax
VERSION = $(shell awk '/Version:/ { print $$2 }' $(PKGNAME).spec)
RELEASE = $(shell awk '/Release:/ { print $$2 }' $(PKGNAME).spec | sed -e 's|%.*$$||g')
TAG = lorax-$(VERSION)-$(RELEASE)
PW_DIR ?= $(shell pwd)
USER_SITE_PACKAGES ?= $(shell sudo $(PYTHON) -m site --user-site)


default: all

src/composer/version.py: lorax.spec
	echo "num = '$(VERSION)-$(RELEASE)'" > src/composer/version.py

src/pylorax/version.py: lorax.spec
	echo "num = '$(VERSION)-$(RELEASE)'" > src/pylorax/version.py

all: src/pylorax/version.py src/composer/version.py
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install --root=$(DESTDIR)
	mkdir -p $(DESTDIR)/$(mandir)/man1
	install -m 644 docs/man/lorax.1 $(DESTDIR)/$(mandir)/man1
	install -m 644 docs/man/livemedia-creator.1 $(DESTDIR)/$(mandir)/man1

check:
	@echo "*** Running pylint ***"
	PYTHONPATH=$(PYTHONPATH):./src/ ./tests/pylint/runpylint.py

# /api/docs/ tests require we have the documentation already built
test: docs
	@echo "*** Running tests ***"
	sudo mkdir -p $(USER_SITE_PACKAGES)
	sudo cp ./tests/usercustomize.py $(USER_SITE_PACKAGES)
	sudo COVERAGE_PROCESS_START=$(PW_DIR)/.coveragerc PYTHONPATH=$(PYTHONPATH):./src/ \
			$(PYTHON) -m nose -v ./src/pylorax/ ./src/composer/ ./tests/pylorax/ ./tests/composer/
	sudo rm -rf $(USER_SITE_PACKAGES)

	coverage combine
	coverage report -m
	[ -f "/usr/bin/coveralls" ] && [ -n "$(COVERALLS_REPO_TOKEN)" ] && coveralls || echo

clean:
	-rm -rf build src/pylorax/version.py
	-rm -rf build src/composer/version.py

tag:
	git tag -f $(TAG)

docs:
	$(MAKE) -C docs apidoc html

archive: tag
	@git archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ $(TAG) > $(PKGNAME)-$(VERSION).tar
	@gzip $(PKGNAME)-$(VERSION).tar
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.gz"

local:
	@rm -rf $(PKGNAME)-$(VERSION).tar.gz
	@rm -rf /var/tmp/$(PKGNAME)-$(VERSION)
	@dir=$$PWD; cp -a $$dir /var/tmp/$(PKGNAME)-$(VERSION)
	@rm -rf /var/tmp/$(PKGNAME)-$(VERSION)/.git
	@dir=$$PWD; cd /var/tmp; tar --gzip -cSpf $$dir/$(PKGNAME)-$(VERSION).tar.gz $(PKGNAME)-$(VERSION)
	@rm -rf /var/tmp/$(PKGNAME)-$(VERSION)
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.gz"

test-in-docker:
	sudo docker build -t welder/lorax-composer:latest -f Dockerfile.test .

ci: check test

.PHONY: all install check test clean tag docs archive local
