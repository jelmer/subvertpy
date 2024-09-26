#!/usr/bin/env python3
# Setup file for subvertpy
# Copyright (C) 2005-2010 Jelmer Vernooij <jelmer@jelmer.uk>

import errno
import os
import re
import shlex
import subprocess
import sys

from setuptools import setup
from setuptools.extension import Extension
from setuptools_rust import Binding, RustExtension


def split_shell_results(line):
    return shlex.split(line)


def config_value(command, env, args):
    command = os.environ.get(env, command)
    try:
        return subprocess.check_output([command, *args]).strip().decode()
    except OSError as e:
        if e.errno == errno.ENOENT:
            raise Exception(
                f"{command} not found. Please set {env} environment variable")
        raise


def apr_config(args):
    return config_value("apr-1-config", "APR_CONFIG", args)


def apu_config(args):
    return config_value("apu-1-config", "APU_CONFIG", args)


def apr_build_data():
    """Determine the APR header file location."""
    try:
        includedir = os.environ['APR_INCLUDE_DIR']
    except KeyError:
        includedir = apr_config(["--includedir"])
    if not os.path.isdir(includedir):
        raise Exception("APR development headers not found")
    try:
        extra_link_flags = split_shell_results(
            os.environ['APR_LINK_FLAGS'])
    except KeyError:
        extra_link_flags = split_shell_results(
            apr_config(["--link-ld", "--libs"]))
    return (includedir, extra_link_flags)


def apu_build_data():
    """Determine the APR util header file location."""
    try:
        includedir = os.environ['APU_INCLUDE_DIR']
    except KeyError:
        includedir = apu_config(["--includedir"])
    if not os.path.isdir(includedir):
        raise Exception("APR util development headers not found")
    try:
        extra_link_flags = split_shell_results(
            os.environ['APU_LINK_FLAGS'])
    except KeyError:
        extra_link_flags = split_shell_results(
            apu_config(["--link-ld", "--libs"]))
    return (includedir, extra_link_flags)


def svn_build_data():
    """Determine the Subversion header file location."""
    if "SVN_HEADER_PATH" in os.environ and "SVN_LIBRARY_PATH" in os.environ:
        return ([os.getenv("SVN_HEADER_PATH")],
                [os.getenv("SVN_LIBRARY_PATH")], [])
    svn_prefix = os.getenv("SVN_PREFIX")
    if svn_prefix is None:
        basedirs = ["/usr/local", "/usr"]
        for basedir in basedirs:
            includedir = os.path.join(basedir, "include/subversion-1")
            if os.path.isdir(includedir):
                svn_prefix = basedir
                break
    if svn_prefix is not None:
        return ([os.path.join(svn_prefix, "include/subversion-1")],
                [os.path.join(svn_prefix, "lib")], [])
    raise Exception("Subversion development files not found. "
                    "Please set SVN_PREFIX or (SVN_LIBRARY_PATH and "
                    "SVN_HEADER_PATH) environment variable. ")


