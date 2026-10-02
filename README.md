[![](./FoxG-Kit.png)](./FoxG-Kit.png)

# Rust-Native

**A multi-client application foundation with a Rust backend.**

The API in `backend/` is the source of truth and follows the [FoxG wire contract](../../../CONTRACT.md). `web use svelte` installs the Rust-Svelte frontend into `frontend/web`. Android and Windows folders exist so the layout is ready; they are not implemented.

**Docs:** [AGENTS.md](AGENTS.md) · [ROADMAP.md](ROADMAP.md) · [docs/](docs/) · [plans](__plans__/PROGRESS.md) · [`__ctrl__`](__ctrl__/README.md)

```text
backend/               Rust API and worker (`backend/src/modules/{apps,base,system}`, `backend/src/core`, and `backend/src/bin/{api,worker}.rs`)
frontend/web           filled by web use svelte
frontend/android       reserved
frontend/windows       reserved
__ctrl__/kits.json     web catalog
__ctrl__/clients.json  client registry
```

```bat
__ctrl__\rust-native-ctrl.bat web list
__ctrl__\rust-native-ctrl.bat web use svelte
__ctrl__\rust-native-ctrl.bat setup-local
__ctrl__\rust-native-ctrl.bat dev run all
```

`web use svelte` copies the `frontend/` of the sibling [Rust-Svelte](../rust-svelte/README.md) into `frontend/web` (the `source` in `__ctrl__/kits.json`; remove `source` to download from GitHub instead) and pins it in a lock file. Run it before `setup-local`.

Scalar: http://api.localhost/sdoc · Swagger: http://api.localhost/docs · Superuser `admin@example.com` / `Admin@1234`.

Changing backend works as in every FoxG kit: keep `frontend/`, the module names, and the contract, then reimplement `backend/`. Index: [foxg-kit](../../../README.md).
