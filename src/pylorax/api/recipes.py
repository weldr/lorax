#
# Copyright (C) 2017-2019  Red Hat, Inc.
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

from pylorax.api.projects import dep_evra
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
    def __init__(self, name, description, version, modules, packages, groups, customizations=None, gitrepos=None):
        # Check that version is empty or semver compatible
        if version:
            semver.Version(version)

        # Make sure modules, packages, and groups are listed by their case-insensitive names
        if modules is not None:
            modules = sorted(modules, key=lambda m: m["name"].lower())
        if packages is not None:
            packages = sorted(packages, key=lambda p: p["name"].lower())
        if groups is not None:
            groups = sorted(groups, key=lambda g: g["name"].lower())

        # Only support [[repos.git]] for now
        if gitrepos is not None:
            repos = {"git": sorted(gitrepos, key=lambda g: g["repo"].lower())}
        else:
            repos = None
        dict.__init__(self, name=name,
                            description=description,
                            version=version,
                            modules=modules,
                            packages=packages,
                            groups=groups,
                            customizations=customizations,
                            repos=repos)

        # We don't want customizations=None to show up in the TOML so remove it
        if customizations is None:
            del self["customizations"]

        # Don't include empty repos or repos.git
        if repos is None or not repos["git"]:
            del self["repos"]

    @property
    def package_names(self):
        """Return the names of the packages"""
        return [p["name"] for p in self["packages"] or []]

    @property
    def package_nver(self):
        """Return the names and version globs of the packages"""
        return [(p["name"], p["version"]) for p in self["packages"] or []]

    @property
    def module_names(self):
        """Return the names of the modules"""
        return [m["name"] for m in self["modules"] or []]

    @property
    def module_nver(self):
        """Return the names and version globs of the modules"""
        return [(m["name"], m["version"]) for m in self["modules"] or []]

    @property
    def group_names(self):
        """Return the names of the groups.  Groups do not have versions."""
        return map(lambda g: g["name"], self["groups"] or [])

    @property
    def filename(self):
        """Return the Recipe's filename

        Replaces spaces in the name with '-' and appends .toml
        """
        return recipe_filename(self.get("name"))

    def toml(self):
        """Return the Recipe in TOML format"""
        return toml.dumps(self)

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

    def freeze(self, deps):
        """ Return a new Recipe with full module and package NEVRA

        :param deps: A list of dependency NEVRA to use to fill in the modules and packages
        :type deps: list(
        :returns: A new Recipe object
        :rtype: Recipe
        """
        module_names = self.module_names
        package_names = self.package_names
        group_names = self.group_names

        new_modules = []
        new_packages = []
        new_groups = []
        for dep in deps:
            if dep["name"] in package_names:
                new_packages.append(RecipePackage(dep["name"], dep_evra(dep)))
            elif dep["name"] in module_names:
                new_modules.append(RecipeModule(dep["name"], dep_evra(dep)))
            elif dep["name"] in group_names:
                new_groups.append(RecipeGroup(dep["name"]))
        if "customizations" in self:
            customizations = self["customizations"]
        else:
            customizations = None
        if "repos" in self and "git" in self["repos"]:
            gitrepos = self["repos"]["git"]
        else:
            gitrepos = None

        return Recipe(self["name"], self["description"], self["version"],
                      new_modules, new_packages, new_groups, customizations, gitrepos)

class RecipeModule(dict):
    def __init__(self, name, version):
        dict.__init__(self, name=name, version=version)

class RecipePackage(RecipeModule):
    pass

class RecipeGroup(dict):
    def __init__(self, name):
        dict.__init__(self, name=name)

