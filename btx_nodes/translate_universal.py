import json
import hashlib
import requests

from nodes import CLIPTextEncode

# =========================================
# CACHE
# =========================================

_translate_cache = {}

# =========================================
# LANGUAGES
# =========================================

LANGUAGES = [
    "auto",
    "id",
    "en",
    "ja",
    "ko",
    "zh-CN",
    "zh-TW",
    "fr",
    "de",
    "es",
    "pt",
    "ru",
    "it",
    "ar",
    "tr",
    "hi",
    "th",
    "vi",
]

# =========================================
# QUALITY PRESETS
# =========================================

QUALITY_MAP = {
    "normal": "",
    "high": "high quality, detailed, sharp focus",
    "ultra": "ultra high quality, extremely detailed, 8k, sharp focus",
}

# =========================================
# STYLE PRESETS
# =========================================

STYLE_MAP = {
    "none": "",
    "anime": "anime style, clean lineart, vibrant colors",
    "realistic": "photorealistic, natural lighting",
    "cinematic": "cinematic lighting, dramatic shadows",
    "photography": "professional photography, depth of field",
    "product": "product photography, studio lighting, clean background",
    "fantasy": "fantasy art, magical atmosphere",
    "portrait": "portrait photography, detailed face",
}

# =========================================
# AUTO NEGATIVE
# =========================================

AUTO_NEGATIVE_BASE = {
    "normal": (
        "low quality, blurry, watermark, text"
    ),

    "strong": (
        "low quality, worst quality, blurry, bad anatomy, "
        "bad hands, extra fingers, watermark, text, logo, artifacts"
    ),

    "ultra": (
        "low quality, worst quality, blurry, bad anatomy, "
        "bad hands, extra fingers, deformed, distorted, "
        "watermark, text, logo, artifacts, jpeg artifacts"
    ),
}

STYLE_NEG_EXTRA = {
    "portrait": "bad eyes, asymmetrical face, distorted face",
    "anime": "bad proportions, extra limbs",
    "realistic": "plastic skin, overexposed, underexposed",
    "photography": "noise, chromatic aberration",
    "cinematic": "flat lighting",
    "product": "dirty background",
    "fantasy": "",
    "none": "",
}

# =========================================
# GOOGLE TRANSLATE
# =========================================

def google_translate(text, src, dst):
    try:
        url = "https://translate.googleapis.com/translate_a/single"

        params = {
            "client": "gtx",
            "sl": src,
            "tl": dst,
            "dt": "t",
            "q": text
        }

        response = requests.get(
            url,
            params=params,
            timeout=10
        )

        data = response.json()

        return "".join([x[0] for x in data[0]])

    except Exception:
        return text

# =========================================
# PROCESS TEXT
# =========================================

def process_text(
    text,
    src,
    dst,
    enable_translate,
    enable_clean,
    enable_cache
):
    original = text.strip()

    if not original:
        return "", ""

    key = hashlib.md5(
        f"{src}:{dst}:{original}".encode()
    ).hexdigest()

    # TRANSLATE
    if enable_translate:

        if enable_cache and key in _translate_cache:
            translated = _translate_cache[key]

        else:
            translated = google_translate(
                original,
                src,
                dst
            )

            if enable_cache:
                _translate_cache[key] = translated

    else:
        translated = original

    # CLEAN
    if enable_clean:
        translated = translated.replace("\n", ", ")

    return original, translated

# =========================================
# MAIN NODE
# =========================================

