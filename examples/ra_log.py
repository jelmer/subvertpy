#!/usr/bin/python
# Demonstrates how to iterate over the log of a Subversion repository.

from subvertpy.six import iterkeys,itervalues,iteritems
from subvertpy.ra import RemoteAccess

conn = RemoteAccess("svn://svn.samba.org/subvertpy/trunk")

for (changed_paths, rev, revprops, has_children) in conn.iter_log(paths=None,
        start=0, end=conn.get_latest_revnum(), discover_changed_paths=True):
    print "=" * 79
    print "%d:" % rev
    print "Revision properties:"
    for entry in iteritems(revprops): 
        print "  %s: %s" % entry
    print ""

    print "Changed paths"
    for path, (action, from_path, from_rev) in iteritems(changed_paths):
        print "  %s (%s)" % (path, action)

