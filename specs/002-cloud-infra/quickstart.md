# Quickstart: validating Cloud Infrastructure

## Local (no cloud)

```bash
make test                                      # includes tests/test_main_healthz.py
docker compose build                           # app and mcp images build from the repo root
docker compose up -d app && sleep 3
curl -s localhost:8000/healthz                 # {"ok": true}  (port mapping is only for this local check)
docker compose down
```

## Provision (laptop, LINODE_TOKEN in .env)

```bash
scripts/provision_linode.sh                    # prints IPv4 and HOST=<ip-with-dashes>.sslip.io; run twice → no duplicates
ssh -A root@<IP> 'bash -s' < scripts/bootstrap_vm.sh   # docker, sqlite3, clone to /opt/callmeback
grep -v -E '^(LINODE_TOKEN|AWS_)' .env | ssh root@<IP> 'umask 077; cat > /opt/callmeback/.env'
ssh root@<IP> "cd /opt/callmeback && sed -i -E 's|^HOST=.*|HOST=<host>|; s|^PUBLIC_BASE_URL=.*|PUBLIC_BASE_URL=https://<host>|; s|^MCP_ALLOWED_HOSTS=.*|MCP_ALLOWED_HOSTS=<host>|; s|^ACME_EMAIL=.*|ACME_EMAIL=<you@example.com>|' .env && docker compose up -d --build && docker compose logs -f caddy"
# wait for "certificate obtained successfully", Ctrl-C
```

## Verify the edge (laptop)

```bash
scripts/probe_edge.sh <host> demo '<dashboard password>'   # every row OK, exit 0
make check-env PHASE=integrate                              # Public HTTPS URL READY
```

## Operations

```bash
time make deploy                                            # < 3 min; new commit visible
ssh root@<IP> 'reboot'; sleep 90; curl -s https://<host>/healthz   # 200, same certificate
ssh root@<IP> 'cd /opt/callmeback && bash scripts/backup_db.sh && ls data/'
```

## Twilio spike (milestone B2)

```bash
.venv/bin/python scripts/twilio_spike.py        # calls DEMO_VENDOR_PHONE; answer, press 1 or say yes
ssh root@<IP> 'cd /opt/callmeback && docker compose logs app | grep spike'   # timestamps per status
```
Record dial → ring → answer times and the caller-ID shown on the phone in `docs/decisions.md`.
