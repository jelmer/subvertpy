#!/usr/bin/python
# Demonstrates how to use the replay function to fetch the
# changes made in a revision.

from subvertpy.ra import RemoteAccess, Auth, get_username_provider

conn = RemoteAccess("svn://svn.gnome.org/svn/gnome-specimen/trunk",
                    auth=Auth([get_username_provider()]))


class MyFileEditor:

    def change_prop(self, key, value):
        print("Change prop: %s -> %r" % (key, value))

    def apply_textdelta(self, base_checksum):
        # This should return a function that can receive delta windows
        def apply_window(x):
            pass
        return apply_window

    def close(self):
        pass


class MyDirEditor:

    def open_directory(self, *args):
        print("Open dir: %s (base revnum: %r)" % args)
        return MyDirEditor()

    def add_directory(self, path, copyfrom_path=None, copyfrom_rev=-1):
        print("Add dir: %s (from %r:%r)" % (path, copyfrom_path, copyfrom_rev))
        return MyDirEditor()

    def open_file(self, *args):
        print("Open file: %s (base revnum: %r)" % args)
        return MyFileEditor()

    def add_file(self, path, copyfrom_path=None, copyfrom_rev=-1):
        print("Add file: %s (from %r:%r)" %
              (path, copyfrom_path, copyfrom_rev))
        return MyFileEditor()

    def change_prop(self, key, value):
        print("Change prop %s -> %r" % (key, value))

    def delete_entry(self, path, revision):
        print("Delete: %s" % path)

    def close(self):
        pass


class MyEditor:

    def set_target_revision(self, revnum):
        print("Target revision: %d" % revnum)

    def abort(self):
        print("Aborted")

    def close(self):
        print("Closed")

    def open_root(self, base_revnum):
        print("/")
        return MyDirEditor()


editor = MyEditor()
conn.replay(230, 1, editor)
