# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Cumplimiento de Addendas - Sprint 6 Phase 5
Reporte especializado para análisis de cumplimiento de addendas
"""

import frappe
from frappe import _


def execute(filters=None):
	"""Ejecutar reporte de cumplimiento de addendas"""
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data, filters)
	chart = get_chart_data(data)

	return columns, data, None, chart, summary


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"fieldname": "customer",
			"label": _("Cliente"),
			"fieldtype": "Link",
			"options": "Customer",
			"width": 200,
		},
		{
			"fieldname": "customer_name",
			"label": _("Nombre Cliente"),
			"fieldtype": "Data",
			"width": 250,
		},
		{
			"fieldname": "addenda_type",
			"label": _("Tipo Addenda"),
			"fieldtype": "Link",
			"options": "Addenda Type",
			"width": 150,
		},
		{
			"fieldname": "requires_addenda",
			"label": _("Requiere Addenda"),
			"fieldtype": "Check",
			"width": 120,
		},
		{
			"fieldname": "auto_detected",
			"label": _("Auto-detectado"),
			"fieldtype": "Check",
			"width": 120,
		},
		{
			"fieldname": "total_invoices",
			"label": _("Total Facturas"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "invoices_with_addenda",
			"label": _("Con Addenda"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "invoices_without_addenda",
			"label": _("Sin Addenda"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "compliance_percentage",
			"label": _("% Cumplimiento"),
			"fieldtype": "Percent",
			"width": 130,
		},
		{
			"fieldname": "total_amount",
			"label": _("Monto Total"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "amount_with_addenda",
			"label": _("Monto Con Addenda"),
			"fieldtype": "Currency",
			"width": 150,
		},
		{
			"fieldname": "last_invoice_date",
			"label": _("Última Factura"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "status",
			"label": _("Estado"),
			"fieldtype": "Data",
			"width": 100,
		},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	conditions = get_conditions(filters)

	# Query principal para obtener datos de clientes y addendas
	query = f"""
		SELECT
			c.name as customer,
			c.customer_name,
			c.fm_addenda_type as addenda_type,
			c.fm_requires_addenda as requires_addenda,
			c.fm_addenda_auto_detected as auto_detected,
			COUNT(si.name) as total_invoices,
			COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) as invoices_with_addenda,
			COUNT(CASE WHEN si.fm_has_addenda = 0 OR si.fm_has_addenda IS NULL THEN 1 END) as invoices_without_addenda,
			ROUND(
				COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) * 100.0 / COUNT(si.name),
				2
			) as compliance_percentage,
			SUM(si.grand_total) as total_amount,
			SUM(CASE WHEN si.fm_has_addenda = 1 THEN si.grand_total ELSE 0 END) as amount_with_addenda,
			MAX(si.posting_date) as last_invoice_date
		FROM `tabCustomer` c
		LEFT JOIN `tabSales Invoice` si ON si.customer = c.name AND si.docstatus = 1 {conditions}
		WHERE c.disabled = 0
		GROUP BY c.name, c.customer_name, c.fm_addenda_type, c.fm_requires_addenda, c.fm_addenda_auto_detected
		HAVING total_invoices > 0
		ORDER BY compliance_percentage ASC, total_amount DESC
	"""

	data = frappe.db.sql(query, filters, as_dict=True)

	# Determinar estado de cumplimiento
	for row in data:
		row["status"] = get_compliance_status(row)

		# Convertir booleanos a enteros para display
		row["requires_addenda"] = 1 if row["requires_addenda"] else 0
		row["auto_detected"] = 1 if row["auto_detected"] else 0

	return data


def get_conditions(filters):
	"""Construir condiciones WHERE del query"""
	conditions = []

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")

	if filters.get("customer"):
		conditions.append("c.name = %(customer)s")

	if filters.get("addenda_type"):
		conditions.append("c.fm_addenda_type = %(addenda_type)s")

	if filters.get("requires_addenda"):
		conditions.append("c.fm_requires_addenda = 1")

	if filters.get("compliance_status"):
		if filters["compliance_status"] == "Completo":
			conditions.append("COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) = COUNT(si.name)")
		elif filters["compliance_status"] == "Parcial":
			conditions.append("""
				COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) > 0
				AND COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) < COUNT(si.name)
			""")
		elif filters["compliance_status"] == "Sin Cumplir":
			conditions.append("COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) = 0")

	return " AND " + " AND ".join(conditions) if conditions else ""


def get_compliance_status(row):
	"""Determinar estado de cumplimiento"""
	if not row["requires_addenda"]:
		return "No Requerida"

	compliance = row["compliance_percentage"] or 0

	if compliance == 100:
		return "✅ Completo"
	elif compliance >= 80:
		return "🟡 Bueno"
	elif compliance >= 50:
		return "🟠 Parcial"
	elif compliance > 0:
		return "🔴 Bajo"
	else:
		return "❌ Sin Cumplir"


def get_summary(data, filters):
	"""Generar resumen del reporte"""
	if not data:
		return []

	# Filtrar solo clientes que requieren addenda
	requiring_addenda = [row for row in data if row["requires_addenda"]]

	if not requiring_addenda:
		return [{"label": _("No hay clientes que requieran addenda"), "value": "", "indicator": "blue"}]

	# Calcular estadísticas
	total_customers = len(requiring_addenda)
	total_invoices = sum(row["total_invoices"] for row in requiring_addenda)
	total_with_addenda = sum(row["invoices_with_addenda"] for row in requiring_addenda)
	total_without_addenda = sum(row["invoices_without_addenda"] for row in requiring_addenda)

	# Estadísticas de cumplimiento
	full_compliance = len([row for row in requiring_addenda if row["compliance_percentage"] == 100])
	good_compliance = len([row for row in requiring_addenda if 80 <= row["compliance_percentage"] < 100])
	len([row for row in requiring_addenda if 50 <= row["compliance_percentage"] < 80])
	low_compliance = len([row for row in requiring_addenda if 0 < row["compliance_percentage"] < 50])
	no_compliance = len([row for row in requiring_addenda if row["compliance_percentage"] == 0])

	# Auto-detectados
	auto_detected = len([row for row in requiring_addenda if row["auto_detected"]])

	# Promedios
	avg_compliance = sum(row["compliance_percentage"] for row in requiring_addenda) / total_customers

	summary = [
		{"label": _("Clientes Requieren Addenda"), "value": total_customers, "indicator": "blue"},
		{
			"label": _("Cumplimiento Promedio"),
			"value": f"{avg_compliance:.1f}%",
			"indicator": "green" if avg_compliance > 80 else "orange" if avg_compliance > 50 else "red",
		},
		{
			"label": _("Cumplimiento Completo"),
			"value": f"{full_compliance} clientes ({(full_compliance/total_customers*100):.1f}%)",
			"indicator": "green",
		},
		{
			"label": _("Cumplimiento Bueno"),
			"value": f"{good_compliance} clientes ({(good_compliance/total_customers*100):.1f}%)",
			"indicator": "orange",
		},
		{
			"label": _("Cumplimiento Bajo/Nulo"),
			"value": f"{low_compliance + no_compliance} clientes ({((low_compliance + no_compliance)/total_customers*100):.1f}%)",
			"indicator": "red",
		},
		{
			"label": _("Auto-detectados"),
			"value": f"{auto_detected} clientes ({(auto_detected/total_customers*100):.1f}%)",
			"indicator": "blue",
		},
		{
			"label": _("Total Facturas"),
			"value": f"{total_invoices} ({total_with_addenda} con addenda)",
			"indicator": "blue",
		},
		{
			"label": _("Facturas Sin Addenda"),
			"value": f"{total_without_addenda} facturas",
			"indicator": "red" if total_without_addenda > 0 else "green",
		},
	]

	return summary


def get_chart_data(data):
	"""Generar datos para gráfico"""
	if not data:
		return None

	# Filtrar solo clientes que requieren addenda
	requiring_addenda = [row for row in data if row["requires_addenda"]]

	if not requiring_addenda:
		return None

	# Agrupar por estado de cumplimiento
	status_counts = {}
	for row in requiring_addenda:
		status = get_compliance_status(row)
		clean_status = (
			status.replace("✅ ", "")
			.replace("🟡 ", "")
			.replace("🟠 ", "")
			.replace("🔴 ", "")
			.replace("❌ ", "")
		)
		status_counts[clean_status] = status_counts.get(clean_status, 0) + 1

	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [{"name": "Clientes", "values": list(status_counts.values())}],
		},
		"type": "donut",
		"height": 300,
		"colors": ["#28a745", "#ffc107", "#fd7e14", "#dc3545", "#6c757d"],
	}
