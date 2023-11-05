#!/usr/bin/env python
# Setup file for subvertpy
# Copyright (C) 2005-2010 Jelmer Vernooij <jelmer@jelmer.uk>

from distutils.core import setup, Command
from distutils.extension import Extension
from distutils import log
import sys
import os
import re
import subprocess
from setuptools_rust import RustExtension, Binding, Strip


class CommandException(Exception):
    """Encapsulate exit status of command execution"""

    def __init__(self, msg, cmd, arg, status, val):
        self.message = msg % (cmd, val)
        Exception.__init__(self, self.message)
        self.cmd = cmd
        self.arg = arg
        self.status = status

    def not_found(self):
        return os.WIFEXITED(self.status) and os.WEXITSTATUS(self.status) == 127


def split_shell_results(line):
    return [s for s in line.split(" ") if s != ""]


def run_cmd(cmd, arg):
    """Run specified command with given arguments, handling status"""
    f = os.popen("'%s' %s" % (cmd, arg))
    dir = f.read().rstrip("\n")
    status = f.close()
    if status is None:
        return dir
    if os.WIFEXITED(status):
        code = os.WEXITSTATUS(status)
        if code == 0:
            return dir
        raise CommandException("%s exited with status %d",
                               cmd, arg, status, code)
    if os.WIFSIGNALED(status):
        signal = os.WTERMSIG(status)
        raise CommandException("%s killed by signal %d",
                               cmd, arg, status, signal)
    raise CommandException("%s terminated abnormally (%d)",
                           cmd, arg, status, status)


def config_value(command, arg):
    cmds = [command] + [
            os.path.join(p, command) for p in
            ["/usr/local/apr/bin/", "/opt/local/bin/"]]
    for cmd in cmds:
        try:
            return run_cmd(cmd, arg)
        except CommandException as e:
            if not e.not_found():
                raise
    else:
        raise Exception("apr-config not found."
                        " Please set APR_CONFIG environment variable")


def apr_config(arg):
    config_cmd = os.getenv("APR_CONFIG")
    if config_cmd is None:
        return config_value("apr-1-config", arg)
    else:
        return run_cmd(config_cmd, arg)


def apu_config(arg):
    config_cmd = os.getenv("APU_CONFIG")
    if config_cmd is None:
        return config_value("apu-1-config", arg)
    else:
        return run_cmd(config_cmd, arg)


def apr_build_data():
    """Determine the APR header file location."""
    includedir = apr_config("--includedir")
    if not os.path.isdir(includedir):
        raise Exception("APR development headers not found")
    extra_link_flags = apr_config("--link-ld --libs")
    return (includedir, split_shell_results(extra_link_flags))


def apu_build_data():
    """Determine the APR util header file location."""
    includedir = apu_config("--includedir")
    if not os.path.isdir(includedir):
        raise Exception("APR util development headers not found")
    extra_link_flags = apu_config("--link-ld --libs")
    return (includedir, split_shell_results(extra_link_flags))


def svn_build_data():
    """Determine the Subversion header file location."""
    if "SVN_HEADER_PATH" in os.environ and "SVN_LIBRARY_PATH" in os.environ:
        return ([os.getenv("SVN_HEADER_PATH")],
                [os.getenv("SVN_LIBRARY_PATH")], [], [])
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
                [os.path.join(svn_prefix, "lib")], [], [])
    raise Exception("Subversion development files not found. "
                    "Please set SVN_PREFIX or (SVN_LIBRARY_PATH and "
                    "SVN_HEADER_PATH) environment variable. ")


