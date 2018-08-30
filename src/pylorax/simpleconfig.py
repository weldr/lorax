#
# simpleconifg.py - representation of a simple configuration file (sh-like)
#
# Copyright (C) 1999-2015 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#
import os
import shlex
import string  # pylint: disable=deprecated-module
import tempfile

import unicodedata
# Used for ascii_lowercase, ascii_uppercase constants
import string  # pylint: disable=deprecated-module

_SAFECHARS = frozenset(string.ascii_letters + string.digits + '@%_-+=:,./')

def unquote(s):
    return ' '.join(shlex.split(s))

def quote(s, always=False):
    """ If always is set it returns a quoted value
    """
    if not always:
        for c in s:
            if c not in _SAFECHARS:
                break
        else:
            return s
    return '"' + s.replace('"', '\\"') + '"'

def find_comment(s):
    """ Look for a # comment outside of a quoted string.
        If there are no quotes, find the last # in the string.

        :param str s: string to check for comment and quotes
        :returns: index of comment or None
        :rtype: int or None

        Handles comments inside quotes and quotes inside quotes.
    """
    q = None
    for i in range(len(s)):
        if not q and s[i] == '#':
            return i

        # Ignore quotes inside other quotes
        if s[i] in "'\"":
            if s[i] == q:
                q = None
            elif q is None:
                q = s[i]
    return None


def write_tmpfile(filename, data):
    # Create a temporary in the same directory as the target file to ensure
    # the new file is on the same filesystem
    tmpf = tempfile.NamedTemporaryFile(mode="w", delete=False,
                                       dir=os.path.dirname(filename) or '.',
                                       prefix="." + os.path.basename(filename))
    tmpf.write(data)
    tmpf.close()

    # Change the permissions (currently 0600) to match the original file
    if os.path.exists(filename):
        m = os.stat(filename).st_mode
    else:
        m = 0o0644
    os.chmod(tmpf.name, m)

    # Move the temporary file over the top of the original
    os.rename(tmpf.name, filename)

class SimpleConfigFile(object):
    """ Edit values in a configuration file without changing comments.
        Supports KEY=VALUE lines and ignores everything else.
        Supports adding new keys.
        Supports deleting keys.
        Preserves comment, blank lines and comments on KEY lines
        Does not support duplicate key entries.
    """
    def __init__(self, filename=None, read_unquote=True, write_quote=True,
                 always_quote=False):
        self.filename = filename
        self.read_unquote = read_unquote
        self.write_quote = write_quote
        self.always_quote = always_quote
        self.reset()

    def reset(self):
        self._lines = []
        self.info = {}

    def read(self, filename=None):
        """ passing filename will override the filename passed to init.

            save the lines into self._lines and the key/value pairs into
            self.info
        """
        filename = filename or self.filename
        with open(filename) as f:
            for line in f:
                self._lines.append(line)
                key, value, _comment = self._parseline(line)
                if key:
                    self.info[key] = value

    def write(self, filename=None, use_tmp=True):
        """ passing filename will override the filename passed to init.
        """
        filename = filename or self.filename
        if not filename:
            return None

        if use_tmp:
            write_tmpfile(filename, str(self))
        else:
            # write directly to the file
            with open(filename, "w") as fobj:
                fobj.write(str(self))

    def set(self, *args):
        for key, value in args:
            self.info[self._upperASCII(key)] = value

    def unset(self, *keys):
        for key in (self._upperASCII(k) for k in keys):
            if key in self.info:
                del self.info[key]

    def get(self, key):
        return self.info.get(self._upperASCII(key), "")

    def _parseline(self, line):
        """ parse a line into a key, value and comment

            :param str line: Line to be parsed
            :returns: Tuple of key, value, comment
            :rtype: tuple

            Handle comments and optionally unquote quoted strings
            Returns (key, value, comment) or (None, None, comment)
            key is always UPPERCASE and comment may by "" if none was found.
        """
        s = line.strip()
        # Look for a # outside any quotes
        comment = ""
        comment_index = find_comment(s)
        if comment_index is not None:
            comment = s[comment_index:]
            s = s[:comment_index]   # remove from comment to EOL

        key, eq, val = s.partition('=')
        key = key.strip()
        val = val.strip()
        if self.read_unquote:
            val = unquote(val)
        if key != '' and eq == '=':
            return (self._upperASCII(key), val, comment)
        else:
            return (None, None, comment)

    def _kvpair(self, key, comment=""):
        value = self.info[key]
        if self.write_quote or self.always_quote:
            value = quote(value, self.always_quote)
        if comment:
            comment = " " + comment
        return key + '=' + value + comment + "\n"

    def __str__(self):
        """ Return the file that was read, replacing existing keys with new values
            removing keys that have been deleted and adding new keys.
        """
        oldkeys = []
        s = ""
        for line in self._lines:
            key, _value, comment = self._parseline(line)
            if key is None:
                s += line
            else:
                if key not in self.info:
                    continue
                oldkeys.append(key)
                s += self._kvpair(key, comment)

        # Add new keys
        for key in self.info:
            if key not in oldkeys:
                s += self._kvpair(key)

        return s

    def _ensure_str(self, str_or_bytes, keep_none=True):
        """
        Returns a str instance for given string or ``None`` if requested
        to keep it.
        
        :param str_or_bytes: string to be kept or converted to str type
        :type str_or_bytes: str or bytes
        :param bool keep_none: whether to keep None as it is or raise
                               ValueError if ``None`` is passed
        :raises ValueError: if applied on an object not being of type
                            bytes nor str (nor NoneType if ``keep_none``
                            is ``False``)
        """

        if keep_none and str_or_bytes is None:
            return None
        elif isinstance(str_or_bytes, str):
            return str_or_bytes
        elif isinstance(str_or_bytes, bytes):
            return str_or_bytes.decode(sys.getdefaultencoding())
        else:
            raise ValueError("str_or_bytes must be of type 'str' or 'bytes', not '%s'" % type(str_or_bytes))

    # Define translation to ASCII uppercase for locale-independent string
    # conversions. The table is a 256-byte string used with str.translate.
    # If str.translate is used with a unicode string, even if the string
    # contains only 7-bit characters, str.translate will raise a
    # UnicodeDecodeError.
    _ASCIIupper_table = str.maketrans(string.ascii_lowercase, string.ascii_uppercase)

    def _toASCII(self, s):
        """Convert a unicode string to ASCII"""
        if isinstance(s, str):
            # Decompose the string using the NFK decomposition, which in
            # addition to the canonical decomposition replaces characters
            # based on compatibility equivalence (e.g., ROMAN NUMERAL ONE
            # has its own code point but it's really just a capital I), so
            # that we can keep as much of the ASCII part of the string as
            # possible.
            s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode("ascii")
        elif not isinstance(s, bytes):
            s = ''
        return s

    def _upperASCII(self, s):
        """
        Convert a string to uppercase using only ASCII character definitions.

        The returned string will contain only ASCII characters. This function
        is locale-independent.
        """

        # XXX: Python 3 has str.maketrans() and bytes.maketrans() so we should
        # ideally use one or the other depending on the type of 's'. But it turns
        # out we expect this function to always return string even if given bytes.
        s = self._ensure_str(s)
        return str.translate(self._toASCII(s), self._ASCIIupper_table)
