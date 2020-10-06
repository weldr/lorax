PYTHON ?= /usr/bin/python3
DESTDIR ?= /
PREFIX ?= /usr
mandir ?= $(PREFIX)/share/man
DOCKER ?= podman
DOCS_VERSION ?= next
RUN_TESTS ?= ci
BACKEND ?= osbuild-composer

PKGNAME = lorax
VERSION = $(shell awk '/Version:/ { print $$2 }' $(PKGNAME).spec)
RELEASE = $(shell awk '/Release:/ { print $$2 }' $(PKGNAME).spec | sed -e 's|%.*$$||g')
TAG = lorax-$(VERSION)-$(RELEASE)

IMAGE_RELEASE = $(shell awk -F: '/FROM/ { print $$2}' Dockerfile.test)

ifeq ($(TEST_OS),)
OS_ID = $(shell awk -F= '/^ID/ {print $$2}' /etc/os-release)
OS_VERSION = $(shell awk -F= '/^VERSION_ID/ {print $$2}' /etc/os-release)
TEST_OS = $(OS_ID)-$(OS_VERSION)
endif
export TEST_OS
VM_IMAGE=$(CURDIR)/test/images/$(TEST_OS)

ifeq ($(REPOS_DIR),)
REPOS_DIR = /etc/yum.repos.d
endif

default: all

src/composer/version.py: lorax.spec
	echo "num = '$(VERSION)-$(RELEASE)'" > src/composer/version.py

src/pylorax/version.py: lorax.spec
	echo "num = '$(VERSION)-$(RELEASE)'" > src/pylorax/version.py

all: src/pylorax/version.py src/composer/version.py
	$(PYTHON) setup.py build

install: all
	$(PYTHON) setup.py install --root=$(DESTDIR) --prefix=$(PREFIX)
	mkdir -p $(DESTDIR)/$(mandir)/man1
	install -m 644 docs/man/*.1 $(DESTDIR)/$(mandir)/man1
	mkdir -p $(DESTDIR)/etc/bash_completion.d
	install -m 644 etc/bash_completion.d/composer-cli $(DESTDIR)/etc/bash_completion.d

check:
	@echo "*** Running pylint ***"
	PYTHONPATH=$(PYTHONPATH):./src/ ./tests/pylint/runpylint.py

test:
	@echo "*** Running tests ***"
	PYTHONPATH=$(PYTHONPATH):./src/ $(PYTHON) -X dev -m pytest -v --cov-branch \
					--cov=pylorax --cov=composer \
					./tests/pylorax/ ./tests/composer/

	coverage3 report -m
	[ -f "/usr/bin/coveralls" ] && [ -n "$(COVERALLS_REPO_TOKEN)" ] && coveralls || echo

test_cli:
	sudo -E ./tests/test_cli.sh

test_mkksiso:
	sudo -E ./tests/mkksiso/test_mkksiso.sh

clean_cloud_envs:
	# clean beakerlib logs from previous executions
	sudo rm -rf /var/tmp/beakerlib-*/
	sudo -E ./tests/cleanup/remove_old_objects_aws.sh
	sudo -E ./tests/cleanup/remove_old_objects_openstack.sh
	sudo -E ./tests/cleanup/remove_old_objects_azure.sh
	sudo -E ./tests/cleanup/remove_old_objects_vmware.sh
	# make sure all cleanup scripts finished successfully
	sudo sh -c 'grep RESULT_STRING /var/tmp/beakerlib-*/TestResults | grep -v PASS && exit 1 || exit 0'

clean:
	-rm -rf build src/pylorax/version.py
	-rm -rf build src/composer/version.py

tag:
	git tag -f $(TAG)

docs:
	$(MAKE) -C docs apidoc html man

# This is needed to reset the ownership of the new docs files after they are created in a container
set-docs-owner:
	chown -R $(LOCAL_UID):$(LOCAL_GID) docs/

archive:
	@git archive --format=tar --prefix=$(PKGNAME)-$(VERSION)/ $(TAG) > $(PKGNAME)-$(VERSION).tar
	@gzip -f $(PKGNAME)-$(VERSION).tar
	@echo "The archive is in $(PKGNAME)-$(VERSION).tar.gz"

dist: tag archive
	scp $(PKGNAME)-$(VERSION).tar.gz fedorahosted.org:lorax

srpm: archive $(PKGNAME).spec
	rpmbuild -bs \
	  --define "_sourcedir $(CURDIR)" \
	  --define "_srcrpmdir $(CURDIR)" \
	  lorax.spec

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
	make -C /lorax/ $(RUN_TESTS)
	cp /lorax/.coverage /test-results/

test-in-docker:
	sudo $(DOCKER) build -t welder/lorax-tests:$(IMAGE_RELEASE) -f Dockerfile.test .
	@mkdir -p `pwd`/.test-results
	sudo $(DOCKER) run --rm -it -v `pwd`/.test-results/:/test-results \
		-v `pwd`:/lorax-ro:ro --security-opt label=disable \
		--env RUN_TESTS="$(RUN_TESTS)" \
		welder/lorax-tests:$(IMAGE_RELEASE) make test-in-copy

docs-in-docker:
	sudo $(DOCKER) run -it --rm -v `pwd`:/lorax-ro:ro \
		-v `pwd`/docs/:/lorax-ro/docs/ \
		--env LORAX_VERSION=$(DOCS_VERSION) \
		--env LOCAL_UID=`id -u` --env LOCAL_GID=`id -g` \
		--security-opt label=disable welder/lorax-tests:$(IMAGE_RELEASE) make docs set-docs-owner

ci: check test

$(VM_IMAGE): TAG=HEAD
$(VM_IMAGE): srpm bots
	rm -f $(VM_IMAGE) $(VM_IMAGE).qcow2
	srpm=$(shell rpm --qf '%{Name}-%{Version}-%{Release}.src.rpm\n' -q --specfile lorax.spec | head -n1) ; \
	bots/image-customize -v \
		--resize 20G \
		--upload $$srpm:/var/tmp \
		--upload $(CURDIR)/test/vm.install:/var/tmp/vm.install \
		--upload $(realpath tests):/ \
		--run-command "chmod +x /var/tmp/vm.install" \
		--run-command "cd /var/tmp; BACKEND=$(BACKEND) /var/tmp/vm.install $$srpm" \
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
		--run-command "yum -y remove composer-cli $(BACKEND)" \
		--run-command "yum -y update" \
		--run-command "yum -y install composer-cli $(BACKEND)" \
		--run-command "systemctl enable $(BACKEND).socket" \
		$(TEST_OS)

vm-reset:
	rm -f $(VM_IMAGE) $(VM_IMAGE).qcow2

# checkout Cockpit's bots for standard test VM images and API to launch them
# must be from master, as only that has current and existing images; but testvm.py API is stable
# support CI testing against a bots change
bots:
	git clone --quiet --reference-if-able $${XDG_CACHE_HOME:-$$HOME/.cache}/cockpit-project/bots https://github.com/cockpit-project/bots.git
	if [ -n "$$COCKPIT_BOTS_REF" ]; then git -C bots fetch --quiet --depth=1 origin "$$COCKPIT_BOTS_REF"; git -C bots checkout --quiet FETCH_HEAD; fi
	@echo "checked out bots/ ref $$(git -C bots rev-parse HEAD)"

.PHONY: ci_after_success
ci_after_success:
# nothing to do here, but Jenkins expects this to be present, otherwise fails

.PHONY: docs check test srpm vm vm-reset