def NewRecipeGit(toml_dict):
    """Create a RecipeGit object from fields in a TOML dict

    :param rpmname: Name of the rpm to create, also used as the prefix name in the tar archive
    :type rpmname: str
    :param rpmversion: Version of the rpm, eg. "1.0.0"
    :type rpmversion: str
    :param rpmrelease: Release of the rpm, eg. "1"
    :type rpmrelease: str
    :param summary: Summary string for the rpm
    :type summary: str
    :param repo: URL of the get repo to clone and create the archive from
    :type repo: str
    :param ref: Git reference to check out. eg. origin/branch-name, git tag, or git commit hash
    :type ref: str
    :param destination: Path to install the / of the git repo at when installing the rpm
    :type destination: str
    :returns: A populated RecipeGit object
    :rtype: RecipeGit

    The TOML should look like this::

        [[repos.git]]
        rpmname="server-config"
        rpmversion="1.0"
        rpmrelease="1"
        summary="Setup files for server deployment"
        repo="PATH OF GIT REPO TO CLONE"
        ref="v1.0"
        destination="/opt/server/"

    Note that the repo path supports anything that git supports, file://, https://, http://

    Currently there is no support for authentication
    """
    return RecipeGit(toml_dict.get("rpmname"),
                     toml_dict.get("rpmversion"),
                     toml_dict.get("rpmrelease"),
                     toml_dict.get("summary", ""),
                     toml_dict.get("repo"),
                     toml_dict.get("ref"),
                     toml_dict.get("destination"))

class RecipeGit(dict):
    def __init__(self, rpmname, rpmversion, rpmrelease, summary, repo, ref, destination):
        dict.__init__(self, rpmname=rpmname, rpmversion=rpmversion, rpmrelease=rpmrelease,
                      summary=summary, repo=repo, ref=ref, destination=destination)

def recipe_from_file(recipe_path):
    """Return a recipe file as a Recipe object

    :param recipe_path: Path to the recipe fila
    :type recipe_path: str
    :returns: A Recipe object
    :rtype: Recipe
    """
    with open(recipe_path, 'rb') as f:
        return recipe_from_toml(f.read())

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

def check_required_list(lst, fields):
    """Check a list of dicts for required fields

    :param lst: A list of dicts with fields
    :type lst: list of dict
    :param fields: A list of field name strings
    :type fields: list of str
    :returns: A list of error strings
    :rtype: list of str
    """
    errors = []
    for i, m in enumerate(lst):
        m_errs = []
        errors.extend(check_list_case(fields, m.keys(), prefix="%d " % (i+1)))
        for f in fields:
            if f not in m:
                m_errs.append("'%s'" % f)
        if m_errs:
            errors.append("%d is missing %s" % (i+1, ", ".join(m_errs)))
    return errors

def check_list_case(expected_keys, recipe_keys, prefix=""):
    """Check the case of the recipe keys

    :param expected_keys: A list of expected key strings
    :type expected_keys: list of str
    :param recipe_keys: A list of the recipe's key strings
    :type recipe_keys: list of str
    :returns: list of errors
    :rtype: list of str
    """
    errors = []
    for k in recipe_keys:
        if k in expected_keys:
            continue
        if k.lower() in expected_keys:
            errors.append(prefix + "%s should be %s" % (k, k.lower()))
    return errors

