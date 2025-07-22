"""
E-Receipts Integration - Dashboard Fiscal
Integración del módulo de E-Receipts con el Dashboard
"""

from ..dashboard_registry import DashboardRegistry


def register_ereceipts_kpis():
	"""Registrar KPIs del módulo E-Receipts"""
	DashboardRegistry.register_kpi(
		"E-Receipts",
		{
			"ereceipts_generados_hoy": get_ereceipts_today,
			"ereceipts_pendientes_procesamiento": get_pending_ereceipts,
			"monto_total_ereceipts_mes": get_monthly_ereceipts_amount,
			"tasa_autofacturacion": get_auto_billing_rate,
			"errores_ereceipts_semana": get_weekly_ereceipt_errors,
			"clientes_activos_ereceipts": get_active_ereceipt_customers,
		},
	)


def register_ereceipts_widgets():
	"""Registrar widgets del módulo E-Receipts"""
	DashboardRegistry.register_widget(
		{
			"code": "ereceipts_overview",
			"name": "Resumen E-Receipts",
			"type": "kpi_grid",
			"module": "E-Receipts",
			"position": {"row": 2, "col": 3, "width": 2, "height": 1},
		}
	)

	DashboardRegistry.register_widget(
		{
			"code": "ereceipts_monthly_chart",
			"name": "E-Receipts Mensuales",
			"type": "line_chart",
			"module": "E-Receipts",
			"position": {"row": 3, "col": 3, "width": 2, "height": 1},
		}
	)


def register_ereceipts_alerts():
	"""Registrar evaluadores de alertas para E-Receipts"""
	DashboardRegistry.register_alert_evaluator(
		"E-Receipts",
		{
			"ereceipts_sin_procesar_24h": check_unprocessed_ereceipts,
			"errores_autofacturacion": check_auto_billing_errors,
			"limite_mensual_ereceipts": check_monthly_limit,
			"clientes_inactivos": check_inactive_customers,
		},
	)


# KPI Functions


