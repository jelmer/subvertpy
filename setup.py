#!/usr/bin/env python3
# Setup file for subvertpy
# Copyright (C) 2005-2010 Jelmer Vernooij <jelmer@samba.org>

from distutils.core import setup, Command
from distutils.extension import Extension
from distutils.command.build import build
from distutils import log
import sys
import os
import re

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
    cmds = [command] + [os.path.join(p, command) for p in ["/usr/local/apr/bin/", "/opt/local/bin/"]]
    for cmd in cmds:
        try:
            return run_cmd(cmd, arg)
        except CommandException:
            _, e, _ = sys.exc_info()
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
        return ([os.getenv("SVN_HEADER_PATH")], [os.getenv("SVN_LIBRARY_PATH")], [], [])
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
                    "Please set SVN_PREFIX or (SVN_LIBRARY_PATH and SVN_HEADER_PATH) environment variable. ")

def is_keychain_provider_available():
    """
    Checks for the availability of the Keychain simple authentication provider in Subversion by compiling a simple test program.
    """
    abd = apr_build_data()
    sbd = svn_build_data()
    gcc_command_args = ['gcc'] + ['-I' + inc for inc in sbd[0]] + ['-L' + lib for lib in sbd[1]] + ['-I' + abd[0], '-lsvn_subr-1', '-x', 'c', '-']
    (gcc_in, gcc_out, gcc_err) = os.popen3(gcc_command_args)
    gcc_in.write("""
#include <svn_auth.h>
int main(int argc, const char* arv[]) {
    svn_auth_get_keychain_simple_provider(NULL, NULL);
}
""")
    gcc_in.close()
    gcc_out.read()
    return (gcc_out.close() is None)


class VersionQuery(object):

    def __init__(self, filename):
        self.filename = filename
        f = open(filename, "rU")
        try:
            self.text = f.read()
        finally:
            f.close()

    def grep(self, what):
        m = re.search(r"^#define\s+%s\s+(\d+)\s*$" % (what,), self.text, re.MULTILINE)
        if not m:
            raise Exception("Definition for %s was not found in file %s." % (what, self.filename))
        return int(m.group(1))