def is_keychain_provider_available():
    """Checks for the availability of the Keychain simple authentication provider
    in Subversion by compiling a simple test program.
    """
    abd = apr_build_data()
    sbd = svn_build_data()
    gcc_command_args = (
            ['gcc'] + ['-I' + inc for inc in sbd[0]] +
            ['-L' + lib for lib in sbd[1]] +
            ['-I' + abd[0], '-lsvn_subr-1', '-x', 'c', '-'])
    gcc = subprocess.Popen(
            gcc_command_args,
            stdin=subprocess.PIPE, universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    gcc.communicate("""
#include <svn_auth.h>
int main(int argc, const char* arv[]) {
    svn_auth_get_keychain_simple_provider(NULL, NULL);
}
""")
    return (gcc.returncode == 0)


class VersionQuery:

    def __init__(self, filename):
        self.filename = filename
        f = open(filename, "rU")
        try:
            self.text = f.read()
        finally:
            f.close()

    def grep(self, what):
        m = re.search(rf"^#define\s+{what}\s+(\d+)\s*$", self.text,
                      re.MULTILINE)
        if not m:
            raise Exception(
                    f"Definition for {what} was not found in file {self.filename}.")
        return int(m.group(1))


(apr_includedir, apr_link_flags) = apr_build_data()
(apu_includedir, apu_link_flags) = apu_build_data()
(svn_includedirs, svn_libdirs, svn_link_flags) = svn_build_data()


class SvnExtension(Extension):

    def __init__(self, name, *args, **kwargs):
        if sys.platform == 'win32':
            libraries = kwargs.get('libraries', [])
            modified = True
            while modified:
                modified = False
                for lib in libraries:
                    for extra in deep_deps.get(lib, []):
                        if extra not in libraries:
                            modified = True
                            libraries.append(extra)
            kwargs['libraries'] = libraries
        kwargs["include_dirs"] = ([apr_includedir, apu_includedir, *svn_includedirs, "subvertpy"])
        kwargs["library_dirs"] = svn_libdirs
        # Note that the apr-util link flags are not included here, as
        # subvertpy only uses some apr util constants but does not use
        # the library directly.
        kwargs["extra_link_args"] = (
            apr_link_flags + apu_link_flags + svn_link_flags)
        if os.name == 'nt':
            # APR needs WIN32 defined.
            kwargs["define_macros"] = [("WIN32", None)]
        if sys.platform == 'darwin':
            # on Mac OS X, we need to check for Keychain availability
            if is_keychain_provider_available():
                if "define_macros" not in kwargs:
                    kwargs["define_macros"] = []
                kwargs["define_macros"].extend((
                    ('DARWIN', None),
                    ('SVN_KEYCHAIN_PROVIDER_AVAILABLE', '1'))
                    )
        Extension.__init__(self, name, *args, **kwargs)


def source_path(filename):
    return os.path.join("subvertpy", filename)


# Urgh. It's a pain having to maintain these manually. But what else can we do?
subr_deep_deps = [
    "svn_subr-1",
    "sqlite3",
    "zlib",
    "advapi32",
    "crypt32",
    "libexpat",
    "shell32",
    "ws2_32",
    "mswsock",
    "version",
    "ole32",
    ]


repos_deep_deps = [
    "svn_repos-1",
    "svn_fs-1",
    "libsvn_fs_util-1",
    "libsvn_fs_fs-1",
    "libsvn_fs_x-1",
    "svn_delta-1",
    ]


ra_deep_deps = [
    "libsvn_ra_svn-1",
    "libsvn_ra_local-1",
    "svn_repos-1",
    ]


deep_deps = {
    "svn_ra-1": ra_deep_deps,
    "svn_repos-1": repos_deep_deps,
    "svn_subr-1": subr_deep_deps,
}


def subvertpy_modules():
    return [
        SvnExtension(
            "subvertpy.client",
            [source_path(n)
                for n in ("client.c", "editor.c", "util.c", "_ra.c", "wc.c")],
            libraries=["svn_client-1", "svn_diff-1", "svn_delta-1",
                       "svn_wc-1", "svn_ra-1", "svn_subr-1"]),
        SvnExtension(
            "subvertpy.repos", [source_path(n) for n in ("repos.c", "util.c")],
            libraries=["svn_repos-1", "svn_subr-1"]),
        SvnExtension(
            "subvertpy.wc",
            [source_path(n) for n in
                ["wc.c", "util.c", "editor.c"]],
            libraries=["svn_wc-1", "svn_diff-1", "svn_delta-1", "svn_subr-1"]),
        ]


def package_data():
    if sys.platform == 'win32':
        return {'subvertpy': ['subvertpy/*.dll']}
    else:
        return {}


if __name__ == "__main__":
    setup(packages=['subvertpy'],
          package_data=package_data(),
          ext_modules=subvertpy_modules(),
          rust_extensions=[
              RustExtension(
                  "subvertpy.subr", "subr/Cargo.toml", binding=Binding.PyO3),
              RustExtension(
                  "subvertpy._ra", "ra/Cargo.toml", binding=Binding.PyO3),
          ],
          scripts=['bin/subvertpy-fast-export'],
          )
