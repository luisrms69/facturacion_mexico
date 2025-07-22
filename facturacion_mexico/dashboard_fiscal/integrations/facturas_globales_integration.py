"""
Facturas Globales Integration - Dashboard Fiscal
Integración del módulo de Facturas Globales con el Dashboard
"""

from ..dashboard_registry import DashboardRegistry


def register_facturas_globales_kpis():
	"""Registrar KPIs del módulo Facturas Globales"""
	DashboardRegistry.register_kpi(
		"Facturas Globales",
		{
			"facturas_globales_mes": get_monthly_global_invoices,
			"monto_total_globales": get_global_invoices_amount,
			"ereceipts_consolidados_mes": get_consolidated_ereceipts,
			"tiempo_promedio_consolidacion": get_average_consolidation_time,
			"facturas_globales_pendientes": get_pending_global_invoices,
			"tasa_exito_consolidacion": get_consolidation_success_rate,
		},
	)


def register_facturas_globales_widgets():
	"""Registrar widgets del módulo Facturas Globales"""
	DashboardRegistry.register_widget(
		{
			"code": "facturas_globales_overview",
			"name": "Resumen Facturas Globales",
			"type": "kpi_grid",
			"module": "Facturas Globales",
			"position": {"row": 3, "col": 3, "width": 2, "height": 1},
		}
	)

	DashboardRegistry.register_widget(
		{
			"code": "consolidation_timeline",
			"name": "Timeline Consolidación",
			"type": "timeline",
			"module": "Facturas Globales",
			"position": {"row": 4, "col": 3, "width": 2, "height": 1},
		}
	)


def register_facturas_globales_alerts():
	"""Registrar evaluadores de alertas para Facturas Globales"""
	DashboardRegistry.register_alert_evaluator(
		"Facturas Globales",
		{
			"consolidacion_retrasada": check_delayed_consolidation,
			"limite_mensual_globales": check_monthly_global_limit,
			"errores_consolidacion": check_consolidation_errors,
			"ereceipts_sin_consolidar": check_unconsolidated_ereceipts,
		},
	)


# KPI Functions


