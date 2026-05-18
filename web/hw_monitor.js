/**
 * BangtrixToolkit — Universal Hardware Monitor Overlay
 * ComfyUI Extension
 * 
 * Strategy: REST API polling via GET /bangtrix/hw/stats every 1s.
 * Fallback: WebSocket /ws/hw_monitor.
 * Toggle: Ctrl+Shift+M
 */

(function() {
    "use strict";

    console.log("🖥️ Bangtrix HW Monitor: loading...");

    // ========== STATE ==========
    let widget = null;
    let isMinimized = false;
    let isVisible = true;
    let isDragging = false;
    let dragStart = { x: 0, y: 0 };
    let pollInterval = null;
    let pollRetries = 0;
    const MAX_RETRIES = 30;  // 30 seconds max retry

    function $id(id) {
        const el = document.getElementById(id);
        if (!el) console.error("🖥️ DOM Element tidak ditemukan:", id);
        return el;
    }

    // ========== INIT ==========
    function init() {
        console.log("🖥️ Bangtrix HW Monitor: initializing...");
        
        // Cek duplikasi
        if (document.getElementById('bangtrix-hw-monitor')) {
            console.log("🖥️ Bangtrix HW Monitor: widget already exists, skipping");
            return;
        }

        buildWidget();
        bindEvents();
        
        // Cek apakah element DOM terbuat
        const checkEl = $id('hw-gpu-name');
        console.log("🖥️ Bangtrix HW Monitor: hw-gpu-name element:", checkEl ? "✅ found" : "❌ NOT FOUND");
        
        if (checkEl) {
            checkEl.textContent = "Loading...";
        }
        
        // Start REST polling
        startPolling();
    }

    // ========== WIDGET ==========
    function buildWidget() {
        console.log("🖥️ Bangtrix HW Monitor: building widget...");
        
        widget = document.createElement('div');
        widget.id = 'bangtrix-hw-monitor';

        widget.innerHTML = 
            '<div class="hw-header">' +
                '<span class="hw-icon">🖥️</span>' +
                '<span class="hw-title">HW Monitor</span>' +
                '<div class="hw-controls">' +
                    '<button class="hw-btn" id="hw-btn-min">−</button>' +
                    '<button class="hw-btn" id="hw-btn-close">✕</button>' +
                '</div>' +
            '</div>' +
            '<div class="hw-body">' +
                '<div class="hw-gpu-name" id="hw-gpu-name">Detecting...</div>' +
                '<div class="hw-vendor-line" id="hw-vendor-line"></div>' +
                '<div class="hw-grid">' +
                    '<div class="hw-stat"><div class="hw-stat-label">GPU</div><div class="hw-stat-value" id="hw-gpu-util">--</div><div class="hw-bar"><div class="hw-fill" id="hw-gpu-bar"></div></div></div>' +
                    '<div class="hw-stat"><div class="hw-stat-label">VRAM</div><div class="hw-stat-value" id="hw-vram">--</div><div class="hw-bar"><div class="hw-fill" id="hw-vram-bar"></div></div></div>' +
                    '<div class="hw-stat"><div class="hw-stat-label">Temp</div><div class="hw-stat-value" id="hw-temp">--</div><div class="hw-bar"><div class="hw-fill hw-temp-fill" id="hw-temp-bar"></div></div></div>' +
                    '<div class="hw-stat"><div class="hw-stat-label">Fan</div><div class="hw-stat-value" id="hw-fan">--</div><div class="hw-bar"><div class="hw-fill" id="hw-fan-bar"></div></div></div>' +
                '</div>' +
                '<div class="hw-sparkline-container">' +
                    '<canvas class="hw-sparkline" id="hw-sparkline" width="232" height="36"></canvas>' +
                '</div>' +
                '<div class="hw-status-bar">' +
                    '<span class="hw-status" id="hw-status">Starting...</span>' +
                    '<span class="hw-method" id="hw-method"></span>' +
                '</div>' +
            '</div>';

        // Inject CSS
        const css = document.createElement('style');
        css.textContent = 
            '#bangtrix-hw-monitor{position:fixed;top:60px;right:20px;width:260px;' +
            'background:rgba(18,18,24,0.92);border:1px solid rgba(100,150,255,0.3);border-radius:10px;' +
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;' +
            'color:#e0e0e0;z-index:99999;box-shadow:0 8px 32px rgba(0,0,0,0.4);' +
            'backdrop-filter:blur(8px);user-select:none;}' +
            '#bangtrix-hw-monitor.hidden{display:none}' +
            '#bangtrix-hw-monitor.minimized .hw-body{display:none}' +
            '.hw-header{display:flex;align-items:center;padding:8px 12px;gap:8px;cursor:move;' +
            'background:rgba(100,150,255,0.1);border-radius:10px 10px 0 0;border-bottom:1px solid rgba(255,255,255,0.04)}' +
            '.hw-icon{font-size:12px;animation:pulse 1.5s infinite}' +
            '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
            '.hw-title{flex:1;font-weight:600;font-size:12px;color:#fff}' +
            '.hw-controls{display:flex;gap:4px}' +
            '.hw-btn{background:rgba(255,255,255,0.08);border:none;color:#ccc;width:20px;height:20px;border-radius:4px;cursor:pointer;font-size:11px;line-height:20px;text-align:center}' +
            '.hw-btn:hover{background:rgba(255,255,255,0.2)}' +
            '.hw-btn-close:hover{background:rgba(220,60,60,0.4)!important}' +
            '.hw-body{padding:8px 12px 10px}' +
            '.hw-gpu-name{text-align:center;font-size:11px;font-weight:600;color:#66aaff;padding:4px 8px;' +
            'border-radius:4px;background:rgba(255,255,255,0.03);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
            '.hw-vendor-line{text-align:center;font-size:9px;color:#666;margin:2px 0 6px}' +
            '.hw-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px}' +
            '.hw-stat{display:flex;flex-direction:column;gap:1px}' +
            '.hw-stat-label{color:#666;font-size:9px;text-transform:uppercase}' +
            '.hw-stat-value{font-weight:600;font-size:12px;color:#00e676;transition:color 0.2s}' +
            '.hw-stat-value.warn{color:#ffaa00}' +
            '.hw-stat-value.crit{color:#ff4444}' +
            '.hw-bar{height:3px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden}' +
            '.hw-fill{height:100%;width:0%;background:#00e676;border-radius:2px;transition:width 0.3s ease}' +
            '.hw-fill.hw-temp-fill{background:linear-gradient(90deg,#00e676,#ffaa00,#ff4444)}' +
            '.hw-sparkline-container{margin-top:6px}' +
            '.hw-sparkline{width:100%;height:36px;border-radius:4px;background:rgba(0,0,0,0.2)}' +
            '.hw-status-bar{display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;' +
            'border-top:1px solid rgba(255,255,255,0.04);font-size:9px;color:#666}' +
            '.hw-status.live{color:#00e676;animation:livePulse 1.5s infinite}' +
            '.hw-status.err{color:#ff4444}' +
            '@keyframes livePulse{0%,100%{color:#00e676}50%{color:#00e67688}}';
        document.head.appendChild(css);
        document.body.appendChild(widget);
        
        console.log("🖥️ Bangtrix HW Monitor: widget built ✅");
        makeDraggable();
    }

    // ========== DRAG ==========
    function makeDraggable() {
        const header = widget.querySelector('.hw-header');
        if (!header) return;
        header.addEventListener('mousedown', function(e) {
            if (e.target.closest('.hw-btn')) return;
            isDragging = true;
            dragStart.x = e.clientX - widget.offsetLeft;
            dragStart.y = e.clientY - widget.offsetTop;
            widget.style.transition = 'none';
            document.body.style.cursor = 'grabbing';
            document.addEventListener('mousemove', onDrag);
            document.addEventListener('mouseup', stopDrag);
        });
        function onDrag(e) {
            if (!isDragging) return;
            const x = Math.max(10, Math.min(e.clientX - dragStart.x, window.innerWidth - widget.offsetWidth + 10));
            const y = Math.max(10, Math.min(e.clientY - dragStart.y, window.innerHeight - widget.offsetHeight + 10));
            widget.style.left = x + 'px';
            widget.style.top = y + 'px';
            widget.style.right = 'auto';
        }
        function stopDrag() {
            isDragging = false;
            widget.style.transition = '';
            document.body.style.cursor = '';
            document.removeEventListener('mousemove', onDrag);
            document.removeEventListener('mouseup', stopDrag);
        }
    }

    // ========== EVENTS ==========
    function bindEvents() {
        const minBtn = document.getElementById('hw-btn-min');
        if (minBtn) minBtn.onclick = function() {
            isMinimized = !isMinimized;
            widget.classList.toggle('minimized', isMinimized);
            this.textContent = isMinimized ? '+' : '−';
        };
        
        const closeBtn = document.getElementById('hw-btn-close');
        if (closeBtn) closeBtn.onclick = function() {
            isVisible = false;
            widget.classList.add('hidden');
            if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        };
        
        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.shiftKey && e.key === 'M') {
                e.preventDefault();
                isVisible = !isVisible;
                widget.classList.toggle('hidden', !isVisible);
                if (isVisible) startPolling();
            }
        });
    }

    // ========== REST POLLING (PRIMARY) ==========
    function startPolling() {
        console.log("🖥️ Bangtrix HW Monitor: starting REST polling...");
        setStatus("Connecting...", "");
        
        // Immediate first poll
        fetchStats();
        
        // Then every 1s
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(fetchStats, 1000);
        console.log("🖥️ Bangtrix HW Monitor: polling every 1000ms ✅");
    }

    function fetchStats() {
        fetch('/bangtrix/hw/stats')
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(data) {
                console.log("🖥️ Fetch HW data:", JSON.stringify(data).substring(0, 200) + "...");
                pollRetries = 0;
                
                if (data && data.type === 'hw_stats') {
                    setStatus("● LIVE", "live");
                    setMethod("REST 1s");
                    updateDisplay(data);
                } else {
                    console.warn("🖥️ Fetch HW data: unexpected format", data);
                }
            })
            .catch(function(err) {
                pollRetries++;
                console.warn("🖥️ Fetch HW error (" + pollRetries + "/" + MAX_RETRIES + "):", err.message);
                setStatus("Retry " + pollRetries, "err");
                setMethod("");
                
                // After 5 failed retries with REST, try WebSocket fallback
                if (pollRetries === 5) {
                    console.log("🖥️ REST failed, trying WebSocket fallback...");
                    startWebSocket();
                }
            });
    }

    // ========== WEBSOCKET FALLBACK ==========
    let ws = null;
    let wsRetries = 0;
    const MAX_WS_RETRIES = 10;

    function startWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = protocol + '//' + location.host + '/ws/hw_monitor';
        
        console.log("🖥️ Trying WebSocket fallback:", url);
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        
        ws = new WebSocket(url);
        
        ws.onopen = function() {
            console.log("🖥️ WebSocket connected ✅");
            setStatus("● LIVE", "live");
            setMethod("WS 1s");
            wsRetries = 0;
        };
        
        ws.onmessage = function(ev) {
            try {
                const d = JSON.parse(ev.data);
                console.log("🖥️ WS data received");
                if (d.type === 'hw_stats') updateDisplay(d);
            } catch(e) {
                console.warn("🖥️ WS JSON error:", e.message);
            }
        };
        
        ws.onclose = function() {
            console.log("🖥️ WebSocket disconnected");
            setStatus("WS Disc.", "err");
            if (wsRetries < MAX_WS_RETRIES) {
                wsRetries++;
                setTimeout(startWebSocket, 2000);
            }
        };
        
        ws.onerror = function() {
            console.warn("🖥️ WebSocket error");
        };
    }

    // ========== DISPLAY UPDATE ==========
    function updateDisplay(d) {
        // === GPU Name ===
        const nameEl = $id('hw-gpu-name');
        if (nameEl) {
            const newName = d.gpu_name || ('GPU ' + (d.gpu_id || 0));
            nameEl.textContent = newName;
            console.log("🖥️ GPU name set to:", newName);
        }

        // === Vendor ===
        const vendorEl = $id('hw-vendor-line');
        if (vendorEl) {
            const parts = [];
            if (d.vendor) parts.push(d.vendor.toUpperCase());
            if (d.driver) parts.push(d.driver);
            if (d.is_apu) parts.push('APU');
            if (d.os_type) parts.push(d.os_type);
            vendorEl.textContent = parts.join(' | ') || '-';
        }

        // === Unavailable ===
        if (!d.is_available) {
            console.warn("🖥️ GPU unavailable:", d.error || "no error");
            setUtil('hw-gpu-util', d.error || '--', 0);
            setUtil('hw-vram', d.error || '--', 0);
            setUtil('hw-temp', d.error || '--', 0);
            setUtil('hw-fan', d.error || '--', 0);
            setBar('hw-gpu-bar', 0);
            setBar('hw-vram-bar', 0);
            setBar('hw-temp-bar', 0);
            setBar('hw-fan-bar', 0);
            setStatus(d.error || 'Unavailable', 'err');
            return;
        }

        // === GPU ===
        const util = d.gpu_utilization || 0;
        setUtil('hw-gpu-util', Number(util).toFixed(1) + '%', util);
        setBar('hw-gpu-bar', util);
        console.log("🖥️ GPU util:", util);

        // === VRAM ===
        const vramUsed = d.vram_used_mb || 0;
        const vramTotal = d.vram_total_mb || 0;
        const vramPct = d.vram_usage_pct || 0;
        if (vramTotal > 0) {
            setUtil('hw-vram', (vramUsed / 1024).toFixed(2) + ' / ' + (vramTotal / 1024).toFixed(1) + ' GB', vramPct);
            setBar('hw-vram-bar', vramPct);
            console.log("🖥️ VRAM:", vramUsed, "/", vramTotal, "MB =", vramPct, "%");
        } else {
            setUtil('hw-vram', 'N/A', 0);
            setBar('hw-vram-bar', 0);
        }

        // === Temp ===
        const temp = d.temperature || 0;
        if (temp > 0) {
            setUtil('hw-temp', Number(temp).toFixed(1) + '°C', temp);
            setBar('hw-temp-bar', Math.min(temp, 100));
        } else {
            setUtil('hw-temp', 'N/A', 0);
            setBar('hw-temp-bar', 0);
        }

        // === Fan ===
        const fan = d.fan_speed || 0;
        if (fan > 0) {
            setUtil('hw-fan', fan + '%', fan);
            setBar('hw-fan-bar', fan);
        } else {
            setUtil('hw-fan', 'N/A', 0);
            setBar('hw-fan-bar', 0);
        }

        // === Method info ===
        let info = d.driver || 'unknown';
        if (d.core_clock_mhz > 0) info += ' | ' + d.core_clock_mhz + 'MHz';
        setMethod(info);

        // === Sparkline ===
        if (d.history && d.history.length > 0) {
            drawSparkline(d.history);
        }
    }

    function setUtil(id, text, pct) {
        const el = $id(id);
        if (!el) {
            console.error("🖥️ DOM Element untuk", id, "tidak ditemukan!");
            return;
        }
        el.textContent = text;
        el.className = 'hw-stat-value';
        if (pct > 85) el.classList.add('crit');
        else if (pct > 70) el.classList.add('warn');
    }

    function setBar(id, pct) {
        const el = $id(id);
        if (el) el.style.width = Math.min(100, Math.max(0, pct || 0)) + '%';
    }

    function setStatus(text, cls) {
        const el = $id('hw-status');
        if (el) { el.textContent = text; el.className = 'hw-status ' + (cls || ''); }
        if (widget) {
            const icon = widget.querySelector('.hw-icon');
            if (icon) icon.textContent = cls === 'live' ? '🟢' : cls === 'err' ? '🔴' : '🟡';
        }
    }

    function setMethod(text) {
        const el = $id('hw-method');
        if (el) el.textContent = text || '';
    }

    // ========== SPARKLINE ==========
    function drawSparkline(values) {
        const canvas = $id('hw-sparkline');
        if (!canvas || !values || values.length < 2) return;

        const ctx = canvas.getContext('2d');
        const w = canvas.width, h = canvas.height, pad = 3;
        ctx.clearRect(0, 0, w, h);

        const dataMax = Math.max.apply(null, values);
        const max = dataMax > 80 ? 100 : (dataMax < 1 ? 100 : dataMax * 1.2);
        const pw = w - pad * 2, ph = h - pad * 2;

        ctx.beginPath();
        ctx.moveTo(pad, h - pad);
        for (let i = 0; i < values.length; i++) {
            const x = pad + (i / (values.length - 1)) * pw;
            const y = h - pad - (values[i] / max) * ph;
            ctx.lineTo(x, y);
        }
        ctx.lineTo(pad + pw, h - pad);
        ctx.closePath();
        const grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, '#00e67633');
        grad.addColorStop(1, '#00e67605');
        ctx.fillStyle = grad;
        ctx.fill();

        ctx.beginPath();
        ctx.strokeStyle = '#00e676';
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        for (let i = 0; i < values.length; i++) {
            const x = pad + (i / (values.length - 1)) * pw;
            const y = h - pad - (values[i] / max) * ph;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        const lx = pad + pw;
        const ly = h - pad - (values[values.length - 1] / max) * ph;
        ctx.beginPath();
        ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#00e676';
        ctx.fill();
    }

    // ========== START ==========
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Fallback startup - try again if first attempt missed
    setTimeout(function() {
        if (!document.getElementById('bangtrix-hw-monitor')) {
            console.log("🖥️ Bangtrix HW Monitor: fallback init...");
            init();
        }
    }, 3000);

    console.log("🖥️ Bangtrix HW Monitor: loaded ✅");
})();