# Windows versions - we use environment variables to locate the directories
# and hard-code a list of libraries.
if os.name == "nt":
    def get_apr_version():
        apr_version_file = os.path.join(os.environ["SVN_DEV"],
                r"include\apr\apr_version.h")
        if not os.path.isfile(apr_version_file):
            raise Exception(
                "Please check that your SVN_DEV location is correct.\n"
                "Unable to find required apr\\apr_version.h file.")
        query = VersionQuery(apr_version_file)
        return (query.grep("APR_MAJOR_VERSION"),
                query.grep("APR_MINOR_VERSION"),
                query.grep("APR_PATCH_VERSION"))

    def get_svn_version():
        svn_version_file = os.path.join(os.environ["SVN_DEV"], r"include\svn_version.h")
        if not os.path.isfile(svn_version_file):
            raise Exception(
                "Please check that your SVN_DEV location is correct.\n"
                "Unable to find required svn_version.h file.")
        query = VersionQuery(svn_version_file)
        return (query.grep("SVN_VER_MAJOR"),
                query.grep("SVN_VER_MINOR"),
                query.grep("SVN_VER_PATCH"))

    # just clobber the functions above we can't use
    # for simplicitly, everything is done in the 'svn' one
    def apr_build_data():
        return '.', []

    def apu_build_data():
        return '.', []

    def svn_build_data():
        # environment vars for the directories we need.
        svn_dev_dir = os.environ.get("SVN_DEV")
        if not svn_dev_dir or not os.path.isdir(svn_dev_dir):
            raise Exception(
                "Please set SVN_DEV to the location of the svn development "
                "packages.\nThese can be downloaded from:\n"
                "http://sourceforge.net/projects/win32svn/files/")
        svn_bdb_dir = os.environ.get("SVN_BDB")
        if not svn_bdb_dir or not os.path.isdir(svn_bdb_dir):
            raise Exception(
                "Please set SVN_BDB to the location of the svn BDB packages "
                "- see README.txt in the SVN_DEV dir")
        svn_libintl_dir = os.environ.get("SVN_LIBINTL")
        if not svn_libintl_dir or not os.path.isdir(svn_libintl_dir):
            raise Exception(
                "Please set SVN_LIBINTL to the location of the svn libintl "
                "packages - see README.txt in the SVN_DEV dir")

        svn_version = get_svn_version()
        apr_version = get_apr_version()

        includes = [
            # apr dirs.
            os.path.join(svn_dev_dir, r"include\apr"),
            os.path.join(svn_dev_dir, r"include\apr-util"),
            os.path.join(svn_dev_dir, r"include\apr-iconv"),
            # svn dirs.
            os.path.join(svn_dev_dir, "include"),
        ]
        lib_dirs = [
            os.path.join(svn_dev_dir, "lib"),
            os.path.join(svn_dev_dir, "lib", "apr"),
            os.path.join(svn_dev_dir, "lib", "apr-iconv"),
            os.path.join(svn_dev_dir, "lib", "apr-util"),
            os.path.join(svn_dev_dir, "lib", "neon"),
            os.path.join(svn_bdb_dir, "lib"),
            os.path.join(svn_libintl_dir, "lib"),
        ]
        aprlibs = """libapr libapriconv libaprutil""".split()
        if apr_version[0] == 1:
            aprlibs = [aprlib + "-1" for aprlib in aprlibs]
        elif apr_version[0] > 1:
            raise Exception(
                "You have apr version %d.%d.%d.\n"
                "This setup only knows how to build with 0.*.* or 1.*.*." % apr_version)
        libs = """libneon libsvn_subr-1 libsvn_client-1 libsvn_ra-1
                  libsvn_ra_dav-1 libsvn_ra_local-1 libsvn_ra_svn-1
                  libsvn_repos-1 libsvn_wc-1 libsvn_delta-1 libsvn_diff-1
                  libsvn_fs-1 libsvn_repos-1 libsvn_fs_fs-1 libsvn_fs_base-1
                  intl3_svn
                  xml
                  advapi32 shell32 ws2_32 zlibstat
               """.split()
        if svn_version >= (1,7,0):
            libs += ["libdb48"]
        else:
            libs += ["libdb44"]
        if svn_version >= (1,5,0):
            # Since 1.5.0 libsvn_ra_dav-1 was removed
            libs.remove("libsvn_ra_dav-1")

        return includes, lib_dirs, [], aprlibs+libs,

(apr_includedir, apr_link_flags) = apr_build_data()
(apu_includedir, apu_link_flags) = apu_build_data()
(svn_includedirs, svn_libdirs, svn_link_flags, extra_libs) = svn_build_data()

class SvnExtension(Extension):

    def __init__(self, name, *args, **kwargs):
        kwargs["include_dirs"] = ([apr_includedir, apu_includedir] + svn_includedirs +
                                  ["subvertpy"])
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


class TestCommand(Command):
    """Command for running unittests without install."""

    user_options = [("args=", None, '''The command args string passed to
                                    unittest framework, such as 
                                     --args="-v -f"''')]

    def initialize_options(self):
        self.args = ''
        pass

    def finalize_options(self):
        pass

    def run(self):
        self.run_command('build')
        bld = self.distribution.get_command_obj('build')
        #Add build_lib in to sys.path so that unittest can found DLLs and libs
        sys.path = [os.path.abspath(bld.build_lib)] + sys.path
        os.chdir(bld.build_lib)
        log.info("Running unittest without install.")

        import shlex
        import unittest
        test_argv0 = [sys.argv[0] + ' test --args=']
        #For transfering args to unittest, we have to split args
        #by ourself, so that command like:
        #python setup.py test --args="-v -f"
        #can be executed, and the parameter '-v -f' can be
        #transfering to unittest properly.
        test_argv = test_argv0 + shlex.split(self.args)
        unittest.main(module=None, defaultTest='subvertpy.tests.test_suite', argv=test_argv)


