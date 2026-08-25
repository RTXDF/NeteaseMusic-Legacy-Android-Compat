# Configuration and credential handling

## Addon settings

The addon loads `config/config.json` when present. Set `NCM_COMPAT_CONFIG` to use another JSON file. Environment variables have highest precedence:

| Environment variable | JSON key | Tested default |
| --- | --- | --- |
| `NCM_QR_FILE` | `qr_file` | `~/ncm_qr_result.json` |
| `NCM_LOCAL_API` | `local_api` | `http://127.0.0.1:3000` |
| `NCM_APPVER` | `appver` | `8.20.20.231215173437` |
| `NCM_VERSIONCODE` | `versioncode` | `140` |

The launch script also accepts `NCM_API_HOST`, `NCM_API_PORT`, `NCM_PROXY_HOST`, `NCM_PROXY_PORT`, `NCM_LOG_DIR`, and `NCM_ADDON`.

If you change the local API port, update both `NCM_API_PORT` and `NCM_LOCAL_API`.

## Credential file

The real QR result must remain outside version control. It contains at least `code`, `message`, and `cookie`; the cookie is an active account session. Keep the file owner-readable only:

```bash
chmod 600 ~/ncm_qr_result.json
```

The addon accepts only `MUSIC_U`, `MUSIC_A`, `__csrf`, `NMTID`, `MUSIC_R_T`, and `MUSIC_R_I` from that file for request and response injection. It does not log cookie values.

Before committing, confirm that `git check-ignore` reports the real QR result, logs, mitmproxy profile, captures, certificates, and local config as ignored.
