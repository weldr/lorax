--- Description of proposed changes ---




--- Merge policy ---

- [ ] Travis CI PASS
- [ ] `*-aws-runtest` PASS
- [ ] `*-azure-runtest` PASS
- [ ] `*-images-runtest` PASS
- [ ] `*-openstack-runtest` PASS
- [ ] `*-vmware-runtest` PASS
- [ ] For `rhel8-*` and `rhel7-*` branches commit log references an approved
  bug in Bugzilla. Do not merge if the bug doesn't have the 3 ACKs set to `+`!

--- Jenkins commands ---

- `ok to test` to accept this pull request for testing
- `test this please` for a one time test run
- `retest this please` to start a new build
