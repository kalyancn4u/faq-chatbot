# ============================================================================
#  Semantic FAQ Chatbot -- developer task runner
# ----------------------------------------------------------------------------
#  Quickstart:
#      make setup        # create .venv and install deps (prod + dev)
#      make data         # initialize the SQLite DB (+sample FAQs) and build the index
#      make run          # launch the Streamlit app
#      make test         # run the test suite
#      make help         # list every target
#
#  SHELL NOTE (Windows): recipes are POSIX shell. On Windows run this from
#  **Git Bash** (or WSL) -- NOT PowerShell/cmd, where GnuWin32 make falls back
#  to cmd.exe and these recipes will not run. On macOS/Linux/CI it just works.
#
#  PYTHON NOTE (Windows): the `python` on PATH is a Microsoft Store stub, so the
#  base interpreter used to *create* the venv defaults to the local Miniconda.
#  Override if yours lives elsewhere:  make setup BASE_PYTHON=/c/Python312/python.exe
# ============================================================================

# ---- Configuration (override on the command line, e.g. `make run PORT=8600`) ----
# NOTE: values must not carry trailing spaces, so comments sit on their own lines
# (Make would fold any space between the value and a trailing `#` into the value).
VENV := .venv
# sidestep the base pip's dead extra-index-url (pypi.ngc.nvidia.com)
PIP_INDEX ?= https://pypi.org/simple
# port for `make serve-slides`
PORT ?= 8000
# source CSV for `make import`
CSV ?= data/sample/faqs.csv
# folder of NN-*.md chapters to build into slides
SLIDES_SRC ?= docs/walkthrough
SLIDES_OUT := $(SLIDES_SRC)/slides

# ---- OS detection: venv layout + base interpreter differ on Windows ----
ifeq ($(OS),Windows_NT)
  VENV_PY := $(VENV)/Scripts/python.exe
  # PATH `python` is a Microsoft Store stub here; use the real Miniconda interpreter
  BASE_PYTHON ?= D:/tools/miniconda3/python.exe
else
  VENV_PY := $(VENV)/bin/python
  BASE_PYTHON ?= python3
endif

PIP := $(VENV_PY) -m pip

.DEFAULT_GOAL := help

# ============================  Help  ========================================
.PHONY: help
help:  ## Show this help
	@echo "Semantic FAQ Chatbot -- make targets:"
	@echo ""
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
	  | sort \
	  | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Interpreter: $(VENV_PY)   (base for venv: $(BASE_PYTHON))"

# ========================  Environment / deps  ==============================
$(VENV_PY):
	@echo ">> creating virtualenv in $(VENV) using $(BASE_PYTHON)"
	"$(BASE_PYTHON)" -m venv $(VENV)
	$(PIP) install --index-url $(PIP_INDEX) --upgrade pip

.PHONY: venv
venv: $(VENV_PY)  ## Create the virtualenv (only if missing)

.PHONY: install
install: venv  ## Install runtime dependencies
	$(PIP) install --index-url $(PIP_INDEX) -r requirements.txt

.PHONY: install-dev
install-dev: venv  ## Install dev/test dependencies
	$(PIP) install --index-url $(PIP_INDEX) -r requirements-dev.txt

.PHONY: setup
setup: install install-dev  ## Full setup: venv + runtime + dev deps

# ============================  Data / index  ================================
.PHONY: init-db
init-db: venv  ## Initialize the SQLite schema and import the sample FAQs
	$(VENV_PY) scripts/initialize_database.py --with-sample

.PHONY: import
import: venv  ## Import FAQs from a CSV (override CSV=path/to/faqs.csv)
	$(VENV_PY) scripts/import_faqs.py $(CSV)

.PHONY: index
index: venv  ## (Re)build the FAISS index from active FAQs
	$(VENV_PY) scripts/rebuild_index.py

.PHONY: index-status
index-status: venv  ## Show index / DB consistency status (no rebuild)
	$(VENV_PY) scripts/rebuild_index.py --status

.PHONY: data
data: init-db index  ## First-run data: initialize the DB (+sample) then build the index

# ============================  Run / test  ==================================
.PHONY: run
run: venv  ## Launch the Streamlit app (needs `make data` first)
	$(VENV_PY) -m streamlit run app/main.py

.PHONY: test
test: venv  ## Run the test suite (quiet)
	$(VENV_PY) -m pytest -q

.PHONY: test-v
test-v: venv  ## Run the test suite (verbose)
	$(VENV_PY) -m pytest -v

.PHONY: compile
compile: venv  ## Byte-compile app/ and scripts/ as a fast syntax check
	$(VENV_PY) -m compileall -q app scripts

# ==============================  Slides  ====================================
# build_slides.sh prefers a globally-installed `marp`; otherwise it fetches the
# Marp CLI on demand via npx. Both need Node.js. Decks land in $(SLIDES_OUT).
.PHONY: slides
slides:  ## Build the HTML slide decks (into <SLIDES_SRC>/slides/)
	@command -v marp >/dev/null 2>&1 \
	  && SRC_DIR=$(SLIDES_SRC) MARP_CMD=marp bash scripts/build_slides.sh \
	  || SRC_DIR=$(SLIDES_SRC) bash scripts/build_slides.sh

.PHONY: slides-pdf
slides-pdf:  ## Build the slide decks as PDFs (needs Chromium/Chrome)
	@command -v marp >/dev/null 2>&1 \
	  && SRC_DIR=$(SLIDES_SRC) MARP_CMD=marp bash scripts/build_slides.sh --pdf \
	  || SRC_DIR=$(SLIDES_SRC) bash scripts/build_slides.sh --pdf

.PHONY: serve-slides
serve-slides: slides  ## Build then serve the decks locally (Ctrl-C to stop; override PORT=)
	@echo ">> serving $(SLIDES_OUT) at http://localhost:$(PORT)/  (Ctrl-C to stop)"
	$(VENV_PY) -m http.server $(PORT) --directory $(SLIDES_OUT)

# ==============================  Cleanup  ===================================
.PHONY: clean
clean:  ## Remove caches, built slides, and slide-build temp files
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .ruff_cache
	@rm -rf $(SLIDES_SRC)/slides
	@rm -f $(SLIDES_SRC)/_build_*.md
	@echo ">> cleaned caches + built slides"

.PHONY: clean-data
clean-data:  ## Remove the generated SQLite DB and FAISS index (derived artifacts)
	@rm -f data/database/*.db data/database/*.sqlite3
	@rm -f data/indexes/*.faiss data/indexes/*.pkl data/indexes/*.json
	@echo ">> removed generated DB + index (re-create with: make data)"

.PHONY: distclean
distclean: clean  ## clean + remove the virtualenv
	@rm -rf $(VENV)
	@echo ">> removed $(VENV)"
