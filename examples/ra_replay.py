#!/usr/bin/python
# Demonstrates how to use the replay function to fetch the
# changes made in a revision.

from subvertpy.ra import Auth, RemoteAccess, get_username_provider

conn = RemoteAccess("svn://svn.gnome.org/svn/gnome-specimen/trunk",
                    auth=Auth([get_username_provider()]))


class MyFileEditor:

    def change_prop(self, key, value):
        print(f"Change prop: {key} -> {value!r}")

    def apply_textdelta(self, base_checksum):
        # This should return a function that can receive delta windows
        def apply_window(x):
            pass
        return apply_window

    def close(self):
        pass


class MyDirEditor:

    def open_directory(self, *args):
        print("Open dir: {} (base revnum: {!r})".format(*args))
        return MyDirEditor()

    def add_directory(self, path, copyfrom_path=None, copyfrom_rev=-1):
        print(f"Add dir: {path} (from {copyfrom_path!r}:{copyfrom_rev!r})")
        return MyDirEditor()

    def open_file(self, *args):
        print("Open file: {} (base revnum: {!r})".format(*args))
        return MyFileEditor()

    def add_file(self, path, copyfrom_path=None, copyfrom_rev=-1):
        print(f"Add file: {path} (from {copyfrom_path!r}:{copyfrom_rev!r})")
        return MyFileEditor()

    def change_prop(self, key, value):
        print(f"Change prop {key} -> {value!r}")

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
