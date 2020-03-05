PYTHON ?= /usr/bin/python
DESTDIR ?= /
DOCKER ?= docker

PKGNAME = lorax-composer
VERSION = $(shell awk '/Version:/ { print $$2 }' $(PKGNAME).spec)
RELEASE = $(shell awk '/Release:/ { print $$2 }' $(PKGNAME).spec | sed -e 's|%.*$$||g')
TAG = lorax-$(VERSION)-$(RELEASE)

IMAGE_RELEASE = $(shell awk -F: '/FROM/ { print $$2}' Dockerfile.test)

ifeq ($(TEST_OS),)
OS_ID = $(shell awk -F= '/^ID=/ {print $$2}' /etc/os-release)
OS_VERSION = $(shell awk -F= '/^VERSION_ID/ {print $$2}' /etc/os-release | tr '.' '-')
TEST_OS = $(OS_ID)-$(OS_VERSION)
endif
export TEST_OS
VM_IMAGE=$(CURDIR)/test/images/$(TEST_OS)

ifeq ($(REPOS_DIR),)
REPOS_DIR = /etc/yum.repos.d
endif

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

# need `losetup`, which needs Docker to be in privileged mode (--privileged)
# but even so fails in Travis CI
test_images:
	sudo -E ./tests/test_cli.sh tests/cli/test_compose_ext4-filesystem.sh  \
				    tests/cli/test_compose_partitioned-disk.sh \
				    tests/cli/test_compose_tar.sh              \
				    tests/cli/test_compose_tar_kickstart.sh    \
				    tests/cli/test_compose_qcow2.sh            \
				    tests/cli/test_compose_live-iso.sh

test_cli:
	sudo -E ./tests/test_cli.sh

clean:
	-rm -rf build src/pylorax/version.py
	-rm -rf build src/pylorax/api/version.py
	-rm -rf build src/composer/version.py

tag:
	git tag -f $(TAG)

docs:
	$(MAKE) -C docs apidoc html

archive:
	@git archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ $(TAG) > $(PKGNAME)-$(VERSION).tar
	@gzip -f $(PKGNAME)-$(VERSION).tar
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.gz"

srpm: archive $(PKGNAME).spec
	rpmbuild -bs \
	  --define "_sourcedir $(CURDIR)" \
	  --define "_srcrpmdir $(CURDIR)" \
	  lorax-composer.spec

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

$(VM_IMAGE): TAG=HEAD
$(VM_IMAGE): srpm bots
	rm -f $(VM_IMAGE) $(VM_IMAGE).qcow2
	srpm=$(shell rpm --qf '%{Name}-%{Version}-%{Release}.src.rpm\n' -q --specfile lorax-composer.spec | head -n1) ; \
	bots/image-customize -v \
		--resize 20G \
		--upload $$srpm:/var/tmp \
		--upload $(CURDIR)/test/vm.install:/var/tmp/vm.install \
		--upload $(realpath tests):/ \
		--run-command "chmod +x /var/tmp/vm.install" \
		--run-command "cd /var/tmp; /var/tmp/vm.install $$srpm" \
		$(TEST_OS)
	[ -f ~/.config/lorax-test-env ] && bots/image-customize \
		--upload ~/.config/lorax-test-env:/var/tmp/lorax-test-env \
		$(TEST_OS) || echo

# convenience target for the above
vm: $(VM_IMAGE)
	echo $(VM_IMAGE)

# grab all repositories from the host system, overwriting what's inside the VM
# and update the image. Mostly used when testing downstream snapshots to make
# sure VM_IMAGE is as close as possible to the host!
vm-local-repos: vm
	bots/image-customize -v \
		--run-command "rm -rf /etc/yum.repos.d" \
		$(TEST_OS)
	bots/image-customize -v \
		--upload $(REPOS_DIR):/etc/yum.repos.d \
		--run-command "yum -y remove composer-cli lorax-composer" \
		--run-command "yum -y update" \
		--run-command "yum -y install composer-cli lorax-composer" \
		--run-command "systemctl enable lorax-composer" \
		$(TEST_OS)

vm-releng:
	rm -f $(VM_IMAGE) $(VM_IMAGE).qcow2
	bots/image-customize -v \
		--resize 20G \
		--upload $(CURDIR)/test/vm.install:/var/tmp/vm.install \
		--upload $(realpath tests):/ \
		--run-command "chmod +x /var/tmp/vm.install" \
		--run-command "cd /var/tmp; BUILD_SRPM=0 /var/tmp/vm.install" \
		$(TEST_OS)
	[ -f ~/.config/lorax-test-env ] && bots/image-customize \
		--upload ~/.config/lorax-test-env:/var/tmp/lorax-test-env \
		$(TEST_OS) || echo


vm-reset:
	rm -f $(VM_IMAGE) $(VM_IMAGE).qcow2

# checkout Cockpit's bots for standard test VM images and API to launch them
# must be from master, as only that has current and existing images; but testvm.py API is stable
# support CI testing against a bots change
bots:
	git clone --quiet --reference-if-able $${XDG_CACHE_HOME:-$$HOME/.cache}/cockpit-project/bots https://github.com/cockpit-project/bots.git
	if [ -n "$$COCKPIT_BOTS_REF" ]; then git -C bots fetch --quiet --depth=1 origin "$$COCKPIT_BOTS_REF"; git -C bots checkout --quiet FETCH_HEAD; fi
	@echo "checked out bots/ ref $$(git -C bots rev-parse HEAD)"

.PHONY: all install check test clean tag docs archive local

.PHONY: ci_after_success
ci_after_success:
# nothing to do here, but Jenkins expects this to be present, otherwise fails
