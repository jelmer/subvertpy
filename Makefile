PYTHON = python
PYDOCTOR = pydoctor
SETUP = $(PYTHON) setup.py
ifeq ($(shell $(PYTHON) -c "import sys; print sys.version_info >= (2, 7)"),True)
TESTRUNNER = unittest
else
TESTRUNNER = testtools.run
endif
RUNTEST = PYTHONPATH=.:$(PYTHONPATH) $(PYTHON) -m $(TESTRUNNER)

all: build build-inplace

build::
	$(SETUP) build

build-inplace::
	$(SETUP) build_ext --inplace

install::
	$(SETUP) install

check:: build-inplace
	$(RUNTEST) subvertpy.tests.test_suite

clean::
	$(SETUP) clean
	rm -f subvertpy/*.so subvertpy/*.o subvertpy/*.pyc

pydoctor:
	$(PYDOCTOR) --introspect-c-modules -c subvertpy.cfg --make-html
