# safe/ — keys, addresses, prod env (local only)

| Pattern | Purpose |
|---------|---------|
| `*-privatekey.pem` | SSH private key |
| `*-address.txt` | VM IP / hostname (first line) |
| `*-env.env` | Production secrets → uploaded as `~/projects/rust-native/.env` |

| Files | Server id |
|-------|-----------|
| `ar-rust-native-bamdad-*` | `rust-native` |

Copy the `*.example` stubs, drop the `.example` suffix, and fill real values.

`*.pem`, `*.env`, `*-address.txt` are gitignored.

Upload env to VM:

```bat
rust-native-ctrl.bat env
```

That copies `safe/ar-rust-native-bamdad-env.env` → `~/projects/rust-native/.env`.
