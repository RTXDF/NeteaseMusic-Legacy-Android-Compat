# Android 4 TLS and CA notes

Android 4.2 clients may offer TLS versions that modern proxy defaults reject. The launch script therefore passes:

```text
--set tls_version_client_min=TLS1
```

This weakens the minimum protocol accepted on the proxy's client-facing side. Do not expose the proxy port to the public internet. Restrict it to a trusted LAN or dedicated device network.

## Certificate setup

1. Start mitmweb once so it creates its local CA under the operator's mitmproxy profile.
2. On the legacy device, configure the Wi-Fi proxy to the host and port shown by the script.
3. Visit mitmproxy's certificate installation page through that proxy or transfer the public CA certificate through a trusted local path.
4. Install only the public CA certificate on the device. Never copy the CA private key to the device or repository.
5. Confirm the certificate fingerprint out of band before trusting it.

Some applications pin certificates or do not trust user-installed CAs. Do not disable unrelated platform security or install unknown certificates to work around that limitation.

## Cleanup

After testing, stop mitmweb, remove the Wi-Fi proxy setting, and remove the testing CA from devices that no longer need it. Revoke the NetEase session if traffic or credentials may have been exposed.
