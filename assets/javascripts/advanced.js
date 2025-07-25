/* Advanced JavaScript for Facturación México Documentation */

document.addEventListener("DOMContentLoaded", function () {
	console.log("🚀 Facturación México - Advanced Documentation Features Loaded");

	// Initialize all features
	initCopyCodeButtons();
	initProgressBars();
	initSearchEnhancements();
	initTooltips();
	initMetricsBadges();
	initPrintOptimizations();
	initKeyboardShortcuts();
	initThemeToggle();
	initTableEnhancements();

	// Analytics and user behavior
	initAnalytics();
});

/**
 * Add copy buttons to all code blocks
 */
function initCopyCodeButtons() {
	const codeBlocks = document.querySelectorAll(".highlight pre code");

	codeBlocks.forEach(function (codeBlock, index) {
		const pre = codeBlock.parentNode;
		const highlight = pre.parentNode;

		// Create copy button
		const copyButton = document.createElement("button");
		copyButton.className = "copy-code-btn";
		copyButton.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z"/>
            </svg>
            <span>Copiar</span>
        `;
		copyButton.title = "Copiar código al portapapeles";

		// Style the button
		copyButton.style.cssText = `
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 4px;
            opacity: 0;
            transition: all 0.2s ease;
            backdrop-filter: blur(4px);
            z-index: 10;
        `;

		// Add hover effects
		highlight.style.position = "relative";
		highlight.addEventListener("mouseenter", () => {
			copyButton.style.opacity = "1";
		});
		highlight.addEventListener("mouseleave", () => {
			copyButton.style.opacity = "0";
		});

		// Copy functionality
		copyButton.addEventListener("click", async function () {
			const text = codeBlock.textContent;

			try {
				await navigator.clipboard.writeText(text);

				// Success feedback
				copyButton.innerHTML = `
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/>
                    </svg>
                    <span>¡Copiado!</span>
                `;
				copyButton.style.background = "rgba(76, 175, 80, 0.8)";

				setTimeout(() => {
					copyButton.innerHTML = `
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                            <path d="M16 1H4C2.9 1 2 1.9 2 3V17H4V3H16V1ZM19 5H8C6.9 5 6 5.9 6 7V21C6 22.1 6.9 23 8 23H19C20.1 23 21 22.1 21 21V7C21 5.9 20.1 5 19 5ZM19 21H8V7H19V21Z"/>
                        </svg>
                        <span>Copiar</span>
                    `;
					copyButton.style.background = "rgba(255,255,255,0.1)";
				}, 2000);
			} catch (err) {
				console.error("Error copying code:", err);

				// Fallback for older browsers
				const textArea = document.createElement("textarea");
				textArea.value = text;
				document.body.appendChild(textArea);
				textArea.select();
				document.execCommand("copy");
				document.body.removeChild(textArea);

				copyButton.innerHTML = "<span>¡Copiado!</span>";
				setTimeout(() => {
					copyButton.innerHTML = "<span>Copiar</span>";
				}, 2000);
			}
		});

		highlight.appendChild(copyButton);
	});

	console.log(`📋 Copy buttons added to ${codeBlocks.length} code blocks`);
}

/**
 * Initialize animated progress bars
 */
function initProgressBars() {
	const progressBars = document.querySelectorAll(".progress-bar");

	// Create intersection observer for animations
	const observer = new IntersectionObserver(
		(entries) => {
			entries.forEach((entry) => {
				if (entry.isIntersecting) {
					const progressFill = entry.target.querySelector(".progress-fill");
					const targetWidth = progressFill.dataset.width || "0%";

					setTimeout(() => {
						progressFill.style.width = targetWidth;
					}, 100);
				}
			});
		},
		{ threshold: 0.1 }
	);

	progressBars.forEach((bar) => {
		observer.observe(bar);
	});
}

/**
 * Enhanced search functionality
 */
function initSearchEnhancements() {
	const searchInput = document.querySelector('input[data-md-component="search-query"]');

	if (searchInput) {
		// Add search suggestions
		searchInput.addEventListener(
			"input",
			debounce(function () {
				const query = this.value.toLowerCase();
				if (query.length > 2) {
					highlightSearchTerms(query);
					trackSearchQuery(query);
				}
			}, 300)
		);

		// Add keyboard shortcuts info
		searchInput.placeholder = "Buscar documentación... (Ctrl+K)";
	}
}

/**
 * Initialize tooltips for interactive elements
 */
function initTooltips() {
	const elementsWithTooltips = document.querySelectorAll("[title]");

	elementsWithTooltips.forEach((element) => {
		element.addEventListener("mouseenter", showTooltip);
		element.addEventListener("mouseleave", hideTooltip);
		element.addEventListener("focus", showTooltip);
		element.addEventListener("blur", hideTooltip);
	});
}

/**
 * Show custom tooltip
 */
function showTooltip(event) {
	const element = event.target;
	const tooltipText = element.title;

	if (!tooltipText) return;

	// Remove existing tooltips
	const existingTooltip = document.querySelector(".custom-tooltip");
	if (existingTooltip) {
		existingTooltip.remove();
	}

	// Create tooltip
	const tooltip = document.createElement("div");
	tooltip.className = "custom-tooltip";
	tooltip.textContent = tooltipText;
	tooltip.style.cssText = `
        position: absolute;
        background: rgba(0, 0, 0, 0.9);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 12px;
        z-index: 1000;
        pointer-events: none;
        max-width: 200px;
        word-wrap: break-word;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        backdrop-filter: blur(4px);
    `;

	document.body.appendChild(tooltip);

	// Position tooltip
	const rect = element.getBoundingClientRect();
	const tooltipRect = tooltip.getBoundingClientRect();

	let left = rect.left + rect.width / 2 - tooltipRect.width / 2;
	let top = rect.top - tooltipRect.height - 8;

	// Adjust if tooltip goes off screen
	if (left < 8) left = 8;
	if (left + tooltipRect.width > window.innerWidth - 8) {
		left = window.innerWidth - tooltipRect.width - 8;
	}
	if (top < 8) {
		top = rect.bottom + 8;
	}

	tooltip.style.left = left + "px";
	tooltip.style.top = top + "px";

	// Hide original title to prevent double tooltip
	element.setAttribute("data-original-title", element.title);
	element.removeAttribute("title");
}

/**
 * Hide custom tooltip
 */
function hideTooltip(event) {
	const tooltip = document.querySelector(".custom-tooltip");
	if (tooltip) {
		tooltip.remove();
	}

	// Restore original title
	const element = event.target;
	const originalTitle = element.getAttribute("data-original-title");
	if (originalTitle) {
		element.title = originalTitle;
		element.removeAttribute("data-original-title");
	}
}

/**
 * Initialize metrics badges with animations
 */
function initMetricsBadges() {
	const badges = document.querySelectorAll(".metric-badge");

	badges.forEach((badge) => {
		badge.addEventListener("mouseenter", function () {
			this.style.transform = "scale(1.05)";
			this.style.boxShadow = "0 4px 12px rgba(0,0,0,0.2)";
		});

		badge.addEventListener("mouseleave", function () {
			this.style.transform = "scale(1)";
			this.style.boxShadow = "none";
		});
	});
}

/**
 * Optimize for printing
 */
function initPrintOptimizations() {
	window.addEventListener("beforeprint", function () {
		// Expand all collapsed sections
		const details = document.querySelectorAll("details");
		details.forEach((detail) => {
			detail.setAttribute("open", "true");
		});

		// Remove animations
		document.body.style.animationDuration = "0s";
		document.body.style.transitionDuration = "0s";
	});
}

/**
 * Initialize keyboard shortcuts
 */
function initKeyboardShortcuts() {
	document.addEventListener("keydown", function (event) {
		// Ctrl/Cmd + K for search
		if ((event.ctrlKey || event.metaKey) && event.key === "k") {
			event.preventDefault();
			const searchInput = document.querySelector('input[data-md-component="search-query"]');
			if (searchInput) {
				searchInput.focus();
				searchInput.select();
			}
		}

		// Ctrl/Cmd + / for help
		if ((event.ctrlKey || event.metaKey) && event.key === "/") {
			event.preventDefault();
			showKeyboardShortcuts();
		}

		// ESC to close search
		if (event.key === "Escape") {
			const searchInput = document.querySelector('input[data-md-component="search-query"]');
			if (searchInput && document.activeElement === searchInput) {
				searchInput.blur();
			}
		}
	});
}

/**
 * Show keyboard shortcuts modal
 */
function showKeyboardShortcuts() {
	const modal = document.createElement("div");
	modal.className = "shortcuts-modal";
	modal.innerHTML = `
        <div class="shortcuts-content">
            <h3>⌨️ Atajos de Teclado</h3>
            <ul>
                <li><kbd>Ctrl</kbd> + <kbd>K</kbd> - Buscar</li>
                <li><kbd>Ctrl</kbd> + <kbd>/</kbd> - Mostrar atajos</li>
                <li><kbd>Esc</kbd> - Cerrar búsqueda</li>
            </ul>
            <button onclick="this.parentElement.parentElement.remove()">Cerrar</button>
        </div>
    `;

	modal.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.5);
        display: flex;
        align-items: center;
        justify-content: center;
        z-index: 2000;
    `;

	const content = modal.querySelector(".shortcuts-content");
	content.style.cssText = `
        background: white;
        padding: 24px;
        border-radius: 8px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        max-width: 400px;
        width: 90%;
    `;

	document.body.appendChild(modal);

	// Close on click outside
	modal.addEventListener("click", function (event) {
		if (event.target === modal) {
			modal.remove();
		}
	});
}

/**
 * Enhanced theme toggle
 */
function initThemeToggle() {
	const themeToggle = document.querySelector('[data-md-component="palette"]');

	if (themeToggle) {
		themeToggle.addEventListener("change", function () {
			const theme = this.checked ? "dark" : "light";
			localStorage.setItem("fm-docs-theme", theme);
			trackThemeChange(theme);
		});
	}
}

/**
 * Enhance tables with sorting and filtering
 */
function initTableEnhancements() {
	const tables = document.querySelectorAll(".md-typeset table");

	tables.forEach((table) => {
		// Add sorting to headers
		const headers = table.querySelectorAll("th");
		headers.forEach((header, index) => {
			if (header.textContent.trim()) {
				header.style.cursor = "pointer";
				header.title = "Clic para ordenar";

				header.addEventListener("click", function () {
					sortTable(table, index);
				});
			}
		});

		// Add hover effects to rows
		const rows = table.querySelectorAll("tbody tr");
		rows.forEach((row) => {
			row.addEventListener("mouseenter", function () {
				this.style.backgroundColor = "rgba(25, 118, 210, 0.08)";
			});

			row.addEventListener("mouseleave", function () {
				this.style.backgroundColor = "";
			});
		});
	});
}

/**
 * Sort table by column
 */
function sortTable(table, columnIndex) {
	const tbody = table.querySelector("tbody");
	const rows = Array.from(tbody.querySelectorAll("tr"));

	const isNumeric = rows.every((row) => {
		const cell = row.cells[columnIndex];
		return cell && !isNaN(parseFloat(cell.textContent.trim()));
	});

	rows.sort((a, b) => {
		const aText = a.cells[columnIndex].textContent.trim();
		const bText = b.cells[columnIndex].textContent.trim();

		if (isNumeric) {
			return parseFloat(aText) - parseFloat(bText);
		} else {
			return aText.localeCompare(bText, "es");
		}
	});

	// Re-append sorted rows
	rows.forEach((row) => tbody.appendChild(row));
}

/**
 * Analytics and tracking
 */
function initAnalytics() {
	// Track page views
	trackPageView();

	// Track scroll depth
	trackScrollDepth();

	// Track time on page
	const startTime = Date.now();
	window.addEventListener("beforeunload", function () {
		const timeSpent = Date.now() - startTime;
		trackTimeOnPage(timeSpent);
	});
}

/**
 * Track page view
 */
function trackPageView() {
	const page = location.pathname;
	console.log(`📊 Page view: ${page}`);

	// Send to analytics if configured
	if (typeof window.gtag !== "undefined") {
		window.gtag("config", "GA_TRACKING_ID", {
			page_path: page,
		});
	}
}

/**
 * Track search queries
 */
function trackSearchQuery(query) {
	console.log(`🔍 Search query: ${query}`);

	if (typeof window.gtag !== "undefined") {
		window.gtag("event", "search", {
			search_term: query,
		});
	}
}

/**
 * Track theme changes
 */
function trackThemeChange(theme) {
	console.log(`🎨 Theme changed to: ${theme}`);

	if (typeof window.gtag !== "undefined") {
		window.gtag("event", "theme_change", {
			theme: theme,
		});
	}
}

/**
 * Track scroll depth
 */
function trackScrollDepth() {
	let maxScroll = 0;
	const milestones = [25, 50, 75, 100];
	const tracked = new Set();

	window.addEventListener(
		"scroll",
		debounce(function () {
			const scrollPercent = Math.round(
				(window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100
			);

			maxScroll = Math.max(maxScroll, scrollPercent);

			milestones.forEach((milestone) => {
				if (maxScroll >= milestone && !tracked.has(milestone)) {
					tracked.add(milestone);
					console.log(`📊 Scroll depth: ${milestone}%`);

					if (typeof window.gtag !== "undefined") {
						window.gtag("event", "scroll", {
							scroll_depth: milestone,
						});
					}
				}
			});
		}, 250)
	);
}

/**
 * Track time on page
 */
function trackTimeOnPage(timeSpent) {
	const minutes = Math.floor(timeSpent / 60000);
	console.log(`⏱️ Time on page: ${minutes} minutes`);

	if (typeof window.gtag !== "undefined") {
		window.gtag("event", "time_on_page", {
			time_minutes: minutes,
			page: location.pathname,
		});
	}
}

/**
 * Utility: Debounce function
 */
function debounce(func, wait) {
	let timeout;
	return function executedFunction(...args) {
		const later = () => {
			clearTimeout(timeout);
			func(...args);
		};
		clearTimeout(timeout);
		timeout = setTimeout(later, wait);
	};
}

/**
 * Highlight search terms in content
 */
function highlightSearchTerms(query) {
	// Remove existing highlights
	const existingHighlights = document.querySelectorAll(".search-highlight");
	existingHighlights.forEach((el) => {
		el.outerHTML = el.innerHTML;
	});

	if (query.length < 3) return;

	// Find and highlight terms
	const walker = document.createTreeWalker(
		document.querySelector(".md-content"),
		NodeFilter.SHOW_TEXT,
		null,
		false
	);

	const textNodes = [];
	let node;

	while ((node = walker.nextNode())) {
		if (node.parentElement.closest("script, style, code, pre")) continue;
		textNodes.push(node);
	}

	textNodes.forEach((textNode) => {
		const text = textNode.textContent;
		const regex = new RegExp(`(${escapeRegExp(query)})`, "gi");

		if (regex.test(text)) {
			const highlightedHTML = text.replace(
				regex,
				'<span class="search-highlight">$1</span>'
			);
			const wrapper = document.createElement("span");
			wrapper.innerHTML = highlightedHTML;
			textNode.parentNode.replaceChild(wrapper, textNode);
		}
	});
}

/**
 * Escape string for regex
 */
function escapeRegExp(string) {
	return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// Export functions for external use
window.FMDocs = {
	initCopyCodeButtons,
	showKeyboardShortcuts,
	trackPageView,
	trackSearchQuery,
};

console.log("✅ Advanced documentation features initialized successfully");
