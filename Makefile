.PHONY: setup init cards scrape meta buylist report full clean

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

# Run the full pipeline end-to-end
full: init cards scrape meta report

# Remove database and report output
clean:
	rm -f data/scout.db
	rm -rf reports/output/