def is_keychain_provider_available():
    """
    Checks for the availability of the Keychain simple authentication provider
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


class VersionQuery(object):

    def __init__(self, filename):
        self.filename = filename
        f = open(filename, "rU")
        try:
            self.text = f.read()
        finally:
            f.close()

    def grep(self, what):
        m = re.search(r"^#define\s+%s\s+(\d+)\s*$" % (what,), self.text,
                      re.MULTILINE)
        if not m:
            raise Exception(
                    "Definition for %s was not found in file %s." %
                    (what, self.filename))
        return int(m.group(1))


(apr_includedir, apr_link_flags) = apr_build_data()
(apu_includedir, apu_link_flags) = apu_build_data()
(svn_includedirs, svn_libdirs, svn_link_flags, extra_libs) = svn_build_data()


class SvnExtension(Extension):

    def __init__(self, name, *args, **kwargs):
        kwargs["include_dirs"] = ([apr_includedir, apu_includedir] +
                                  svn_includedirs + ["subvertpy"])
        kwargs["library_dirs"] = svn_libdirs
        # Note that the apr-util link flags are not included here, as
        # subvertpy only uses some apr util constants but does not use
        # the library directly.
        kwargs["extra_link_args"] = apr_link_flags + svn_link_flags
        if os.name == 'nt':
            # on windows, just ignore and overwrite the libraries!
            kwargs["libraries"] = extra_libs
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


def subvertpy_modules():
    return [
        SvnExtension(
            "subvertpy.client",
            [source_path(n)
                for n in ("client.c", "editor.c", "util.c", "_ra.c", "wc.c",
                          "wc_adm.c")],
            libraries=["svn_client-1", "svn_subr-1", "svn_ra-1", "svn_wc-1"]),
        SvnExtension(
            "subvertpy._ra",
            [source_path(n) for n in ("_ra.c", "util.c", "editor.c")],
            libraries=["svn_ra-1", "svn_delta-1", "svn_subr-1"]),
        SvnExtension(
            "subvertpy.repos", [source_path(n) for n in ("repos.c", "util.c")],
            libraries=["svn_repos-1", "svn_subr-1", "svn_fs-1"]),
        SvnExtension(
            "subvertpy.wc",
            [source_path(n) for n in
                ["wc.c", "wc_adm.c", "util.c", "editor.c"]],
            libraries=["svn_wc-1", "svn_subr-1"]),
        ]


subvertpy_version = (0, 11, 0)
subvertpy_version_string = ".".join(map(str, subvertpy_version))


if __name__ == "__main__":
    setup(name='subvertpy',
          description='Alternative Python bindings for Subversion',
          keywords='svn subvertpy subversion bindings',
          version=subvertpy_version_string,
          url='https://jelmer.uk/subvertpy',
          download_url="https://jelmer.uk/subvertpy/tarball/subvertpy-%s/" % (
              subvertpy_version_string, ),
          license='LGPLv2.1 or later',
          author='Jelmer Vernooij',
          author_email='jelmer@jelmer.uk',
          long_description="""
Alternative Python bindings for Subversion. The goal is to have
complete, portable and "Pythonic" Python bindings.

Bindings are provided for the working copy, client, delta, remote access and
repository APIs. A hookable server side implementation of the custom Subversion
protocol (svn_ra) is also provided.

Differences with similar packages
---------------------------------
subvertpy covers more of the APIs than python-svn. It provides a more
"Pythonic" API than python-subversion, which wraps the Subversion C API pretty
much directly. Neither provide a hookable server-side.

Dependencies
------------
Subvertpy depends on Python 3.5, and Subversion 1.4 or later. It should
work on Windows as well as most POSIX-based platforms (including Linux, BSDs
and Mac OS X).
""",
          packages=['subvertpy'],
          ext_modules=subvertpy_modules(),
          rust_extensions=[RustExtension("subvertpy.subr", "subr/Cargo.toml")],
          scripts=['bin/subvertpy-fast-export'],
          classifiers=[
              'Development Status :: 4 - Beta',
              'License :: OSI Approved :: GNU General Public '
              'License v2 or later (GPLv2+)',
              'Programming Language :: Python :: 2.7',
              'Programming Language :: Python :: 3.4',
              'Programming Language :: Python :: 3.5',
              'Programming Language :: Python :: 3.6',
              'Programming Language :: Python :: Implementation :: CPython',
              'Operating System :: POSIX',
              'Topic :: Software Development :: Version Control',
          ],
          )
