How to release a new version of Lorax for Fedora
================================================

Install `tito` and `podman` on your system.

Optionally patch `tito` to support signing the tags with your gpg key. If you
do this your key should be available on the public gpg keyservers so that
people can verify your signature.

The upstream `tito` PR can be found [here](https://github.com/dgoodwin/tito/pull/328).

You will need to have permission to push to the lorax repository, and to the
Fedora dist-git repository. If your FAS name isn't listed on the [lorax package
page](https://src.fedoraproject.org/rpms/lorax/) members list then you need to
contact one of the project admins and ask to be added.


Run the tests
-------------
You can run the tests using `podman` instead of `docker` by running this from the
top level of the checked-out lorax repo:

    DOCKER=podman RUN_TESTS="ci test_cli" make test-in-docker

If they fail, fix them and submit a PR :)

You can also run the cockpit CI tests locally:

    make vm
    ./test/check-cli

See the `./test/README.md` documentation for more details about the cockpit CI
tests.


Update the documentation
------------------------
If there are changes to the code that would effect the documentation you should
rebuild the `sphinx` based documents:

    DOCKER=podman make docs-in-docker
    git add docs/
    git commit -m "New lorax documentation - x.y"

The documentation is accessible [from here](https://weldr.io/lorax), and the
source for those pages is stored in the `gh-pages` branch of lorax. I have a
second `lorax` repository checked out that I use for updating the `gh-pages`
branch:

    git clone git@github.com:weldr/lorax.git lorax-gh-pages
    cd lorax-gh-pages
    git checkout gh-pages
    git pull

And then I rsync the new documentation over from the current lorax build
directory:

    rsync -aP --exclude .git --exclude .nojekyll ../lorax/docs/html/ ./
    git add .
    git commit -m "Add lorax x.y documentation"
    git push

After a few minutes the online version of the documentation should appear.

Tag and build the release tar.gz
--------------------------------
We use the `tito` tool to handle incrementing the version number and updating
the `lorax.spec` file changelog section using the git commits since the last
tag. `tito tag` will open an editor, allowing you to edit the changelog. Make
sure it looks clean, entries starting with '- ' and no wrapped lines:

    tito tag
    git push --follow-tags origin

Build the release tarball:

    tito build --tgz

The release tarball will be placed into /tmp/tito/lorax-x.y.z.tar.gz


Build the Fedora lorax package
------------------------------
The first time you do this you need to clone the Fedora dist-git repository
[from here](https://src.fedoraproject.org/rpms/lorax/) using your ssh key:

git clone URL lorax-fedora

After that the steps are the same each time, make sure your `lorax-fedora` repo
is up to date:

    git co master
    git pull

Copy the `lorax.spec` that tito modified from your `lorax` project repo:

    cp /path/to/lorax/repo/lorax.spec .

Make sure you have a current fedoraproject kerberos ticket, you can use
`kswitch -p FEDORAPROJECT.ORG` to switch to it if you need to, or `kinit` to
get one. See [the Fedora
wiki](https://fedoraproject.org/wiki/Infrastructure/Kerberos) for more details
and debugging tips.

Upload the new release's tar to build system, making sure you pick the right
one. The `/tmp/tito/` directory is only cleared out when you reboot, so it may
have several versions in there:

    fedpkg new-sources /tmp/tito/lorax-x.y.tar.gz

Update the changelog. Yes, fedpkg changes the formatting and it is annoying.
Make sure the lines start with '- ' and that any wrapped lines are un-wrapped.
Usually the committer email address is what will get bumped to the next line:

    fedpkg clog
    vim clog

Add all the updated files, make sure nothing has been forgotten (lorax.spec, sources, .gitignore):

    git add -u
    git status (just to be sure you have all the files added )
    git commit -F clog
    git show

Examine the commit with care.  Make sure the sources have changed, that the NVR
is correct, and that it contains the %changelog

At this point anything can be changed, either reset the checkout to the last
commit and start over, or fix the problems and squash the changes together into
the commit you just made. There should be one commit per-release.

    fedpkg push && fedpkg build

If there are errors in the build, check the logs in koji at the link provided by fedpkg.