def check_recipe_dict(recipe_dict):
    """Check a dict before using it to create a new Recipe

    :param recipe_dict: A plain dict of the recipe
    :type recipe_dict: dict
    :returns: True if dict is ok
    :rtype: bool
    :raises: RecipeError

    This checks a dict to make sure required fields are present,
    that optional fields are correct, and that other optional fields
    are of the correct format, when included.

    This collects all of the errors and returns a single RecipeError with
    a string that can be presented to users.
    """
    errors = []

    # Check for wrong case of top level keys
    top_keys = ["name", "description", "version", "modules", "packages", "groups", "repos", "customizations"]
    errors.extend(check_list_case(recipe_dict.keys(), top_keys))

    if "name" not in recipe_dict:
        errors.append("Missing 'name'")
    if "description" not in recipe_dict:
        errors.append("Missing 'description'")
    if "version" in recipe_dict:
        try:
            semver.Version(recipe_dict["version"])
        except ValueError:
            errors.append("Invalid 'version', must use Semantic Versioning")

    # Examine all the modules
    if recipe_dict.get("modules"):
        module_errors = check_required_list(recipe_dict["modules"], ["name", "version"])
        if module_errors:
            errors.append("'modules' errors:\n%s" % "\n".join(module_errors))

    # Examine all the packages
    if recipe_dict.get("packages"):
        package_errors = check_required_list(recipe_dict["packages"], ["name", "version"])
        if package_errors:
            errors.append("'packages' errors:\n%s" % "\n".join(package_errors))

    if recipe_dict.get("groups"):
        groups_errors = check_required_list(recipe_dict["groups"], ["name"])
        if groups_errors:
            errors.append("'groups' errors:\n%s" % "\n".join(groups_errors))

    if recipe_dict.get("repos") and recipe_dict.get("repos").get("git"):
        repos_errors = check_required_list(recipe_dict.get("repos").get("git"),
                           ["rpmname", "rpmversion", "rpmrelease", "summary", "repo", "ref", "destination"])
        if repos_errors:
            errors.append("'repos.git' errors:\n%s" % "\n".join(repos_errors))

    # No customizations to check, exit now
    c = recipe_dict.get("customizations")
    if not c:
        return errors

    # Make sure to catch empty sections by testing for keywords, not just looking at .get() result.
    if "kernel" in c:
        errors.extend(check_list_case(["append"], c["kernel"].keys(), prefix="kernel "))
        if "append" not in c.get("kernel", []):
            errors.append("'customizations.kernel': missing append field.")

    if "sshkey" in c:
        sshkey_errors = check_required_list(c.get("sshkey"), ["user", "key"])
        if sshkey_errors:
            errors.append("'customizations.sshkey' errors:\n%s" % "\n".join(sshkey_errors))

    if "user" in c:
        user_errors = check_required_list(c.get("user"), ["name"])
        if user_errors:
            errors.append("'customizations.user' errors:\n%s" % "\n".join(user_errors))

    if "group" in c:
        group_errors = check_required_list(c.get("group"), ["name"])
        if group_errors:
            errors.append("'customizations.group' errors:\n%s" % "\n".join(group_errors))

    if "timezone" in c:
        errors.extend(check_list_case(["timezone", "ntpservers"], c["timezone"].keys(), prefix="timezone "))
        if not c.get("timezone"):
            errors.append("'customizations.timezone': missing timezone or ntpservers fields.")

    if "locale" in c:
        errors.extend(check_list_case(["languages", "keyboard"], c["locale"].keys(), prefix="locale "))
        if not c.get("locale"):
            errors.append("'customizations.locale': missing languages or keyboard fields.")

    if "firewall" in c:
        errors.extend(check_list_case(["ports"], c["firewall"].keys(), prefix="firewall "))
        if not c.get("firewall"):
            errors.append("'customizations.firewall': missing ports field or services section.")

        if "services" in c.get("firewall", []):
            errors.extend(check_list_case(["enabled", "disabled"], c["firewall"]["services"].keys(), prefix="firewall.services "))
            if not c.get("firewall").get("services"):
                errors.append("'customizations.firewall.services': missing enabled or disabled fields.")

    if "services" in c:
        errors.extend(check_list_case(["enabled", "disabled"], c["services"].keys(), prefix="services "))
        if not c.get("services"):
            errors.append("'customizations.services': missing enabled or disabled fields.")

    return errors

