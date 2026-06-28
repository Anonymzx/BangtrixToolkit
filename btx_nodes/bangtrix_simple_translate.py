import logging

import requests
import urllib.parse

logger = logging.getLogger(__name__)


class BangtrixSimpleTranslate:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(cls):
        # Daftar lengkap kode bahasa yang didukung oleh Google Translate
        languages = [
            "auto", "af", "sq", "am", "ar", "hy", "az", "eu", "be", "bn", "bs", "bg", "ca", "ceb", "ny", "zh-CN", "zh-TW", "co",
            "hr", "cs", "da", "nl", "en", "eo", "et", "tl", "fi", "fr", "fy", "gl", "ka", "de", "el", "gu", "ht", "ha", "haw",
            "iw", "hi", "hmn", "hu", "is", "ig", "id", "ga", "it", "ja", "jw", "kn", "kk", "km", "ko", "ku", "ky", "lo", "la",
            "lv", "lt", "lb", "mk", "mg", "ms", "ml", "mt", "mi", "mr", "mn", "my", "ne", "no", "ps", "fa", "pl", "pt", "pa",
            "ro", "ru", "sm", "gd", "sr", "st", "sn", "sd", "si", "sk", "sl", "so", "es", "su", "sw", "sv", "tg", "ta", "te",
            "th", "tr", "uk", "ur", "uz", "vi", "cy", "xh", "yi", "yo", "zu"
        ]
        
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": ""}),
                "source_language": (languages, {"default": "auto"}),
                "target_language": ([lang for lang in languages if lang != "auto"], {"default": "en"}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("translated_text",)
    FUNCTION = "do_translation"
    CATEGORY = "BangtrixToolkit"

    def do_translation(self, text, source_language, target_language):
        if not text.strip():
            return ("",)
        try:
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_language}&tl={target_language}&dt=t&q={urllib.parse.quote(text)}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                result = response.json()
                translated_text = "".join([sentence[0] for sentence in result[0] if sentence[0]])
                return (translated_text,)
            else:
                logger.warning("BangtrixToolkit: Translation API responded with status %s", response.status_code)
                return (text,)
        except Exception as e:
            logger.error("BangtrixToolkit: translation error: %s", e)
            return (text,)

# =========================================
# NODE MAPPINGS
# =========================================

NODE_CLASS_MAPPINGS = {
    "BangtrixSimpleTranslate": BangtrixSimpleTranslate
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BangtrixSimpleTranslate": "Bangtrix Simple Translate 🌐"
}