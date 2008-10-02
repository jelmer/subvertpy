PYTHON = python
SETUP = $(PYTHON) setup.py
TRIAL = trial

all: build

build::
	$(SETUP) build

install::
	$(SETUP) install

check::
	$(SETUP) build_ext --inplace
	PYTHONPATH=. $(TRIAL) subvertpy

clean::
	$(SETUP) clean
