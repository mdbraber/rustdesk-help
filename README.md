# rustdesk-help

RustDesk clients for my own RustDesk server (`rustdesk.nedworks.org`), built
from the official RustDesk source on GitHub, and the download page at
<https://help.mdbraber.com> that my clients use to get them.

This is not an official RustDesk project. RustDesk is licensed under the
AGPL-3.0; the source of every build is the `build/<version>` branch it was
built from.

## What it does

- **Daily check** (`.github/workflows/sync.yml`): when RustDesk publishes a
  release that is at least 7 days old, `scripts/sync.sh` creates the branch
  `build/<version>` from the official source with:
  - `patch/apply.py`: my ID server and key built in, the update check off
    (it would offer the official build, which would replace this one);
  - `scripts/trim-workflow.sh`: RustDesk's own build workflow, cut down to
    the Android and Mac jobs; the Mac job waits for approval in the
    `signing` environment, the only place the Mac signing secrets exist;
  - `scripts/custom-build.yml`: builds, then publishes release `<version>`
    with `RustDesk-Android.apk`, `RustDesk-Mac-Apple-chip.dmg` and
    `RustDesk-Mac-Intel.dmg`, and refreshes the page.
  A failure of the daily check opens an issue.
- **Download page** (`.github/workflows/pages.yml`, `site/`): Dutch
  (`index.html`) and English (`en.html`). Mac and Android come from this
  repository's latest release when it has them, otherwise from the official
  release with a setup step. Windows is the official installer saved under a
  name that carries the server settings (RustDesk reads `host=` and `key=`
  from its file name). Linux links to the official packages.

## Secrets and settings

| Name | Kind | Used for |
|------|------|----------|
| `SYNC_TOKEN` | repository secret | fine-grained token for this repository only (Contents and Workflows: read and write): pushing build branches, which contain workflow files |
| `ANDROID_SIGNING_KEY`, `ANDROID_ALIAS`, `ANDROID_KEY_STORE_PASSWORD`, `ANDROID_KEY_PASSWORD` | repository secrets | signing the Android app (own key, PKCS#12, base64) |
| `MACOS_P12_BASE64`, `MACOS_P12_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `MACOS_NOTARIZE_JSON` | `signing` environment secrets | Developer ID signing and notarization of the Mac app |
| `MAC_SIGNING` | repository variable | `true` once Mac signing is set up; until then the release has no Mac apps |

`MACOS_CODESIGN_IDENTITY` is used unquoted in RustDesk's shell steps, so store
it with its own quotes, e.g. `"Developer ID Application: Name (TEAMID)"`.
`MACOS_NOTARIZE_JSON` is the base64 of an `rcodesign` App Store Connect API
key file (`rcodesign encode-app-store-connect-api-key`).

## By hand

- Build a version now: Actions → *Check for a new RustDesk release* → Run
  workflow (optionally a version, and *force*).
- Approve the Mac signing: the build waits at *Review deployments*.
