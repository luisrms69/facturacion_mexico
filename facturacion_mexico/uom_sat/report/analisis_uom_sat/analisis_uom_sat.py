# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Análisis UOM-SAT - Sprint 6 Phase 5
Reporte especializado para análisis de mapeos UOM-SAT
"""

import frappe
from frappe import _


def execute(filters=None):
	"""Ejecutar reporte de análisis UOM-SAT"""
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data, filters)
	chart = get_chart_data(data)

	return columns, data, None, chart, summary


def get_columns():
	"""Definir columnas del reporte"""
	return [
		{
			"fieldname": "uom",
			"label": _("UOM"),
			"fieldtype": "Link",
			"options": "UOM",
			"width": 120,
		},
		{
			"fieldname": "uom_name",
			"label": _("Nombre UOM"),
			"fieldtype": "Data",
			"width": 180,
		},
		{
			"fieldname": "sat_clave",
			"label": _("Clave SAT"),
			"fieldtype": "Data",
			"width": 100,
		},
		{
			"fieldname": "sat_description",
			"label": _("Descripción SAT"),
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"fieldname": "mapping_source",
			"label": _("Origen Mapeo"),
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"fieldname": "mapping_confidence",
			"label": _("Confianza"),
			"fieldtype": "Percent",
			"width": 100,
		},
		{
			"fieldname": "mapping_verified",
			"label": _("Verificado"),
			"fieldtype": "Check",
			"width": 100,
		},
		{
			"fieldname": "usage_count",
			"label": _("Uso en Facturas"),
			"fieldtype": "Int",
			"width": 130,
		},
		{
			"fieldname": "total_amount",
			"label": _("Monto Total"),
			"fieldtype": "Currency",
			"width": 140,
		},
		{
			"fieldname": "items_count",
			"label": _("Items Únicos"),
			"fieldtype": "Int",
			"width": 120,
		},
		{
			"fieldname": "last_used",
			"label": _("Último Uso"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "last_sync_date",
			"label": _("Última Sync"),
			"fieldtype": "Date",
			"width": 120,
		},
		{
			"fieldname": "status",
			"label": _("Estado"),
			"fieldtype": "Data",
			"width": 120,
		},
	]


def get_data(filters):
	"""Obtener datos del reporte"""
	conditions = get_conditions(filters)

	# Query principal para obtener UOMs y su uso
	query = f"""
		SELECT
			u.name as uom,
			u.uom_name,
			u.fm_clave_sat as sat_clave,
			u.fm_mapping_source as mapping_source,
			u.fm_mapping_confidence as mapping_confidence,
			u.fm_mapping_verified as mapping_verified,
			u.fm_last_sync_date as last_sync_date,
			COUNT(DISTINCT si.name) as usage_count,
			SUM(si.grand_total) as total_amount,
			COUNT(DISTINCT sii.item_code) as items_count,
			MAX(si.posting_date) as last_used
		FROM `tabUOM` u
		LEFT JOIN `tabSales Invoice Item` sii ON sii.uom = u.name
		LEFT JOIN `tabSales Invoice` si ON si.name = sii.parent AND si.docstatus = 1 {conditions}
		WHERE u.enabled = 1
		GROUP BY u.name, u.uom_name, u.fm_clave_sat, u.fm_mapping_source,
				 u.fm_mapping_confidence, u.fm_mapping_verified, u.fm_last_sync_date
		ORDER BY usage_count DESC, total_amount DESC
	"""

	data = frappe.db.sql(query, filters, as_dict=True)

	# Enriquecer datos con información SAT y estado
	for row in data:
		# Obtener descripción SAT
		row["sat_description"] = get_sat_description(row["sat_clave"])

		# Determinar estado del mapeo
		row["status"] = get_mapping_status(row)

		# Convertir booleanos
		row["mapping_verified"] = 1 if row["mapping_verified"] else 0

		# Manejar valores nulos
		row["usage_count"] = row["usage_count"] or 0
		row["total_amount"] = row["total_amount"] or 0
		row["items_count"] = row["items_count"] or 0

	return data


def get_conditions(filters):
	"""Construir condiciones WHERE del query"""
	conditions = []

	if filters.get("from_date"):
		conditions.append("si.posting_date >= %(from_date)s")

	if filters.get("to_date"):
		conditions.append("si.posting_date <= %(to_date)s")

	if filters.get("uom"):
		conditions.append("u.name = %(uom)s")

	if filters.get("mapping_source"):
		conditions.append("u.fm_mapping_source = %(mapping_source)s")

	if filters.get("has_mapping"):
		conditions.append("u.fm_clave_sat IS NOT NULL AND u.fm_clave_sat != ''")

	if filters.get("no_mapping"):
		conditions.append("(u.fm_clave_sat IS NULL OR u.fm_clave_sat = '')")

	if filters.get("verified_only"):
		conditions.append("u.fm_mapping_verified = 1")

	if filters.get("low_confidence"):
		conditions.append("u.fm_mapping_confidence < 80")

	return " AND " + " AND ".join(conditions) if conditions else ""


def get_sat_description(sat_clave):
	"""Obtener descripción de la clave SAT"""
	if not sat_clave:
		return ""

	try:
		# Intentar obtener de DocType si existe
		if frappe.db.exists("DocType", "Unidad Medida SAT"):
			description = frappe.db.get_value("Unidad Medida SAT", sat_clave, "descripcion")
			if description:
				return description

		# Catálogo básico como fallback
		sat_catalog = {
			"H87": "Pieza",
			"KGM": "Kilogramo",
			"GRM": "Gramo",
			"MTR": "Metro",
			"CMT": "Centímetro",
			"LTR": "Litro",
			"MTQ": "Metro cúbico",
			"KWT": "Kilowatt",
			"HUR": "Hora",
			"DAY": "Día",
		}

		return sat_catalog.get(sat_clave, "")

	except Exception:
		return ""


def get_mapping_status(row):
	"""Determinar estado del mapeo UOM-SAT"""
	if not row["sat_clave"]:
		if row["usage_count"] > 0:
			return "❌ Sin Mapear (Usado)"
		else:
			return "⚪ Sin Mapear"

	if row["mapping_verified"]:
		return "✅ Verificado"

	confidence = row["mapping_confidence"] or 0

	if confidence >= 90:
		return "🟢 Alta Confianza"
	elif confidence >= 80:
		return "🟡 Buena Confianza"
	elif confidence >= 70:
		return "🟠 Confianza Media"
	else:
		return "🔴 Baja Confianza"


def get_summary(data, filters):
	"""Generar resumen del reporte"""
	if not data:
		return []

	# Estadísticas generales
	total_uoms = len(data)
	mapped_uoms = len([row for row in data if row["sat_clave"]])
	unmapped_uoms = total_uoms - mapped_uoms

	# UOMs usadas en facturas
	used_uoms = len([row for row in data if row["usage_count"] > 0])
	used_mapped = len([row for row in data if row["usage_count"] > 0 and row["sat_clave"]])
	used_uoms - used_mapped

	# Estadísticas por fuente de mapeo
	auto_mapped = len([row for row in data if row["mapping_source"] == "Auto"])
	len([row for row in data if row["mapping_source"] == "Manual"])
	verified_mapped = len([row for row in data if row["mapping_verified"]])

	# Estadísticas de confianza
	high_confidence = len([row for row in data if (row["mapping_confidence"] or 0) >= 90])
	len([row for row in data if 70 <= (row["mapping_confidence"] or 0) < 90])
	low_confidence = len([row for row in data if row["sat_clave"] and (row["mapping_confidence"] or 0) < 70])

	# Uso en facturas
	total_usage = sum(row["usage_count"] for row in data)
	total_amount = sum(row["total_amount"] for row in data)
	unmapped_usage = sum(row["usage_count"] for row in data if not row["sat_clave"])

	# Porcentajes
	mapping_percentage = (mapped_uoms / total_uoms * 100) if total_uoms > 0 else 0
	usage_mapping_percentage = (used_mapped / used_uoms * 100) if used_uoms > 0 else 0

	summary = [
		{"label": _("Total UOMs"), "value": total_uoms, "indicator": "blue"},
		{
			"label": _("UOMs Mapeadas"),
			"value": f"{mapped_uoms} ({mapping_percentage:.1f}%)",
			"indicator": "green"
			if mapping_percentage > 80
			else "orange"
			if mapping_percentage > 50
			else "red",
		},
		{
			"label": _("UOMs Sin Mapear"),
			"value": f"{unmapped_uoms} ({(100-mapping_percentage):.1f}%)",
			"indicator": "red" if unmapped_uoms > 0 else "green",
		},
		{
			"label": _("UOMs Usadas en Facturas"),
			"value": f"{used_uoms} ({used_mapped} mapeadas)",
			"indicator": "blue",
		},
		{
			"label": _("% Mapeo UOMs Usadas"),
			"value": f"{usage_mapping_percentage:.1f}%",
			"indicator": "green"
			if usage_mapping_percentage > 90
			else "orange"
			if usage_mapping_percentage > 70
			else "red",
		},
		{"label": _("Mapeos Automáticos"), "value": f"{auto_mapped} de {mapped_uoms}", "indicator": "blue"},
		{
			"label": _("Mapeos Verificados"),
			"value": f"{verified_mapped} de {mapped_uoms}",
			"indicator": "green",
		},
		{"label": _("Alta Confianza"), "value": f"{high_confidence} mapeos (≥90%)", "indicator": "green"},
		{
			"label": _("Baja Confianza"),
			"value": f"{low_confidence} mapeos (<70%)",
			"indicator": "red" if low_confidence > 0 else "green",
		},
		{
			"label": _("Uso Total"),
			"value": f"{total_usage} facturas ({unmapped_usage} sin mapear)",
			"indicator": "blue",
		},
		{
			"label": _("Monto Total"),
			"value": frappe.format_value(total_amount, "Currency"),
			"indicator": "blue",
		},
	]

	return summary


def get_chart_data(data):
	"""Generar datos para gráfico"""
	if not data:
		return None

	# Gráfico de distribución por estado de mapeo
	status_counts = {}
	for row in data:
		status = get_mapping_status(row)
		# Limpiar emojis para labels
		clean_status = (
			status.replace("✅ ", "")
			.replace("🟢 ", "")
			.replace("🟡 ", "")
			.replace("🟠 ", "")
			.replace("🔴 ", "")
			.replace("❌ ", "")
			.replace("⚪ ", "")
		)
		status_counts[clean_status] = status_counts.get(clean_status, 0) + 1

	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [{"name": "UOMs", "values": list(status_counts.values())}],
		},
		"type": "pie",
		"height": 300,
		"colors": ["#28a745", "#20c997", "#ffc107", "#fd7e14", "#dc3545", "#6c757d"],
	}
