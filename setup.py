#!/usr/bin/env python2.4
# Setup file for bzr-svn
# Copyright (C) 2005-2008 Jelmer Vernooij <jelmer@samba.org>

from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext
import os

def apr_include_dir():
    """Determine the APR header file location."""
    f = os.popen("apr-config --includedir")
    dir = f.read().rstrip("\n")
    if not os.path.isdir(dir):
        raise Exception("APR development headers not found")
    return dir

def svn_include_dir():
    """Determine the Subversion header file location."""
    dirs = ["/usr/local/include/subversion-1", "/usr/include/subversion-1"]
    for dir in dirs:
        if os.path.isdir(dir):
            return dir
    raise Exception("Subversion development headers not found")

setup(name='bzr-svn',
      description='Support for Subversion branches in Bazaar',
      keywords='plugin bzr svn',
      version='0.4.9',
      url='http://bazaar-vcs.org/BzrForeignBranches/Subversion',
      download_url='http://bazaar-vcs.org/BzrSvn',
      license='GPL',
      author='Jelmer Vernooij',
      author_email='jelmer@samba.org',
      long_description="""
      This plugin adds support for branching off and 
      committing to Subversion repositories from 
      Bazaar.
      """,
      package_dir={'bzrlib.plugins.svn':'.', 
                   'bzrlib.plugins.svn.tests':'tests'},
      packages=['bzrlib.plugins.svn', 
                'bzrlib.plugins.svn.tests'],
      ext_modules=[
          Extension("core", ["core.pyx"], libraries=["svn_subr-1"], 
                    include_dirs=[apr_include_dir(), svn_include_dir()]), 
          Extension("client", ["client.pyx"], libraries=["svn_client-1"], 
                    include_dirs=[apr_include_dir(), svn_include_dir()]), 
          Extension("ra", ["ra.pyx"], libraries=["svn_ra-1"], 
                    include_dirs=[apr_include_dir(), svn_include_dir()]), 
          Extension("repos", ["repos.pyx"], libraries=["svn_repos-1"], 
                    include_dirs=[apr_include_dir(), svn_include_dir()]), 
          Extension("wc", ["wc.pyx"], libraries=["svn_wc-1"],
                     include_dirs=[apr_include_dir(), svn_include_dir()])],
      cmdclass = {'build_ext': build_ext},
      )
