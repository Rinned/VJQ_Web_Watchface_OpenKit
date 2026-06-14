#!/usr/bin/env python3
"""
Build and optionally apply a VJQ web-watchface shell for simple GWS/XML faces.

This does not install the target TPK as a Tizen package. It uses the already
installed VJQAyUfd52.watch02 web watchface as a switchable host, then injects a
localStorage payload that renders the target watchface assets from VJQ's
user-writable shared/data directory.
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image


ROOT = Path(__file__).resolve().parent

DEFAULT_SDB = Path(os.environ.get("TIZEN_SDB", r"F:\Tizen\tools\sdb.exe"))
DEFAULT_GCC = Path(os.environ.get("TIZEN_GCC", r"F:\Tizen\tools\arm-linux-gnueabi-gcc-9.2\bin\arm-linux-gnueabi-gcc.exe"))

VJQ_PKG = "VJQAyUfd52"
VJQ_APP = "VJQAyUfd52.watch02"

REMOTE_ASSET_DIR = "/home/owner/apps_rw/VJQAyUfd52/shared/data/r"
REMOTE_PAYLOAD = "/home/owner/share/tmp/codex_vjq_000003_texture0.log"
REMOTE_GDBSERVER = "/opt/usr/home/owner/share/tmp/sdk_tools/gdbserver/gdbserver"

ORIGINS = [
    "file://",
    "file:///opt/usr/globalapps/VJQAyUfd52/res/wgt/index.html",
    "file:///opt/usr/globalapps/VJQAyUfd52/res/wgt/",
    "http://yourdomain",
    "http://yourdomain/",
    "http://yourdomain/watch02",
    "app://VJQAyUfd52.watch02",
    "tizen://VJQAyUfd52.watch02",
    "widget://VJQAyUfd52.watch02",
]

FRAME_OVERLAY_NAME = "frame_overlay.png"
INDEX_REPLACEMENT_NAME = "index_replacement.png"
SQUARE_INDEX_NAME = "square_index.png"
CORNER_OVERLAY_NAMES = ("corner_tl.png", "corner_tr.png", "corner_bl.png", "corner_br.png")


def run(cmd: list[str] | str, *, check: bool = True, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    print("+", cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd))
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        shell=isinstance(cmd, str),
        cwd=str(cwd) if cwd else None,
    )


def unpack_source(source: Path, work_dir: Path) -> Path:
    source = source.resolve()
    if source.is_dir():
        return source

    if source.suffix.lower() != ".tpk":
        raise SystemExit(f"Unsupported source: {source}")

    out = work_dir / f"unpacked_{source.stem}"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    with zipfile.ZipFile(source) as zf:
        zf.extractall(out)
    return out


def parse_parts(unpacked: Path) -> list[dict[str, object]]:
    xml_path = unpacked / "res" / "watchface.xml"
    root = ET.parse(xml_path).getroot()
    parts: list[dict[str, object]] = []
    for idx, part in enumerate(root.findall(".//part")):
        image = part.find("image")
        if image is None or not image.text:
            continue
        rot = part.find("rotation")
        color = part.find("color")
        opacity = 1.0
        if color is not None and color.attrib.get("a") is not None:
            try:
                opacity = max(0.0, min(1.0, float(color.attrib["a"]) / 255.0))
            except ValueError:
                opacity = 1.0
        parts.append(
            {
                "idx": idx,
                "image": image.text.strip(),
                "x": int(float(part.attrib.get("x", "0"))),
                "y": int(float(part.attrib.get("y", "0"))),
                "w": int(float(part.attrib.get("width", "0"))),
                "h": int(float(part.attrib.get("height", "0"))),
                "rotation": dict(rot.attrib) if rot is not None else None,
                "opacity": opacity,
            }
        )
    return parts


def safe_asset_name(index: int, original: str) -> str:
    suffix = Path(original).suffix.lower() or ".png"
    return f"p{index:02d}{suffix}"


def zero_transparent_rgb(im: Image.Image) -> Image.Image:
    im = im.convert("RGBA")
    pix = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pix[x, y]
            if a == 0 and (r or g or b):
                pix[x, y] = (0, 0, 0, 0)
    return im


def hard_edge_crop(im: Image.Image, radius: int) -> Image.Image:
    im = im.convert("RGBA")
    pix = im.load()
    cx = (im.width - 1) / 2
    cy = (im.height - 1) / 2
    r2 = float(radius * radius)
    for y in range(im.height):
        for x in range(im.width):
            dx = x - cx
            dy = y - cy
            if dx * dx + dy * dy > r2:
                pix[x, y] = (0, 0, 0, 0)
    return im


def threshold_alpha(im: Image.Image, threshold: int) -> Image.Image:
    if threshold <= 0:
        return im
    im = im.convert("RGBA")
    pix = im.load()
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pix[x, y]
            if a < threshold:
                pix[x, y] = (0, 0, 0, 0)
    return im


def matte_low_alpha_to_black(im: Image.Image, max_alpha: int) -> Image.Image:
    if max_alpha <= 0:
        return im
    im = im.convert("RGBA")
    pix = im.load()
    max_alpha = max(0, min(255, max_alpha))
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pix[x, y]
            if 0 < a < max_alpha:
                t = a / 255.0
                pix[x, y] = (round(r * t), round(g * t), round(b * t), a)
    return im


def parse_hex_color(value: str | None) -> tuple[int, int, int] | None:
    if not value:
        return None
    text = value.strip()
    if text.startswith("#"):
        text = text[1:]
    if len(text) != 6:
        raise ValueError(f"expected 6-digit RGB color, got {value!r}")
    try:
        return tuple(int(text[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise ValueError(f"expected 6-digit RGB color, got {value!r}") from exc


def force_visible_pixels_to_color(im: Image.Image, color: tuple[int, int, int]) -> Image.Image:
    im = im.convert("RGBA")
    pix = im.load()
    r, g, b = color
    for y in range(im.height):
        for x in range(im.width):
            _old_r, _old_g, _old_b, a = pix[x, y]
            if a == 0:
                pix[x, y] = (0, 0, 0, 0)
            else:
                pix[x, y] = (r, g, b, a)
    return im


def clear_cardinal_wedges(im: Image.Image, gap_deg: float, inner_radius: float) -> Image.Image:
    if gap_deg <= 0:
        return im
    im = im.convert("RGBA")
    pix = im.load()
    cx = (im.width - 1) / 2
    cy = (im.height - 1) / 2
    gap_deg = max(0.0, min(20.0, gap_deg))
    inner_radius = max(0.0, inner_radius)
    cardinals = (0.0, 90.0, 180.0, 270.0)
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pix[x, y]
            if a == 0:
                continue
            dx = x - cx
            dy = y - cy
            radius = (dx * dx + dy * dy) ** 0.5
            if radius < inner_radius:
                continue
            deg = (math.degrees(math.atan2(dy, dx)) + 450.0) % 360.0
            if any(min(abs(deg - c), 360.0 - abs(deg - c)) <= gap_deg for c in cardinals):
                pix[x, y] = (0, 0, 0, 0)
    return im


def dim_cardinal_wedges(
    im: Image.Image,
    dim_deg: float,
    inner_radius: float,
    min_alpha_factor: float,
) -> Image.Image:
    if dim_deg <= 0:
        return im
    im = im.convert("RGBA")
    pix = im.load()
    cx = (im.width - 1) / 2
    cy = (im.height - 1) / 2
    dim_deg = max(0.0, min(30.0, dim_deg))
    inner_radius = max(0.0, inner_radius)
    min_alpha_factor = max(0.0, min(1.0, min_alpha_factor))
    outer_span = max(1.0, min(im.width, im.height) / 2 - inner_radius)
    cardinals = (0.0, 90.0, 180.0, 270.0)
    for y in range(im.height):
        for x in range(im.width):
            r, g, b, a = pix[x, y]
            if a == 0:
                continue
            dx = x - cx
            dy = y - cy
            radius = math.hypot(dx, dy)
            if radius < inner_radius:
                continue
            deg = (math.degrees(math.atan2(dy, dx)) + 450.0) % 360.0
            d = min(min(abs(deg - c), 360.0 - abs(deg - c)) for c in cardinals)
            if d > dim_deg:
                continue
            angle_strength = 1.0 - (d / dim_deg)
            radius_strength = min(1.0, (radius - inner_radius) / outer_span)
            strength = angle_strength * radius_strength
            factor = 1.0 - strength * (1.0 - min_alpha_factor)
            pix[x, y] = (r, g, b, int(a * factor))
    return im


def build_assets(
    unpacked: Path,
    parts: list[dict[str, object]],
    build_dir: Path,
    corner_dir: Path,
    hard_edge_radius: int,
    alpha_threshold: int,
    black_matte_alpha: int,
    opaque_hands: bool,
    index_color: tuple[int, int, int] | None,
    cardinal_gap_deg: float,
    cardinal_gap_inner_radius: float,
    cardinal_dim_deg: float,
    cardinal_dim_inner_radius: float,
    cardinal_dim_factor: float,
    frame_cardinal_gap_deg: float,
    frame_cardinal_gap_inner_radius: float,
) -> list[dict[str, object]]:
    asset_dir = build_dir / "assets"
    if asset_dir.exists():
        shutil.rmtree(asset_dir)
    asset_dir.mkdir(parents=True)
    index_replacement = corner_dir / INDEX_REPLACEMENT_NAME

    rendered: list[dict[str, object]] = []
    for item in parts:
        original = str(item["image"])
        src = unpacked / "res" / original
        if not src.exists():
            src = unpacked / original
        if not src.exists():
            print(f"warning: missing image asset {original}", file=sys.stderr)
            continue

        w = int(item["w"])
        h = int(item["h"])
        out_name = safe_asset_name(int(item["idx"]), original)
        dst = asset_dir / out_name
        is_full_index = (
            hard_edge_radius > 0
            and not item.get("rotation")
            and w == 360
            and h == 360
            and "index" in original.lower()
        )
        replacement_used = is_full_index and index_replacement.exists()
        im = Image.open(index_replacement if replacement_used else src).convert("RGBA")
        if w > 0 and h > 0:
            im = im.resize((w, h), Image.Resampling.LANCZOS)
        im = zero_transparent_rgb(im)

        hard_edge = False
        if is_full_index:
            if not replacement_used:
                im = hard_edge_crop(im, hard_edge_radius)
            hard_edge = True
        im = matte_low_alpha_to_black(im, black_matte_alpha)
        im = threshold_alpha(im, alpha_threshold)
        if index_color and hard_edge and not replacement_used:
            im = force_visible_pixels_to_color(im, index_color)
        if hard_edge and cardinal_gap_deg > 0:
            im = clear_cardinal_wedges(im, cardinal_gap_deg, cardinal_gap_inner_radius)
        if hard_edge and cardinal_dim_deg > 0:
            im = dim_cardinal_wedges(
                im,
                cardinal_dim_deg,
                cardinal_dim_inner_radius,
                cardinal_dim_factor,
            )
        im.save(dst)

        entry = dict(item)
        entry["asset"] = out_name
        entry["hard_edge"] = hard_edge
        if opaque_hands and entry.get("rotation"):
            entry["opacity"] = 1.0
        rendered.append(entry)

    fonts = unpacked / "res" / "fonts"
    tinker = fonts / "WatchTinkerbell.ttf"
    breeze = fonts / "WatchBreezeSans-Light.ttf"
    if tinker.exists():
        shutil.copy2(tinker, asset_dir / "tinker.ttf")
    if breeze.exists():
        shutil.copy2(breeze, asset_dir / "breeze.ttf")

    if corner_dir.exists():
        custom_index = corner_dir / INDEX_REPLACEMENT_NAME
        if custom_index.exists():
            Image.open(custom_index).convert("RGBA").save(asset_dir / INDEX_REPLACEMENT_NAME)
        square_index = corner_dir / SQUARE_INDEX_NAME
        if square_index.exists():
            Image.open(square_index).convert("RGBA").save(asset_dir / SQUARE_INDEX_NAME)
        full_frame = corner_dir / FRAME_OVERLAY_NAME
        if full_frame.exists():
            frame_im = Image.open(full_frame).convert("RGBA")
            if frame_cardinal_gap_deg > 0:
                frame_im = clear_cardinal_wedges(
                    frame_im,
                    frame_cardinal_gap_deg,
                    frame_cardinal_gap_inner_radius,
                )
            frame_im.save(asset_dir / FRAME_OVERLAY_NAME)
        for name in CORNER_OVERLAY_NAMES:
            src = corner_dir / name
            if not src.exists():
                continue
            dst = asset_dir / name
            Image.open(src).convert("RGBA").save(dst)

    return rendered


def build_canvas_shell(
    parts: list[dict[str, object]],
    asset_dir: Path,
    image_scale: float,
    outer_ui_scale: float,
    hand_scale: float,
    hand_width_scale: float,
    composition_safe_scale: float,
    logical_canvas_size: int,
    viewport_canvas_scale: float,
    wrapper_transform_scale: float,
    canvas_transform_scale: float,
    scene_scale: float,
    layer_visibility: dict[str, bool],
    battery_radius: float,
    battery_glow_scale: float,
    edge_blackout: dict[str, int],
    shell_edge_mask: dict[str, int],
    outer_blank_ring_radius: int,
    outer_blank_ring_padding: int,
    battery_label: bool,
    cardinal_gap_deg: float,
    square_ui: bool,
    square_ui_inset: float,
    square_arc_inset: float,
    square_arc_corner_radius: float,
    spark_scale: float,
) -> Path:
    canvas_parts: list[dict[str, object]] = []
    for index, part in enumerate(parts):
        item: dict[str, object] = {
            "asset": part["asset"],
            "x": part["x"],
            "y": part["y"],
            "w": part["w"],
            "h": part["h"],
            "opacity": part.get("opacity", 1.0),
            "hardEdge": bool(part.get("hard_edge")),
            "layer": "index" if index == 0 else ("art" if index == 1 else "hands"),
        }
        rot = part.get("rotation")
        if rot:
            r = rot  # type: ignore[assignment]
            item["rotation"] = {
                "source": r.get("source", ""),
                "startAngle": float(r.get("start_angle", "0")),
                "endAngle": float(r.get("end_angle", "0")),
                "startValue": float(r.get("start_value", "0")),
                "endValue": float(r.get("end_value", "1")),
                "centerX": float(r.get("center_x", float(part["w"]) / 2)),
                "centerY": float(r.get("center_y", float(part["h"]) / 2)),
            }
        canvas_parts.append(item)

    data = json.dumps(canvas_parts, separators=(",", ":"))
    frame_overlays = [{"asset": FRAME_OVERLAY_NAME}] if (asset_dir / FRAME_OVERLAY_NAME).exists() else []
    square_index_asset = SQUARE_INDEX_NAME if (asset_dir / SQUARE_INDEX_NAME).exists() else ""
    corner_overlays = [
        item
        for item in (
            {"asset": "corner_tl.png", "x": "left", "y": "top"},
            {"asset": "corner_tr.png", "x": "right", "y": "top"},
            {"asset": "corner_bl.png", "x": "left", "y": "bottom"},
            {"asset": "corner_br.png", "x": "right", "y": "bottom"},
        )
        if (asset_dir / str(item["asset"])).exists()
    ]
    frame_overlays_json = json.dumps(frame_overlays, separators=(",", ":"))
    square_index_asset_json = json.dumps(square_index_asset)
    corner_overlays_json = json.dumps(corner_overlays, separators=(",", ":"))
    image_scale = max(0.5, min(1.0, image_scale))
    outer_ui_scale = max(1.0, min(1.06, outer_ui_scale))
    hand_scale = max(0.75, min(1.08, hand_scale))
    hand_width_scale = max(0.45, min(1.15, hand_width_scale))
    composition_safe_scale = max(0.75, min(1.0, composition_safe_scale))
    logical_canvas_size = max(300, min(360, int(logical_canvas_size)))
    coord_scale = logical_canvas_size / 360.0
    viewport_canvas_scale = max(1.0, min(1.35, viewport_canvas_scale))
    wrapper_transform_scale = max(1.0, min(1.35, wrapper_transform_scale))
    canvas_transform_scale = max(1.0, min(1.35, canvas_transform_scale))
    scene_scale = max(0.65, min(1.0, scene_scale))
    battery_radius = max(150.0, min(179.0, battery_radius))
    battery_glow_scale = max(0.0, min(1.5, battery_glow_scale))
    canvas_css_size = logical_canvas_size * viewport_canvas_scale
    canvas_css_margin = canvas_css_size / -2
    edge_blackout = {k: max(0, min(40, int(v))) for k, v in edge_blackout.items()}
    shell_edge_mask = {k: max(0, min(80, int(v))) for k, v in shell_edge_mask.items()}
    edge_blackout_json = json.dumps(edge_blackout, separators=(",", ":"))
    shell_edge_mask_json = json.dumps(shell_edge_mask, separators=(",", ":"))
    layer_visibility_json = json.dumps(layer_visibility, separators=(",", ":"))
    square_ui_js = str(square_ui).lower()
    square_ui_inset = max(12.0, min(42.0, float(square_ui_inset)))
    square_arc_inset = max(8.0, min(42.0, float(square_arc_inset)))
    square_arc_corner_radius = max(0.0, min(64.0, float(square_arc_corner_radius)))
    spark_scale = max(0.5, min(2.2, float(spark_scale)))
    outer_blank_ring_radius = max(0, min(180, outer_blank_ring_radius))
    outer_blank_ring_padding = max(0, min(8, outer_blank_ring_padding))
    cardinal_gap_deg = max(0.0, min(20.0, cardinal_gap_deg))
    doc = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width={logical_canvas_size},user-scalable=no">
  <style>
    @font-face {{ font-family: Tink; src: url("tinker.ttf"); }}
    @font-face {{ font-family: Breeze; src: url("breeze.ttf"); }}
    html, body {{
      margin: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #000;
    }}
    #surface {{
      position: fixed;
      left: 50%;
      top: 50%;
      width: {canvas_css_size:.6f}px;
      height: {canvas_css_size:.6f}px;
      margin-left: {canvas_css_margin:.6f}px;
      margin-top: {canvas_css_margin:.6f}px;
      background: #000;
      overflow: hidden;
      transform: scale({wrapper_transform_scale:.6f});
      transform-origin: center center;
    }}
    canvas {{
      width: 100%;
      height: 100%;
      display: block;
      background: #000;
      transform: scale({canvas_transform_scale:.6f});
      transform-origin: center center;
    }}
  </style>
</head>
<body>
  <div id="surface"><canvas id="face" width="{logical_canvas_size}" height="{logical_canvas_size}"></canvas></div>
  <script>
    (function () {{
      var parts = {data};
      var imageScale = {image_scale:.6f};
      var outerUiScale = {outer_ui_scale:.6f};
      var handScale = {hand_scale:.6f};
      var handWidthScale = {hand_width_scale:.6f};
      var compositionSafeScale = {composition_safe_scale:.6f};
      var coordScale = {coord_scale:.8f};
      var sceneScale = {scene_scale:.6f};
      var batteryRadius = {battery_radius:.6f};
      var batteryGlowScale = {battery_glow_scale:.6f};
      var edgeBlackout = {edge_blackout_json};
      var shellEdgeMask = {shell_edge_mask_json};
      var layerVisibility = {layer_visibility_json};
      var outerBlankRingRadius = {outer_blank_ring_radius};
      var outerBlankRingPadding = {outer_blank_ring_padding};
      var cardinalGapDeg = {cardinal_gap_deg:.6f};
      var squareUi = {square_ui_js};
      var squareUiInset = {square_ui_inset:.6f};
      var squareArcInset = {square_arc_inset:.6f};
      var squareArcCornerRadius = {square_arc_corner_radius:.6f};
      var sparkScale = {spark_scale:.6f};
      var showBatteryLabel = {str(battery_label).lower()};
      var frameOverlays = {frame_overlays_json};
      var squareIndexAsset = {square_index_asset_json};
      var cornerOverlays = {corner_overlays_json};
      var c = document.getElementById("face");
      var ctx = c.getContext("2d");
      var composeCanvas = document.createElement("canvas");
      composeCanvas.width = 360;
      composeCanvas.height = 360;
      var composeCtx = composeCanvas.getContext("2d");
      var ringCanvas = document.createElement("canvas");
      ringCanvas.width = 360;
      ringCanvas.height = 360;
      var ringCtx = ringCanvas.getContext("2d");
      var batteryArcCanvas = document.createElement("canvas");
      batteryArcCanvas.width = 360;
      batteryArcCanvas.height = 360;
      var batteryArcCtx = batteryArcCanvas.getContext("2d");
      var battery = null;
      var batteryTimer = null;
      var batteryArcDirty = true;
      var imgs = {{}};
      function load(name) {{
        return new Promise(function (resolve) {{
          var im = new Image();
          im.onload = function () {{ imgs[name] = im; resolve(); }};
          im.onerror = resolve;
          im.src = name;
        }});
      }}
      function pad(n) {{ return (n < 10 ? "0" : "") + n; }}
      function mix(a, b, t) {{ return Math.round(a + (b - a) * t); }}
      function clamp01(v) {{ return Math.max(0, Math.min(1, v)); }}
      function arcColor(t, alpha) {{
        t = clamp01(t);
        var r, g, b, u;
        if (t < .35) {{
          u = t / .35;
          r = mix(136, 190, u);
          g = mix(64, 136, u);
          b = mix(22, 34, u);
        }} else {{
          u = (t - .35) / .65;
          r = mix(190, 74, u);
          g = mix(136, 246, u);
          b = mix(34, 46, u);
        }}
        return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
      }}
      function sparkColor(t, alpha) {{
        t = clamp01(t);
        var r, g, b, u;
        if (t < .35) {{
          u = t / .35;
          r = mix(178, 230, u);
          g = mix(82, 168, u);
          b = mix(22, 36, u);
        }} else {{
          u = (t - .35) / .65;
          r = mix(230, 122, u);
          g = mix(168, 255, u);
          b = mix(36, 54, u);
        }}
        return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
      }}
      function setBatteryValue(value) {{
        var n = parseFloat(value);
        if (!isFinite(n)) return;
        if (n >= 0 && n <= 1) n = n * 100;
        n = Math.max(0, Math.min(100, Math.round(n)));
        if (battery === n) return;
        battery = n;
        batteryArcDirty = true;
        if (isVisible()) draw();
      }}
      function isVisible() {{
        return document.hidden !== true && document.visibilityState !== "hidden";
      }}
      function readBatteryFile(path) {{
        try {{
          var xhr = new XMLHttpRequest();
          xhr.onreadystatechange = function () {{
            if (xhr.readyState === 4 && (xhr.status === 0 || xhr.status === 200)) setBatteryValue(xhr.responseText);
          }};
          xhr.open("GET", path, true);
          xhr.send(null);
        }} catch (e) {{}}
      }}
      function updateBattery() {{
        if (!isVisible()) return;
        try {{
          if (window.tizen && tizen.systeminfo) {{
            tizen.systeminfo.getPropertyValue("BATTERY", function (x) {{
              if (x && x.level != null) setBatteryValue(x.level);
            }});
          }}
        }} catch (e) {{}}
        readBatteryFile("../../../../../../../sys/class/power_supply/battery/capacity");
        readBatteryFile("file:///sys/class/power_supply/battery/capacity");
      }}
      function watchBattery() {{
        try {{
          if (window.tizen && tizen.systeminfo && tizen.systeminfo.addPropertyValueChangeListener) {{
            tizen.systeminfo.addPropertyValueChangeListener("BATTERY", function (x) {{
              if (isVisible() && x && x.level != null) setBatteryValue(x.level);
            }}, {{ lowThreshold: 0, highThreshold: 1 }});
          }}
        }} catch (e) {{}}
      }}
      function startBatteryPolling() {{
        if (batteryTimer !== null || !isVisible()) return;
        updateBattery();
        batteryTimer = setInterval(updateBattery, 5000);
      }}
      function stopBatteryPolling() {{
        if (batteryTimer !== null) {{
          clearInterval(batteryTimer);
          batteryTimer = null;
        }}
      }}
      function syncBatteryPolling() {{
        if (isVisible()) startBatteryPolling();
        else stopBatteryPolling();
      }}
      function angle(part, t) {{
        var r = part.rotation;
        if (!r) return 0;
        var value = 0;
        if (r.source === "hour0-23.minute") value = t.getHours() + t.getMinutes() / 60 + t.getSeconds() / 3600;
        else if (r.source === "minute.second") value = t.getMinutes() + t.getSeconds() / 60;
        else if (r.source === "second") value = t.getSeconds();
        var range = r.endValue - r.startValue;
        if (!range) range = 1;
        return r.startAngle + ((value - r.startValue) / range) * (r.endAngle - r.startAngle);
      }}
      function drawPartOn(target, part, t, dx, dy, forceOpacity) {{
        if (part.layer && layerVisibility[part.layer] === false) return;
        var im = imgs[part.asset];
        if (!im) return;
        var uiScale = part.rotation ? handScale : (part.hardEdge ? outerUiScale : 1);
        target.save();
        target.globalAlpha = forceOpacity == null ? (part.opacity == null ? 1 : part.opacity) : forceOpacity;
        target.imageSmoothingEnabled = !part.hardEdge;
        dx = dx || 0;
        dy = dy || 0;
        if (part.rotation) {{
          target.translate(part.x + part.rotation.centerX + dx, part.y + part.rotation.centerY + dy);
          target.rotate(angle(part, t) * Math.PI / 180);
          if (uiScale !== 1 || handWidthScale !== 1) target.scale(uiScale * handWidthScale, uiScale);
          target.drawImage(im, -part.rotation.centerX, -part.rotation.centerY, part.w, part.h);
        }} else {{
          if (uiScale !== 1) {{
            target.translate(180 + dx, 180 + dy);
            target.scale(uiScale, uiScale);
            target.drawImage(im, part.x - 180, part.y - 180, part.w, part.h);
          }} else {{
            target.drawImage(im, part.x + dx, part.y + dy, part.w, part.h);
          }}
        }}
        target.restore();
      }}
      function drawPart(part, t) {{
        drawPartOn(ctx, part, t, 0, 0, null);
      }}
      function drawText(text, y, font, color, scaleX, scaleY, shadow) {{
        scaleX = scaleX || 1;
        scaleY = scaleY || 1;
        shadow = shadow !== false;
        ctx.save();
        ctx.font = font;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = color;
        if (shadow) {{
          ctx.shadowColor = "#000";
          ctx.shadowBlur = 5;
          ctx.shadowOffsetY = 1;
        }}
        if (scaleX !== 1 || scaleY !== 1) {{
          ctx.translate(180, y);
          ctx.scale(scaleX, scaleY);
          ctx.fillText(text, 0, 0);
        }} else {{
          ctx.fillText(text, 180, y);
        }}
        ctx.restore();
      }}
      function ringPoint(deg, radius) {{
        var rad = (deg - 90) * Math.PI / 180;
        return [180 + Math.cos(rad) * radius, 180 + Math.sin(rad) * radius];
      }}
      function squarePointAt(unit, inset) {{
        var side = 360 - inset * 2;
        var d = ((((unit % 1) + 1) % 1) * side * 4);
        if (d < side / 2) return {{x: 180 + d, y: inset, nx: 0, ny: 1}};
        if (d < side * 1.5) return {{x: 360 - inset, y: inset + d - side / 2, nx: -1, ny: 0}};
        if (d < side * 2.5) return {{x: 360 - inset - (d - side * 1.5), y: 360 - inset, nx: 0, ny: -1}};
        if (d < side * 3.5) return {{x: inset, y: 360 - inset - (d - side * 2.5), nx: 1, ny: 0}};
        return {{x: inset + d - side * 3.5, y: inset, nx: 0, ny: 1}};
      }}
      function squarePoint(unit) {{
        return squarePointAt(unit, squareUiInset);
      }}
      function squareArcPoint(unit) {{
        if (squareArcCornerRadius <= 0) return squarePointAt(unit, squareArcInset);
        var inset = squareArcInset;
        var r = Math.min(squareArcCornerRadius, Math.max(0, 180 - inset));
        var left = inset, top = inset, right = 360 - inset, bottom = 360 - inset;
        var straight = Math.max(1, (right - left) - 2 * r);
        var arcLen = Math.PI * r / 2;
        var per = straight * 4 + arcLen * 4;
        var d = ((((unit % 1) + 1) % 1) * per) % per;
        function line(x0, y0, vx, vy, nx, ny, len, next) {{
          if (d <= len) return {{x: x0 + vx * d, y: y0 + vy * d, nx: nx, ny: ny}};
          d -= len;
          return next();
        }}
        function arc(cx, cy, start, end, next) {{
          if (d <= arcLen) {{
            var a = start + (end - start) * (d / Math.max(1, arcLen));
            var x = cx + Math.cos(a) * r;
            var y = cy + Math.sin(a) * r;
            var nx = cx - x;
            var ny = cy - y;
            var m = Math.max(.001, Math.hypot(nx, ny));
            return {{x:x, y:y, nx:nx/m, ny:ny/m}};
          }}
          d -= arcLen;
          return next();
        }}
        return line(180, top, 1, 0, 0, 1, straight / 2, function() {{
          return arc(right - r, top + r, -Math.PI / 2, 0, function() {{
            return line(right, top + r, 0, 1, -1, 0, straight, function() {{
              return arc(right - r, bottom - r, 0, Math.PI / 2, function() {{
                return line(right - r, bottom, -1, 0, 0, -1, straight, function() {{
                  return arc(left + r, bottom - r, Math.PI / 2, Math.PI, function() {{
                    return line(left, bottom - r, 0, -1, 1, 0, straight, function() {{
                      return arc(left + r, top + r, Math.PI, Math.PI * 1.5, function() {{
                        return line(left + r, top, 1, 0, 0, 1, straight / 2, function() {{
                          return {{x:180, y:top, nx:0, ny:1}};
                        }});
                      }});
                    }});
                  }});
                }});
              }});
            }});
          }});
        }});
      }}
      function strokeSquareSegment(target, fromUnit, toUnit, width, style, steps) {{
        if (toUnit <= fromUnit) return;
        steps = steps || Math.max(2, Math.ceil((toUnit - fromUnit) * 240));
        target.beginPath();
        for (var i = 0; i <= steps; i++) {{
          var p = squareArcPoint(fromUnit + (toUnit - fromUnit) * i / steps);
          if (i === 0) target.moveTo(p.x, p.y);
          else target.lineTo(p.x, p.y);
        }}
        target.strokeStyle = style;
        target.lineWidth = width;
        target.stroke();
      }}
      function drawSquareIndex() {{
        if (!squareUi) return;
        if (layerVisibility.index === false) return;
        if (squareIndexAsset && imgs[squareIndexAsset]) {{
          ctx.drawImage(imgs[squareIndexAsset], 0, 0, 360, 360);
          return;
        }}
        ctx.save();
        ctx.lineCap = "butt";
        ctx.lineJoin = "miter";
        ctx.strokeStyle = "rgba(117,102,68,.72)";
        ctx.lineWidth = 1.1;
        strokeSquareSegment(ctx, 0, 1, 1.1, "rgba(117,102,68,.72)", 240);
        for (var i = 0; i < 60; i++) {{
          var major = i % 5 === 0;
          var cardinal = i % 15 === 0;
          var p = squarePoint(i / 60);
          var len = cardinal ? 25 : (major ? 16 : 9);
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(p.x + p.nx * len, p.y + p.ny * len);
          ctx.strokeStyle = cardinal ? "rgba(244,187,64,.96)" : (major ? "rgba(218,159,44,.9)" : "rgba(213,151,40,.76)");
          ctx.lineWidth = cardinal ? 2.3 : (major ? 1.8 : 1.2);
          ctx.stroke();
        }}
        ctx.font = "22px Tink, serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillStyle = "rgba(232,178,67,.95)";
        ctx.shadowColor = "rgba(0,0,0,.9)";
        ctx.shadowBlur = 4;
        var labels = [60,5,10,15,20,25,30,35,40,45,50,55];
        for (var j = 0; j < labels.length; j++) {{
          var q = squarePoint((j * 5) / 60);
          var off = (j % 3 === 0) ? 37 : 31;
          ctx.fillText(String(labels[j]), q.x + q.nx * off, q.y + q.ny * off);
        }}
        ctx.restore();
      }}
      function inCardinalGap(deg) {{
        if (!cardinalGapDeg) return false;
        deg = ((deg % 360) + 360) % 360;
        var cardinals = [0, 90, 180, 270];
        for (var i = 0; i < cardinals.length; i++) {{
          var d = Math.abs(deg - cardinals[i]);
          d = Math.min(d, 360 - d);
          if (d <= cardinalGapDeg) return true;
        }}
        return false;
      }}
      function strokeRingSegment(target, fromDeg, toDeg, radius, width, style, steps) {{
        if (toDeg <= fromDeg) return;
        steps = steps || Math.max(2, Math.ceil((toDeg - fromDeg) / 4));
        target.beginPath();
        var drawing = false;
        for (var i = 0; i <= steps; i++) {{
          var deg = fromDeg + (toDeg - fromDeg) * i / steps;
          if (inCardinalGap(deg)) {{
            drawing = false;
            continue;
          }}
          var p = ringPoint(deg, radius);
          if (!drawing) {{
            target.moveTo(p[0], p[1]);
            drawing = true;
          }}
          else target.lineTo(p[0], p[1]);
        }}
        target.strokeStyle = style;
        target.lineWidth = width;
        target.stroke();
      }}
      function drawBatteryAura(target) {{
        if (batteryGlowScale <= 0) return;
        target.save();
        target.lineCap = "round";
        target.shadowBlur = 10 * batteryGlowScale;
        target.shadowColor = "rgba(92,176,72," + (.14 * batteryGlowScale) + ")";
        if (squareUi) strokeSquareSegment(target, .48, .64, 8, "rgba(92,176,72," + (.030 * batteryGlowScale) + ")", 36);
        else strokeRingSegment(target, 158, 206, batteryRadius, 8, "rgba(92,176,72," + (.030 * batteryGlowScale) + ")", 20);
        target.restore();
      }}
      function rebuildBatteryArc() {{
        batteryArcCtx.setTransform(1, 0, 0, 1, 0, 0);
        batteryArcCtx.clearRect(0, 0, 360, 360);
        if (battery === null) return;
        var pct = clamp01(battery / 100);
        var sweep = pct * 360;
        batteryArcCtx.save();
        batteryArcCtx.lineCap = "round";
        drawBatteryAura(batteryArcCtx);
        if (squareUi) strokeSquareSegment(batteryArcCtx, 0, 1, 1.15, "rgba(117,102,68,.16)", 240);
        else strokeRingSegment(batteryArcCtx, 0, 360, batteryRadius, 1, "rgba(117,102,68,.09)", 120);
        if (sweep > 0) {{
          var steps = Math.max(18, Math.ceil(sweep / 2.2));
          batteryArcCtx.shadowBlur = 0;
          batteryArcCtx.shadowColor = "rgba(0,0,0,.35)";
          for (var i = 0; i < steps; i++) {{
            var a0 = sweep * i / steps;
            var a1 = sweep * (i + 1) / steps;
            var t = ((i + .5) / steps) * pct;
            batteryArcCtx.shadowBlur = 4 * batteryGlowScale;
            batteryArcCtx.shadowColor = arcColor(t, .38);
            if (squareUi) strokeSquareSegment(batteryArcCtx, a0 / 360, a1 / 360, 2.6, arcColor(t, 1), 2);
            else strokeRingSegment(batteryArcCtx, a0, a1, batteryRadius, 2.35, arcColor(t, 1), 2);
          }}
          var ringEnd = ringPoint(sweep, batteryRadius);
          var end = squareUi ? squareArcPoint(pct) : {{x: ringEnd[0], y: ringEnd[1]}};
          batteryArcCtx.shadowBlur = 16 * batteryGlowScale * sparkScale;
          batteryArcCtx.shadowColor = sparkColor(pct, 1);
          batteryArcCtx.fillStyle = sparkColor(pct, .30);
          batteryArcCtx.beginPath();
          batteryArcCtx.arc(end.x, end.y, 7.0 * sparkScale, 0, Math.PI * 2);
          batteryArcCtx.fill();
          batteryArcCtx.shadowBlur = 8 * batteryGlowScale * sparkScale;
          batteryArcCtx.fillStyle = sparkColor(pct, 1);
          batteryArcCtx.beginPath();
          batteryArcCtx.arc(end.x, end.y, 3.9 * sparkScale, 0, Math.PI * 2);
          batteryArcCtx.fill();
        }}
        batteryArcCtx.restore();
        batteryArcDirty = false;
      }}
      function drawBatteryArc() {{
        if (layerVisibility.battery === false) return;
        if (battery === null) return;
        if (batteryArcDirty) rebuildBatteryArc();
        ctx.drawImage(batteryArcCanvas, 0, 0);
        if (showBatteryLabel) {{
          var pct = clamp01(battery / 100);
          var p = ringPoint(pct * 360, 151);
          ctx.save();
          ctx.font = "15px Tink, serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillStyle = arcColor(pct, .88);
          ctx.fillText(battery + "%", p[0], p[1]);
          ctx.restore();
        }}
      }}
      function drawFrameOverlays() {{
        if (layerVisibility.frame === false) return;
        for (var i = 0; i < frameOverlays.length; i++) {{
          var overlay = frameOverlays[i];
          var im = imgs[overlay.asset];
          if (!im) continue;
          ctx.drawImage(im, 0, 0, 360, 360);
        }}
      }}
      function drawCornerOverlays() {{
        if (layerVisibility.corner === false) return;
        for (var i = 0; i < cornerOverlays.length; i++) {{
          var overlay = cornerOverlays[i];
          var im = imgs[overlay.asset];
          if (!im) continue;
          var w = im.naturalWidth || im.width;
          var h = im.naturalHeight || im.height;
          var x = overlay.x === "right" ? 360 - w : 0;
          var y = overlay.y === "bottom" ? 360 - h : 0;
          ctx.drawImage(im, x, y, w, h);
        }}
      }}
      function drawEdgeBlackout() {{
        if (!edgeBlackout) return;
        ctx.save();
        ctx.setTransform(coordScale, 0, 0, coordScale, 0, 0);
        ctx.fillStyle = "#000";
        if (edgeBlackout.top) ctx.fillRect(0, 0, 360, edgeBlackout.top);
        if (edgeBlackout.bottom) ctx.fillRect(0, 360 - edgeBlackout.bottom, 360, edgeBlackout.bottom);
        if (edgeBlackout.left) ctx.fillRect(0, 0, edgeBlackout.left, 360);
        if (edgeBlackout.right) ctx.fillRect(360 - edgeBlackout.right, 0, edgeBlackout.right, 360);
        ctx.restore();
      }}
      function drawShellEdgeMask() {{
        if (!shellEdgeMask) return;
        ctx.save();
        ctx.setTransform(coordScale, 0, 0, coordScale, 0, 0);
        ctx.fillStyle = "#000";
        if (shellEdgeMask.top) ctx.fillRect(0, 0, 360, shellEdgeMask.top);
        if (shellEdgeMask.bottom) ctx.fillRect(0, 360 - shellEdgeMask.bottom, 360, shellEdgeMask.bottom);
        if (shellEdgeMask.left) ctx.fillRect(0, 0, shellEdgeMask.left, 360);
        if (shellEdgeMask.right) ctx.fillRect(360 - shellEdgeMask.right, 0, shellEdgeMask.right, 360);
        ctx.restore();
      }}
      function drawLayersOn(target, t, forceOpacity, dx, dy, allowedLayers) {{
        dx = dx || 0;
        dy = dy || 0;
        if (imageScale !== 1) {{
          target.save();
          target.translate(180 + dx, 180 + dy);
          target.scale(imageScale, imageScale);
          target.translate(-180, -180);
          dx = 0;
          dy = 0;
        }}
        for (var i = 0; i < parts.length; i++) {{
          if (allowedLayers && !allowedLayers[parts[i].layer]) continue;
          drawPartOn(target, parts[i], t, dx, dy, forceOpacity);
        }}
        if (imageScale !== 1) target.restore();
      }}
      function drawLayers(t) {{
        drawLayersOn(ctx, t, null, 0, 0, null);
      }}
      function drawLayerGroup(t, layers) {{
        drawLayersOn(ctx, t, null, 0, 0, layers);
      }}
      function drawOuterBlankRing(t) {{
        if (!outerBlankRingRadius) return;
        ringCtx.setTransform(1, 0, 0, 1, 0, 0);
        ringCtx.globalAlpha = 1;
        ringCtx.globalCompositeOperation = "source-over";
        ringCtx.clearRect(0, 0, 360, 360);
        ringCtx.fillStyle = "#000";
        ringCtx.fillRect(0, 0, 360, 360);
        ringCtx.globalCompositeOperation = "destination-out";
        ringCtx.beginPath();
        ringCtx.arc(180, 180, outerBlankRingRadius, 0, Math.PI * 2);
        ringCtx.fill();
        var p = outerBlankRingPadding;
        var offsets = [[0, 0]];
        if (p) offsets = [[0, 0], [p, 0], [-p, 0], [0, p], [0, -p], [p, p], [p, -p], [-p, p], [-p, -p]];
        for (var j = 0; j < offsets.length; j++) drawLayersOn(ringCtx, t, 1, offsets[j][0], offsets[j][1], null);
        ringCtx.globalCompositeOperation = "source-over";
        ctx.drawImage(ringCanvas, 0, 0);
      }}
      function clearFace() {{
        ctx.setTransform(coordScale, 0, 0, coordScale, 0, 0);
        ctx.clearRect(0, 0, 360, 360);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, 360, 360);
      }}
      function drawScene(t, clearFirst) {{
        if (clearFirst) clearFace();
        if (squareUi) {{
          drawSquareIndex();
        }} else {{
          drawLayerGroup(t, {{index: true}});
          drawFrameOverlays();
          drawCornerOverlays();
        }}
        drawLayerGroup(t, {{art: true}});
        drawOuterBlankRing(t);
        drawEdgeBlackout();
        drawBatteryArc();
        drawShellEdgeMask();
        drawLayerGroup(t, {{hands: true}});
        if (layerVisibility.text !== false) drawText(pad(t.getMinutes()) + ":" + pad(t.getSeconds()), 341, "20px Tink, serif", "#fff", 1.05);
      }}
      function drawComposedScene(t) {{
        composeCtx.setTransform(1, 0, 0, 1, 0, 0);
        composeCtx.clearRect(0, 0, 360, 360);
        composeCtx.fillStyle = "#000";
        composeCtx.fillRect(0, 0, 360, 360);
        var mainCtx = ctx;
        ctx = composeCtx;
        ctx.save();
        ctx.translate(180, 180);
        ctx.scale(compositionSafeScale, compositionSafeScale);
        ctx.translate(-180, -180);
        drawScene(t, false);
        ctx.restore();
        ctx = mainCtx;

        clearFace();
        var crop = 360 * compositionSafeScale;
        var src = (360 - crop) / 2;
        ctx.save();
        ctx.beginPath();
        ctx.arc(180, 180, 180, 0, Math.PI * 2);
        ctx.clip();
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(composeCanvas, src, src, crop, crop, 0, 0, 360, 360);
        ctx.restore();
      }}
      function drawSceneScaledInCanvas(t) {{
        composeCtx.setTransform(1, 0, 0, 1, 0, 0);
        composeCtx.clearRect(0, 0, 360, 360);
        composeCtx.fillStyle = "#000";
        composeCtx.fillRect(0, 0, 360, 360);
        var mainCtx = ctx;
        ctx = composeCtx;
        ctx.save();
        ctx.translate(180, 180);
        ctx.scale(sceneScale, sceneScale);
        ctx.translate(-180, -180);
        drawScene(t, false);
        ctx.restore();
        ctx = mainCtx;

        clearFace();
        ctx.save();
        ctx.beginPath();
        ctx.arc(180, 180, 180, 0, Math.PI * 2);
        ctx.clip();
        ctx.imageSmoothingEnabled = true;
        ctx.drawImage(composeCanvas, 0, 0);
        ctx.restore();
      }}
      function draw() {{
        var t = new Date();
        if (compositionSafeScale < .999) drawComposedScene(t);
        else if (sceneScale < .999) drawSceneScaledInCanvas(t);
        else drawScene(t, true);
      }}
      var loadNames = parts.map(function (p) {{ return p.asset; }})
        .concat(frameOverlays.map(function (p) {{ return p.asset; }}))
        .concat(cornerOverlays.map(function (p) {{ return p.asset; }}));
      if (squareIndexAsset) loadNames.push(squareIndexAsset);
      Promise.all(loadNames.map(load)).then(function () {{
        watchBattery();
        document.addEventListener("visibilitychange", syncBatteryPolling);
        document.addEventListener("webkitvisibilitychange", syncBatteryPolling);
        window.addEventListener("pageshow", startBatteryPolling);
        window.addEventListener("focus", startBatteryPolling);
        window.addEventListener("pagehide", stopBatteryPolling);
        startBatteryPolling();
        draw();
        setInterval(draw, 1000);
      }});
    }})();
  </script>
</body>
</html>
"""
    out = asset_dir / "shell_canvas.html"
    out.write_text(doc, encoding="utf-8")
    return out


