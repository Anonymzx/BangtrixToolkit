import time
import psutil

class BangtrixAMDMonitor:

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "refresh": ("BOOLEAN", {"default": True}),
            }
        }

    RETURN_TYPES = (
        "STRING",
        "STRING",
        "STRING",
        "STRING",
    )

    RETURN_NAMES = (
        "gpu_usage",
        "vram_usage",
        "ram_usage",
        "timer",
    )

    FUNCTION = "monitor"
    CATEGORY = "Bangtrix Toolkit/AMD"

    def monitor(self, refresh):

        gpu_usage = "AMD Monitoring Active"

        ram = psutil.virtual_memory()
        ram_usage = f"{ram.used / (1024**3):.2f} GB / {ram.total / (1024**3):.2f} GB"

        vram_usage = "VRAM Monitoring Coming Soon"

        timer = f"{time.time():.2f}"

        return (
            gpu_usage,
            vram_usage,
            ram_usage,
            timer,
        )


NODE_CLASS_MAPPINGS = {
    "BangtrixAMDMonitor": BangtrixAMDMonitor
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BangtrixAMDMonitor": "Bangtrix AMD Monitor 📊"
}