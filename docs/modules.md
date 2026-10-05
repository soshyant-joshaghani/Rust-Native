# Modules

| Group | Role |
|-------|------|
| `apps/sample` | Canonical notes example |
| `base/auth`, `base/users` | Login, session, user records |
| `system` | Health and private dev routes |

Paths: `backend/src/modules/{apps,base,system}`, `backend/src/core`, and `backend/src/bin/{api,worker}.rs`.

```bat
__ctrl__\rust-native-ctrl.bat app create myfeature
```

Merge the generated router in `backend/src/modules/apps/mod.rs`. Then copy the depth of `sample` before adding rules.

1. Copy `backend/src/modules/apps/sample/` to `backend/src/modules/apps/<name>/` (router, service, repository, schemas).
2. Merge the new router in `backend/src/modules/apps/mod.rs`.
3. Add `backend/migrations/NNNN_<name>.sql` when tables change.
4. Add `frontend/src/lib/modules/apps/<name>/api.ts` and a route under `frontend/src/routes/(dashboard)/`.
5. Add tests in `tests/backend/`.