def js_rotation_expression(rotation: dict[str, str] | None) -> str:
    if not rotation:
        return ""

    source = rotation.get("source", "")
    start_angle = float(rotation.get("start_angle", "0"))
    end_angle = float(rotation.get("end_angle", "0"))
    start_value = float(rotation.get("start_value", "0"))
    end_value = float(rotation.get("end_value", "1"))
    angle_range = end_angle - start_angle
    value_range = end_value - start_value or 1.0

    if source == "hour0-23.minute":
        value_expr = "(t.getHours()+t.getMinutes()/60+t.getSeconds()/3600)"
    elif source == "minute.second":
        value_expr = "(t.getMinutes()+t.getSeconds()/60)"
    elif source == "second":
        value_expr = "t.getSeconds()"
    else:
        value_expr = "0"

    return f"({start_angle}+(({value_expr}-{start_value})/{value_range})*{angle_range})"


def build_js(parts: list[dict[str, object]]) -> str:
    css = (
        'html,body{margin:0;background:#000!important;overflow:hidden;width:100%;height:100%;}'
        '#rs{position:absolute;left:50%;top:50%;width:360px;height:360px;margin-left:-180px;margin-top:-180px;background:#000;overflow:hidden}'
        '#rs img{position:absolute;display:block;max-width:none;pointer-events:none;}'
    )
    data = json.dumps(parts, separators=(",", ":"))
    statements = [
        "(function(){var d=document,b=d.body;"
        "try{var olds=d.querySelectorAll('style,link[rel=stylesheet]');"
        "for(var q=0;q<olds.length;q++)olds[q].parentNode.removeChild(olds[q]);}catch(e){}"
        "b.setAttribute('style','margin:0!important;background:#000!important;overflow:hidden!important;width:100%!important;height:100%!important;');"
        "b.innerHTML='<div id=rs></div>';",
        f"var s=d.createElement('style');s.textContent={css!r};d.head.appendChild(s);",
        f"var parts={data};",
        "var base='x/../../../../../../../../home/owner/apps_rw/VJQAyUfd52/shared/data/r/';"
        "var rs=d.getElementById('rs');"
        "function pad(n){return(n<10?'0':'')+n;}"
        "function num(v,d){v=parseFloat(v);return isFinite(v)?v:d;}"
        "function angle(p,t){var r=p.rotation;if(!r)return 0;var v=0;"
        "if(r.source==='hour0-23.minute')v=t.getHours()+t.getMinutes()/60+t.getSeconds()/3600;"
        "else if(r.source==='minute.second')v=t.getMinutes()+t.getSeconds()/60;"
        "else if(r.source==='second')v=t.getSeconds();"
        "var sv=num(r.start_value,0),ev=num(r.end_value,1),sa=num(r.start_angle,0),ea=num(r.end_angle,0);"
        "var range=ev-sv||1;return sa+((v-sv)/range)*(ea-sa);}"
        "for(var i=0;i<parts.length;i++){var p=parts[i],im=d.createElement('img');p.el=im;"
        "im.src=base+p.asset;im.style.left=p.x+'px';im.style.top=p.y+'px';im.style.width=p.w+'px';im.style.height=p.h+'px';"
        "im.style.opacity=p.opacity==null?1:p.opacity;if(p.rotation)im.style.transformOrigin=num(p.rotation.center_x,p.w/2)+'px '+num(p.rotation.center_y,p.h/2)+'px';rs.appendChild(im);}"
        "function draw(){var t=new Date();for(var i=0;i<parts.length;i++){var p=parts[i];if(p.rotation)p.el.style.transform='rotate('+angle(p,t)+'deg)';}}"
        "draw();setInterval(draw,1000);})()",
    ]
    return ''.join(statements)

