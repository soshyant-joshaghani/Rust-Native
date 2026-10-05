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
