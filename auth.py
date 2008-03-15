# Copyright (C) 2005-2007 Jelmer Vernooij <jelmer@samba.org>
 
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Authentication token retrieval."""

from bzrlib.config import AuthenticationConfig
from bzrlib.ui import ui_factory
from ra import (get_username_prompt_provider,
                get_simple_prompt_provider,
                get_ssl_server_trust_prompt_provider,
                get_ssl_client_cert_pw_prompt_provider,
                get_simple_provider, get_username_provider, 
                get_ssl_client_cert_file_provider, 
                get_ssl_client_cert_pw_file_provider,
                get_ssl_server_trust_file_provider
                )
from ra import Auth
import constants
import client

class SubversionAuthenticationConfig(AuthenticationConfig):
    """Simple extended version of AuthenticationConfig that can provide 
    the information Subversion requires.
    """
    def __init__(self, file=None, scheme="svn", host=None):
        super(SubversionAuthenticationConfig, self).__init__(file)
        self.scheme = scheme
        self.host = host

    def get_svn_username(self, realm, may_save):
        """Look up a Subversion user name in the Bazaar authentication cache.

        :param realm: Authentication realm (optional)
        :param may_save: Whether or not the username should be saved.
        """
        username = self.get_user(self.scheme, host=self.host, realm=realm)
        return (username, False)

    def get_svn_simple(self, realm, username, may_save, pool):
        """Look up a Subversion user name+password combination in the Bazaar 
        authentication cache.

        :param realm: Authentication realm (optional)
        :param username: Username, if it is already known, or None.
        :param may_save: Whether or not the username should be saved.
        :param pool: Allocation pool, is ignored.
        """
        username = username or self.get_username(realm, may_save, 
                                             pool, prompt="%s password" % realm)
        password = self.get_password(self.scheme, host=self.host, 
                                    user=simple_cred.username, realm=realm,
                                    prompt="%s password" % realm)
        return (username, password, False)

    def get_svn_ssl_server_trust(self, realm, failures, cert_info, may_save, 
                                 pool):
        """Return a Subversion auth provider that verifies SSL server trust.

        :param realm: Realm name (optional)
        :param failures: Failures to check for (bit field, SVN_AUTH_SSL_*)
        :param cert_info: Certificate information
        :param may_save: Whether this information may be stored.
        """
        credentials = self.get_credentials(self.scheme, host=self.host)
        if (credentials is not None and 
            credentials.has_key("verify_certificates") and 
            credentials["verify_certificates"] == False):
            accepted_failures = (
                    constants.AUTH_SSL_NOTYETVALID + 
                    constants.AUTH_SSL_EXPIRED +
                    constants.AUTH_SSL_CNMISMATCH +
                    constants.AUTH_SSL_UNKNOWNCA +
                    constants.AUTH_SSL_OTHER)
        else:
            accepted_failures = 0
        return (accepted_failures, False)

    def get_svn_username_prompt_provider(self, retries):
        """Return a Subversion auth provider for retrieving the username, as 
        accepted by svn_auth_open().
        
        :param retries: Number of allowed retries.
        """
        return get_username_prompt_provider(self.get_svn_username, 
                                                     retries)

    def get_svn_simple_prompt_provider(self, retries):
        """Return a Subversion auth provider for retrieving a 
        username+password combination, as accepted by svn_auth_open().
        
        :param retries: Number of allowed retries.
        """
        return get_simple_prompt_provider(self.get_svn_simple, retries)

    def get_svn_ssl_server_trust_prompt_provider(self):
        """Return a Subversion auth provider for checking 
        whether a SSL server is trusted."""
        return get_ssl_server_trust_prompt_provider(
                    self.get_svn_ssl_server_trust)

    def get_svn_auth_providers(self):
        """Return a list of auth providers for this authentication file.
        """
        return [self.get_svn_username_prompt_provider(1),
                self.get_svn_simple_prompt_provider(1),
                self.get_svn_ssl_server_trust_prompt_provider()]


def get_ssl_client_cert_pw(realm, may_save, pool):
    """Simple SSL client certificate password prompter.

    :param realm: Realm, optional.
    :param may_save: Whether the password can be cached.
    """
    password = ui_factory.get_password(
            "Please enter password for client certificate[realm=%s]" % realm)
    return (password, False)


def get_ssl_client_cert_pw_provider(tries):
    return get_ssl_client_cert_pw_prompt_provider(
                get_ssl_client_cert_pw, tries)


def create_auth_baton():
    """Create a Subversion authentication baton. """
    # Give the client context baton a suite of authentication
    # providers.h
    providers = []
    providers += SubversionAuthenticationConfig().get_svn_auth_providers()
    providers += [
        get_ssl_client_cert_pw_provider(1),
        get_simple_provider(),
        get_username_provider(),
        get_ssl_client_cert_file_provider(),
        get_ssl_client_cert_pw_file_provider(),
        get_ssl_server_trust_file_provider(),
        ]

    if hasattr(client, 'get_windows_simple_provider'):
        providers.append(client.get_windows_simple_provider())

    if hasattr(client, 'get_keychain_simple_provider'):
        providers.append(client.get_keychain_simple_provider())

    if hasattr(client, 'get_windows_ssl_server_trust_provider'):
        providers.append(client.get_windows_ssl_server_trust_provider())

    return Auth(providers)

