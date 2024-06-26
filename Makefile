PYTHON = python3
RUFF ?= ruff
PYDOCTOR = pydoctor
PYDOCTOR_OPTIONS ?=
SETUP = $(PYTHON) setup.py
TESTRUNNER = unittest
DEBUGGER ?=
RUNTEST = PYTHONPATH=.:$(PYTHONPATH) $(DEBUGGER) $(PYTHON) -m $(TESTRUNNER) -v

all: build build-inplace

build::
	$(SETUP) build

build-nodeprecated:
	$(MAKE) build CFLAGS+=-Wno-deprecated-declarations

build-inplace::
	$(SETUP) build_ext --inplace

install::
	$(SETUP) install

check:: build-inplace
	$(RUNTEST) $(TEST_OPTIONS) tests.test_suite

gdb-check::
	$(MAKE) check DEBUGGER="gdb --args"

valgrind-check:
	PYTHONMALLOC=malloc $(MAKE) check PYTHON=python DEBUGGER="valgrind --suppressions=/usr/lib/valgrind/python3.supp"

check-one::
	$(MAKE) check TEST_OPTIONS=-f

clean::
	$(SETUP) clean
	rm -f subvertpy/*.so subvertpy/*.o subvertpy/*.pyc

pydoctor:
	$(PYDOCTOR) $(PYDOCTOR_OPTIONS) --introspect-c-modules -c subvertpy.cfg --make-html

style:
	$(RUFF) check .
