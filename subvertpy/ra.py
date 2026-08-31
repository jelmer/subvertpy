# Copyright (C) 2006-2008 Jelmer Vernooij <jelmer@jelmer.uk>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.

# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301, USA
"""Access to remote Subversion repositories.

The :func:`RemoteAccess` object represents a connection to a Subversion
server. When the server requires credentials (basic auth over http/https,
SSL client certificates, etc.), pass an ``auth`` keyword holding an
:class:`Auth` object built from a list of "auth providers"::

    from subvertpy import ra
    from subvertpy.ra import Auth, RemoteAccess

    auth = Auth([
        ra.get_simple_provider(),
        ra.get_username_provider(),
        ra.get_ssl_client_cert_file_provider(),
        ra.get_ssl_client_cert_pw_file_provider(),
        ra.get_ssl_server_trust_file_provider(),
    ])
    # Optionally hardcode a default username/password rather than
    # reading from ~/.subversion or prompting:
    # auth.set_parameter(subvertpy.AUTH_PARAM_DEFAULT_USERNAME, "alice")
    # auth.set_parameter(subvertpy.AUTH_PARAM_DEFAULT_PASSWORD, "s3cret")
    conn = RemoteAccess("https://svn.example.com/repo", auth=auth)

Providers are tried in order. The ``get_*_provider`` functions read
cached credentials from ``~/.subversion``; the ``get_*_prompt_provider``
variants invoke a Python callback to obtain credentials interactively.
See ``examples/ra_auth.py`` for a fuller example, including SSL server
trust handling.
"""

__author__ = "Jelmer Vernooij <jelmer@jelmer.uk>"

from subvertpy import (
    ERR_BAD_URL,
    SubversionException,
    _ra,
    ra_svn,  # noqa: F401
)
from subvertpy._ra import *  # noqa: F403

url_handlers = {
    "svn": _ra.RemoteAccess,
    # "svn": ra_svn.Client,
    "svn+ssh": _ra.RemoteAccess,
    # "svn+ssh": ra_svn.Client,
    "http": _ra.RemoteAccess,
    "https": _ra.RemoteAccess,
    "file": _ra.RemoteAccess,
}


def RemoteAccess(  # type: ignore[no-redef]
    url: str | bytes, *args: object, **kwargs: object
) -> _ra.RemoteAccess:
    """Connect to a remote Subversion server.

    :param url: URL to connect to
    :return: RemoteAccess object
    """
    if isinstance(url, bytes):
        url = url.decode("utf-8")
    scheme, _, _ = url.partition(":")
    if scheme not in url_handlers:
        raise SubversionException(f"Unknown URL type '{scheme}'", ERR_BAD_URL)
    # Kwargs are forwarded to the underlying RemoteAccess constructor,
    # which validates them; the object-typed *args/**kwargs here can't
    # be statically matched to the typed constructor parameters.
    return url_handlers[scheme](url, *args, **kwargs)  # type: ignore[arg-type]
