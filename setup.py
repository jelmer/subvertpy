#!/usr/bin/env python2.4

from distutils.core import setup
from distutils.extension import Extension
from Pyrex.Distutils import build_ext
import os

def apr_include_dir():
    f = os.popen("apr-config --includedir")
    dir = f.read().rstrip("\n")
    assert os.path.isdir(dir)
    return dir

def svn_include_dir():
    # FIXME
    return "/usr/include/subversion-1"

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
      ext_modules=[Extension("ra", ["ra.pyx"], libraries=["svn_ra-1"],
                     include_dirs=[apr_include_dir(), svn_include_dir()])],
      ext_modules=[Extension("wc", ["wc.pyx"], libraries=["svn_wc-1"],
                     include_dirs=[apr_include_dir(), svn_include_dir()])],
      cmdclass = {'build_ext': build_ext},
      )
