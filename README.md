# phonehome — does your self-hosted app phone home?

A verified registry of **what self-hosted apps send out of your network by default** — usage telemetry, crash reports, update checks and third-party requests — with the **exact switch that turns each one off**. Every entry links to the source code or documentation it was checked against.

It ships as:

- **Website** — searchable list with per-app opt-outs (built from `data/apps/`, published with GitHub Pages).
- **Blocklists** — `dist/blocklists/telemetry.{hosts,adguard.txt,domains.txt}` for Pi-hole, AdGuard Home, Blocky, Technitium, uBlock, `/etc/hosts`. A second set also blocks update-check hosts.
- **CLI** — `phonehome audit docker-compose.yml` matches your service images against the registry and prints the opt-out variables you are missing.
- **Data** — `dist/apps.json`, one JSON array for anyone to reuse.

Why: self-hosting is about control, yet many popular apps ship with analytics on, and the flag to disable it is buried in a config reference. This project is the shared fact base so nobody has to grep the source again.

## Quick start

```bash
pipx run phonehome audit docker-compose.yml     # or: pip install phonehome
phonehome list
phonehome show grafana
```

Example output:

```
grafana  (Grafana, Telemetry on by default)
   [ok]   telemetry      -> stats.grafana.org  (opt-out env present)
   [MISS] update_check   -> grafana.com
          add: GF_ANALYTICS_CHECK_FOR_UPDATES=false or GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false

meili  (Meilisearch, Telemetry on by default)
   [MISS] telemetry      -> telemetry.meilisearch.com, api.segment.io
          add: MEILI_NO_ANALYTICS=true
```

Exit code `2` means at least one default-on call has no opt-out in your compose file, so it works as a CI gate.

Blocklists: point your DNS filter at `blocklists/telemetry.domains.txt` (plain domains) or `telemetry.adguard.txt`. Only dedicated telemetry hostnames are listed; shared hosts like `sentry.io` or `api.github.com` are never included unless an entry explicitly marks them blockable. Prefer the opt-out switch — some apps log errors or retry when DNS is blocked.

## How entries are classified

| Status | Meaning |
| --- | --- |
| Telemetry on by default | Sends usage or crash data without asking |
| Asks on first run | Prompts the admin during setup |
| Third-party requests by default | Leaks metadata to outside services (Gravatar, vendor map tiles, icon CDNs) but no usage telemetry |
| Update check only | Only fetches version information |
| Telemetry is opt-in | Telemetry code exists but is off until you enable it |
| No outbound calls found | Nothing recorded |

The status is derived automatically from the recorded `calls`. Defaults describe the upstream Docker image / default config at the `verified` date; distributions, Helm charts and “all-in-one” images may differ.

## Data format

One YAML file per app in `data/apps/<id>.yaml`:

```yaml
id: grafana
name: Grafana
category: Monitoring
repo: https://github.com/grafana/grafana
images: [grafana/grafana, grafana/grafana-oss]     # used by `phonehome audit`
verified: 2026-11-14
calls:
  - type: telemetry            # telemetry | crash_report | update_check | external_asset | cloud_feature
    default: "on"              # on | off | prompt
    destinations: [stats.grafana.org]
    sends: Counters of running instances, versions, dashboards and errors
    frequency: every 24h
    optout:
      env: ["GF_ANALYTICS_REPORTING_ENABLED=false"]   # NAME=value, used by the audit
      config: "[analytics] reporting_enabled = false"
      ui: ...                                           # optional
      cli: ...                                          # optional
    block: false               # optional: force a host in/out of the blocklists
    sources:
      - https://grafana.com/docs/grafana/latest/setup-grafana/configure-grafana/#analytics
notes: optional free text
```

Rules enforced by `phonehome validate` (and CI): every call needs a source URL and a description of what is sent; every default-on or prompt call needs an opt-out; env opt-outs must be `NAME=value`.

## Contributing

1. Add or edit `data/apps/<id>.yaml`. Cite the config reference, `.env.example`, or the source file that proves the default and the switch — not a blog post.
2. Run `phonehome validate && pytest -q`.
3. Open a pull request. Corrections from maintainers of the listed projects are especially welcome; if we got your project wrong, tell us and we will fix it fast.

Things we want next: more apps (the long tail of r/selfhosted), a GitHub Action that re-verifies sources, and a `check` subcommand that inspects a running container's environment.

## Development

```bash
pip install -e . pytest
pytest -q
python -m phonehome.build dist     # site + blocklists + apps.json
python -m http.server -d dist 8000
```

## License

MIT. Not affiliated with any listed project; trademarks belong to their owners.
