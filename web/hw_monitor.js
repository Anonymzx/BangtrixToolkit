/**
 * BANGTRIXTOOLKIT — Universal Hardware Monitor Overlay v5.0
 * Real-time GPU monitoring overlay for ComfyUI
 * Supports: AMD, NVIDIA, Intel, APU/iGPU
 * Platform: Windows, Linux
 * 
 * WebSocket: /ws/hw_monitor
 * Toggle: Ctrl+Shift+M
 */

(function () {
    "use strict";

    // === STATE ===
    var ws = null;
    var reconnectTimer = null;
    var reconnectAttempts = 0;
    const MAX_RECONNECT = 15;

    var widget = null;
    var isMinimized = false;
    var isVisible = true;
    var isDragging = false;
    var dragStart = { x: 0, y: 0 };

    var currentGpu = 0;
    var gpuCount = 1;
    var gpuData = {};
    var historyData = [];

    // === INIT ===
    function init() {
        createWidget();
        loadConfig();
        applyConfig();
        bindEvents();
        connect();
    }

    // === WIDGET ===
    function createWidget() {
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
                '<canvas class="hw-sparkline" id="hw-sparkline" width="232" height="36"></canvas>' +
                '<div class="hw-status-bar">' +
                    '<span class="hw-status" id="hw-status">Connecting...</span>' +
                    '<span class="hw-method" id="hw-method"></span>' +
                '</div>' +
            '</div>';

        var css = document.createElement('style');
        css.textContent =
            '#bangtrix-hw-monitor{position:fixed;top:60px;right:20px;width:260px;' +
            'background:rgba(18,18,24,0.92);border:1px solid rgba(100,150,255,0.3);border-radius:10px;' +
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;' +
            'color:#e0e0e0;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.4);' +
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
            '.hw-sparkline{width:100%;height:36px;margin-top:6px;border-radius:4px;background:rgba(0,0,0,0.2)}' +
            '.hw-status-bar{display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;' +
            'border-top:1px solid rgba(255,255,255,0.04);font-size:9px;color:#666}' +
            '.hw-status.live{color:#00e676;animation:livePulse 1.5s infinite}' +
            '.hw-status.err{color:#ff4444}' +
            '@keyframes livePulse{0%,100%{color:#00e676}50%{color:#00e67688}}';
        document.head.appendChild(css);
        document.body.appendChild(widget);
        makeDraggable();
    }

    // === DRAG ===
    function makeDraggable() {
        var header = widget.querySelector('.hw-header');
        header.addEventListener('mousedown', function (e) {
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
            var x = Math.max(10, Math.min(e.clientX - dragStart.x, window.innerWidth - widget.offsetWidth + 10));
            var y = Math.max(10, Math.min(e.clientY - dragStart.y, window.innerHeight - widget.offsetHeight + 10));
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
            saveConfig();
        }
    }

    // === EVENTS ===
    function bindEvents() {
        document.getElementById('hw-btn-min').onclick = function () {
            isMinimized = !isMinimized;
            widget.classList.toggle('minimized', isMinimized);
            this.textContent = isMinimized ? '+' : '−';
            saveConfig();
        };
        document.getElementById('hw-btn-close').onclick = function () {
            isVisible = false;
            widget.classList.add('hidden');
            saveConfig();
        };
        document.addEventListener('keydown', function (e) {
            if (e.ctrlKey && e.shiftKey && e.key === 'M') {
                e.preventDefault();
                isVisible = !isVisible;
                widget.classList.toggle('hidden', !isVisible);
                if (isVisible) connect();
                saveConfig();
            }
        });
    }

    // === CONFIG ===
    function loadConfig() {
        try {
            var c = JSON.parse(localStorage.getItem('bangtrix_hw_config') || '{}');
            if (c.pos) { widget.style.left = c.pos.x; widget.style.top = c.pos.y; widget.style.right = 'auto'; }
            if (c.min) { isMinimized = c.min; widget.classList.toggle('minimized', true);
                var b = document.getElementById('hw-btn-min'); if (b) b.textContent = '+'; }
            if (c.vis === false) { isVisible = false; widget.classList.add('hidden'); }
        } catch (e) {}
    }
    function saveConfig() {
        try {
            localStorage.setItem('bangtrix_hw_config', JSON.stringify({
                pos: { x: widget.style.left, y: widget.style.top },
                min: isMinimized,
                vis: isVisible
            }));
        } catch (e) {}
    }
    function applyConfig() {
        // Minimal - no settings panel needed
    }

    // === WEBSOCKET ===
    function connect() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        if (!isVisible) return;
        
        var url = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws/hw_monitor';
        
        setStatus('Connecting...', '');
        ws = new WebSocket(url);
        
        ws.onopen = function () {
            setStatus('● LIVE', 'live');
            setMethod('500ms');
            reconnectAttempts = 0;
        };
        ws.onmessage = function (ev) {
            try {
                var d = JSON.parse(ev.data);
                if (d.type === 'hw_stats') onStats(d);
            } catch (e) {}
        };
        ws.onclose = function () {
            setStatus('Disconnected', 'err');
            setMethod('');
            if (reconnectAttempts < MAX_RECONNECT) {
                reconnectAttempts++;
                setTimeout(connect, Math.min(1000 * Math.pow(1.5, reconnectAttempts), 10000));
            }
        };
        ws.onerror = function () {
            if (reconnectAttempts === 0) setTimeout(connect, 2000);
        };
    }

    // === DATA ===
    function onStats(d) {
        gpuData[d.gpu_id] = d;
        if (d.gpu_count && d.gpu_count !== gpuCount) gpuCount = d.gpu_count;
        if (d.gpu_id === currentGpu) updateDisplay(d);
    }

    function $id(id) { return document.getElementById(id); }

    function updateDisplay(d) {
        var nameEl = $id('hw-gpu-name');
        var vendorEl = $id('hw-vendor-line');
        
        if (nameEl) nameEl.textContent = d.gpu_name || ('GPU ' + d.gpu_id);
        if (vendorEl) {
            var parts = [];
            if (d.vendor) parts.push(d.vendor.toUpperCase());
            if (d.driver) parts.push(d.driver);
            if (d.is_apu) parts.push('APU');
            if (d.os_type) parts.push(d.os_type);
            vendorEl.textContent = parts.join(' | ');
        }

        if (!d.is_available) {
            setUtil('hw-gpu-util', '--', 0);
            setUtil('hw-vram', '--', 0);
            setUtil('hw-temp', '--', 0);
            setUtil('hw-fan', '--', 0);
            setBar('hw-gpu-bar', 0);
            setBar('hw-vram-bar', 0);
            setBar('hw-temp-bar', 0);
            setBar('hw-fan-bar', 0);
            setStatus(d.error || 'Unavailable', 'err');
            return;
        }

        // GPU Util
        var util = d.gpu_utilization || 0;
        setUtil('hw-gpu-util', util.toFixed(1) + '%', util);
        setBar('hw-gpu-bar', util);

        // VRAM
        var vramUsed = d.vram_used_mb || 0;
        var vramTotal = d.vram_total_mb || 0;
        var vramShared = d.vram_shared_mb || 0;
        var vramPct = d.vram_usage_pct || 0;

        if (vramTotal > 0 && vramUsed > 0) {
            setUtil('hw-vram', (vramUsed/1024).toFixed(2) + ' / ' + (vramTotal/1024).toFixed(1) + ' GB', vramPct);
            setBar('hw-vram-bar', vramPct);
        } else if (vramShared > 0) {
            setUtil('hw-vram', (vramUsed/1024).toFixed(2) + ' / ' + (vramShared/1024).toFixed(1) + ' GB (shared)', vramPct);
            setBar('hw-vram-bar', vramPct);
        } else if (vramTotal > 0) {
            setUtil('hw-vram', '0 / ' + (vramTotal/1024).toFixed(1) + ' GB', 0);
            setBar('hw-vram-bar', 0);
        } else {
            setUtil('hw-vram', 'N/A', 0);
            setBar('hw-vram-bar', 0);
        }

        // Temp
        var temp = d.temperature || 0;
        if (temp > 0) {
            setUtil('hw-temp', temp.toFixed(1) + '°C', temp);
            setBar('hw-temp-bar', Math.min(temp, 100));
        } else {
            setUtil('hw-temp', 'N/A', 0);
            setBar('hw-temp-bar', 0);
        }

        // Fan
        var fan = d.fan_speed || 0;
        if (fan > 0) {
            setUtil('hw-fan', fan + '%', fan);
            setBar('hw-fan-bar', fan);
        } else {
            setUtil('hw-fan', 'N/A', 0);
            setBar('hw-fan-bar', 0);
        }

        // Method info
        var info = d.driver || 'unknown';
        if (d.core_clock_mhz > 0) info += ' | ' + d.core_clock_mhz + 'MHz';
        if (d.power_draw_watts > 0) info += ' | ' + d.power_draw_watts + 'W';
        setMethod(info);
        setStatus('● LIVE', 'live');

        // Sparkline
        if (d.history && d.history.length > 0) {
            historyData = d.history;
            drawSparkline(historyData);
        }
    }

    function setUtil(id, text, pct) {
        var el = $id(id);
        if (!el) return;
        el.textContent = text;
        el.className = 'hw-stat-value';
        if (pct !== undefined && pct !== null) {
            if (pct > 85) el.classList.add('crit');
            else if (pct > 70) el.classList.add('warn');
        }
    }

    function setBar(id, pct) {
        var el = $id(id);
        if (el) el.style.width = Math.min(100, Math.max(0, pct || 0)) + '%';
    }

    function setStatus(text, cls) {
        var el = $id('hw-status');
        if (el) { el.textContent = text; el.className = 'hw-status ' + (cls || ''); }
        var icon = widget.querySelector('.hw-icon');
        if (icon) icon.textContent = cls === 'live' ? '🟢' : cls === 'err' ? '🔴' : '🟡';
    }

    function setMethod(text) {
        var el = $id('hw-method');
        if (el) el.textContent = text || '';
    }

    // === SPARKLINE ===
    function drawSparkline(values) {
        var canvas = $id('hw-sparkline');
        if (!canvas || values.length < 2) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width, h = canvas.height, pad = 3;
        ctx.clearRect(0, 0, w, h);

        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        for (var y = 0; y <= 3; y++) {
            ctx.beginPath(); ctx.moveTo(0, pad + (y/3)*(h-pad*2)); ctx.lineTo(w, pad + (y/3)*(h-pad*2)); ctx.stroke();
        }

        var dataMax = Math.max.apply(null, values);
        var max = dataMax > 80 ? 100 : (dataMax < 1 ? 100 : dataMax * 1.2);
        var pw = w - pad * 2, ph = h - pad * 2;

        // Area fill
        ctx.beginPath();
        ctx.moveTo(pad, h - pad);
        for (var i = 0; i < values.length; i++) {
            var x = pad + (i / (values.length - 1)) * pw;
            var y = h - pad - (values[i] / max) * ph;
            ctx.lineTo(x, y);
        }
        ctx.lineTo(pad + pw, h - pad);
        ctx.closePath();
        var grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, '#00e67633');
        grad.addColorStop(1, '#00e67605');
        ctx.fillStyle = grad;
        ctx.fill();

        // Line
        ctx.beginPath();
        ctx.strokeStyle = '#00e676';
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        for (var i = 0; i < values.length; i++) {
            var x = pad + (i / (values.length - 1)) * pw;
            var y = h - pad - (values[i] / max) * ph;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Dot
        var lx = pad + pw;
        var ly = h - pad - (values[values.length-1] / max) * ph;
        ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#00e676';
        ctx.fill();

        // Label
        ctx.fillStyle = '#00e676';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(values[values.length-1].toFixed(0) + '%', w - pad, pad);
    }

    // === START ===
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();