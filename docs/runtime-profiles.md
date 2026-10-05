# Runtime profiles

| Profile | Command | Redis | Worker |
|---------|---------|-------|--------|
| Full | `dev run all` | yes | yes |
| Slim | `dev run all --slim` | no | no |

Slim is a supported lightweight mode for CRUD and auth work. Production is always full.
