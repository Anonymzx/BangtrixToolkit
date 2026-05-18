<div align="center">

# 🚀 BangtrixToolkit

**Essential Custom Nodes for ComfyUI**

[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Node-FF6B6B?style=flat-square)](https://github.com/comfyanonymous/ComfyUI)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/github/license/Anonymzx/BangtrixToolkit?style=flat-square)](LICENSE)

</div>

---

## ✨ Key Features

- **🖥️ Advanced HW Monitor** — Real-time overlay displaying **GPU Load**, **VRAM Usage**, **Temperature**, and **Fan Speed** directly on the ComfyUI canvas. Includes a live sparkline graph and draggable widget.

- **🔌 Multi-Backend Intelligence** — Auto-detects your GPU vendor and OS, then selects the best data source:
  - **AMD RDNA3** (RX 7000+): Native **ROCm / HIP SDK** integration via `hipInfo.exe` + Windows **PDH counters** for live VRAM
  - **Legacy AMD**: ADL fallback
  - **NVIDIA**: NVML / `nvidia-smi`
  - **Intel ARC / iGPU**: PDH + sysfs
  - **Linux**: `/sys/class/drm/`, `nvidia-smi`, `hwmon`

- **🎨 Customizable UI** — Change the overlay theme, refresh rate, background opacity, and toggle **Compact Mode** — all from a built-in settings panel (⚙). No reload required.

- **🌐 Universal Prompt Translator** — Translate and enhance prompts directly inside ComfyUI with Google Translate integration, quality/style presets, and auto-negative generation.

---

## 📦 Installation

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Anonymzx/BangtrixToolkit.git
pip install -r BangtrixToolkit/requirements.txt
```

> Restart ComfyUI after installation. The HW Monitor overlay appears automatically — no node setup required.

---

## ⚙️ HW Monitor Quick Reference

| Action | Shortcut |
|--------|----------|
| Show / Hide Overlay | `Ctrl + Shift + M` |
| Minimize Widget | Click `−` button |
| Open Settings Panel | Click `⚙` button |
| Reposition Widget | Drag the header bar |

### Settings

| Setting | Type | Options |
|---------|------|---------|
| **Theme** | Combo | Default Green · Neon Blue · Crimson Red · Hacker |
| **Refresh Rate** | Combo | 500ms · 1s · 2s |
| **Show on Startup** | Boolean | On / Off |
| **Background Opacity** | Slider | 0.1 – 1.0 |
| **Compact Mode** | Boolean | Hide sparkline graph for minimal footprint |

---

## 📋 AMD Users — Important Note

> **For AMD RDNA3 GPUs (RX 7000 series and newer):**
> 
> Installing the **AMD HIP SDK / ROCm** is strongly recommended to unlock full sensor data (temperature, fan, core clock). Without it, the monitor gracefully falls back to **Windows PDH counters** which provide **GPU Load and VRAM** — temperature and fan will show `N/A`.
>
> Download: [AMD ROCm HIP SDK](https://www.amd.com/en/developer/rocm.html)
>
> After installation, the backend auto-detects `hipInfo.exe` from `HIP_PATH` and combines it with live PDH data for complete monitoring.

---

## 🚀 Roadmap

| Version | Features |
|:-------:|----------|
| **v1** ✅ | Universal Prompt Translator |
| **v2** ✅ | HW Monitor — AMD / NVIDIA / Intel · Multi-backend · Settings UI |
| **v3** 🔜 | Smart Cache · Performance Optimizer · Benchmark Tools |

---

<div align="center">

### ❤️ Created by [Anonymzx](https://github.com/Anonymzx)

</div>