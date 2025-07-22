# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import date, datetime, timedelta

import frappe
from frappe import _


def execute(filters=None):
	"""
	Reporte de Complementos de Pago Pendientes
	Payment Entries sin complemento PPD generado
	"""
	columns = get_columns()
	data = get_data(filters)

	return columns, data


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"label": _("Payment Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "Payment Entry",
			"width": 140,
		},
		{"label": _("Fecha Pago"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("Cliente"),
			"fieldname": "party",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 180,
		},
		{"label": _("Nombre Cliente"), "fieldname": "party_name", "fieldtype": "Data", "width": 180},
		{"label": _("Monto Pago"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Días Transcurridos"), "fieldname": "days_elapsed", "fieldtype": "Int", "width": 120},
		{"label": _("Estado PPD"), "fieldname": "fm_ppd_status", "fieldtype": "Data", "width": 120},
		{
			"label": _("Complemento UUID"),
			"fieldname": "fm_complemento_uuid",
			"fieldtype": "Data",
			"width": 160,
		},
		{
			"label": _("Facturas Relacionadas"),
			"fieldname": "related_invoices",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": _("Company"),
			"fieldname": "company",
			"fieldtype": "Link",
			"options": "Company",
			"width": 120,
		},
		{"label": _("Urgencia"), "fieldname": "urgency", "fieldtype": "Data", "width": 100},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	if not filters:
		filters = {}

	# Aplicar filtros por defecto
	where_conditions = get_where_conditions(filters)

	# Query principal para Payment Entries sin complemento
	query = f"""
        SELECT
            pe.name,
            pe.posting_date,
            pe.party,
            pe.party_name,
            pe.paid_amount,
            pe.company,
            pe.fm_ppd_status,
            pe.fm_complemento_uuid,
            pe.fm_payment_method,
            pe.fm_payment_type,
            DATEDIFF(CURDATE(), pe.posting_date) as days_elapsed
        FROM `tabPayment Entry` pe
        WHERE pe.docstatus = 1
        AND pe.payment_type = 'Receive'
        AND pe.party_type = 'Customer'
        AND (pe.fm_complemento_uuid IS NULL OR pe.fm_complemento_uuid = '')
        AND (pe.fm_ppd_status != 'Completed' OR pe.fm_ppd_status IS NULL)
        {where_conditions}
        ORDER BY pe.posting_date ASC, pe.paid_amount DESC
    """

	data = frappe.db.sql(query, filters, as_dict=True)

	# Enriquecer datos con información adicional
	for row in data:
		# Obtener facturas relacionadas
		row["related_invoices"] = get_related_invoices(row["name"])

		# Determinar urgencia
		row["urgency"] = get_urgency_level(row["days_elapsed"], row["paid_amount"])

		# Formatear estado PPD
		if not row["fm_ppd_status"]:
			row["fm_ppd_status"] = "Pendiente"

		if not row["fm_complemento_uuid"]:
			row["fm_complemento_uuid"] = "Sin Generar"

	return data


def get_where_conditions(filters):
	"""Construir condiciones WHERE basadas en filtros"""
	conditions = []

	if filters.get("company"):
		conditions.append("AND pe.company = %(company)s")

	if filters.get("customer"):
		conditions.append("AND pe.party = %(customer)s")

	if filters.get("from_date"):
		conditions.append("AND pe.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("AND pe.posting_date <= %(to_date)s")

	if filters.get("min_amount"):
		conditions.append("AND pe.paid_amount >= %(min_amount)s")

	if filters.get("min_days"):
		conditions.append("AND DATEDIFF(CURDATE(), pe.posting_date) >= %(min_days)s")

	if filters.get("payment_method"):
		conditions.append("AND pe.fm_payment_method = %(payment_method)s")

	return " ".join(conditions)


def get_related_invoices(payment_entry):
	"""Obtener facturas relacionadas al Payment Entry"""
	try:
		invoices = frappe.db.sql(
			"""
            SELECT DISTINCT per.reference_name
            FROM `tabPayment Entry Reference` per
            WHERE per.parent = %s
            AND per.reference_doctype = 'Sales Invoice'
            ORDER BY per.reference_name
        """,
			payment_entry,
			as_dict=True,
		)

		invoice_names = [inv.reference_name for inv in invoices]
		return ", ".join(invoice_names[:3])  # Mostrar máximo 3 facturas

	except Exception:
		return "N/A"


def get_urgency_level(days_elapsed, paid_amount):
	"""Determinar nivel de urgencia basado en días y monto"""
	# Reglas de urgencia SAT: complementos deben emitirse dentro de ciertos plazos
	if days_elapsed > 30:  # Más de 30 días = crítico
		return "CRÍTICA"
	elif days_elapsed > 15:  # 15-30 días
		if paid_amount > 50000:
			return "CRÍTICA"
		else:
			return "ALTA"
	elif days_elapsed > 7:  # 7-15 días
		if paid_amount > 100000:
			return "CRÍTICA"
		elif paid_amount > 20000:
			return "ALTA"
		else:
			return "MEDIA"
	else:  # 0-7 días
		if paid_amount > 200000:
			return "ALTA"
		else:
			return "NORMAL"


def get_chart_data(data, filters):
	"""Datos para gráfico del reporte"""
	if not data:
		return None

	# Agrupar por urgencia
	urgency_counts = {}
	urgency_amounts = {}

	for row in data:
		urgency = row["urgency"]
		urgency_counts[urgency] = urgency_counts.get(urgency, 0) + 1
		urgency_amounts[urgency] = urgency_amounts.get(urgency, 0) + (row["paid_amount"] or 0)

	# Gráfico de distribución por urgencia
	return {
		"data": {
			"labels": list(urgency_counts.keys()),
			"datasets": [
				{"name": "Cantidad de Pagos", "values": list(urgency_counts.values())},
				{"name": "Monto (Miles)", "values": [v / 1000 for v in urgency_amounts.values()]},
			],
		},
		"type": "bar",
		"height": 300,
		"colors": ["#ff6b6b", "#ffa726", "#ffd54f", "#66bb6a"],
	}


def get_summary_data(data):
	"""Datos de resumen para el reporte"""
	if not data:
		return []

	total_payments = len(data)
	total_amount = sum(row["paid_amount"] or 0 for row in data)
	avg_days_elapsed = (
		sum(row["days_elapsed"] or 0 for row in data) / total_payments if total_payments > 0 else 0
	)

	# Contar por urgencia
	critical_count = sum(1 for row in data if row["urgency"] == "CRÍTICA")
	sum(1 for row in data if row["urgency"] == "ALTA")

	# Pagos con más de 30 días (violación SAT)
	overdue_count = sum(1 for row in data if row["days_elapsed"] > 30)

	return [
		{
			"label": _("Total Pagos Sin Complemento"),
			"value": total_payments,
			"indicator": "Red" if critical_count > 0 else "Orange",
		},
		{
			"label": _("Monto Total Pendiente"),
			"value": f"${total_amount:,.2f}",
			"indicator": "Red" if total_amount > 2000000 else "Orange",
		},
		{
			"label": _("Promedio Días Transcurridos"),
			"value": f"{avg_days_elapsed:.1f} días",
			"indicator": "Red" if avg_days_elapsed > 15 else "Orange",
		},
		{
			"label": _("Pagos Críticos"),
			"value": critical_count,
			"indicator": "Red" if critical_count > 0 else "Green",
		},
		{
			"label": _("Pagos Vencidos (>30d)"),
			"value": overdue_count,
			"indicator": "Red" if overdue_count > 0 else "Green",
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
			"default": (date.today() - timedelta(days=60)).strftime("%Y-%m-%d"),
		},
		{
			"fieldname": "to_date",
			"label": _("Hasta Fecha"),
			"fieldtype": "Date",
			"default": date.today().strftime("%Y-%m-%d"),
		},
		{"fieldname": "customer", "label": _("Cliente"), "fieldtype": "Link", "options": "Customer"},
		{"fieldname": "min_amount", "label": _("Monto Mínimo"), "fieldtype": "Currency", "default": 0},
		{"fieldname": "min_days", "label": _("Mínimo Días Transcurridos"), "fieldtype": "Int", "default": 0},
		{
			"fieldname": "payment_method",
			"label": _("Método de Pago"),
			"fieldtype": "Select",
			"options": "\nPPD\nPUE\nTransferencia\nEfectivo\nCheque",
		},
	]
