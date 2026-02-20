# BangtrixTranslateUniversal

ComfyUI custom node repository.

**BangtrixTranslateUniversal** is a **Custom Node for ComfyUI** that translates text from one language to another in real-time. This node is designed for AI generative workflows in ComfyUI that require multi-language prompts.

---

## 🌟 Key Features
- Automatic translation of positive and negative prompts.
- Supports multiple popular languages.
- Quality and style presets to enhance prompts.
- Auto-negative presets to reduce undesirable outputs.
- Translation caching for faster processing.
- Option to display original and translated text.

---

## 📝 Supported Languages

| Code   | Language |
|--------|---------|
| auto   | Auto-detect |
| id     | Indonesian |
| en     | English |
| ja     | Japanese |
| ko     | Korean |
| zh-CN  | Simplified Chinese |
| zh-TW  | Traditional Chinese |
| fr     | French |
| de     | German |
| es     | Spanish |
| pt     | Portuguese |
| ru     | Russian |
| it     | Italian |
| ar     | Arabic |
| tr     | Turkish |
| hi     | Hindi |
| th     | Thai |
| vi     | Vietnamese |

---

## 💻 Installation

1. Go to the `custom_nodes` folder in ComfyUI:

```bash
cd "F:\Program Files\ComfyUI\custom_nodes"
```
2. Clone the repository or copy the folder:

```bash
git clone https://github.com/Anonymzx/BangtrixTranslateUniversal.git
```
3. Restart ComfyUI. The node will appear automatically in the Custom Nodes panel.

---

## ⚙️ How to Use

1. Add the **BangtrixTranslateUniversal** node to your workflow.
2. Enter **positive** and **negative prompts**.
3. Select **source** and **target languages**.
4. Choose **quality preset** (`normal`, `high`, `ultra`) and **style preset** (`anime`, `realistic`, `cinematic`, etc.).
5. Enable the following options as needed:
   - **Enable Translate** → translate the text
   - **Enable Enhance** → add quality/style enhancements
   - **Enable Clean** → remove newlines
   - **Enable Cache** → use cached translations for speed
   - **Enable Auto Negative** → automatically apply negative prompt presets
6. Run the workflow → outputs:
   - **positive_conditioning**
   - **negative_conditioning**
   - **positive_prompt_final**
   - **negative_prompt_final**

---

## 🔧 Presets

### Quality Preset
- `normal`
- `high`
- `ultra`

### Style Preset
- `none`
- `anime`
- `realistic`
- `cinematic`
- `photography`
- `product`
- `fantasy`
- `portrait`

### Auto Negative Strength
- `normal`
- `strong`
- `ultra`

---

## ⚡ Tips
- Use **show_original** to see both original and translated text.
- Enable **enable_cache** to avoid repeated translation requests.
- Ideal for multi-language workflows and AI generative prompts.

---

# Sample

<img width="570" height="792" alt="image" src="https://github.com/user-attachments/assets/44a6aeb5-1b15-4461-be2c-ec98291ac2e9" />

<img width="1800" height="1121" alt="image" src="https://github.com/user-attachments/assets/36b098b9-4a4e-4787-aaea-8f249674a151" />













