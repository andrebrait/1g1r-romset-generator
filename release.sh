#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

RELEASE_VERSION="${1}"
NEXT_VERSION="${2}-SNAPSHOT"
ZIP_FILENAME="1g1r-romset-generator-${RELEASE_VERSION}.zip"

echo "Changing version to ${RELEASE_VERSION}"
sed -E -i.releaseBackup "s/^__version__ = .*$/__version__ = \"${RELEASE_VERSION}\"/" modules/cli.py

echo "Committing changes"
git add modules/cli.py
git commit -m "Release ${RELEASE_VERSION}"

echo "Generating tag ${RELEASE_VERSION}"
git tag -a "${RELEASE_VERSION}" -m "Release ${RELEASE_VERSION}"

echo "Pushing changes"
git push --follow-tags

echo "Generating compressed archive ${ZIP_FILENAME}"
[ -f "${ZIP_FILENAME}" ] && rm "${ZIP_FILENAME}" 2>/dev/null
zip -r "${ZIP_FILENAME}" generate.py LICENSE README.md headers modules -x "*__pycache__*"

echo "Changing version to ${NEXT_VERSION}"
sed -E -i "s/^__version__ = .*$/__version__ = \"${NEXT_VERSION}\"/" modules/cli.py

echo "Committing changes"
git add modules/cli.py
git commit -m "Bump version to ${NEXT_VERSION}"
git push