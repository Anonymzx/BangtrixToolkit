/**
 * BangtrixToolkit — Universal Hardware Monitor Overlay
 * ComfyUI Extension
 * 
 * Strategy: REST API polling via GET /bangtrix/hw/stats.
 * Fallback: WebSocket /ws/hw_monitor.
 * Toggle: Ctrl+Shift+M
 */

(function() {
    "use strict";
    console.log("🖥️ Bangtrix HW Monitor: loading...");

    // ================================================================
    // T H E M E S  (Dark + Light variants for each)
    // ================================================================
    const THEMES = {
        "Default Green": {
            dark: {
                bg: "rgba(12,12,18,0.92)", accent: "#00e676", accentRgb: "0,230,118",
                accentWarm: "#ffaa00", accentCrit: "#ff4444", gpuName: "#66aaff",
                fillBar: "#00e676", tempGrad: "linear-gradient(90deg,#00e676,#ffaa00,#ff4444)",
                sparklineLine: "#00e676", sparklineTop: "#00e67644", sparklineBot: "#00e67608",
                liveColor: "#00e676", vendorColor: "#888", labelColor: "#888",
                statValueColor: "#e0e0e0", headerBg: "rgba(0,230,118,0.08)",
                glowColor: "0,230,118", neonIntensity: 0
            },
            light: {
                bg: "rgba(240,240,248,0.92)", accent: "#008844", accentRgb: "0,136,68",
                accentWarm: "#cc7700", accentCrit: "#cc2222", gpuName: "#2266cc",
                fillBar: "#008844", tempGrad: "linear-gradient(90deg,#008844,#cc7700,#cc2222)",
                sparklineLine: "#008844", sparklineTop: "#00884433", sparklineBot: "#00884408",
                liveColor: "#008844", vendorColor: "#666", labelColor: "#666",
                statValueColor: "#222", headerBg: "rgba(0,136,68,0.08)",
                glowColor: "0,136,68", neonIntensity: 0
            }
        },
        "Neon Blue": {
            dark: {
                bg: "rgba(8,12,28,0.92)", accent: "#00bfff", accentRgb: "0,191,255",
                accentWarm: "#ff7700", accentCrit: "#ff3355", gpuName: "#66ddff",
                fillBar: "#00bfff", tempGrad: "linear-gradient(90deg,#00bfff,#ff7700,#ff3355)",
                sparklineLine: "#00bfff", sparklineTop: "#00bfff44", sparklineBot: "#00bfff08",
                liveColor: "#00bfff", vendorColor: "#7799bb", labelColor: "#7799bb",
                statValueColor: "#e0e0e0", headerBg: "rgba(0,180,255,0.08)",
                glowColor: "0,191,255", neonIntensity: 1
            },
            light: {
                bg: "rgba(235,242,250,0.92)", accent: "#0066aa", accentRgb: "0,102,170",
                accentWarm: "#b85a00", accentCrit: "#bb2244", gpuName: "#3377cc",
                fillBar: "#0066aa", tempGrad: "linear-gradient(90deg,#0066aa,#b85a00,#bb2244)",
                sparklineLine: "#0066aa", sparklineTop: "#0066aa33", sparklineBot: "#0066aa08",
                liveColor: "#0066aa", vendorColor: "#556677", labelColor: "#556677",
                statValueColor: "#222", headerBg: "rgba(0,102,170,0.08)",
                glowColor: "0,102,170", neonIntensity: 0
            }
        },
        "Crimson Red": {
            dark: {
                bg: "rgba(20,8,8,0.92)", accent: "#ff4444", accentRgb: "255,68,68",
                accentWarm: "#ff8844", accentCrit: "#cc0000", gpuName: "#ff6666",
                fillBar: "#ff4444", tempGrad: "linear-gradient(90deg,#ff4444,#ff8844,#cc0000)",
                sparklineLine: "#ff4444", sparklineTop: "#ff444444", sparklineBot: "#ff444408",
                liveColor: "#ff4444", vendorColor: "#aa7777", labelColor: "#aa7777",
                statValueColor: "#e0e0e0", headerBg: "rgba(255,68,68,0.08)",
                glowColor: "255,68,68", neonIntensity: 1
            },
            light: {
                bg: "rgba(252,238,238,0.92)", accent: "#bb2222", accentRgb: "187,34,34",
                accentWarm: "#bb6622", accentCrit: "#990000", gpuName: "#cc4444",
                fillBar: "#bb2222", tempGrad: "linear-gradient(90deg,#bb2222,#bb6622,#990000)",
                sparklineLine: "#bb2222", sparklineTop: "#bb222233", sparklineBot: "#bb222208",
                liveColor: "#bb2222", vendorColor: "#885555", labelColor: "#885555",
                statValueColor: "#222", headerBg: "rgba(187,34,34,0.08)",
                glowColor: "187,34,34", neonIntensity: 0
            }
        },
        "Hacker Green": {
            dark: {
                bg: "rgba(0,0,0,0.92)", accent: "#00ff00", accentRgb: "0,255,0",
                accentWarm: "#88ff00", accentCrit: "#ff0000", gpuName: "#00ff00",
                fillBar: "#00ff00", tempGrad: "linear-gradient(90deg,#00ff00,#88ff00,#ff0000)",
                sparklineLine: "#00ff00", sparklineTop: "#00ff0044", sparklineBot: "#00ff0008",
                liveColor: "#00ff00", vendorColor: "#336633", labelColor: "#336633",
                statValueColor: "#c0c0c0", headerBg: "rgba(0,255,0,0.05)",
                glowColor: "0,255,0", neonIntensity: 1
            },
            light: {
                bg: "rgba(240,248,240,0.92)", accent: "#007700", accentRgb: "0,119,0",
                accentWarm: "#669900", accentCrit: "#cc0000", gpuName: "#005500",
                fillBar: "#007700", tempGrad: "linear-gradient(90deg,#007700,#669900,#cc0000)",
                sparklineLine: "#007700", sparklineTop: "#00770033", sparklineBot: "#00770008",
                liveColor: "#007700", vendorColor: "#446644", labelColor: "#446644",
                statValueColor: "#222", headerBg: "rgba(0,119,0,0.08)",
                glowColor: "0,119,0", neonIntensity: 0
            }
        },
        "Cyberpunk (Yellow/Cyan)": {
            dark: {
                bg: "rgba(10,0,20,0.95)", accent: "#ffdd00", accentRgb: "255,221,0",
                accentWarm: "#ff8800", accentCrit: "#ff0055", gpuName: "#00ffcc",
                fillBar: "#ffdd00", tempGrad: "linear-gradient(90deg,#00ffcc,#ffdd00,#ff0055)",
                sparklineLine: "#ffdd00", sparklineTop: "#ffdd0044", sparklineBot: "#ffdd0008",
                liveColor: "#00ffcc", vendorColor: "#ff88cc", labelColor: "#aa66cc",
                statValueColor: "#f0e0ff", headerBg: "rgba(255,221,0,0.08)",
                glowColor: "255,221,0", neonIntensity: 2
            },
            light: {
                bg: "rgba(250,245,235,0.92)", accent: "#886600", accentRgb: "136,102,0",
                accentWarm: "#aa5500", accentCrit: "#cc0044", gpuName: "#007766",
                fillBar: "#886600", tempGrad: "linear-gradient(90deg,#007766,#886600,#cc0044)",
                sparklineLine: "#886600", sparklineTop: "#88660033", sparklineBot: "#88660008",
                liveColor: "#007766", vendorColor: "#886655", labelColor: "#886655",
                statValueColor: "#222", headerBg: "rgba(136,102,0,0.08)",
                glowColor: "136,102,0", neonIntensity: 0
            }
        },
        "Synthwave (Pink/Purple)": {
            dark: {
                bg: "rgba(16,0,28,0.95)", accent: "#ff44cc", accentRgb: "255,68,204",
                accentWarm: "#ffaa00", accentCrit: "#00ffaa", gpuName: "#aa66ff",
                fillBar: "#ff44cc", tempGrad: "linear-gradient(90deg,#ff44cc,#ffaa00,#00ffaa)",
                sparklineLine: "#ff44cc", sparklineTop: "#ff44cc44", sparklineBot: "#ff44cc08",
                liveColor: "#ff44cc", vendorColor: "#aa88cc", labelColor: "#8866aa",
                statValueColor: "#f0e0ff", headerBg: "rgba(255,68,204,0.08)",
                glowColor: "255,68,204", neonIntensity: 2
            },
            light: {
                bg: "rgba(248,240,248,0.92)", accent: "#993377", accentRgb: "153,51,119",
                accentWarm: "#aa7700", accentCrit: "#007755", gpuName: "#7744bb",
                fillBar: "#993377", tempGrad: "linear-gradient(90deg,#993377,#aa7700,#007755)",
                sparklineLine: "#993377", sparklineTop: "#99337733", sparklineBot: "#99337708",
                liveColor: "#993377", vendorColor: "#775566", labelColor: "#775566",
                statValueColor: "#222", headerBg: "rgba(153,51,119,0.08)",
                glowColor: "153,51,119", neonIntensity: 0
            }
        },
        "Bangtrix Signature": {
            dark: {
                bg: "rgba(6,6,18,0.95)", accent: "#ff6600", accentRgb: "255,102,0",
                accentWarm: "#ffcc00", accentCrit: "#00ccff", gpuName: "#ff8844",
                fillBar: "#ff6600", tempGrad: "linear-gradient(90deg,#ff6600,#ffcc00,#00ccff)",
                sparklineLine: "#ff6600", sparklineTop: "#ff660044", sparklineBot: "#ff660008",
                liveColor: "#ff6600", vendorColor: "#ff8844", labelColor: "#ffaa44",
                statValueColor: "#fff0e0", headerBg: "rgba(255,102,0,0.08)",
                glowColor: "255,102,0", neonIntensity: 1
            },
            light: {
                bg: "rgba(252,244,236,0.92)", accent: "#cc5500", accentRgb: "204,85,0",
                accentWarm: "#aa8800", accentCrit: "#0088aa", gpuName: "#cc7733",
                fillBar: "#cc5500", tempGrad: "linear-gradient(90deg,#cc5500,#aa8800,#0088aa)",
                sparklineLine: "#cc5500", sparklineTop: "#cc550033", sparklineBot: "#cc550008",
                liveColor: "#cc5500", vendorColor: "#aa6633", labelColor: "#aa6633",
                statValueColor: "#222", headerBg: "rgba(204,85,0,0.08)",
                glowColor: "204,85,0", neonIntensity: 0
            }
        },
        "Custom": {
            dark: {
                bg: "rgba(12,12,18,0.92)", accent: "#00ff00", accentRgb: "0,255,0",
                accentWarm: "#ffaa00", accentCrit: "#ff4444", gpuName: "#66aaff",
                fillBar: "#00ff00", tempGrad: "linear-gradient(90deg,#00ff00,#ffaa00,#ff4444)",
                sparklineLine: "#00ff00", sparklineTop: "#00ff0044", sparklineBot: "#00ff0008",
                liveColor: "#00ff00", vendorColor: "#888", labelColor: "#888",
                statValueColor: "#e0e0e0", headerBg: "rgba(0,255,0,0.08)",
                glowColor: "0,255,0", neonIntensity: 1
            },
            light: {
                bg: "rgba(240,240,248,0.92)", accent: "#008800", accentRgb: "0,136,0",
                accentWarm: "#cc7700", accentCrit: "#cc2222", gpuName: "#2266cc",
                fillBar: "#008800", tempGrad: "linear-gradient(90deg,#008800,#cc7700,#cc2222)",
                sparklineLine: "#008800", sparklineTop: "#00880033", sparklineBot: "#00880008",
                liveColor: "#008800", vendorColor: "#666", labelColor: "#666",
                statValueColor: "#222", headerBg: "rgba(0,136,0,0.08)",
                glowColor: "0,136,0", neonIntensity: 0
            }
        }
    };
    const THEME_NAMES = Object.keys(THEMES);

    // ================================================================
    // S T A T E
    // ================================================================
    let widget = null, dynamicCss = null, isMinimized = false, isVisible = true;
    let isDragging = false, dragStart = { x: 0, y: 0 };
    let pollInterval = null, pollRetries = 0;
    const MAX_RETRIES = 30;

    let curTheme = "Default Green", curBaseMode = "Dark", curRefreshMs = 500;
    let curShowOnStartup = true, curBgOpacity = 0.92, curCompactMode = false, curGhostMode = false;
    let curCustomAccent = "#00ff00", curCustomText = "#ffffff";

    // ================================================================
    // T H E M E   H E L P E R
    // ================================================================
    function _getTheme() {
        const t = THEMES[curTheme] || THEMES["Default Green"];
        const mode = curBaseMode === "Light" ? "light" : "dark";
        let colors = t[mode];
        // If Custom theme, override accent & color with user values
        if (curTheme === "Custom") {
            const mode2 = curBaseMode === "Light" ? "light" : "dark";
            let base = THEMES["Default Green"][mode2];
            // Parse custom accent to RGB
            let acRgb = "0,255,0";
            try {
                const c = document.createElement('span');
                c.style.color = curCustomAccent;
                const m = c.style.color.match(/rgb\((\d+),\s*(\d+),\s*(\d+)/);
                if (m) acRgb = m[1] + "," + m[2] + "," + m[3];
            } catch(e) {}
            const statVal = curBaseMode === "Light" ? curCustomText : "#fff";
            const valColor = curBaseMode === "Light" ? "#222" : statVal;
            colors = {
                bg: base.bg, accent: curCustomAccent, accentRgb: acRgb,
                accentWarm: base.accentWarm, accentCrit: base.accentCrit,
                gpuName: curCustomAccent, fillBar: curCustomAccent,
                tempGrad: "linear-gradient(90deg," + curCustomAccent + "," + base.accentWarm + "," + base.accentCrit + ")",
                sparklineLine: curCustomAccent, sparklineTop: "rgba(" + acRgb + ",0.27)",
                sparklineBot: "rgba(" + acRgb + ",0.03)",
                liveColor: curCustomAccent, vendorColor: base.labelColor,
                labelColor: base.labelColor, statValueColor: valColor,
                headerBg: "rgba(" + acRgb + ",0.08)",
                glowColor: acRgb, neonIntensity: 1
            };
        }
        return colors;
    }

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
            if (s['Bangtrix.HWMonitor.BaseMode']) curBaseMode = s['Bangtrix.HWMonitor.BaseMode'];
            if (s['Bangtrix.HWMonitor.RefreshRate'] != null) curRefreshMs = Number(s['Bangtrix.HWMonitor.RefreshRate']) || 1000;
            if (s['Bangtrix.HWMonitor.ShowOnStartup'] != null) curShowOnStartup = !!s['Bangtrix.HWMonitor.ShowOnStartup'];
            if (s['Bangtrix.HWMonitor.BgOpacity'] != null) curBgOpacity = Number(s['Bangtrix.HWMonitor.BgOpacity']) || 0.92;
            if (s['Bangtrix.HWMonitor.CompactMode'] != null) curCompactMode = !!s['Bangtrix.HWMonitor.CompactMode'];
            if (s['Bangtrix.HWMonitor.GhostMode'] != null) curGhostMode = !!s['Bangtrix.HWMonitor.GhostMode'];
            if (s['Bangtrix.HWMonitor.CustomAccent']) curCustomAccent = s['Bangtrix.HWMonitor.CustomAccent'];
            if (s['Bangtrix.HWMonitor.CustomText']) curCustomText = s['Bangtrix.HWMonitor.CustomText'];
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
        const t = _getTheme();
        const isTextDark = curBaseMode === "Light";
        const textMain = isTextDark ? "#1a1a1a" : "#e0e0e0";
        const headerBorderBottom = "rgba(255,255,255,0.04)";
        const sparklineBg = isTextDark ? "rgba(0,0,0,0.08)" : "rgba(0,0,0,0.2)";
        const barBg = isTextDark ? "rgba(0,0,0,0.1)" : "rgba(255,255,255,0.08)";
        const statusBorderTop = isTextDark ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.04)";
        const gpuNameBg = isTextDark ? "rgba(0,0,0,0.03)" : "rgba(255,255,255,0.03)";

        let glowExtra = "";
        if (t.neonIntensity >= 1 && !curGhostMode) {
            // Subtle glow on accent elements
            glowExtra = 
                '.hw-fill{box-shadow:0 0 8px rgba(' + t.glowColor + ',0.4)}' +
                '.hw-stat-value{text-shadow:0 0 8px rgba(' + t.glowColor + ',0.15)}';
        }
        if (t.neonIntensity >= 2 && !curGhostMode) {
            glowExtra += 
                '.hw-gpu-name{text-shadow:0 0 12px rgba(' + t.glowColor + ',0.25)}' +
                '.hw-title{text-shadow:0 0 10px rgba(' + t.glowColor + ',0.2)}';
        }

        dynamicCss.textContent =
            '#bangtrix-hw-monitor{background:' + t.bg + ';' +
            'border:1px solid rgba(' + t.accentRgb + ',0.25);' +
            'backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);' +
            'transition:all 0.3s ease;}' +
            '#bangtrix-hw-monitor.hidden{display:none}' +
            '#bangtrix-hw-monitor.minimized .hw-body{display:none}' +
            '.hw-header{background:' + t.headerBg + ';border-bottom:1px solid ' + headerBorderBottom + ';transition:all 0.3s ease;}' +
            '.hw-gpu-name{color:' + t.gpuName + ';background:' + gpuNameBg + ';transition:all 0.3s ease;}' +
            '.hw-vendor-line{color:' + t.vendorColor + ';transition:color 0.3s ease;}' +
            '.hw-stat-label{color:' + t.labelColor + ';transition:color 0.3s ease;}' +
            '.hw-stat-value{color:' + t.statValueColor + ';transition:all 0.3s ease;}' +
            '.hw-stat-value.warn{color:' + t.accentWarm + '}' +
            '.hw-stat-value.crit{color:' + t.accentCrit + '}' +
            '.hw-fill{background:' + t.fillBar + ';transition:all 0.3s ease;}' +
            '.hw-fill.hw-temp-fill{background:' + t.tempGrad + '}' +
            '.hw-bar{background:' + barBg + ';transition:background 0.3s ease;}' +
            '#bangtrix-hw-monitor,.hw-header,.hw-body{transition:all 0.3s ease;}' +
            '.hw-status.live{color:' + t.liveColor + ';transition:color 0.3s ease;}' +
            '.hw-status.err{color:' + t.accentCrit + '}' +
            '.hw-sparkline{background:' + sparklineBg + ';transition:background 0.3s ease;}' +
            '.hw-status-bar{border-top:1px solid ' + statusBorderTop + ';transition:border-color 0.3s ease;}' +
            '.hw-btn{transition:all 0.2s ease;}' +
            '.hw-title{color:' + textMain + ';transition:color 0.3s ease;}' +
            '.hw-icon{transition:color 0.3s ease;}' +
            glowExtra;
    }
    function _applyTheme() {
        _updateDynamicCss();
        _applyBgOpacity();
        _applyGhostMode();
    }
    function _applyBgOpacity() {
        if (!widget) return;
        const t = _getTheme();
        if (!curGhostMode) {
            widget.style.background = curBaseMode === "Light"
                ? 'rgba(240,240,248,' + Number(curBgOpacity).toFixed(2) + ')'
                : 'rgba(12,12,18,' + Number(curBgOpacity).toFixed(2) + ')';
            widget.style.borderColor = 'rgba(' + t.accentRgb + ',0.25)';
        }
    }
    function _applyCompactMode() {
        if (!widget) return;
        const sc = widget.querySelector('.hw-sparkline-container');
        if (sc) sc.style.display = curCompactMode ? 'none' : '';
    }
    function _applyGhostMode() {
        if (!widget) return;
        if (curGhostMode) {
            widget.style.background = 'transparent';
            widget.style.border = 'none';
            widget.style.boxShadow = 'none';
            widget.style.backdropFilter = 'none';
            widget.style.webkitBackdropFilter = 'none';
        } else {
            const t = _getTheme();
            widget.style.background = curBaseMode === "Light"
                ? 'rgba(240,240,248,' + Number(curBgOpacity).toFixed(2) + ')'
                : 'rgba(12,12,18,' + Number(curBgOpacity).toFixed(2) + ')';
            widget.style.border = '1px solid rgba(' + t.accentRgb + ',0.25)';
            widget.style.boxShadow = '0 8px 32px rgba(0,0,0,0.35), 0 2px 8px rgba(0,0,0,0.15)';
            widget.style.backdropFilter = 'blur(10px)';
            widget.style.webkitBackdropFilter = 'blur(10px)';
        }
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
                    '<div class="hw-stat"><div class="hw-stat-label" id="hw-vram-label">VRAM</div><div class="hw-stat-value" id="hw-vram">--</div><div class="hw-bar"><div class="hw-fill" id="hw-vram-bar"></div></div></div>' +
                    '<div class="hw-stat"><div class="hw-stat-label">Temp</div><div class="hw-stat-value" id="hw-temp">--</div><div class="hw-bar"><div class="hw-fill hw-temp-fill" id="hw-temp-bar"></div></div></div>' +
                    '<div class="hw-stat"><div class="hw-stat-label">Fan</div><div class="hw-stat-value" id="hw-fan">--</div><div class="hw-bar"><div class="hw-fill" id="hw-fan-bar"></div></div></div>' +
                '</div>' +
                '<div class="hw-sparkline-container">' +
                    '<canvas class="hw-sparkline" id="hw-sparkline" width="228" height="36"></canvas>' +
                '</div>' +
                '<div class="hw-status-bar">' +
                    '<span class="hw-status" id="hw-status">Starting...</span>' +
                    '<span class="hw-method" id="hw-method"></span>' +
                    '<button class="hw-btn hw-btn-clear" id="hw-btn-clear" title="Free VRAM & RAM">🧹 Clear</button>' +
                '</div>' +
            '</div>';
        const baseCss = document.createElement('style');
        baseCss.id = 'bangtrix-hw-base-css';
        baseCss.textContent =
            '#bangtrix-hw-monitor{position:fixed;top:60px;right:20px;width:260px;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;font-size:11px;z-index:99999;box-shadow:0 8px 32px rgba(0,0,0,0.35),0 2px 8px rgba(0,0,0,0.15);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);user-select:none;border-radius:12px;overflow:hidden}' +
            '.hw-header{display:flex;align-items:center;padding:8px 12px;gap:8px;cursor:move;border-radius:12px 12px 0 0}' +
            '.hw-icon{font-size:12px;animation:pulse 1.5s infinite}' +
            '@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
            '.hw-title{flex:1;font-weight:600;font-size:12px}' +
            '.hw-controls{display:flex;gap:4px}' +
            '.hw-btn{background:rgba(255,255,255,0.08);border:none;color:#ccc;width:20px;height:20px;border-radius:4px;cursor:pointer;font-size:11px;line-height:20px;text-align:center}' +
            '.hw-btn:hover{background:rgba(255,255,255,0.2)}' +
            '.hw-btn-close:hover{background:rgba(220,60,60,0.4)!important}' +
            '.hw-body{padding:8px 12px 10px;transition:all 0.3s ease}' +
            '.hw-gpu-name{text-align:center;font-size:11px;font-weight:600;padding:4px 8px;border-radius:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}' +
            '.hw-vendor-line{text-align:center;font-size:9px;margin:2px 0 6px}' +
            '.hw-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px 10px}' +
            '.hw-stat{display:flex;flex-direction:column;gap:1px}' +
            '.hw-stat-label{font-size:9px;text-transform:uppercase}' +
            '.hw-stat-value{font-weight:600;font-size:12px;transition:all 0.2s ease-in-out}' +
            '.hw-bar{height:4px;border-radius:2px;overflow:hidden}' +
            '.hw-fill{height:100%;width:0%;border-radius:2px}' +
            '.hw-sparkline-container{margin-top:6px}' +
            '.hw-sparkline{width:100%;height:36px;border-radius:4px}' +
            '.hw-status-bar{display:flex;align-items:center;margin-top:6px;padding-top:6px;font-size:9px}' +
            '.hw-method{flex:1;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin:0 4px}' +
            '.hw-btn-clear{flex-shrink:0;width:auto;padding:0 6px;font-size:10px;background:rgba(255,255,255,0.06)}' +
            '.hw-btn-clear:hover{background:rgba(0,255,100,0.2)!important;color:#0f0}' +
            '.hw-btn-clear:disabled{background:rgba(255,255,255,0.04)}' +
            '.hw-status.live{animation:livePulse 1.5s infinite}' +
            '.hw-status.loading{color:#ffaa00;animation:loadingPulse 1s infinite}' +
            '@keyframes loadingPulse{0%,100%{opacity:1}50%{opacity:0.4}}' +
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
            _showSettingsPanel();
        };
        const closeBtn = document.getElementById('hw-btn-close');
        if (closeBtn) closeBtn.onclick = function() {
            isVisible = false;
            widget.classList.add('hidden');
            if (pollInterval) { clearInterval(pollInterval); pollInterval = null; }
        };

        // --- Free Memory button ---
        const clearBtn = document.getElementById('hw-btn-clear');
        if (clearBtn) clearBtn.onclick = function() {
            var btn = this;
            btn.disabled = true;
            btn.textContent = '⏳';
            btn.style.opacity = '0.5';
            btn.style.cursor = 'wait';
            fetch('/btx/free_memory', { method: 'POST' })
                .then(function(r) { return r.json(); })
                .then(function(data) {
                    btn.textContent = data.status === 'success' ? '✅' : '❌';
                    btn.style.opacity = '1';
                    btn.style.cursor = '';
                    setTimeout(function() {
                        btn.textContent = '🧹 Clear';
                        btn.disabled = false;
                    }, 2000);
                })
                .catch(function() {
                    btn.textContent = '❌';
                    btn.style.opacity = '1';
                    btn.style.cursor = '';
                    setTimeout(function() {
                        btn.textContent = '🧹 Clear';
                        btn.disabled = false;
                    }, 2000);
                });
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
    // S E T T I N G S   P A N E L
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
                '<div class="hws-row"><label>Base Mode</label><select id="hws-basemode">' +
                    '<option value="Dark">Dark</option><option value="Light">Light</option>' +
                '</select></div>' +
                '<div class="hws-row"><label>Theme</label><select id="hws-theme">' +
                    THEME_NAMES.map(function(t) { return '<option value="' + t + '">' + t + '</option>'; }).join('') +
                '</select></div>' +
                '<div class="hws-row"><label>Refresh Rate</label><select id="hws-refresh">' +
                    '<option value="500">500ms</option><option value="1000">1s</option><option value="2000">2s</option><option value="250">250ms</option>' +
                '</select></div>' +
                '<div class="hws-row"><label>Show on Startup</label><input type="checkbox" id="hws-startup"></div>' +
                '<div class="hws-row"><label>Bg Opacity</label><input type="range" id="hws-opacity" min="0.1" max="1.0" step="0.05"></div>' +
                '<div class="hws-row"><label>Compact Mode</label><input type="checkbox" id="hws-compact"></div>' +
                '<div class="hws-row"><label>Ghost Mode</label><input type="checkbox" id="hws-ghost"></div>' +
                '<div class="hws-row" id="hws-row-accent" style="display:none"><label>Custom Accent</label><input type="color" id="hws-custom-accent" value="#00ff00"></div>' +
                '<div class="hws-row" id="hws-row-text" style="display:none"><label>Custom Text</label><input type="color" id="hws-custom-text" value="#ffffff"></div>' +
            '</div>';
        const hwsCss = document.createElement('style');
        hwsCss.textContent =
            '#bangtrix-hw-settings{position:fixed;top:120px;right:30px;width:260px;background:rgba(18,18,24,0.96);border:1px solid rgba(255,255,255,0.15);border-radius:10px;z-index:100000;color:#ccc;font-size:11px;box-shadow:0 4px 20px rgba(0,0,0,0.5);backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);}' +
            '.hws-header{display:flex;justify-content:space-between;padding:8px 12px;font-weight:600;color:#fff;border-bottom:1px solid rgba(255,255,255,0.06);}' +
            '.hws-close{cursor:pointer;color:#888;}' +
            '.hws-close:hover{color:#f44;}' +
            '.hws-body{padding:10px 12px;}' +
            '.hws-row{display:flex;justify-content:space-between;align-items:center;padding:5px 0;}' +
            '.hws-row label{color:#999;}' +
            '.hws-row select,.hws-row input{background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.1);color:#ddd;border-radius:4px;padding:2px 6px;font-size:11px;}' +
            '.hws-row select{min-width:170px;}' +
            '.hws-row input[type=range]{width:100px;}' +
            '.hws-row input[type=color]{width:40px;height:22px;padding:1px;cursor:pointer}';
        document.head.appendChild(hwsCss);
        document.body.appendChild(settingsPanel);
        _syncSettingsPanel();
        // Show custom color rows only when Custom theme is selected
        function _toggleCustomRows() {
            var show = document.getElementById('hws-theme').value === 'Custom';
            document.getElementById('hws-row-accent').style.display = show ? 'flex' : 'none';
            document.getElementById('hws-row-text').style.display = show ? 'flex' : 'none';
        }
        document.getElementById('hws-close').onclick = function() { settingsPanel.style.display = 'none'; };
        document.getElementById('hws-basemode').onchange = function() {
            curBaseMode = this.value;
            _saveSetting('Bangtrix.HWMonitor.BaseMode', curBaseMode);
            _applyTheme();
            _syncSettingsPanel();
        };
        document.getElementById('hws-theme').onchange = function() {
            curTheme = this.value;
            _saveSetting('Bangtrix.HWMonitor.Theme', curTheme);
            _toggleCustomRows();
            _applyTheme();
            _syncSettingsPanel();
        };
        document.getElementById('hws-refresh').onchange = function() {
            curRefreshMs = Number(this.value) || 1000;
            _saveSetting('Bangtrix.HWMonitor.RefreshRate', curRefreshMs);
            restartPolling();
        };
        document.getElementById('hws-startup').onchange = function() {
            curShowOnStartup = !!this.checked;
            _saveSetting('Bangtrix.HWMonitor.ShowOnStartup', curShowOnStartup);
        };
        document.getElementById('hws-opacity').oninput = function() {
            curBgOpacity = Number(this.value);
            _saveSetting('Bangtrix.HWMonitor.BgOpacity', curBgOpacity);
            _applyBgOpacity();
        };
        document.getElementById('hws-compact').onchange = function() {
            curCompactMode = !!this.checked;
            _saveSetting('Bangtrix.HWMonitor.CompactMode', curCompactMode);
            _applyCompactMode();
        };
        document.getElementById('hws-ghost').onchange = function() {
            curGhostMode = !!this.checked;
            _saveSetting('Bangtrix.HWMonitor.GhostMode', curGhostMode);
            _applyGhostMode();
            _updateDynamicCss();
        };
        document.getElementById('hws-custom-accent').oninput = function() {
            curCustomAccent = this.value;
            _saveSetting('Bangtrix.HWMonitor.CustomAccent', curCustomAccent);
            _applyTheme();
        };
        document.getElementById('hws-custom-text').oninput = function() {
            curCustomText = this.value;
            _saveSetting('Bangtrix.HWMonitor.CustomText', curCustomText);
            _applyTheme();
        };
        _toggleCustomRows();
    }
    function _syncSettingsPanel() {
        if (!settingsPanel) return;
        document.getElementById('hws-basemode').value = curBaseMode;
        document.getElementById('hws-theme').value = curTheme;
        document.getElementById('hws-refresh').value = curRefreshMs;
        document.getElementById('hws-startup').checked = curShowOnStartup;
        document.getElementById('hws-opacity').value = curBgOpacity;
        document.getElementById('hws-compact').checked = curCompactMode;
        document.getElementById('hws-ghost').checked = curGhostMode;
        document.getElementById('hws-custom-accent').value = curCustomAccent;
        document.getElementById('hws-custom-text').value = curCustomText;
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
                try {
                    pollRetries = 0;
                    if (data && data.type === 'hw_stats') {
                        if (data.is_loading) {
                            setStatus("\u25A0 DETECTING", "loading");
                            setMethod("Initializing...");
                            updateDisplay(data);
                        } else if (data.is_available) {
                            setStatus("\u25CF LIVE", "live");
                            setMethod("REST " + (curRefreshMs / 1000) + "s");
                            updateDisplay(data);
                        } else {
                            setStatus(data.gpu_name || "Offline", "err");
                            setMethod(data.driver || "");
                            updateDisplay(data);
                        }
                    }
                } catch (error) {
                    console.error("Bangtrix HW Monitor UI Error:", error);
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
        // CRITICAL: When is_loading is true, DO NOT enter the error branch.
        // Just render placeholder values. The status/method is already
        // set by fetchStats -> setStatus("■ DETECTING", "loading").
        if (d.is_loading) {
            setUtil('hw-gpu-util', '--', 0); setUtil('hw-vram', '--', 0);
            setUtil('hw-temp', '--', 0); setUtil('hw-fan', '--', 0);
            setBar('hw-gpu-bar', 0); setBar('hw-vram-bar', 0); setBar('hw-temp-bar', 0); setBar('hw-fan-bar', 0);
            // Do NOT overwrite status — fetchStats already set it.
            // Do NOT return — let the stat labels update so the overlay shows something.
            // But skip the rest of the real stats rendering.
            if (!curCompactMode && d.history && d.history.length > 0) drawSparkline(d.history);
            return;
        }
        if (!d.is_available) {
            setUtil('hw-gpu-util', d.error || '--', 0); setUtil('hw-vram', d.error || '--', 0);
            setUtil('hw-temp', d.error || '--', 0); setUtil('hw-fan', d.error || '--', 0);
            setBar('hw-gpu-bar', 0); setBar('hw-vram-bar', 0); setBar('hw-temp-bar', 0); setBar('hw-fan-bar', 0);
            // Only overwrite status if it wasn't already set by caller
            // (caller already set status in fetchStats for unavail case)
            setStatus(d.error || 'Unavailable', 'err');
            return;
        }
        // Dynamically update VRAM label for APU vs dedicated GPU
        var vramLabel = $id('hw-vram-label');
        if (vramLabel) {
            vramLabel.textContent = d.is_apu ? 'GPU MEM' : 'VRAM';
        }
        var util = Number(d.gpu_utilization) || 0;
        setUtil('hw-gpu-util', util.toFixed(1) + '%', util);
        setBar('hw-gpu-bar', util);
        var vramUsed = Number(d.vram_used_mb) || 0;
        var vramTotal = Number(d.vram_total_mb) || 1;  // minimum 1 prevents div/0
        var vramPct = Number(d.vram_usage_pct) || 0;
        // Cap pct so bar never exceeds 100%
        if (vramPct > 100) vramPct = 100;
        setUtil('hw-vram', (vramUsed / 1024).toFixed(2) + ' / ' + (vramTotal / 1024).toFixed(1) + ' GB', vramPct);
        setBar('hw-vram-bar', vramPct);
        // OOM Warning: if VRAM >= 90%, color the bar and value red
        var vramBar = $id('hw-vram-bar');
        var vramVal = $id('hw-vram');
        if (vramPct >= 90) {
            if (vramBar) vramBar.style.background = '#ff4444';
            if (vramVal) vramVal.style.color = '#ff4444';
        } else {
            if (vramBar) vramBar.style.background = '';
            if (vramVal) vramVal.style.color = '';
        }
        var temp = Number(d.temperature) || 0;
        if (temp > 0) { setUtil('hw-temp', temp.toFixed(1) + '\u00B0C', temp); setBar('hw-temp-bar', Math.min(temp, 100)); }
        else { setUtil('hw-temp', 'N/A', 0); setBar('hw-temp-bar', 0); }
        var fan = Number(d.fan_speed) || 0;
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
        if (widget) { var icon = widget.querySelector('.hw-icon'); if (icon) icon.textContent = cls === 'live' ? '\uD83D\uDFE2' : cls === 'err' ? '\uD83D\uDD34' : cls === 'loading' ? '\u23F3' : '\uD83D\uDFE1'; }
    }
    function setMethod(text) { var el = $id('hw-method'); if (el) el.textContent = text || ''; }

    // ================================================================
    // S P A R K L I N E
    // ================================================================
    function drawSparkline(values) {
        var canvas = $id('hw-sparkline');
        if (!canvas || values.length < 2) return;
        const t = _getTheme();
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
    // C O M F Y U I   S E T T I N G S
    // ================================================================
    function _registerComfyUISettings() {
        if (!app || !app.ui || !app.ui.settings || !app.ui.settings.addSetting) {
            setTimeout(_registerComfyUISettings, 200);
            return;
        }
        try {
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.BaseMode",
                name: "\uD83C\uDF11 HW Monitor Base Mode",
                type: "combo",
                defaultValue: "Dark",
                options: ["Dark", "Light"],
                onChange: function(v) { curBaseMode = v; _saveSetting("Bangtrix.HWMonitor.BaseMode", v); _applyTheme(); _syncSettingsPanel(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.Theme",
                name: "\uD83C\uDFA8 HW Monitor Theme",
                type: "combo",
                defaultValue: "Default Green",
                options: THEME_NAMES,
                onChange: function(v) { curTheme = v; _saveSetting("Bangtrix.HWMonitor.Theme", v); _applyTheme(); _syncSettingsPanel(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.RefreshRate",
                name: "\u23F1\uFE0F HW Monitor Refresh Rate",
                type: "combo",
                defaultValue: 1000,
                options: [250, 500, 1000, 2000],
                onChange: function(v) { curRefreshMs = Number(v) || 1000; _saveSetting("Bangtrix.HWMonitor.RefreshRate", curRefreshMs); _syncSettingsPanel(); restartPolling(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.ShowOnStartup",
                name: "\uD83D\uDC41\uFE0F Show HW Monitor on Startup",
                type: "boolean",
                defaultValue: true,
                onChange: function(v) { curShowOnStartup = !!v; _saveSetting("Bangtrix.HWMonitor.ShowOnStartup", curShowOnStartup); _syncSettingsPanel(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.BgOpacity",
                name: "\uD83D\uDD32 HW Monitor Background Opacity",
                type: "slider",
                defaultValue: 0.92,
                attrs: { min: 0.1, max: 1.0, step: 0.05 },
                onChange: function(v) { curBgOpacity = Number(v) || 0.92; _saveSetting("Bangtrix.HWMonitor.BgOpacity", curBgOpacity); _syncSettingsPanel(); _applyBgOpacity(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.CompactMode",
                name: "\uD83D\uDCE6 HW Monitor Compact Mode",
                type: "boolean",
                defaultValue: false,
                onChange: function(v) { curCompactMode = !!v; _saveSetting("Bangtrix.HWMonitor.CompactMode", curCompactMode); _syncSettingsPanel(); _applyCompactMode(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.GhostMode",
                name: "\uD83D\uDC7B HW Monitor Ghost Mode (Borderless)",
                type: "boolean",
                defaultValue: false,
                onChange: function(v) { curGhostMode = !!v; _saveSetting("Bangtrix.HWMonitor.GhostMode", curGhostMode); _syncSettingsPanel(); _applyGhostMode(); _updateDynamicCss(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.CustomAccent",
                name: "\uD83C\uDFA8 Custom Accent Color (Custom theme only)",
                type: "text",
                defaultValue: "#00ff00",
                onChange: function(v) { curCustomAccent = v || "#00ff00"; _saveSetting("Bangtrix.HWMonitor.CustomAccent", curCustomAccent); _syncSettingsPanel(); if (curTheme === 'Custom') _applyTheme(); }
            });
            app.ui.settings.addSetting({
                id: "Bangtrix.HWMonitor.CustomText",
                name: "\uD83D\uDD8C\uFE0F Custom Text Color (Custom theme only)",
                type: "text",
                defaultValue: "#ffffff",
                onChange: function(v) { curCustomText = v || "#ffffff"; _saveSetting("Bangtrix.HWMonitor.CustomText", curCustomText); _syncSettingsPanel(); if (curTheme === 'Custom') _applyTheme(); }
            });
            console.log("\uD83D\uDDA5\uFE0F Bangtrix HW Monitor: 9 ComfyUI settings registered \u2705");
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
        _applyTheme(); _applyCompactMode(); _applyGhostMode();
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