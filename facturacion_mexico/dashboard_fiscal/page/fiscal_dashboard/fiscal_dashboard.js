// Dashboard Fiscal JavaScript
// Sistema de facturación legal México

frappe.pages["fiscal_dashboard"].on_page_load = function (wrapper) {
	// Inicializar página del dashboard
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dashboard Fiscal"),
		single_column: true,
	});

	// Configurar la página
	page.dashboard = new FiscalDashboard(page);
};

class FiscalDashboard {
	constructor(page) {
		this.page = page;
		this.wrapper = page.wrapper;
		this.company = frappe.defaults.get_user_default("Company");
		this.refresh_interval = 300000; // 5 minutos
		this.auto_refresh_enabled = true;
		this.widgets = new Map();
		this.refresh_timer = null;

		this.init();
	}

	init() {
		// Configurar interfaz
		this.setup_page();
		this.setup_controls();
		this.load_dashboard_data();
		this.setup_auto_refresh();

		// Event listeners
		this.setup_event_listeners();
	}

	setup_page() {
		// Limpiar contenido existente
		this.page.clear_inner_toolbar();

		// Agregar controles al toolbar
		this.page.add_inner_button(
			__("Refresh"),
			() => {
				this.refresh_dashboard();
			},
			"refresh"
		);

		this.page.add_inner_button(
			__("Configure"),
			() => {
				this.open_configuration_dialog();
			},
			"settings"
		);

		this.page.add_inner_button(
			__("Export"),
			() => {
				this.export_dashboard_report();
			},
			"download"
		);

		// Agregar selector de empresa
		this.company_select = this.page.add_field({
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			label: __("Company"),
			default: this.company,
			change: () => {
				this.company = this.company_select.get_value();
				this.refresh_dashboard();
			},
		});
	}

	setup_controls() {
		// Crear contenedor principal del dashboard
		this.dashboard_container = $(`
			<div class="fiscal-dashboard-main">
				<div class="dashboard-header-info">
					<div class="dashboard-stats">
						<div class="stat-item">
							<label>${__("Last Update")}:</label>
							<span id="last-update-time">--</span>
						</div>
						<div class="stat-item">
							<label>${__("Auto Refresh")}:</label>
							<span id="auto-refresh-status">${this.auto_refresh_enabled ? __("Enabled") : __("Disabled")}</span>
						</div>
						<div class="stat-item">
							<label>${__("Next Update")}:</label>
							<span id="next-update-time">--</span>
						</div>
					</div>
				</div>
				<div class="dashboard-grid" id="dashboard-grid">
					<!-- Widgets se cargan aquí -->
				</div>
				<div class="dashboard-alerts" id="dashboard-alerts">
					<!-- Alertas se cargan aquí -->
				</div>
			</div>
		`);

		$(this.wrapper).find(".layout-main-section").html(this.dashboard_container);
	}

	setup_event_listeners() {
		// Listener para cambios de tamaño de ventana
		$(window).on(
			"resize",
			frappe.utils.debounce(() => {
				this.resize_widgets();
			}, 300)
		);

		// Listener para visibilidad de página (pausar refresh cuando no visible)
		document.addEventListener("visibilitychange", () => {
			if (document.visibilityState === "visible") {
				this.resume_auto_refresh();
			} else {
				this.pause_auto_refresh();
			}
		});
	}

	async load_dashboard_data() {
		try {
			this.show_loading();

			// Cargar datos principales del dashboard
			const dashboard_data = await this.fetch_dashboard_data();

			if (dashboard_data.success) {
				await this.render_widgets(dashboard_data.data.widgets);
				await this.render_alerts(dashboard_data.data.alerts);
				this.update_performance_info(dashboard_data.data.performance);
			} else {
				this.show_error(dashboard_data.message || __("Error loading dashboard data"));
			}
		} catch (error) {
			console.error("Error loading dashboard:", error);
			this.show_error(__("Failed to load dashboard data"));
		} finally {
			this.hide_loading();
			this.update_last_update_time();
		}
	}