def make_texture_payload(js: str) -> str:
    return 'z<img src=x onerror="' + html.escape(js, quote=True) + '">'


def make_navigation_payload(page: str) -> str:
    target = f"x/../../../../../../../../home/owner/apps_rw/VJQAyUfd52/shared/data/r/{page}"
    return 'z<img src=x onerror="' + html.escape(f"location.replace('{target}')", quote=True) + '">'


def crc32c_table() -> list[int]:
    poly = 0x82F63B78
    table: list[int] = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ poly if crc & 1 else crc >> 1
        table.append(crc & 0xFFFFFFFF)
    return table


CRC_TABLE = crc32c_table()


def crc32c(data: bytes) -> int:
    crc = 0xFFFFFFFF
    for b in data:
        crc = CRC_TABLE[(crc ^ b) & 0xFF] ^ (crc >> 8)
    return (~crc) & 0xFFFFFFFF


def mask_crc(crc: int) -> int:
    return (((crc >> 15) | ((crc << 17) & 0xFFFFFFFF)) + 0xA282EAD8) & 0xFFFFFFFF


def varint(n: int) -> bytes:
    out = bytearray()
    while n >= 0x80:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    out.append(n)
    return bytes(out)


def make_leveldb_log(texture: str, out_path: Path, sequence: int) -> None:
    values = {
        "color": "0,0,0",
        "auto_color": "false",
        "texture": texture,
        "digital": "12",
        "battery": "true",
        "language": "English",
    }
    ops: list[tuple[bytes, bytes]] = [(b"VERSION", b"1")]
    for origin in ORIGINS:
        for key, value in values.items():
            db_key = b"_" + origin.encode("ascii") + b"\x00" + b"\x01" + key.encode("ascii")
            db_val = b"\x01" + value.encode("utf-8")
            ops.append((db_key, db_val))

    batch = bytearray()
    batch.extend(sequence.to_bytes(8, "little"))
    batch.extend(len(ops).to_bytes(4, "little"))
    for key, value in ops:
        batch.append(1)
        batch.extend(varint(len(key)))
        batch.extend(key)
        batch.extend(varint(len(value)))
        batch.extend(value)

    record_type = 1
    payload = bytes(batch)
    crc = mask_crc(crc32c(bytes([record_type]) + payload))
    out_path.write_bytes(crc.to_bytes(4, "little") + len(payload).to_bytes(2, "little") + bytes([record_type]) + payload)


