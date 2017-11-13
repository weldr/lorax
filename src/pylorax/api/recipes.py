#
# Copyright (C) 2017  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import gi
gi.require_version("Ggit", "1.0")
from gi.repository import Ggit as Git
from gi.repository import Gio
from gi.repository import GLib

import os
import pytoml as toml
import semantic_version as semver

from pylorax.base import DataHolder
from pylorax.sysutils import joinpaths


class CommitTimeValError(Exception):
    pass

class RecipeFileError(Exception):
    pass

class RecipeError(Exception):
    pass


class Recipe(dict):
    """A Recipe of package and modules

    This is a subclass of dict that enforces the constructor arguments
    and adds a .filename property to return the recipe's filename,
    and a .toml() function to return the recipe as a TOML string.
    """
    def __init__(self, name, description, version, modules, packages):
        # Check that version is empty or semver compatible
        if version:
            semver.Version(version)

        # Make sure modules and packages are listed by their case-insensitive names
        if modules is not None:
            modules = sorted(modules, key=lambda m: m["name"].lower())
        if packages is not None:
            packages = sorted(packages, key=lambda p: p["name"].lower())
        dict.__init__(self, name=name,
                            description=description,
                            version=version,
                            modules=modules,
                            packages=packages)

    @property
    def filename(self):
        """Return the Recipe's filename

        Replaces spaces in the name with '-' and appends .toml
        """
        return recipe_filename(self.get("name"))

    def toml(self):
        """Return the Recipe in TOML format"""
        return toml.dumps(self).encode("UTF-8")

    def bump_version(self, old_version=None):
        """semver recipe version number bump

        :param old_version: An optional old version number
        :type old_version: str
        :returns: The new version number or None
        :rtype: str
        :raises: ValueError

        If neither have a version, 0.0.1 is returned
        If there is no old version the new version is checked and returned
        If there is no new version, but there is a old one, bump its patch level
        If the old and new versions are the same, bump the patch level
        If they are different, check and return the new version
        """
        new_version = self.get("version")
        if not new_version and not old_version:
            self["version"] = "0.0.1"

        elif new_version and not old_version:
            semver.Version(new_version)
            self["version"] = new_version

        elif not new_version or new_version == old_version:
            new_version = str(semver.Version(old_version).next_patch())
            self["version"] = new_version

        else:
            semver.Version(new_version)
            self["version"] = new_version

        # Return the new version
        return str(semver.Version(self["version"]))

class RecipeModule(dict):
    def __init__(self, name, version):
        dict.__init__(self, name=name, version=version)

class RecipePackage(RecipeModule):
    pass

def recipe_from_toml(recipe_str):
    """Create a Recipe object from a toml string.

    :param recipe_str: The Recipe TOML string
    :type recipe_str: str
    :returns: A Recipe object
    :rtype: Recipe
    :raises: TomlError
    """
    recipe_dict = toml.loads(recipe_str)
    return recipe_from_dict(recipe_dict)

def recipe_from_dict(recipe_dict):
    """Create a Recipe object from a plain dict.

    :param recipe_dict: A plain dict of the recipe
    :type recipe_dict: dict
    :returns: A Recipe object
    :rtype: Recipe
    :raises: RecipeError
    """
    # Make RecipeModule objects from the toml
    # The TOML may not have modules or packages in it. Set them to None in this case
    try:
        if recipe_dict.get("modules"):
            modules = [RecipeModule(m.get("name"), m.get("version")) for m in recipe_dict["modules"]]
        else:
            modules = None
        if recipe_dict.get("packages"):
            packages = [RecipePackage(p.get("name"), p.get("version")) for p in recipe_dict["packages"]]
        else:
            packages = None
        name = recipe_dict["name"]
        description = recipe_dict["description"]
        version = recipe_dict.get("version", None)
    except KeyError as e:
        raise RecipeError("There was a problem parsing the recipe: %s" % str(e))

    return Recipe(name, description, version, modules, packages)

def gfile(path):
    """Convert a string path to GFile for use with Git"""
    return Gio.file_new_for_path(path)

def recipe_filename(name):
    """Return the toml filename for a recipe

    Replaces spaces with '-' and appends '.toml'
    """
    # XXX Raise and error if this is empty?
    return name.replace(" ", "-") + ".toml"

def head_commit(repo, branch):
    """Get the branch's HEAD Commit Object

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :returns: Branch's head commit
    :rtype: Git.Commit
    :raises: Can raise errors from Ggit
    """
    branch_obj = repo.lookup_branch(branch, Git.BranchType.LOCAL)
    commit_id = branch_obj.get_target()
    return repo.lookup(commit_id, Git.Commit)

