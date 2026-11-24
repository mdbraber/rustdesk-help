#!/usr/bin/env bash
# Trim RustDesk's .github/workflows in a source tree to what this repository
# builds: the Android apps and the signed Mac apps.
#
# Usage: scripts/trim-workflow.sh <rustdesk-source-dir>
#
# - flutter-build.yml keeps only the jobs below; everything else (Windows,
#   Linux, iOS, update metadata, SBOM) is removed.
# - The Mac job runs in the "signing" environment: it waits for the owner's
#   approval and is the only job that sees the Mac signing secrets.
# - Every other workflow file is removed unless a kept job calls it, so the
#   build branch runs nothing but custom-build.yml.
set -euo pipefail
src=$1
wf="$src/.github/workflows"
fb="$wf/flutter-build.yml"

KEEP='["validate-update-metadata-keys","generate-bridge","build-for-macOS","build-rustdesk-android","build-rustdesk-android-universal"]'

for j in $(yq -r "$KEEP | .[]" <<<'{}'); do
  [ "$(yq -r ".jobs | has(\"$j\")" "$fb")" = true ] || { echo "flutter-build.yml has no job $j" >&2; exit 1; }
done

yq -i "
  .jobs |= with_entries(select(.key as \$k | $KEEP | any_c(. == \$k)))
  | .jobs.\"build-for-macOS\".environment = \"signing\"
  | .jobs.\"build-for-macOS\".env.MACOS_P12_BASE64 = \"\${{ secrets.MACOS_P12_BASE64 }}\"
" "$fb"

# Every job a kept job needs must still be there.
missing=$(yq -r "[.jobs[] | .needs // [] | (select(type == \"!!str\") | [.]) // . | .[]] - (.jobs | keys) | .[]" "$fb")
if [ -n "$missing" ]; then
  echo "kept jobs need removed jobs: $missing" >&2
  exit 1
fi

# Keep only workflow files that flutter-build.yml calls (and itself).
keep="flutter-build.yml"
for f in $(grep -oE 'uses: \./\.github/workflows/[A-Za-z0-9._-]+' "$fb" | sed 's|.*/||' | sort -u); do
  keep="$keep $f"
done
for f in "$wf"/*; do
  name=$(basename "$f")
  case " $keep " in
    *" $name "*) ;;
    *) rm -f "$f" ;;
  esac
done
echo "workflows kept: $keep"