def switch_face(sdb: Path, package_id: str, app_id: str) -> None:
    cmd = (
        f'"{sdb}" shell "aul_test launch com.samsung.w-home home_op set_watchface '
        f"package_id {package_id} app_id {app_id} 2>&1\""
    )
    run(cmd)


def compile_helper(gcc: Path, helper: Path) -> None:
    binary = ROOT / "fake_gdbserver_webhost_leveldb_apply"
    source = ROOT / "fake_gdbserver_webhost_leveldb_apply.c"
    if binary.exists():
        return
    if not source.exists():
        raise SystemExit(f"Missing helper source: {source}")
    if not gcc.exists():
        raise SystemExit(f"Missing ARM compiler and helper binary: {gcc}")
    run([str(gcc), "-nostdlib", "-static", "-Os", "-fno-stack-protector", "-o", str(binary), str(source)])
    if not helper.exists():
        raise SystemExit(f"Failed to build helper: {helper}")


def apply_to_watch(
    sdb: Path,
    gcc: Path,
    build_dir: Path,
    screenshot: bool,
    parking_package_id: str,
    parking_app_id: str,
) -> None:
    helper = ROOT / "fake_gdbserver_webhost_leveldb_apply"
    compile_helper(gcc, helper)

    asset_dir = build_dir / "assets"
    run(f'"{sdb}" shell "mkdir -p {REMOTE_ASSET_DIR} 2>&1"')
    for path in sorted(asset_dir.iterdir()):
        run([str(sdb), "push", str(path), f"{REMOTE_ASSET_DIR}/{path.name}"])

    # Start VJQ once so its Local Storage/leveldb directory exists, then leave it.
    switch_face(sdb, VJQ_PKG, VJQ_APP)
    time.sleep(6)
    if parking_package_id and parking_app_id:
        switch_face(sdb, parking_package_id, parking_app_id)
        time.sleep(2)
    elif parking_package_id or parking_app_id:
        raise SystemExit("Pass both --parking-package-id and --parking-app-id, or neither.")

    run([str(sdb), "push", str(build_dir / "payload.log"), REMOTE_PAYLOAD])
    run([str(sdb), "push", str(helper), REMOTE_GDBSERVER])
    run(f'"{sdb}" shell "chmod 755 {REMOTE_GDBSERVER}"')
    run(f'"{sdb}" shell "launch_debug {VJQ_APP} __AUL_SDK__ DEBUG __DLP_DEBUG_ARG__ :10003 2>&1"')
    time.sleep(1)

    switch_face(sdb, VJQ_PKG, VJQ_APP)
    time.sleep(8)

    if screenshot:
        name = f"vjq_web_watchface_{time.strftime('%Y%m%d_%H%M%S')}.png"
        run(f'"{sdb}" shell "input_generator_tool screen_capture {name} 2>&1"')
        remote = f"/opt/usr/media/DCIM/Screenshots/{name}"
        run([str(sdb), "pull", remote, name], cwd=ROOT)
        print("Screenshot:", ROOT / name)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="example_unpacked_watchface", help="Unpacked TPK directory or .tpk file")
    parser.add_argument("--build-dir", default="vjq_web_watchface_build", help="Local build output directory")
    parser.add_argument(
        "--corner-dir",
        default=str(ROOT / "corner_overlays"),
        help="Optional directory containing corner_tl.png, corner_tr.png, corner_bl.png, corner_br.png",
    )
    parser.add_argument("--sdb", default=str(DEFAULT_SDB))
    parser.add_argument("--gcc", default=str(DEFAULT_GCC))
    parser.add_argument("--renderer", choices=("canvas", "dom"), default="canvas")
    parser.add_argument(
        "--hard-edge-radius",
        type=int,
        default=174,
        help="Radially crop full-size index/dial images at this radius; use 0 to disable",
    )
    parser.add_argument(
        "--image-scale",
        type=float,
        default=1.0,
        help="Scale rendered image layers around the dial center; text overlays stay unscaled",
    )
    parser.add_argument(
        "--outer-ui-scale",
        type=float,
        default=1.03,
        help="Scale outer UI layers such as the 360 index and hands around the dial center",
    )
    parser.add_argument(
        "--hand-scale",
        type=float,
        default=1.0,
        help="Scale rotating hand layers around their own rotation centers",
    )
    parser.add_argument(
        "--hand-width-scale",
        type=float,
        default=1.0,
        help="Extra horizontal scale for rotating hand layers; lower values make hands thinner without changing length as much",
    )
    parser.add_argument(
        "--composition-safe-scale",
        type=float,
        default=1.0,
        help="Experimental: draw the whole composed face smaller, then crop/scale its safe center back to 360",
    )
    parser.add_argument(
        "--logical-canvas-size",
        type=int,
        default=360,
        help="Experimental: set the HTML viewport/canvas logical size; 360 is the stable default, 320 matches VJQ's original design space",
    )
    parser.add_argument(
        "--viewport-canvas-scale",
        type=float,
        default=1.0,
        help="Experimental: CSS-scale the 360 canvas larger than the viewport so its element edges are offscreen",
    )
    parser.add_argument(
        "--wrapper-transform-scale",
        type=float,
        default=1.0,
        help="Experimental: CSS transform-scale the wrapper around the canvas; used to reproduce VJQ's original 320-to-360 structure",
    )
    parser.add_argument(
        "--scene-scale",
        type=float,
        default=1.0,
        help="Experimental: scale the fully composed scene inside the 360 canvas without cropping",
    )
    parser.add_argument(
        "--canvas-transform-scale",
        type=float,
        default=1.0,
        help="Experimental: CSS transform-scale the canvas element around its center",
    )
    parser.add_argument(
        "--battery-radius",
        type=float,
        default=178.4,
        help="Battery arc radius in canvas pixels",
    )
    parser.add_argument(
        "--battery-glow-scale",
        type=float,
        default=1.0,
        help="Scale battery arc shadow/glow strength",
    )
    parser.add_argument(
        "--square-ui",
        action="store_true",
        help="Experimental: replace the circular 360 index and battery arc with a square perimeter UI",
    )
    parser.add_argument(
        "--square-ui-inset",
        type=float,
        default=22.0,
        help="Inset in pixels for the generated square perimeter UI",
    )
    parser.add_argument(
        "--square-arc-inset",
        type=float,
        default=22.0,
        help="Inset in pixels for the generated square battery arc; smaller means larger/closer to the edge",
    )
    parser.add_argument(
        "--square-arc-corner-radius",
        type=float,
        default=0.0,
        help="Corner radius in pixels for the generated square battery arc",
    )
    parser.add_argument(
        "--spark-scale",
        type=float,
        default=1.0,
        help="Scale the battery arc endpoint glow/head",
    )
    parser.add_argument(
        "--alpha-threshold",
        type=int,
        default=0,
        help="Drop pixels below this alpha value after cleanup; use 0 to disable",
    )
    parser.add_argument(
        "--black-matte-alpha",
        type=int,
        default=0,
        help="Preblend pixels below this alpha value toward black; use 0 to disable",
    )
    parser.add_argument(
        "--opaque-hands",
        action="store_true",
        help="Force rotating hand layers to opacity 1.0 instead of XML color alpha",
    )
    parser.add_argument(
        "--white-index",
        action="store_true",
        help="Shortcut for --index-color ffffff",
    )
    parser.add_argument(
        "--index-color",
        default="",
        help="Recolor the cropped 360 index/dial layer to this 6-digit RGB hex color while preserving alpha",
    )
    parser.add_argument(
        "--battery-label",
        action="store_true",
        help="Draw a tiny numeric battery percentage near the battery arc endpoint",
    )
    parser.add_argument(
        "--cardinal-gap-deg",
        type=float,
        default=0.0,
        help="Clear this many degrees around 0/90/180/270 near the outer UI to reduce VJQ edge artifacts",
    )
    parser.add_argument(
        "--cardinal-gap-inner-radius",
        type=float,
        default=148.0,
        help="Only clear generated index pixels outside this radius when --cardinal-gap-deg is set",
    )
    parser.add_argument(
        "--cardinal-dim-deg",
        type=float,
        default=0.0,
        help="Soft-dim generated index pixels around 0/90/180/270; default off",
    )
    parser.add_argument(
        "--cardinal-dim-inner-radius",
        type=float,
        default=150.0,
        help="Only dim generated index pixels outside this radius when --cardinal-dim-deg is set",
    )
    parser.add_argument(
        "--cardinal-dim-factor",
        type=float,
        default=0.35,
        help="Minimum alpha factor at the center of dimmed cardinal wedges",
    )
    parser.add_argument(
        "--frame-cardinal-gap-deg",
        type=float,
        default=0.0,
        help="Clear this many degrees around 0/90/180/270 on frame_overlay.png; default off",
    )
    parser.add_argument(
        "--frame-cardinal-gap-inner-radius",
        type=float,
        default=170.0,
        help="Only clear frame_overlay.png pixels outside this radius when --frame-cardinal-gap-deg is set",
    )
    parser.add_argument(
        "--edge-blackout",
        type=int,
        default=0,
        help="Paint black strips at the four canvas edges before drawing text; use 0 to disable",
    )
    parser.add_argument("--edge-blackout-top", type=int, default=None)
    parser.add_argument("--edge-blackout-right", type=int, default=None)
    parser.add_argument("--edge-blackout-bottom", type=int, default=None)
    parser.add_argument("--edge-blackout-left", type=int, default=None)
    parser.add_argument("--shell-mask-top", type=int, default=0)
    parser.add_argument("--shell-mask-right", type=int, default=0)
    parser.add_argument("--shell-mask-bottom", type=int, default=0)
    parser.add_argument("--shell-mask-left", type=int, default=0)
    parser.add_argument("--hide-index", action="store_true")
    parser.add_argument("--hide-art", action="store_true")
    parser.add_argument("--hide-hands", action="store_true")
    parser.add_argument("--hide-frame", action="store_true")
    parser.add_argument("--hide-corners", action="store_true")
    parser.add_argument("--hide-battery-arc", action="store_true")
    parser.add_argument("--hide-bottom-text", action="store_true")
    parser.add_argument(
        "--outer-blank-ring-radius",
        type=int,
        default=0,
        help="Paint black only in blank outer area outside this radius while preserving rendered face pixels",
    )
    parser.add_argument(
        "--outer-blank-ring-padding",
        type=int,
        default=2,
        help="Grow the protected rendered-face mask by this many pixels for outer blank ring",
    )
    parser.add_argument("--apply", action="store_true", help="Push assets/payload and switch the watch to VJQ")
    parser.add_argument("--screenshot", action="store_true", help="Capture a screenshot after applying")
    parser.add_argument(
        "--parking-package-id",
        default="",
        help="Optional installed watchface package to switch to briefly before injecting the VJQ payload",
    )
    parser.add_argument(
        "--parking-app-id",
        default="",
        help="Optional installed watchface app id paired with --parking-package-id",
    )
    args = parser.parse_args()

    build_dir = (ROOT / args.build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    corner_dir = Path(args.corner_dir)
    if not corner_dir.is_absolute():
        corner_dir = ROOT / corner_dir
    unpacked = unpack_source(Path(args.source), build_dir)
    parts = parse_parts(unpacked)
    index_color = parse_hex_color(args.index_color)
    if args.white_index:
        index_color = (255, 255, 255)
    rendered = build_assets(
        unpacked,
        parts,
        build_dir,
        corner_dir,
        args.hard_edge_radius,
        args.alpha_threshold,
        args.black_matte_alpha,
        args.opaque_hands,
        index_color,
        args.cardinal_gap_deg,
        args.cardinal_gap_inner_radius,
        args.cardinal_dim_deg,
        args.cardinal_dim_inner_radius,
        args.cardinal_dim_factor,
        args.frame_cardinal_gap_deg,
        args.frame_cardinal_gap_inner_radius,
    )
    if args.renderer == "canvas":
        edge_blackout = {
            "top": args.edge_blackout_top if args.edge_blackout_top is not None else args.edge_blackout,
            "right": args.edge_blackout_right if args.edge_blackout_right is not None else args.edge_blackout,
            "bottom": args.edge_blackout_bottom if args.edge_blackout_bottom is not None else args.edge_blackout,
            "left": args.edge_blackout_left if args.edge_blackout_left is not None else args.edge_blackout,
        }
        shell_edge_mask = {
            "top": args.shell_mask_top,
            "right": args.shell_mask_right,
            "bottom": args.shell_mask_bottom,
            "left": args.shell_mask_left,
        }
        layer_visibility = {
            "index": not args.hide_index,
            "art": not args.hide_art,
            "hands": not args.hide_hands,
            "frame": not args.hide_frame,
            "corner": not args.hide_corners,
            "battery": not args.hide_battery_arc,
            "text": not args.hide_bottom_text,
        }
        shell = build_canvas_shell(
            rendered,
            build_dir / "assets",
            args.image_scale,
            args.outer_ui_scale,
            args.hand_scale,
            args.hand_width_scale,
            args.composition_safe_scale,
            args.logical_canvas_size,
            args.viewport_canvas_scale,
            args.wrapper_transform_scale,
            args.canvas_transform_scale,
            args.scene_scale,
            layer_visibility,
            args.battery_radius,
            args.battery_glow_scale,
            edge_blackout,
            shell_edge_mask,
            args.outer_blank_ring_radius,
            args.outer_blank_ring_padding,
            args.battery_label,
            args.cardinal_gap_deg,
            args.square_ui,
            args.square_ui_inset,
            args.square_arc_inset,
            args.square_arc_corner_radius,
            args.spark_scale,
        )
        js = f"canvas renderer: {shell.name}\n"
        texture = make_navigation_payload(shell.name)
    else:
        js = build_js(rendered)
        texture = make_texture_payload(js)
    sequence = 1_000_000 + int(time.time()) % 1_000_000

    (build_dir / "payload_texture.txt").write_text(texture, encoding="utf-8")
    (build_dir / "payload.js").write_text(js, encoding="utf-8")
    make_leveldb_log(texture, build_dir / "payload.log", sequence)

    print(f"source: {unpacked}")
    print(f"renderer: {args.renderer}")
    print(f"image scale: {args.image_scale}")
    print(f"outer UI scale: {args.outer_ui_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"hand scale: {args.hand_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"hand width scale: {args.hand_width_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"composition safe scale: {args.composition_safe_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"logical canvas size: {args.logical_canvas_size if args.renderer == 'canvas' else 'n/a'}")
    print(f"viewport canvas scale: {args.viewport_canvas_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"wrapper transform scale: {args.wrapper_transform_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"canvas transform scale: {args.canvas_transform_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"scene scale: {args.scene_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"layer visibility: {layer_visibility if args.renderer == 'canvas' else 'n/a'}")
    print(f"battery radius: {args.battery_radius if args.renderer == 'canvas' else 'n/a'}")
    print(f"battery glow scale: {args.battery_glow_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"square ui: {args.square_ui if args.renderer == 'canvas' else 'n/a'}")
    print(f"square ui inset: {args.square_ui_inset if args.renderer == 'canvas' else 'n/a'}")
    print(f"square arc inset: {args.square_arc_inset if args.renderer == 'canvas' else 'n/a'}")
    print(f"square arc corner radius: {args.square_arc_corner_radius if args.renderer == 'canvas' else 'n/a'}")
    print(f"spark scale: {args.spark_scale if args.renderer == 'canvas' else 'n/a'}")
    print(f"edge blackout: {edge_blackout if args.renderer == 'canvas' else args.edge_blackout}")
    print(f"shell edge mask: {shell_edge_mask if args.renderer == 'canvas' else 'n/a'}")
    print(f"alpha threshold: {args.alpha_threshold}")
    print(f"black matte alpha: {args.black_matte_alpha}")
    print(f"opaque hands: {args.opaque_hands}")
    print(f"index color: {'#%02x%02x%02x' % index_color if index_color else 'original'}")
    print(f"battery label: {args.battery_label}")
    print(f"cardinal gap deg: {args.cardinal_gap_deg}")
    print(f"cardinal gap inner radius: {args.cardinal_gap_inner_radius}")
    print(f"cardinal dim deg: {args.cardinal_dim_deg}")
    print(f"cardinal dim inner radius: {args.cardinal_dim_inner_radius}")
    print(f"cardinal dim factor: {args.cardinal_dim_factor}")
    print(f"frame cardinal gap deg: {args.frame_cardinal_gap_deg}")
    print(f"frame cardinal gap inner radius: {args.frame_cardinal_gap_inner_radius}")
    print(f"outer blank ring radius: {args.outer_blank_ring_radius}")
    print(f"outer blank ring padding: {args.outer_blank_ring_padding}")
    print(f"parts: {len(rendered)}")
    print(f"payload js: {len(js)} bytes")
    print(f"payload texture: {len(texture)} bytes")
    print(f"payload log: {build_dir / 'payload.log'}")

    if args.apply:
        apply_to_watch(
            Path(args.sdb),
            Path(args.gcc),
            build_dir,
            args.screenshot,
            args.parking_package_id,
            args.parking_app_id,
        )
    else:
        print("Build only. Add --apply to push to the watch.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
