# Testing

`test backend` runs `cargo test` in `backend/`.

Integration tests live in `tests/backend/*.rs`. `backend/Cargo.toml` points its `[[test]]` targets there, so the kit keeps the shared `tests/backend` folder.

The tests inject in-memory repositories, cache, and job queue, so they need neither Postgres nor Redis. They cover auth, the superuser routes, notes isolation and caching, and the local-only private routes.
