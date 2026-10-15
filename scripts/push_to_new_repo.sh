#!/usr/bin/env bash
# Move the scholarship-navigator/ folder into its own GitHub repository (run from the WeatherGPT1 checkout root).
#   1. Create an EMPTY repo on GitHub named scholarship-navigator (no README/.gitignore):
#      https://github.com/new
#   2. bash scholarship-navigator/scripts/push_to_new_repo.sh <github-user-or-org>
set -euo pipefail
OWNER="${1:?usage: push_to_new_repo.sh <github-owner>}"
REMOTE="https://github.com/${OWNER}/scholarship-navigator.git"
cd "$(git rev-parse --show-toplevel)"
git subtree split --prefix=scholarship-navigator -b scholarship-navigator-export
git push -u "${REMOTE}" scholarship-navigator-export:main
echo "Pushed. Clone with: git clone ${REMOTE}"
