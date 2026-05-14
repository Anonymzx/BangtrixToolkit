import "./amd_monitor.css";

const panel = document.createElement("div");

panel.id = "bangtrix-amd-monitor";

panel.innerHTML = `
    <h3>Bangtrix AMD Monitor 📊</h3>

    <div class="bangtrix-item">
        GPU Usage: <span id="gpu_usage">Loading...</span>
    </div>

    <div class="bangtrix-item">
        VRAM: <span id="vram_usage">Loading...</span>
    </div>

    <div class="bangtrix-item">
        RAM: <span id="ram_usage">Loading...</span>
    </div>

    <div class="bangtrix-item">
        Timer: <span id="timer_usage">Loading...</span>
    </div>
`;

document.body.appendChild(panel);

function updateMonitor() {

    const ramUsed = (performance.memory?.usedJSHeapSize || 0) / 1024 / 1024;

    document.getElementById("gpu_usage").innerText =
        "AMD Active";

    document.getElementById("vram_usage").innerText =
        "Coming Soon";

    document.getElementById("ram_usage").innerText =
        ramUsed.toFixed(2) + " MB";

    document.getElementById("timer_usage").innerText =
        new Date().toLocaleTimeString();
}

setInterval(updateMonitor, 1000);