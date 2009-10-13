#!/usr/bin/python
#
# subvertpy-fast-export.py
# ----------
#  Walk through each revision of a local Subversion repository and export it
#  in a stream that git-fast-import can consume.
#
# Author: Chris Lee <clee@kde.org>
# License: MIT <http://www.opensource.org/licenses/mit-license.php>
#
# Adapted for subvertpy by Jelmer Vernooij <jelmer@samba.org>

trunk_path = '/trunk/'
branches_path = '/branches/'
tags_path = '/tags/'

import sys, os.path
from optparse import OptionParser
from time import mktime, strptime

from subvertpy.repos import PATH_CHANGE_DELETE, Repository

ct_short = ['M', 'A', 'D', 'R', 'X']

def dump_file_blob(root, full_path):
    stream_length = root.file_length(full_path)
    stream = root.file_content(full_path)
    sys.stdout.write("data %s\n" % stream_length)
    sys.stdout.flush()
    sys.stdout.write(stream.read())
    stream.close()
    sys.stdout.write("\n")


class Matcher(object):

    branch = None

    def __init__(self, trunk_path):
        self.trunk_path = trunk_path

    def branchname(self):
        return self.branch

    def __str__(self):
        return super(Matcher, self).__str__() + ":" + self.trunk_path

    @staticmethod
    def getMatcher(trunk_path):
        if trunk_path.startswith("regex:"):
            return RegexStringMatcher(trunk_path)
        else:
            return StaticStringMatcher(trunk_path)


class StaticStringMatcher(Matcher):

    branch = "master"

    def matches(self, path):
        return path.startswith(trunk_path)

    def replace(self, path):
        return path.replace(self.trunk_path, '')


class RegexStringMatcher(Matcher):

    def __init__(self, trunk_path):
        super(RegexStringMatcher, self).__init__(trunk_path)
        import re
        self.matcher = re.compile(self.trunk_path[len("regex:"):])

    def matches(self, path):
        match = self.matcher.match(path)
        if match:
            self.branch = match.group(1)
            return True
        else:
            return False

    def replace(self, path):
        return self.matcher.sub("\g<2>", path)

MATCHER = None

def export_revision(rev, fs):
    sys.stderr.write("Exporting revision %s... " % rev)

    # Open a root object representing the youngest (HEAD) revision.
    root = fs.revision_root(rev)

    # And the list of what changed in this revision.
    changes = root.paths_changed()

    i = 1
    marks = {}
    file_changes = []

    for path, (node_id, change_type, text_changed, prop_changed) in changes.iteritems():
        if root.is_dir(path):
            continue
        if not MATCHER.matches(path):
            # We don't handle branches. Or tags. Yet.
            pass
        else:
            if change_type == PATH_CHANGE_DELETE:
                file_changes.append("D %s" % MATCHER.replace(path))
            else:
                marks[i] = MATCHER.replace(path)
                file_changes.append("M 644 :%s %s" % (i, marks[i]))
                sys.stdout.write("blob\nmark :%s\n" % i)
                dump_file_blob(root, path)
                i += 1

    # Get the commit author and message
    props = fs.revision_proplist(rev)

    # Do the recursive crawl.
    if props.has_key('svn:author'):
        author = "%s <%s@localhost>" % (props['svn:author'], props['svn:author'])
    else:
        author = 'nobody <nobody@localhost>'

    if len(file_changes) == 0:
        sys.stderr.write("skipping.\n")
        return

    svndate = props['svn:date'][0:-8]
    commit_time = mktime(strptime(svndate, '%Y-%m-%dT%H:%M:%S'))
    sys.stdout.write("commit refs/heads/%s\n" % MATCHER.branchname())
    sys.stdout.write("committer %s %s -0000\n" % (author, int(commit_time)))
    sys.stdout.write("data %s\n" % len(props['svn:log']))
    sys.stdout.write(props['svn:log'])
    sys.stdout.write("\n")
    sys.stdout.write('\n'.join(file_changes))
    sys.stdout.write("\n\n")
    sys.stderr.write("done!\n")


def crawl_revisions(repos_path, first_rev=1, final_rev=None):
    """Open the repository at REPOS_PATH, and recursively crawl all its
    revisions."""

    # Open the repository at REPOS_PATH, and get a reference to its
    # versioning filesystem.
    fs_obj = Repository(repos_path).fs()

    # Query the current youngest revision.
    if final_rev is None:
        final_rev = fs_obj.youngest_revision()
    for rev in xrange(first_rev, final_rev + 1):
        export_revision(rev, fs_obj)


if __name__ == '__main__':
    usage = '%prog [options] REPOS_PATH'
    parser = OptionParser()
    parser.set_usage(usage)
    parser.add_option('-f', '--final-rev', help='Final revision to import', 
                      dest='final_rev', metavar='FINAL_REV', type='int')
    parser.add_option('-t', '--trunk-path', help="Path in repo to /trunk, may be `regex:/cvs/(trunk)/proj1/(.*)`\nFirst group is used as branchname, second to match files",
                      dest='trunk_path', metavar='TRUNK_PATH')
    parser.add_option('-b', '--branches-path', help='Path in repo to /branches',
                      dest='branches_path', metavar='BRANCHES_PATH')
    parser.add_option('-T', '--tags-path', help='Path in repo to /tags',
                      dest='tags_path', metavar='TAGS_PATH')
    (options, args) = parser.parse_args()

    if options.trunk_path != None:
        trunk_path = options.trunk_path
    if options.branches_path != None:
        branches_path = options.branches_path
    if options.tags_path != None:
        tags_path = options.tags_path

    MATCHER = Matcher.getMatcher(trunk_path)
    sys.stderr.write("%s\n" % MATCHER)
    if len(args) != 1:
        parser.print_help()
        sys.exit(2)

    # Canonicalize (enough for Subversion, at least) the repository path.
    repos_path = os.path.normpath(args[0])
    if repos_path == '.': 
        repos_path = ''

    try:
        import msvcrt
        msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
    except ImportError:
        pass

    crawl_revisions(repos_path, final_rev=options.final_rev)
