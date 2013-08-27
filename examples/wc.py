#!/usr/bin/python
# Demonstrates how to do access the working tree using subvertpy

import os
from subvertpy import client, repos, wc
from subvertpy.ra import Auth, get_username_provider

# Create a repository
repos.create("tmprepo")

c = client.Client(auth=Auth([get_username_provider()]))
c.checkout("file://" + os.getcwd() + "/tmprepo", "tmpco", "HEAD")

w = wc.WorkingCopy(None, "tmpco")
print(w)
entry = w.entry("tmpco")
print(entry.revision)
print(entry.url)
