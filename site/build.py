#!/usr/bin/env python3
"""Build the download page for help.mdbraber.com.

Run with: python3 -I site/build.py [output-dir]   (default: ./public)
Env: GH_TOKEN (optional, avoids GitHub's rate limit), GITHUB_REPOSITORY
     (default mdbraber/rustdesk-help).

- Mac and Android: this repository's latest release (RustDesk built with
  the server inside) when it has that platform's file; otherwise the
  official app, and the page shows the setup step for the server settings.
- Windows: the official installer, saved under a name that carries the
  server settings (RustDesk reads host= and key= from its file name). It is
  downloaded, checked against GitHub's SHA-256 digest and served from the
  page itself, because a page can't rename a download from another site.
- Linux: links to the official packages; the page shows the setup step.
"""
import base64, hashlib, html, json, os, re, shutil, sys, urllib.request

HOST = "rustdesk.nedworks.org"
KEY = "kSqfVgZGwOHx2yoFdJGkNS3H5mCg6UF40aeBFyx3P8M="
REPO = os.environ.get("GITHUB_REPOSITORY", "mdbraber/rustdesk-help")

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "public")
FILES = os.path.join(OUT, "files")


def config_string():
    # RustDesk's ServerConfig.encode(): base64url of the JSON, reversed.
    c = {"host": HOST, "relay": "", "api": "", "key": KEY}
    return base64.urlsafe_b64encode(json.dumps(c, separators=(",", ":")).encode()).decode()[::-1]