def prepare_commit(repo, branch, builder):
    """Prepare for a commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param builder: instance of TreeBuilder
    :type builder: TreeBuilder
    :returns: (Tree, Sig, Ref)
    :rtype: tuple
    :raises: Can raise errors from Ggit
    """
    tree_id = builder.write()
    tree = repo.lookup(tree_id, Git.Tree)
    sig = Git.Signature.new_now("bdcs-api-server", "user-email")
    ref = "refs/heads/%s" % branch
    return (tree, sig, ref)

def open_or_create_repo(path):
    """Open an existing repo, or create a new one

    :param path: path to recipe directory
    :type path: string
    :returns: A repository object
    :rtype: Git.Repository
    :raises: Can raise errors from Ggit

    A bare git repo will be created in the git directory of the specified path.
    If a repo already exists it will be opened and returned instead of
    creating a new one.
    """
    Git.init()
    git_path = joinpaths(path, "git")
    if os.path.exists(joinpaths(git_path, "HEAD")):
        return Git.Repository.open(gfile(git_path))

    repo = Git.Repository.init_repository(gfile(git_path), True)

    # Make an initial empty commit
    sig = Git.Signature.new_now("bdcs-api-server", "user-email")
    tree_id = repo.get_index().write_tree()
    tree = repo.lookup(tree_id, Git.Tree)
    repo.create_commit("HEAD", sig, sig, "UTF-8", "Initial Recipe repository commit", tree, [])
    return repo

def write_commit(repo, branch, filename, message, content):
    """Make a new commit to a repository's branch

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: full path of the file to add
    :type filename: str
    :param message: The commit message
    :type message: str
    :param content: The data to write
    :type content: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    parent_commit = head_commit(repo, branch)
    blob_id = repo.create_blob_from_buffer(content)

    # Use treebuilder to make a new entry for this filename and blob
    parent_tree = parent_commit.get_tree()
    builder = repo.create_tree_builder_from_tree(parent_tree)
    builder.insert(filename, blob_id, Git.FileMode.BLOB)
    (tree, sig, ref) = prepare_commit(repo, branch, builder)
    return repo.create_commit(ref, sig, sig, "UTF-8", message, tree, [parent_commit])

def read_commit_spec(repo, spec):
    """Return the raw content of the blob specified by the spec

    :param repo: Open repository
    :type repo: Git.Repository
    :param spec: Git revparse spec
    :type spec: str
    :returns: Contents of the commit
    :rtype: str
    :raises: Can raise errors from Ggit

    eg. To read the README file from master the spec is "master:README"
    """
    commit_id = repo.revparse(spec).get_id()
    blob = repo.lookup(commit_id, Git.Blob)
    return blob.get_raw_content()

def read_commit(repo, branch, filename, commit=None):
    """Return the contents of a file on a specific branch or commit.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to read
    :type filename: str
    :param commit: Optional commit hash
    :type commit: str
    :returns: Contents of the commit
    :rtype: str
    :raises: Can raise errors from Ggit

    If no commit is passed the master:filename is returned, otherwise it will be
    commit:filename
    """
    return read_commit_spec(repo, "%s:%s" % (commit or branch, filename))

def read_recipe_commit(repo, branch, filename, commit=None):
    """Read a recipe commit from git and return a Recipe object

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to read
    :type filename: str
    :param commit: Optional commit hash
    :type commit: str
    :returns: A Recipe object
    :rtype: Recipe
    :raises: Can raise errors from Ggit

    If no commit is passed the master:filename is returned, otherwise it will be
    commit:filename
    """
    recipe_toml = read_commit(repo, branch, filename, commit)
    return recipe_from_toml(recipe_toml)

def list_branch_files(repo, branch):
    """Return a sorted list of the files on the branch HEAD

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :returns: A sorted list of the filenames
    :rtype: list(str)
    :raises: Can raise errors from Ggit
    """
    commit = head_commit(repo, branch).get_id().to_string()
    return list_commit_files(repo, commit)

def list_commit_files(repo, commit):
    """Return a sorted list of the files on a commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param commit: The commit hash to list
    :type commit: str
    :returns: A sorted list of the filenames
    :rtype: list(str)
    :raises: Can raise errors from Ggit
    """
    commit_id = Git.OId.new_from_string(commit)
    commit_obj = repo.lookup(commit_id, Git.Commit)
    tree = commit_obj.get_tree()
    return sorted([tree.get(i).get_name() for i in range(0,tree.size())])

def delete_recipe(repo, branch, recipe_name):
    """Delete a recipe from a branch.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to delete
    :type recipe_name: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    return delete_file(repo, branch, recipe_filename(recipe_name))

