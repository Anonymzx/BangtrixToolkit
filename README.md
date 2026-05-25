<div align="center">

# 🚀 BangtrixToolkit

**Essential Custom Nodes for ComfyUI**

[![ComfyUI](https://img.shields.io/badge/ComfyUI-Custom_Node-FF6B6B?style=flat-square)](https://github.com/comfyanonymous/ComfyUI)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python)](https://python.org)
[![License](https://img.shields.io/github/license/Anonymzx/BangtrixToolkit?style=flat-square)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Anonymzx/BangtrixToolkit?style=flat-square)](https://github.com/Anonymzx/BangtrixToolkit/stargazers)

A powerful toolkit for ComfyUI featuring a **real-time Hardware Monitor overlay** with native **AMD/NVIDIA GPU/APU** support, and a **Universal Prompt Translator** node — all in one clean package.

</div>

---

<details>
<summary><b>✨ Key Features</b> (Click to Collapse)</summary>
<br>

# 🖥️ Advanced HW Monitor

A real-time monitoring overlay displayed directly on the ComfyUI canvas. Tracks **GPU Name**, **Load (%)**, **VRAM Usage**, **Temperature (°C)**, and **Fan Speed (%)** with animated progress bars and a live sparkline graph. The widget is fully draggable, minimizable, and toggleable via `Ctrl + Shift + M`.

### 🔥 New Quality of Life Additions:
* 🧹 **One-Click Memory Flush:** Instantly free up VRAM and System RAM directly from the overlay using the clear button. It safely unloads all idle models, clears the PyTorch cache, and triggers Python garbage collection—saving you from Out of Memory (OOM) errors before running heavy upscale workflows.
* ⚡ **Smart ROCm Smoothing:** Uses an ultra-responsive 500ms polling rate coupled with a custom "Peak Hold / Max Aggregate" algorithm. This ensures accurate tracking of *bursty* AI compute workloads across all GPU engines, completely eliminating the inaccurate "0% usage drops" commonly seen in standard Windows Task Manager monitoring.

<br>

<div align="center">
<img width="264" height="258" alt="image" src="https://github.com/user-attachments/assets/4e5fb35c-8cf3-4ff9-9a33-1d216d84b674" />
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

<img width="272" height="387" alt="image" src="https://github.com/user-attachments/assets/e1e187f2-e967-4dd8-86c0-5a6d211a5c0c" />

<br>

| Setting | Type | Options |
|---------|------|---------|
| **🌗 Base Mode** | Combo | Dark · Light |
| **🎨 Theme** | Combo | Default Green · Neon Blue · Crimson Red · Hacker (Black & Green) · Custom Colors|
| **⏱️ Refresh Rate** | Combo | 500ms · 1s · 2s |
| **👁️ Show on Startup** | Boolean | On / Off |
| **🔲 Background Opacity** | Slider | 0.1 – 1.0 (step 0.05) |
| **📦 Compact Mode** | Boolean | Hides sparkline graph for minimal footprint |
| **👻 Ghost Mode** | Boolean | Makes the background completely invisible/transparent |
| **🔍 UI Scale** | Slider | 0.5x (50%) – 2.0x (200%), step 0.1 — Zoom the entire widget for high-DPI (4K) displays or improved readability |

Access the settings by clicking the **⚙ gear icon** on the HW Monitor widget header.

<br><br>

# 🎨 Theme Samples, Compact Mode, and Ghost Mode

<div align="center">
 
 **Themes** <br>
 <img width="267" height="258" alt="image" src="https://github.com/user-attachments/assets/75bca8f7-102c-4fb1-b162-e660d7e18c82" />
 <img width="265" height="259" alt="image" src="https://github.com/user-attachments/assets/483666da-2cfc-40c3-9a83-cf1d2b7e9cee" />
 <img width="266" height="255" alt="image" src="https://github.com/user-attachments/assets/9cfb34da-57ad-401f-b479-23d67d5e5096" />
 <img width="265" height="258" alt="image" src="https://github.com/user-attachments/assets/741af102-6229-485c-9abd-1f2d95c7af83" />
 <img width="265" height="258" alt="image" src="https://github.com/user-attachments/assets/d60f3bbc-4607-4231-948a-1d6faad4d61f" />
 <img width="266" height="258" alt="image" src="https://github.com/user-attachments/assets/3cbb7cd0-ecd9-438d-968b-35e2f1a1efe2" />
 <img width="267" height="258" alt="image" src="https://github.com/user-attachments/assets/b6ca2afe-5bc9-47a1-afc3-8bd469fe67da" />
 <br> <br>
 **Base Theme Light** <br>
 <img width="266" height="265" alt="image" src="https://github.com/user-attachments/assets/f01227ec-e75f-4544-b9bf-cb4bd0727ca2" />
 <br> <br>
 **Custom Themes** <br>
 <img width="538" height="584" alt="image" src="https://github.com/user-attachments/assets/2ef3fb6a-a081-469d-8d49-777f0320d1e0" />
 <br> <br>
**Compact Mode** <br>
<img width="264" height="216" alt="image" src="https://github.com/user-attachments/assets/72419998-dcab-4c60-b688-5cde627d342b" />
 <br> <br>
**Ghost Mode/invisble Background** <br>
<img width="269" height="264" alt="image" src="https://github.com/user-attachments/assets/ac7d0d2b-f5ca-4a76-902a-bd6b9665a366" />
</div>

<br><br>

## ⌨️ Keyboard Shortcuts & Actions

| Action | Control |
|--------|----------|
| Show / Hide Overlay | `Ctrl + Shift + M` |
| Minimize Widget | Click `−` button |
| Open Settings | Click `⚙` button |
| **Flush VRAM & RAM** | **Click 🧹 Clear button** |
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
<summary><b>⚠️ Compatibility, Testing & Bug Reports</b> (Click to Expand)</summary>

<br>

🧪 **Hardware Testing Status:**

✅ **AMD Radeon™ RX 7800 XT (RDNA3) & Ryzen™ APUs:** Explicitly tested and verified natively by the author.

✅ **NVIDIA GPUs:** Successfully tested and verified to work flawlessly by a community user on [Reddit](https://www.reddit.com/r/comfyui/comments/1tjtn9b/built_an_incanvas_hardware_monitor_prompt/?utm_source=share&utm_medium=web3x&utm_name=web3xcss&utm_term=1&utm_content=share_button) (Tested on **RTX 3090 / Linux**)!

⏳ **Intel ARC / iGPU & Legacy AMD:** Implemented via official APIs, currently awaiting community feedback.

<br>

🤝 **Call for Feedback (NVIDIA, Intel & Other AMD GPUs):**
Since this toolkit was developed and explicitly tested on the specific AMD hardware above, the integrations for NVIDIA, Intel, and other AMD GPUs (like RDNA2, Vega, Polaris) are implemented based on official APIs (NVML, sysfs, PDH, ADL).

If you are using an NVIDIA GPU, an Intel ARC/iGPU, or other AMD GPUs and encounter any issues (such as N/A values, missing sensors, or graphical glitches), please open an issue on GitHub. Kindly include:

> A screenshot of the HW Monitor overlay.
> 
> Your ComfyUI terminal log (showing the backend initialization).

Your feedback is highly appreciated to help patch and perfect the monitoring experience for everyone!

---

**Why install AMD ROCm / HIP SDK?**

Windows restricts direct access to **temperature** and **fan speed** sensors on most AMD GPUs. To allow the HW Monitor to extract these values natively without relying on bloated third-party background apps, installing the **AMD ROCm / HIP SDK** is highly recommended for the general AMD ecosystem.

📥 **Download:** [AMD ROCm HIP SDK](https://www.amd.com/en/developer/resources/rocm-hub/hip-sdk.html)

After installation, the backend will automatically detect `hipInfo.exe` and `amd-smi` through the `HIP_PATH` environment variable and combine it with live Windows PDH data.

---

🚨 **Current RDNA3 (RX 7000 Series) Limitation:**

While the ROCm backend works flawlessly for extracting advanced metrics, please note that **as of the current Windows drivers, AMD's RDNA3 architecture strictly locks thermal extraction via native APIs**. 

If you are using an RX 7000 series GPU, you will reliably get **GPU Name**, **GPU Load**, and **VRAM Usage**, but thermal sensors (Temp/Fan) will temporarily output `N/A` even with ROCm installed.

*We have integrated the native ROCm backend to future-proof your setup. Once AMD releases a driver patch that unlocks this API for Windows, your Temp and Fan readings will automatically spring to life without needing to update this node!*

</details>

<div align="left">

### 💖 [Support This Project](https://ko-fi.com/anonymzx)

If you find this toolkit useful and it improves your ComfyUI workflow, consider supporting its development!

### ❤️ Created by [Anonymzx](https://github.com/Anonymzx)
