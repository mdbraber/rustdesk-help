#!/usr/bin/env bash
# Prepare and push the build branch for the newest RustDesk release.
#
# Usage: scripts/sync.sh            (run by .github/workflows/sync.yml)
# Env:   VERSION   build this RustDesk version instead of the latest
#        FORCE     "true": build even if the release is newer than WAIT_DAYS
#                  or the branch already exists
#        WAIT_DAYS days a release must be public first (default 7)
#        REMOTE    where to push (default: origin of this checkout)
#
# The branch build/<version> holds the official RustDesk source of that
# release (with the hbb_common submodule as plain files), the changes of
# patch/apply.py, RustDesk's build workflow trimmed by trim-workflow.sh, and
# custom-build.yml. Pushing it starts the build.
set -euo pipefail
here=$(cd "$(dirname "$0")/.." && pwd)
WAIT_DAYS=${WAIT_DAYS:-7}
REMOTE=${REMOTE:-$(git -C "$here" remote get-url origin)}
FORCE=${FORCE:-false}

if [ -z "${VERSION:-}" ]; then
  rel=$(gh api repos/rustdesk/rustdesk/releases/latest)
  VERSION=$(jq -r .tag_name <<<"$rel")
  published=$(jq -r .published_at <<<"$rel")
  age=$(( ($(date -u +%s) - $(date -u -d "$published" +%s 2>/dev/null || date -u -j -f %Y-%m-%dT%H:%M:%SZ "$published" +%s)) / 86400 ))
  echo "latest RustDesk release: $VERSION, published $published ($age days ago)"
  if [ "$age" -lt "$WAIT_DAYS" ] && [ "$FORCE" != true ]; then
    echo "waiting until it is $WAIT_DAYS days old"
    exit 0
  fi
fi
[[ "$VERSION" =~ ^[0-9]+(\.[0-9]+)*$ ]] || { echo "unexpected version: $VERSION" >&2; exit 1; }

branch="build/$VERSION"
if git ls-remote --exit-code --heads "$REMOTE" "$branch" >/dev/null 2>&1 && [ "$FORCE" != true ]; then
  echo "$branch exists already; nothing to do"
  exit 0
fi

work=$(mktemp -d)
trap 'chmod -R u+w "$work" 2>/dev/null; rm -rf "$work" 2>/dev/null || true' EXIT
git clone -q --depth 1 --branch "$VERSION" https://github.com/rustdesk/rustdesk "$work/src"
cd "$work/src"
upstream=$(git rev-parse HEAD)
git submodule update -q --init --depth 1 libs/hbb_common
hbb=$(git -C libs/hbb_common rev-parse HEAD)
# The branch is a fresh history: plain files, no submodules.
rm -rf .git libs/hbb_common/.git .gitmodules

python3 -I "$here/patch/apply.py" .
bash "$here/scripts/trim-workflow.sh" .
sed "s/@VERSION@/$VERSION/g" "$here/scripts/custom-build.yml" > .github/workflows/custom-build.yml

git init -q -b "$branch"
git add -A
git -c user.name="rustdesk-help" -c user.email="rustdesk-help@users.noreply.github.com" commit -q \
  -m "RustDesk $VERSION with the ID server rustdesk.nedworks.org" \
  -m "Official source: rustdesk/rustdesk $VERSION ($upstream), libs/hbb_common at rustdesk/hbb_common $hbb. Changes: patch/apply.py and scripts/trim-workflow.sh of rustdesk-help."
push_args=(-q)
[ "$FORCE" = true ] && push_args+=(--force)
git push "${push_args[@]}" "$REMOTE" "HEAD:refs/heads/$branch"
echo "pushed $branch; the build starts on GitHub"
