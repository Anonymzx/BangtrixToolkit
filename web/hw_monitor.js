/**
 * BangtrixToolkit — Universal Hardware Monitor Overlay
 * ComfyUI Extension
 * 
 * Strategy: REST API polling via GET /bangtrix/hw/stats.
 * Fallback: WebSocket /ws/hw_monitor.
 * Toggle: Ctrl+Shift+M
 * 
 * Settings (5 integrated via app.ui.settings.addSetting):
 *   1. HW Monitor Theme          — Combo (4 themes)
 *   2. HW Monitor Refresh Rate   — Combo (500/1000/2000 ms)
 *   3. Show HW Monitor on Startup — Boolean
 *   4. Background Opacity        — Slider (0.1 .. 1.0)
 *   5. Compact Mode              — Boolean
 */

(function() {
    "use strict";
    console.log("🖥️ Bangtrix HW Monitor: loading...");

    // ================================================================
    // T H E M E S
    // ================================================================
    const THEMES = {
        "Default (Dark Green)": {
            accent: "#00e676", accentRgb: "0,230,118", accentWarm: "#ffaa00",
            accentCrit: "#ff4444", gpuName: "#66aaff", fillBar: "#00e676",
            tempGrad: "linear-gradient(90deg,#00e676,#ffaa00,#ff4444)",
            sparklineLine: "#00e676", sparklineTop: "#00e67633", sparklineBot: "#00e67605",
            liveColor: "#00e676", vendorColor: "#666", labelColor: "#666",
            statValueColor: "#00e676", headerBg: "rgba(100,150,255,0.1)", headerBgHex: "rgba(100,150,255,0.1)"
        },
        "Neon Blue": {
            accent: "#00bfff", accentRgb: "0,191,255", accentWarm: "#ff7700",
            accentCrit: "#ff3355", gpuName: "#66ddff", fillBar: "#00bfff",
            tempGrad: "linear-gradient(90deg,#00bfff,#ff7700,#ff3355)",
            sparklineLine: "#00bfff", sparklineTop: "#00bfff33", sparklineBot: "#00bfff05",
            liveColor: "#00bfff", vendorColor: "#6688aa", labelColor: "#6688aa",
            statValueColor: "#00bfff", headerBg: "rgba(0,180,255,0.1)", headerBgHex: "rgba(0,180,255,0.1)"
        },
        "Crimson Red": {
            accent: "#ff4444", accentRgb: "255,68,68", accentWarm: "#ff8844",
            accentCrit: "#cc0000", gpuName: "#ff6666", fillBar: "#ff4444",
            tempGrad: "linear-gradient(90deg,#ff4444,#ff8844,#cc0000)",
            sparklineLine: "#ff4444", sparklineTop: "#ff444433", sparklineBot: "#ff444405",
            liveColor: "#ff4444", vendorColor: "#996666", labelColor: "#996666",
            statValueColor: "#ff4444", headerBg: "rgba(255,68,68,0.1)", headerBgHex: "rgba(255,68,68,0.1)"
        },
        "Hacker (Black & Bright Green)": {
            accent: "#00ff00", accentRgb: "0,255,0", accentWarm: "#88ff00",
            accentCrit: "#ff0000", gpuName: "#00ff00", fillBar: "#00ff00",
            tempGrad: "linear-gradient(90deg,#00ff00,#88ff00,#ff0000)",
            sparklineLine: "#00ff00", sparklineTop: "#00ff0033", sparklineBot: "#00ff0005",
            liveColor: "#00ff00", vendorColor: "#338833", labelColor: "#338833",
            statValueColor: "#00ff00", headerBg: "rgba(0,255,0,0.05)", headerBgHex: "rgba(0,255,0,0.05)"
        }
    };

    // ================================================================
    // S T A T E
    // ================================================================
    let widget = null, dynamicCss = null, isMinimized = false, isVisible = true;
    let isDragging = false, dragStart = { x: 0, y: 0 };
    let pollInterval = null, pollRetries = 0;
    const MAX_RETRIES = 30;

    let curTheme = "Default (Dark Green)", curRefreshMs = 1000;
    let curShowOnStartup = true, curBgOpacity = 0.92, curCompactMode = false;

    // ================================================================
    // U T I L S
    // ================================================================
    function $id(id) {
        const el = document.getElementById(id);
        if (!el) console.error("🖥️ DOM Element:", id);
        return el;
    }
    function _saveSetting(key, value) {
        try {
            const raw = localStorage.getItem('Comfy.Settings');
            const s = raw ? JSON.parse(raw) : {};
            s[key] = value;
            localStorage.setItem('Comfy.Settings', JSON.stringify(s));
        } catch(e) {}
    }
    function _readSettings() {
        try {
            const raw = localStorage.getItem('Comfy.Settings');
            if (!raw) return;
            const s = JSON.parse(raw);
            if (s['Bangtrix.HWMonitor.Theme'] && THEMES[s['Bangtrix.HWMonitor.Theme']]) curTheme = s['Bangtrix.HWMonitor.Theme'];
            if (s['Bangtrix.HWMonitor.RefreshRate'] != null) curRefreshMs = Number(s['Bangtrix.HWMonitor.RefreshRate']) || 1000;
            if (s['Bangtrix.HWMonitor.ShowOnStartup'] != null) curShowOnStartup = !!s['Bangtrix.HWMonitor.ShowOnStartup'];
            if (s['Bangtrix.HWMonitor.BgOpacity'] != null) curBgOpacity = Number(s['Bangtrix.HWMonitor.BgOpacity']) || 0.92;
            if (s['Bangtrix.HWMonitor.CompactMode'] != null) curCompactMode = !!s['Bangtrix.HWMonitor.CompactMode'];
        } catch(e) {}
    }

    // ================================================================
    // D Y N A M I C   C S S
    // ================================================================
    function buildDynamicCss() {
        if (document.getElementById('bangtrix-hw-dynamic-css')) return;
        dynamicCss = document.createElement('style');
        dynamicCss.id = 'bangtrix-hw-dynamic-css';
        document.head.appendChild(dynamicCss);
        _updateDynamicCss();
    }
    function _updateDynamicCss() {
        if (!dynamicCss) return;
        const t = THEMES[curTheme] || THEMES["Default (Dark Green)"];
        dynamicCss.textContent =
            '#bangtrix-hw-monitor{background:rgba(18,18,24,' + Number(curBgOpacity).toFixed(2) + ');' +
            'border:1px solid rgba(' + t.accentRgb + ',0.3);}' +
            '#bangtrix-hw-monitor.hidden{display:none}' +
            '#bangtrix-hw-monitor.minimized .hw-body{display:none}' +
            '.hw-header{background:' + t.headerBgHex + ';}' +
            '.hw-gpu-name{color:' + t.gpuName + '}' +
            '.hw-vendor-line{color:' + t.vendorColor + '}' +
            '.hw-stat-label{color:' + t.labelColor + '}' +
            '.hw-stat-value{color:' + t.statValueColor + '}' +
            '.hw-stat-value.warn{color:' + t.accentWarm + '}' +
            '.hw-stat-value.crit{color:' + t.accentCrit + '}' +
            '.hw-fill{background:' + t.fillBar + '}' +
            '.hw-fill.hw-temp-fill{background:' + t.tempGrad + '}' +
            '.hw-status.live{color:' + t.liveColor + '}' +
            '.hw-status.err{color:' + t.accentCrit + '}';
    }
    function _applyTheme() { _updateDynamicCss(); }
    function _applyBgOpacity() {
        if (!widget) return;
        const t = THEMES[curTheme] || THEMES["Default (Dark Green)"];
        widget.style.background = 'rgba(18,18,24,' + Number(curBgOpacity).toFixed(2) + ')';
        widget.style.borderColor = 'rgba(' + t.accentRgb + ',0.3)';
    }
    function _applyCompactMode() {
        if (!widget) return;
        const sc = widget.querySelector('.hw-sparkline-container');
        if (sc) sc.style.display = curCompactMode ? 'none' : '';
    }

    // ================================================================
    // W I D G E T
    // ================================================================
    function buildWidget() {
        if (document.getElementById('bangtrix-hw-monitor')) return;
        widget = document.createElement('div');
        widget.id = 'bangtrix-hw-monitor';
        widget.innerHTML =
            '<div class="hw-header">' +
                '<span class="hw-icon">🖥️</span>' +
                '<span class="hw-title">HW Monitor</span>' +
                '<div class="hw-controls">' +
                    '<button class="hw-btn hw-btn-settings" id="hw-btn-settings" title="Open Settings">⚙</button>' +
                    '<button class="hw-btn" id="hw-btn-min">−</button>' +
                    '<button class="hw-btn hw-btn-close" id="hw-btn-close">✕</button>' +
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
                    '<canvas class="hw-sparkline" id="hw-sparkline" width="228" height="36"></canvas>' +
                '</div>' +
                '<div class="hw-status-bar">' +
                    '<span class="hw-status" id="hw-status">Starting...</span>' +
                    '<span class="hw-method" id="hw-method"></span>' +
                '</div>' +
            '</div>';
        const baseCss = document.createElement('style');
        baseCss.id = 'bangtrix-hw-base-css';
        baseCss.textContent =
            '#bangtrix-hw-monitor{position:fixed;top:60px;right:20px;width:260px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;color:#e0e0e0;z-index:99999;box-shadow:0 8px 32px rgba(0,0,0,0.4);backdrop-filter:blur(8px);user-select:none;border-radius:10px;}' +
            '.hw-header{display:flex;align-items:center;padding:8px 12px;gap:8px;cursor:move;border-radius:10px 10px 0 0;border-bottom:1px solid rgba(255,255,255,0.04)}' +
            '.hw-icon{font-size:12px;animation:pulse 1.5s infinite}' +
            '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
            '.hw-title{flex:1;font-weight:600;font-size:12px;color:#fff}' +
            '.hw-controls{display:flex;gap:4px}' +
            '.hw-btn{background:rgba(255,255,255,0.08);border:none;color:#ccc;width:20px;height:20px;border-radius:4px;cursor:pointer;font-size:11px;line-height:20px;text-align:center}' +
            '.hw-btn:hover{background:rgba(255,255,255,0.2)}' +
            '.hw-btn-close:hover{background:rgba(220,60,60,0.4)!important}' +
            '.hw-body{padding:8px 12px 10px}' +
            '.hw-gpu-name{text-align:center;font-size:11px;font-weight:600;padding:4px 8px;border-radius:4px;background:rgba(255,255,255,0.03);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
            '.hw-vendor-line{text-align:center;font-size:9px;margin:2px 0 6px}' +
            '.hw-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px}' +
            '.hw-stat{display:flex;flex-direction:column;gap:1px}' +
            '.hw-stat-label{font-size:9px;text-transform:uppercase}' +
            '.hw-stat-value{font-weight:600;font-size:12px;transition:color 0.2s}' +
            '.hw-bar{height:3px;background:rgba(255,255,255,0.08);border-radius:2px;overflow:hidden}' +
            '.hw-fill{height:100%;width:0%;border-radius:2px;transition:width 0.3s ease}' +
            '.hw-sparkline-container{margin-top:6px}' +
            '.hw-sparkline{width:100%;height:36px;border-radius:4px;background:rgba(0,0,0,0.2)}' +
            '.hw-status-bar{display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;border-top:1px solid rgba(255,255,255,0.04);font-size:9px}' +
            '.hw-status.live{animation:livePulse 1.5s infinite}' +
            '@keyframes livePulse{0%,100%{color:inherit}50%{opacity:0.5}}';
        document.head.appendChild(baseCss);
        document.body.appendChild(widget);
        makeDraggable();
    }

    // ================================================================
    // D R A G
    // ================================================================
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
            widget.style.left = Math.max(10, Math.min(e.clientX - dragStart.x, innerWidth - widget.offsetWidth + 10)) + 'px';
            widget.style.top = Math.max(10, Math.min(e.clientY - dragStart.y, innerHeight - widget.offsetHeight + 10)) + 'px';
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

    // ================================================================
    // E V E N T S
    // ================================================================
    function bindEvents() {
        const minBtn = document.getElementById('hw-btn-min');
        if (minBtn) minBtn.onclick = function() {
            isMinimized = !isMinimized;
            widget.classList.toggle('minimized', isMinimized);
            this.textContent = isMinimized ? '+' : '\u2212';
        };
        const settingsBtn = document.getElementById('hw-btn-settings');
        if (settingsBtn) settingsBtn.onclick = function(e) {
            e.stopPropagation();
            // Open built-in settings panel
            _showSettingsPanel();
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

    // ================================================================
    // S E T T I N G S   P A N E L   (built-in, self-contained)
    // ================================================================
    let settingsPanel = null;
    function _showSettingsPanel() {
        if (settingsPanel) {
            settingsPanel.style.display = settingsPanel.style.display === 'none' ? 'block' : 'none';
            return;
        }
        settingsPanel = document.createElement('div');
        settingsPanel.id = 'bangtrix-hw-settings';
        settingsPanel.innerHTML =
            '<div class="hws-header">HW Monitor Settings <span class="hws-close" id="hws-close">\u2715</span></div>' +
            '<div class="hws-body">' +
                '<div class="hws-row"><label>Theme</label><select id="hws-theme">' +
                    Object.keys(THEMES).map(function(t) { return '<option value="' + t + '">' + t + '</option>'; }).join('') +
                '</select></div>' +
                '<div class="hws-row"><label>Refresh Rate</label><select id="hws-refresh">' +
                    '<option value="500">500ms</option><option value="1000">1s</option><option value="2000">2s</option>' +
                '</select></div>' +
                '<div class="hws-row"><label>Show on Startup</label><input type="checkbox" id="hws-startup"></div>' +
                '<div class="hws-row"><label>Bg Opacity</label><input type="range" id="hws-opacity" min="0.1" max="1.0" step="0.05"></div>' +
                '<div class="hws-row"><label>Compact Mode</label><input type="checkbox" id="hws-compact"></div>' +
            '</div>';
        const hwsCss = document.createElement('style');
        hwsCss.textContent =
            '#bangtrix-hw-settings{position:fixed;top:120px;right:30px;width:240px;background:rgba(18,18,24,0.96);border:1px solid rgba(255,255,255,0.15);border-radius:10px;z-index:100000;color:#ccc;font-size:11px;box-shadow:0 4px 20px rgba(0,0,0,0.5);}' +
            '.hws-header{display:flex;justify-content:space-between;padding:8px 12px;font-weight:600;color:#fff;border-bottom:1px solid rgba(255,255,255,0.06);}' +
            '.hws-close{cursor:pointer;color:#888;}' +
            '.hws-close:hover{color:#f44;}' +
            '.hws-body{padding:10px 12px;}' +
            '.hws-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;}' +
            '.hws-row label{color:#999;}' +
            '.hws-row select,.hws-row input{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);color:#ddd;border-radius:4px;padding:2px 6px;font-size:11px;}' +
            '.hws-row select{min-width:160px;}' +
            '.hws-row input[type=range]{width:100px;}';
        document.head.appendChild(hwsCss);
        document.body.appendChild(settingsPanel);
        _syncSettingsPanel();
        // Bind events
        document.getElementById('hws-close').onclick = function() { settingsPanel.style.display = 'none'; };
        document.getElementById('hws-theme').onchange = function() { curTheme = this.value; _saveSetting('Bangtrix.HWMonitor.Theme', curTheme); _applyTheme(); _applyBgOpacity(); };
        document.getElementById('hws-refresh').onchange = function() { curRefreshMs = Number(this.value) || 1000; _saveSetting('Bangtrix.HWMonitor.RefreshRate', curRefreshMs); restartPolling(); };
        document.getElementById('hws-startup').onchange = function() { curShowOnStartup = !!this.checked; _saveSetting('Bangtrix.HWMonitor.ShowOnStartup', curShowOnStartup); };
        document.getElementById('hws-opacity').oninput = function() { curBgOpacity = Number(this.value); _saveSetting('Bangtrix.HWMonitor.BgOpacity', curBgOpacity); _applyBgOpacity(); };
        document.getElementById('hws-compact').onchange = function() { curCompactMode = !!this.checked; _saveSetting('Bangtrix.HWMonitor.CompactMode', curCompactMode); _applyCompactMode(); };
    }
    function _syncSettingsPanel() {
        if (!settingsPanel) return;
        document.getElementById('hws-theme').value = curTheme;
        document.getElementById('hws-refresh').value = curRefreshMs;
        document.getElementById('hws-startup').checked = curShowOnStartup;
        document.getElementById('hws-opacity').value = curBgOpacity;
        document.getElementById('hws-compact').checked = curCompactMode;
    }

    // ================================================================
    // P O L L I N G
    // ================================================================
    function restartPolling() {
        if (!isVisible) return;
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = null;
        startPolling();
    }
    function startPolling() {
        setStatus("Connecting...", "");
        fetchStats();
        if (pollInterval) clearInterval(pollInterval);
        pollInterval = setInterval(fetchStats, curRefreshMs);
    }
    function fetchStats() {
        fetch('/bangtrix/hw/stats')
            .then(function(r) { if (!r.ok) throw new Error('HTTP ' + r.status); return r.json(); })
            .then(function(data) {
                pollRetries = 0;
                if (data && data.type === 'hw_stats') {
                    setStatus("\u25CF LIVE", "live");
                    setMethod("REST " + (curRefreshMs / 1000) + "s");
                    updateDisplay(data);
                }
            })
            .catch(function(err) {
                pollRetries++;
                setStatus("Retry " + pollRetries, "err");
                setMethod("");
                if (pollRetries === 5) startWebSocket();
            });
    }

    // ================================================================
    // W E B S O C K E T   F A L L B A C K
    // ================================================================
    let ws = null, wsRetries = 0, MAX_WS_RETRIES = 10;
    function startWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        const url = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws/hw_monitor';
        if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        ws = new WebSocket(url);
        ws.onopen = function() { setStatus("\u25CF LIVE", "live"); setMethod("WS 1s"); wsRetries = 0; };
        ws.onmessage = function(ev) { try { var d = JSON.parse(ev.data); if (d.type === 'hw_stats') updateDisplay(d); } catch(e) {} };
        ws.onclose = function() { setStatus("WS Disc.", "err"); if (wsRetries < MAX_WS_RETRIES) { wsRetries++; setTimeout(startWebSocket, 2000); } };
    }

    // ================================================================
    // D I S P L A Y   U P D A T E
    // ================================================================
    function updateDisplay(d) {
        var el;
        el = $id('hw-gpu-name'); if (el) el.textContent = d.gpu_name || ('GPU ' + (d.gpu_id || 0));
        el = $id('hw-vendor-line');
        if (el) {
            var parts = [];
            if (d.vendor) parts.push(d.vendor.toUpperCase());
            if (d.driver) parts.push(d.driver);
            if (d.is_apu) parts.push('APU');
            if (d.os_type) parts.push(d.os_type);
            el.textContent = parts.join(' | ') || '-';
        }
        if (!d.is_available) {
            setUtil('hw-gpu-util', d.error || '--', 0); setUtil('hw-vram', d.error || '--', 0);
            setUtil('hw-temp', d.error || '--', 0); setUtil('hw-fan', d.error || '--', 0);
            setBar('hw-gpu-bar', 0); setBar('hw-vram-bar', 0); setBar('hw-temp-bar', 0); setBar('hw-fan-bar', 0);
            setStatus(d.error || 'Unavailable', 'err');
            return;
        }
        var util = d.gpu_utilization || 0;
        setUtil('hw-gpu-util', Number(util).toFixed(1) + '%', util);
        setBar('hw-gpu-bar', util);
        var vramUsed = d.vram_used_mb || 0, vramTotal = d.vram_total_mb || 0, vramPct = d.vram_usage_pct || 0;
        if (vramTotal > 0) { setUtil('hw-vram', (vramUsed / 1024).toFixed(2) + ' / ' + (vramTotal / 1024).toFixed(1) + ' GB', vramPct); setBar('hw-vram-bar', vramPct); }
        else { setUtil('hw-vram', 'N/A', 0); setBar('hw-vram-bar', 0); }
        var temp = d.temperature || 0;
        if (temp > 0) { setUtil('hw-temp', Number(temp).toFixed(1) + '\u00B0C', temp); setBar('hw-temp-bar', Math.min(temp, 100)); }
        else { setUtil('hw-temp', 'N/A', 0); setBar('hw-temp-bar', 0); }
        var fan = d.fan_speed || 0;
        if (fan > 0) { setUtil('hw-fan', fan + '%', fan); setBar('hw-fan-bar', fan); }
        else { setUtil('hw-fan', 'N/A', 0); setBar('hw-fan-bar', 0); }
        var info = d.driver || 'unknown';
        if (d.core_clock_mhz > 0) info += ' | ' + d.core_clock_mhz + 'MHz';
        setMethod(info);
        if (!curCompactMode && d.history && d.history.length > 0) drawSparkline(d.history);
    }
    function setUtil(id, text, pct) {
        var el = $id(id); if (!el) return;
        el.textContent = text; el.className = 'hw-stat-value';
        if (pct > 85) el.classList.add('crit'); else if (pct > 70) el.classList.add('warn');
    }
    function setBar(id, pct) { var el = $id(id); if (el) el.style.width = Math.min(100, Math.max(0, pct || 0)) + '%'; }
    function setStatus(text, cls) {
        var el = $id('hw-status'); if (el) { el.textContent = text; el.className = 'hw-status ' + (cls || ''); }
        if (widget) { var icon = widget.querySelector('.hw-icon'); if (icon) icon.textContent = cls === 'live' ? '\uD83D\uDFE2' : cls === 'err' ? '\uD83D\uDD34' : '\uD83D\uDFE1'; }
    }
    function setMethod(text) { var el = $id('hw-method'); if (el) el.textContent = text || ''; }

    // ================================================================
    // S P A R K L I N E
    // ================================================================
    function drawSparkline(values) {
        var canvas = $id('hw-sparkline');
        if (!canvas || values.length < 2) return;
        var t = THEMES[curTheme] || THEMES["Default (Dark Green)"];
        var ctx = canvas.getContext('2d'), w = canvas.width, h = canvas.height, pad = 3;
        ctx.clearRect(0, 0, w, h);
        var dataMax = Math.max.apply(null, values), max = dataMax > 80 ? 100 : (dataMax < 1 ? 100 : dataMax * 1.2);
        var pw = w - pad * 2, ph = h - pad * 2;
        ctx.beginPath(); ctx.moveTo(pad, h - pad);
        for (var i = 0; i < values.length; i++) { var x = pad + (i / (values.length - 1)) * pw; var y = h - pad - (values[i] / max) * ph; ctx.lineTo(x, y); }
        ctx.lineTo(pad + pw, h - pad); ctx.closePath();
        var grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, t.sparklineTop); grad.addColorStop(1, t.sparklineBot);
        ctx.fillStyle = grad; ctx.fill();
        ctx.beginPath(); ctx.strokeStyle = t.sparklineLine; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
        for (var i = 0; i < values.length; i++) { var x = pad + (i / (values.length - 1)) * pw; var y = h - pad - (values[i] / max) * ph; if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y); }
        ctx.stroke();
        var lx = pad + pw, ly = h - pad - (values[values.length - 1] / max) * ph;
        ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2); ctx.fillStyle = t.sparklineLine; ctx.fill();
    }

    // ================================================================
    // C O M F Y U I   S E T T I N G S   R E G I S T R A T I O N
    // ================================================================
    // Also register with ComfyUI's native settings dialog so they appear
    // under Settings -> BangtrixToolkit
    function _registerComfyUISettings() {
        if (!app || !app.ui || !app.ui.settings || !app.ui.settings.addSetting) {
            setTimeout(_registerComfyUISettings, 200);
            return;
        }
        try {
            // 1. Theme
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.Theme",
                name: "\uD83C\uDFA8 HW Monitor Theme",
                type: "combo",
                defaultValue: "Default (Dark Green)",
                options: ["Default (Dark Green)", "Neon Blue", "Crimson Red", "Hacker (Black & Bright Green)"],
                onChange: function(v) { curTheme = v; _saveSetting("Bangtrix.HWMonitor.Theme", v); _applyTheme(); _applyBgOpacity(); _syncSettingsPanel(); }
            });
            // 2. Refresh Rate
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.RefreshRate",
                name: "\u23F1\uFE0F HW Monitor Refresh Rate",
                type: "combo",
                defaultValue: 1000,
                options: [500, 1000, 2000],
                onChange: function(v) { curRefreshMs = Number(v) || 1000; _saveSetting("Bangtrix.HWMonitor.RefreshRate", curRefreshMs); _syncSettingsPanel(); restartPolling(); }
            });
            // 3. Show on Startup
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.ShowOnStartup",
                name: "\uD83D\uDC41\uFE0F Show HW Monitor on Startup",
                type: "boolean",
                defaultValue: true,
                onChange: function(v) { curShowOnStartup = !!v; _saveSetting("Bangtrix.HWMonitor.ShowOnStartup", curShowOnStartup); _syncSettingsPanel(); }
            });
            // 4. Background Opacity
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.BgOpacity",
                name: "\uD83D\uDD32 HW Monitor Background Opacity",
                type: "slider",
                defaultValue: 0.92,
                attrs: { min: 0.1, max: 1.0, step: 0.05 },
                onChange: function(v) { curBgOpacity = Number(v) || 0.92; _saveSetting("Bangtrix.HWMonitor.BgOpacity", curBgOpacity); _syncSettingsPanel(); _applyBgOpacity(); }
            });
            // 5. Compact Mode
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.CompactMode",
                name: "\uD83D\uDCE6 HW Monitor Compact Mode",
                type: "boolean",
                defaultValue: false,
                onChange: function(v) { curCompactMode = !!v; _saveSetting("Bangtrix.HWMonitor.CompactMode", curCompactMode); _syncSettingsPanel(); _applyCompactMode(); }
            });
            console.log("\uD83D\uDDA5\uFE0F Bangtrix HW Monitor: 5 ComfyUI settings registered \u2705");
        } catch(e) {
            console.warn("\uD83D\uDDA5\uFE0F ComfyUI settings registration deferred:", e.message);
            setTimeout(_registerComfyUISettings, 500);
        }
    }

    // ================================================================
    // I N I T
    // ================================================================
    function initWidget() {
        if (document.getElementById('bangtrix-hw-monitor')) return;
        _readSettings();
        buildDynamicCss();
        buildWidget();
        bindEvents();
        var checkEl = $id('hw-gpu-name'); if (checkEl) checkEl.textContent = "Loading...";
        if (!curShowOnStartup) { isVisible = false; widget.classList.add('hidden'); }
        _applyTheme(); _applyBgOpacity(); _applyCompactMode();
        if (isVisible) startPolling();
        console.log("\uD83D\uDDA5\uFE0F Bangtrix HW Monitor: widget initialized \u2705");
    }

    // ================================================================
    // S T A R T
    // ================================================================
    initWidget();
    _registerComfyUISettings();

    console.log("\uD83D\uDDA5\uFE0F Bangtrix HW Monitor: loaded \u2705");
})();