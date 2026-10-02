# On-VM / local-prod scripts (run inside the project tree)

These bash/bat helpers live in the cloned repo so production can start without the
laptop CLI. Prefer **`rust-native-ctrl`** from your machine when possible.

| Script | CLI equivalent |
|--------|----------------|
| `start-prod.*` | `rust-native-ctrl start` (SSH) or `prod start` (local) |
| `stop-prod.*` | `stop` / `prod stop` |
| `reset-prod.*` | `reset` / `prod reset` |
| `backup-acme.*` / `restore-acme.*` | `backup-acme` / `restore-acme` / `prod …` |
| `prune-docker-build.*` | `prod prune-build` |
| `setup-ubuntu.sh` | Prefer `rust-native-ctrl setup` from laptop |

`servers.json` points `start_cmd` / `stop_cmd` at these scripts.
