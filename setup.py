#!/usr/bin/env python3
# Setup file for subvertpy
# Copyright (C) 2005-2010 Jelmer Vernooij <jelmer@jelmer.uk>

import sys

from setuptools import setup
from setuptools_rust import Binding, RustExtension


def package_data():
    if sys.platform == "win32":
        return {"subvertpy": ["subvertpy/*.dll"]}
    else:
        return {}


if __name__ == "__main__":
    setup(
        packages=["subvertpy"],
        package_data=package_data(),
        rust_extensions=[
            RustExtension("subvertpy.subr", "subr/Cargo.toml", binding=Binding.PyO3),
            RustExtension("subvertpy.repos", "repos/Cargo.toml", binding=Binding.PyO3),
            RustExtension("subvertpy._ra", "ra/Cargo.toml", binding=Binding.PyO3),
            RustExtension("subvertpy.client", "client/Cargo.toml", binding=Binding.PyO3),
            RustExtension("subvertpy.wc", "wc/Cargo.toml", binding=Binding.PyO3),
        ],
        scripts=["bin/subvertpy-fast-export"],
    )