def delete_file(repo, branch, filename):
    """Delete a file from a branch.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to delete
    :type filename: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    parent_commit = head_commit(repo, branch)
    parent_tree = parent_commit.get_tree()
    builder = repo.create_tree_builder_from_tree(parent_tree)
    builder.remove(filename)
    (tree, sig, ref) = prepare_commit(repo, branch, builder)
    message = "Recipe %s deleted" % filename
    return repo.create_commit(ref, sig, sig, "UTF-8", message, tree, [parent_commit])

def revert_file(repo, branch, filename, commit):
    """Revert the contents of a file to that of a previous commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to revert
    :type filename: str
    :param commit: Commit hash
    :type commit: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    commit_id = Git.OId.new_from_string(commit)
    commit_obj = repo.lookup(commit_id, Git.Commit)
    revert_tree = commit_obj.get_tree()
    entry = revert_tree.get_by_name(filename)
    blob_id = entry.get_id()
    parent_commit = head_commit(repo, branch)

    # Use treebuilder to modify the tree
    parent_tree = parent_commit.get_tree()
    builder = repo.create_tree_builder_from_tree(parent_tree)
    builder.insert(filename, blob_id, Git.FileMode.BLOB)
    (tree, sig, ref) = prepare_commit(repo, branch, builder)
    commit_hash = commit_id.to_string()
    message = "Recipe %s reverted to commit %s" % (filename, commit_hash)
    return repo.create_commit(ref, sig, sig, "UTF-8", message, tree, [parent_commit])

