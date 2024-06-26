Subvertpy
=========

Homepage: https://github.com/jelmer/subvertpy/

Python bindings for the Subversion version control system that are aimed to be
complete, fast and feel native to Python programmers.

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
Subvertpy depends on Python 3.8, and Subversion 1.14 or later. It should
work on Windows as well as most POSIX-based platforms (including Linux, BSDs
and Mac OS X).

See https://subversion.apache.org/ for instructions on installing Subversion.

Installation
------------
Standard distutils are used - use "setup.py build" to build and "setup.install"
to install. On most platforms, setup will find the Python and Subversion
development libraries by itself.

Development
-----------
If using GCC it might be useful to disable the deprecation warnings when
compiling to see if there are any more serious warnings:

make CFLAGS="-Wno-deprecated-declarations"
