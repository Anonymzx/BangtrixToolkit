import json
import urllib.parse
import urllib.request
import hashlib
from nodes import CLIPTextEncode

_translate_cache = {}

LANGUAGES = [
    "auto","id","en","ja","ko","zh-CN","zh-TW",
    "fr","de","es","pt","ru","it","ar","tr","hi","th","vi"
]

QUALITY_MAP = {
    "normal": "",
    "high": "high quality, detailed, sharp focus",
    "ultra": "ultra high quality, extremely detailed, 8k, sharp focus"
}

STYLE_MAP = {
    "none": "",
    "anime": "anime style, clean lineart, vibrant colors",
    "realistic": "photorealistic, natural lighting",
    "cinematic": "cinematic lighting, dramatic shadows",
    "photography": "professional photography, depth of field",
    "product": "product photography, studio lighting, clean background",
    "fantasy": "fantasy art, magical atmosphere",
    "portrait": "portrait photography, detailed face"
}

AUTO_NEGATIVE_BASE = {
    "normal": "low quality, blurry, watermark, text",
    "strong": "low quality, worst quality, blurry, bad anatomy, bad hands, extra fingers, watermark, text, logo, artifacts",
    "ultra": "low quality, worst quality, blurry, bad anatomy, bad hands, extra fingers, deformed, distorted, watermark, text, logo, artifacts, jpeg artifacts"
}

STYLE_NEG_EXTRA = {
    "portrait": "bad eyes, asymmetrical face, distorted face",
    "anime": "bad proportions, extra limbs",
    "realistic": "plastic skin, overexposed, underexposed",
    "photography": "noise, chromatic aberration",
    "cinematic": "flat lighting",
    "product": "dirty background",
    "fantasy": "",
    "none": ""
}

def google_translate(text, src, dst):
    try:
        url = (
            "https://translate.googleapis.com/translate_a/single"
            "?client=gtx"
            f"&sl={src}&tl={dst}&dt=t&q={urllib.parse.quote(text)}"
        )
        with urllib.request.urlopen(url, timeout=5) as r:
            data = json.loads(r.read())
        return "".join([i[0] for i in data[0]])
    except:
        return text

def process_text(text, src, dst, enable_translate, enable_clean, enable_cache):
    original = text.strip()
    key = hashlib.md5(f"{src}:{dst}:{original}".encode()).hexdigest()

    if enable_translate:
        if enable_cache and key in _translate_cache:
            translated = _translate_cache[key]
        else:
            translated = google_translate(original, src, dst)
            if enable_cache:
                _translate_cache[key] = translated
    else:
        translated = original

    if enable_clean:
        translated = translated.replace("\n", ", ")

    return original, translated

class BangtrixTranslateUniversal:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "clip": ("CLIP",),
                "positive_prompt": ("STRING", {"multiline": True}),
                "negative_prompt": ("STRING", {"multiline": True}),
                "source_language": (LANGUAGES,),
                "target_language": (LANGUAGES,),
                "quality_preset": (list(QUALITY_MAP.keys()),),
                "style_preset": (list(STYLE_MAP.keys()),),
                "enable_translate": ("BOOLEAN", {"default": True}),
                "enable_enhance": ("BOOLEAN", {"default": True}),
                "enable_clean": ("BOOLEAN", {"default": True}),
                "enable_cache": ("BOOLEAN", {"default": True}),
                "enable_auto_negative": ("BOOLEAN", {"default": True}),
                "auto_negative_strength": (list(AUTO_NEGATIVE_BASE.keys()),),
                "show_original": ("BOOLEAN", {"default": False}),
            }
        }

    RETURN_TYPES = ("CONDITIONING","CONDITIONING","STRING","STRING")
    RETURN_NAMES = (
        "positive_conditioning",
        "negative_conditioning",
        "positive_prompt_final",
        "negative_prompt_final"
    )
    FUNCTION = "process"
    CATEGORY = "Bangtrix Toolkit"

    def process(
        self,
        clip,
        positive_prompt,
        negative_prompt,
        source_language,
        target_language,
        quality_preset,
        style_preset,
        enable_translate,
        enable_enhance,
        enable_clean,
        enable_cache,
        enable_auto_negative,
        auto_negative_strength,
        show_original
    ):
        # POSITIVE
        pos_orig, pos_trans = process_text(
            positive_prompt,
            source_language,
            target_language,
            enable_translate,
            enable_clean,
            enable_cache,
        )

        pos_parts = [pos_trans]

        if enable_enhance:
            if STYLE_MAP[style_preset]:
                pos_parts.append(STYLE_MAP[style_preset])
            if QUALITY_MAP[quality_preset]:
                pos_parts.append(QUALITY_MAP[quality_preset])

        positive_final = ", ".join(pos_parts)

        if show_original:
            positive_final = f"[ORIGINAL]: {pos_orig} | [TRANSLATED]: {positive_final}"

        positive_cond = CLIPTextEncode().encode(clip, positive_final)[0]

        # NEGATIVE
        neg_orig, neg_trans = process_text(
            negative_prompt,
            source_language,
            target_language,
            enable_translate,
            enable_clean,
            enable_cache,
        )

        neg_parts = []

        if neg_trans.strip():
            neg_parts.append(neg_trans)

        if enable_auto_negative:
            neg_parts.append(AUTO_NEGATIVE_BASE[auto_negative_strength])
            extra = STYLE_NEG_EXTRA.get(style_preset, "")
            if extra:
                neg_parts.append(extra)

        negative_final = ", ".join(neg_parts)

        if show_original:
            negative_final = f"[ORIGINAL]: {neg_orig} | [TRANSLATED]: {negative_final}"

        negative_cond = CLIPTextEncode().encode(clip, negative_final)[0]

        return (
            positive_cond,
            negative_cond,
            positive_final,
            negative_final
        )

NODE_CLASS_MAPPINGS = {
    "BangtrixTranslateUniversal": BangtrixTranslateUniversal
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BangtrixTranslateUniversal": "Bangtrix Translate Universal 🌐"
}
