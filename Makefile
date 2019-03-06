PYTHON ?= /usr/bin/python
DESTDIR ?= /
DOCKER ?= docker

PKGNAME = lorax-composer
VERSION = $(shell awk '/Version:/ { print $$2 }' $(PKGNAME).spec)
RELEASE = $(shell awk '/Release:/ { print $$2 }' $(PKGNAME).spec | sed -e 's|%.*$$||g')
TAG = lorax-$(VERSION)-$(RELEASE)

IMAGE_RELEASE = $(shell awk -F: '/FROM/ { print $$2}' Dockerfile.test)

default: all

src/composer/version.py:
	echo "num = '$(VERSION)-$(RELEASE)'" > src/composer/version.py

src/pylorax/version.py:
	echo "num = '$(VERSION)-$(RELEASE)'" > src/pylorax/version.py

src/pylorax/api/version.py:
	echo "num = '$(VERSION)-$(RELEASE)'" > src/pylorax/api/version.py

all: src/pylorax/version.py src/pylorax/api/version.py src/composer/version.py
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install --root=$(DESTDIR)
	mkdir -p $(DESTDIR)/$(mandir)/man1
	install -m 644 docs/man/lorax.1 $(DESTDIR)/$(mandir)/man1
	install -m 644 docs/man/livemedia-creator.1 $(DESTDIR)/$(mandir)/man1
	mkdir -p $(DESTDIR)/etc/bash_completion.d
	install -m 644 etc/bash_completion.d/composer-cli $(DESTDIR)/etc/bash_completion.d

check:
	@echo "*** Running pylint ***"
	PYTHONPATH=$(PYTHONPATH):./src/ ./tests/pylint/runpylint.py

test: docs
	@echo "*** Running tests ***"
	PYTHONPATH=$(PYTHONPATH):./src/ $(PYTHON) -m nose -v --with-coverage --cover-erase --cover-branches \
					--cover-package=pylorax --cover-inclusive \
					./tests/pylorax/ ./tests/composer/

	coverage report -m
	[ -f "/usr/bin/coveralls" ] && [ -n "$(COVERALLS_REPO_TOKEN)" ] && coveralls || echo
	
	./tests/test_cli.sh

# need `losetup`, which needs Docker to be in privileged mode (--privileged)
# but even so fails in Travis CI
test_images:
	sudo -E ./tests/test_cli.sh tests/cli/test_compose_ext4-filesystem.sh  \
				    tests/cli/test_compose_partitioned-disk.sh \
				    tests/cli/test_compose_tar.sh              \
				    tests/cli/test_compose_qcow2.sh            \
				    tests/cli/test_compose_live-iso.sh

test_aws:
	sudo -E ./tests/test_cli.sh tests/cli/test_build_and_deploy_aws.sh

test_azure:
	sudo -E ./tests/test_cli.sh tests/cli/test_build_and_deploy_azure.sh

test_openstack:
	sudo -E ./tests/test_cli.sh tests/cli/test_build_and_deploy_openstack.sh

test_vmware:
	sudo -E ./tests/test_cli.sh tests/cli/test_build_and_deploy_vmware.sh

clean:
	-rm -rf build src/pylorax/version.py
	-rm -rf build src/pylorax/api/version.py
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

test-in-copy:
	rsync -aP --exclude=.git /lorax-ro/ /lorax/
	make -C /lorax/ ci
	cp /lorax/.coverage /test-results/

test-in-docker:
	sudo $(DOCKER) build -t welder/lorax-tests:$(IMAGE_RELEASE) -f Dockerfile.test .
	sudo $(DOCKER) run --rm -it -v `pwd`/.test-results/:/test-results -v `pwd`:/lorax-ro:ro --security-opt label=disable welder/lorax-tests:$(IMAGE_RELEASE) make test-in-copy

docs-in-docker:
	sudo $(DOCKER) run -it --rm -v `pwd`/docs/html/:/lorax/docs/html/ --security-opt label=disable welder/lorax-tests:$(IMAGE_RELEASE) make docs

ci: check test

.PHONY: all install check test clean tag docs archive local

.PHONY: ci_after_success
ci_after_success:
# nothing to do here, but Jenkins expects this to be present, otherwise fails