def recipe_from_dict(recipe_dict):
    """Create a Recipe object from a plain dict.

    :param recipe_dict: A plain dict of the recipe
    :type recipe_dict: dict
    :returns: A Recipe object
    :rtype: Recipe
    :raises: RecipeError
    """
    errors = check_recipe_dict(recipe_dict)
    if errors:
        msg = "\n".join(errors)
        raise RecipeError(msg)

    # Make RecipeModule objects from the toml
    # The TOML may not have modules or packages in it. Set them to None in this case
    try:
        if recipe_dict.get("modules"):
            modules = [RecipeModule(m.get("name"), m.get("version")) for m in recipe_dict["modules"]]
        else:
            modules = []
        if recipe_dict.get("packages"):
            packages = [RecipePackage(p.get("name"), p.get("version")) for p in recipe_dict["packages"]]
        else:
            packages = []
        if recipe_dict.get("groups"):
            groups = [RecipeGroup(g.get("name")) for g in recipe_dict["groups"]]
        else:
            groups = []
        if recipe_dict.get("repos") and recipe_dict.get("repos").get("git"):
            gitrepos = [NewRecipeGit(r) for r in recipe_dict["repos"]["git"]]
        else:
            gitrepos = []
        name = recipe_dict["name"]
        description = recipe_dict["description"]
        version = recipe_dict.get("version", None)
        customizations = recipe_dict.get("customizations", None)

        # [customizations] was incorrectly documented at first, so we have to support using it
        # as [[customizations]] by grabbing the first element.
        if isinstance(customizations, list):
            customizations = customizations[0]

    except KeyError as e:
        raise RecipeError("There was a problem parsing the recipe: %s" % str(e))

    return Recipe(name, description, version, modules, packages, groups, customizations, gitrepos)

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
    try:
        parent_commit = head_commit(repo, branch)
    except GLib.GError:
        # Branch doesn't exist, make a new one based on master
        master_head = head_commit(repo, "master")
        repo.create_branch(branch, master_head, 0)
        parent_commit = head_commit(repo, branch)

    parent_commit = head_commit(repo, branch)
    blob_id = repo.create_blob_from_buffer(content.encode("UTF-8"))

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
    :returns: The commit id, and the contents of the commit
    :rtype: tuple(str, str)
    :raises: Can raise errors from Ggit

    If no commit is passed the master:filename is returned, otherwise it will be
    commit:filename
    """
    if not commit:
        # Find the most recent commit for filename on the selected branch
        commits = list_commits(repo, branch, filename, 1)
        if not commits:
            raise RecipeError("No commits for %s on the %s branch." % (filename, branch))
        commit = commits[0].commit
    return (commit, read_commit_spec(repo, "%s:%s" % (commit, filename)))

def read_recipe_commit(repo, branch, recipe_name, commit=None):
    """Read a recipe commit from git and return a Recipe object

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to read
    :type recipe_name: str
    :param commit: Optional commit hash
    :type commit: str
    :returns: A Recipe object
    :rtype: Recipe
    :raises: Can raise errors from Ggit

    If no commit is passed the master:filename is returned, otherwise it will be
    commit:filename
    """
    if not repo_file_exists(repo, branch, recipe_filename(recipe_name)):
        raise RecipeFileError("Unknown blueprint")

    (_, recipe_toml) = read_commit(repo, branch, recipe_filename(recipe_name), commit)
    return recipe_from_toml(recipe_toml)

def read_recipe_and_id(repo, branch, recipe_name, commit=None):
    """Read a recipe commit and its id from git

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to read
    :type recipe_name: str
    :param commit: Optional commit hash
    :type commit: str
    :returns: The commit id, and a Recipe object
    :rtype: tuple(str, Recipe)
    :raises: Can raise errors from Ggit

    If no commit is passed the master:filename is returned, otherwise it will be
    commit:filename
    """
    (commit_id, recipe_toml) = read_commit(repo, branch, recipe_filename(recipe_name), commit)
    return (commit_id, recipe_from_toml(recipe_toml))

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
    return sorted([tree.get(i).get_name() for i in range(0, tree.size())])

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

def revert_recipe(repo, branch, recipe_name, commit):
    """Revert the contents of a recipe to that of a previous commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to revert
    :type recipe_name: str
    :param commit: Commit hash
    :type commit: str
    :returns: OId of the new commit
    :rtype: Git.OId
    :raises: Can raise errors from Ggit
    """
    return revert_file(repo, branch, recipe_filename(recipe_name), commit)

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
    message = "%s reverted to commit %s" % (filename, commit_hash)
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
        old_recipe = read_recipe_commit(repo, branch, recipe["name"])
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
        recipe = recipe_from_file(filename)
    except IOError:
        raise RecipeFileError

    return commit_recipe(repo, branch, recipe)

def commit_recipe_directory(repo, branch, directory):
    r"""Commit all \*.toml files from a directory, if they aren't already in git.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param directory: The directory of \*.toml recipes to commit
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

