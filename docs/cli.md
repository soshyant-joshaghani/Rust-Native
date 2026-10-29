# CLI

```bat
__ctrl__\rust-native-ctrl.bat <command>
```

| Command | Effect |
|---------|--------|
| `setup-local` | Install this kit's runtime dependencies |
| `dev run all` | Infra, API, worker, Vite |
| `dev stop all` | Stop host apps and compose |
| `test all` | Backend and frontend tests |
| `app create <name>` | Module stub (backend and frontend) |
| `prod start` / `prod stop` | Production compose |
| `logs` | Host and production logs |
| `flatten` / `restore-flat` | Single-root git history |
| `ping`, `clone`, `env`, `start`, `stop`, `status`, `update` | SSH operations from `servers.json` |
| `web list`, `web use svelte`, `native list` | Web client catalog and native platforms |

Linux and macOS use `rust-native-ctrl.sh`. Details: [`__ctrl__/README.md`](../__ctrl__/README.md).

## Seed

Demo data through the public APIs (idempotent, no raw SQL):

```bat
rust-native-ctrl.bat seed all --api http://api.localhost
rust-native-ctrl.bat seed users
rust-native-ctrl.bat seed all --purge
```

Packs: `users`, `notes`. Auth is `FIRST_SUPERUSER` from `.env`; non-local APIs need `--allow-remote`. See [`utils/seed/README.md`](../__ctrl__/utils/seed/README.md).
