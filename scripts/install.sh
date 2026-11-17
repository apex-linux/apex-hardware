#!/bin/bash
#
# Installs every component's files under <destdir>/usr, the acceptance
# checks as /usr/libexec/apex-hardware/accept with /usr/bin/apex-accept
# pointing at it, and requires.txt, the packages the image must carry for
# them. With a flavor, also installs flavors/<flavor>/*/usr. apex-image
# depends on this contract: nothing is written outside <destdir>/usr, and
# each usr/ tree is copied as it is.

set -euo pipefail

readonly ACCEPT="usr/libexec/apex-hardware/accept"
readonly COMMAND="usr/bin/apex-accept"
readonly REQUIRES="usr/share/apex-hardware/requires.txt"

usage() {
  echo "usage: install.sh <destdir> [flavor]" >&2
  exit 2
}

# Copies one component's usr/ tree under <destdir>/usr.
install_tree() {
  local tree="$1" destdir="$2" file
  while IFS= read -r -d '' file; do
    install -D -m 0644 "${tree}/${file}" "${destdir}/usr/${file}"
  done < <(cd "${tree}" && find . -type f -printf '%P\0')
}

# Prints the source's git version, or "unknown" outside a clone.
source_version() {
  git -C "$1" describe --always --dirty 2>/dev/null || echo unknown
}

# Packs src/ into one executable zip that runs with the image's python3,
# isolated from the user's environment and site packages.
install_accept() {
  local root="$1" destdir="$2" stage="$3"
  cp -R "${root}/src/apex_hw" "${stage}/apex_hw"
  source_version "${root}" >"${stage}/apex_hw/version.txt"
  install -d "${destdir}/${ACCEPT%/*}" "${destdir}/${COMMAND%/*}"
  python3 -I - "${stage}" "${destdir}/${ACCEPT}" <<'PY'
import sys
import zipapp

zipapp.create_archive(
    sys.argv[1],
    sys.argv[2],
    interpreter="/usr/bin/python3 -I",
    main="apex_hw.entrypoints.accept:run",
    filter=lambda path: "__pycache__" not in path.parts
    and "testkit" not in path.parts,
)
PY
  chmod 0755 "${destdir}/${ACCEPT}"
  ln -sfn "../libexec/apex-hardware/accept" "${destdir}/${COMMAND}"
}

main() {
  if [[ $# -lt 1 || $# -gt 2 || -z "$1" ]]; then
    usage
  fi
  local destdir="$1" flavor="${2:-}"
  local root
  root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [[ -n "${flavor}" && ! -d "${root}/flavors/${flavor}" ]]; then
    echo "install.sh: no flavor '${flavor}' in flavors/" >&2
    exit 2
  fi

  local tree
  for tree in "${root}"/components/*/usr; do
    [[ -d "${tree}" ]] && install_tree "${tree}" "${destdir}"
  done
  if [[ -n "${flavor}" ]]; then
    for tree in "${root}/flavors/${flavor}"/*/usr; do
      [[ -d "${tree}" ]] && install_tree "${tree}" "${destdir}"
    done
  fi
  STAGE="$(mktemp -d)"
  trap 'rm -rf "${STAGE}"' EXIT
  install_accept "${root}" "${destdir}" "${STAGE}"
  install -D -m 0644 "${root}/requires.txt" "${destdir}/${REQUIRES}"
}

main "$@"
