#!/usr/bin/env bash
# Download openframe's API contract at a release tag into tests/contract/.
#
#   tools/update-contract.sh v0.5.0
#
# Writes tests/contract/openapi.yaml, tests/contract/presentation-cases.json (the test cases of
# openframe's presentation formula, for the card's crop editor) and tests/contract/OPENFRAME_VERSION.
# CI runs it with the pinned tag and fails if the copy differs; Renovate's branches run it with the
# new tag.
set -euo pipefail

if [ $# -ne 1 ] || ! [[ $1 =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "usage: $0 vX.Y.Z" >&2
  exit 2
fi
tag=$1
dir=$(cd "$(dirname "$0")/.." && pwd)/tests/contract
base=https://raw.githubusercontent.com/tycho991/openframe/$tag

tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT
for file in openapi.yaml fixtures/presentation-cases.json; do
  curl --fail --silent --show-error --location --retry 3 "$base/api/$file" -o "$tmp"
  mv "$tmp" "$dir/$(basename "$file")"
done
echo "$tag" > "$dir/OPENFRAME_VERSION"
