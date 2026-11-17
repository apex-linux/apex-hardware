# Lists the available recipes.
default:
    @just --list

# Checks formatting and style: Markdown, shell, Python.
lint:
    npx --yes markdownlint-cli2@0.24.1 "**/*.md" "#node_modules" "#build" "#.venv"
    uv run --frozen shellcheck scripts/*.sh
    uv run --frozen shfmt -d -i 2 -ci -bn scripts
    uv run --frozen pyink --check src tests
    uv run --frozen isort --check-only src tests
    uv run --frozen pylint src tests
    uv run --frozen mypy src tests

# Runs the unit tests, also on Fedora 45's Python, which runs the installed
# checker.
test:
    PYTHONPATH=src uv run --frozen python -m unittest discover -s tests -t . -p '*_test.py'
    PYTHONPATH=src uv run --no-project --python 3.15 python -m unittest discover -s tests -t . -p '*_test.py'

# Runs the acceptance checks on this machine; pass row names to run a few.
accept *rows:
    @PYTHONPATH=src python3 -m apex_hw.entrypoints.accept \
        --firmware-list components/firmware/usr/share/apex-hardware/firmware.txt \
        {{rows}}

# Installs the components under <destdir>/usr, the contract apex-image uses.
# A flavor, such as nvidia, adds the files in flavors/<flavor>.
install destdir flavor="":
    scripts/install.sh "{{destdir}}" {{flavor}}
