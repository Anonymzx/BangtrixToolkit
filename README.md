<div align="center">

# 🚀 BangtrixToolkit

**Essential Custom Nodes for ComfyUI**

[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Node-FF6B6B?style=flat-square)](https://github.com/comfyanonymous/ComfyUI)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/github/license/Anonymzx/BangtrixToolkit?style=flat-square)](LICENSE)

A powerful toolkit for ComfyUI featuring a **real-time Hardware Monitor overlay** with native AMD ROCm support, and a **Universal Prompt Translator** node — all in one clean package.

</div>

---

<details open>
<summary><b>✨ Fitur Utama</b> (Klik untuk menutup)</summary>
<br>

### 🖥️ Advanced HW Monitor

Real-time monitoring overlay displayed directly on the ComfyUI canvas. Tracks **GPU Name**, **Load (%)**, **VRAM Usage**, **Temperature (°C)**, and **Fan Speed (%)** with animated progress bars and a live sparkline graph. The widget is fully draggable, minimizable, and toggleable via `Ctrl + Shift + M`.

### 🔌 Native AMD ROCm Support

Intelligent multi-backend architecture that auto-detects your GPU vendor and selects the optimal data source:

| GPU | Platform | Primary Backend | Fallback |
|-----|----------|----------------|----------|
| **AMD RDNA3** (RX 7000+) | Windows | ROCm / HIP SDK (`hipInfo.exe`) + PDH | PowerShell / WMI |
| **Legacy AMD** | Windows | ADL (`atiadlxx.dll`) + PDH | PowerShell |
| **NVIDIA** | Windows / Linux | NVML / `nvidia-smi` | PDH / sysfs |
| **Intel ARC / iGPU** | Windows / Linux | PDH + sysfs | PowerShell / `hwmon` |

No third-party background applications required — the backend uses only native OS tools and your existing AMD driver stack.

### 🌐 Universal Prompt Translator

An integrated translation node that converts prompts from **16+ languages** into English and directly outputs CLIP conditioning. Features quality presets (Normal / High / Ultra), style presets (Anime / Realistic / Cinematic / Fantasy), auto-negative generation, and a built-in translation cache for fast repeated workflows.

</details>

---

<details>
<summary><b>⚙️ Kustomisasi UI & Settings</b> (Klik untuk membuka)</summary>
<br>

The HW Monitor is fully integrated with the built-in ComfyUI Settings dialog. All changes apply **instantly** — no browser reload required.

| Setting | Type | Options |
|---------|------|---------|
| **🎨 Theme** | Combo | Default Green · Neon Blue · Crimson Red · Hacker (Black & Green) |
| **⏱️ Refresh Rate** | Combo | 500ms · 1s · 2s |
| **👁️ Show on Startup** | Boolean | On / Off |
| **🔲 Background Opacity** | Slider | 0.1 – 1.0 (step 0.05) |
| **📦 Compact Mode** | Boolean | Hide sparkline graph for minimal footprint |

Access the settings by clicking the **⚙ gear icon** on the HW Monitor widget header, or through the ComfyUI Settings menu.

</details>

---

<details>
<summary><b>🚀 Cara Instalasi</b> (Klik untuk membuka)</summary>
<br>

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/Anonymzx/BangtrixToolkit.git
pip install -r BangtrixToolkit/requirements.txt
```

> **Restart ComfyUI** after installation. The HW Monitor overlay appears automatically — no node configuration needed.

</details>

---

<details>
<summary><b>⚠️ Catatan Khusus Pengguna AMD</b> (Klik untuk membuka)</summary>
<br>

> **Untuk pengguna GPU AMD — khususnya arsitektur RDNA3 (seri RX 7000 ke atas):**
>
> Windows membatasi akses sensor **suhu (temperature)** dan **kipas (fan)** pada GPU AMD modern. Agar HW Monitor dapat membaca nilai **TEMP** dan **FAN** secara sempurna tanpa aplikasi pihak ketiga, **sangat disarankan untuk menginstal AMD ROCm / HIP SDK**.
>
> 📥 Download: [AMD ROCm HIP SDK](https://www.amd.com/en/developer/rocm.html)
>
> Setelah instalasi, backend akan otomatis mendeteksi `hipInfo.exe` melalui environment variable `HIP_PATH` dan menggabungkannya dengan live data dari Windows PDH counters.
>
> **Tanpa ROCm**, sistem akan otomatis menggunakan fallback Windows — tetap menampilkan **GPU Load** dan **VRAM Usage**, namun suhu dan kipas akan menampilkan `N/A`.

</details>

---

<div align="center">

### ❤️ Created by [Anonymzx](https://github.com/Anonymzx)

</div>