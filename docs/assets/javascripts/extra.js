/* Custom JavaScript for Facturación México Documentation */

document.addEventListener("DOMContentLoaded", function () {
	// Add copy buttons to code blocks
	addCopyButtons();

	// Initialize tooltips
	initializeTooltips();

	// Add smooth scrolling
	addSmoothScrolling();

	// Initialize search enhancements
	enhanceSearch();

	// Add version switcher functionality
	initVersionSwitcher();
});

/**
 * Add copy buttons to code blocks
 */
function addCopyButtons() {
	const codeBlocks = document.querySelectorAll("pre code");

	codeBlocks.forEach(function (codeBlock) {
		const pre = codeBlock.parentNode;
		const button = document.createElement("button");

		button.className = "copy-button";
		button.innerHTML = '<i class="material-icons">content_copy</i>';
		button.title = "Copiar código";

		button.addEventListener("click", function () {
			const text = codeBlock.textContent;

			navigator.clipboard.writeText(text).then(function () {
				button.innerHTML = '<i class="material-icons">check</i>';
				button.style.color = "#4caf50";

				setTimeout(function () {
					button.innerHTML = '<i class="material-icons">content_copy</i>';
					button.style.color = "";
				}, 2000);
			});
		});

		pre.style.position = "relative";
		pre.appendChild(button);
	});
}

/**
 * Initialize tooltips for badges and status indicators
 */
function initializeTooltips() {
	const badgeElements = document.querySelectorAll(".status-badge, .interrogate-badge");

	badgeElements.forEach(function (element) {
		if (element.title) {
			element.addEventListener("mouseenter", showTooltip);
			element.addEventListener("mouseleave", hideTooltip);
		}
	});
}

/**
 * Add smooth scrolling to anchor links
 */
function addSmoothScrolling() {
	const links = document.querySelectorAll('a[href^="#"]');

	links.forEach(function (link) {
		link.addEventListener("click", function (e) {
			const target = document.querySelector(this.getAttribute("href"));

			if (target) {
				e.preventDefault();
				target.scrollIntoView({
					behavior: "smooth",
					block: "start",
				});
			}
		});
	});
}

/**
 * Enhance search functionality
 */
function enhanceSearch() {
	const searchInput = document.querySelector(".md-search__input");

	if (searchInput) {
		// Add search suggestions
		searchInput.addEventListener(
			"input",
			debounce(function () {
				const query = this.value.toLowerCase();
				if (query.length > 2) {
					highlightSearchTerms(query);
				}
			}, 300)
		);
	}
}

/**
 * Initialize version switcher
 */
function initVersionSwitcher() {
	const versionSelect = document.querySelector("#version-selector");

	if (versionSelect) {
		versionSelect.addEventListener("change", function () {
			const selectedVersion = this.value;
			window.location.href = `/${selectedVersion}/`;
		});
	}
}

/**
 * Highlight search terms in content
 */
function highlightSearchTerms(query) {
	const content = document.querySelector(".md-content");
	const walker = document.createTreeWalker(content, NodeFilter.SHOW_TEXT, null, false);

	const textNodes = [];
	let node;

	while ((node = walker.nextNode())) {
		textNodes.push(node);
	}

	textNodes.forEach(function (textNode) {
		const text = textNode.textContent;
		const regex = new RegExp(`(${query})`, "gi");

		if (regex.test(text)) {
			const highlightedText = text.replace(regex, "<mark>$1</mark>");
			const wrapper = document.createElement("span");
			wrapper.innerHTML = highlightedText;
			textNode.parentNode.replaceChild(wrapper, textNode);
		}
	});
}

/**
 * Show tooltip
 */
function showTooltip(event) {
	const tooltip = document.createElement("div");
	tooltip.className = "custom-tooltip";
	tooltip.textContent = event.target.title;

	document.body.appendChild(tooltip);

	const rect = event.target.getBoundingClientRect();
	tooltip.style.left = rect.left + rect.width / 2 - tooltip.offsetWidth / 2 + "px";
	tooltip.style.top = rect.top - tooltip.offsetHeight - 8 + "px";

	event.target.setAttribute("data-original-title", event.target.title);
	event.target.removeAttribute("title");
}

/**
 * Hide tooltip
 */
function hideTooltip(event) {
	const tooltip = document.querySelector(".custom-tooltip");
	if (tooltip) {
		tooltip.remove();
	}

	const originalTitle = event.target.getAttribute("data-original-title");
	if (originalTitle) {
		event.target.title = originalTitle;
		event.target.removeAttribute("data-original-title");
	}
}

/**
 * Debounce function for performance
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
 * Add CSS for custom elements
 */
const customStyles = `
    .copy-button {
        position: absolute;
        top: 8px;
        right: 8px;
        background: rgba(255, 255, 255, 0.8);
        border: none;
        border-radius: 4px;
        padding: 4px;
        cursor: pointer;
        opacity: 0;
        transition: opacity 0.2s ease;
    }
    
    pre:hover .copy-button {
        opacity: 1;
    }
    
    .copy-button:hover {
        background: rgba(255, 255, 255, 1);
    }
    
    .custom-tooltip {
        position: absolute;
        background: rgba(0, 0, 0, 0.8);
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        z-index: 1000;
        pointer-events: none;
    }
    
    mark {
        background-color: #ffeb3b;
        padding: 1px 2px;
        border-radius: 2px;
    }
`;

// Add styles to document
const styleSheet = document.createElement("style");
styleSheet.textContent = customStyles;
document.head.appendChild(styleSheet);
