#!/bin/bash
#
# Installs every component's files under <destdir>/usr, and the acceptance
# checks as /usr/libexec/apex-hardware/accept. apex-image depends on this
# contract: nothing is written outside <destdir>/usr, and the layout under
# components/<name>/usr is copied as it is.

set -euo pipefail

readonly ACCEPT="usr/libexec/apex-hardware/accept"

# Packs src/ into one executable zip that runs with the image's python3.
install_accept() {
  local root="$1" destdir="$2"
  install -d "${destdir}/${ACCEPT%/*}"
  python3 -I - "${root}/src" "${destdir}/${ACCEPT}" <<'PY'
import pathlib
import sys
import zipapp

zipapp.create_archive(
    sys.argv[1],
    sys.argv[2],
    interpreter="/usr/bin/python3",
    main="apex_hw.entrypoints.accept:run",
    filter=lambda path: "__pycache__" not in path.parts
    and "testkit" not in path.parts,
)
PY
  chmod 0755 "${destdir}/${ACCEPT}"
}

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
  install_accept "${root}" "${destdir}"
}

main "$@"
