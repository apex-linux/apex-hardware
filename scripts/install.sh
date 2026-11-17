#!/bin/bash
#
# Installs every component's files under <destdir>/usr. apex-image depends on
# this contract: nothing is written outside <destdir>/usr, and the layout under
# components/<name>/usr is copied as it is.

set -euo pipefail

main() {
  if [[ $# -ne 1 || -z "$1" ]]; then
    echo "usage: install.sh <destdir>" >&2
    exit 2
  fi
  local destdir="$1"
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

  local tree file
  for tree in "${root}"/components/*/usr; do
    [[ -d "${tree}" ]] || continue
    while IFS= read -r -d '' file; do
      install -D -m 0644 "${tree}/${file}" "${destdir}/usr/${file}"
    done < <(cd "${tree}" && find . -type f -printf '%P\0')
  done
}

main "$@"
