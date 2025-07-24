# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT Custom Fields - Sprint 6 Phase 4
Custom fields para mapeo de UOM con catálogo SAT
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def create_uom_sat_fields():
	"""Crear custom fields para mapeo SAT en UOM"""

	custom_fields = {
		"UOM": [
			{
				"fieldname": "fm_sat_section",
				"fieldtype": "Section Break",
				"label": "Configuración SAT",
				"insert_after": "enabled",
				"collapsible": 1,
			},
			{
				"fieldname": "fm_clave_sat",
				"fieldtype": "Link",
				"label": "Clave SAT",
				"options": "Unidad Medida SAT",
				"insert_after": "fm_sat_section",
				"description": "Unidad de medida según catálogo SAT",
			},
			{
				"fieldname": "fm_mapping_confidence",
				"fieldtype": "Percent",
				"label": "Confianza del Mapeo",
				"insert_after": "fm_clave_sat",
				"description": "Porcentaje de confianza en el mapeo automático",
				"depends_on": "eval:doc.fm_clave_sat",
				"read_only": 1,
			},
			{
				"fieldname": "fm_mapping_source",
				"fieldtype": "Select",
				"label": "Origen del Mapeo",
				"options": "Manual\nAuto\nVerified\nSuggested",
				"default": "Manual",
				"insert_after": "fm_mapping_confidence",
				"depends_on": "eval:doc.fm_clave_sat",
			},
			{
				"fieldname": "fm_last_sync_date",
				"fieldtype": "Date",
				"label": "Última Sincronización",
				"insert_after": "fm_mapping_source",
				"depends_on": "eval:doc.fm_clave_sat",
				"read_only": 1,
				"description": "Fecha de última sincronización con catálogo SAT",
			},
			{
				"fieldname": "fm_mapping_verified",
				"fieldtype": "Check",
				"label": "Mapeo Verificado",
				"insert_after": "fm_last_sync_date",
				"depends_on": "eval:doc.fm_clave_sat",
				"description": "Marcar si el mapeo ha sido verificado manualmente",
			},
		]
	}

	try:
		create_custom_fields(custom_fields, update=True)
		frappe.db.commit()
		return {"success": True, "message": "Custom fields UOM-SAT creados exitosamente"}
	except Exception as e:
		frappe.log_error(f"Error creando custom fields UOM-SAT: {e!s}", "UOM SAT Fields")
		return {"success": False, "message": f"Error: {e!s}"}


def remove_uom_sat_fields():
	"""Remover custom fields UOM-SAT (para desarrollo/testing)"""

	field_names = [
		"fm_sat_section",
		"fm_clave_sat",
		"fm_mapping_confidence",
		"fm_mapping_source",
		"fm_last_sync_date",
		"fm_mapping_verified",
	]

	try:
		for field_name in field_names:
			frappe.db.sql(
				"""
                DELETE FROM `tabCustom Field`
                WHERE dt = 'UOM' AND fieldname = %s
            """,
				field_name,
			)

		frappe.db.commit()
		frappe.clear_cache()
		return {"success": True, "message": "Custom fields UOM-SAT removidos exitosamente"}
	except Exception as e:
		frappe.log_error(f"Error removiendo custom fields UOM-SAT: {e!s}", "UOM SAT Fields")
		return {"success": False, "message": f"Error: {e!s}"}


# Hook para sugerir mapeo SAT automáticamente
def uom_validate(doc, method):
	"""Hook que se ejecuta al validar UOM para sugerir mapeo SAT"""
	try:
		# REGLA #35: Defensive access para fm_clave_sat field
		current_sat_mapping = getattr(doc, "fm_clave_sat", None)
		if not current_sat_mapping:
			from facturacion_mexico.uom_sat.mapper import UOMSATMapper

			mapper = UOMSATMapper()
			uom_name = getattr(doc, "uom_name", None)
			if not uom_name:
				return

			suggestion = mapper.suggest_mapping(uom_name)

			if suggestion.get("suggested_mapping"):
				# Auto-asignar si la confianza es muy alta (>90%)
				if suggestion["confidence"] > 90:
					doc.fm_clave_sat = suggestion["suggested_mapping"]
					doc.fm_mapping_confidence = suggestion["confidence"]
					doc.fm_mapping_source = "Auto"
					doc.fm_last_sync_date = frappe.utils.today()

					frappe.msgprint(
						f"Mapeo SAT auto-asignado: {suggestion['suggested_mapping']} "
						f"(Confianza: {suggestion['confidence']}%)",
						title="Mapeo SAT Automático",
						indicator="green",
					)
				elif suggestion["confidence"] > 70:
					# Solo mostrar sugerencia si confianza es moderada
					frappe.msgprint(
						f"Sugerencia de mapeo SAT: {suggestion['suggested_mapping']} "
						f"(Confianza: {suggestion['confidence']}%)",
						title="Sugerencia de Mapeo SAT",
						indicator="blue",
					)

	except Exception as e:
		# No fallar la validación por error en mapeo
		frappe.log_error(f"Error en hook UOM validate: {e!s}", "UOM SAT Hook")


# API endpoints
@frappe.whitelist()
def setup_uom_sat_fields():
	"""API para crear custom fields UOM-SAT"""
	return create_uom_sat_fields()


@frappe.whitelist()
def remove_sat_fields():
	"""API para remover custom fields UOM-SAT"""
	return remove_uom_sat_fields()