	async fetch_dashboard_data() {
		return new Promise((resolve) => {
			frappe.call({
				method: "facturacion_mexico.dashboard_fiscal.api.get_dashboard_data",
				args: {
					company: this.company,
					period: "month",
				},
				callback: (r) => {
					resolve(r.message || { success: false, message: "No data received" });
				},
				error: (r) => {
					resolve({ success: false, message: r.message || "API Error" });
				},
			});
		});
	}

	async render_widgets(widgets_data) {
		const grid = this.dashboard_container.find("#dashboard-grid");
		grid.empty();

		// Configurar CSS Grid
		grid.css({
			display: "grid",
			"grid-template-columns": "repeat(4, 1fr)",
			"grid-template-rows": "repeat(4, 1fr)",
			gap: "20px",
			"min-height": "600px",
		});

		// Renderizar cada widget
		for (const widget_data of widgets_data) {
			await this.render_widget(widget_data, grid);
		}
	}

	async render_widget(widget_data, container) {
		const widget_element = $(`
			<div class="dashboard-widget"
				 data-widget-code="${widget_data.code}"
				 style="grid-column: ${widget_data.position.col} / span ${widget_data.position.width};
						grid-row: ${widget_data.position.row} / span ${widget_data.position.height};">
				<div class="widget-header">
					<h4 class="widget-title">${widget_data.name}</h4>
					<div class="widget-controls">
						<button class="btn btn-xs widget-refresh" title="${__("Refresh Widget")}">
							<i class="fa fa-refresh"></i>
						</button>
						<button class="btn btn-xs widget-expand" title="${__("Expand Widget")}">
							<i class="fa fa-expand"></i>
						</button>
					</div>
				</div>
				<div class="widget-content">
					<!-- Contenido se carga dinámicamente -->
				</div>
				<div class="widget-loading" style="display: none;">
					<div class="text-center">
						<i class="fa fa-spinner fa-spin"></i>
						<p>${__("Loading...")}</p>
					</div>
				</div>
			</div>
		`);

		// Event listeners para controles del widget
		widget_element.find(".widget-refresh").on("click", () => {
			this.refresh_widget(widget_data.code);
		});

		widget_element.find(".widget-expand").on("click", () => {
			this.expand_widget(widget_data.code);
		});

		container.append(widget_element);

		// Cargar contenido del widget
		await this.load_widget_content(widget_data, widget_element);

		// Guardar referencia del widget
		this.widgets.set(widget_data.code, {
			element: widget_element,
			data: widget_data,
		});
	}

	async load_widget_content(widget_data, widget_element) {
		const content_container = widget_element.find(".widget-content");

		try {
			switch (widget_data.type) {
				case "kpi_grid":
					await this.render_kpi_grid(widget_data, content_container);
					break;
				case "chart":
					await this.render_chart_widget(widget_data, content_container);
					break;
				case "table":
					await this.render_table_widget(widget_data, content_container);
					break;
				case "metric":
					await this.render_metric_widget(widget_data, content_container);
					break;
				case "alerts":
					await this.render_alerts_widget(widget_data, content_container);
					break;
				default:
					content_container.html(
						`<p class="text-muted">${__("Widget type not supported")}: ${
							widget_data.type
						}</p>`
					);
			}
		} catch (error) {
			console.error(`Error loading widget ${widget_data.code}:`, error);
			content_container.html(
				`<p class="text-danger">${__("Error loading widget content")}</p>`
			);
		}
	}

	async render_kpi_grid(widget_data, container) {
		if (!widget_data.kpis || widget_data.kpis.length === 0) {
			container.html(`<p class="text-muted">${__("No KPIs available")}</p>`);
			return;
		}

		const kpi_grid = $('<div class="kpi-grid"></div>');

		widget_data.kpis.forEach((kpi) => {
			const kpi_item = $(`
				<div class="kpi-item kpi-${kpi.color || "primary"}">
					<div class="kpi-value">${this.format_kpi_value(kpi.value, kpi.format)}</div>
					<div class="kpi-label">${kpi.subtitle || kpi.name}</div>
					${
						kpi.trend
							? `<div class="kpi-trend trend-${kpi.trend.direction}">
						<i class="fa fa-arrow-${kpi.trend.direction === "up" ? "up" : "down"}"></i>
						${kpi.trend.percentage}%
					</div>`
							: ""
					}
				</div>
			`);

			kpi_grid.append(kpi_item);
		});

		container.html(kpi_grid);
	}

