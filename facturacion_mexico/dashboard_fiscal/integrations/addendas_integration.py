"""
Addendas Integration - Dashboard Fiscal
Integración del módulo de Addendas con el Dashboard
"""

from ..dashboard_registry import DashboardRegistry


def register_addendas_kpis():
	"""Registrar KPIs del módulo Addendas"""
	DashboardRegistry.register_kpi(
		"Addendas",
		{
			"addendas_activas": get_active_addendas,
			"facturas_con_addenda_mes": get_monthly_invoices_with_addenda,
			"templates_addenda_disponibles": get_available_addenda_templates,
			"tasa_aplicacion_addendas": get_addenda_application_rate,
			"errores_addendas_semana": get_weekly_addenda_errors,
			"clientes_requieren_addenda": get_customers_requiring_addenda,
		},
	)


def register_addendas_widgets():
	"""Registrar widgets del módulo Addendas"""
	DashboardRegistry.register_widget(
		{
			"code": "addendas_overview",
			"name": "Resumen Addendas",
			"type": "kpi_grid",
			"module": "Addendas",
			"position": {"row": 3, "col": 1, "width": 2, "height": 1},
		}
	)

	DashboardRegistry.register_widget(
		{
			"code": "addendas_usage_chart",
			"name": "Uso de Addendas",
			"type": "donut_chart",
			"module": "Addendas",
			"position": {"row": 4, "col": 1, "width": 2, "height": 1},
		}
	)


def register_addendas_alerts():
	"""Registrar evaluadores de alertas para Addendas"""
	DashboardRegistry.register_alert_evaluator(
		"Addendas",
		{
			"addendas_desactualizadas": check_outdated_addendas,
			"facturas_sin_addenda_requerida": check_missing_required_addendas,
			"errores_validacion_addenda": check_addenda_validation_errors,
			"templates_no_utilizados": check_unused_templates,
		},
	)


# KPI Functions


