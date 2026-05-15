from ..utils.amd_utils import get_amd_monitor


class AMDMonitorNode:
    """
    A node to monitor AMD GPU statistics.
    Outputs: GPU Usage (%), VRAM Used (MB), VRAM Total (MB), Temperature (C)
    """
    
    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "gpu_index": ("INT", {"default": 0, "min": 0, "max": 10, "step": 1}),
            }
        }

    RETURN_TYPES = ("FLOAT", "FLOAT", "FLOAT", "INT", "INT", "STRING")
    RETURN_NAMES = ("gpu_utilization", "vram_usage_pct", "temperature", "vram_used_mb", "vram_total_mb", "status_msg")
    FUNCTION = "monitor"
    CATEGORY = "BANGTRIXTOOLKIT/System"

    def monitor(self, gpu_index):
        monitor = get_amd_monitor()
        
        if not monitor.available:
            return (0.0, 0.0, 0.0, 0, 0, "Error: AMD Backend not found")

        stats = monitor.get_gpu_stats(gpu_index)
        
        if not stats.is_available:
            return (0.0, 0.0, 0.0, 0, 0, f"Error: {stats.error_message}")

        # Convert bytes to MB for easier reading
        vram_used_mb = stats.memory_used / (1024 * 1024)
        vram_total_mb = stats.memory_total / (1024 * 1024)
        
        status = "OK"
        
        return (
            float(stats.utilization_gpu),
            float(stats.utilization_memory),
            float(stats.temperature),
            int(vram_used_mb),
            int(vram_total_mb),
            status
        )


# Registry
NODE_CLASS_MAPPINGS = {
    "BANGTRIX_AMD_Monitor": AMDMonitorNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "BANGTRIX_AMD_Monitor": "AMD Monitor (BANGTRIX)"
}