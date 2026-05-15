"""
Quick test script for AMD Monitor backend
Run: python_embeded\python.exe test_amd_monitor.py
"""

import sys
import os

# Add project to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

print("=== BANGTRIXTOOLKIT AMD Monitor Test ===\n")

# Test 1: Import utils
print("1. Testing amd_utils import...")
try:
    from utils.amd_utils import get_amd_monitor, AMDGPUStats
    print("   ✅ amd_utils imported")
except Exception as e:
    print(f"   ❌ amd_utils import failed: {e}")
    sys.exit(1)

# Test 2: Initialize monitor
print("\n2. Initializing AMD monitor...")
monitor = get_amd_monitor()
print(f"   Available: {monitor.available}")
print(f"   Method: {monitor.method}")
print(f"   GPU Count: {monitor.gpu_count}")

# Test 3: Get stats
if monitor.available:
    print("\n3. Fetching GPU stats...")
    stats = monitor.get_gpu_stats(0)
    print(f"   GPU ID: {stats.gpu_id}")
    print(f"   Utilization: {stats.utilization_gpu}%")
    print(f"   VRAM: {stats.memory_used / 1024 / 1024:.0f} MB / {stats.memory_total / 1024 / 1024:.0f} MB")
    print(f"   Temperature: {stats.temperature}°C")
    print(f"   Fan: {stats.fan_speed}%")
    print(f"   Status: {'✅ OK' if stats.is_available else '❌ Error: ' + str(stats.error_message)}")
else:
    print("\n⚠️ AMD backend not available - check requirements & drivers")

# Test 4: Check dependencies
print("\n4. Dependency check:")
deps = ['aiohttp', 'psutil', 'pyadl', 'pyrsmi']
for dep in deps:
    try:
        __import__(dep)
        ver = getattr(__import__(dep), '__version__', 'unknown')
        print(f"   ✅ {dep}: {ver}")
    except ImportError:
        print(f"   ⚪ {dep}: not installed")

print("\n=== Test Complete ===")