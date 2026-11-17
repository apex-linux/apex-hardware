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

# Runs the unit tests.
test:
    PYTHONPATH=src uv run --frozen python -m unittest discover -s tests -t . -p '*_test.py'

# Installs the components under <destdir>/usr, the contract apex-image uses.
install destdir:
    scripts/install.sh "{{destdir}}"
