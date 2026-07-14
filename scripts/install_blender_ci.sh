#!/usr/bin/env bash
set -euo pipefail

VERSION="4.2.15"
ARCHIVE="blender-${VERSION}-linux-x64.tar.xz"
SHA256="b9dcc1d06861529779e7faf8d82c9dd3563443dfb1eb14212424c8c40b77074e"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CACHE="${VIBE_BLENDER_CACHE:-${ROOT}/.runtime/blender}"
URL="https://download.blender.org/release/Blender4.2/${ARCHIVE}"
mkdir -p "${CACHE}"
if [[ ! -f "${CACHE}/${ARCHIVE}" ]]; then
  curl --fail --location --retry 3 --output "${CACHE}/${ARCHIVE}" "${URL}"
fi
echo "${SHA256}  ${CACHE}/${ARCHIVE}" | sha256sum --check --status
if [[ ! -x "${CACHE}/blender-${VERSION}-linux-x64/blender" ]]; then
  tar -xf "${CACHE}/${ARCHIVE}" -C "${CACHE}"
fi
"${CACHE}/blender-${VERSION}-linux-x64/blender" --version | head -1
printf '%s\n' "${CACHE}/blender-${VERSION}-linux-x64/blender"
