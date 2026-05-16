/**
 * BANGTRIXTOOLKIT - AMD Monitor Overlay v4.0
 * Real-time AMD GPU monitoring overlay for ComfyUI
 * Features: Theme system, Real-time 500ms updates, smooth CSS transitions, live VRAM
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
    var currentTheme = 'dark';
    var animationFrame = null;

    // ===== THEMES =====
    var THEMES = {
        dark: {
            name: 'Dark',
            bg: 'rgba(18,18,24,0.92)',
            border: 'rgba(196,48,43,0.3)',
            headerGrad1: 'rgba(196,48,43,0.2)',
            headerGrad2: 'rgba(139,32,29,0.1)',
            text: '#e0e0e0',
            textBright: '#ffffff',
            accent: '#00e676',
            accent2: '#00c853',
            accentGpu: '#ff6b6b',
            bgSecondary: 'rgba(255,255,255,0.04)',
            barBg: 'rgba(255,255,255,0.1)',
            btnBg: 'rgba(255,255,255,0.1)',
            btnHover: 'rgba(255,255,255,0.2)',
            labelColor: '#888',
            valueColor: '#00e676',
            toggleOn: 'rgba(196,48,43,0.6)',
            toggleOff: 'rgba(255,255,255,0.15)',
            processBg: 'rgba(0,0,0,0.2)',
            sparkBg: 'rgba(0,0,0,0.3)',
            alertBg: 'rgba(255,80,80,0.15)',
            alertBorder: 'rgba(255,80,80,0.3)',
            alertColor: '#ff6b6b',
            tempGrad: 'linear-gradient(90deg,#00e676,#ffaa00,#ff4444)',
            gridColor: 'rgba(255,255,255,0.04)',
        },
        light: {
            name: 'Light',
            bg: 'rgba(245,245,250,0.95)',
            border: 'rgba(200,50,50,0.2)',
            headerGrad1: 'rgba(200,50,50,0.1)',
            headerGrad2: 'rgba(200,50,50,0.05)',
            text: '#333333',
            textBright: '#111111',
            accent: '#0088cc',
            accent2: '#006699',
            accentGpu: '#cc4444',
            bgSecondary: 'rgba(0,0,0,0.04)',
            barBg: 'rgba(0,0,0,0.08)',
            btnBg: 'rgba(0,0,0,0.06)',
            btnHover: 'rgba(0,0,0,0.12)',
            labelColor: '#888',
            valueColor: '#0088cc',
            toggleOn: '#0088cc',
            toggleOff: 'rgba(0,0,0,0.15)',
            processBg: 'rgba(0,0,0,0.04)',
            sparkBg: 'rgba(0,0,0,0.06)',
            alertBg: 'rgba(255,80,80,0.1)',
            alertBorder: 'rgba(255,80,80,0.25)',
            alertColor: '#cc3333',
            tempGrad: 'linear-gradient(90deg,#0088cc,#ff8800,#ff4444)',
            gridColor: 'rgba(0,0,0,0.06)',
        },
        red: {
            name: 'Red',
            bg: 'rgba(24,10,10,0.92)',
            border: 'rgba(220,40,40,0.4)',
            headerGrad1: 'rgba(220,40,40,0.25)',
            headerGrad2: 'rgba(160,20,20,0.15)',
            text: '#e0c0c0',
            textBright: '#ffffff',
            accent: '#ff4444',
            accent2: '#cc2222',
            accentGpu: '#ff6666',
            bgSecondary: 'rgba(255,50,50,0.06)',
            barBg: 'rgba(255,50,50,0.12)',
            btnBg: 'rgba(255,50,50,0.12)',
            btnHover: 'rgba(255,50,50,0.22)',
            labelColor: '#cc9999',
            valueColor: '#ff4444',
            toggleOn: '#ff4444',
            toggleOff: 'rgba(255,50,50,0.2)',
            processBg: 'rgba(255,20,20,0.08)',
            sparkBg: 'rgba(255,20,20,0.12)',
            alertBg: 'rgba(255,60,60,0.2)',
            alertBorder: 'rgba(255,60,60,0.4)',
            alertColor: '#ff6666',
            tempGrad: 'linear-gradient(90deg,#ff4444,#ff8800,#ffcc00)',
            gridColor: 'rgba(255,50,50,0.08)',
        },
        blue: {
            name: 'Blue',
            bg: 'rgba(10,15,30,0.92)',
            border: 'rgba(40,120,220,0.4)',
            headerGrad1: 'rgba(40,120,220,0.25)',
            headerGrad2: 'rgba(20,80,180,0.15)',
            text: '#c0d0e0',
            textBright: '#ffffff',
            accent: '#4488ff',
            accent2: '#2266dd',
            accentGpu: '#66aaff',
            bgSecondary: 'rgba(50,100,255,0.06)',
            barBg: 'rgba(50,100,255,0.12)',
            btnBg: 'rgba(50,100,255,0.12)',
            btnHover: 'rgba(50,100,255,0.22)',
            labelColor: '#8899cc',
            valueColor: '#4488ff',
            toggleOn: '#4488ff',
            toggleOff: 'rgba(50,100,255,0.2)',
            processBg: 'rgba(30,80,200,0.08)',
            sparkBg: 'rgba(30,80,200,0.12)',
            alertBg: 'rgba(255,80,80,0.15)',
            alertBorder: 'rgba(255,80,80,0.3)',
            alertColor: '#ff6b6b',
            tempGrad: 'linear-gradient(90deg,#4488ff,#8844ff,#ff4488)',
            gridColor: 'rgba(50,100,255,0.08)',
        },
        green: {
            name: 'Green',
            bg: 'rgba(10,24,10,0.92)',
            border: 'rgba(40,200,80,0.4)',
            headerGrad1: 'rgba(40,200,80,0.25)',
            headerGrad2: 'rgba(20,160,40,0.15)',
            text: '#c0e0c0',
            textBright: '#ffffff',
            accent: '#44dd66',
            accent2: '#22bb44',
            accentGpu: '#66ff88',
            bgSecondary: 'rgba(50,255,80,0.06)',
            barBg: 'rgba(50,255,80,0.12)',
            btnBg: 'rgba(50,255,80,0.12)',
            btnHover: 'rgba(50,255,80,0.22)',
            labelColor: '#88cc88',
            valueColor: '#44dd66',
            toggleOn: '#44dd66',
            toggleOff: 'rgba(50,255,80,0.2)',
            processBg: 'rgba(20,200,40,0.08)',
            sparkBg: 'rgba(20,200,40,0.12)',
            alertBg: 'rgba(255,160,40,0.15)',
            alertBorder: 'rgba(255,160,40,0.3)',
            alertColor: '#ffaa33',
            tempGrad: 'linear-gradient(90deg,#44dd66,#dddd44,#ff6644)',
            gridColor: 'rgba(50,255,80,0.08)',
        },
        purple: {
            name: 'Purple',
            bg: 'rgba(22,12,32,0.92)',
            border: 'rgba(160,60,220,0.4)',
            headerGrad1: 'rgba(160,60,220,0.25)',
            headerGrad2: 'rgba(120,40,180,0.15)',
            text: '#d0c0e0',
            textBright: '#ffffff',
            accent: '#bb66ff',
            accent2: '#9944dd',
            accentGpu: '#cc88ff',
            bgSecondary: 'rgba(160,60,255,0.06)',
            barBg: 'rgba(160,60,255,0.12)',
            btnBg: 'rgba(160,60,255,0.12)',
            btnHover: 'rgba(160,60,255,0.22)',
            labelColor: '#9988cc',
            valueColor: '#bb66ff',
            toggleOn: '#bb66ff',
            toggleOff: 'rgba(160,60,255,0.2)',
            processBg: 'rgba(120,40,200,0.08)',
            sparkBg: 'rgba(120,40,200,0.12)',
            alertBg: 'rgba(255,80,80,0.15)',
            alertBorder: 'rgba(255,80,80,0.3)',
            alertColor: '#ff6b6b',
            tempGrad: 'linear-gradient(90deg,#bb66ff,#ff66bb,#ff4488)',
            gridColor: 'rgba(160,60,255,0.08)',
        },
        cyan: {
            name: 'Cyan',
            bg: 'rgba(10,24,30,0.92)',
            border: 'rgba(40,200,220,0.4)',
            headerGrad1: 'rgba(40,200,220,0.25)',
            headerGrad2: 'rgba(20,160,180,0.15)',
            text: '#c0e0e0',
            textBright: '#ffffff',
            accent: '#44dddd',
            accent2: '#22bbbb',
            accentGpu: '#66ffff',
            bgSecondary: 'rgba(50,255,255,0.06)',
            barBg: 'rgba(50,255,255,0.12)',
            btnBg: 'rgba(50,255,255,0.12)',
            btnHover: 'rgba(50,255,255,0.22)',
            labelColor: '#88cccc',
            valueColor: '#44dddd',
            toggleOn: '#44dddd',
            toggleOff: 'rgba(50,255,255,0.2)',
            processBg: 'rgba(20,200,200,0.08)',
            sparkBg: 'rgba(20,200,200,0.12)',
            alertBg: 'rgba(255,80,80,0.15)',
            alertBorder: 'rgba(255,80,80,0.3)',
            alertColor: '#ff6b6b',
            tempGrad: 'linear-gradient(90deg,#44dddd,#44dd88,#44dd44)',
            gridColor: 'rgba(50,255,255,0.08)',
        },
        orange: {
            name: 'Orange',
            bg: 'rgba(28,18,10,0.92)',
            border: 'rgba(220,120,40,0.4)',
            headerGrad1: 'rgba(220,120,40,0.25)',
            headerGrad2: 'rgba(180,80,20,0.15)',
            text: '#e0d0c0',
            textBright: '#ffffff',
            accent: '#ff8833',
            accent2: '#dd6611',
            accentGpu: '#ffaa66',
            bgSecondary: 'rgba(255,120,40,0.06)',
            barBg: 'rgba(255,120,40,0.12)',
            btnBg: 'rgba(255,120,40,0.12)',
            btnHover: 'rgba(255,120,40,0.22)',
            labelColor: '#ccaa88',
            valueColor: '#ff8833',
            toggleOn: '#ff8833',
            toggleOff: 'rgba(255,120,40,0.2)',
            processBg: 'rgba(200,100,20,0.08)',
            sparkBg: 'rgba(200,100,20,0.12)',
            alertBg: 'rgba(255,60,60,0.15)',
            alertBorder: 'rgba(255,60,60,0.3)',
            alertColor: '#ff4444',
            tempGrad: 'linear-gradient(90deg,#ff8833,#ffcc33,#ff4444)',
            gridColor: 'rgba(255,120,40,0.08)',
        },
        pink: {
            name: 'Pink',
            bg: 'rgba(28,10,20,0.92)',
            border: 'rgba(220,40,140,0.4)',
            headerGrad1: 'rgba(220,40,140,0.25)',
            headerGrad2: 'rgba(180,20,100,0.15)',
            text: '#e0c0d0',
            textBright: '#ffffff',
            accent: '#ff66aa',
            accent2: '#dd4488',
            accentGpu: '#ff88bb',
            bgSecondary: 'rgba(255,60,160,0.06)',
            barBg: 'rgba(255,60,160,0.12)',
            btnBg: 'rgba(255,60,160,0.12)',
            btnHover: 'rgba(255,60,160,0.22)',
            labelColor: '#cc88aa',
            valueColor: '#ff66aa',
            toggleOn: '#ff66aa',
            toggleOff: 'rgba(255,60,160,0.2)',
            processBg: 'rgba(200,20,120,0.08)',
            sparkBg: 'rgba(200,20,120,0.12)',
            alertBg: 'rgba(255,80,80,0.15)',
            alertBorder: 'rgba(255,80,80,0.3)',
            alertColor: '#ff6b6b',
            tempGrad: 'linear-gradient(90deg,#ff66aa,#ff4488,#ff2244)',
            gridColor: 'rgba(255,60,160,0.08)',
        },
    };

    // Custom theme for user-defined colors
    var customTheme = null;

    // ===== UTILITY =====
    function $(id) { return document.getElementById(id); }

    // ===== INIT =====
    function init() {
        console.log('[AMD Monitor] Initializing v4.0 with Themes...');
        loadConfig();
        createWidget();
        applyConfigToWidget();
        applyTheme(currentTheme);
        setupEventListeners();
        connectWebSocket();
    }

    // ===== THEME ENGINE =====
    function applyTheme(themeKey) {
        var theme;
        if (themeKey === 'custom' && customTheme) {
            theme = customTheme;
        } else if (THEMES[themeKey]) {
            theme = THEMES[themeKey];
        } else {
            theme = THEMES.dark;
        }
        currentTheme = themeKey;

        if (!widget) return;

        // Apply theme as CSS custom properties
        widget.style.setProperty('--amd-bg', theme.bg);
        widget.style.setProperty('--amd-border', theme.border);
        widget.style.setProperty('--amd-header-grad1', theme.headerGrad1);
        widget.style.setProperty('--amd-header-grad2', theme.headerGrad2);
        widget.style.setProperty('--amd-text', theme.text);
        widget.style.setProperty('--amd-text-bright', theme.textBright);
        widget.style.setProperty('--amd-accent', theme.accent);
        widget.style.setProperty('--amd-accent2', theme.accent2);
        widget.style.setProperty('--amd-accent-gpu', theme.accentGpu);
        widget.style.setProperty('--amd-bg-secondary', theme.bgSecondary);
        widget.style.setProperty('--amd-bar-bg', theme.barBg);
        widget.style.setProperty('--amd-btn-bg', theme.btnBg);
        widget.style.setProperty('--amd-btn-hover', theme.btnHover);
        widget.style.setProperty('--amd-label-color', theme.labelColor);
        widget.style.setProperty('--amd-value-color', theme.valueColor);
        widget.style.setProperty('--amd-toggle-on', theme.toggleOn);
        widget.style.setProperty('--amd-toggle-off', theme.toggleOff);
        widget.style.setProperty('--amd-process-bg', theme.processBg);
        widget.style.setProperty('--amd-spark-bg', theme.sparkBg);
        widget.style.setProperty('--amd-alert-bg', theme.alertBg);
        widget.style.setProperty('--amd-alert-border', theme.alertBorder);
        widget.style.setProperty('--amd-alert-color', theme.alertColor);
        widget.style.setProperty('--amd-temp-grad', theme.tempGrad);
        widget.style.setProperty('--amd-grid-color', theme.gridColor);

        // Update live display
        var statusEl = $('amd-status');
        if (statusEl && statusEl.className.indexOf('live') >= 0) {
            statusEl.style.color = theme.accent;
        }

        // Update active chip in theme selector
        var chips = document.querySelectorAll('.amd-theme-chip');
        chips.forEach(function(c) {
            c.classList.toggle('active', c.dataset.theme === themeKey);
        });

        // Redraw sparkline with new theme
        if (historyData.length > 0) drawSparkline(historyData);

        saveConfig();
    }

    function getActiveTheme() {
        if (currentTheme === 'custom' && customTheme) return customTheme;
        return THEMES[currentTheme] || THEMES.dark;
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
                    '<div class="amd-sparkline-header">' +
                        '<span class="amd-label-small">GPU Load</span>' +
                        '<span class="amd-live-label" id="amd-live-label">● LIVE</span>' +
                    '</div>' +
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
                    '<div class="amd-theme-section">' +
                        '<div class="amd-settings-row"><span class="amd-label-small">Theme</span></div>' +
                        '<div class="amd-theme-chips" id="amd-theme-chips"></div>' +
                        '<div class="amd-custom-colors" id="amd-custom-colors" style="display:none;">' +
                            '<div class="amd-color-row"><span class="amd-label-xs">Accent</span><input type="color" class="amd-color-picker" id="amd-custom-accent" value="#00e676" /></div>' +
                            '<div class="amd-color-row"><span class="amd-label-xs">Background</span><input type="color" class="amd-color-picker" id="amd-custom-bg" value="#121218" /></div>' +
                            '<div class="amd-color-row"><span class="amd-label-xs">Border</span><input type="color" class="amd-color-picker" id="amd-custom-border" value="#c4302b" /></div>' +
                            '<div class="amd-color-row"><span class="amd-label-xs">GPU Name</span><input type="color" class="amd-color-picker" id="amd-custom-gpu-color" value="#ff6b6b" /></div>' +
                            '<div class="amd-color-row"><span class="amd-label-xs">Text</span><input type="color" class="amd-color-picker" id="amd-custom-text" value="#e0e0e0" /></div>' +
                            '<button class="amd-theme-apply" id="amd-theme-apply">Apply Custom</button>' +
                        '</div>' +
                    '</div>' +
                '</div>' +
                '<div class="amd-footer"><span class="amd-status" id="amd-status">Initializing...</span><span class="amd-method" id="amd-method">--</span></div>' +
            '</div>';

        var style = document.createElement('style');
        style.id = 'bangtrix-amd-monitor-styles';
        style.textContent =
            '#bangtrix-amd-monitor{position:fixed;top:60px;right:20px;width:260px;' +
            'background:var(--amd-bg,rgba(18,18,24,0.92));border:1px solid var(--amd-border,rgba(196,48,43,0.3));border-radius:10px;' +
            'font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;' +
            'color:var(--amd-text,#e0e0e0);z-index:9999;box-shadow:0 8px 32px rgba(0,0,0,0.4);' +
            'backdrop-filter:blur(8px);user-select:none;}' +
            '#bangtrix-amd-monitor.hidden{display:none}' +
            '#bangtrix-amd-monitor.minimized .amd-body{display:none}' +
            '.amd-header{display:flex;justify-content:space-between;align-items:center;padding:10px 14px;' +
            'background:linear-gradient(135deg,var(--amd-header-grad1,rgba(196,48,43,0.2))0%,var(--amd-header-grad2,rgba(139,32,29,0.1))100%);' +
            'border-radius:10px 10px 0 0;cursor:move;border-bottom:1px solid rgba(255,255,255,0.05)}' +
            '.amd-title{display:flex;align-items:center;gap:8px;font-weight:600;font-size:12px;color:var(--amd-text-bright,#fff)}' +
            '.amd-icon{font-size:14px;animation:pulse 1s infinite}' +
            '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
            '.amd-controls{display:flex;gap:4px}' +
            '.amd-btn{background:var(--amd-btn-bg,rgba(255,255,255,0.1));border:none;color:var(--amd-text,#ccc);width:22px;height:22px;border-radius:4px;cursor:pointer;font-size:12px}' +
            '.amd-btn:hover{background:var(--amd-btn-hover,rgba(255,255,255,0.2));color:var(--amd-text-bright,#fff)}' +
            '.amd-btn-close:hover{background:rgba(255,80,80,0.3)}' +
            '.amd-body{padding:12px 14px}' +
            '.amd-gpu-name{text-align:center;font-size:11px;font-weight:600;color:var(--amd-accent-gpu,#ff6b6b);margin-bottom:8px;' +
            'padding:4px 8px;border-radius:4px;background:var(--amd-bg-secondary,rgba(255,255,255,0.04));overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
            '.amd-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px}' +
            '.amd-stat{display:flex;flex-direction:column;gap:2px}' +
            '.amd-label{color:var(--amd-label-color,#888);font-size:10px;text-transform:uppercase}' +
            '.amd-label-small{color:var(--amd-label-color,#888);font-size:10px}' +
            '.amd-value{font-weight:600;font-size:13px;color:var(--amd-value-color,#00e676);transition:color 0.3s ease}' +
            '.amd-value.na{color:#666}' +
            '.amd-value.warning{color:#ffaa00}' +
            '.amd-value.critical{color:#ff4444}' +
            '.amd-bar{height:4px;background:var(--amd-bar-bg,rgba(255,255,255,0.1));border-radius:2px;overflow:hidden;margin-top:2px}' +
            '.amd-fill{height:100%;border-radius:2px;width:0%;background:var(--amd-accent,#00e676);' +
            'transition:width 0.4s cubic-bezier(0.4,0,0.2,1)}' +
            '.amd-fill.amd-temp{background:var(--amd-temp-grad,linear-gradient(90deg,#00e676,#ffaa00,#ff4444))}' +
            '.amd-sparkline-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}' +
            '.amd-live-label{font-size:9px;color:var(--amd-accent,#00e676);animation:livePulse 1.5s infinite}' +
            '.amd-sparkline-container{margin-top:8px}' +
            '.amd-sparkline{width:100%;height:40px;border-radius:4px;background:var(--amd-spark-bg,rgba(0,0,0,0.3))}' +
            '.amd-process{margin-top:8px;padding:6px 8px;background:var(--amd-process-bg,rgba(0,0,0,0.2));border-radius:6px;border:1px solid var(--amd-border,rgba(255,255,255,0.06))}' +
            '.amd-process-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:4px}' +
            '.amd-process-status{font-size:10px}' +
            '.amd-process-status.generating{color:var(--amd-accent,#00e676)}' +
            '.amd-process-status.idle{color:var(--amd-label-color,#888)}' +
            '.amd-process-body{display:grid;grid-template-columns:1fr 1fr;gap:2px 8px}' +
            '.amd-stat-row{display:flex;justify-content:space-between}' +
            '.amd-label-xs{color:var(--amd-label-color,#666);font-size:9px}' +
            '.amd-value-sm{color:var(--amd-text,#ccc);font-size:10px}' +
            '.amd-alert{display:flex;align-items:center;gap:6px;padding:6px 10px;margin-top:8px;' +
            'background:var(--amd-alert-bg,rgba(255,80,80,0.15));border:1px solid var(--amd-alert-border,rgba(255,80,80,0.3));border-radius:6px;font-size:11px;color:var(--amd-alert-color,#ff6b6b)}' +
            '.amd-settings{margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05)}' +
            '.amd-settings-row{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}' +
            '.amd-select,.amd-input{background:var(--amd-btn-bg,rgba(255,255,255,0.1));border:1px solid rgba(255,255,255,0.15);color:var(--amd-text,#e0e0e0);padding:2px 6px;border-radius:4px;font-size:10px;width:70px}' +
            '.amd-input{width:50px}' +
            '.amd-toggle{position:relative;width:32px;height:16px;cursor:pointer}' +
            '.amd-toggle input{display:none}' +
            '.amd-toggle-slider{position:absolute;top:0;left:0;right:0;bottom:0;background:var(--amd-toggle-off,rgba(255,255,255,0.15));border-radius:8px;transition:0.2s}' +
            '.amd-toggle-slider:before{content:"";position:absolute;width:12px;height:12px;left:2px;bottom:2px;background:var(--amd-text,#ccc);border-radius:50%;transition:0.2s}' +
            '.amd-toggle input:checked+.amd-toggle-slider{background:var(--amd-toggle-on,rgba(196,48,43,0.6))}' +
            '.amd-toggle input:checked+.amd-toggle-slider:before{transform:translateX(16px);background:var(--amd-text-bright,#fff)}' +
            '.amd-theme-section{margin-top:8px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05)}' +
            '.amd-theme-chips{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}' +
            '.amd-theme-chip{padding:3px 8px;border-radius:10px;font-size:9px;cursor:pointer;transition:all 0.15s;border:1px solid transparent}' +
            '.amd-theme-chip:hover{opacity:0.8}' +
            '.amd-theme-chip.active{font-weight:700}' +
            '.amd-custom-colors{display:flex;flex-direction:column;gap:4px}' +
            '.amd-color-row{display:flex;justify-content:space-between;align-items:center}' +
            '.amd-color-picker{width:50px;height:20px;border:none;border-radius:3px;cursor:pointer;padding:0;background:transparent}' +
            '.amd-color-picker::-webkit-color-swatch-wrapper{padding:0}' +
            '.amd-color-picker::-webkit-color-swatch{border:1px solid rgba(255,255,255,0.2);border-radius:3px}' +
            '.amd-theme-apply{width:100%;margin-top:4px;padding:4px;background:var(--amd-accent,#00e676);color:#000;border:none;border-radius:4px;font-size:10px;font-weight:600;cursor:pointer}' +
            '.amd-theme-apply:hover{opacity:0.9}' +
            '.amd-footer{display:flex;justify-content:space-between;margin-top:10px;padding-top:8px;border-top:1px solid rgba(255,255,255,0.05);font-size:10px;color:var(--amd-label-color,#666)}' +
            '.amd-status{transition:color 0.2s}' +
            '.amd-status.connected{color:var(--amd-accent,#00e676)}' +
            '.amd-status.disconnected{color:#ff4444}' +
            '.amd-status.warning{color:#ffaa00}' +
            '.amd-status.live{color:var(--amd-accent,#00e676);animation:livePulse 1.5s infinite}' +
            '@keyframes livePulse{0%,100%{color:var(--amd-accent,#00e676)}50%{color:var(--amd-accent,#00e67688)}}' +
            '.amd-method{color:var(--amd-label-color,#888);font-family:monospace;font-size:9px}';
        document.head.appendChild(style);

        document.body.appendChild(widget);
        setupDrag();
        buildThemeChips();
    }

    function buildThemeChips() {
        var container = $('amd-theme-chips');
        if (!container) return;

        var themeKeys = Object.keys(THEMES);
        themeKeys.push('custom');

        themeKeys.forEach(function(key) {
            var chip = document.createElement('span');
            chip.className = 'amd-theme-chip' + (key === currentTheme ? ' active' : '');
            chip.dataset.theme = key;

            if (key === 'custom') {
                chip.textContent = '🎨 Custom';
                chip.style.background = 'linear-gradient(135deg,#ff6b6b,#ffd93d,#6bcb77,#4d96ff)';
                chip.style.color = '#fff';
            } else {
                chip.textContent = THEMES[key].name;
                chip.style.background = THEMES[key].bgSecondary;
                chip.style.color = THEMES[key].text;
                chip.style.borderColor = THEMES[key].border;
            }

            chip.addEventListener('click', function() {
                if (key === 'custom') {
                    var customColors = $('amd-custom-colors');
                    if (customColors) customColors.style.display = 'block';
                    applyTheme('custom');
                } else {
                    var customColors = $('amd-custom-colors');
                    if (customColors) customColors.style.display = 'none';
                    applyTheme(key);
                }
                // Update active state
                container.querySelectorAll('.amd-theme-chip').forEach(function(c) {
                    c.classList.remove('active');
                });
                chip.classList.add('active');
            });

            container.appendChild(chip);
        });
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

        // Custom theme apply button
        var applyBtn = $('amd-theme-apply');
        if (applyBtn) applyBtn.addEventListener('click', function() {
            customTheme = {
                name: 'Custom',
                bg: 'rgba(' + hexToRgb($('amd-custom-bg').value) + ',0.92)',
                border: 'rgba(' + hexToRgb($('amd-custom-border').value) + ',0.3)',
                headerGrad1: 'rgba(' + hexToRgb($('amd-custom-border').value) + ',0.2)',
                headerGrad2: 'rgba(' + hexToRgb($('amd-custom-border').value) + ',0.1)',
                text: $('amd-custom-text').value,
                textBright: '#ffffff',
                accent: $('amd-custom-accent').value,
                accent2: adjustBrightness($('amd-custom-accent').value, -20),
                accentGpu: $('amd-custom-gpu-color').value,
                bgSecondary: 'rgba(' + hexToRgb($('amd-custom-bg').value) + ',0.04)',
                barBg: 'rgba(' + hexToRgb($('amd-custom-bg').value) + ',0.1)',
                btnBg: 'rgba(255,255,255,0.1)',
                btnHover: 'rgba(255,255,255,0.2)',
                labelColor: '#888',
                valueColor: $('amd-custom-accent').value,
                toggleOn: 'rgba(' + hexToRgb($('amd-custom-accent').value) + ',0.6)',
                toggleOff: 'rgba(255,255,255,0.15)',
                processBg: 'rgba(0,0,0,0.2)',
                sparkBg: 'rgba(0,0,0,0.3)',
                alertBg: 'rgba(255,80,80,0.15)',
                alertBorder: 'rgba(255,80,80,0.3)',
                alertColor: '#ff6b6b',
                tempGrad: 'linear-gradient(90deg,' + $('amd-custom-accent').value + ',#ffaa00,#ff4444)',
                gridColor: 'rgba(255,255,255,0.04)',
            };
            applyTheme('custom');
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

    function hexToRgb(hex) {
        var r = parseInt(hex.slice(1,3), 16);
        var g = parseInt(hex.slice(3,5), 16);
        var b = parseInt(hex.slice(5,7), 16);
        return r + ',' + g + ',' + b;
    }

    function adjustBrightness(hex, percent) {
        var r = parseInt(hex.slice(1,3), 16);
        var g = parseInt(hex.slice(3,5), 16);
        var b = parseInt(hex.slice(5,7), 16);
        r = Math.max(0, Math.min(255, r + percent));
        g = Math.max(0, Math.min(255, g + percent));
        b = Math.max(0, Math.min(255, b + percent));
        return '#' + r.toString(16).padStart(2,'0') + g.toString(16).padStart(2,'0') + b.toString(16).padStart(2,'0');
    }

    // ===== CONFIG =====
    function loadConfig() {
        try {
            var saved = localStorage.getItem(CONFIG.storageKey);
            if (saved) {
                savedConfig = JSON.parse(saved);
                if (savedConfig.theme) currentTheme = savedConfig.theme;
                if (savedConfig.customTheme) customTheme = savedConfig.customTheme;
            }
        } catch(e) {}
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
                showSparkline: $('amd-settings-sparkline')?.checked !== false,
                theme: currentTheme,
                customTheme: customTheme,
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

        // Sparkline — REAL-TIME with animated rendering
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

    // ===== SPARKLINE — REAL-TIME =====
    function drawSparkline(values) {
        var canvas = $('amd-sparkline');
        if (!canvas) return;
        var ctx = canvas.getContext('2d');
        var w = canvas.width, h = canvas.height, padding = 3;
        ctx.clearRect(0, 0, w, h);

        var theme = getActiveTheme();

        // Draw grid lines
        ctx.strokeStyle = theme.gridColor || 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        for (var gridY = 0; gridY < 4; gridY++) {
            var gy = padding + (gridY / 3) * (h - padding * 2);
            ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(w, gy); ctx.stroke();
        }

        if (values.length < 2 || values.every(function(v) { return v === 0; })) {
            ctx.fillStyle = theme.labelColor || '#555';
            ctx.font = '10px monospace'; ctx.textAlign = 'center';
            ctx.fillText('awaiting data...', w / 2, h / 2 + 3);
            return;
        }

        var dataMax = Math.max.apply(null, values);
        var max = dataMax > 80 ? 100 : (dataMax < 1 ? 100 : dataMax * 1.2);
        var plotW = w - padding * 2;
        var plotH = h - padding * 2;

        // Gradient fill under line
        ctx.beginPath();
        ctx.moveTo(padding, h - padding);
        for (var i = 0; i < values.length; i++) {
            var x = padding + (i / Math.max(values.length - 1, 1)) * plotW;
            var y = h - padding - (values[i] / max) * plotH;
            ctx.lineTo(x, y);
        }
        ctx.lineTo(padding + plotW, h - padding);
        ctx.closePath();
        var accent = theme.accent || '#00e676';
        var grad = ctx.createLinearGradient(0, 0, 0, h);
        grad.addColorStop(0, accent + '33');
        grad.addColorStop(1, accent + '05');
        ctx.fillStyle = grad;
        ctx.fill();

        // Draw line
        ctx.beginPath();
        ctx.strokeStyle = accent;
        ctx.lineWidth = 1.5;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        for (var i = 0; i < values.length; i++) {
            var x = padding + (i / Math.max(values.length - 1, 1)) * plotW;
            var y = h - padding - (values[i] / max) * plotH;
            if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Latest point glow
        var lastIdx = values.length - 1;
        var lx = padding + (lastIdx / Math.max(values.length - 1, 1)) * plotW;
        var ly = h - padding - (values[lastIdx] / max) * plotH;
        ctx.beginPath(); ctx.arc(lx, ly, 3, 0, Math.PI * 2);
        ctx.fillStyle = accent;
        ctx.fill();
        ctx.beginPath(); ctx.arc(lx, ly, 5, 0, Math.PI * 2);
        ctx.fillStyle = accent + '44';
        ctx.fill();

        // Value label
        ctx.fillStyle = accent;
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText(values[lastIdx].toFixed(0) + '%', w - padding, padding);
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
        el.textContent = message;
        el.className = 'amd-status ' + className;
        var theme = getActiveTheme();
        if (className === 'live' || className === 'connected') {
            el.style.color = theme.accent;
        } else if (className === 'warning') {
            el.style.color = '#ffaa00';
        } else {
            el.style.color = '#ff4444';
        }
        var icon = widget.querySelector('.amd-icon');
        if (icon) icon.textContent = className === 'live' || className === 'connected' ? '🟢' : className === 'warning' ? '🟡' : '🔴';
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
        var theme = getActiveTheme();
        var toast = document.createElement('div');
        toast.className = 'bangtrix-toast';
        toast.textContent = message;
        toast.style.cssText = 'position:fixed;bottom:20px;right:20px;background:' + theme.bg + ';color:' + theme.text + ';padding:10px 16px;border-radius:6px;font-size:12px;z-index:10001;border:1px solid ' + theme.border + ';animation:slideIn 0.2s ease;max-width:300px;';
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