PYTHON ?= python3

.PHONY: run demo test compile install user-install uninstall screenshots clean

run:
	$(PYTHON) -m madlions_control

demo:
	$(PYTHON) -m madlions_control --demo

test:
	$(PYTHON) -m unittest discover -s tests -v

compile:
	$(PYTHON) -m compileall -q madlions_control

install:
	PREFIX=/usr ./install.sh

user-install:
	./install.sh --user

uninstall:
	./uninstall.sh

screenshots:
	./tools/screenshots.sh

clean:
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +
	rm -rf build dist *.egg-info AppDir flatpak-build flatpak-repo
