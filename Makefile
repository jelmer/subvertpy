PYTHON = python
PYDOCTOR = pydoctor
EPYDOC = epydoc
SETUP = $(PYTHON) setup.py
TRIAL = $(shell which trial)

all: build build-inplace

build::
	$(SETUP) build

build-inplace::
	$(SETUP) build_ext --inplace

install::
	$(SETUP) install

check::
	$(SETUP) build_ext --inplace
	PYTHONPATH=. $(PYTHON) $(TRIAL) subvertpy

clean::
	$(SETUP) clean
	rm -f subvertpy/*.so subvertpy/*.o subvertpy/*.pyc

pydoctor:
	$(PYDOCTOR) -c subvertpy.cfg --make-html

epydoc:
	$(EPYDOC) subvertpy
