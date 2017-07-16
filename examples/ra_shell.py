#!/usr/bin/python

import cmd
import subvertpy
from subvertpy.ra import RemoteAccess
import sys

if len(sys.argv) == 1:
    print("Usage: %s <url>" % sys.argv)

url = sys.argv[1]

conn = RemoteAccess(url)


def log_printer(changed_paths, rev, revprops, has_children=None):
    print("=" * 79)
    print("%d:" % rev)
    print("Revision properties:")
    for entry in revprops.items():
        print("  %s: %s" % entry)
    print("")

    if changed_paths is None:
        return
    print("Changed paths:")
    for path, (action, from_path, from_rev) in changed_paths.items():
        print("  %s (%s)" % (path, action))


class RaCmd(cmd.Cmd):

    @staticmethod
    def parse_path_revnum(line):
        args = line.split(" ")
        if len(args) == 0:
            return ".", -1
        elif len(args) == 1:
            return args[0], -1
        elif len(args) == 2:
            return args[0], int(args[1])
        else:
            raise Exception("Too much arguments (%r), expected 2" % (args,))

    def do_help(self, args):
        for name in sorted(self.__class__.__dict__):
            if name.startswith("do_"):
                print(name[3:])

    def do_stat(self, args):
        path, revnum = self.parse_path_revnum(args)
        print(conn.stat(path, revnum))

    def do_ls(self, args):
        path, revnum = self.parse_path_revnum(args)
        (dirents, fetched_rev, props) = conn.get_dir(path, revnum)
        for name in dirents:
            print(name)

    def do_cat(self, args):
        path, revnum = self.parse_path_revnum(args)
        outf = getattr(sys.stdout, 'buffer', sys.stdout)
        (fetched_rev, props) = conn.get_file(path, outf, revnum)

    def do_reparent(self, args):
        conn.reparent(args)

    def do_set_revprop(self, args):
        (revnum, name, value) = args.split(" ", 2)
        conn.change_rev_prop(int(revnum), name, value)

    def do_has_capability(self, args):
        print(conn.has_capability(args))

    def do_revprops(self, args):
        for item in conn.rev_proplist(int(args)).items():
            print("%s: %s" % item)

    def do_check_path(self, args):
        path, revnum = self.parse_path_revnum(args)
        kind = conn.check_path(path, revnum)
        if kind == subvertpy.NODE_DIR:
            print("dir")
        elif kind == subvertpy.NODE_FILE:
            print("file")
        else:
            print("nonexistant")

    def do_uuid(self, args):
        print(conn.get_uuid())

    def do_get_repos_root(self, args):
        print(conn.get_repos_root())

    def do_log(self, args):
        conn.get_log(callback=log_printer, paths=None, start=0,
                     end=conn.get_latest_revnum(), discover_changed_paths=True)


cmdline = RaCmd()
cmdline.cmdloop()
