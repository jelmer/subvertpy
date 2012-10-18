#!/usr/bin/python
# Demonstrates how to do a new commit using Subvertpy

import os
from subvertpy.six import BytesIO,b
from subvertpy import delta, repos
from subvertpy.ra import RemoteAccess, Auth, get_username_provider

# Create a repository
repos.create("tmprepo")

# Connect to the "remote" repository using the file transport. 
# Note that a username provider needs to be provided, so that Subversion
# knows who to record as the author of new commits made over this connection.
repo_url = "file://%s" % os.path.abspath("tmprepo")
conn = RemoteAccess(repo_url,
                    auth=Auth([get_username_provider()]))

# Simple commit that adds a directory
editor = conn.get_commit_editor({"svn:log": "Commit message"})
root = editor.open_root()
# Add a directory
dir = root.add_directory("somedir")
dir.close()
# Add and edit a file
file = root.add_file("somefile")
# Set the svn:executable attribute
file.change_prop("svn:executable", "*")
# Obtain a textdelta handler and send the new file contents
txdelta = file.apply_textdelta()
delta.send_stream(BytesIO(b("new file contents")), txdelta)
file.close()
root.close()
editor.close()

# Rename the directory
editor = conn.get_commit_editor({"svn:log": "Commit message"})
root = editor.open_root()
# Create a new directory copied from somedir:1
dir = root.add_directory("new dir name", "%s/somedir" % repo_url, 1)
dir.close()
# Remove the original directory
root.delete_entry("somedir")
root.close()
editor.close()
