.PHONY: setup init cards scrape meta buylist report full clean fukuoka-cl import-cl mappings translate

PYTHON = uv run python

# First-time setup: install dependencies and initialize database
setup: init

# Initialize (or reset) the database
init:
	$(PYTHON) cli.py init --reset

# Fetch rotation-legal card data from TCGdex
cards:
	$(PYTHON) cli.py cards

# Scrape JP City League results from LimitlessTCG
scrape:
	$(PYTHON) cli.py scrape

# Compute meta snapshot (tier list)
meta:
	$(PYTHON) cli.py meta

# Generate prioritized buy list
buylist:
	$(PYTHON) cli.py buylist

# Export markdown report + CSV buy list to ./reports/output/
report:
	$(PYTHON) cli.py report

# Scrape Fukuoka Champions League (Juniors, Seniors, Masters)
fukuoka-cl:
	$(PYTHON) cli.py champions 903701 903702 903703

# Import CL data from CSV files into SQLite
import-cl:
	$(PYTHON) cli.py import-cl

# Sync JP-to-EN card mappings from Limitless
mappings:
	$(PYTHON) cli.py mappings

# Translate JP card names in CL decklists
translate:
	$(PYTHON) cli.py translate

# Run the full pipeline end-to-end
full: init cards scrape meta report

# Remove database and report output
clean:
	rm -f data/scout.db
	rm -rf reports/output/
