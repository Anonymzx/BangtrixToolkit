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

<details>
<summary><b>✨ Key Features</b> (Click to Collapse)</summary>
<br>

# 🖥️ Advanced HW Monitor

A real-time monitoring overlay displayed directly on the ComfyUI canvas. Tracks **GPU Name**, **Load (%)**, **VRAM Usage**, **Temperature (°C)**, and **Fan Speed (%)** with animated progress bars and a live sparkline graph. The widget is fully draggable, minimizable, and toggleable via `Ctrl + Shift + M`.

<br>

<div align="center">
<img width="264" height="249" alt="image" src="https://github.com/user-attachments/assets/3967ee42-4f6e-40f7-b5fd-e55c21f719a4" />
</div>

<br>

# 🔌 Native AMD ROCm Support

An intelligent multi-backend architecture automatically detects your GPU vendor and selects the optimal data source.

| GPU | Platform | Primary Backend | Fallback |
|-----|----------|----------------|----------|
| **AMD RDNA3** (RX 7000+) | Windows | ROCm / HIP SDK (`hipInfo.exe`) + PDH | PowerShell / WMI |
| **Legacy AMD** | Windows | ADL (`atiadlxx.dll`) + PDH | PowerShell |
| **NVIDIA** | Windows / Linux | NVML / `nvidia-smi` | PDH / sysfs |
| **Intel ARC / iGPU** | Windows / Linux | PDH + sysfs | PowerShell / `hwmon` |

No third-party background applications are required — the backend relies only on native OS tools and your existing AMD driver stack.

<br>

# 🌐 Universal Prompt Translator

An integrated translation node that converts prompts from **16+ languages** into English and directly outputs CLIP conditioning.

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

<br>

## ✨ Sample Translation

| Indonesian Input | Final English Prompt |
|-----------------|---------------------|
| `wanita cantik memakai kimono di malam hari` | `beautiful woman wearing kimono at night, cinematic lighting, high quality, detailed` |

<br>

## 🎛️ Presets

| Quality | Style | Auto Negative |
|---------|-------|---------------|
| `normal` — Standard | `none` — No style | `normal` — Basic |
| `high` — Enhanced details | `anime` · `realistic` · `cinematic` | `strong` — Reduced artifacts |
| `ultra` — Maximum quality | `photography` · `product` · `fantasy` · `portrait` | `ultra` — Maximum cleanup |

> 💡 **Tips:** Use `show_original` to debug translations · Enable `enable_cache` for faster workflows · Use `ultra` quality for SDXL and Flux · Use the `anime` preset for anime models · Use `realistic` or `photography` for realism-based models

<br>

## 📸 Sample Workflow

<div align="center">
<img width="570" alt="Workflow" src="https://github.com/user-attachments/assets/44a6aeb5-1b15-4461-be2c-ec98291ac2e9" />
<br><br>
<img width="900" alt="Workflow detail" src="https://github.com/user-attachments/assets/36b098b9-4a4e-4787-aaea-8f249674a151" />
</div>

</details>

---

<details>
<summary><b>⚙️ Customization UI & Settings</b> (Click to Expand)</summary>
<br>

The HW Monitor integrates directly into the ComfyUI Settings panel. All changes are applied **instantly** — no browser reload required.

<br>

<img width="246" height="237" alt="image" src="https://github.com/user-attachments/assets/57bab366-c238-4653-8580-bd5c9cae3a61" />

<br>

| Setting | Type | Options |
|---------|------|---------|
| **🎨 Theme** | Combo | Default Green · Neon Blue · Crimson Red · Hacker (Black & Green) |
| **⏱️ Refresh Rate** | Combo | 500ms · 1s · 2s |
| **👁️ Show on Startup** | Boolean | On / Off |
| **🔲 Background Opacity** | Slider | 0.1 – 1.0 (step 0.05) |
| **📦 Compact Mode** | Boolean | Hides sparkline graph for minimal footprint |

Access the settings by clicking the **⚙ gear icon** on the HW Monitor widget header.

<br><br>

# 🎨 Theme Samples

<div align="center">
<img width="268" height="251" alt="image" src="https://github.com/user-attachments/assets/c9211c90-048f-4263-83b8-2a5cdc79a9d6" /> 
<img width="266" height="252" alt="image" src="https://github.com/user-attachments/assets/066e7968-1df3-4cec-b9bf-98f9bda1d06c" />
<img width="268" height="254" alt="image" src="https://github.com/user-attachments/assets/bf4e645f-b83f-41f9-99f5-49adaf63fafa" />
<img width="269" height="253" alt="image" src="https://github.com/user-attachments/assets/030c8548-f47d-4871-b64a-a18b36d33fea" />
</div>

<br><br>

## ⌨️ Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Show / Hide Overlay | `Ctrl + Shift + M` |
| Minimize Widget | Click `−` button |
| Open Settings | Click `⚙` button |
| Reposition Widget | Drag the header bar |

</details>

---

<details>
<summary><b>🚀 Installation Guide</b> (Click to Expand)</summary>
<br>

## 🔧 Manual Installation

```bash
cd ComfyUI/custom_nodes
git clone [https://github.com/Anonymzx/BangtrixToolkit.git](https://github.com/Anonymzx/BangtrixToolkit.git)
pip install -r BangtrixToolkit/requirements.txt

```
## 📥 Via ComfyUI Manager (Recommended)
 1. Open **ComfyUI Manager** inside ComfyUI
 2. Go to the **Custom Nodes Manager** tab
 3. Search for **BangtrixToolkit**
 4. Click **Install**
 5. **Restart** ComfyUI
> After restarting, the HW Monitor overlay will appear automatically — no additional node configuration is required.
> 
</details>

---

<details>
<summary><b>⚠️ Important Notes for AMD Users</b> (Click to Expand)</summary>

<br>

**Why install AMD ROCm / HIP SDK?**

Windows restricts direct access to **temperature** and **fan speed** sensors on most AMD GPUs. To allow the HW Monitor to extract these values natively without relying on bloated third-party background apps, installing the **AMD ROCm / HIP SDK** is highly recommended for the general AMD ecosystem.

📥 **Download:** [AMD ROCm HIP SDK](https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html)

After installation, the backend will automatically detect `hipInfo.exe` and `amd-smi` through the `HIP_PATH` environment variable and combine it with live Windows PDH data.

---

🧪 **Tested explicitly on:** **AMD Radeon™ RX 7800 XT (RDNA3)**

🚨 **Current RDNA3 (RX 7000 Series) Limitation:**

While the ROCm backend works flawlessly for extracting advanced metrics, please note that **as of the current Windows drivers, AMD's RDNA3 architecture strictly locks thermal extraction via native APIs**. 

If you are using an RX 7000 series GPU, you will reliably get **GPU Name**, **GPU Load**, and **VRAM Usage**, but thermal sensors (Temp/Fan) will temporarily output `N/A` even with ROCm installed.

*We have integrated the native ROCm backend to future-proof your setup. Once AMD releases a driver patch that unlocks this API for Windows, your Temp and Fan readings will automatically spring to life without needing to update this node!*

</details>

<div align="left">

### 💖 [Support This Project](https://trakteer.id/anonymzx)

If you find this toolkit useful and it improves your ComfyUI workflow, consider supporting its development!

### ❤️ Created by [Anonymzx](https://github.com/Anonymzx)
