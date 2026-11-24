#!/usr/bin/env python3
"""Apply this repository's changes to a RustDesk source tree.

Usage: python3 -I patch/apply.py <rustdesk-source-dir>

1. The built-in ID server and key become ours, so the app works with
   rustdesk.nedworks.org without any setup.
2. The update check is switched off: it would offer clients the official
   RustDesk build, which replaces this one (and its settings). New versions
   reach clients through this repository's download page instead.

Every change must match exactly once; anything else stops the build, so an
upstream change never yields a client that silently uses RustDesk's servers.
"""
import re
import sys
from pathlib import Path

HOST = "rustdesk.nedworks.org"
KEY = "kSqfVgZGwOHx2yoFdJGkNS3H5mCg6UF40aeBFyx3P8M="


def sub_once(path, pattern, repl):
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text, flags=re.M)
    if n != 1:
        sys.exit(f"{path}: expected exactly one match for {pattern!r}, found {n}")
    path.write_text(new, encoding="utf-8")
    print(f"patched {path}")


def main():
    src = Path(sys.argv[1])
    config = src / "libs/hbb_common/src/config.rs"
    sub_once(config,
             r'^pub const RENDEZVOUS_SERVERS: &\[&str\] = &\[[^\]]*\];$',
             f'pub const RENDEZVOUS_SERVERS: &[&str] = &["{HOST}"];')
    sub_once(config,
             r'^pub const RS_PUB_KEY: &str = "[^"]*";$',
             f'pub const RS_PUB_KEY: &str = "{KEY}";')
    common = src / "src/common.rs"
    sub_once(common,
             r'^(pub fn check_software_update\(\) \{\n    )if is_custom_client\(\) \{$',
             r'\1// rustdesk-help: no update check, see patch/apply.py\n    if true || is_custom_client() {')


if __name__ == "__main__":
    main()
