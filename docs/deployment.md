# Deployment

```bat
__ctrl__\rust-native-ctrl.bat prod start
__ctrl__\rust-native-ctrl.bat prod stop
```

`prod start` builds `compose.yml` (backend, worker, frontend, Postgres, Redis, Traefik, Adminer). Set `DOMAIN` and the URLs in `compose.yml`, and replace the placeholder secrets in `.env`; outside `ENVIRONMENT=local` the API refuses to start with `SECRET_KEY` or `FIRST_SUPERUSER_PASSWORD` set to `changethis`.

Remote commands use `__ctrl__/servers.json` and the example files under `__ctrl__/safe/`. Real keys stay gitignored. The API applies migrations on start, so there is no separate prestart step.
