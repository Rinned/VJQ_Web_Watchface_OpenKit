# VJQ Web Watchface OpenKit

## Intro

Render a self-made GWS/Tizen watchface inside an already installed and selectable Tizen Web watchface host. Tizen Studio must be installed first because this toolkit uses its `sdb` and ARM toolchain.

This project was built for a practical problem: older Samsung/Tizen wearable devices can still run existing Web watchfaces, while the official store and signing paths may no longer be usable. Instead of bypassing Samsung package signing, this toolkit keeps a trusted Web watchface installed on the watch, then replaces its local Web storage payload with a Canvas renderer for your own watchface assets.

中文简介：这是一个面向旧款 Samsung/Tizen 手表的自制表盘替换工具包。使用前需要先安装 Tizen Studio，因为工具会用到其中的 `sdb` 和 ARM 工具链。它不破解官方签名链，而是复用手表上已经安装、已经能切换的 Web 表盘作为宿主，把自己的 GWS/Tizen 表盘资源转换成 Canvas 渲染器并写入宿主本地存储，从而实现稳定显示和后续复用。

Built collaboratively by Rinned and Codex (GPT-5.5). See [CREDITS.md](CREDITS.md).

Tested host:

```text
VJQAyUfd52.watch02
```

## Features

- Converts a `.tpk` or unpacked GWS/Tizen watchface directory into a Canvas renderer.
- Pushes renderer assets to the host app's writable `shared/data` directory.
- Injects the host WebView localStorage / LevelDB payload through a small debug helper.
- Provides verification scripts for remote asset hashes, payload persistence, cold start, reboot, and screenshots.
- Includes WebView rendering probes used to inspect artifact boundaries.

## Requirements

- Windows PowerShell.
- Python 3.
- Pillow (`pip install -r requirements.txt`).
- Tizen Studio installed before use.
- Tizen `sdb.exe` from Tizen Studio.
- Tizen ARM GCC / wearable toolchain for compiling the small helper probes.
- A Tizen wearable with debugging enabled.
- The Web watchface host already installed and selectable on the watch.

## Quick Start

```powershell
pip install -r requirements.txt

powershell -ExecutionPolicy Bypass -File .\install-vjq-web-watchface.ps1 `
  -Python python `
  -Sdb 'C:\path\to\sdb.exe' `
  -Gcc 'C:\path\to\arm-linux-gnueabi-gcc.exe' `
  -Source 'C:\path\to\your_face.tpk' `
  -Apply `
  -Screenshot
```

If the host watchface stays locked or does not refresh cleanly, pass another already installed watchface as a temporary parking face:

```powershell
  -ParkingPackageId 'com.example.otherface' `
  -ParkingAppId 'com.example.otherface'
```

Verify:

```powershell
powershell -ExecutionPolicy Bypass -File .\verify-vjq-web-watchface.ps1 `
  -Sdb 'C:\path\to\sdb.exe' `
  -Gcc 'C:\path\to\arm-linux-gnueabi-gcc.exe' `
  -CheckAssets `
  -CheckPayload `
  -Screenshot
```

Switch back to the host if needed:

```powershell
powershell -ExecutionPolicy Bypass -File .\switch-installed-watchface.ps1 `
  -Sdb 'C:\path\to\sdb.exe' `
  -PackageId VJQAyUfd52 `
  -AppId VJQAyUfd52.watch02 `
  -Screenshot
```

## Documentation

- [Chinese workflow](docs/WORKFLOW.zh-CN.md)
- [Security notes](docs/SECURITY_NOTES.md)
- [Example square style command](examples/apply-square-style.ps1)
- [Credits](CREDITS.md)

## Repository Contents

- `vjq_web_watchface_installer.py` builds and applies the Canvas shell.
- `install-vjq-web-watchface.ps1` is the main PowerShell wrapper.
- `verify-vjq-web-watchface.ps1` verifies remote assets and injected payloads.
- `switch-installed-watchface.ps1` switches to an installed watchface.
- `wait-watch-reboot-verify.ps1` waits after reboot and verifies persistence.
- `fake_gdbserver_webhost_leveldb_apply.c` and `fake_gdbserver_webhost_leveldb_dump.c` are the required helper sources.
- `probes/` contains optional WebView/rendering boundary probe pages.
- `corner_overlays/` documents optional local overlay assets, but does not ship private artwork.

## Scope

This toolkit is for your own devices and watchfaces you created or have permission to use. It is not a Samsung signing bypass and does not include Samsung certificates, third-party assets, private screenshots, or compiled helper binaries.

## License

MIT. See [LICENSE](LICENSE).
