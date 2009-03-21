#!/usr/bin/python

from subvertpy.ra import RemoteAccess

conn = RemoteAccess("svn://svn.gnome.org/svn/gnome-specimen/trunk")

def cb(changed_paths, rev, revprops, has_children=None):
    print "=" * 79
    print "%d:" % rev
    print "Revision properties:"
    for entry in revprops.items(): 
        print "  %s: %s" % entry
    print ""
    
    print "Changed paths"
    for path, (action, from_path, from_rev) in changed_paths.iteritems():
        print "  %s (%s)" % (path, action)

conn.get_log(callback=cb, paths=None, start=0, end=conn.get_latest_revnum(), 
             discover_changed_paths=True)