class BangtrixTranslateUniversal:

    @classmethod
    def INPUT_TYPES(cls):

        return {
            "required": {

                "clip": ("CLIP",),

                "positive_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": ""
                    }
                ),

                "negative_prompt": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": ""
                    }
                ),

                "source_language": (
                    LANGUAGES,
                    {
                        "default": "auto"
                    }
                ),

                "target_language": (
                    LANGUAGES,
                    {
                        "default": "en"
                    }
                ),

                "quality_preset": (
                    list(QUALITY_MAP.keys()),
                    {
                        "default": "high"
                    }
                ),

                "style_preset": (
                    list(STYLE_MAP.keys()),
                    {
                        "default": "none"
                    }
                ),

                "enable_translate": (
                    "BOOLEAN",
                    {
                        "default": True
                    }
                ),

                "enable_enhance": (
                    "BOOLEAN",
                    {
                        "default": True
                    }
                ),

                "enable_clean": (
                    "BOOLEAN",
                    {
                        "default": True
                    }
                ),

                "enable_cache": (
                    "BOOLEAN",
                    {
                        "default": True
                    }
                ),

                "enable_auto_negative": (
                    "BOOLEAN",
                    {
                        "default": True
                    }
                ),

                "auto_negative_strength": (
                    list(AUTO_NEGATIVE_BASE.keys()),
                    {
                        "default": "strong"
                    }
                ),

                "show_original": (
                    "BOOLEAN",
                    {
                        "default": False
                    }
                ),
            }
        }

    RETURN_TYPES = (
        "CONDITIONING",
        "CONDITIONING",
        "STRING",
        "STRING"
    )

    RETURN_NAMES = (
        "positive_conditioning",
        "negative_conditioning",
        "positive_prompt_final",
        "negative_prompt_final"
    )

    FUNCTION = "process"

    CATEGORY = "Bangtrix Toolkit/Translate"

    # =========================================
    # PROCESS
    # =========================================

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

        # =========================================
        # POSITIVE
        # =========================================

        pos_orig, pos_trans = process_text(
            positive_prompt,
            source_language,
            target_language,
            enable_translate,
            enable_clean,
            enable_cache,
        )

        pos_parts = []

        if pos_trans.strip():
            pos_parts.append(pos_trans)

        # ENHANCE
        if enable_enhance:

            style_text = STYLE_MAP.get(
                style_preset,
                ""
            )

            quality_text = QUALITY_MAP.get(
                quality_preset,
                ""
            )

            if style_text:
                pos_parts.append(style_text)

            if quality_text:
                pos_parts.append(quality_text)

        positive_final = ", ".join(pos_parts)

        # SAFETY
        if not positive_final.strip():
            positive_final = "masterpiece"

        # SHOW ORIGINAL
        if show_original:
            positive_final = (
                f"[ORIGINAL]: {pos_orig} "
                f"| [TRANSLATED]: {positive_final}"
            )

        # CLIP ENCODE
        positive_cond = CLIPTextEncode().encode(
            clip,
            positive_final
        )[0]

        # =========================================
        # NEGATIVE
        # =========================================

        neg_orig, neg_trans = process_text(
            negative_prompt,
            source_language,
            target_language,
            enable_translate,
            enable_clean,
            enable_cache,
        )

        neg_parts = []

        # USER NEGATIVE
        if neg_trans.strip():
            neg_parts.append(neg_trans)

        # AUTO NEGATIVE
        if enable_auto_negative:

            neg_parts.append(
                AUTO_NEGATIVE_BASE[
                    auto_negative_strength
                ]
            )

            style_extra = STYLE_NEG_EXTRA.get(
                style_preset,
                ""
            )

            if style_extra:
                neg_parts.append(style_extra)

        negative_final = ", ".join(neg_parts)

        # SAFETY
        if not negative_final.strip():
            negative_final = "low quality"

        # SHOW ORIGINAL
        if show_original:
            negative_final = (
                f"[ORIGINAL]: {neg_orig} "
                f"| [TRANSLATED]: {negative_final}"
            )

        # CLIP ENCODE
        negative_cond = CLIPTextEncode().encode(
            clip,
            negative_final
        )[0]

        # =========================================
        # RETURN
        # =========================================

        return (
            positive_cond,
            negative_cond,
            positive_final,
            negative_final
        )

# =========================================
# NODE MAPPINGS
# =========================================

NODE_CLASS_MAPPINGS = {
    "BangtrixTranslateUniversal": BangtrixTranslateUniversal
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BangtrixTranslateUniversal":
        "Bangtrix Translate Universal 🌐"
}