def commit_recipe(repo, branch, recipe):
    """Commit a recipe to a branch

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe: Recipe to commit
    :type recipe: Recipe
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    try:
        old_recipe = read_recipe_commit(repo, branch, recipe.filename)
        old_version = old_recipe["version"]
    except Exception:
        old_version = None

    recipe.bump_version(old_version)
    recipe_toml = recipe.toml()
    message = "Recipe %s, version %s saved." % (recipe["name"], recipe["version"])
    return write_commit(repo, branch, recipe.filename, message, recipe_toml)

def commit_recipe_file(repo, branch, filename):
    """Commit a recipe file to a branch

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: Path to the recipe file to commit
    :type filename: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit or RecipeFileError
    """
    try:
        f = open(filename, 'rb')
        recipe = recipe_from_toml(f.read())
    except IOError:
        raise RecipeFileError

    return commit_recipe(repo, branch, recipe)

def commit_recipe_directory(repo, branch, directory):
    """Commit all *.toml files from a directory, if they aren't already in git.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param directory: The directory of *.toml recipes to commit
    :type directory: str
    :returns: None
    :raises: Can raise errors from Ggit or RecipeFileError

    Files with Toml or RecipeFileErrors will be skipped, and the remainder will
    be tried.
    """
    dir_files = set([e for e in os.listdir(directory) if e.endswith(".toml")])
    branch_files = set(list_branch_files(repo, branch))
    new_files = dir_files.difference(branch_files)

    for f in new_files:
        # Skip files with errors, but try the others
        try:
            commit_recipe_file(repo, branch, joinpaths(directory, f))
        except (RecipeFileError, toml.TomlError):
            pass

def tag_file_commit(repo, branch, filename):
    """Tag a file's most recent commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: Filename to tag
    :type filename: str
    :returns: Tag id or None if it failed.
    :rtype: Git.OId
    :raises: Can raise errors from Ggit

    This uses git tags, of the form `refs/tags/<branch>/<filename>/r<revision>`
    Only the most recent recipe commit can be tagged to prevent out of order tagging.
    Revisions start at 1 and increment for each new commit that is tagged.
    If the commit has already been tagged it will return false.
    """
    file_commits = list_commits(repo, branch, filename)
    if not file_commits:
        return None

    # Find the most recently tagged version (may not be one) and add 1 to it.
    for details in file_commits:
        if details.revision is not None:
            new_revision = details.revision + 1
            break
    else:
        new_revision = 1

    name = "%s/%s/r%d" % (branch, filename, new_revision)
    sig = Git.Signature.new_now("bdcs-api-server", "user-email")
    commit_id = Git.OId.new_from_string(file_commits[0].commit)
    commit = repo.lookup(commit_id, Git.Commit)
    return repo.create_tag(name, commit, sig, name, Git.CreateFlags.NONE)

def find_commit_tag(repo, branch, filename, commit_id):
    """Find the tag that matches the commit_id

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to revert
    :type filename: str
    :param commit_id: The commit id to check
    :type commit_id: Git.OId
    :returns: The tag or None if there isn't one
    :rtype: str or None

    There should be only 1 tag pointing to a commit, but there may not
    be a tag at all.

    The tag will look like: 'refs/tags/<branch>/<filename>/r<revision>'
    """
    pattern = "%s/%s/r*" % (branch, filename)
    tags = [t for t in repo.list_tags_match(pattern) if is_commit_tag(repo, commit_id, t)]
    if len(tags) != 1:
        return None
    else:
        return tags[0]

def is_commit_tag(repo, commit_id, tag):
    """Check to see if a tag points to a specific commit.

    :param repo: Open repository
    :type repo: Git.Repository
    :param commit_id: The commit id to check
    :type commit_id: Git.OId
    :param tag: The tag to check
    :type tag: str
    :returns: True if the tag points to the commit, False otherwise
    :rtype: bool
    """
    ref = repo.lookup_reference("refs/tags/" + tag)
    tag_id = ref.get_target()
    tag = repo.lookup(tag_id, Git.Tag)
    target_id = tag.get_target_id()
    return commit_id.compare(target_id) == 0

def get_revision_from_tag(tag):
    """Return the revision number from a tag

    :param tag: The tag to exract the revision from
    :type tag: str
    :returns: The integer revision or None
    :rtype: int or None

    The revision is the part after the r in 'branch/filename/rXXX'
    """
    if tag is None:
        return None
    try:
        return int(tag.rsplit('r',2)[-1])
    except (ValueError, IndexError):
        return None

class CommitDetails(DataHolder):
    def __init__(self, commit, timestamp, message, revision=None):
        DataHolder.__init__(self,
                            commit = commit,
                            timestamp = timestamp,
                            message = message,
                            revision = revision)

def list_commits(repo, branch, filename):
    """List the commit history of a file on a branch.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to revert
    :type filename: str
    :returns: A list of commit details
    :rtype: list(CommitDetails)
    :raises: Can raise errors from Ggit
    """
    revwalk = Git.RevisionWalker.new(repo)
    revwalk.set_sort_mode(Git.SortMode.TIME)
    branch_ref = "refs/heads/%s" % branch
    revwalk.push_ref(branch_ref)

    commits = []
    while True:
        commit_id = revwalk.next()
        if not commit_id:
            break
        commit = repo.lookup(commit_id, Git.Commit)

        parents = commit.get_parents()
        # No parents? Must be the first commit.
        if parents.get_size() == 0:
            continue

        tree = commit.get_tree()
        # Is the filename in this tree? If not, move on.
        if not tree.get_by_name(filename):
            continue

        # Is filename different in all of the parent commits?
        parent_commits = map(parents.get, xrange(0, parents.get_size()))
        is_diff = all(map(lambda pc: is_parent_diff(repo, filename, tree, pc), parent_commits))
        # No changes from parents, skip it.
        if not is_diff:
            continue

        tag = find_commit_tag(repo, branch, filename, commit.get_id())
        try:
            commits.append(get_commit_details(commit, get_revision_from_tag(tag)))
        except CommitTimeValError:
            # Skip any commits that have trouble converting the time
            # TODO - log details about this failure
            pass

    # These will be in reverse time sort order thanks to revwalk
    return commits

def get_commit_details(commit, revision=None):
    """Return the details about a specific commit.

    :param commit: The commit to get details from
    :type commit: Git.Commit
    :param revision: Optional commit revision
    :type revision: int
    :returns: Details about the commit
    :rtype: CommitDetails
    :raises: CommitTimeValError or Ggit exceptions

    """
    message = commit.get_message()
    commit_str = commit.get_id().to_string()
    sig = commit.get_committer()

    datetime = sig.get_time()
    # XXX What do we do with timezone?
    _timezone = sig.get_time_zone()
    timeval = GLib.TimeVal()
    ok = datetime.to_timeval(timeval)
    if not ok:
        raise CommitTimeValError
    time_str = timeval.to_iso8601()

    return CommitDetails(commit_str, time_str, message, revision)

def is_parent_diff(repo, filename, tree, parent):
    """Check to see if the commit is different from its parents

    :param repo: Open repository
    :type repo: Git.Repository
    :param filename: filename to revert
    :type filename: str
    :param tree: The commit's tree
    :type tree: Git.Tree
    :param parent: The commit's parent commit
    :type parent: Git.Commit
    :retuns: True if filename in the commit is different from its parents
    :rtype: bool
    """
    diff_opts = Git.DiffOptions.new()
    diff_opts.set_pathspec([filename])
    diff = Git.Diff.new_tree_to_tree(repo, parent.get_tree(), tree, diff_opts)
    return diff.get_num_deltas() > 0