def tag_recipe_commit(repo, branch, recipe_name):
    """Tag a file's most recent commit

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param recipe_name: Recipe name to tag
    :type recipe_name: str
    :returns: Tag id or None if it failed.
    :rtype: Git.OId
    :raises: Can raise errors from Ggit

    Uses tag_file_commit()
    """
    if not repo_file_exists(repo, branch, recipe_filename(recipe_name)):
        raise RecipeFileError("Unknown blueprint")

    return tag_file_commit(repo, branch, recipe_filename(recipe_name))

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
        return int(tag.rsplit('r', 2)[-1])
    except (ValueError, IndexError):
        return None

class CommitDetails(DataHolder):
    def __init__(self, commit, timestamp, message, revision=None):
        DataHolder.__init__(self,
                            commit = commit,
                            timestamp = timestamp,
                            message = message,
                            revision = revision)

def list_commits(repo, branch, filename, limit=0):
    """List the commit history of a file on a branch.

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: filename to revert
    :type filename: str
    :param limit: Number of commits to return (0=all)
    :type limit: int
    :returns: A list of commit details
    :rtype: list(CommitDetails)
    :raises: Can raise errors from Ggit
    """
    revwalk = Git.RevisionWalker.new(repo)
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
        parent_commits = list(map(parents.get, range(0, parents.get_size())))
        is_diff = all([is_parent_diff(repo, filename, tree, pc) for pc in parent_commits])
        # No changes from parents, skip it.
        if not is_diff:
            continue

        tag = find_commit_tag(repo, branch, filename, commit.get_id())
        try:
            commits.append(get_commit_details(commit, get_revision_from_tag(tag)))
            if limit and len(commits) > limit:
                break
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

def find_field_value(field, value, lst):
    """Find a field matching value in the list of dicts.

    :param field: field to search for
    :type field: str
    :param value: value to match in the field
    :type value: str
    :param lst: List of dict's with field
    :type lst: list of dict
    :returns: First dict with matching field:value, or None
    :rtype: dict or None

    Used to return a specific entry from a list that looks like this:

    [{"name": "one", "attr": "green"}, ...]

    find_field_value("name", "one", lst) will return the matching dict.
    """
    for d in lst:
        if d.get(field) and d.get(field) == value:
            return d
    return None

def find_name(name, lst):
    """Find the dict matching the name in a list and return it.

    :param name: Name to search for
    :type name: str
    :param lst: List of dict's with "name" field
    :type lst: list of dict
    :returns: First dict with matching name, or None
    :rtype: dict or None

    This is just a wrapper for find_field_value with field set to "name"
    """
    return find_field_value("name", name, lst)

def find_recipe_obj(path, recipe, default=None):
    """Find a recipe object

    :param path: A list of dict field names
    :type path: list of str
    :param recipe: The recipe to search
    :type recipe: Recipe
    :param default: The value to return if it is not found
    :type default: Any

    Return the object found by applying the path to the dicts in the recipe, or
    return the default if it doesn't exist.

    eg. {"customizations": {"hostname": "foo", "users": [...]}}

    find_recipe_obj(["customizations", "hostname"], recipe, "")
    """
    o = recipe
    try:
        for p in path:
            if not o.get(p):
                return default
            o = o.get(p)
    except AttributeError:
        return default

    return o

def diff_lists(title, field, old_items, new_items):
    """Return the differences between two lists of dicts.

    :param title: Title of the entry
    :type title: str
    :param field: Field to use as the key for comparisons
    :type field: str
    :param old_items: List of item dicts with "name" field
    :type old_items: list(dict)
    :param new_items: List of item dicts with "name" field
    :type new_items: list(dict)
    :returns: List of diff dicts with old/new entries
    :rtype: list(dict)
    """
    diffs = []
    old_fields= set(m[field] for m in old_items)
    new_fields= set(m[field] for m in new_items)

    added_items = new_fields.difference(old_fields)
    added_items = sorted(added_items, key=lambda n: n.lower())

    removed_items = old_fields.difference(new_fields)
    removed_items = sorted(removed_items, key=lambda n: n.lower())

    same_items = old_fields.intersection(new_fields)
    same_items = sorted(same_items, key=lambda n: n.lower())

    for v in added_items:
        diffs.append({"old":None,
                      "new":{title:find_field_value(field, v, new_items)}})

    for v in removed_items:
        diffs.append({"old":{title:find_field_value(field, v, old_items)},
                      "new":None})

    for v in same_items:
        old_item = find_field_value(field, v, old_items)
        new_item = find_field_value(field, v, new_items)
        if old_item != new_item:
            diffs.append({"old":{title:old_item},
                          "new":{title:new_item}})

    return diffs

