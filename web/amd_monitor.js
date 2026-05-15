/**
 * BANGTRIXTOOLKIT - AMD Monitor Floating Widget
 * Real-time AMD GPU monitoring overlay for ComfyUI
 * Cross-platform: Windows (ADL) / Linux (ROCm)
 */

(function() {
    "use strict";

    // ===== CONFIGURATION =====
    const CONFIG = {
        wsUrl: `ws://${window.location.host}/ws/amd_monitor`,
        updateInterval: 1000,
        storageKey: 'bangtrix_amd_monitor_config',
        defaultPosition: { top: '60px', right: '20px' }
    };

    // ===== STATE =====
    let ws = null;
    let reconnectTimer = null;
    let reconnectAttempts = 0;
    const MAX_RECONNECT = 5;
    
    // Widget state
    let widget = null;
    let isMinimized = false;
    let isVisible = true;
    let isDragging = false;
    let dragOffset = { x: 0, y: 0 };

    // ===== INITIALIZATION =====
    function init() {
        if (document.getElementById('bangtrix-amd-monitor')) {
            console.log('AMD Monitor: Already initialized');
            return;
        }
        
        console.log('AMD Monitor: Initializing floating widget...');
        createWidget();
        setupEventListeners();
        loadConfig();
        connectWebSocket();
    }

    // ===== WIDGET CREATION =====
    function createWidget() {
        widget = document.createElement('div');
        widget.id = 'bangtrix-amd-monitor';
        widget.className = 'amd-monitor-widget';
        
        widget.innerHTML = `
            <div class="amd-header">
                <div class="amd-title">
                    <span class="amd-icon">🔴</span>
                    <span class="amd-text">AMD Monitor</span>
                </div>
                <div class="amd-controls">
                    <button class="amd-btn amd-btn-minimize" title="Minimize">−</button>
                    <button class="amd-btn amd-btn-settings" title="Settings">⚙</button>
                    <button class="amd-btn amd-btn-close" title="Hide">✕</button>
                </div>
            </div>
            
            <div class="amd-body">
                <div class="amd-grid">
                    <div class="amd-stat">
                        <span class="amd-label">GPU Load</span>
                        <span class="amd-value" id="amd-gpu-util">--</span>
                        <div class="amd-bar"><div class="amd-fill" id="amd-gpu-bar"></div></div>
                    </div>
                    <div class="amd-stat">
                        <span class="amd-label">VRAM</span>
                        <span class="amd-value" id="amd-vram">-- / -- GB</span>
                        <div class="amd-bar"><div class="amd-fill" id="amd-vram-bar"></div></div>
                    </div>
                    <div class="amd-stat">
                        <span class="amd-label">Temperature</span>
                        <span class="amd-value" id="amd-temp">--°C</span>
                        <div class="amd-bar"><div class="amd-fill amd-temp" id="amd-temp-bar"></div></div>
                    </div>
                    <div class="amd-stat">
                        <span class="amd-label">Fan Speed</span>
                        <span class="amd-value" id="amd-fan">--%</span>
                        <div class="amd-bar"><div class="amd-fill" id="amd-fan-bar"></div></div>
                    </div>
                </div>
                
                <div class="amd-footer">
                    <span class="amd-status" id="amd-status">Initializing...</span>
                    <span class="amd-method" id="amd-method">--</span>
                </div>
            </div>
        `;

        injectStyles();
        document.body.appendChild(widget);
        setupDrag();
        
        return widget;
    }

    function injectStyles() {
        const style = document.createElement('style');
        style.id = 'bangtrix-amd-monitor-styles';
        style.textContent = `
            #bangtrix-amd-monitor {
                position: fixed;
                top: 60px;
                right: 20px;
                width: 240px;
                background: rgba(18, 18, 24, 0.92);
                border: 1px solid rgba(196, 48, 43, 0.3);
                border-radius: 10px;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                font-size: 11px;
                color: #e0e0e0;
                z-index: 9999;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
                backdrop-filter: blur(8px);
                user-select: none;
                transition: opacity 0.2s, transform 0.2s;
            }
            
            #bangtrix-amd-monitor.hidden { display: none; }
            #bangtrix-amd-monitor.minimized .amd-body { display: none; }
            
            .amd-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 10px 14px;
                background: linear-gradient(135deg, rgba(196, 48, 43, 0.2) 0%, rgba(139, 32, 29, 0.1) 100%);
                border-radius: 10px 10px 0 0;
                cursor: move;
                border-bottom: 1px solid rgba(255,255,255,0.05);
            }
            
            .amd-title {
                display: flex;
                align-items: center;
                gap: 8px;
                font-weight: 600;
                font-size: 12px;
                color: #fff;
            }
            
            .amd-icon { font-size: 14px; animation: pulse 2s infinite; }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }
            
            .amd-controls { display: flex; gap: 4px; }
            
            .amd-btn {
                background: rgba(255,255,255,0.1);
                border: none;
                color: #ccc;
                width: 22px;
                height: 22px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 12px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.15s;
            }
            
            .amd-btn:hover { background: rgba(255,255,255,0.2); color: #fff; }
            .amd-btn-close:hover { background: rgba(255, 80, 80, 0.3); color: #fff; }
            
            .amd-body { padding: 12px 14px; }
            .amd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 14px; }
            
            .amd-stat {
                display: flex;
                flex-direction: column;
                gap: 4px;
            }
            
            .amd-label {
                color: #888;
                font-size: 10px;
                text-transform: uppercase;
                letter-spacing: 0.3px;
            }
            
            .amd-value {
                font-weight: 600;
                font-size: 13px;
                color: #00e676;
                transition: color 0.2s;
            }
            
            .amd-value.warning { color: #ffaa00; }
            .amd-value.critical { color: #ff4444; }
            
            .amd-bar {
                height: 4px;
                background: rgba(255,255,255,0.1);
                border-radius: 2px;
                overflow: hidden;
                margin-top: 2px;
            }
            
            .amd-fill {
                height: 100%;
                background: linear-gradient(90deg, #00e676, #00c853);
                border-radius: 2px;
                transition: width 0.3s ease;
                width: 0%;
            }
            
            .amd-fill.amd-temp {
                background: linear-gradient(90deg, #00e676, #ffaa00, #ff4444);
            }
            
            .amd-footer {
                display: flex;
                justify-content: space-between;
                margin-top: 14px;
                padding-top: 10px;
                border-top: 1px solid rgba(255,255,255,0.05);
                font-size: 10px;
                color: #666;
            }
            
            .amd-status { transition: color 0.2s; }
            .amd-status.connected { color: #00e676; }
            .amd-status.disconnected { color: #ff4444; }
            .amd-status.warning { color: #ffaa00; }
            
            .amd-method { color: #888; font-family: monospace; }
            .amd-header:active { cursor: grabbing; }
            
            @media (max-width: 768px) {
                #bangtrix-amd-monitor { width: 200px; font-size: 10px; }
                .amd-grid { grid-template-columns: 1fr; }
            }
        `;
        document.head.appendChild(style);
    }

    // ===== DRAG FUNCTIONALITY =====
    function setupDrag() {
        const header = widget.querySelector('.amd-header');
        
        header.addEventListener('mousedown', (e) => {
            if (e.target.closest('.amd-btn')) return;
            
            isDragging = true;
            const rect = widget.getBoundingClientRect();
            dragOffset.x = e.clientX - rect.left;
            dragOffset.y = e.clientY - rect.top;
            
            widget.style.transition = 'none';
            document.body.style.cursor = 'grabbing';
            
            document.addEventListener('mousemove', onDrag);
            document.addEventListener('mouseup', stopDrag);
        });
        
        function onDrag(e) {
            if (!isDragging) return;
            
            const x = e.clientX - dragOffset.x;
            const y = e.clientY - dragOffset.y;
            
            const maxX = window.innerWidth - widget.offsetWidth + 20;
            const maxY = window.innerHeight - widget.offsetHeight + 20;
            
            widget.style.left = Math.max(10, Math.min(x, maxX)) + 'px';
            widget.style.top = Math.max(10, Math.min(y, maxY)) + 'px';
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
        widget.querySelector('.amd-btn-minimize').addEventListener('click', () => {
            isMinimized = !isMinimized;
            widget.classList.toggle('minimized', isMinimized);
            widget.querySelector('.amd-btn-minimize').textContent = isMinimized ? '+' : '−';
            saveConfig();
        });
        
        widget.querySelector('.amd-btn-close').addEventListener('click', () => {
            isVisible = !isVisible;
            widget.classList.toggle('hidden', !isVisible);
            saveConfig();
        });
        
        widget.querySelector('.amd-btn-settings').addEventListener('click', () => {
            showToast('Settings coming soon!');
        });
    }

    // ===== CONFIGURATION PERSISTENCE =====
    function loadConfig() {
        try {
            const saved = localStorage.getItem(CONFIG.storageKey);
            if (saved) {
                const config = JSON.parse(saved);
                if (config.position) {
                    if (config.position.left) {
                        widget.style.left = config.position.left;
                        widget.style.right = 'auto';
                    }
                    if (config.position.top) {
                        widget.style.top = config.position.top;
                    }
                }
                if (config.minimized !== undefined) {
                    isMinimized = config.minimized;
                    widget.classList.toggle('minimized', isMinimized);
                    widget.querySelector('.amd-btn-minimize').textContent = isMinimized ? '+' : '−';
                }
                if (config.visible !== undefined) {
                    isVisible = config.visible;
                    widget.classList.toggle('hidden', !isVisible);
                }
            }
        } catch (e) {
            console.warn('AMD Monitor: Failed to load config:', e);
        }
    }

    function saveConfig() {
        try {
            const config = {
                position: {
                    top: widget.style.top,
                    left: widget.style.left
                },
                minimized: isMinimized,
                visible: isVisible
            };
            localStorage.setItem(CONFIG.storageKey, JSON.stringify(config));
        } catch (e) {
            console.warn('AMD Monitor: Failed to save config:', e);
        }
    }

    // ===== WEBSOCKET CONNECTION =====
    function connectWebSocket() {
        if (ws?.readyState === WebSocket.OPEN) return;
        
        console.log('AMD Monitor: Connecting to', CONFIG.wsUrl);
        updateStatus('Connecting...', 'warning');
        
        ws = new WebSocket(CONFIG.wsUrl);
        
        ws.onopen = () => {
            console.log('AMD Monitor: Connected');
            updateStatus('Connected', 'connected');
            updateMethod('Live');
            reconnectAttempts = 0;
            if (reconnectTimer) {
                clearTimeout(reconnectTimer);
                reconnectTimer = null;
            }
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                if (data.type === 'amd_stats') {
                    updateDisplay(data);
                }
            } catch (e) {
                console.error('AMD Monitor: Parse error:', e);
            }
        };
        
        ws.onclose = () => {
            console.log('AMD Monitor: Disconnected');
            updateStatus('Disconnected', 'disconnected');
            updateMethod('--');
            
            if (reconnectAttempts < MAX_RECONNECT) {
                reconnectAttempts++;
                const delay = Math.min(1000 * Math.pow(1.5, reconnectAttempts), 8000);
                console.log(`AMD Monitor: Reconnecting in ${delay}ms (attempt ${reconnectAttempts})`);
                reconnectTimer = setTimeout(connectWebSocket, delay);
            }
        };
        
        ws.onerror = (error) => {
            console.error('AMD Monitor: WebSocket error:', error);
            updateStatus('Connection error', 'disconnected');
        };
    }

    // ===== DISPLAY UPDATES =====
    function updateDisplay(data) {
        if (!data.is_available) {
            setStat('amd-gpu-util', 'N/A');
            setStat('amd-vram', 'N/A');
            setStat('amd-temp', 'N/A');
            setStat('amd-fan', 'N/A');
            setBar('amd-gpu-bar', 0);
            setBar('amd-vram-bar', 0);
            setBar('amd-temp-bar', 0);
            setBar('amd-fan-bar', 0);
            updateStatus(data.error || 'AMD backend unavailable', 'warning');
            updateMethod(data.method || '--');
            return;
        }

        const gpuUtil = data.gpu_utilization || 0;
        setStat('amd-gpu-util', `${gpuUtil.toFixed(1)}%`, gpuUtil);
        setBar('amd-gpu-bar', gpuUtil);
        
        const vramUsedGB = (data.vram_used_mb || 0) / 1024;
        const vramTotalGB = (data.vram_total_mb || 0) / 1024;
        const vramPct = data.vram_usage_pct || (vramTotalGB > 0 ? (vramUsedGB / vramTotalGB * 100) : 0);
        setStat('amd-vram', `${vramUsedGB.toFixed(1)} / ${vramTotalGB.toFixed(1)} GB`, vramPct);
        setBar('amd-vram-bar', vramPct);
        
        const temp = data.temperature || 0;
        setStat('amd-temp', `${temp.toFixed(1)}°C`, temp);
        setBar('amd-temp-bar', Math.min(temp, 100));
        
        const fan = data.fan_speed || 0;
        setStat('amd-fan', `${fan}%`, fan);
        setBar('amd-fan-bar', fan);
        
        updateStatus(`GPU ${data.gpu_id}`, 'connected');
        updateMethod(data.method || 'unknown');
    }

    function setStat(elementId, value, numericValue = null) {
        const el = document.getElementById(elementId);
        if (!el) return;
        el.textContent = value;
        
        el.classList.remove('warning', 'critical');
        if (numericValue !== null) {
            if (elementId === 'amd-temp' && numericValue > 80) {
                el.classList.add('critical');
            } else if (elementId === 'amd-temp' && numericValue > 65) {
                el.classList.add('warning');
            } else if ((elementId === 'amd-gpu-util' || elementId === 'amd-vram') && numericValue > 90) {
                el.classList.add('critical');
            } else if ((elementId === 'amd-gpu-util' || elementId === 'amd-vram') && numericValue > 75) {
                el.classList.add('warning');
            }
        }
    }

    function setBar(elementId, percent) {
        const el = document.getElementById(elementId);
        if (!el) return;
        el.style.width = `${Math.min(100, Math.max(0, percent))}%`;
    }

    function updateStatus(message, className) {
        const el = document.getElementById('amd-status');
        if (!el) return;
        el.textContent = message;
        el.className = `amd-status ${className}`;
        
        const icon = widget.querySelector('.amd-icon');
        if (icon) {
            icon.textContent = className === 'connected' ? '🟢' : 
                               className === 'warning' ? '🟡' : '🔴';
        }
    }

    function updateMethod(method) {
        const el = document.getElementById('amd-method');
        if (!el) return;
        el.textContent = method ? `[${method}]` : '';
    }

    // ===== UTILITIES =====
    function showToast(message, duration = 2000) {
        const toast = document.createElement('div');
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(30, 30, 40, 0.95);
            color: #fff;
            padding: 10px 16px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 10001;
            border: 1px solid rgba(196, 48, 43, 0.5);
            animation: slideIn 0.2s ease;
        `;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOut 0.2s ease';
            setTimeout(() => toast.remove(), 200);
        }, duration);
    }

    if (!document.getElementById('amd-monitor-animations')) {
        const animStyle = document.createElement('style');
        animStyle.id = 'amd-monitor-animations';
        animStyle.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(animStyle);
    }

    // ===== START =====
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    window.addEventListener('beforeunload', () => {
        if (ws) ws.close();
        if (reconnectTimer) clearTimeout(reconnectTimer);
    });

})();