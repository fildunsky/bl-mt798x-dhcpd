/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Copyright (C) 2026 Yuzhii0718
 *
 * All rights reserved.
 *
 * This file is part of the project bl-mt798x-dhcpd
 * You may not use, copy, modify or distribute this file except in compliance with the license agreement.
 */
(function () {
	function normalizeHexColor(input) {
		if (!input) return null;
		let s = String(input).trim();
		if (s === "") return null;
		if (s[0] === "#") s = s.slice(1);
		if (!/^[0-9a-fA-F]{3}$/.test(s) && !/^[0-9a-fA-F]{6}$/.test(s)) return null;
		const hex = s.length === 3 ? `#${s[0]}${s[0]}${s[1]}${s[1]}${s[2]}${s[2]}` : `#${s}`;
		return hex.toLowerCase();
	}

	function normalizeThemeMode(input) {
		if (!input) return null;
		const s = String(input).trim().toLowerCase();
		return (s === "auto" || s === "light" || s === "dark") ? s : null;
	}

	function hexToRgb(hex) {
		const n = normalizeHexColor(hex);
		if (!n) return null;
		return {
			r: parseInt(n.slice(1, 3), 16),
			g: parseInt(n.slice(3, 5), 16),
			b: parseInt(n.slice(5, 7), 16)
		};
	}

	function blendColor(hex, targetHex, t) {
		const a = hexToRgb(hex);
		const b = hexToRgb(targetHex);
		if (!a || !b) return hex;
		const r = Math.round(a.r + (b.r - a.r) * t);
		const g = Math.round(a.g + (b.g - a.g) * t);
		const bl = Math.round(a.b + (b.b - a.b) * t);
		return `#${r.toString(16).padStart(2, "0")}${g.toString(16).padStart(2, "0")}${bl.toString(16).padStart(2, "0")}`;
	}

	function setupThemeTransition(root) {
		let timer = null;
		let ready = false;
		let lastThemeAttr = root.getAttribute("data-theme");
		const durationMs = 700;

		const pulse = () => {
			if (!ready) return;
			if (timer) {
				clearTimeout(timer);
				timer = null;
			}
			root.classList.add("theme-transition");
			timer = setTimeout(() => {
				root.classList.remove("theme-transition");
				timer = null;
			}, durationMs);
		};

		root.__failsafeThemePulse = pulse;

		try {
			const obs = new MutationObserver(() => {
				const now = root.getAttribute("data-theme");
				if (now !== lastThemeAttr) {
					lastThemeAttr = now;
					if (root.__failsafeThemeSilent) return;
					pulse();
				}
			});
			obs.observe(root, { attributes: true, attributeFilter: ["data-theme"] });
		} catch (e) { }

		try {
			const mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
			if (mq && mq.addEventListener) {
				mq.addEventListener("change", () => {
					const cur = root.getAttribute("data-theme");
					if (!cur || cur === "auto") pulse();
				});
			} else if (mq && mq.addListener) {
				mq.addListener(() => {
					const cur2 = root.getAttribute("data-theme");
					if (!cur2 || cur2 === "auto") pulse();
				});
			}
		} catch (e2) { }

		setTimeout(() => { ready = true; }, 0);
	}

	function getPreferredScheme() {
		try {
			const mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
			return mq && mq.matches ? "dark" : "light";
		} catch (e) {
			return "light";
		}
	}

	function applyThemeMode(root, mode, opts) {
		const norm = normalizeThemeMode(mode) || "auto";
		const silent = opts && opts.silent;
		if (!root) return;
		const applyAttr = (value, isAuto) => {
			if (silent) root.__failsafeThemeSilent = true;
			if (isAuto) {
				root.setAttribute("data-theme-auto", "1");
				root.setAttribute("data-theme", value);
			} else {
				root.removeAttribute("data-theme-auto");
				root.setAttribute("data-theme", value);
			}
			if (silent) root.__failsafeThemeSilent = false;
		};

		const scheduleApply = (value, isAuto, shouldPulse) => {
			if (shouldPulse && root.__failsafeThemePulse) root.__failsafeThemePulse();
			if (silent) {
				applyAttr(value, isAuto);
				return;
			}
			if (window.requestAnimationFrame) {
				requestAnimationFrame(() => {
					requestAnimationFrame(() => {
						applyAttr(value, isAuto);
					});
				});
			} else {
				setTimeout(() => applyAttr(value, isAuto), 0);
			}
		};
		if (!applyThemeMode._mq) {
			applyThemeMode._mq = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)");
		}
		if (!applyThemeMode._onChange) {
			applyThemeMode._onChange = () => {
				if (applyThemeMode._mode !== "auto") return;
				const next = getPreferredScheme();
				scheduleApply(next, true, true);
			};
		}

		if (applyThemeMode._mq) {
			try {
				if (applyThemeMode._mq.addEventListener) {
					applyThemeMode._mq.removeEventListener("change", applyThemeMode._onChange);
					applyThemeMode._mq.addEventListener("change", applyThemeMode._onChange);
				} else if (applyThemeMode._mq.removeListener) {
					applyThemeMode._mq.removeListener(applyThemeMode._onChange);
					applyThemeMode._mq.addListener(applyThemeMode._onChange);
				}
			} catch (e2) { }
		}

		applyThemeMode._mode = norm;
		if (norm === "auto") {
			const cur = getPreferredScheme();
			scheduleApply(cur, true, !silent);
		} else {
			scheduleApply(norm, false, !silent);
		}
	}

	try {
		const cached = localStorage.getItem("failsafe_theme_color_cache");
		const cachedTheme = localStorage.getItem("theme");
		const norm = normalizeHexColor(cached);
		const themeMode = normalizeThemeMode(cachedTheme);
		let rgb;
		const root = document.documentElement;
		let lighter;
		let meta;
		setupThemeTransition(root);
		applyThemeMode(root, themeMode || "auto", { silent: true });
		window.__failsafeThemeApplyMode = (mode, opts) => {
			applyThemeMode(root, mode, opts);
		};
		if (!norm) return;
		rgb = hexToRgb(norm);
		if (!rgb) return;
		root.style.setProperty("--primary", norm);
		root.style.setProperty("--primary-rgb", `${rgb.r}, ${rgb.g}, ${rgb.b}`);
		lighter = blendColor(norm, "#ffffff", 0.28);
		root.style.setProperty("--primary-2", lighter);
		meta = document.querySelector("meta[name='theme-color']");
		if (!meta) {
			meta = document.createElement("meta");
			meta.setAttribute("name", "theme-color");
			document.head && document.head.appendChild(meta);
		}
		meta.setAttribute("content", norm);
	} catch (e) {
		/* ignore storage errors */
	}
})();