	async render_metric_widget(widget_data, container) {
		if (!widget_data.metric) {
			container.html(`<p class="text-muted">${__("No metric data available")}</p>`);
			return;
		}

		const metric = widget_data.metric;
		const metric_html = $(`
			<div class="metric-widget">
				<div class="metric-main">
					<div class="metric-value metric-${metric.color || "primary"}">
						${this.format_kpi_value(metric.value, metric.format)}
					</div>
					<div class="metric-label">${metric.label}</div>
				</div>
				${metric.description ? `<div class="metric-description">${metric.description}</div>` : ""}
				${
					metric.trend
						? `
					<div class="metric-trend">
						<span class="trend-${metric.trend.direction}">
							<i class="fa fa-arrow-${metric.trend.direction === "up" ? "up" : "down"}"></i>
							${metric.trend.percentage}% ${__("vs previous period")}
						</span>
					</div>
				`
						: ""
				}
			</div>
		`);

		container.html(metric_html);
	}

	async render_alerts(alerts_data) {
		const alerts_container = this.dashboard_container.find("#dashboard-alerts");

		if (!alerts_data || alerts_data.length === 0) {
			alerts_container.html(`
				<div class="alert alert-info">
					<i class="fa fa-info-circle"></i>
					${__("No active alerts")}
				</div>
			`);
			return;
		}

		const alerts_html = $(`
			<div class="alerts-section">
				<h3 class="alerts-title">
					<i class="fa fa-exclamation-triangle"></i>
					${__("Active Alerts")} (${alerts_data.length})
				</h3>
				<div class="alerts-list"></div>
			</div>
		`);

		const alerts_list = alerts_html.find(".alerts-list");

		alerts_data.forEach((alert) => {
			const alert_item = $(`
				<div class="alert-item alert-${alert.type}">
					<div class="alert-icon">
						<i class="fa fa-${this.get_alert_icon(alert.type)}"></i>
					</div>
					<div class="alert-content">
						<div class="alert-message">${alert.message}</div>
						<div class="alert-meta">
							<span class="alert-module">${alert.module}</span>
							<span class="alert-time">${moment(alert.timestamp).fromNow()}</span>
							<span class="alert-priority priority-${alert.priority}">${__("Priority")}: ${alert.priority}</span>
						</div>
					</div>
					<div class="alert-actions">
						<button class="btn btn-sm btn-outline-secondary" onclick="frappe.dashboard.dismiss_alert('${
							alert.id
						}')">
							${__("Dismiss")}
						</button>
					</div>
				</div>
			`);

			alerts_list.append(alert_item);
		});

		alerts_container.html(alerts_html);
	}

	format_kpi_value(value, format) {
		if (value === null || value === undefined) return "--";

		switch (format) {
			case "currency":
				return frappe.format(value, { fieldtype: "Currency" });
			case "percentage":
				return `${parseFloat(value).toFixed(1)}%`;
			case "number":
				return frappe.format(value, { fieldtype: "Int" });
			case "float":
				return frappe.format(value, { fieldtype: "Float", precision: 2 });
			default:
				return value;
		}
	}

	get_alert_icon(type) {
		const icons = {
			error: "times-circle",
			warning: "exclamation-triangle",
			info: "info-circle",
			success: "check-circle",
		};
		return icons[type] || "bell";
	}

	// Funciones de control
	refresh_dashboard() {
		this.load_dashboard_data();
	}

	async refresh_widget(widget_code) {
		const widget = this.widgets.get(widget_code);
		if (!widget) return;

		const loading = widget.element.find(".widget-loading");
		const content = widget.element.find(".widget-content");

		loading.show();

		try {
			// Recargar datos específicos del widget
			const widget_data = await this.fetch_widget_data(widget_code);
			await this.load_widget_content(widget_data, widget.element);
		} finally {
			loading.hide();
		}
	}

