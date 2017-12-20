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
import logging
log = logging.getLogger("lorax-composer")

from flask import current_app
from flask_jwt import JWT, _jwt_required
from functools import wraps
import os
import PAM
import uuid

from pylorax.sysutils import safe_write

def user_allowed(username):
    """Check to see if the user is allowed to use lorax-composer

    :param username: name to lookup in the config file
    :type username: str
    :returns: True if the user is allowed, False otherwise
    :rtype: bool

    If the username is set to "1" in the configuration file's users
    section then it returns True. All other cases return False.
    """
    return current_app.config["COMPOSER_CFG"].get_default("users", username, "0") == "1"

def check_unpw(un, pw, service="passwd"):
    """Check the username and password authentication.

    :param un: username
    :type un: str
    :param pw: password
    :type pw: str
    :param service: Service to authenticate against. Default is "passwd"
    :type service: str
    :returns: True if the user is authenticated, False if not, or if there was an error

    Use PAM to authenticate the user with the local system.
    """
    def pam_conv(auth, query_list):
        responses = []
        for _query, typ in query_list:
            if typ == PAM.PAM_PROMPT_ECHO_OFF:
                responses.append((pw,0))
            else:
                responses.append(())
        return responses

    auth = PAM.pam()
    auth.start(service)
    auth.set_item(PAM.PAM_USER, un)
    auth.set_item(PAM.PAM_CONV, pam_conv)

    try:
        auth.authenticate()
    except PAM.error as e:
        log.debug("Authentication for %s failed: %s", un, e)
        return False
    except Exception as e:
        log.debug("Authentication for %s failed: %s", un, e)
        return False

    return user_allowed(un)

class User(object):
    def __init__(self, username):
        self.id = username

def jwt_test_auth(username, password):
    """Test authentication

    :param username: User to authenticate
    :type username: str
    :param password: User's password to use for authentication
    :type password: str
    :returns: username if they are authenticated, None otherwise
    :rtype: str or None

    This method is only successfull for testuser:goodpassword
    and should ONLY be used for testing.
    """
    if username == "testuser" and password == "goodpassword":
        return User(username)
    else:
        return None

def jwt_auth(username, password):
    """Authenticate a user

    :param username: User to authenticate
    :type username: str
    :param password: User's password to use for authentication
    :type password: str
    :returns: username if they are authenticated, None otherwise
    :rtype: str or None
    """
    if check_unpw(username, password) == True:
        return User(username)
    else:
        return None

def jwt_identity(payload):
    """Return details about the user
    """
    return payload["identity"]

def auth_enabled():
    """Return True if the configuration file has disabled authentication
    """
    # Authentication can be disabled via the config file
    return current_app.config["COMPOSER_CFG"].get("composer", "auth") != "0"

def authenticate():
    """API Route decorator

    Authentication can be disabled by setting the "auth" config value to "0"

    NOTE: This uses a private method from flask-jwt, _jwt_required
    """
    def wrapper(fn):
        @wraps(fn)
        def decorator(*args, **kwargs):
            if auth_enabled():
                _jwt_required(current_app.config['JWT_DEFAULT_REALM'])
            return fn(*args, **kwargs)
        return decorator
    return wrapper

def setup_jwt(server, test_user=False):
    """Initialize JWT for the server application

    :param server: Flask server
    :type server: Flask
    :param test_user: Use the test user instead of local system users
    :type test_user: bool

    If test_user is set to True the authentication will be done using
    jwt_test_auth function. Otherwise it uses local users and the jwt_auth
    function.
    """
    # Use a new secret key
    server.config["JWT_SECRET_KEY"] = uuid.uuid4().hex
    server.config["JWT_AUTH_URL_RULE"] = "/api/auth"

    # If we have a safe place to write the secret, do so in a secure manner.
    try:
        if os.stat("/var/run/lorax").st_mode & 0o007 == 0:
            with safe_write("/var/run/lorax/composer-secret", 0o750) as f:
                f.write(server.config["JWT_SECRET_KEY"])
        else:
            log.info("/var/run/lorax has unsafe permissions. Not writing secret.")
    except OSError:
        log.info("/var/run/lorax is missing. Not writing secret.")

    if test_user:
        # Setup test auth
        JWT(server, jwt_test_auth, jwt_identity)
    else:
        # Initialize JWT support
        JWT(server, jwt_auth, jwt_identity)
