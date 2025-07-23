# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Multi-Sucursal Dashboard Integration - Sprint 6 Phase 5
Integración del sistema multi-sucursal con Dashboard Fiscal
"""

import frappe
from frappe import _

from facturacion_mexico.dashboard_fiscal.dashboard_registry import DashboardRegistry


def setup_multibranch_dashboard_integration():
	"""Configurar integración completa multi-sucursal con Dashboard Fiscal"""
	try:
		# 1. Registrar KPIs multi-sucursal
		_register_multibranch_kpis()

		# 2. Registrar widgets especializados
		_register_multibranch_widgets()

		# 3. Registrar alertas específicas
		_register_multibranch_alerts()

		# 4. Configurar métricas de performance
		_register_performance_metrics()

		return {"success": True, "message": "Integración multi-sucursal configurada exitosamente"}

	except Exception as e:
		frappe.log_error(f"Error in multibranch dashboard integration: {e!s}", "Multibranch Integration")
		return {"success": False, "message": f"Error: {e!s}"}


def _register_multibranch_kpis():
	"""Registrar KPIs específicos de multi-sucursal"""
	kpis = {
		"facturas_por_sucursal": {
			"name": "Facturas por Sucursal",
			"description": "Distribución de facturas por ubicación",
			"calculation_function": calculate_invoices_by_branch,
			"refresh_interval": 300,  # 5 minutos
			"widget_type": "chart_bar",
			"category": "multi_sucursal",
		},
		"folios_disponibles": {
			"name": "Folios Disponibles",
			"description": "Disponibilidad de folios por sucursal",
			"calculation_function": calculate_folio_availability,
			"refresh_interval": 60,  # 1 minuto
			"widget_type": "gauge",
			"category": "multi_sucursal",
			"alert_threshold": 100,  # Alertar cuando < 100 folios
		},
		"certificados_por_vencer": {
			"name": "Certificados por Vencer",
			"description": "Certificados SAT próximos a vencer",
			"calculation_function": get_expiring_certificates,
			"refresh_interval": 3600,  # 1 hora
			"widget_type": "alert_list",
			"category": "multi_sucursal",
		},
		"sucursales_activas": {
			"name": "Sucursales Activas",
			"description": "Estado operativo de sucursales",
			"calculation_function": count_active_branches,
			"refresh_interval": 900,  # 15 minutos
			"widget_type": "counter",
			"category": "multi_sucursal",
		},
		"eficiencia_timbrado": {
			"name": "Eficiencia de Timbrado",
			"description": "Tiempo promedio de timbrado por sucursal",
			"calculation_function": calculate_stamping_efficiency,
			"refresh_interval": 1800,  # 30 minutos
			"widget_type": "chart_line",
			"category": "multi_sucursal",
		},
	}

	for kpi_code, kpi_config in kpis.items():
		DashboardRegistry.register_kpi(kpi_code, kpi_config)


def _register_multibranch_widgets():
	"""Registrar widgets especializados multi-sucursal"""
	widgets = [
		{
			"code": "branch_heatmap",
			"name": "Mapa de Calor Sucursales",
			"description": "Visualización geográfica del rendimiento",
			"type": "map",
			"size": "large",
			"data_source": "branch_performance_data",
			"refresh_interval": 600,
			"permissions": ["Multi Sucursal Manager", "System Manager"],
		},
		{
			"code": "folio_status_grid",
			"name": "Estado de Folios Grid",
			"description": "Vista detallada de folios por sucursal",
			"type": "grid",
			"size": "medium",
			"data_source": "folio_status_data",
			"refresh_interval": 300,
			"permissions": ["Multi Sucursal Manager", "Accounts User"],
		},
		{
			"code": "certificate_timeline",
			"name": "Timeline Certificados",
			"description": "Cronología de vencimientos de certificados",
			"type": "timeline",
			"size": "medium",
			"data_source": "certificate_expiry_data",
			"refresh_interval": 3600,
			"permissions": ["Multi Sucursal Manager", "System Manager"],
		},
		{
			"code": "branch_comparison",
			"name": "Comparativo Sucursales",
			"description": "Análisis comparativo de rendimiento",
			"type": "comparison_chart",
			"size": "large",
			"data_source": "branch_comparison_data",
			"refresh_interval": 1800,
			"permissions": ["Multi Sucursal Manager"],
		},
	]

	for widget in widgets:
		DashboardRegistry.register_widget(widget)


def _register_multibranch_alerts():
	"""Registrar alertas específicas multi-sucursal"""
	alerts = [
		{
			"code": "folio_shortage",
			"name": "Escasez de Folios",
			"description": "Alerta cuando folios disponibles < threshold",
			"severity": "warning",
			"check_function": check_folio_shortage,
			"check_interval": 300,  # 5 minutos
			"notification_channels": ["email", "dashboard"],
		},
		{
			"code": "certificate_expiry",
			"name": "Certificado por Vencer",
			"description": "Certificado vence en menos de 30 días",
			"severity": "critical",
			"check_function": check_certificate_expiry,
			"check_interval": 3600,  # 1 hora
			"notification_channels": ["email", "dashboard", "slack"],
		},
		{
			"code": "branch_offline",
			"name": "Sucursal Sin Actividad",
			"description": "Sucursal sin facturas en 24h",
			"severity": "warning",
			"check_function": check_branch_activity,
			"check_interval": 1800,  # 30 minutos
			"notification_channels": ["dashboard"],
		},
	]

	for alert in alerts:
		DashboardRegistry.register_alert(alert)


def _register_performance_metrics():
	"""Registrar métricas de performance multi-sucursal"""
	metrics = [
		{
			"code": "stamping_time_avg",
			"name": "Tiempo Promedio Timbrado",
			"unit": "seconds",
			"calculation_function": "calculate_avg_stamping_time",
			"target_value": 30,  # 30 segundos objetivo
		},
		{
			"code": "error_rate_by_branch",
			"name": "Tasa de Error por Sucursal",
			"unit": "percentage",
			"calculation_function": "calculate_error_rate_by_branch",
			"target_value": 5,  # Máximo 5% errores
		},
		{
			"code": "daily_invoice_volume",
			"name": "Volumen Diario Facturas",
			"unit": "count",
			"calculation_function": "calculate_daily_invoice_volume",
			"target_value": None,  # Sin objetivo específico
		},
	]

	for metric in metrics:
		DashboardRegistry.register_metric(metric)


# Funciones de cálculo KPI
def calculate_invoices_by_branch() -> dict:
	"""Calcular distribución de facturas por sucursal"""
	try:
		query = """
            SELECT
                COALESCE(si.fm_branch, 'Sin Sucursal') as branch,
                COUNT(*) as invoice_count,
                SUM(si.grand_total) as total_amount,
                COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) as stamped_count
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
            AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            GROUP BY branch
            ORDER BY invoice_count DESC
        """

		results = frappe.db.sql(query, as_dict=True)

		return {
			"success": True,
			"data": results,
			"chart_data": {
				"labels": [r["branch"] for r in results],
				"datasets": [
					{
						"name": "Facturas",
						"values": [r["invoice_count"] for r in results],
					}
				],
			},
		}

	except Exception as e:
		frappe.log_error(f"Error calculating invoices by branch: {e!s}", "Multibranch KPI")
		return {"success": False, "error": str(e)}


def calculate_folio_availability() -> dict:
	"""Calcular disponibilidad de folios por sucursal"""
	try:
		# Obtener folios disponibles por sucursal
		folios_data = frappe.db.sql(
			"""
            SELECT
                cfs.parent as branch,
                cfs.folio_end - cfs.folio_current as available_folios,
                cfs.folio_end,
                cfs.folio_current,
                CASE
                    WHEN (cfs.folio_end - cfs.folio_current) > 500 THEN 'good'
                    WHEN (cfs.folio_end - cfs.folio_current) > 100 THEN 'warning'
                    ELSE 'critical'
                END as status
            FROM `tabConfiguracion Fiscal Sucursal` cfs
            WHERE cfs.parenttype = 'Branch'
            AND cfs.is_active = 1
        """,
			as_dict=True,
		)

		return {
			"success": True,
			"data": folios_data,
			"summary": {
				"total_branches": len(folios_data),
				"critical_branches": len([f for f in folios_data if f["status"] == "critical"]),
				"warning_branches": len([f for f in folios_data if f["status"] == "warning"]),
			},
		}

	except Exception as e:
		frappe.log_error(f"Error calculating folio availability: {e!s}", "Multibranch KPI")
		return {"success": False, "error": str(e)}


def get_expiring_certificates() -> dict:
	"""Obtener certificados próximos a vencer"""
	try:
		expiring_certs = frappe.db.sql(
			"""
            SELECT
                cfs.parent as branch,
                cfs.certificate_file_name,
                cfs.certificate_expiry_date,
                DATEDIFF(cfs.certificate_expiry_date, CURDATE()) as days_to_expiry
            FROM `tabConfiguracion Fiscal Sucursal` cfs
            WHERE cfs.parenttype = 'Branch'
            AND cfs.is_active = 1
            AND cfs.certificate_expiry_date <= DATE_ADD(CURDATE(), INTERVAL 60 DAY)
            ORDER BY cfs.certificate_expiry_date ASC
        """,
			as_dict=True,
		)

		return {
			"success": True,
			"data": expiring_certs,
			"summary": {
				"total_expiring": len(expiring_certs),
				"critical": len([c for c in expiring_certs if c["days_to_expiry"] <= 7]),
				"warning": len([c for c in expiring_certs if 7 < c["days_to_expiry"] <= 30]),
			},
		}

	except Exception as e:
		frappe.log_error(f"Error getting expiring certificates: {e!s}", "Multibranch KPI")
		return {"success": False, "error": str(e)}


def count_active_branches() -> dict:
	"""Contar sucursales activas y su estado"""
	try:
		branch_status = frappe.db.sql(
			"""
            SELECT
                b.name as branch,
                b.is_group,
                COUNT(DISTINCT cfs.name) as fiscal_configs,
                COUNT(DISTINCT si.name) as recent_invoices,
                CASE
                    WHEN COUNT(DISTINCT si.name) > 0 THEN 'active'
                    WHEN COUNT(DISTINCT cfs.name) > 0 THEN 'configured'
                    ELSE 'inactive'
                END as status
            FROM `tabBranch` b
            LEFT JOIN `tabConfiguracion Fiscal Sucursal` cfs ON cfs.parent = b.name
            LEFT JOIN `tabSales Invoice` si ON si.fm_branch = b.name
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
                AND si.docstatus = 1
            WHERE b.disabled = 0
            GROUP BY b.name, b.is_group
            ORDER BY recent_invoices DESC
        """,
			as_dict=True,
		)

		return {
			"success": True,
			"data": branch_status,
			"summary": {
				"total_branches": len(branch_status),
				"active_branches": len([b for b in branch_status if b["status"] == "active"]),
				"configured_branches": len([b for b in branch_status if b["status"] == "configured"]),
				"inactive_branches": len([b for b in branch_status if b["status"] == "inactive"]),
			},
		}

	except Exception as e:
		frappe.log_error(f"Error counting active branches: {e!s}", "Multibranch KPI")
		return {"success": False, "error": str(e)}


def calculate_stamping_efficiency() -> dict:
	"""Calcular eficiencia de timbrado por sucursal"""
	try:
		efficiency_data = frappe.db.sql(
			"""
            SELECT
                COALESCE(si.fm_branch, 'Sin Sucursal') as branch,
                COUNT(*) as total_invoices,
                COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) as stamped_invoices,
                ROUND(
                    (COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) * 100.0 / COUNT(*)),
                    2
                ) as stamping_percentage,
                AVG(
                    CASE WHEN si.fm_cfdi_xml IS NOT NULL
                    THEN TIMESTAMPDIFF(SECOND, si.creation, si.modified)
                    END
                ) as avg_stamping_time_seconds
            FROM `tabSales Invoice` si
            WHERE si.docstatus = 1
            AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 7 DAY)
            GROUP BY branch
            HAVING total_invoices > 0
            ORDER BY stamping_percentage DESC
        """,
			as_dict=True,
		)

		return {
			"success": True,
			"data": efficiency_data,
			"chart_data": {
				"labels": [r["branch"] for r in efficiency_data],
				"datasets": [
					{
						"name": "% Timbrado",
						"values": [r["stamping_percentage"] for r in efficiency_data],
					}
				],
			},
		}

	except Exception as e:
		frappe.log_error(f"Error calculating stamping efficiency: {e!s}", "Multibranch KPI")
		return {"success": False, "error": str(e)}


# Funciones de verificación de alertas
def check_folio_shortage() -> dict:
	"""Verificar escasez de folios"""
	try:
		shortage_branches = frappe.db.sql(
			"""
            SELECT
                cfs.parent as branch,
                (cfs.folio_end - cfs.folio_current) as available_folios
            FROM `tabConfiguracion Fiscal Sucursal` cfs
            WHERE cfs.parenttype = 'Branch'
            AND cfs.is_active = 1
            AND (cfs.folio_end - cfs.folio_current) < 100
        """,
			as_dict=True,
		)

		if shortage_branches:
			return {
				"alert_triggered": True,
				"severity": "warning",
				"message": f"Escasez de folios detectada en {len(shortage_branches)} sucursales",
				"details": shortage_branches,
			}

		return {"alert_triggered": False}

	except Exception as e:
		frappe.log_error(f"Error checking folio shortage: {e!s}", "Multibranch Alert")
		return {"alert_triggered": False, "error": str(e)}


def check_certificate_expiry() -> dict:
	"""Verificar vencimiento de certificados"""
	try:
		expiring_soon = frappe.db.sql(
			"""
            SELECT
                cfs.parent as branch,
                cfs.certificate_file_name,
                DATEDIFF(cfs.certificate_expiry_date, CURDATE()) as days_to_expiry
            FROM `tabConfiguracion Fiscal Sucursal` cfs
            WHERE cfs.parenttype = 'Branch'
            AND cfs.is_active = 1
            AND cfs.certificate_expiry_date <= DATE_ADD(CURDATE(), INTERVAL 30 DAY)
        """,
			as_dict=True,
		)

		if expiring_soon:
			critical = [c for c in expiring_soon if c["days_to_expiry"] <= 7]
			severity = "critical" if critical else "warning"

			return {
				"alert_triggered": True,
				"severity": severity,
				"message": f"Certificados por vencer: {len(expiring_soon)} total, {len(critical)} críticos",
				"details": expiring_soon,
			}

		return {"alert_triggered": False}

	except Exception as e:
		frappe.log_error(f"Error checking certificate expiry: {e!s}", "Multibranch Alert")
		return {"alert_triggered": False, "error": str(e)}


def check_branch_activity() -> dict:
	"""Verificar actividad de sucursales"""
	try:
		inactive_branches = frappe.db.sql(
			"""
            SELECT b.name as branch
            FROM `tabBranch` b
            LEFT JOIN `tabSales Invoice` si ON si.fm_branch = b.name
                AND si.posting_date >= DATE_SUB(CURDATE(), INTERVAL 1 DAY)
                AND si.docstatus = 1
            WHERE b.disabled = 0
            AND b.is_group = 0
            GROUP BY b.name
            HAVING COUNT(si.name) = 0
        """,
			as_dict=True,
		)

		if inactive_branches:
			return {
				"alert_triggered": True,
				"severity": "info",
				"message": f"Sucursales sin actividad en 24h: {len(inactive_branches)}",
				"details": inactive_branches,
			}

		return {"alert_triggered": False}

	except Exception as e:
		frappe.log_error(f"Error checking branch activity: {e!s}", "Multibranch Alert")
		return {"alert_triggered": False, "error": str(e)}


# APIs públicas
@frappe.whitelist()
def setup_multibranch_integration():
	"""API para configurar integración multi-sucursal"""
	return setup_multibranch_dashboard_integration()


@frappe.whitelist()
def get_multibranch_dashboard_data():
	"""API para obtener datos completos del dashboard multi-sucursal"""
	try:
		data = {
			"invoices_by_branch": calculate_invoices_by_branch(),
			"folio_availability": calculate_folio_availability(),
			"expiring_certificates": get_expiring_certificates(),
			"active_branches": count_active_branches(),
			"stamping_efficiency": calculate_stamping_efficiency(),
		}

		return {"success": True, "dashboard_data": data}

	except Exception as e:
		frappe.log_error(f"Error getting multibranch dashboard data: {e!s}", "Multibranch Dashboard API")
		return {"success": False, "message": f"Error: {e!s}"}
