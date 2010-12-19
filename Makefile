PYTHON = python
PYDOCTOR = pydoctor
SETUP = $(PYTHON) setup.py
TESTRUNNER = $(shell which nosetests)

all: build build-inplace

build::
	$(SETUP) build

build-inplace::
	$(SETUP) build_ext --inplace

install::
	$(SETUP) install

check:: build-inplace
	PYTHONPATH=. $(PYTHON) $(TESTRUNNER) subvertpy

coverage::
	PYTHONPATH=. $(PYTHON) $(TESTRUNNER) --cover-package=subvertpy --with-coverage --cover-erase --cover-inclusive subvertpy

clean::
	$(SETUP) clean
	rm -f subvertpy/*.so subvertpy/*.o subvertpy/*.pyc

pydoctor:
	$(PYDOCTOR) --introspect-c-modules -c subvertpy.cfg --make-html
