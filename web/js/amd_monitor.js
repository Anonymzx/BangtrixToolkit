import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "Bangtrix.AMDMonitor",

    async setup() {

        const panel = document.createElement("div");

        panel.id = "bangtrix-amd-monitor";

        panel.style.position = "fixed";
        panel.style.top = "20px";
        panel.style.right = "20px";
        panel.style.width = "220px";
        panel.style.padding = "12px";
        panel.style.background = "rgba(20,20,20,0.9)";
        panel.style.color = "white";
        panel.style.fontSize = "14px";
        panel.style.borderRadius = "12px";
        panel.style.zIndex = "99999";
        panel.style.backdropFilter = "blur(10px)";
        panel.style.boxShadow = "0 0 10px rgba(0,0,0,0.5)";

        panel.innerHTML = `
            <h3 style="margin-top:0;">AMD Monitor 📊</h3>

            <div>GPU Usage: <span id="gpu_usage">0%</span></div>
            <div>VRAM: <span id="vram_usage">0 GB</span></div>
            <div>RAM: <span id="ram_usage">0 GB</span></div>
            <div>Timer: <span id="timer">0s</span></div>
        `;

        document.body.appendChild(panel);

        let seconds = 0;

        setInterval(() => {

            seconds++;

            document.getElementById("gpu_usage").innerText =
                Math.floor(Math.random() * 100) + "%";

            document.getElementById("vram_usage").innerText =
                (Math.random() * 16).toFixed(2) + " GB";

            document.getElementById("ram_usage").innerText =
                (Math.random() * 32).toFixed(2) + " GB";

            document.getElementById("timer").innerText =
                seconds + "s";

        }, 1000);
    }
});