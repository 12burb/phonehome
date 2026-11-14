"""Generate dist/: apps.json, blocklists and the static site."""
import os, sys, json, datetime
from .registry import load_apps, validate, status_of, env_optouts, block_hosts, STATUS_LABEL, STATUS_ORDER

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def public(app):
    a = {k: v for k, v in app.items() if not k.startswith("_")}
    a["status"] = status_of(app)
    a["status_label"] = STATUS_LABEL[a["status"]]
    a["env_optouts"] = env_optouts(app)
    return a

def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

def hosts_file(hosts, title, fmt):
    today = datetime.date.today().isoformat()
    lines = [f"# phonehome - {title}", f"# generated {today} from https://github.com/12burb/phonehome", "#"]
    for h in sorted(hosts):
        apps = ",".join(sorted(hosts[h]))
        if fmt == "hosts":
            lines.append(f"0.0.0.0 {h}  # {apps}")
        elif fmt == "adguard":
            lines.append(f"||{h}^  # {apps}")
        else:  # plain domains (Pi-hole / Blocky / Technitium)
            lines.append(f"{h}")
    return "\n".join(lines) + "\n"

def main(out=None):
    out = out or os.path.join(ROOT, "dist")
    apps = load_apps()
    errs = [e for a in apps for e in validate(a)]
    if errs:
        print("\n".join(errs)); sys.exit(1)
    pub = sorted((public(a) for a in apps), key=lambda a: (STATUS_ORDER.index(a["status"]), a["name"].lower()))
    write(os.path.join(out, "apps.json"), json.dumps(pub, indent=1, ensure_ascii=False))
    tele = block_hosts(apps)
    tele_upd = block_hosts(apps, include_update_checks=True)
    for name, hosts in (("telemetry", tele), ("telemetry-and-updates", tele_upd)):
        write(os.path.join(out, "blocklists", f"{name}.hosts"), hosts_file(hosts, name + " (hosts format)", "hosts"))
        write(os.path.join(out, "blocklists", f"{name}.adguard.txt"), hosts_file(hosts, name + " (AdGuard Home / uBlock)", "adguard"))
        write(os.path.join(out, "blocklists", f"{name}.domains.txt"), hosts_file(hosts, name + " (plain domains for Pi-hole, Blocky, Technitium)", "domains"))
    from .site import render
    write(os.path.join(out, "index.html"), render(pub))
    counts = {s: sum(1 for a in pub if a["status"] == s) for s in STATUS_ORDER}
    print(f"{len(pub)} apps, {len(tele)} telemetry hosts, {len(tele_upd)} incl. update hosts ->", out)
    print(counts)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
