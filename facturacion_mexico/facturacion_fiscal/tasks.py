"""
Tareas programadas para Facturación Fiscal México
"""

import frappe
from frappe.utils import add_days, today


def cleanup_old_fiscal_events():
	"""Limpiar eventos fiscales antiguos - scheduled task."""
	try:
		frappe.logger().info("Ejecutando limpieza de eventos fiscales antiguos...")

		# TODO: Implementar lógica real cuando esté disponible
		# Por ejemplo: eliminar eventos fiscales de más de 30 días
		cutoff_date = add_days(today(), -30)

		frappe.logger().info(f"Limpieza configurada para eventos anteriores a: {cutoff_date}")

		return {"status": "success", "message": "Limpieza completada (placeholder)"}

	except Exception as e:
		frappe.log_error(f"Error en limpieza de eventos fiscales: {e}")
		return {"status": "error", "message": str(e)}
