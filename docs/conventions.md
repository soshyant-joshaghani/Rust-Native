# Conventions

Product code goes in `apps/<name>/`. Platform code stays in `base/` and `system/`.

JSON fields are `snake_case`. HTTP paths stay under `/api/v1`. Errors are `{"detail": "..."}`. Database tables and columns are the ones in [CONTRACT.md](../../../../CONTRACT.md).

Do not add a frontend `components/` folder. Svelte UI lives in `frontend/src/lib/modules/base` and `frontend/src/lib/modules/apps`.
