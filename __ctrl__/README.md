# rust-native `__ctrl__`

The **control layer** for Rust-Native — one CLI for the web kit, native shells, and the project lifecycle.

```bat
rust-native-ctrl.bat web use svelte
rust-native-ctrl.bat setup-local
rust-native-ctrl.bat dev run all
rust-native-ctrl.bat native run win
rust-native-ctrl.bat native run android
```

## Command map

| Area | Commands |
|------|----------|
| Web kit | `web list` · `web use svelte` · `web status` · `web update` |
| Native clients | `native list` · `native build {android\|win\|all}` · `native run {android\|win}` · `native clean {android\|win\|all}` |
| Local tooling | `setup-local [--force]` |
| Dev stack | `dev run\|stop\|down\|purge\|reset {infra,apps,all}` · `--slim` for lightweight runtime |
| App scaffold | `app create <name>` |
| Tests | `test {all,backend,frontend}` |
| Local prod smoke | `prod start\|stop\|reset\|backup-acme\|…` |
| SSH / VM | `setup`, `pubkey`, `clone`, `env`, `start`, `stop`, `update`, `reset`, `backup-acme`, `connect`, … |

`web use` downloads that kit's `frontend/` from GitHub into `frontend/web` and writes `frontend/kit.lock.json`. `setup-local`, `dev run`, and `test frontend` stop until a kit is installed. Switching kits needs `web use <kit> --replace`. `web update` re-fetches the locked branch and stops when `frontend/web` has local edits unless you pass `--force`.

## Layout

| Path | Role |
|------|------|
| `kits.json` | Svelte download profile |
| `platforms.json` | Windows and Android targets (reserved, not built) |
| `servers.json` | Single VM entry |
| `safe/` | PEM, address, prod `.env` |
| `static/gpg` | Docker Ubuntu GPG (Iran bootstrap) |
| `remote/` | On-VM / local-prod compose scripts |
| `rust-native-ctrl.bat` / `.sh` | CLI entry |

## Local dev

`dev run` starts the backend on :8000 and the installed web kit on :5000.

Production compose builds `frontend/web` (`context: frontend/web`). `web use` rewrites the extracted Dockerfiles for that context.

## Native clients

```bat
rust-native-ctrl.bat native list
rust-native-ctrl.bat native build win
rust-native-ctrl.bat native run android
```

Android and Windows are reserved in `platforms.json`; `native build` and `native run` stop with a clear message until a client exists.

## Quick start (Windows)

From `rust-native/__ctrl__/`:

```bat
rust-native-ctrl.bat
```

Interactive prompt, or one-shot:

```bat
rust-native-ctrl.bat setup-local
rust-native-ctrl.bat dev run all
rust-native-ctrl.bat test all
rust-native-ctrl.bat list
rust-native-ctrl.bat connect
```

Linux/mac:

```bash
chmod +x rust-native-ctrl.sh
./rust-native-ctrl.sh status
```

## Command map

| Area | Commands |
|------|----------|
| Local tooling | `setup-local [--force]` |
| Dev stack | `dev run\|stop\|down\|purge\|reset {infra,apps,all}` · `--slim` for lightweight runtime |
| App scaffold | `app create <name>` |
| Tests | `test {all,backend,frontend}` |
| Local prod smoke | `prod start\|stop\|reset\|backup-acme\|…` |
| SSH / VM | `setup`, `pubkey`, `clone`, `env`, `start`, `stop`, `update`, `reset`, `backup-acme`, `connect`, … |

On-VM bash/bat scripts (what SSH `start`/`stop` invoke) live in [`remote/`](remote/README.md).

## Layout

| Path | Role |
|------|------|
| `servers.json` | Single VM entry (`rust-native`) |
| `safe/` | PEM, address, prod `.env` |
| `static/gpg` | Docker Ubuntu GPG (Iran bootstrap) |
| `remote/` | On-VM / local-prod compose scripts |
| `rust-native-ctrl.bat` / `.sh` | CLI entry |

## Typical first deploy (SSH)

```bat
rust-native-ctrl.bat setup
rust-native-ctrl.bat pubkey
REM add VM pubkey to GitHub
rust-native-ctrl.bat clone
rust-native-ctrl.bat env
rust-native-ctrl.bat start
```

Day-2:

```bat
rust-native-ctrl.bat update
rust-native-ctrl.bat status
rust-native-ctrl.bat backup-acme
```

## Local dev (Docker Desktop / host apps)

```bat
rust-native-ctrl.bat setup-local
rust-native-ctrl.bat dev run all
rust-native-ctrl.bat dev stop all
rust-native-ctrl.bat dev down all
rust-native-ctrl.bat dev purge infra
rust-native-ctrl.bat dev reset all
```

| Action | Infra (compose.dev.yml) | Apps (host) |
|--------|-------------------------|-------------|
| `run` / `start` | `up -d` db, redis (full), proxy, adminer | Rust (Axum) API :8000 (runs SQL migrations), Redis queue worker (full), installed web kit :5000 |
| `stop` | `compose stop` — containers kept | kill host processes |
| `down` | `compose down` — volumes kept | kill host processes |
| `purge` | `compose down -v` — wipe data, stay down | kill host processes |
| `reset` | wipe then `run` | stop then run |

| Target | Notes |
|--------|-------|
| `infra` | Docker only. SQL migrations run when the API starts |
| `apps` | host processes (needs infra already up) |
| `all` | run: infra→apps · stop/down/purge/reset: apps→infra |

Opens browser tabs for Adminer / Traefik / dashboard / API docs after a successful run.

**Runtime profiles:** `dev run all` (full — includes Redis + worker) · `dev run all --slim` (no Redis/worker). See [docs/runtime-profiles.md](../docs/runtime-profiles.md).

## Tests

```bat
rust-native-ctrl.bat test all
rust-native-ctrl.bat test backend
rust-native-ctrl.bat test frontend
```

Backend tests use in-memory fakes and need neither Postgres nor Redis. `test frontend` runs Vitest and `svelte-check`.

## Local production smoke

```bat
rust-native-ctrl.bat prod start
rust-native-ctrl.bat prod stop
rust-native-ctrl.bat prod reset
rust-native-ctrl.bat prod backup-acme
```

Same scripts SSH uses under `remote/`. Prefer SSH `start`/`stop` when operating the real VM from your laptop.

## Setup (ctrl tool itself)

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

`setup-local` also runs `npm install` for the frontend workspace.

On first `setup-local` / `dev run all`, the ctrl entry installs system **Python 3.10+** (via winget / Homebrew / apt) if missing, then `_setup_local` installs **Node.js LTS + npm** the same way before creating the project `.venv` and running `npm install`.

Iran VMs (`iran_setup: true`) keep provider DNS, rewrite apt to Arvan `apt_mirror`, and use Arvan Docker `registry_mirror`. `clone` routes GitHub SSH via `ssh.github.com:443`.

## Logs

```bat
REM Production VM (SSH)
rust-native-ctrl.bat logs api
rust-native-ctrl.bat logs db --no-follow

REM Local development
rust-native-ctrl.bat dev logs api
rust-native-ctrl.bat dev logs db

REM Local compose.yml smoke
rust-native-ctrl.bat prod logs api
```

## Flatten / restore-flat

```bat
rust-native-ctrl.bat flatten --yes
rust-native-ctrl.bat restore-flat
rust-native-ctrl.bat restore-flat --server <id> --yes
```