def customizations_diff(old_recipe, new_recipe):
    """Diff the customizations sections from two versions of a recipe
    """
    diffs = []
    old_keys = set(old_recipe.get("customizations", {}).keys())
    new_keys = set(new_recipe.get("customizations", {}).keys())

    added_keys = new_keys.difference(old_keys)
    added_keys = sorted(added_keys, key=lambda n: n.lower())

    removed_keys = old_keys.difference(new_keys)
    removed_keys = sorted(removed_keys, key=lambda n: n.lower())

    same_keys = old_keys.intersection(new_keys)
    same_keys = sorted(same_keys, key=lambda n: n.lower())

    for v in added_keys:
        diffs.append({"old": None,
                      "new": {"Customizations."+v: new_recipe["customizations"][v]}})

    for v in removed_keys:
        diffs.append({"old": {"Customizations."+v: old_recipe["customizations"][v]},
                      "new": None})

    for v in same_keys:
        if new_recipe["customizations"][v] == old_recipe["customizations"][v]:
            continue

        if type(new_recipe["customizations"][v]) == type([]):
            # Lists of dicts need to use diff_lists
            # sshkey uses 'user', user and group use 'name'
            if "user" in new_recipe["customizations"][v][0]:
                field_name = "user"
            elif "name" in new_recipe["customizations"][v][0]:
                field_name = "name"
            else:
                raise RuntimeError("%s list has unrecognized key, not 'name' or 'user'" % "customizations."+v)

            diffs.extend(diff_lists("Customizations."+v, field_name, old_recipe["customizations"][v], new_recipe["customizations"][v]))
        else:
            diffs.append({"old": {"Customizations."+v: old_recipe["customizations"][v]},
                          "new": {"Customizations."+v: new_recipe["customizations"][v]}})

    return diffs


def recipe_diff(old_recipe, new_recipe):
    """Diff two versions of a recipe

    :param old_recipe: The old version of the recipe
    :type old_recipe: Recipe
    :param new_recipe: The new version of the recipe
    :type new_recipe: Recipe
    :returns: A list of diff dict entries with old/new
    :rtype: list(dict)
    """

    diffs = []
    # These cannot be added or removed, just different
    for element in ["name", "description", "version"]:
        if old_recipe[element] != new_recipe[element]:
            diffs.append({"old":{element.title():old_recipe[element]},
                          "new":{element.title():new_recipe[element]}})

    # These lists always exist
    diffs.extend(diff_lists("Module", "name", old_recipe["modules"], new_recipe["modules"]))
    diffs.extend(diff_lists("Package", "name", old_recipe["packages"], new_recipe["packages"]))
    diffs.extend(diff_lists("Group", "name", old_recipe["groups"], new_recipe["groups"]))

    # The customizations section can contain a number of different types
    diffs.extend(customizations_diff(old_recipe, new_recipe))

    # repos contains keys that are lists (eg. [[repos.git]])
    diffs.extend(diff_lists("Repos.git", "rpmname",
                            find_recipe_obj(["repos", "git"], old_recipe, []),
                            find_recipe_obj(["repos", "git"], new_recipe, [])))

    return diffs

def repo_file_exists(repo, branch, filename):
    """Return True if the filename exists on the branch

    :param repo: Open repository
    :type repo: Git.Repository
    :param branch: Branch name
    :type branch: str
    :param filename: Filename to check
    :type filename: str
    :returns: True if the filename exists on the HEAD of the branch, False otherwise.
    :rtype: bool
    """
    commit = head_commit(repo, branch).get_id().to_string()
    commit_id = Git.OId.new_from_string(commit)
    commit_obj = repo.lookup(commit_id, Git.Commit)
    tree = commit_obj.get_tree()
    return tree.get_by_name(filename) is not None
