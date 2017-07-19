PYTHON = python
FLAKE8 ?= flake8
PYDOCTOR = pydoctor
PYDOCTOR_OPTIONS ?=
SETUP = $(PYTHON) setup.py
TESTRUNNER = unittest
DEBUGGER ?=
RUNTEST = PYTHONPATH=.:$(PYTHONPATH) $(DEBUGGER) $(PYTHON) -m $(TESTRUNNER) -v

all: build build-inplace

build::
	$(SETUP) build

build-inplace::
	$(SETUP) build_ext --inplace

install::
	$(SETUP) install

check:: build-inplace
	$(RUNTEST) $(TEST_OPTIONS) subvertpy.tests.test_suite

gdb-check::
	$(MAKE) check DEBUGGER="gdb --args"

check-one::
	$(MAKE) check TEST_OPTIONS=-f

clean::
	$(SETUP) clean
	rm -f subvertpy/*.so subvertpy/*.o subvertpy/*.pyc

pydoctor:
	$(PYDOCTOR) $(PYDOCTOR_OPTIONS) --introspect-c-modules -c subvertpy.cfg --make-html

style:
	$(FLAKE8) --exclude=build,.git,build-pypy,.tox