class BuildWithDLLs(build):
    def _get_dlls(self):
        # return a list of of (FQ-in-name, relative-out-name) tuples.
        ret = []
        # the apr binaries.
        apr_bins = [libname + ".dll" for libname in extra_libs
                    if libname.startswith("libapr")]
        if get_svn_version() >= (1,5,0):
            # Since 1.5.0 these libraries became shared
            apr_bins += """libsvn_client-1.dll libsvn_delta-1.dll libsvn_diff-1.dll
                           libsvn_fs-1.dll libsvn_ra-1.dll libsvn_repos-1.dll
                           libsvn_subr-1.dll libsvn_wc-1.dll libsasl.dll""".split()
        if get_svn_version() >= (1,7,0):
            apr_bins += ["libdb48.dll"]
        else:
            apr_bins += ["libdb44.dll"]
        apr_bins += """intl3_svn.dll libeay32.dll ssleay32.dll""".split()
        look_dirs = os.environ.get("PATH","").split(os.pathsep)
        look_dirs.insert(0, os.path.join(os.environ["SVN_DEV"], "bin"))

        target = os.path.abspath(os.path.join(self.build_lib, 'subvertpy'))
        for bin in apr_bins:
            for look in look_dirs:
                f = os.path.join(look, bin)
                if os.path.isfile(f):
                    ret.append((f, target))
                    break
            else:
                log.warn("Could not find required DLL %r to include", bin)
                log.debug("(looked in %s)", look_dirs)
        return ret

    def run(self):
        build.run(self)
        # the apr binaries.
        # On Windows we package up the apr dlls with the plugin.
        for s, d in self._get_dlls():
            self.copy_file(s, d)

    def get_outputs(self):
        ret = build.get_outputs(self)
        ret.extend(info[1] for info in self._get_dlls())
        return ret

cmdclass = {'test': TestCommand}
if os.name == 'nt':
    # BuildWithDLLs can copy external DLLs into build directory On Win32.
    # So we can running unittest directly from build directory.
    cmdclass['build'] = BuildWithDLLs

def source_path(filename):
    return os.path.join("subvertpy", filename)


def subvertpy_modules():
    return [
        SvnExtension("subvertpy.client", [source_path(n) for n in
            ("client.c", "editor.c", "util.c", "_ra.c", "wc.c")],
            libraries=["svn_client-1", "svn_subr-1", "svn_ra-1", "svn_wc-1"]),
        SvnExtension("subvertpy._ra", [source_path(n) for n in
            ("_ra.c", "util.c", "editor.c")],
            libraries=["svn_ra-1", "svn_delta-1", "svn_subr-1"]),
        SvnExtension("subvertpy.repos", [source_path(n) for n in ("repos.c", "util.c")],
            libraries=["svn_repos-1", "svn_subr-1", "svn_fs-1"]),
        SvnExtension("subvertpy.wc", [source_path(n) for n in ("wc.c",
            "util.c", "editor.c")], libraries=["svn_wc-1", "svn_subr-1"])
        ]


subvertpy_version = (0, 9, 2)
subvertpy_version_string = ".".join(map(str, subvertpy_version))


if __name__ == "__main__":
    setup(name='subvertpy',
          description='Alternative Python bindings for Subversion',
          keywords='svn subvertpy subversion bindings',
          version=subvertpy_version_string,
          url='http://samba.org/~jelmer/subvertpy',
          download_url="http://samba.org/~jelmer/subvertpy/subvertpy-%s.tar.gz" % (
              subvertpy_version_string, ),
          license='LGPLv2.1 or later',
          author='Jelmer Vernooij',
          author_email='jelmer@samba.org',
          long_description="""
          Alternative Python bindings for Subversion. The goal is to have complete, portable and "Pythonic" Python bindings.
          """,
          packages=['subvertpy', 'subvertpy.tests'],
          ext_modules=subvertpy_modules(),
          scripts=['bin/subvertpy-fast-export'],
          cmdclass=cmdclass,
          )
