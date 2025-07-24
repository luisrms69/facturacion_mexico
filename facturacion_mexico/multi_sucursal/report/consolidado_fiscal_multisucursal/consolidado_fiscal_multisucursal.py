# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Consolidado Fiscal Multi-Sucursal - Sprint 6 Phase 5
Reporte especializado para análisis fiscal consolidado por sucursales
"""

import frappe
from frappe import _


def execute(filters=None):
	"""Ejecutar reporte consolidado fiscal multi-sucursal"""
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data, filters)

	return columns, data, None, None, summary


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"fieldname": "branch",
			"label": _("Sucursal"),
			"fieldtype": "Link",
			"options": "Branch",
			"width": 150,
		},
		{
			"fieldname": "branch_name",
			"label": _("Nombre Sucursal"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "total_invoices",
			"label": _("Total Facturas"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "stamped_invoices",
			"label": _("Facturas Timbradas"),
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"fieldname": "pending_invoices",
			"label": _("Pendientes Timbrar"),
			"fieldtype": "Int",
			"width": 140,
		},
		{
			"fieldname": "stamping_percentage",
			"label": _("% Timbrado"),
			"fieldtype": "Percent",
			"width": 120,
		},
		{
			"fieldname": "total_amount",
			"label": _("Monto Total"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "stamped_amount",
			"label": _("Monto Timbrado"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "addenda_invoices",
			"label": _("Con Addenda"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "error_count",
			"label": _("Errores"),
			"fieldtype": "Int",
			"width": 100,
		},
		{
			"fieldname": "avg_stamping_time",
			"label": _("Tiempo Prom. (min)"),
			"fieldtype": "Float",
			"precision": 2,
			"width": 140,
		},
		{
			"fieldname": "folio_usage",
			"label": _("Uso Folios"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "certificate_status",
			"label": _("Estado Certificado"),
			"fieldtype": "Data",
			"width": 140,
		},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	conditions = get_conditions(filters)

	query = f"""
		SELECT
			si.fm_branch as branch,
			b.branch_name,
			COUNT(si.name) as total_invoices,
			COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) as stamped_invoices,
			COUNT(CASE WHEN si.fm_cfdi_xml IS NULL THEN 1 END) as pending_invoices,
			ROUND(
				COUNT(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN 1 END) * 100.0 / COUNT(si.name),
				2
			) as stamping_percentage,
			SUM(si.grand_total) as total_amount,
			SUM(CASE WHEN si.fm_cfdi_xml IS NOT NULL THEN si.grand_total ELSE 0 END) as stamped_amount,
			COUNT(CASE WHEN si.fm_has_addenda = 1 THEN 1 END) as addenda_invoices,
			COUNT(CASE WHEN si.fm_cfdi_error IS NOT NULL THEN 1 END) as error_count,
			ROUND(
				AVG(CASE WHEN si.fm_cfdi_xml IS NOT NULL
					THEN TIMESTAMPDIFF(MINUTE, si.creation, si.modified) END),
				2
			) as avg_stamping_time
		FROM `tabSales Invoice` si
		LEFT JOIN `tabBranch` b ON b.name = si.fm_branch
		WHERE si.docstatus = 1 {conditions}
		GROUP BY si.fm_branch, b.branch_name
		ORDER BY total_amount DESC
	"""

	# REGLA #35: Defensive SQL execution
	try:
		data = frappe.db.sql(query, filters, as_dict=True)
	except Exception as e:
		frappe.log_error(f"Error executing consolidado fiscal query: {e}", "Consolidado Fiscal Report")
		data = []

	# Enriquecer datos con información adicional
	for row in data:
		# Información de folios
		row["folio_usage"] = get_folio_usage(row["branch"])

		# Estado del certificado
		row["certificate_status"] = get_certificate_status(row["branch"])

		# Manejar sucursal sin definir
		if not row["branch"]:
			row["branch"] = "Sin Sucursal"
			row["branch_name"] = "Sin Sucursal Definida"

	return data


def get_conditions(filters):
	"""Construir condiciones WHERE del query"""
	conditions = []

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")

	if filters.get("branch"):
		conditions.append("si.fm_branch = %(branch)s")

	if filters.get("company"):
		conditions.append("si.company = %(company)s")

	if filters.get("customer"):
		conditions.append("si.customer = %(customer)s")

	if filters.get("only_stamped"):
		conditions.append("si.fm_cfdi_xml IS NOT NULL")

	if filters.get("only_pending"):
		conditions.append("si.fm_cfdi_xml IS NULL")

	return " AND " + " AND ".join(conditions) if conditions else ""


def get_folio_usage(branch):
	"""Obtener información de uso de folios"""
	if not branch or branch == "Sin Sucursal":
		return "N/A"

	try:
		folio_info = frappe.db.sql(
			"""
			SELECT
				folio_current,
				folio_end,
				(folio_end - folio_current) as available
			FROM `tabConfiguracion Fiscal Sucursal`
			WHERE parent = %s AND parenttype = 'Branch' AND is_active = 1
			ORDER BY creation DESC
			LIMIT 1
		""",
			branch,
			as_dict=True,
		)

		if folio_info:
			info = folio_info[0]
			used_percentage = (
				((info["folio_current"] / info["folio_end"]) * 100) if info["folio_end"] > 0 else 0
			)
			return f"{info['available']} disp. ({used_percentage:.1f}% usado)"

		return "Sin configurar"

	except Exception:
		return "Error"


def get_certificate_status(branch):
	"""Obtener estado del certificado"""
	if not branch or branch == "Sin Sucursal":
		return "N/A"

	try:
		cert_info = frappe.db.sql(
			"""
			SELECT
				certificate_expiry_date,
				DATEDIFF(certificate_expiry_date, CURDATE()) as days_to_expiry
			FROM `tabConfiguracion Fiscal Sucursal`
			WHERE parent = %s AND parenttype = 'Branch' AND is_active = 1
			ORDER BY creation DESC
			LIMIT 1
		""",
			branch,
			as_dict=True,
		)

		if cert_info:
			info = cert_info[0]
			days = info["days_to_expiry"]

			if days < 0:
				return "⚠️ Vencido"
			elif days <= 7:
				return f"🔴 Vence en {days} días"
			elif days <= 30:
				return f"🟡 Vence en {days} días"
			else:
				return f"✅ Válido ({days} días)"

		return "Sin certificado"

	except Exception:
		return "Error"


def get_summary(data, filters):
	"""Generar resumen del reporte"""
	if not data:
		return []

	# Calcular totales
	total_invoices = sum(row["total_invoices"] for row in data)
	total_stamped = sum(row["stamped_invoices"] for row in data)
	total_pending = sum(row["pending_invoices"] for row in data)
	total_amount = sum(row["total_amount"] for row in data)
	total_stamped_amount = sum(row["stamped_amount"] for row in data)
	total_addenda = sum(row["addenda_invoices"] for row in data)
	total_errors = sum(row["error_count"] for row in data)

	# Calcular promedios
	avg_stamping_percentage = (total_stamped / total_invoices * 100) if total_invoices > 0 else 0
	avg_stamping_time = sum(row["avg_stamping_time"] or 0 for row in data) / len(data)

	# Estadísticas adicionales
	branches_with_errors = len([row for row in data if row["error_count"] > 0])
	branches_with_addenda = len([row for row in data if row["addenda_invoices"] > 0])

	summary = [
		{"label": _("Total Sucursales"), "value": len(data), "indicator": "blue"},
		{"label": _("Total Facturas"), "value": total_invoices, "indicator": "blue"},
		{
			"label": _("Facturas Timbradas"),
			"value": f"{total_stamped} ({avg_stamping_percentage:.1f}%)",
			"indicator": "green" if avg_stamping_percentage > 90 else "orange",
		},
		{
			"label": _("Pendientes Timbrar"),
			"value": total_pending,
			"indicator": "red" if total_pending > 0 else "green",
		},
		{
			"label": _("Monto Total"),
			"value": frappe.format_value(total_amount, "Currency"),
			"indicator": "blue",
		},
		{
			"label": _("Monto Timbrado"),
			"value": frappe.format_value(total_stamped_amount, "Currency"),
			"indicator": "green",
		},
		{
			"label": _("Con Addenda"),
			"value": f"{total_addenda} facturas ({branches_with_addenda} sucursales)",
			"indicator": "blue",
		},
		{
			"label": _("Errores Total"),
			"value": f"{total_errors} errores ({branches_with_errors} sucursales)",
			"indicator": "red" if total_errors > 0 else "green",
		},
		{
			"label": _("Tiempo Promedio"),
			"value": f"{avg_stamping_time:.2f} minutos",
			"indicator": "green" if avg_stamping_time < 5 else "orange",
		},
	]

	return summary