def get_ereceipts_today(**kwargs):
	"""E-Receipts generados hoy"""
	from datetime import date

	import frappe

	try:
		count = frappe.db.count("EReceipt MX", filters={"creation": [">=", date.today()], "docstatus": 1})

		return {
			"value": count,
			"format": "number",
			"subtitle": "E-Receipts generados hoy",
			"color": "success" if count > 0 else "secondary",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando ereceipts hoy: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_pending_ereceipts(**kwargs):
	"""E-Receipts pendientes de procesamiento"""
	import frappe

	try:
		count = frappe.db.count("EReceipt MX", filters={"status": "Pending", "docstatus": 1})

		return {
			"value": count,
			"format": "number",
			"subtitle": "Pendientes procesamiento",
			"color": "warning" if count > 0 else "success",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando ereceipts pendientes: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_monthly_ereceipts_amount(**kwargs):
	"""Monto total de E-Receipts del mes"""
	from datetime import date, datetime

	import frappe

	try:
		# Obtener primer día del mes actual
		today = date.today()
		first_day = date(today.year, today.month, 1)

		result = frappe.db.sql(
			"""
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM `tabEReceipt MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND status = 'Completed'
        """,
			(first_day,),
			as_dict=True,
		)

		total = float(result[0].total or 0)

		return {
			"value": total,
			"format": "currency",
			"subtitle": f"Monto e-receipts {today.strftime('%B')}",
			"color": "primary",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando monto mensual ereceipts: {e!s}")
		return {"value": 0, "format": "currency", "error": str(e)}


def get_auto_billing_rate(**kwargs):
	"""Tasa de autofacturación exitosa"""
	from datetime import date, timedelta

	import frappe

	try:
		# Últimos 30 días
		thirty_days_ago = date.today() - timedelta(days=30)

		total_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as total
            FROM `tabEReceipt MX`
            WHERE creation >= %s
            AND docstatus = 1
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		successful_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as successful
            FROM `tabEReceipt MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND status = 'Completed'
            AND billing_status = 'Success'
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		total = total_result[0].total or 0
		successful = successful_result[0].successful or 0

		rate = (successful / total * 100) if total > 0 else 0

		return {
			"value": round(rate, 1),
			"format": "percentage",
			"subtitle": "Tasa autofacturación (30d)",
			"color": "success" if rate >= 95 else ("warning" if rate >= 80 else "danger"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando tasa autofacturación: {e!s}")
		return {"value": 0, "format": "percentage", "error": str(e)}


def get_weekly_ereceipt_errors(**kwargs):
	"""Errores en E-Receipts de la semana"""
	from datetime import date, timedelta

	import frappe

	try:
		week_ago = date.today() - timedelta(days=7)

		count = frappe.db.count(
			"EReceipt MX", filters={"creation": [">=", week_ago], "status": "Error", "docstatus": 1}
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Errores últimos 7 días",
			"color": "danger" if count > 5 else ("warning" if count > 0 else "success"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando errores semanales: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_active_ereceipt_customers(**kwargs):
	"""Clientes activos con E-Receipts"""
	from datetime import date, timedelta

	import frappe

	try:
		thirty_days_ago = date.today() - timedelta(days=30)

		result = frappe.db.sql(
			"""
            SELECT COUNT(DISTINCT customer) as active_customers
            FROM `tabEReceipt MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND status = 'Completed'
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		count = result[0].active_customers or 0

		return {"value": count, "format": "number", "subtitle": "Clientes activos (30d)", "color": "info"}
	except Exception as e:
		frappe.log_error(f"Error calculando clientes activos: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


# Alert Functions


def check_unprocessed_ereceipts(**kwargs):
	"""Verificar E-Receipts sin procesar por más de 24h"""
	from datetime import datetime, timedelta

	import frappe

	try:
		yesterday = datetime.now() - timedelta(hours=24)

		count = frappe.db.count(
			"EReceipt MX", filters={"creation": ["<=", yesterday], "status": "Pending", "docstatus": 1}
		)

		return {
			"triggered": count > 0,
			"message": f"{count} e-receipts sin procesar por más de 24 horas",
			"priority": 8 if count > 10 else 6,
			"data": {"count": count, "threshold_hours": 24},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando ereceipts sin procesar: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_auto_billing_errors(**kwargs):
	"""Verificar errores recurrentes en autofacturación"""
	from datetime import datetime, timedelta

	import frappe

	try:
		# Errores en las últimas 4 horas
		four_hours_ago = datetime.now() - timedelta(hours=4)

		count = frappe.db.count(
			"EReceipt MX",
			filters={"creation": [">=", four_hours_ago], "billing_status": "Error", "docstatus": 1},
		)

		return {
			"triggered": count >= 5,  # 5 o más errores en 4 horas
			"message": f"{count} errores de autofacturación en las últimas 4 horas",
			"priority": 7,
			"data": {"count": count, "threshold_hours": 4, "threshold_errors": 5},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando errores autofacturación: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_monthly_limit(**kwargs):
	"""Verificar límite mensual de E-Receipts"""
	from datetime import date

	import frappe

	try:
		# Obtener límite de configuración (default: 1000)
		monthly_limit = (
			frappe.db.get_single_value("Facturacion Mexico Settings", "ereceipt_monthly_limit") or 1000
		)

		today = date.today()
		first_day = date(today.year, today.month, 1)

		count = frappe.db.count("EReceipt MX", filters={"creation": [">=", first_day], "docstatus": 1})

		percentage_used = (count / monthly_limit * 100) if monthly_limit > 0 else 0

		return {
			"triggered": percentage_used >= 80,  # Alerta al 80% del límite
			"message": f"Uso mensual e-receipts: {count}/{monthly_limit} ({percentage_used:.1f}%)",
			"priority": 5 if percentage_used >= 90 else 4,
			"data": {"count": count, "limit": monthly_limit, "percentage": percentage_used},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando límite mensual: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_inactive_customers(**kwargs):
	"""Verificar clientes inactivos con E-Receipts configurados"""
	from datetime import date, timedelta

	import frappe

	try:
		# Clientes sin e-receipts en los últimos 30 días pero que tenían actividad previa
		thirty_days_ago = date.today() - timedelta(days=30)
		sixty_days_ago = date.today() - timedelta(days=60)

		result = frappe.db.sql(
			"""
            SELECT COUNT(DISTINCT er1.customer) as inactive_count
            FROM `tabEReceipt MX` er1
            WHERE er1.creation BETWEEN %s AND %s
            AND er1.docstatus = 1
            AND er1.customer NOT IN (
                SELECT DISTINCT er2.customer
                FROM `tabEReceipt MX` er2
                WHERE er2.creation >= %s
                AND er2.docstatus = 1
            )
        """,
			(sixty_days_ago, thirty_days_ago, thirty_days_ago),
			as_dict=True,
		)

		count = result[0].inactive_count or 0

		return {
			"triggered": count >= 5,  # 5 o más clientes inactivos
			"message": f"{count} clientes con e-receipts inactivos por más de 30 días",
			"priority": 3,
			"data": {"count": count, "days_inactive": 30},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando clientes inactivos: {e!s}")
		return {"triggered": False, "error": str(e)}


# Auto-register on import
def setup():
	"""Setup de la integración E-Receipts"""
	import frappe

	try:
		register_ereceipts_kpis()
		register_ereceipts_widgets()
		register_ereceipts_alerts()
		frappe.logger().info("E-Receipts integration setup completado")
	except Exception as e:
		frappe.log_error("Error en setup E-Receipts integration", str(e))
