#!/usr/bin/python
# Demonstrates how to authenticate against a Subversion server.
#
# Authentication in Subversion is handled by an Auth object that wraps
# a list of "auth providers". A provider is queried whenever the server
# needs a particular kind of credential (username, password, SSL client
# certificate, SSL server trust decision, ...). Providers are tried in
# order, so put more specific providers before more general ones.
#
# Stock providers fall into two families:
#   * ``get_*_provider`` -- read cached credentials from ~/.subversion
#   * ``get_*_prompt_provider`` -- invoke a Python callback (typically to
#     ask the user interactively)
#
# Defaults for common parameters (such as the username or password) can
# be set with ``auth.set_parameter``; ``get_simple_provider`` will use
# those before falling back to prompting.

import sys

import subvertpy
from subvertpy import ra
from subvertpy.ra import Auth, RemoteAccess


def simple_prompt(realm, username, may_save):
    """Prompt for a username and password on the terminal.

    Return a (username, password, may_save) tuple.
    """
    import getpass

    print(f"Authentication realm: {realm}")
    if not username:
        username = input("Username: ")
    password = getpass.getpass(f"Password for {username!r}: ")
    return (username, password, False)


def ssl_server_trust_prompt(realm, failures, cert_info, may_save):
    """Decide whether to trust an SSL server certificate.

    ``failures`` is a bitmask of the ``subvertpy.SSL_*`` flags describing
    what is wrong with the certificate (unknown CA, hostname mismatch,
    expired, ...). ``cert_info`` is a dict with keys ``hostname``,
    ``fingerprint``, ``valid_from``, ``valid_until``, ``issuer_dname``
    and ``ascii_cert``.

    Return a (accepted_failures, may_save) tuple to accept the cert, or
    ``None`` to reject it. ``cert_info`` may be ``None`` if Subversion
    could not parse the certificate.
    """
    print(f"Certificate problem for realm {realm!r}:")
    if failures & subvertpy.SSL_UNKNOWNCA:
        print("  issuer is not trusted")
    if failures & subvertpy.SSL_CNMISMATCH:
        print("  hostname does not match certificate")
    if failures & subvertpy.SSL_NOTYETVALID:
        print("  certificate is not yet valid")
    if failures & subvertpy.SSL_EXPIRED:
        print("  certificate has expired")
    if cert_info is not None:
        print(f"  hostname:    {cert_info['hostname']}")
        print(f"  fingerprint: {cert_info['fingerprint']}")
        print(
            f"  valid:       {cert_info['valid_from']} until {cert_info['valid_until']}"
        )
        print(f"  issuer:      {cert_info['issuer_dname']}")
    answer = input("(R)eject or accept (t)emporarily? ").strip().lower()
    if answer == "t":
        return (failures, False)
    return None


def make_auth(username=None, password=None):
    """Build an Auth object suitable for a typical https/basic-auth setup.

    The list below covers the credential kinds most callers care about:
      * ``get_simple_provider`` and ``get_username_provider`` read cached
        (username, password) pairs from ~/.subversion.
      * The three ``ssl_*_file_provider`` calls read cached client
        certificates, client certificate passphrases and server trust
        decisions, respectively.
      * The corresponding ``*_prompt_provider`` calls fall back to
        prompting the user interactively when no cached credential
        matches.
    """
    providers = [
        ra.get_simple_provider(),
        ra.get_username_provider(),
        ra.get_ssl_client_cert_file_provider(),
        ra.get_ssl_client_cert_pw_file_provider(),
        ra.get_ssl_server_trust_file_provider(),
        ra.get_simple_prompt_provider(simple_prompt, 3),
        ra.get_ssl_server_trust_prompt_provider(ssl_server_trust_prompt),
    ]
    # On Windows/macOS, add platform-specific providers (Windows crypto
    # API, macOS Keychain) so cached OS-level credentials are used.
    providers.extend(ra.get_platform_specific_client_providers())
    auth = Auth(providers)
    if username is not None:
        auth.set_parameter(subvertpy.AUTH_PARAM_DEFAULT_USERNAME, username)
    if password is not None:
        auth.set_parameter(subvertpy.AUTH_PARAM_DEFAULT_PASSWORD, password)
    return auth


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(f"usage: {sys.argv[0]} URL [USERNAME [PASSWORD]]")
    url = sys.argv[1]
    username = sys.argv[2] if len(sys.argv) > 2 else None
    password = sys.argv[3] if len(sys.argv) > 3 else None

    conn = RemoteAccess(url, auth=make_auth(username, password))
    print(f"Connected to {url}, HEAD is r{conn.get_latest_revnum()}")