def request(url, accept="application/vnd.github+json"):
    h = {"Accept": accept, "User-Agent": "rustdesk-help-page"}
    if os.environ.get("GH_TOKEN") and url.startswith("https://api.github.com/"):
        h["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    return urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=300)


def get_json(url):
    with request(url) as r:
        return json.load(r)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def download(asset, dest):
    want = (asset.get("digest") or "").removeprefix("sha256:")
    if not want:
        sys.exit(f"no digest published for {asset['name']}; refusing to serve it unverified")
    tmp = dest + ".part"
    with request(asset["browser_download_url"], "application/octet-stream") as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    if sha256(tmp) != want:
        os.remove(tmp)
        sys.exit(f"checksum mismatch for {asset['name']}")
    os.replace(tmp, dest)
    print(f"verified {asset['name']} -> {os.path.basename(dest)}")


def ours():
    """This repository's latest published release, or None."""
    try:
        for rel in get_json(f"https://api.github.com/repos/{REPO}/releases?per_page=20"):
            if not rel["draft"] and not rel["prerelease"] and not rel["tag_name"].startswith("build-"):
                return rel
    except urllib.error.HTTPError as e:
        print(f"no releases of {REPO}: {e}")
    return None


def main():
    official = get_json("https://api.github.com/repos/rustdesk/rustdesk/releases/latest")
    ov = official["tag_name"]
    oa = {a["name"]: a for a in official["assets"]}

    def off(name):
        name = name.format(v=ov)
        if name not in oa:
            sys.exit(f"official release {ov} has no file {name}")
        return oa[name]

    rel = ours()
    # GitHub's "latest release" links always lead to the newest file under
    # the same name, so a copy of this page hosted elsewhere stays current
    # for Mac and Android without being rebuilt.
    latest = f"https://github.com/{REPO}/releases/latest/download/"
    mine = {a["name"]: latest + a["name"] for a in (rel["assets"] if rel else [])}
    custom_mac = "RustDesk-Mac-Apple-chip.dmg" in mine and "RustDesk-Mac-Intel.dmg" in mine
    custom_android = "RustDesk-Android.apk" in mine

    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(FILES)
    win = {}
    for arch, tag in (("x86_64", "x64"), ("aarch64", "arm64")):
        # RustDesk ignores file-name parts it doesn't know; the trailing tag
        # keeps the two apart and absorbs a browser's " (1)" suffix.
        name = f"rustdesk-host={HOST},key={KEY},{tag}.exe"
        download(off(f"rustdesk-{{v}}-{arch}.exe"), os.path.join(FILES, name))
        win[arch] = name

    url = lambda n: off(n)["browser_download_url"]
    values = {
        "HOST": HOST, "KEY": KEY, "CONFIG": config_string(),
        "WIN_X64": win["x86_64"], "WIN_ARM": win["aarch64"],
        "MAC_ARM": mine["RustDesk-Mac-Apple-chip.dmg"] if custom_mac else url("rustdesk-{v}-aarch64.dmg"),
        "MAC_X64": mine["RustDesk-Mac-Intel.dmg"] if custom_mac else url("rustdesk-{v}-x86_64.dmg"),
        "ANDROID": mine["RustDesk-Android.apk"] if custom_android else url("rustdesk-{v}-universal-signed.apk"),
        "LINUX_X64_DEB": url("rustdesk-{v}-x86_64.deb"), "LINUX_X64_RPM": url("rustdesk-{v}-0.x86_64.rpm"),
        "LINUX_X64_APPIMAGE": url("rustdesk-{v}-x86_64.AppImage"), "LINUX_X64_FLATPAK": url("rustdesk-{v}-x86_64.flatpak"),
        "LINUX_ARM_DEB": url("rustdesk-{v}-aarch64.deb"), "LINUX_ARM_RPM": url("rustdesk-{v}-0.aarch64.rpm"),
        "LINUX_ARM_APPIMAGE": url("rustdesk-{v}-aarch64.AppImage"), "LINUX_ARM_FLATPAK": url("rustdesk-{v}-aarch64.flatpak"),
    }
    # Every download, for the split buttons: the page shows the detected
    # version as the main button and the others in the menu beside it.
    def item(id_, os_, url_, nl, en, local=False):
        return {"id": id_, "os": os_, "url": url_, "local": local, "nl": nl, "en": en}
    def names(group_nl, group_en, name_nl, name_en, main_nl, main_en):
        # "main" without the "Download for" prefix: the page adds it, and
        # leaves it out on narrow screens so the button fits on one line.
        return ({"group": group_nl, "name": name_nl, "main": main_nl.removeprefix("Downloaden voor ")},
                {"group": group_en, "name": name_en, "main": main_en.removeprefix("Download for ")})
    lx = lambda arch_nl, arch_en, kind, kind_long, key: item(
        f"linux-{'arm' if arch_en == 'ARM' else 'x64'}-{kind}", "linux", values[key],
        *names(f"Linux ({arch_nl})", f"Linux ({arch_en})", kind_long, kind_long,
               f"Downloaden voor Linux ({kind_long.split()[0]}, {arch_nl})",
               f"Download for Linux ({kind_long.split()[0]}, {arch_en})"))
    downloads = [
        item("win-x64", "windows", "files/" + values["WIN_X64"],
             *names("Windows", "Windows", "Windows (Intel/AMD)", "Windows (Intel/AMD)",
                    "Downloaden voor Windows", "Download for Windows"), local=True),
        item("win-arm", "windows", "files/" + values["WIN_ARM"],
             *names("Windows", "Windows", "Windows op ARM", "Windows on ARM",
                    "Downloaden voor Windows op ARM", "Download for Windows on ARM"), local=True),
        item("mac-arm", "mac", values["MAC_ARM"],
             *names("Mac", "Mac", "Mac met Apple-chip (M1 of nieuwer)", "Mac with Apple chip (M1 or newer)",
                    "Downloaden voor Mac met Apple-chip", "Download for Mac with Apple chip")),
        item("mac-x64", "mac", values["MAC_X64"],
             *names("Mac", "Mac", "Mac met Intel-processor", "Mac with Intel processor",
                    "Downloaden voor Mac met Intel", "Download for Mac with Intel")),
        lx("Intel/AMD", "Intel/AMD", "deb", ".deb (Ubuntu, Debian)", "LINUX_X64_DEB"),
        lx("Intel/AMD", "Intel/AMD", "rpm", ".rpm (Fedora)", "LINUX_X64_RPM"),
        lx("Intel/AMD", "Intel/AMD", "appimage", "AppImage", "LINUX_X64_APPIMAGE"),
        lx("Intel/AMD", "Intel/AMD", "flatpak", "Flatpak", "LINUX_X64_FLATPAK"),
        lx("ARM", "ARM", "deb", ".deb (Ubuntu, Debian)", "LINUX_ARM_DEB"),
        lx("ARM", "ARM", "rpm", ".rpm (Fedora)", "LINUX_ARM_RPM"),
        lx("ARM", "ARM", "appimage", "AppImage", "LINUX_ARM_APPIMAGE"),
        lx("ARM", "ARM", "flatpak", "Flatpak", "LINUX_ARM_FLATPAK"),
        item("android", "android", values["ANDROID"],
             *names("Android", "Android", "Android", "Android",
                    "Downloaden voor Android", "Download for Android")),
    ]
    # Safe inside <script>: no "</" can end the element early.
    downloads_json = json.dumps(downloads, ensure_ascii=False).replace("</", "<\\/")
    def noscript(lang):
        out, group = [], None
        for d in downloads:
            if d[lang]["group"] != group:
                if group is not None:
                    out.append("</p>")
                group = d[lang]["group"]
                out.append(f"<p><strong>{html.escape(group)}</strong>: ")
            dl = " download" if d["local"] else ""
            out.append(f'<a href="{html.escape(d["url"])}"{dl}>{html.escape(d[lang]["name"])}</a> ')
        out.append("</p>")
        return "".join(out)

    flags = {"custom-mac": custom_mac, "official-mac": not custom_mac,
             "custom-android": custom_android, "official-android": not custom_android}
    src = f"https://github.com/{REPO}" if rel else "https://github.com/rustdesk/rustdesk"
    off_link = f'<a href="https://github.com/rustdesk/rustdesk/releases/tag/{ov}">'
    footers = {
        "nl": (f'RustDesk {html.escape(rel["tag_name"])} voor Mac en Android is <a href="{src}">gebouwd uit de officiële broncode</a> met mijn server ingebouwd; '
               f'de andere downloads komen van {off_link}RustDesk {ov}</a>.') if rel else
              f'De downloads komen van {off_link}de officiële RustDesk-release {ov}</a>.',
        "en": (f'RustDesk {html.escape(rel["tag_name"])} for Mac and Android is <a href="{src}">built from the official source</a> with my server built in; '
               f'the other downloads come from {off_link}RustDesk {ov}</a>.') if rel else
              f'Downloads come from {off_link}the official RustDesk release {ov}</a>.',
    }

    for lang, out in (("nl", "index.html"), ("en", "en.html")):
        with open(os.path.join(HERE, f"template.{lang}.html"), encoding="utf-8") as f:
            page = f.read()
        def block(m):
            return m.group(2) if flags[m.group(1)] else ""
        page = re.sub(r"<!--if ([a-z-]+)-->\n(.*?)<!--end-->\n", block, page, flags=re.S)
        if "<!--if" in page or "<!--end" in page:
            sys.exit(f"unbalanced <!--if--> blocks in template.{lang}.html")
        for k, v in {**values, "FOOTER": footers[lang], "DOWNLOADS_JSON": downloads_json, "NOSCRIPT": noscript(lang)}.items():
            page = page.replace("{{" + k + "}}", v)
        if "{{" in page:
            sys.exit(f"unfilled placeholder left in template.{lang}.html")
        with open(os.path.join(OUT, out), "w", encoding="utf-8") as f:
            f.write(page)
    shutil.copy(os.path.join(HERE, "qr-config.svg"), OUT)
    print(f"built {OUT}: Windows/Linux official {ov}; Mac {'ours' if custom_mac else 'official'}; "
          f"Android {'ours' if custom_android else 'official'}"
          + (f" (release {rel['tag_name']})" if rel else ""))


if __name__ == "__main__":
    main()
