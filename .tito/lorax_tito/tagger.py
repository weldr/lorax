import os

from tito.common import debug, run_command, replace_version
from tito.compat import StringIO
from tito.tagger import VersionTagger


class PyProjectTagger(VersionTagger):
    """
    Tagger that replaces the version in a pyproject.toml file instead
    of setup.py

    Add this to tito.props to enable it:
    [buildconfig]
    lib_dir = .tito/
    tagger = lorax_tito.PyProjectTagger
    """

    def _update_setup_py(self, new_version):
        # Update setup.py using the superclass' version
        # This also handles any version template files
        super(PyProjectTagger, self)._update_setup_py(new_version)

        pyproject_file = os.path.join(self.full_project_dir, "pyproject.toml")
        if not os.path.exists(pyproject_file):
            return

        debug("Found pyproject.toml, attempting to update version.")

        # NOTE: This is just a copy of the core of _update_setup_py since the
        # version field is 'version="x.y.z"' in toml as well as python

        # We probably don't want version-release in setup.py as release is
        # an rpm concept. Hopefully this assumption on
        py_new_version = new_version.split('-')[0]

        f = open(pyproject_file, 'r')
        buf = StringIO()
        for line in f.readlines():
            buf.write(replace_version(line, py_new_version))
        f.close()

        # Write out the new setup.py file contents:
        f = open(pyproject_file, 'w')
        f.write(buf.getvalue())
        f.close()
        buf.close()

        run_command("git add %s" % pyproject_file)