def get_monthly_global_invoices(**kwargs):
	"""Facturas globales generadas este mes"""
	from datetime import date

	import frappe

	try:
		today = date.today()
		first_day = date(today.year, today.month, 1)

		count = frappe.db.count("Factura Global MX", filters={"creation": [">=", first_day], "docstatus": 1})

		return {
			"value": count,
			"format": "number",
			"subtitle": f"Facturas globales {today.strftime('%B')}",
			"color": "primary",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando facturas globales del mes: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_global_invoices_amount(**kwargs):
	"""Monto total de facturas globales del mes"""
	from datetime import date

	import frappe

	try:
		today = date.today()
		first_day = date(today.year, today.month, 1)

		result = frappe.db.sql(
			"""
            SELECT COALESCE(SUM(total_amount), 0) as total
            FROM `tabFactura Global MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND billing_status = 'Success'
        """,
			(first_day,),
			as_dict=True,
		)

		total = float(result[0].total or 0)

		return {
			"value": total,
			"format": "currency",
			"subtitle": f"Monto globales {today.strftime('%B')}",
			"color": "success" if total > 0 else "secondary",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando monto globales: {e!s}")
		return {"value": 0, "format": "currency", "error": str(e)}


def get_consolidated_ereceipts(**kwargs):
	"""E-Receipts consolidados en facturas globales este mes"""
	from datetime import date

	import frappe

	try:
		today = date.today()
		first_day = date(today.year, today.month, 1)

		result = frappe.db.sql(
			"""
            SELECT COALESCE(SUM(ereceipts_count), 0) as total
            FROM `tabFactura Global MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND consolidation_status = 'Completed'
        """,
			(first_day,),
			as_dict=True,
		)

		total = int(result[0].total or 0)

		return {"value": total, "format": "number", "subtitle": "E-Receipts consolidados", "color": "info"}
	except Exception as e:
		frappe.log_error(f"Error calculando ereceipts consolidados: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_average_consolidation_time(**kwargs):
	"""Tiempo promedio de consolidación en minutos"""
	from datetime import date, timedelta

	import frappe

	try:
		# Últimos 30 días para obtener promedio representativo
		thirty_days_ago = date.today() - timedelta(days=30)

		result = frappe.db.sql(
			"""
            SELECT AVG(consolidation_time_minutes) as avg_time
            FROM `tabFactura Global MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND consolidation_status = 'Completed'
            AND consolidation_time_minutes IS NOT NULL
            AND consolidation_time_minutes > 0
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		avg_time = round(float(result[0].avg_time or 0), 1)

		return {
			"value": avg_time,
			"format": "number",
			"subtitle": "Min promedio consolidación",
			"color": "success" if avg_time <= 30 else ("warning" if avg_time <= 60 else "danger"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando tiempo promedio: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_pending_global_invoices(**kwargs):
	"""Facturas globales pendientes de procesamiento"""
	import frappe

	try:
		count = frappe.db.count(
			"Factura Global MX",
			filters={"consolidation_status": ["in", ["Pending", "Processing", "Ready"]], "docstatus": 1},
		)

		return {
			"value": count,
			"format": "number",
			"subtitle": "Pendientes procesamiento",
			"color": "warning" if count > 0 else "success",
		}
	except Exception as e:
		frappe.log_error(f"Error calculando globales pendientes: {e!s}")
		return {"value": 0, "format": "number", "error": str(e)}


def get_consolidation_success_rate(**kwargs):
	"""Tasa de éxito en consolidación"""
	from datetime import date, timedelta

	import frappe

	try:
		# Últimos 30 días
		thirty_days_ago = date.today() - timedelta(days=30)

		total_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as total
            FROM `tabFactura Global MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND consolidation_status IN ('Completed', 'Error', 'Failed')
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		successful_result = frappe.db.sql(
			"""
            SELECT COUNT(*) as successful
            FROM `tabFactura Global MX`
            WHERE creation >= %s
            AND docstatus = 1
            AND consolidation_status = 'Completed'
            AND billing_status = 'Success'
        """,
			(thirty_days_ago,),
			as_dict=True,
		)

		total = total_result[0].total or 0
		successful = successful_result[0].successful or 0

		rate = (successful / total * 100) if total > 0 else 100

		return {
			"value": round(rate, 1),
			"format": "percentage",
			"subtitle": "Tasa éxito consolidación (30d)",
			"color": "success" if rate >= 95 else ("warning" if rate >= 85 else "danger"),
		}
	except Exception as e:
		frappe.log_error(f"Error calculando tasa éxito: {e!s}")
		return {"value": 0, "format": "percentage", "error": str(e)}


# Alert Functions


def check_delayed_consolidation(**kwargs):
	"""Verificar consolidaciones retrasadas"""
	from datetime import datetime, timedelta

	import frappe

	try:
		# Facturas globales en procesamiento por más de 2 horas
		two_hours_ago = datetime.now() - timedelta(hours=2)

		count = frappe.db.count(
			"Factura Global MX",
			filters={
				"creation": ["<=", two_hours_ago],
				"consolidation_status": ["in", ["Pending", "Processing"]],
				"docstatus": 1,
			},
		)

		return {
			"triggered": count > 0,
			"message": f"{count} facturas globales con consolidación retrasada (>2h)",
			"priority": 8,
			"data": {"count": count, "threshold_hours": 2},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando consolidación retrasada: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_monthly_global_limit(**kwargs):
	"""Verificar límite mensual de facturas globales"""
	from datetime import date

	import frappe

	try:
		# Límite recomendado SAT: 500 facturas globales por mes
		monthly_limit = (
			frappe.db.get_single_value("Facturacion Mexico Settings", "global_invoice_monthly_limit") or 500
		)

		today = date.today()
		first_day = date(today.year, today.month, 1)

		count = frappe.db.count("Factura Global MX", filters={"creation": [">=", first_day], "docstatus": 1})

		percentage_used = (count / monthly_limit * 100) if monthly_limit > 0 else 0

		return {
			"triggered": percentage_used >= 80,  # Alerta al 80%
			"message": f"Uso mensual facturas globales: {count}/{monthly_limit} ({percentage_used:.1f}%)",
			"priority": 6 if percentage_used >= 90 else 4,
			"data": {"count": count, "limit": monthly_limit, "percentage": percentage_used},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando límite mensual: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_consolidation_errors(**kwargs):
	"""Verificar errores en consolidación"""
	from datetime import datetime, timedelta

	import frappe

	try:
		# Errores en las últimas 6 horas
		six_hours_ago = datetime.now() - timedelta(hours=6)

		count = frappe.db.count(
			"Factura Global MX",
			filters={
				"creation": [">=", six_hours_ago],
				"consolidation_status": ["in", ["Error", "Failed"]],
				"docstatus": 1,
			},
		)

		return {
			"triggered": count >= 2,  # 2 o más errores en 6 horas
			"message": f"{count} errores de consolidación en las últimas 6 horas",
			"priority": 7,
			"data": {"count": count, "hours_checked": 6},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando errores consolidación: {e!s}")
		return {"triggered": False, "error": str(e)}


def check_unconsolidated_ereceipts(**kwargs):
	"""Verificar E-Receipts sin consolidar antiguos"""
	from datetime import date, timedelta

	import frappe

	try:
		# E-Receipts de más de 7 días sin consolidar
		week_ago = date.today() - timedelta(days=7)

		result = frappe.db.sql(
			"""
            SELECT COUNT(*) as unconsolidated
            FROM `tabEReceipt MX` er
            WHERE er.creation <= %s
            AND er.docstatus = 1
            AND er.status = 'Completed'
            AND (er.fm_included_in_global != 1 OR er.fm_global_invoice IS NULL)
            AND NOT EXISTS (
                SELECT 1 FROM `tabFactura Global MX` fg
                WHERE fg.period_start <= DATE(er.creation)
                AND fg.period_end >= DATE(er.creation)
                AND fg.consolidation_status = 'Completed'
            )
        """,
			(week_ago,),
			as_dict=True,
		)

		count = result[0].unconsolidated or 0

		return {
			"triggered": count >= 20,  # 20 o más e-receipts antiguos sin consolidar
			"message": f"{count} e-receipts de más de 7 días sin consolidar",
			"priority": 5,
			"data": {"count": count, "days_old": 7},
		}
	except Exception as e:
		frappe.log_error(f"Error verificando ereceipts sin consolidar: {e!s}")
		return {"triggered": False, "error": str(e)}


# Auto-register on import
def setup():
	"""Setup de la integración Facturas Globales"""
	import frappe

	try:
		register_facturas_globales_kpis()
		register_facturas_globales_widgets()
		register_facturas_globales_alerts()
		frappe.logger().info("Facturas Globales integration setup completado")
	except Exception as e:
		frappe.log_error("Error en setup Facturas Globales integration", str(e))
