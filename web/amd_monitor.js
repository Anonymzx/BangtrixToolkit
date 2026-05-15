/**
 * BANGTRIXTOOLKIT - AMD Monitor Overlay v3.5
 * Real-time AMD GPU monitoring overlay for ComfyUI
 * Features: Real-time 500ms updates, smooth CSS transitions, live VRAM
 */

(function () {
    "use strict";

    var CONFIG = {
        storageKey: 'bangtrix_amd_monitor_config',
    };

    var ws = null;
    var reconnectTimer = null;
    var reconnectAttempts = 0;
    var MAX_RECONNECT = 15;

    var widget = null;
    var isMinimized = false;
    var isVisible = true;
    var isDragging = false;
    var dragOffset = { x: 0, y: 0 };

    var gpuDataMap = {};
    var selectedGpuId = 0;
    var gpuCount = 1;
    var historyData = [];

    var savedConfig = {};
    var animationFrame = null;
    var lastUpdate = 0;

    // ===== UTILITY =====
    function $(id) { return document.getElementById(id); }

    // ===== INIT =====
    function init() {
        console.log('[AMD Monitor] Initializing v3.5 Real-Time...');
        loadConfig();
        createWidget();
        applyConfigToWidget();
        setupEventListeners();
        connectWebSocket();
    }

    // ===== WIDGET CREATION =====
    function createWidget() {
        widget = document.createElement('div');
        widget.id = 'bangtrix-amd-monitor';
        widget.className = 'amd-monitor-widget';

        widget.innerHTML =
            '<div class="amd-header">' +
                '<div class="amd-title">' +
                    '<span class="amd-icon">🔴</span>' +
                    '<span class="amd-text">AMD Monitor</span>' +
                '</div>' +
                '<div class="amd-controls">' +
                    '<button class="amd-btn amd-btn-settings" title="Settings">⚙</button>' +
                    '<button class="amd-btn amd-btn-minimize" title="Minimize">−</button>' +
                    '<button class="amd-btn amd-btn-close" title="Hide">✕</button>' +
                '</div>' +
            '</div>' +
            '<div class="amd-body">' +
                '<div class="amd-gpu-selector" id="amd-gpu-selector" style="display:none;">' +
                    '<span class="amd-label-small">GPU:</span>' +
                    '<div class="amd-chip-group" id="amd-gpu-chips"></div>' +
                '</div>' +
                '<div class="amd-gpu-name" id="amd-gpu-name">AMD GPU</div>' +
                '<div class="amd-grid">' +
                    '<div class="amd-stat"><span class="amd-label">GPU Load</span><span class="amd-value" id="amd-gpu-util">--</span><div class="amd-bar"><div class="amd-fill" id="amd-gpu-bar"></div></div></div>' +
                    '<div class="amd-stat"><span class="amd-label">VRAM</span><span class="amd-value" id="amd-vram">-- / -- GB</span><div class="amd-bar"><div class="amd-fill" id="amd-vram-bar"></div></div></div>' +
                    '<div class="amd-stat"><span class="amd-label">Temp</span><span class="amd-value" id="amd-temp">N/A</span><div class="amd-bar"><div class="amd-fill amd-temp" id="amd-temp-bar"></div></div></div>' +
                    '<div class="amd-stat"><span class="amd-label">Fan</span><span class="amd-value" id="amd-fan">N/A</span><div class="amd-bar"><div class="amd-fill" id="amd-fan-bar"></div></div></div>' +
                '</div>' +
                '<div class="amd-sparkline-container" id="amd-sparkline-container">' +
                    '<div class="amd-label-small">GPU Load History (30s)</div>' +
                    '<canvas class="amd-sparkline" id="amd-sparkline" width="232" height="40"></canvas>' +
                '</div>' +
                '<div class="amd-process" id="amd-process">' +
                    '<div class="amd-process-header">' +
                        '<span class="amd-label-small">Generation Stats</span>' +
                        '<span class="amd-process-status" id="amd-process-status">● idle</span>' +
                    '</div>' +
                    '<div class="amd-process-body">' +
                        '<div class="amd-stat-row"><span class="amd-label-xs">Duration</span><span class="amd-value-sm" id="amd-gen-duration">--</span></div>' +
                        '<div class="amd-stat-row"><span class="amd-label-xs">RAM Peak</span><span class="amd-value-sm" id="amd-gen-ram-peak">--</span></div>' +
                        '<div class="amd-stat-row"><span class="amd-label-xs">VRAM Used</span><span class="amd-value-sm" id="amd-gen-vram-used">--</span></div>' +
                        '<div class="amd-stat-row"><span class="amd-label-xs">CPU Peak</span><span class="amd-value-sm" id="amd-gen-cpu-peak">--</span></div>' +
                    '</div>' +
                '</div>' +
                '<div class="amd-alert" id="amd-alert" style="display:none;">' +
                    '<span class="amd-alert-icon">⚠️</span><span class="amd-alert-text" id="amd-alert-text">VRAM Alert</span>' +
                '</div>' +
                '<div class="amd-settings" id="amd-settings" style="display:none;">' +
                    '<div class="amd-settings-row"><span class="amd-label-small">Interval</span><select class="amd-select" id="amd-settings-interval"><option value="0.5">0.5s</option><option value="1" selected>1s</option><option value="5">5s</option><option value="10">10s</option></select></div>' +
                    '<div class="amd-settings-row"><span class="amd-label-small">VRAM Alert %</span><input type="number" class="amd-input" id="amd-settings-vram-threshold" value="90" min="50" max="100" /></div>' +
                    '<div class="amd-settings-row"><span class="amd-label-small">Temp Unit</span><select class="amd-select" id="amd-settings-temp-unit"><option value="celsius" selected>°C</option><option value="fahrenheit">°F</option></select></div>' +
                    '<div class="amd-settings-row"><span class="amd-label-small">Sparkline</span><label class="amd-toggle"><input type="checkbox" id="amd-settings-sparkline" checked /><span class="amd-toggle-slider"></span></label></div>' +
                '</div>' +
                '<div class="amd-footer"><span class="amd-status" id="amd-status">Initializing...</span><span class="amd-method" id="amd-method">--</span></div>' +
            '</div>';

        var style = document.createElement('style');
        style.id = 'bangtrix-amd-monitor-styles';
        style.textContent =
            '#bangtrix-amd-monitor{position:fixed;top:60px;right:20px;width:260px;' +
            'background:rgba(18,18,24,0.92);border:1px solid rgba(196,48,43,0.3);border-radius:10px;' +
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;' +
            'color:#e0e0e0;z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.4);' +
            'backdrop-filter:blur(8px);user-select:none;}' +
            '#bangtrix-amd-monitor.hidden{display:none}' +
            '#bangtrix-amd-monitor.minimized .amd-body{display:none}' +
            '.amd-header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;' +
            'background:linear-gradient(135deg,rgba(196,48,43,0.2)0%,rgba(139,32,29,0.1)100%);' +
            'border-radius:10px 10px 0 0;cursor:move;border-bottom:1px solid rgba(255,255,255,0.05)}' +
            '.amd-title{display:flex;align-items:center;gap:8px;font-weight:600;font-size:12px;color:#fff}' +
            '.amd-icon{font-size:14px;animation:pulse 1s infinite}' +
            '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
            '.amd-controls{display:flex;gap:4px}' +
            '.amd-btn{background:rgba(255,255,255,0.1);border:none;color:#ccc;width:22px;height:22px;border-radius:4px;cursor:pointer;font-size:12px}' +
            '.amd-btn:hover{background:rgba(255,255,255,0.2);color:#fff}' +
            '.amd-btn-close:hover{background:rgba(255,80,80,0.3)}' +
            '.amd-body{padding:12px 14px}' +
            '.amd-gpu-name{text-align:center;font-size:11px;font-weight:600;color:#ff6b6b;margin-bottom:8px;' +
            'padding:4px 8px;border-radius:4px;background:rgba(255,255,255,0.04);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
            '.amd-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}' +
            '.amd-stat{display:flex;flex-direction:column;gap:2px}' +
            '.amd-label{color:#888;font-size:10px;text-transform:uppercase}' +
            '.amd-label-small{color:#888;font-size:10px}' +
            '.amd-value{font-weight:600;font-size:13px;color:#00e676;transition:color 0.3s ease}' +
            '.amd-value.na{color:#666}' +
            '.amd-value.warning{color:#ffaa00}' +
            '.amd-value.critical{color:#ff4444}' +
            '.amd-bar{height:4px;background:rgba(255,255,255,0.1);border-radius:2px;overflow:hidden;margin-top:2px}' +
            '.amd-fill{height:100%;border-radius:2px;width:0%;background:linear-gradient(90deg,#00e676,#00c853);' +
            'transition:width 0.4s cubic-bezier(0.4,0,0.2,1)}' +
            '.amd-fill.amd-temp{background:linear-gradient(90deg,#00e676,#ffaa00,#ff4444)}' +
            '.amd-sparkline-container{margin-top:8px}' +
            '.amd-sparkline{width:100%;height:40px;border-radius:4px;background:rgba(0,0,0,0.3)}' +
            '.amd-process{margin-top:8px;padding:6px 8px;background:rgba(0,0,0,0.2);border-radius:6px;border:1px solid rgba(255,255,255,0.06)}' +
            '.amd-process-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}' +
            '.amd-process-status{font-size:10px}' +
            '.amd-process-status.generating{color:#00e676}' +
            '.amd-process-status.idle{color:#888}' +
            '.amd-process-body{display:grid;grid-template-columns:1fr 1fr;gap:2px 8px}' +
            '.amd-stat-row{display:flex;justify-content:space-between}' +
            '.amd-label-xs{color:#666;font-size:9px}' +
            '.amd-value-sm{color:#ccc;font-size:10px}' +
            '.amd-alert{display:flex;align-items:center;gap:6px;padding:6px 10px;margin-top:8px;' +
            'background:rgba(255,80,80,0.15);border:1px solid rgba(255,80,80,0.3);border-radius:6px;font-size:11px;color:#ff6b6b}' +
            '.amd-settings{margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05)}' +
            '.amd-settings-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}' +
            '.amd-select,.amd-input{background:rgba(255,255,255,0.1);border:1px solid rgba(255,255,255,0.15);color:#e0e0e0;padding:2px 6px;border-radius:4px;font-size:10px;width:70px}' +
            '.amd-input{width:50px}' +
            '.amd-toggle{position:relative;width:32px;height:16px;cursor:pointer}' +
            '.amd-toggle input{display:none}' +
            '.amd-toggle-slider{position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(255,255,255,0.15);border-radius:8px;transition:0.2s}' +
            '.amd-toggle-slider:before{content:"";position:absolute;width:12px;height:12px;left:2px;bottom:2px;background:#ccc;border-radius:50%;transition:0.2s}' +
            '.amd-toggle input:checked+.amd-toggle-slider{background:rgba(196,48,43,0.6)}' +
            '.amd-toggle input:checked+.amd-toggle-slider:before{transform:translateX(16px);background:#fff}' +
            '.amd-footer{display:flex;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);font-size:10px;color:#666}' +
            '.amd-status{transition:color 0.2s}' +
            '.amd-status.connected{color:#00e676}' +
            '.amd-status.disconnected{color:#ff4444}' +
            '.amd-status.warning{color:#ffaa00}' +
            '.amd-status.live{color:#00e676;animation:livePulse 1.5s infinite}' +
            '@keyframes livePulse{0%,100%{color:#00e676}50%{color:#00e67688}}' +
            '.amd-method{color:#888;font-family:monospace;font-size:9px}';
        document.head.appendChild(style);

        document.body.appendChild(widget);
        setupDrag();
    }

    // ===== DRAG =====
    function setupDrag() {
        var header = widget.querySelector('.amd-header');
        if (!header) return;
        header.addEventListener('mousedown', function(e) {
            if (e.target.closest('.amd-btn')) return;
            isDragging = true;
            var rect = widget.getBoundingClientRect();
            dragOffset.x = e.clientX - rect.left;
            dragOffset.y = e.clientY - rect.top;
            widget.style.transition = 'none';
            document.body.style.cursor = 'grabbing';
            document.addEventListener('mousemove', onDrag);
            document.addEventListener('mouseup', stopDrag);
        });
        function onDrag(e) {
            if (!isDragging) return;
            var maxX = window.innerWidth - widget.offsetWidth + 20;
            var maxY = window.innerHeight - widget.offsetHeight + 20;
            widget.style.left = Math.max(10, Math.min(e.clientX - dragOffset.x, maxX)) + 'px';
            widget.style.top = Math.max(10, Math.min(e.clientY - dragOffset.y, maxY)) + 'px';
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

    // ===== EVENT LISTENERS =====
    function setupEventListeners() {
        var minBtn = widget.querySelector('.amd-btn-minimize');
        if (minBtn) minBtn.addEventListener('click', function() {
            isMinimized = !isMinimized;
            widget.classList.toggle('minimized', isMinimized);
            minBtn.textContent = isMinimized ? '+' : '−';
            saveConfig();
        });

        var closeBtn = widget.querySelector('.amd-btn-close');
        if (closeBtn) closeBtn.addEventListener('click', function() {
            isVisible = false;
            widget.classList.add('hidden');
            saveConfig();
            showToast('Hidden. Ctrl+Shift+M to show.');
        });

        var settingsBtn = widget.querySelector('.amd-btn-settings');
        var settingsPanel = $('amd-settings');
        if (settingsBtn && settingsPanel) settingsBtn.addEventListener('click', function() {
            var isOpen = settingsPanel.style.display !== 'none';
            settingsPanel.style.display = isOpen ? 'none' : 'block';
            settingsBtn.classList.toggle('active', !isOpen);
        });

        var intervalSelect = $('amd-settings-interval');
        if (intervalSelect) intervalSelect.addEventListener('change', function(e) {
            sendCommand({type:'set_interval',interval:parseFloat(e.target.value)});
            saveConfig();
        });

        var vramInput = $('amd-settings-vram-threshold');
        if (vramInput) vramInput.addEventListener('change', function(e) {
            savedConfig.vramThreshold = parseInt(e.target.value) || 90;
            saveConfig();
        });

        var tempSelect = $('amd-settings-temp-unit');
        if (tempSelect) tempSelect.addEventListener('change', function(e) {
            savedConfig.tempUnit = e.target.value;
            saveConfig();
            if (gpuDataMap[selectedGpuId]) refreshDisplay(selectedGpuId);
        });

        var sparkCheck = $('amd-settings-sparkline');
        if (sparkCheck) sparkCheck.addEventListener('change', function(e) {
            var container = $('amd-sparkline-container');
            if (container) container.style.display = e.target.checked ? 'block' : 'none';
            saveConfig();
        });

        document.addEventListener('keydown', function(e) {
            if (e.ctrlKey && e.shiftKey && e.key === 'M') {
                e.preventDefault();
                isVisible = !isVisible;
                widget.classList.toggle('hidden', !isVisible);
                if (isVisible) connectWebSocket();
                saveConfig();
            }
        });
    }

    // ===== CONFIG =====
    function loadConfig() {
        try { var saved = localStorage.getItem(CONFIG.storageKey); if (saved) savedConfig = JSON.parse(saved); } catch(e) {}
    }

    function applyConfigToWidget() {
        if (!widget) return;
        var c = savedConfig;
        if (c.position) {
            if (c.position.left) { widget.style.left = c.position.left; widget.style.right = 'auto'; }
            if (c.position.top) widget.style.top = c.position.top;
        }
        if (c.minimized !== undefined) {
            isMinimized = c.minimized;
            widget.classList.toggle('minimized', isMinimized);
            var btn = widget.querySelector('.amd-btn-minimize');
            if (btn) btn.textContent = isMinimized ? '+' : '−';
        }
        if (c.visible !== undefined) { isVisible = c.visible; widget.classList.toggle('hidden', !isVisible); }
        var sel = $('amd-settings-interval'); if (sel) sel.value = String(c.updateInterval || 1);
        var inp = $('amd-settings-vram-threshold'); if (inp) inp.value = c.vramThreshold || 90;
        var sel2 = $('amd-settings-temp-unit'); if (sel2) sel2.value = c.tempUnit || 'celsius';
        var chk = $('amd-settings-sparkline');
        if (chk) { chk.checked = c.showSparkline !== false; var cont = $('amd-sparkline-container'); if (cont) cont.style.display = 'block'; }
    }

    function saveConfig() {
        try {
            var config = {
                position: { top: widget.style.top, left: widget.style.left },
                minimized: isMinimized, visible: isVisible,
                updateInterval: parseFloat($('amd-settings-interval')?.value) || 1,
                vramThreshold: parseInt($('amd-settings-vram-threshold')?.value) || 90,
                tempUnit: $('amd-settings-temp-unit')?.value || 'celsius',
                showSparkline: $('amd-settings-sparkline')?.checked !== false
            };
            localStorage.setItem(CONFIG.storageKey, JSON.stringify(config));
        } catch(e) {}
    }

    // ===== WEBSOCKET =====
    function connectWebSocket() {
        if (ws && ws.readyState === WebSocket.OPEN) return;
        if (!isVisible) return;
        var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        var url = protocol + '//' + window.location.host + '/ws/amd_monitor';
        console.log('[AMD Monitor] Connecting...');
        updateStatus('Connecting...', 'warning');
        ws = new WebSocket(url);
        ws.onopen = function() {
            console.log('[AMD Monitor] Connected — Real-Time');
            updateStatus('● LIVE', 'live');
            updateMethod('Real-Time 500ms');
            reconnectAttempts = 0;
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
        };
        ws.onmessage = function(event) {
            try {
                var data = JSON.parse(event.data);
                if (data.type === 'amd_stats') handleStatsData(data);
            } catch(e) {}
        };
        ws.onclose = function() {
            updateStatus('Disconnected', 'disconnected');
            updateMethod('--');
            if (reconnectAttempts < MAX_RECONNECT) {
                reconnectAttempts++;
                var delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 10000);
                reconnectTimer = setTimeout(connectWebSocket, delay);
            }
        };
        ws.onerror = function() {};
    }

    function sendCommand(cmd) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(cmd)); }

    // ===== DATA HANDLING =====
    function handleStatsData(data) {
        gpuDataMap[data.gpu_id] = data;
        if (data.gpu_count && gpuCount !== data.gpu_count) { gpuCount = data.gpu_count; updateGpuSelector(); }
        if (data.gpu_id === selectedGpuId) {
            // Use requestAnimationFrame for smooth UI updates
            if (animationFrame) cancelAnimationFrame(animationFrame);
            animationFrame = requestAnimationFrame(function() {
                refreshDisplay(selectedGpuId);
                animationFrame = null;
            });
        }
    }

    function refreshDisplay(gpuId) {
        var data = gpuDataMap[gpuId];
        if (!data) return;

        var nameEl = $('amd-gpu-name');
        if (nameEl) nameEl.textContent = data.gpu_name || ('AMD GPU ' + gpuId);

        if (!data.is_available) {
            ['amd-gpu-util','amd-vram','amd-temp','amd-fan'].forEach(function(id) { setStat(id, 'N/A'); });
            ['amd-gpu-bar','amd-vram-bar','amd-temp-bar','amd-fan-bar'].forEach(function(id) { setBar(id, 0); });
            updateStatus(data.error || 'Unavailable', 'warning');
            updateMethod(data.method || '--');
            return;
        }

        // GPU Load
        var gpuUtil = data.gpu_utilization !== undefined ? data.gpu_utilization : 0;
        setStat('amd-gpu-util', gpuUtil.toFixed(1) + '%', gpuUtil);
        setBar('amd-gpu-bar', gpuUtil);

        // VRAM — REAL-TIME used/total
        var vramUsedMB = data.vram_used_mb || 0;
        var vramTotalMB = data.vram_total_mb || 0;
        var vramPct = data.vram_usage_pct || (vramTotalMB > 0 ? (vramUsedMB / vramTotalMB * 100) : 0);
        if (vramTotalMB > 0 && vramUsedMB > 0) {
            setStat('amd-vram', (vramUsedMB / 1024).toFixed(2) + ' / ' + (vramTotalMB / 1024).toFixed(1) + ' GB', vramPct);
            setBar('amd-vram-bar', vramPct);
        } else if (vramTotalMB > 0) {
            setStat('amd-vram', '0 / ' + (vramTotalMB / 1024).toFixed(1) + ' GB', 0);
            setBar('amd-vram-bar', 0);
        } else {
            setStat('amd-vram', 'N/A');
            setBar('amd-vram-bar', 0);
        }

        // Temperature
        var temp = data.temperature || 0;
        if (temp > 0) {
            var tUnit = savedConfig.tempUnit || 'celsius';
            var tempDisplay = temp;
            var tempUnitStr = '°C';
            if (tUnit === 'fahrenheit') { tempDisplay = temp * 9/5 + 32; tempUnitStr = '°F'; }
            setStat('amd-temp', tempDisplay.toFixed(1) + tempUnitStr, temp);
            setBar('amd-temp-bar', Math.min(temp, 100));
        } else { setStat('amd-temp', 'N/A'); setBar('amd-temp-bar', 0); }

        // Fan
        var fan = data.fan_speed || 0;
        if (fan > 0) { setStat('amd-fan', fan + '%', fan); setBar('amd-fan-bar', fan); }
        else { setStat('amd-fan', 'N/A'); setBar('amd-fan-bar', 0); }

        // Status
        var methodInfo = 'Real-Time';
        if (data.core_clock_mhz > 0) methodInfo += ' | ' + data.core_clock_mhz + 'MHz';
        if (data.power_draw_watts > 0) methodInfo += ' | ' + data.power_draw_watts + 'W';
        updateMethod(methodInfo);

        var statusText = data.gpu_name || ('GPU ' + gpuId);
        if (gpuCount > 1) statusText += ' (' + (gpuId + 1) + '/' + gpuCount + ')';
        updateStatus('● LIVE', 'live');

        // Sparkline
        if (data.history && data.history.length > 0) {
            historyData = data.history;
            drawSparkline(historyData);
            var sparkContainer = $('amd-sparkline-container');
            if (sparkContainer) {
                var chk = $('amd-settings-sparkline');
                sparkContainer.style.display = (chk && chk.checked) ? 'block' : 'none';
            }
        }

        // Process stats
        updateProcessDisplay(data);
        checkVramAlert(vramPct);
    }

    function updateProcessDisplay(data) {
        var process = data.process;
        if (!process) return;
        var statusEl = $('amd-process-status');
        var durEl = $('amd-gen-duration');
        var ramPeakEl = $('amd-gen-ram-peak');
        var vramUsedEl = $('amd-gen-vram-used');
        var cpuPeakEl = $('amd-gen-cpu-peak');
        if (!statusEl) return;

        if (process.is_generating && process.generation) {
            var gen = process.generation;
            statusEl.textContent = '● generating';
            statusEl.className = 'amd-process-status generating';
            if (durEl) durEl.textContent = gen.duration + 's';
            if (ramPeakEl) ramPeakEl.textContent = gen.ram_peak_mb + ' MB';
            if (vramUsedEl) vramUsedEl.textContent = gen.vram_peak_mb + ' MB';
            if (cpuPeakEl) cpuPeakEl.textContent = gen.cpu_peak + '%';
        } else if (process.last_generation) {
            var last = process.last_generation;
            statusEl.textContent = '● idle (' + (process.generation_count || 0) + ' gens)';
            statusEl.className = 'amd-process-status idle';
            if (durEl) durEl.textContent = last.duration + 's';
            if (ramPeakEl) ramPeakEl.textContent = last.ram_peak_mb + ' MB';
            if (vramUsedEl) vramUsedEl.textContent = '+' + last.vram_delta_mb + ' MB peak';
            if (cpuPeakEl) cpuPeakEl.textContent = last.cpu_peak + '%';
        } else {
            statusEl.textContent = '● idle';
            statusEl.className = 'amd-process-status idle';
            if (durEl) durEl.textContent = '--'; if (ramPeakEl) ramPeakEl.textContent = '--';
            if (vramUsedEl) vramUsedEl.textContent = '--'; if (cpuPeakEl) cpuPeakEl.textContent = '--';
        }
    }

    function updateGpuSelector() {
        var selector = $('amd-gpu-selector');
        var chips = $('amd-gpu-chips');
        if (!selector || !chips) return;
        if (gpuCount <= 1) { selector.style.display = 'none'; return; }
        selector.style.display = 'block';
        chips.innerHTML = '';
        for (var i = 0; i < gpuCount; i++) (function(idx) {
            var chip = document.createElement('span');
            chip.className = 'amd-chip' + (idx === selectedGpuId ? ' active' : '');
            chip.textContent = 'GPU ' + idx;
            chip.addEventListener('click', function() {
                selectedGpuId = idx;
                chips.querySelectorAll('.amd-chip').forEach(function(c) { c.classList.remove('active'); });
                chip.classList.add('active');
                refreshDisplay(selectedGpuId);
            });
            chips.appendChild(chip);
        })(i);
    }

    // ===== SPARKLINE =====
    function drawSparkline(values) {
        var canvas = $('amd-sparkline');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width, h = canvas.height, padding = 2;
        ctx.clearRect(0, 0, w, h);
        if (values.length < 2 || values.every(function(v) { return v === 0; })) {
            ctx.fillStyle = '#555'; ctx.font = '10px monospace'; ctx.textAlign = 'center';
            ctx.fillText('awaiting data...', w / 2, h / 2 + 3); return;
        }
        var max = Math.max.apply(null, values); if (max < 1) max = 1;
        var stepX = (w - padding * 2) / (values.length - 1);
        ctx.beginPath(); ctx.strokeStyle = '#00e676'; ctx.lineWidth = 1.5; ctx.lineJoin = 'round';
        for (var i = 0; i < values.length; i++) {
            var x = padding + i * stepX;
            var y = h - padding - (values[i] / max) * (h - padding * 2);
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.lineTo(padding + (values.length - 1) * stepX, h - padding);
        ctx.lineTo(padding, h - padding); ctx.closePath();
        ctx.fillStyle = 'rgba(0,230,118,0.1)'; ctx.fill();
        var lastVal = values[values.length - 1];
        ctx.fillStyle = '#00e676'; ctx.font = 'bold 9px monospace'; ctx.textAlign = 'right';
        ctx.fillText(lastVal.toFixed(0) + '%', w - padding, 10);
    }

    // ===== ALERTS =====
    var lastAlertTime = 0;
    function checkVramAlert(vramPct) {
        var threshold = savedConfig.vramThreshold || 90;
        if (vramPct >= threshold && Date.now() - lastAlertTime > 10000) {
            lastAlertTime = Date.now();
            var alertEl = $('amd-alert');
            var alertText = $('amd-alert-text');
            if (alertEl && alertText) {
                alertText.textContent = 'VRAM ' + vramPct.toFixed(0) + '% >= ' + threshold + '%';
                alertEl.style.display = 'flex';
                setTimeout(function() { if (alertEl) alertEl.style.display = 'none'; }, 5000);
            }
        }
    }

    // ===== UI HELPERS =====
    function setStat(elementId, value, numericValue) {
        var el = $(elementId);
        if (!el) return;
        el.textContent = value;
        el.classList.remove('warning', 'critical', 'na');
        if (value === 'N/A') { el.classList.add('na'); }
        else if (numericValue !== null && numericValue !== undefined) {
            if ((elementId === 'amd-temp') && numericValue > 80) el.classList.add('critical');
            else if ((elementId === 'amd-temp') && numericValue > 65) el.classList.add('warning');
            else if ((elementId === 'amd-gpu-util' || elementId.indexOf('vram') >= 0) && numericValue > 90) el.classList.add('critical');
            else if ((elementId === 'amd-gpu-util' || elementId.indexOf('vram') >= 0) && numericValue > 75) el.classList.add('warning');
        }
    }

    function setBar(elementId, percent) {
        var el = $(elementId); if (!el) return;
        el.style.width = Math.min(100, Math.max(0, percent)) + '%';
    }

    function updateStatus(message, className) {
        var el = $('amd-status'); if (!el) return;
        el.textContent = message; el.className = 'amd-status ' + className;
        var icon = widget.querySelector('.amd-icon');
        if (icon) icon.textContent = className === 'live' || className === 'connected' ? '🟢' : className === 'warning' ? '🟡' : '🔴';
        // Pulse faster when live
        if (className === 'live') {
            icon.style.animation = 'pulse 0.8s infinite';
        } else {
            icon.style.animation = 'pulse 2s infinite';
        }
    }

    function updateMethod(method) { var el = $('amd-method'); if (el) el.textContent = method || ''; }

    function showToast(message, duration) {
        duration = duration || 2000;
        var old = document.querySelector('.bangtrix-toast'); if (old) old.remove();
        var toast = document.createElement('div');
        toast.className = 'bangtrix-toast';
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;bottom:20px;right:20px;background:rgba(30,30,40,0.95);color:#fff;padding:10px 16px;border-radius:6px;font-size:12px;z-index:10001;border:1px solid rgba(196,48,43,0.5);animation:slideIn 0.2s ease;max-width:300px;';
        document.body.appendChild(toast);
        setTimeout(function() { toast.style.animation = 'slideOut 0.2s ease'; setTimeout(function() { toast.remove(); }, 200); }, duration);
    }

    // ===== ANIMATIONS =====
    if (!document.getElementById('amd-monitor-animations')) {
        var s = document.createElement('style');
        s.id = 'amd-monitor-animations';
        s.textContent = '@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}@keyframes slideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(100%);opacity:0}}';
        document.head.appendChild(s);
    }

    // ===== AMD CHIP SELECTOR =====
    if (!document.getElementById('amd-chip-styles')) {
        var cs = document.createElement('style');
        cs.id = 'amd-chip-styles';
        cs.textContent = '.amd-chip{padding:2px 8px;border-radius:10px;font-size:10px;background:rgba(255,255,255,0.08);cursor:pointer;transition:all 0.15s;border:1px solid transparent}.amd-chip:hover{background:rgba(255,255,255,0.15)}.amd-chip.active{background:rgba(196,48,43,0.3);border-color:rgba(196,48,43,0.5);color:#fff}.amd-gpu-selector{margin-bottom:6px}.amd-chip-group{display:flex;gap:4px;flex-wrap:wrap}';
        document.head.appendChild(cs);
    }

    // ===== START =====
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();

    window.addEventListener('beforeunload', function() { if (ws) ws.close(); if (reconnectTimer) clearTimeout(reconnectTimer); });
})();