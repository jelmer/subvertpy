cdef extern from "svn_version.h":
	ctypedef struct svn_version_t:
		int major
		int minor
		int patch
		char *tag

cdef extern from "svn_ra.h":
	svn_version_t *svn_ra_version()

def version():
	"""Get libsvn_ra version information.

	:return: tuple with major, minor, patch version number and tag.
	"""
	return (svn_ra_version().major, svn_ra_version().minor, 
			svn_ra_version().minor, svn_ra_version().tag)
