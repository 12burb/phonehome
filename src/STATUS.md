# phonehome project status (scratch for Devin)
- Project at ~/research/phonehome (git initialized on main, 1 commit). Remote: https://github.com/12burb/phonehome, Pages live at https://12burb.github.io/phonehome/
- Build: python3 -m phonehome.build ; tests: python3 -m pytest -q ; CLI: python3 -m phonehome.cli audit <compose>
- Data: data/apps/*.yaml (131 apps). Validator in phonehome/registry.py. Site in phonehome/site.py (vanilla JS). Blocklists only include hosts with >=2 dots unless block: true.
- Research helpers: src/probe.py (curl+grep), src/batch.sh (stdin URL|||pattern), src/ghs.py (GitHub code search, 10/min limit).
- Still unverified/not added: GitLab service ping, Synapse report_stats, Portainer telemetry default, Ghost update check, Plausible/Pi-hole/AdGuard clean entries, memos/miniflux/audiobookshelf.
- Monthly recheck: phonehome/recheck.py + .github/workflows/recheck.yml (cron 1st of month, opens issue, commits data/source_hashes.json). Issue #1 was the baseline run (closed).
- Unresolved candidates (need better sources): Portainer (no telemetry setting found in current code; --no-analytics deprecated), MinIO (MINIO_UPDATE opt-out not confirmed in cmd/update.go), Graylog (telemetry not in graylog.conf), Rancher (telemetry-opt), Woodpecker (version check URL).
