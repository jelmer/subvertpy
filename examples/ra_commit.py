#!/usr/bin/python
# Demonstrates how to do a new commit using Subvertpy

import os
from io import BytesIO

from subvertpy import delta, repos
from subvertpy.ra import Auth, RemoteAccess, get_username_provider

# Create a repository
repos.create("tmprepo")

# Connect to the "remote" repository using the file transport.
# Note that a username provider needs to be provided, so that Subversion
# knows who to record as the author of new commits made over this connection.
repo_url = "file://{}".format(os.path.abspath("tmprepo"))
conn = RemoteAccess(repo_url, auth=Auth([get_username_provider()]))

# Simple commit that adds a directory. The editors are context managers;
# leaving the block closes them, and an exception aborts the edit rather
# than committing it half-finished.
editor = conn.get_commit_editor({"svn:log": "Commit message"})
with editor:
    with editor.open_root() as root:
        # Add a directory
        with root.add_directory("somedir"):
            pass
        # Add and edit a file
        with root.add_file("somefile") as file:
            # Set the svn:executable attribute
            file.change_prop("svn:executable", "*")
            # Obtain a textdelta handler and send the new file contents
            txdelta = file.apply_textdelta()
            delta.send_stream(BytesIO(b"new file contents"), txdelta)

# Rename the directory
editor = conn.get_commit_editor({"svn:log": "Commit message"})
with editor:
    with editor.open_root() as root:
        # Create a new directory copied from somedir:1
        with root.add_directory("new dir name", f"{repo_url}/somedir", 1):
            pass
        # Remove the original directory
        root.delete_entry("somedir")
