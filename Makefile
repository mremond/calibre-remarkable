CALIBRE_PATH := /Applications/calibre.app/Contents/MacOS
PLUGIN_NAME := remarkable_sync
VERSION := $(shell grep "^    version = " __init__.py | grep -o "([0-9], [0-9], [0-9])" | tr -d '() ' | tr ',' '.')

.PHONY: install run dev clean dist

install:
	$(CALIBRE_PATH)/calibre-customize -b .

run:
	$(CALIBRE_PATH)/calibre-debug -g

dev: install run

dist: clean
	@echo "Building $(PLUGIN_NAME)-$(VERSION).zip"
	zip -r $(PLUGIN_NAME)-$(VERSION).zip \
		__init__.py \
		ui.py \
		main.py \
		worker.py \
		remarkable.py \
		config.py \
		plugin-import-name-remarkable_sync.txt \
		images/
	@echo "Created $(PLUGIN_NAME)-$(VERSION).zip"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -f $(PLUGIN_NAME)-*.zip 2>/dev/null || true
