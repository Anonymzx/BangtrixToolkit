# BangtrixToolkit

Advanced Custom Node Toolkit for ComfyUI focused on:
- AI Prompt Translation
- AMD ROCm Utilities
- Workflow Enhancements
- Performance Utilities

---
<details close>
<summary>

# 🌐 Bangtrix Translate Universal

</summary>

Bangtrix Translate Universal is an advanced translation node for ComfyUI that automatically translates prompts into English and directly outputs them into CLIP conditioning.

Designed for:
- Stable Diffusion
- Flux
- SDXL
- Pony
- Anime Models
- Realistic Models
- Any CLIP-based workflow

---

# ✨ Features

## 🌍 Translation
- Automatic Google Translate integration
- Multi-language support
- Real-time prompt translation
- Offline-safe fallback

---

## 🧠 Prompt Enhancement
- Quality presets
- Style presets
- Prompt cleaning
- Prompt enhancement system

---

## ❌ Auto Negative
Automatically generates optimized negative prompts.

Supports:
- anatomy fixes
- blur reduction
- watermark filtering
- artifact reduction
- style-based negatives

---

## ⚡ Performance
- Translation cache system
- Fast repeated translation
- Lightweight architecture
- Universal model compatibility

---

# 📝 Supported Languages

| Code | Language |
|------|------|
| auto | Auto Detect |
| id | Indonesian |
| en | English |
| ja | Japanese |
| ko | Korean |
| zh-CN | Simplified Chinese |
| zh-TW | Traditional Chinese |
| fr | French |
| de | German |
| es | Spanish |
| pt | Portuguese |
| ru | Russian |
| it | Italian |
| ar | Arabic |
| tr | Turkish |
| hi | Hindi |
| th | Thai |
| vi | Vietnamese |

---

# 🎨 Quality Presets

| Preset | Description |
|------|------|
| normal | Standard quality enhancement |
| high | Better details and sharpness |
| ultra | Maximum quality enhancement |

---

# 🎭 Style Presets

| Style | Description |
|------|------|
| none | No style enhancement |
| anime | Anime style optimization |
| realistic | Realistic photography enhancement |
| cinematic | Cinematic lighting and shadows |
| photography | Professional photography style |
| product | Product photography optimization |
| fantasy | Fantasy art enhancement |
| portrait | Portrait optimization |

---

# ❌ Auto Negative Strength

| Strength | Description |
|------|------|
| normal | Basic negative prompt |
| strong | Improved artifact reduction |
| ultra | Maximum cleanup and artifact filtering |

---
</details>

# 📦 Installation

## Manual Installation

Go to your ComfyUI custom_nodes folder:

```bash
cd "ComfyUI/custom_nodes"
```

Clone repository:

```bash
git clone https://github.com/Anonymzx/BangtrixToolkit.git
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Restart ComfyUI.

---

# 🧩 Installation via ComfyUI Manager

1. Open ComfyUI
2. Open ComfyUI Manager
3. Open:
   - Custom Nodes Manager
4. Search:
   - BangtrixToolkit
5. Click:
   - Install
6. Restart ComfyUI

---

# ⚙️ Node Inputs

| Input | Description |
|------|------|
| positive_prompt | Positive prompt |
| negative_prompt | Negative prompt |
| source_language | Original language |
| target_language | Translation target language |
| quality_preset | Quality enhancement |
| style_preset | Style enhancement |
| enable_translate | Enable translation |
| enable_enhance | Enable prompt enhancement |
| enable_clean | Clean newline formatting |
| enable_cache | Enable translation cache |
| enable_auto_negative | Enable automatic negative prompts |
| auto_negative_strength | Auto negative strength |
| show_original | Show original + translated text |

---

# 📤 Outputs

| Output | Description |
|------|------|
| positive_conditioning | CLIP positive conditioning |
| negative_conditioning | CLIP negative conditioning |
| positive_prompt_final | Final translated positive prompt |
| negative_prompt_final | Final translated negative prompt |

---

# 🔥 Workflow Example

## Indonesian Input

```text
wanita cantik memakai kimono di malam hari
```

## Final English Prompt

```text
beautiful woman wearing kimono at night, cinematic lighting, high quality, detailed
```

---

# 💡 Tips

- Use `show_original` to debug translations
- Enable `enable_cache` for faster workflows
- Use `ultra` quality for SDXL and Flux
- Use `anime` preset for anime models
- Use `realistic` or `photography` for realism models

---

# 🖼️ Preview

## Node Preview

<img width="570" height="792" alt="image" src="https://github.com/user-attachments/assets/44a6aeb5-1b15-4461-be2c-ec98291ac2e9" />

---

## Workflow Preview

<img width="1800" height="1121" alt="image" src="https://github.com/user-attachments/assets/36b098b9-4a4e-4787-aaea-8f249674a151" />

---

# 📁 Project Structure

```text
BangtrixToolkit/
│
├── nodes/
│   └── translate_universal.py
│
├── utils/
├── web/
├── workflows/
│
├── __init__.py
├── requirements.txt
├── README.md
├── LICENSE
└── .gitignore
```

---

# 🚀 Roadmap

## v1
- Bangtrix Translate Universal

## v2
- AMD Monitor
- ROCm Utilities

## v3
- Smart Cache
- Performance Optimizer
- Benchmark Tools

---

# ❤️ Credits

Created by:
- Anonymzx

Powered by:
- ComfyUI
- Google Translate API
- Python