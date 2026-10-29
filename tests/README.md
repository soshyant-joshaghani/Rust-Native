# Tests

```bat
__ctrl__\rust-native-ctrl.bat test all
__ctrl__\rust-native-ctrl.bat test backend
__ctrl__\rust-native-ctrl.bat test frontend
```

`test backend` runs `cargo test` in `backend/`. Integration tests live in `tests/backend/*.rs`. `backend/Cargo.toml` points its `[[test]]` targets there, so the kit keeps the shared `tests/backend` folder.

`test frontend` runs `svelte-check` inside `frontend/web` when a kit is installed.
