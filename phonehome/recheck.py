"""Monthly re-verification: fetch every source URL, extract the telemetry-relevant lines,
and compare against data/source_hashes.json. Prints a Markdown report and exits 1 when
anything changed or vanished, so CI can open an issue."""
import os, re, sys, json, hashlib, urllib.request, html
from .registry import load_apps

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HASHES = os.path.join(ROOT, "data", "source_hashes.json")
KEYWORDS = re.compile(r"telemetry|analytics|anonymous|usage|statistic|report|opt[- ]?out|disable|phone|beacon|insights|diagnostic|update[- ]?check|gravatar|track", re.I)


class _Redirect308(urllib.request.HTTPRedirectHandler):
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


_opener = urllib.request.build_opener(_Redirect308())


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; phonehome-recheck/1; +https://github.com/12burb/phonehome)"})
    with _opener.open(req, timeout=40) as r:
        body = r.read().decode("utf-8", "ignore")
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", body, flags=re.S)
    text = html.unescape(re.sub(r"<[^>]+>", " ", body))
    return text


def fingerprint(text):
    """Hash only the lines that talk about telemetry so cosmetic page changes do not alert."""
    lines = sorted({" ".join(l.split()) for l in text.splitlines() if KEYWORDS.search(l)})
    return hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16], len(lines)


def main(update=False):
    apps = load_apps()
    old = json.load(open(HASHES)) if os.path.exists(HASHES) else {}
    new, changed, gone, added = {}, [], [], []
    urls = {}
    for a in apps:
        for c in a.get("calls") or []:
            for u in c.get("sources") or []:
                urls.setdefault(u, set()).add(a["id"])
        for u in a.get("sources") or []:
            urls.setdefault(u, set()).add(a["id"])
    for u in sorted(urls):
        if "github.com/search?" in u:
            continue  # search pages are not stable documents
        try:
            fp, n = fingerprint(fetch(u))
        except Exception as e:
            gone.append((u, sorted(urls[u]), str(e)[:80]))
            if u in old:
                new[u] = old[u]
            continue
        new[u] = {"fp": fp, "lines": n}
        if u not in old:
            added.append((u, sorted(urls[u])))
        elif old[u]["fp"] != fp:
            changed.append((u, sorted(urls[u])))
    lines = ["# phonehome monthly re-check", ""]
    if changed:
        lines += ["## Sources whose telemetry-related text changed", ""] + [f"- {u} (apps: {', '.join(a)})" for u, a in changed] + [""]
    if gone:
        lines += ["## Sources that could not be fetched", ""] + [f"- {u} (apps: {', '.join(a)}) - {e}" for u, a, e in gone] + [""]
    if added:
        lines += ["## New sources recorded", ""] + [f"- {u} (apps: {', '.join(a)})" for u, a in added] + [""]
    if not (changed or gone):
        lines += ["All sources unchanged.", ""]
    lines += [f"Checked {len(new)} URLs across {len(apps)} apps. Re-verify the listed apps and bump their `verified` date."]
    report = "\n".join(lines)
    print(report)
    if update or not os.path.exists(HASHES):
        json.dump(new, open(HASHES, "w"), indent=1, sort_keys=True)
    with open(os.path.join(ROOT, "recheck-report.md"), "w") as f:
        f.write(report)
    return 1 if (changed or gone) else 0


if __name__ == "__main__":
    sys.exit(main(update="--update" in sys.argv))
