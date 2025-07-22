# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""
	Reporte de Facturas Sin Timbrar
	Listado de Sales Invoices submitted sin UUID del SAT
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"label": _("Factura"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Sales Invoice",
			"width": 140,
		},
		{"label": _("Fecha"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Cliente"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 200,
		},
		{"label": _("Nombre Cliente"), "fieldname": "customer_name", "fieldtype": "Data", "width": 180},
		{"label": _("Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("Días Sin Timbrar"), "fieldname": "days_pending", "fieldtype": "Int", "width": 120},
		{"label": _("Estado Timbrado"), "fieldname": "fm_cfdi_uuid", "fieldtype": "Data", "width": 150},
		{"label": _("Error Timbrado"), "fieldname": "fm_timbrado_error", "fieldtype": "Text", "width": 200},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120,
		},
		{"label": _("Prioridad"), "fieldname": "priority", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	if not filters:
		filters = {}

	# Aplicar filtros por defecto
	where_conditions = get_where_conditions(filters)

	# Query principal
	query = f"""
        SELECT
            si.name,
            si.posting_date,
            si.customer,
            si.customer_name,
            si.grand_total,
            si.company,
            si.fm_cfdi_uuid,
            si.fm_timbrado_error,
            si.fm_timbrado_status,
            DATEDIFF(CURDATE(), si.posting_date) as days_pending
        FROM `tabSales Invoice` si
        WHERE si.docstatus = 1
        AND (si.fm_cfdi_uuid IS NULL OR si.fm_cfdi_uuid = '')
        AND (si.fm_timbrado_status != 'Timbrada' OR si.fm_timbrado_status IS NULL)
        {where_conditions}
        ORDER BY si.posting_date DESC, si.grand_total DESC
    """

	data = frappe.db.sql(query, filters, as_dict=True)

	# Agregar campos calculados
	for row in data:
		# Determinar prioridad basada en días y monto
		row["priority"] = get_priority(row["days_pending"], row["grand_total"])

		# Formatear estado de timbrado
		if not row["fm_cfdi_uuid"]:
			row["fm_cfdi_uuid"] = "Sin Timbrar"

	return data


def get_where_conditions(filters):
	"""Construir condiciones WHERE basadas en filtros"""
	conditions = []

	if filters.get("company"):
		conditions.append("AND si.company = %(company)s")

	if filters.get("customer"):
		conditions.append("AND si.customer = %(customer)s")

	if filters.get("from_date"):
		conditions.append("AND si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("AND si.posting_date <= %(to_date)s")

	if filters.get("min_amount"):
		conditions.append("AND si.grand_total >= %(min_amount)s")

	if filters.get("days_pending"):
		conditions.append("AND DATEDIFF(CURDATE(), si.posting_date) >= %(days_pending)s")

	return " ".join(conditions)


def get_priority(days_pending, grand_total):
	"""Determinar prioridad de timbrado basada en días y monto"""
	# Facturas de más de 3 días son críticas
	if days_pending > 3:
		if grand_total > 10000:
			return "CRÍTICA"
		else:
			return "ALTA"

	# Facturas de 1-3 días
	elif days_pending > 1:
		if grand_total > 50000:
			return "CRÍTICA"
		elif grand_total > 10000:
			return "ALTA"
		else:
			return "MEDIA"

	# Facturas del día actual o de ayer
	else:
		if grand_total > 100000:
			return "ALTA"
		else:
			return "NORMAL"


def get_chart_data(data, filters):
	"""Datos para gráfico del reporte"""
	if not data:
		return None

	# Agrupar por prioridad
	priority_counts = {}
	priority_amounts = {}

	for row in data:
		priority = row["priority"]
		priority_counts[priority] = priority_counts.get(priority, 0) + 1
		priority_amounts[priority] = priority_amounts.get(priority, 0) + (row["grand_total"] or 0)

	return {
		"data": {
			"labels": list(priority_counts.keys()),
			"datasets": [{"name": "Cantidad de Facturas", "values": list(priority_counts.values())}],
		},
		"type": "donut",
		"height": 300,
		"colors": ["#ff6b6b", "#ffa726", "#ffd54f", "#66bb6a"],
	}


def get_summary_data(data):
	"""Datos de resumen para el reporte"""
	if not data:
		return []

	total_invoices = len(data)
	total_amount = sum(row["grand_total"] or 0 for row in data)
	avg_days_pending = (
		sum(row["days_pending"] or 0 for row in data) / total_invoices if total_invoices > 0 else 0
	)

	# Contar por prioridad
	critical_count = sum(1 for row in data if row["priority"] == "CRÍTICA")
	high_count = sum(1 for row in data if row["priority"] == "ALTA")

	return [
		{
			"label": _("Total de Facturas Sin Timbrar"),
			"value": total_invoices,
			"indicator": "Red" if critical_count > 0 else "Orange",
		},
		{
			"label": _("Monto Total Pendiente"),
			"value": f"${total_amount:,.2f}",
			"indicator": "Red" if total_amount > 1000000 else "Orange",
		},
		{
			"label": _("Promedio Días Pendientes"),
			"value": f"{avg_days_pending:.1f} días",
			"indicator": "Red" if avg_days_pending > 3 else "Orange",
		},
		{
			"label": _("Facturas Críticas"),
			"value": critical_count,
			"indicator": "Red" if critical_count > 0 else "Green",
		},
		{
			"label": _("Facturas Alta Prioridad"),
			"value": high_count,
			"indicator": "Orange" if high_count > 0 else "Green",
		},
	]


# Filtros del reporte
def get_filters():
	"""Definir filtros disponibles para el reporte"""
	return [
		{
			"fieldname": "company",
			"label": _("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
		},
		{
			"fieldname": "from_date",
			"label": _("Desde Fecha"),
			"fieldtype": "Date",
			"default": (date.today() - timedelta(days=30)).strftime("%Y-%m-%d"),
		},
		{
			"fieldname": "to_date",
			"label": _("Hasta Fecha"),
			"fieldtype": "Date",
			"default": date.today().strftime("%Y-%m-%d"),
		},
		{"fieldname": "customer", "label": _("Cliente"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "min_amount", "label": _("Monto Mínimo"), "fieldtype": "Currency", "default": 0},
		{"fieldname": "days_pending", "label": _("Mínimo Días Pendientes"), "fieldtype": "Int", "default": 0},
	]
