#!/usr/bin/python
# Demonstrates how to do a new commit using Subvertpy

import os
from subvertpy import repos
from subvertpy.ra import RemoteAccess, Auth, get_username_provider

# Create a repository
repos.create("tmprepo")

conn = RemoteAccess("file://%s" % os.path.abspath("tmprepo"),
                    auth=Auth([get_username_provider()]))

editor = conn.get_commit_editor({"svn:log": "Commit message"})
root = editor.open_root()
dir = root.add_directory("some dir")
dir.close()
root.close()
editor.close()
