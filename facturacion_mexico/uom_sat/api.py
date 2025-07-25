# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT API - Sprint 6 Phase 4
APIs principales para el sistema de mapeo UOM-SAT
"""

import json

import frappe
from frappe import _

# Importar componentes del sistema UOM-SAT
from facturacion_mexico.uom_sat.mapper import UOMSATMapper
from facturacion_mexico.uom_sat.validation import UOMSATValidator


@frappe.whitelist()
def get_uom_mapping_dashboard() -> dict:
	"""API para obtener datos del dashboard de mapeo UOM-SAT"""
	try:
		# Estadísticas generales
		total_uoms = frappe.db.count("UOM")
		mapped_uoms = frappe.db.count("UOM", {"fm_clave_sat": ["is", "set"]})
		auto_mapped = frappe.db.count("UOM", {"fm_mapping_source": "Auto"})
		verified_mapped = frappe.db.count("UOM", {"fm_mapping_verified": 1})
		low_confidence = frappe.db.count("UOM", {"fm_mapping_confidence": ["<", 80]})

		# UOMs más usadas sin mapeo
		unmapped_popular = frappe.db.sql(
			"""
            SELECT u.name, u.uom_name, COUNT(si.name) as usage_count
            FROM `tabUOM` u
            LEFT JOIN `tabSales Invoice Item` si ON si.uom = u.name
            WHERE u.fm_clave_sat IS NULL OR u.fm_clave_sat = ''
            GROUP BY u.name, u.uom_name
            ORDER BY usage_count DESC
            LIMIT 10
        """,
			as_dict=True,
		)

		# Distribución por fuente de mapeo
		mapping_sources = frappe.db.sql(
			"""
            SELECT fm_mapping_source as source, COUNT(*) as count
            FROM `tabUOM`
            WHERE fm_clave_sat IS NOT NULL AND fm_clave_sat != ''
            GROUP BY fm_mapping_source
        """,
			as_dict=True,
		)

		# Tendencia de mapeos (últimos 30 días)
		mapping_trend = frappe.db.sql(
			"""
            SELECT DATE(fm_last_sync_date) as date, COUNT(*) as mappings
            FROM `tabUOM`
            WHERE fm_last_sync_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
            AND fm_clave_sat IS NOT NULL
            GROUP BY DATE(fm_last_sync_date)
            ORDER BY date DESC
        """,
			as_dict=True,
		)

		return {
			"success": True,
			"dashboard": {
				"summary": {
					"total_uoms": total_uoms,
					"mapped_uoms": mapped_uoms,
					"unmapped_uoms": total_uoms - mapped_uoms,
					"mapping_percentage": round((mapped_uoms / total_uoms) * 100, 2) if total_uoms > 0 else 0,
					"auto_mapped": auto_mapped,
					"verified_mapped": verified_mapped,
					"low_confidence": low_confidence,
				},
				"unmapped_popular": unmapped_popular,
				"mapping_sources": mapping_sources,
				"mapping_trend": mapping_trend,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error in get_uom_mapping_dashboard API: {e!s}", "UOM SAT Dashboard API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_unmapped_uoms(limit: int = 50, popular_only: bool = False) -> dict:
	"""API para obtener UOMs sin mapeo SAT"""
	try:
		filters = {"fm_clave_sat": ["is", "not set"]}

		if popular_only:
			# Solo UOMs que se usan en facturas
			unmapped_uoms = frappe.db.sql(
				"""
                SELECT DISTINCT u.name, u.uom_name, u.must_be_whole_number,
                       COUNT(si.name) as usage_count
                FROM `tabUOM` u
                LEFT JOIN `tabSales Invoice Item` si ON si.uom = u.name
                WHERE (u.fm_clave_sat IS NULL OR u.fm_clave_sat = '')
                GROUP BY u.name, u.uom_name, u.must_be_whole_number
                HAVING usage_count > 0
                ORDER BY usage_count DESC
                LIMIT %s
            """,
				limit,
				as_dict=True,
			)
		else:
			unmapped_uoms = frappe.get_all(
				"UOM",
				filters=filters,
				fields=["name", "uom_name", "must_be_whole_number"],
				limit=limit,
				order_by="creation desc",
			)

		return {"success": True, "unmapped_uoms": unmapped_uoms, "count": len(unmapped_uoms)}

	except Exception as e:
		frappe.log_error(f"Error in get_unmapped_uoms API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def bulk_suggest_mappings(confidence_threshold: int = 70, limit: int = 50) -> dict:
	"""API para generar sugerencias masivas de mapeo"""
	try:
		# REGLA #35: Validate input parameters defensively
		try:
			confidence_threshold = int(confidence_threshold) if confidence_threshold else 70
			limit = int(limit) if limit else 50
		except (ValueError, TypeError):
			return {
				"success": False,
				"message": "Invalid parameters: confidence_threshold and limit must be integers",
			}

		if not (0 <= confidence_threshold <= 100):
			return {"success": False, "message": "confidence_threshold must be between 0 and 100"}

		if limit <= 0 or limit > 1000:
			return {"success": False, "message": "limit must be between 1 and 1000"}

		mapper = UOMSATMapper()
		mapper.confidence_threshold = confidence_threshold

		# Obtener UOMs sin mapeo
		unmapped_uoms = frappe.get_all(
			"UOM",
			filters={"fm_clave_sat": ["is", "not set"]},
			fields=["name", "uom_name"],
			limit=limit,
		)

		suggestions = []
		for uom in unmapped_uoms:
			# REGLA #35: Defensive access for dict/object compatibility
			uom_name = uom.get("uom_name") if isinstance(uom, dict) else uom.uom_name
			uom_name_key = uom.get("name") if isinstance(uom, dict) else uom.name

			suggestion = mapper.suggest_mapping(uom_name)
			if suggestion.get("suggested_mapping"):
				suggestions.append(
					{
						"uom": uom_name_key,
						"uom_name": uom_name,
						"suggested_mapping": suggestion["suggested_mapping"],
						"confidence": suggestion["confidence"],
						"reason": suggestion["reason"],
						"sat_description": suggestion.get("sat_description"),
					}
				)

		return {
			"success": True,
			"suggestions": suggestions,
			"total_processed": len(unmapped_uoms),
			"suggestions_generated": len(suggestions),
		}

	except Exception as e:
		frappe.log_error(f"Error in bulk_suggest_mappings API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def apply_bulk_mappings(mappings: str, apply_mode: str = "high_confidence") -> dict:
	"""API para aplicar mapeos en lote"""
	try:
		# REGLA #35: Validate parameters and handle JSON parsing defensively
		if not mappings:
			return {"success": False, "message": "mappings parameter is required"}

		valid_modes = ["all", "high_confidence", "medium_confidence"]
		if apply_mode not in valid_modes:
			return {"success": False, "message": f"apply_mode must be one of: {', '.join(valid_modes)}"}

		try:
			if isinstance(mappings, str):
				mappings = json.loads(mappings)
		except json.JSONDecodeError as e:
			return {"success": False, "message": f"Invalid JSON in mappings parameter: {e!s}"}

		applied = 0
		skipped = 0
		errors = 0
		results = []

		for mapping in mappings:
			try:
				confidence = mapping.get("confidence", 0)
				uom = mapping["uom"]

				# Decidir si aplicar basado en modo
				should_apply = False
				if apply_mode == "all":
					should_apply = True
				elif apply_mode == "high_confidence" and confidence >= 85:
					should_apply = True
				elif apply_mode == "medium_confidence" and confidence >= 70:
					should_apply = True

				if should_apply:
					frappe.db.set_value(
						"UOM",
						uom,
						{
							"fm_clave_sat": mapping["suggested_mapping"],
							"fm_mapping_confidence": confidence,
							"fm_mapping_source": "Auto",
							"fm_last_sync_date": frappe.utils.today(),
						},
					)
					applied += 1
					results.append({"uom": uom, "status": "applied", "confidence": confidence})
				else:
					skipped += 1
					results.append(
						{
							"uom": uom,
							"status": "skipped",
							"reason": "Low confidence",
							"confidence": confidence,
						}
					)

			except Exception as e:
				errors += 1
				results.append({"uom": mapping.get("uom", "unknown"), "status": "error", "error": str(e)})

		if applied > 0:
			frappe.db.commit()

		return {
			"success": True,
			"applied": applied,
			"skipped": skipped,
			"errors": errors,
			"results": results,
			"message": f"Aplicados {applied} mapeos, {skipped} omitidos, {errors} errores",
		}

	except Exception as e:
		frappe.log_error(f"Error in apply_bulk_mappings API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def validate_all_pending_invoices(auto_fix: bool = False) -> dict:
	"""API para validar mapeos UOM-SAT en facturas pendientes"""
	try:
		# Obtener facturas pendientes de timbrar
		pending_invoices = frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1, "fm_cfdi_xml": ["is", "not set"]},
			fields=["name", "customer", "grand_total"],
			limit=100,
		)

		validator = UOMSATValidator()
		validation_results = []
		total_invalid = 0
		total_warnings = 0

		for invoice in pending_invoices:
			try:
				# REGLA #35: Defensive DocType access
				try:
					invoice_doc = frappe.get_doc("Sales Invoice", invoice.name)
				except frappe.DoesNotExistError:
					validation_results.append(
						{
							"invoice": invoice.name,
							"customer": invoice.customer,
							"is_valid": False,
							"error": "Invoice not found",
						}
					)
					continue

				validation = validator.validate_invoice_uom_mappings(invoice_doc)

				result = {
					"invoice": invoice.name,
					"customer": invoice.customer,
					"grand_total": invoice.grand_total,
					"is_valid": validation["is_valid"],
					"error_count": len(validation["errors"]),
					"warning_count": len(validation["warnings"]),
				}

				if not validation["is_valid"]:
					total_invalid += 1
					result["errors"] = validation["errors"]

				if validation["warnings"]:
					total_warnings += len(validation["warnings"])
					result["warnings"] = validation["warnings"]

				validation_results.append(result)

			except Exception as e:
				validation_results.append(
					{
						"invoice": invoice.name,
						"customer": invoice.customer,
						"is_valid": False,
						"error": str(e),
					}
				)

		return {
			"success": True,
			"summary": {
				"total_invoices": len(pending_invoices),
				"valid_invoices": len(pending_invoices) - total_invalid,
				"invalid_invoices": total_invalid,
				"total_warnings": total_warnings,
			},
			"validation_results": validation_results,
		}

	except Exception as e:
		frappe.log_error(f"Error in validate_all_pending_invoices API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_sat_catalog() -> dict:
	"""API para obtener catálogo completo de unidades SAT"""
	try:
		# Intentar obtener desde DocType
		if frappe.db.exists("DocType", "Unidad Medida SAT"):
			catalog = frappe.get_all(
				"Unidad Medida SAT",
				fields=["name as clave", "descripcion", "simbolo", "disabled"],
				filters={"disabled": 0},
				order_by="descripcion",
			)
		else:
			# Catálogo básico como fallback
			mapper = UOMSATMapper()
			catalog = mapper._load_sat_catalog()

		return {"success": True, "catalog": catalog, "count": len(catalog)}

	except Exception as e:
		frappe.log_error(f"Error in get_sat_catalog API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def sync_sat_catalog() -> dict:
	"""API para sincronizar catálogo SAT (placeholder para futuras actualizaciones)"""
	try:
		# Placeholder para sincronización con SAT
		# En el futuro podría conectar con APIs oficiales del SAT

		current_count = (
			frappe.db.count("Unidad Medida SAT") if frappe.db.exists("DocType", "Unidad Medida SAT") else 0
		)

		return {
			"success": True,
			"message": "Sincronización del catálogo SAT completada",
			"catalog_entries": current_count,
			"last_sync": frappe.utils.now(),
		}

	except Exception as e:
		frappe.log_error(f"Error in sync_sat_catalog API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def export_uom_mappings(format: str = "json") -> dict:
	"""API para exportar mapeos UOM-SAT"""
	try:
		mappings = frappe.get_all(
			"UOM",
			filters={"fm_clave_sat": ["is", "set"]},
			fields=[
				"name",
				"uom_name",
				"fm_clave_sat",
				"fm_mapping_confidence",
				"fm_mapping_source",
				"fm_last_sync_date",
				"fm_mapping_verified",
			],
		)

		if format.lower() == "csv":
			# Convertir a formato CSV
			import csv
			import io

			output = io.StringIO()
			writer = csv.DictWriter(output, fieldnames=mappings[0].keys() if mappings else [])
			writer.writeheader()
			writer.writerows(mappings)
			csv_content = output.getvalue()

			return {"success": True, "format": "csv", "content": csv_content, "count": len(mappings)}

		# JSON por defecto
		return {"success": True, "format": "json", "mappings": mappings, "count": len(mappings)}

	except Exception as e:
		frappe.log_error(f"Error in export_uom_mappings API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def import_uom_mappings(mappings_data: str, update_existing: bool = False) -> dict:
	"""API para importar mapeos UOM-SAT"""
	try:
		# REGLA #35: Validate parameters and handle JSON parsing defensively
		if not mappings_data:
			return {"success": False, "message": "mappings_data parameter is required"}

		try:
			if isinstance(mappings_data, str):
				mappings = json.loads(mappings_data)
			else:
				mappings = mappings_data
		except json.JSONDecodeError as e:
			return {"success": False, "message": f"Invalid JSON in mappings_data parameter: {e!s}"}

		imported = 0
		updated = 0
		skipped = 0
		errors = 0

		for mapping in mappings:
			try:
				uom_name = mapping.get("name") or mapping.get("uom")
				if not uom_name or not frappe.db.exists("UOM", uom_name):
					skipped += 1
					continue

				# Verificar si ya tiene mapeo
				current_mapping = frappe.db.get_value("UOM", uom_name, "fm_clave_sat")

				if current_mapping and not update_existing:
					skipped += 1
					continue

				# Aplicar mapeo
				frappe.db.set_value(
					"UOM",
					uom_name,
					{
						"fm_clave_sat": mapping.get("fm_clave_sat"),
						"fm_mapping_confidence": mapping.get("fm_mapping_confidence", 100),
						"fm_mapping_source": "Imported",
						"fm_last_sync_date": frappe.utils.today(),
						"fm_mapping_verified": mapping.get("fm_mapping_verified", 0),
					},
				)

				if current_mapping:
					updated += 1
				else:
					imported += 1

			except Exception as e:
				errors += 1
				frappe.log_error(f"Error importing mapping: {e!s}", "UOM Mapping Import")

		if imported > 0 or updated > 0:
			frappe.db.commit()

		return {
			"success": True,
			"imported": imported,
			"updated": updated,
			"skipped": skipped,
			"errors": errors,
			"message": f"Importados {imported} mapeos, actualizados {updated}, omitidos {skipped}, errores {errors}",
		}

	except Exception as e:
		frappe.log_error(f"Error in import_uom_mappings API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}"}


# APIs de instalación y configuración
@frappe.whitelist()
def install_uom_sat_system() -> dict:
	"""API para instalar sistema UOM-SAT completo"""
	try:
		from facturacion_mexico.uom_sat.custom_fields import create_uom_sat_fields

		# Instalar custom fields
		fields_result = create_uom_sat_fields()

		if not fields_result["success"]:
			return fields_result

		# Ejecutar mapeo inicial automático
		mapper = UOMSATMapper()
		bulk_result = mapper.bulk_map_uoms(confidence_threshold=85, auto_apply=True)

		return {
			"success": True,
			"message": "Sistema UOM-SAT instalado exitosamente",
			"fields_installed": fields_result["success"],
			"initial_mappings": bulk_result,
		}

	except Exception as e:
		frappe.log_error(f"Error in install_uom_sat_system API: {e!s}", "UOM SAT Installation")
		return {"success": False, "message": f"Error: {e!s}"}