def get_active_addendas(**kwargs):
	"""Addendas activas en el sistema"""
	import frappe

	try:
		count = frappe.db.count("Addenda Template", filters={"is_active": 1, "docstatus": 1})

		return {"value": count, "format": "number", "subtitle": "Templates activos", "color": "primary"}
	except Exception as e:
		frappe.log_error(f"Error calculando addendas activas: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_monthly_invoices_with_addenda(**kwargs):
	"""Facturas con addenda del mes actual"""
	from datetime import date, datetime

	import frappe

	try:
		today = date.today()
		first_day = date(today.year, today.month, 1)

		count = frappe.db.count(
			"Sales Invoice",
			filters={
				"creation": [">=", first_day],
				"docstatus": 1,
				"fm_has_addenda": 1,  # Custom field
			},
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": f"Facturas con addenda {today.strftime('%B')}",
			"color": "success" if count > 0 else "secondary",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando facturas con addenda: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_available_addenda_templates(**kwargs):
	"""Templates de addenda disponibles por tipo"""
	import frappe

	try:
		result = frappe.db.sql(
			"""
            SELECT
                addenda_type,
                COUNT(*) as count
            FROM `tabAddenda Template`
            WHERE is_active = 1
            AND docstatus = 1
            GROUP BY addenda_type
            ORDER BY count DESC
        """,
			as_dict=True,
		)

		total = sum(r.count for r in result)

		# Crear breakdown por tipo
		breakdown = {r.addenda_type: r.count for r in result}

		return {
			"value": total,
			"format": "number",
			"subtitle": "Templates disponibles",
			"color": "info",
			"breakdown": breakdown,
		}
	except Exception as e:
		frappe.log_error(f"Error calculando templates disponibles: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_addenda_application_rate(**kwargs):
	"""Tasa de aplicación correcta de addendas"""
	from datetime import date, timedelta

	import frappe

	try:
		# Últimos 30 días
		thirty_days_ago = date.today() - timedelta(days=30)

		# Total de facturas que deberían tener addenda
		should_have_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as total
            FROM `tabSales Invoice` si
            INNER JOIN `tabCustomer` c ON si.customer = c.name
            WHERE si.creation >= %s
            AND si.docstatus = 1
            AND (c.fm_requires_addenda = 1 OR c.fm_addenda_template IS NOT NULL)
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		# Total que sí tienen addenda aplicada correctamente
		have_addenda_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as total
            FROM `tabSales Invoice` si
            INNER JOIN `tabCustomer` c ON si.customer = c.name
            WHERE si.creation >= %s
            AND si.docstatus = 1
            AND (c.fm_requires_addenda = 1 OR c.fm_addenda_template IS NOT NULL)
            AND si.fm_has_addenda = 1
            AND si.fm_addenda_status = 'Applied'
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		should_have = should_have_result[0].total or 0
		have_addenda = have_addenda_result[0].total or 0

		rate = (have_addenda / should_have * 100) if should_have > 0 else 100

		return {
			"value": round(rate, 1),
			"format": "percentage",
			"subtitle": "Tasa aplicación correcta (30d)",
			"color": "success" if rate >= 95 else ("warning" if rate >= 80 else "danger"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando tasa aplicación: {e!s}")
		return {"value": 0, "format": "percentage", "error": str(e)}


def get_weekly_addenda_errors(**kwargs):
	"""Errores en addendas de la semana"""
	from datetime import date, timedelta

	import frappe

	try:
		week_ago = date.today() - timedelta(days=7)

		count = frappe.db.count(
			"Sales Invoice",
			filters={"creation": [">=", week_ago], "docstatus": 1, "fm_addenda_status": "Error"},
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Errores últimos 7 días",
			"color": "danger" if count > 10 else ("warning" if count > 0 else "success"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando errores semanales: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_customers_requiring_addenda(**kwargs):
	"""Clientes que requieren addenda configurada"""
	import frappe

	try:
		count = frappe.db.count("Customer", filters={"fm_requires_addenda": 1, "disabled": 0})

		return {
			"value": count,
			"format": "number",
			"subtitle": "Clientes con addenda requerida",
			"color": "info",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando clientes con addenda: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


# Alert Functions


def check_outdated_addendas(**kwargs):
	"""Verificar addendas desactualizadas"""
	from datetime import datetime, timedelta

	import frappe

	try:
		# Addendas no modificadas en los últimos 6 meses
		six_months_ago = datetime.now() - timedelta(days=180)

		count = frappe.db.count(
			"Addenda Template", filters={"is_active": 1, "modified": ["<", six_months_ago], "docstatus": 1}
		)

		return {
			"triggered": count > 0,
			"message": f"{count} templates de addenda sin actualizar en 6+ meses",
			"priority": 4,
			"data": {"count": count, "months_old": 6},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando addendas desactualizadas: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_missing_required_addendas(**kwargs):
	"""Verificar facturas sin addenda requerida"""
	from datetime import date, timedelta

	import frappe

	try:
		# Facturas de los últimos 7 días que deberían tener addenda pero no la tienen
		week_ago = date.today() - timedelta(days=7)

		result = frappe.db.sql(
			"""
            SELECT COUNT(*) as missing_count
            FROM `tabSales Invoice` si
            INNER JOIN `tabCustomer` c ON si.customer = c.name
            WHERE si.creation >= %s
            AND si.docstatus = 1
            AND (c.fm_requires_addenda = 1 OR c.fm_addenda_template IS NOT NULL)
            AND (si.fm_has_addenda != 1 OR si.fm_addenda_status != 'Applied')
        """,
			(week_ago,),
			as_dict=True,
		)

		count = result[0].missing_count or 0

		return {
			"triggered": count > 0,
			"message": f"{count} facturas sin addenda requerida en los últimos 7 días",
			"priority": 7 if count > 5 else 5,
			"data": {"count": count, "days_checked": 7},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando addendas faltantes: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_addenda_validation_errors(**kwargs):
	"""Verificar errores de validación en addendas"""
	from datetime import date, timedelta

	import frappe

	try:
		# Errores en las últimas 24 horas
		yesterday = date.today() - timedelta(days=1)

		count = frappe.db.count(
			"Sales Invoice",
			filters={"creation": [">=", yesterday], "docstatus": 1, "fm_addenda_status": "Validation Error"},
		)

		return {
			"triggered": count >= 3,  # 3 o más errores de validación
			"message": f"{count} errores de validación de addenda en las últimas 24 horas",
			"priority": 6,
			"data": {"count": count, "hours_checked": 24},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando errores validación: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_unused_templates(**kwargs):
	"""Verificar templates de addenda no utilizados"""
	from datetime import date, timedelta

	import frappe

	try:
		# Templates activos no utilizados en los últimos 90 días
		ninety_days_ago = date.today() - timedelta(days=90)

		result = frappe.db.sql(
			"""
            SELECT COUNT(*) as unused_count
            FROM `tabAddenda Template` at
            WHERE at.is_active = 1
            AND at.docstatus = 1
            AND at.name NOT IN (
                SELECT DISTINCT c.fm_addenda_template
                FROM `tabCustomer` c
                INNER JOIN `tabSales Invoice` si ON c.name = si.customer
                WHERE si.creation >= %s
                AND si.docstatus = 1
                AND c.fm_addenda_template IS NOT NULL
                AND si.fm_has_addenda = 1
            )
        """,
			(ninety_days_ago,),
			as_dict=True,
		)

		count = result[0].unused_count or 0

		return {
			"triggered": count >= 2,  # 2 o más templates no utilizados
			"message": f"{count} templates de addenda sin uso en los últimos 90 días",
			"priority": 3,  # Baja prioridad
			"data": {"count": count, "days_unused": 90},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando templates no utilizados: {e!s}")
		return {"triggered": False, "error": str(e)}


# Auto-register on import
def setup():
	"""Setup de la integración Addendas"""
	import frappe

	try:
		register_addendas_kpis()
		register_addendas_widgets()
		register_addendas_alerts()
		frappe.logger().info("Addendas integration setup completado")
	except Exception as e:
		frappe.log_error("Error en setup Addendas integration", str(e))
