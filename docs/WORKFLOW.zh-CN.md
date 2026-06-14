# VJQ 宿主替换表盘流程

English summary: this toolkit renders a self-made GWS/Tizen watchface inside an already installed and selectable Tizen Web watchface host. Tizen Studio must be installed first. It was built collaboratively by Rinned and Codex (GPT-5.5).

这份文档只记录可复用的成功路线：不破解 Samsung/Galaxy Store 签名链，而是使用已经能在手表上切换的 Web 表盘 `VJQAyUfd52.watch02` 作为合法宿主，把自己的 GWS/Tizen 表盘资源转成 Canvas 渲染器并写入宿主本地存储。使用前需要先安装 Tizen Studio，并确保 `sdb.exe` 和 ARM 工具链可用。

## 前提

- Tizen Wearable 手表已开启调试。
- `sdb devices` 能看到手表处于 `device` 状态。
- 电脑已提前安装 Tizen Studio。
- Tizen Studio 的 `sdb.exe` 和 ARM 工具链可用。
- 手表上已经安装并可切换到 `VJQAyUfd52.watch02`。
- 目标表盘是你自己制作或有权使用的 `.tpk` 或解包目录。
- Python 已安装 Pillow。

```powershell
pip install -r requirements.txt
```

## 连接检查

```powershell
& 'C:\path\to\sdb.exe' devices
```

期望输出里能看到：

```text
<serial>    device
```

## 应用表盘

```powershell
powershell -ExecutionPolicy Bypass -File .\install-vjq-web-watchface.ps1 `
  -Python python `
  -Sdb 'C:\path\to\sdb.exe' `
  -Gcc 'C:\path\to\arm-linux-gnueabi-gcc.exe' `
  -Source 'C:\path\to\your_face.tpk' `
  -Apply `
  -Screenshot
```

`-Source` 可以是 `.tpk`，也可以是解包目录。解包目录内通常需要有：

```text
res/watchface.xml
res/*.png
```

如果宿主表盘没有刷新，或 LevelDB 写入时宿主仍被系统占用，可以传入另一块已经安装且能切换的表盘作为临时停靠位：

```powershell
  -ParkingPackageId 'com.example.otherface' `
  -ParkingAppId 'com.example.otherface'
```

## 验证

```powershell
powershell -ExecutionPolicy Bypass -File .\verify-vjq-web-watchface.ps1 `
  -Sdb 'C:\path\to\sdb.exe' `
  -Gcc 'C:\path\to\arm-linux-gnueabi-gcc.exe' `
  -CheckAssets `
  -CheckPayload `
  -Screenshot
```

如果要验证重启后仍然生效：

```powershell
powershell -ExecutionPolicy Bypass -File .\wait-watch-reboot-verify.ps1 `
  -Sdb 'C:\path\to\sdb.exe' `
  -ColdStartAfterReconnect
```

## 稳定参数模板

这是方形 UI / 圆角电量 arc 风格的参数模板。把 `-Source` 换成自己的表盘路径即可：

```powershell
powershell -ExecutionPolicy Bypass -File .\install-vjq-web-watchface.ps1 `
  -Python python `
  -Sdb 'C:\path\to\sdb.exe' `
  -Gcc 'C:\path\to\arm-linux-gnueabi-gcc.exe' `
  -Source 'C:\path\to\your_face.tpk' `
  -IndexColor '#756644' `
  -SquareUi `
  -SquareUiInset 24 `
  -SquareArcInset 36 `
  -SquareArcCornerRadius 30 `
  -SparkScale 1.35 `
  -HandScale 0.84 `
  -HandWidthScale 0.68 `
  -BatteryRadius 168 `
  -BatteryGlowScale 0.72 `
  -CardinalDimDeg 24 `
  -CardinalDimInnerRadius 150 `
  -CardinalDimFactor 0.12 `
  -LogicalCanvasSize 360 `
  -ViewportCanvasScale 1.0 `
  -WrapperTransformScale 1.0 `
  -CanvasTransformScale 1.0 `
  -CardinalGapDeg 0 `
  -FrameCardinalGapDeg 0 `
  -ParkingPackageId 'com.example.otherface' `
  -ParkingAppId 'com.example.otherface' `
  -Apply `
  -Screenshot
```

`-ParkingPackageId` / `-ParkingAppId` 不是固定值；请换成你手表上已有的任意另一块表盘。没有备用表盘时可以先不传。

## 换下一块表盘

1. 把新的 `.tpk` 或解包目录传给 `-Source`。
2. 先跑最小命令确认能显示。
3. 再调 `-HandScale`、`-HandWidthScale`、`-BatteryRadius`、`-SquareArcInset`、`-IndexColor` 等视觉参数。
4. 满意后运行 `verify-vjq-web-watchface.ps1 -CheckAssets -CheckPayload`。
5. 把最终命令保存到自己的项目文档或 `examples/`。

## 不要提交到公开仓库的东西

- Samsung 证书、账号信息、签名备份。
- 第三方表盘素材。
- 私人截图和临时日志。
- 已编译的临时 helper 二进制。
