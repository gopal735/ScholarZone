"""List links and image assets of a page (research helper)."""
import re
import sys
import urllib.request


def main(urls):
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research)"})
        try:
            body = urllib.request.urlopen(request, timeout=45).read().decode("utf-8", "replace")
        except Exception as error:
            print("==", url, "FAILED", type(error).__name__, str(error)[:100])
            continue
        links = sorted(set(re.findall(r"""href=["']([^"']+\.html?)[^"']*["']""", body)))
        imgs = sorted(set(re.findall(r"""(?:src|content)=["']([^"']+\.(?:png|jpg|jpeg|svg|ico))["']""", body, re.I)))
        print("==", url)
        print("  links:", [link for link in links if "hkpfs" in link or "rgc" in link or "ugc" in link][:14])
        print("  imgs:", imgs[:8])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
