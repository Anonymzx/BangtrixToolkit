<div align="center">

# 🚀 BangtrixToolkit

**Advanced Custom Node Toolkit for ComfyUI**

![GitHub](https://img.shields.io/badge/ComfyUI-Custom_Node-FF6B6B?style=flat-square)
![GitHub](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)
![GitHub](https://img.shields.io/github/license/Anonymzx/BangtrixToolkit?style=flat-square)
![GitHub](https://img.shields.io/github/stars/Anonymzx/BangtrixToolkit?style=flat-square)

> *Translate your prompts & monitor your AMD GPU — all inside ComfyUI*

---

[🌐 Translate](#-bangtrix-translate-universal) •
[🖥️ AMD Monitor](#-amd-monitor--real-time-gpu-overlay-) •
[📦 Installation](#-installation) •
[🚀 Roadmap](#-roadmap)

---

</div>

---

<details>
<summary><b>🌐 Bangtrix Translate Universal</b> — Click to expand</summary>

<br>

Bangtrix Translate Universal is an advanced translation node for ComfyUI that automatically translates prompts into English and directly outputs them into CLIP conditioning.

Designed for: **Stable Diffusion · Flux · SDXL · Pony · Anime Models · Realistic Models · Any CLIP-based workflow**

---

### ✨ Features

| Category | Features |
|----------|----------|
| 🌍 **Translation** | Google Translate integration · Multi-language support · Offline-safe fallback |
| 🧠 **Enhancement** | Quality presets · Style presets · Prompt cleaning · Enhancement system |
| ❌ **Auto Negative** | Anatomy fixes · Blur reduction · Watermark filtering · Artifact reduction · Style-based negatives |
| ⚡ **Performance** | Translation cache · Fast repeated translation · Lightweight · Universal compatibility |

---

### 📝 Supported Languages

<div align="center">

| Code | Language | Code | Language |
|------|----------|------|----------|
| `auto` | Auto Detect | `en` | English |
| `id` | Indonesian | `ja` | Japanese |
| `ko` | Korean | `zh-CN` | Chinese (Simplified) |
| `zh-TW` | Chinese (Traditional) | `fr` | French |
| `de` | German | `es` | Spanish |
| `pt` | Portuguese | `ru` | Russian |
| `it` | Italian | `ar` | Arabic |
| `tr` | Turkish | `hi` | Hindi |
| `th` | Thai | `vi` | Vietnamese |

</div>

---

### 🎨 Presets

<div align="center">

| Quality | Style | Auto Negative |
|---------|-------|---------------|
| `normal` — Standard | `none` — No style | `normal` — Basic |
| `high` — Better details | `anime` · `realistic` · `cinematic` | `strong` — Reduced artifacts |
| `ultra` — Maximum | `photography` · `product` · `fantasy` · `portrait` | `ultra` — Maximum cleanup |

</div>

---

### ⚙️ Workflow Example

<details>
<summary><b>See node inputs & outputs</b></summary>

<br>

**Inputs:** `positive_prompt` · `negative_prompt` · `source_language` · `target_language` · `quality_preset` · `style_preset` · `enable_translate` · `enable_enhance` · `enable_clean` · `enable_cache` · `enable_auto_negative` · `auto_negative_strength` · `show_original`

**Outputs:** `positive_conditioning` · `negative_conditioning` · `positive_prompt_final` · `negative_prompt_final`

</details>

<br>

<div align="center">

| Indonesian Input | Final English Prompt |
|-----------------|---------------------|
| `wanita cantik memakai kimono di malam hari` | `beautiful woman wearing kimono at night, cinematic lighting, high quality, detailed` |

</div>

---

<div align="center">
<img width="570" alt="Workflow" src="https://github.com/user-attachments/assets/44a6aeb5-1b15-4461-be2c-ec98291ac2e9" />
<br><br>
<img width="900" alt="Workflow detail" src="https://github.com/user-attachments/assets/36b098b9-4a4e-4787-aaea-8f249674a151" />
</div>

---

### 💡 Tips

> 🔹 Use `show_original` to debug translations  
> 🔹 Enable `enable_cache` for faster workflows  
> 🔹 Use `ultra` quality for SDXL and Flux  
> 🔹 Use `anime` preset for anime models  
> 🔹 Use `realistic` or `photography` for realism models

</details>

---

<details open>
<summary><b>🖥️ AMD Monitor — Real-Time GPU Overlay</b> — Click to expand</summary>

<br>

> **Zero configuration. Plug & play.** AMD Monitor auto-loads when ComfyUI starts — no node needed.

---

### ✨ Features

<div align="center">

| | Feature | Description |
|:---:|---------|-------------|
| 📊 | **GPU Load** | Real-time utilization % with animated bar |
| 💾 | **VRAM Usage** | Used / Total in GB + utilization bar |
| 🌡️ | **Temperature** | GPU temp in °C/°F *(requires LibreHardwareMonitor)* |
| 💨 | **Fan Speed** | Fan RPM/percentage *(requires LibreHardwareMonitor)* |
| 🏷️ | **GPU Name** | Auto-detects your GPU model *(e.g. RX 7800 XT)* |
| 📈 | **Sparkline Chart** | 30-second GPU Load history graph |
| ⚡ | **Generation Stats** | Duration, RAM Peak, Delta & CPU Peak |
| 🖥️ | **Multi-GPU** | Chip selector for multi-GPU systems |
| ⚠️ | **VRAM Alert** | Toast + inline banner on threshold breach |
| 🖱️ | **Draggable** | Click & drag to reposition |
| ➖ | **Minimize** | Toggle with `−` button |
| ⌨️ | **Hide/Show** | `Ctrl + Shift + M` shortcut |
| ⚙️ | **Settings Panel** | Interval, Alert %, Temp unit, Sparkline toggle |
| 💾 | **Persist Config** | Position & settings saved in localStorage |

</div>

---

### 📸 Preview

<!-- Replace with your own screenshot -->
<!-- <img src="docs/screenshot_overlay.png" width="300" align="right"/> -->

```
┌────────────────────────────┐
│ 🔴 AMD Monitor             │
├────────────────────────────┤
│  AMD Radeon RX 7800 XT     │
│ ┌───────┬──────────┐       │
│ │GPU    │ VRAM     │       │
│ │ 1.2%  │1.1/4.0 GB│       │
│ │ █░░░░░│███░░░░░░│       │
│ ├───────┼──────────┤       │
│ │ Temp  │ Fan      │       │
│ │ 45°C  │1200 RPM │       │
│ │ ███░░░│ █░░░░░░░│       │
│ └───────┴──────────┘       │
│  ╱ GPU Load History ╲      │
│ ──────────────────────     │
│ 🟢 RX 7800 XT │ [ps]      │
└────────────────────────────┘
```

---

### ⚙️ Architecture

```
┌──────────────────────────────────────────────┐
│            ComfyUI Server                     │
│  ┌──────────────────────────────────────┐    │
│  │ on_app_started()                     │    │
│  │  ├── WS Route → /ws/amd_monitor      │    │
│  │  └── Stream loop → every 1s          │    │
│  └──────────────┬───────────────────────┘    │
│                 │ WebSocket                   │
│  ┌──────────────▼───────────────────────┐    │
│  │      Backend Auto-Detect              │    │
│  │                                       │    │
│  │ 1. LibreHardwareMonitor  ← WMI       │    │
│  │    → Temp, Fan, Clock, Power         │    │
│  │                                       │    │
│  │ 2. PowerShell Counters  ★ ACTIVE     │    │
│  │    → GPU Load, VRAM, GPU Name        │    │
│  │                                       │    │
│  │ 3. ADL (atiadlxx.dll)                │    │
│  │    → Temp, Fan (partial)             │    │
│  │                                       │    │
│  │ 4. psutil (system RAM)               │    │
│  └──────────────────────────────────────┘    │
│  ┌──────────────────────────────────────┐    │
│  │   Comfy Process Monitor              │    │
│  │   Auto-detect generations            │    │
│  └──────────────────────────────────────┘    │
└──────────────────┬───────────────────────────┘
                   │ JSON every 1s
┌──────────────────▼───────────────────────────┐
│          Browser (ComfyUI)                    │
│  ┌──────────────────────────────────────┐    │
│  │  Floating Overlay (amd_monitor.js)    │    │
│  └──────────────────────────────────────┘    │
└──────────────────────────────────────────────┘
```

---

### 🏗️ Backend Priority

<div align="center">

| Priority | Backend | Metrics | Platform |
|:--------:|---------|---------|----------|
| 🥇 | **LibreHardwareMonitor** | Temp, Fan, Clock, Power | Windows |
| 🥈 | **PowerShell Counters** | Load, VRAM, Name | Windows |
| 🥉 | **ADL** (atiadlxx.dll) | Temp, Fan | Windows |
| 4 | **psutil** | System RAM only | All |

</div>

---

### 🌡️ LibreHardwareMonitor Setup

To enable **Temperature, Fan Speed, Clock speeds & Power Draw**:

1. **Auto-download** — LHM portable (8.5MB) is downloaded automatically on first ComfyUI start
   ```
   📁 BangtrixToolkit/monitor/libre_hardware_monitor/LibreHardwareMonitor.exe
   ```

2. **Run as Administrator** (one-time):
   ```powershell
   .\monitor\libre_hardware_monitor\LibreHardwareMonitor.exe --wmi
   ```

3. **Restart ComfyUI** — Backend auto-switches to LHM 🎯

> ⚠️ **Without LHM**, core metrics still work via PowerShell Counters: GPU Load, VRAM, GPU Name.

---

### ⌨️ Quick Reference

| Action | Keyboard / Button |
|--------|------------------|
| Toggle overlay | `Ctrl + Shift + M` |
| Minimize | `−` button |
| Settings | `⚙` button |

---

### 📋 Requirements

| Package | Needed | Purpose |
|---------|:------:|---------|
| `aiohttp` | ✅ **Yes** | WebSocket server |
| `psutil` | ✅ Recommended | Process Monitor |
| `requests` | ❌ Optional | Translate node fallback |

</details>

---

## 📦 Installation

<details>
<summary><b>See installation guide</b></summary>

<br>

### 🔧 Manual

```bash
cd "ComfyUI/custom_nodes"
git clone https://github.com/Anonymzx/BangtrixToolkit.git
pip install -r requirements.txt
```

> **Restart ComfyUI** after installation.

### 📥 ComfyUI Manager

1. Open **ComfyUI Manager**
2. Go to **Custom Nodes Manager**
3. Search for **BangtrixToolkit**
4. Click **Install**
5. **Restart** ComfyUI

</details>

---

## 🚀 Roadmap

<div align="center">

| Version | Features |
|:-------:|----------|
| **v1** ✅ | Bangtrix Translate Universal |
| **v2** ✅ | AMD Monitor · ROCm Utilities |
| **v3** 🔜 | Smart Cache · Performance Optimizer · Benchmark Tools |

</div>

---

<div align="center">

### ❤️ Created by [Anonymzx](https://github.com/Anonymzx)

</div>