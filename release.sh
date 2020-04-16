#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

RELEASE_VERSION="${1}"
NEXT_VERSION="${2}-SNAPSHOT"

sed -E -i.releaseBackup "s/^__version__ = .*$/__version__ = '${RELEASE_VERSION}'/" generate.py

git add generate.py
git commit -m "Release ${RELEASE_VERSION}"
git tag -a "${RELEASE_VERSION}" -m "Release ${RELEASE_VERSION}"
git push --follow-tags

zip -r "1g1r-romset-generator-${RELEASE_VERSION}.zip" generate.py LICENSE README.md headers modules

sed -E -i.releaseBackup "s/^__version__ = .*$/__version__ = '${NEXT_VERSION}'/" generate.py

git add generate.py
git commit -m "Bump version to ${NEXT_VERSION}"
git push