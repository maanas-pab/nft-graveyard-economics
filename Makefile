# GraveNFT Yard — build entrypoints
#
#   make all      run the full pipeline (metrics + plates + charts + gif + site data)
#   make data     recompute derived metrics from the manual CSVs -> build/metrics.csv
#   make flowers  render the botanical specimen plates -> assets/plates/
#   make charts   render the economics charts -> assets/charts/
#   make gif      render the wilting-garden animation -> assets/garden-anim.gif
#   make site     export the JSON payload the website reads -> site/data/garden.js
#   make test     run the data-integrity tests
#   make check    tests + verify site/data/garden.js is byte-reproducible
#   make serve    preview the garden at http://localhost:8931/#play
#   make clean    remove build artifacts (assets/ and site/data/ stay in git)

PYTHON ?= python3

.PHONY: all data flowers charts gif site test check serve clean

all: data flowers charts gif site

data:
	$(PYTHON) -m src.pipeline

flowers:
	$(PYTHON) -m src.plates

charts:
	$(PYTHON) -m src.charts

gif:
	$(PYTHON) -m src.garden_gif

site:
	$(PYTHON) -m src.pipeline --web

test:
	$(PYTHON) -m pytest -q

check: test
	$(PYTHON) -m src.pipeline --web
	@git diff --quiet -- site/data/garden.js \
		|| { echo "site/data/garden.js differs from a fresh build"; exit 1; }
	@echo "payload reproducible"

serve:
	$(PYTHON) -m http.server 8931 --directory site

clean:
	rm -rf build/*
