# Architecture and request flow

The executable path is deliberately small: `scripts/start_netease6.sh` starts the local API if port 3000 is not already listening, then starts mitmweb with `mitmproxy/netease6_final.py` as its only addon.

## Normal API requests

For NetEase Music hosts other than the legacy login endpoint, the addon:

1. Rewrites the outer `NeteaseMusic/<version>` user agent.
2. Replaces the outer cookie identity fields and adds a fresh `buildver`.
3. Adds only allow-listed authentication cookies from the local QR result.
4. For EAPI bodies, decrypts `params` with the protocol's fixed AES key.
5. Replaces the inner `header.appver`, `header.versioncode`, and `header.buildver`.
6. Recomputes the EAPI MD5 digest and encrypts the new request.

If an `/eapi/` path does not use the standard Android EAPI body shape, the addon logs the parsing error and lets the original request continue.

## Login bridge

The legacy `/eapi/login/cellphone` request is not forwarded with the password entered on the old device. Instead, the addon asks the local API for `/login/status` using the QR credential, builds the account/profile response expected by the old client, encrypts it with the EAPI response format, and adds allow-listed cookies as `Set-Cookie` headers.

The local QR acquisition flow may report code `803` when browser or phone authorization succeeds. The compatibility response sent to the legacy client uses API code `200` because that is the shape expected by the old native login handler.