	setup_auto_refresh() {
		if (this.auto_refresh_enabled && this.refresh_interval > 0) {
			this.refresh_timer = setInterval(() => {
				this.refresh_dashboard();
			}, this.refresh_interval);

			this.update_next_update_time();
		}
	}

	pause_auto_refresh() {
		if (this.refresh_timer) {
			clearInterval(this.refresh_timer);
			this.refresh_timer = null;
		}
	}

	resume_auto_refresh() {
		if (this.auto_refresh_enabled) {
			this.setup_auto_refresh();
		}
	}

	// Funciones de UI
	show_loading() {
		frappe.show_progress(__("Loading Dashboard"), 30, 100);
	}

	hide_loading() {
		frappe.hide_progress();
	}

	show_error(message) {
		frappe.show_alert(
			{
				message: message,
				indicator: "red",
			},
			5
		);
	}

	update_last_update_time() {
		const now = frappe.datetime.now_time();
		$("#last-update-time").text(now);
	}

	update_next_update_time() {
		if (this.auto_refresh_enabled && this.refresh_interval > 0) {
			const next_update = moment().add(this.refresh_interval, "milliseconds");
			$("#next-update-time").text(next_update.format("HH:mm:ss"));
		} else {
			$("#next-update-time").text("--");
		}
	}

	// Configuración
	open_configuration_dialog() {
		const dialog = new frappe.ui.Dialog({
			title: __("Dashboard Configuration"),
			fields: [
				{
					fieldtype: "Section Break",
					label: __("Display Settings"),
				},
				{
					fieldname: "auto_refresh",
					fieldtype: "Check",
					label: __("Enable Auto Refresh"),
					default: this.auto_refresh_enabled,
				},
				{
					fieldname: "refresh_interval",
					fieldtype: "Int",
					label: __("Refresh Interval (seconds)"),
					default: this.refresh_interval / 1000,
					depends_on: "auto_refresh",
				},
				{
					fieldtype: "Section Break",
					label: __("Widget Settings"),
				},
			],
			primary_action: (data) => {
				this.save_configuration(data);
				dialog.hide();
			},
			primary_action_label: __("Save Configuration"),
		});

		dialog.show();
	}

	save_configuration(config_data) {
		// Actualizar configuración local
		this.auto_refresh_enabled = config_data.auto_refresh;
		this.refresh_interval = config_data.refresh_interval * 1000;

		// Reiniciar auto-refresh con nueva configuración
		this.pause_auto_refresh();
		this.setup_auto_refresh();

		// Guardar en servidor
		frappe.call({
			method: "facturacion_mexico.dashboard_fiscal.api.save_dashboard_layout",
			args: {
				layout_config: {
					auto_refresh: this.auto_refresh_enabled,
					refresh_interval: this.refresh_interval,
				},
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					frappe.show_alert({
						message: __("Configuration saved successfully"),
						indicator: "green",
					});
				}
			},
		});
	}

	export_dashboard_report() {
		frappe.call({
			method: "facturacion_mexico.dashboard_fiscal.api.export_dashboard_report",
			args: {
				report_type: "pdf",
				company: this.company,
			},
			callback: (r) => {
				if (r.message && r.message.success) {
					// Descargar archivo
					window.open(r.message.download_url, "_blank");
				}
			},
		});
	}
}

// Función global para descartar alertas
window.dismiss_alert = function (alert_id) {
	frappe.call({
		method: "facturacion_mexico.dashboard_fiscal.api.dismiss_alert",
		args: { alert_id: alert_id },
		callback: (r) => {
			if (r.message && r.message.success) {
				$(`.alert-item[data-alert-id="${alert_id}"]`).fadeOut();
			}
		},
	});
};

// Exponer dashboard globalmente para debugging
frappe.dashboard = null;

// CSS personalizado
frappe.require("/assets/facturacion_mexico/css/fiscal_dashboard.css");
