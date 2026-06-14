# Security Notes

This project is intended for personal devices and watchfaces you created or have permission to use.

It does not provide Samsung distributor certificates and does not patch Samsung system binaries. The working route uses an already installed Web watchface host and writes renderer data into that host's writable storage.

Do not publish:

- Personal certificates or keystores.
- Samsung account data.
- Third-party watchface artwork.
- Device identifiers you do not want public.
- Compiled helper binaries produced during local experiments.

The helper sources in this repository are for applying and verifying the local WebView payload. Build and run them only on devices you own or are authorized to test.
