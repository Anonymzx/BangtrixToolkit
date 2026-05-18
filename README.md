<div align="center">

# 🚀 BangtrixToolkit

**Essential Custom Nodes for ComfyUI**

[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Node-FF6B6B?style=flat-square)](https://github.com/comfyanonymous/ComfyUI)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/github/license/Anonymzx/BangtrixToolkit?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Anonymzx/BangtrixToolkit?style=flat-square)](https://github.com/Anonymzx/BangtrixToolkit/stargazers)

A powerful toolkit for ComfyUI featuring a **real-time Hardware Monitor overlay** with native AMD ROCm support, and a **Universal Prompt Translator** node — all in one clean package.

</div>

---

<details open>
<summary><b>✨ Key Features</b> (Click to Close)</summary>

### 🖥️ Advanced HW Monitor

Real-time monitoring overlay displayed directly on the ComfyUI canvas. Tracks **GPU Name**, **Load (%)**, **VRAM Usage**, **Temperature (°C)**, and **Fan Speed (%)** with animated progress bars and a live sparkline graph. The widget is fully draggable, minimizable, and toggleable via `Ctrl + Shift + M`.

<div align="center">
  <img width="264" height="249" alt="HW Monitor Default" src="https://github.com/user-attachments/assets/3967ee42-4f6e-40f7-b5fd-e55c21f719a4" />
</div>

### 🔌 Native AMD ROCm Support

Intelligent multi-backend architecture that auto-detects your GPU vendor and selects the optimal data source:

| GPU | Platform | Primary Backend | Fallback |
|---|---|---|---|
| **AMD RDNA3** (RX 7000+) | Windows | ROCm / HIP SDK (`hipInfo.exe`) + PDH | PowerShell / WMI |
| **Legacy AMD** | Windows | ADL (`atiadlxx.dll`) + PDH | PowerShell |
| **NVIDIA** | Windows / Linux | NVML / `nvidia-smi` | PDH / sysfs |
| **Intel ARC / iGPU** | Windows / Linux | PDH + sysfs | PowerShell / `hwmon` |

No third-party background applications required — the backend uses only native OS tools and your existing AMD driver stack.

### 🌐 Universal Prompt Translator

An integrated translation node that converts prompts from **16+ languages** into English and directly outputs CLIP conditioning.

| Code | Language | Code | Language |
|---|---|---|---|
| `auto` | Auto Detect | `en` | English |
| `id` | Indonesian | `ja` | Japanese |
| `ko` | Korean | `zh-CN` | Chinese (Simplified) |
| `zh-TW` | Chinese (Traditional) | `fr` | French |
| `de` | German | `es` | Spanish |
| `pt` | Portuguese | `ru` | Russian |
| `it` | Italian | `ar` | Arabic |
| `tr` | Turkish | `hi` | Hindi |
| `th` | Thai | `vi` | Vietnamese |

**Sample Translation:**

| Indonesian Input | Final English Prompt |
|---|---|
| `wanita cantik memakai kimono di malam hari` | `beautiful woman wearing kimono at night, cinematic lighting, high quality, detailed` |

**Presets:**

| Quality | Style | Auto Negative |
|---|---|---|
| `normal` — Standard | `none` — No style | `normal` — Basic |
| `high` — Better details | `anime` · `realistic` · `cinematic` | `strong` — Reduced artifacts |
| `ultra` — Maximum | `photography` · `product` · `fantasy` · `portrait` | `ultra` — Maximum cleanup |

> 💡 **Tips:**
> * Use `show_original` to debug translations
> * Enable `enable_cache` for faster workflows
> * Use `ultra` quality for SDXL and Flux
> * Use `anime` preset for anime models
> * Use `realistic` or `photography` for realism models

**Sample Workflow**

<div align="center">
  <img width="570" alt="Workflow" src="https://github.com/user-attachments/assets/44a6aeb5-1b15-4461-be2c-ec98291ac2e9" />
  <br><br>
  <img width="900" alt="Workflow detail" src="https://github.com/user-attachments/assets/36b098b9-4a4e-4787-aaea-8f249674a151" />
</div>

</details>

---

<details>
<summary><b>⚙️ Customization UI & Settings</b> (Click to Open)</summary>

The HW Monitor integrates directly with the ComfyUI Settings panel. All changes apply **instantly** — no browser reload required.

<div align="center">
  <img width="246" height="237" alt="Settings Menu" src="https://github.com/user-attachments/assets/57bab366-c238-4653-8580-bd5c9cae3a61" />
</div>

| Setting | Type | Options |
|---|---|---|
| **🎨 Theme** | Combo | Default Green · Neon Blue · Crimson Red · Hacker (Black & Green) |
| **⏱️ Refresh Rate** | Combo | 500ms · 1s · 2s |
| **👁️ Show on Startup** | Boolean | On / Off |
| **🔲 Background Opacity** | Slider | 0.1 – 1.0 (step 0.05) |
| **📦 Compact Mode** | Boolean | Hide sparkline graph for minimal footprint |

Access the settings by clicking the **⚙ gear icon** on the HW Monitor widget header.

**Theme Samples**

<div align="center">
  <img width="268" height="251" alt="Theme 1" src="https://github.com/user-attachments/assets/c9211c90-048f-4263-83b8-2a5cdc79a9d6" /> 
  <img width="266" height="252" alt="Theme 2" src="https://github.com/user-attachments/assets/066e7968-1df3-4cec-b9bf-98f9bda1d06c" /> 
  <img width="268" height="254" alt="Theme 3" src="https://github.com/user-attachments/assets/bf4e645f-b83f-41f9-99f5-49adaf63fafa" /> 
  <img width="269" height="253" alt="Theme 4" src="https://github.com/user-attachments/assets/030c8548-f47d-4871-b64a-a18b36d33fea" />
</div>

**Keyboard Shortcuts:**

| Action | Shortcut |
|---|---|
| Show / Hide Overlay | `Ctrl + Shift + M` |
| Minimize Widget | Click `−` button |
| Open Settings | Click `⚙` button |
| Reposition Widget | Drag the header bar |

</details>

---

<details>
<summary><b>🚀 Cara Instalasi</b> (Klik untuk membuka)</summary>

### 🔧 Instalasi Manual

```bash
cd ComfyUI/custom_nodes
git clone [https://github.com/Anonymzx/BangtrixToolkit.git](https://github.com/Anonymzx/BangtrixToolkit.git)
pip install -r BangtrixToolkit/requirements.txt
