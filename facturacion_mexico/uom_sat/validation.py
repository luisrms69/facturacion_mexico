# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT Validation - Sprint 6 Phase 4
Validación de mapeos UOM-SAT en facturación
"""

import frappe
from frappe import _


class UOMSATValidator:
	"""
	Validador de mapeos UOM-SAT para facturación
	Asegura que todas las UOMs tengan mapeo SAT antes del timbrado
	"""

	def __init__(self):
		self.validation_enabled = self._is_validation_enabled()

	def validate_invoice_uom_mappings(self, invoice_doc) -> dict:
		"""
		Validar que todas las UOMs de la factura tengan mapeo SAT

		Args:
		    invoice_doc: Documento Sales Invoice

		Returns:
		    dict con is_valid, errors, warnings, suggestions
		"""
		if not self.validation_enabled:
			return {"is_valid": True, "errors": [], "warnings": [], "suggestions": []}

		try:
			unmapped_items = []
			warnings = []
			suggestions = []

			for item in invoice_doc.items:
				uom_mapping = self._get_uom_mapping(item.uom)

				if not uom_mapping:
					unmapped_items.append(
						{
							"item_code": item.item_code,
							"item_name": item.item_name,
							"uom": item.uom,
							"qty": item.qty,
						}
					)
				elif uom_mapping.get("confidence", 100) < 80:
					warnings.append(
						f"Item '{item.item_code}': UOM '{item.uom}' tiene mapeo SAT con "
						f"baja confianza ({uom_mapping.get('confidence', 0)}%)"
					)

			# Si hay UOMs sin mapeo, generar sugerencias
			if unmapped_items:
				suggestions = self._generate_mapping_suggestions(unmapped_items)

			errors = []
			if unmapped_items:
				errors.append(
					f"Los siguientes items no tienen mapeo UOM-SAT: "
					f"{', '.join([item['item_code'] for item in unmapped_items])}"
				)

			return {
				"is_valid": len(errors) == 0,
				"errors": errors,
				"warnings": warnings,
				"suggestions": suggestions,
				"unmapped_items": unmapped_items,
			}

		except Exception as e:
			frappe.log_error(f"Error validating UOM mappings: {e!s}", "UOM SAT Validation")
			return {
				"is_valid": False,
				"errors": [f"Error en validación UOM-SAT: {e!s}"],
				"warnings": [],
				"suggestions": [],
			}

	def validate_and_suggest_corrections(self, invoice_doc) -> dict:
		"""
		Validar y ofrecer correcciones automáticas para UOMs sin mapeo

		Args:
		    invoice_doc: Documento Sales Invoice

		Returns:
		    dict con validation result y auto-correction options
		"""
		validation_result = self.validate_invoice_uom_mappings(invoice_doc)

		if not validation_result["is_valid"] and validation_result["unmapped_items"]:
			# Generar mapeos automáticos para items sin mapeo
			auto_corrections = self._generate_auto_corrections(validation_result["unmapped_items"])
			validation_result["auto_corrections"] = auto_corrections

		return validation_result

	def apply_auto_corrections(self, corrections: list, apply_mode: str = "suggest") -> dict:
		"""
		Aplicar correcciones automáticas de mapeo UOM-SAT

		Args:
		    corrections: Lista de correcciones sugeridas
		    apply_mode: 'suggest', 'apply_high_confidence', 'apply_all'

		Returns:
		    dict con resultados de la aplicación
		"""
		try:
			applied = 0
			skipped = 0
			errors = 0

			for correction in corrections:
				try:
					confidence = correction.get("confidence", 0)
					uom = correction["uom"]

					# Decidir si aplicar basado en modo y confianza
					should_apply = False
					if apply_mode == "apply_all":
						should_apply = True
					elif apply_mode == "apply_high_confidence" and confidence >= 85:
						should_apply = True

					if should_apply:
						frappe.db.set_value(
							"UOM",
							uom,
							{
								"fm_clave_sat": correction["suggested_mapping"],
								"fm_mapping_confidence": confidence,
								"fm_mapping_source": "Auto",
								"fm_last_sync_date": frappe.utils.today(),
							},
						)
						applied += 1
					else:
						skipped += 1

				except Exception as e:
					errors += 1
					frappe.log_error(
						f"Error applying correction for UOM '{correction.get('uom')}': {e!s}",
						"UOM Auto Correction",
					)

			if applied > 0:
				frappe.db.commit()

			return {
				"success": True,
				"applied": applied,
				"skipped": skipped,
				"errors": errors,
				"message": f"Aplicadas {applied} correcciones, {skipped} omitidas, {errors} errores",
			}

		except Exception as e:
			frappe.log_error(f"Error in apply_auto_corrections: {e!s}", "UOM Auto Correction")
			return {"success": False, "message": f"Error: {e!s}"}

	def _get_uom_mapping(self, uom: str) -> dict | None:
		"""Obtener mapeo SAT de una UOM"""
		try:
			uom_doc = frappe.get_cached_doc("UOM", uom)
			if uom_doc.get("fm_clave_sat"):
				return {
					"sat_clave": uom_doc.fm_clave_sat,
					"confidence": uom_doc.get("fm_mapping_confidence", 100),
					"source": uom_doc.get("fm_mapping_source", "Manual"),
					"verified": uom_doc.get("fm_mapping_verified", 0),
				}
			return None
		except Exception:
			return None

	def _generate_mapping_suggestions(self, unmapped_items: list) -> list:
		"""Generar sugerencias de mapeo para items sin mapeo"""
		try:
			from facturacion_mexico.uom_sat.mapper import UOMSATMapper

			mapper = UOMSATMapper()
			suggestions = []

			for item in unmapped_items:
				suggestion = mapper.suggest_mapping(item["uom"])
				if suggestion.get("suggested_mapping"):
					suggestions.append(
						{
							"item_code": item["item_code"],
							"uom": item["uom"],
							"suggested_mapping": suggestion["suggested_mapping"],
							"confidence": suggestion["confidence"],
							"reason": suggestion["reason"],
							"sat_description": suggestion.get("sat_description"),
						}
					)

			return suggestions

		except Exception as e:
			frappe.log_error(f"Error generating suggestions: {e!s}", "UOM Suggestions")
			return []

	def _generate_auto_corrections(self, unmapped_items: list) -> list:
		"""Generar correcciones automáticas con mayor detalle"""
		suggestions = self._generate_mapping_suggestions(unmapped_items)

		corrections = []
		for suggestion in suggestions:
			# Solo incluir sugerencias con confianza razonable
			if suggestion["confidence"] >= 70:
				corrections.append(
					{
						"uom": suggestion["uom"],
						"current_mapping": None,
						"suggested_mapping": suggestion["suggested_mapping"],
						"confidence": suggestion["confidence"],
						"reason": suggestion["reason"],
						"sat_description": suggestion.get("sat_description"),
						"recommendation": self._get_recommendation(suggestion["confidence"]),
					}
				)

		return corrections

	def _get_recommendation(self, confidence: int) -> str:
		"""Obtener recomendación basada en confianza"""
		if confidence >= 90:
			return "Alta confianza - Aplicar automáticamente"
		elif confidence >= 80:
			return "Confianza media - Revisar antes de aplicar"
		elif confidence >= 70:
			return "Baja confianza - Validar manualmente"
		else:
			return "Muy baja confianza - No recomendado"

	def _is_validation_enabled(self) -> bool:
		"""Verificar si la validación UOM-SAT está habilitada"""
		try:
			settings = frappe.get_single("Facturacion Mexico Settings")
			return getattr(settings, "validate_uom_mappings", True)
		except Exception:
			return True  # Por defecto habilitado


# Hook para Sales Invoice validation
def sales_invoice_validate_uom_mappings(doc, method):
	"""Hook que valida mapeos UOM-SAT en Sales Invoice"""
	try:
		# Solo validar si está habilitado y es factura electrónica
		if not doc.get("fm_factura_electronica"):
			return

		validator = UOMSATValidator()
		validation_result = validator.validate_invoice_uom_mappings(doc)

		# Mostrar warnings si hay
		for warning in validation_result["warnings"]:
			frappe.msgprint(warning, title="Advertencia UOM-SAT", indicator="orange")

		# Fallar validación si hay errores críticos
		if not validation_result["is_valid"]:
			# Mostrar sugerencias si las hay
			if validation_result.get("suggestions"):
				suggestion_msg = _("Sugerencias de mapeo automático disponibles. ")
				suggestion_msg += _("Use el botón 'Sugerir Mapeos UOM-SAT' para aplicarlas.")
				frappe.msgprint(suggestion_msg, title=_("Sugerencias UOM-SAT"), indicator="blue")

			# Fallar con error descriptivo
			error_msg = _("Facturación bloqueada: ") + "; ".join(validation_result["errors"])
			frappe.throw(error_msg, title=_("Error UOM-SAT"))

	except Exception as e:
		# No fallar la factura por errores en validación UOM
		frappe.log_error(f"Error in UOM validation hook: {e!s}", "UOM SAT Validation Hook")


# APIs públicas
@frappe.whitelist()
def validate_invoice_uom_mappings(sales_invoice: str) -> dict:
	"""API para validar mapeos UOM-SAT de una factura"""
	try:
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		validator = UOMSATValidator()
		return {"success": True, "validation": validator.validate_invoice_uom_mappings(invoice_doc)}
	except Exception as e:
		frappe.log_error(f"Error in validate_invoice_uom_mappings API: {e!s}", "UOM SAT Validation API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def suggest_and_apply_uom_corrections(sales_invoice: str, apply_mode: str = "suggest") -> dict:
	"""API para sugerir y aplicar correcciones UOM-SAT"""
	try:
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		validator = UOMSATValidator()

		# Generar sugerencias
		validation_result = validator.validate_and_suggest_corrections(invoice_doc)

		result = {"success": True, "validation": validation_result}

		# Aplicar correcciones si se solicita
		if apply_mode != "suggest" and validation_result.get("auto_corrections"):
			correction_result = validator.apply_auto_corrections(
				validation_result["auto_corrections"], apply_mode
			)
			result["correction_result"] = correction_result

		return result

	except Exception as e:
		frappe.log_error(f"Error in suggest_and_apply_uom_corrections API: {e!s}", "UOM SAT Validation API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_uom_validation_status(sales_invoice: str) -> dict:
	"""API para obtener estado de validación UOM-SAT de una factura"""
	try:
		invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
		validator = UOMSATValidator()

		# Obtener estadísticas
		total_items = len(invoice_doc.items)
		mapped_items = 0
		low_confidence_items = 0

		for item in invoice_doc.items:
			mapping = validator._get_uom_mapping(item.uom)
			if mapping:
				mapped_items += 1
				if mapping.get("confidence", 100) < 80:
					low_confidence_items += 1

		return {
			"success": True,
			"status": {
				"total_items": total_items,
				"mapped_items": mapped_items,
				"unmapped_items": total_items - mapped_items,
				"low_confidence_items": low_confidence_items,
				"mapping_percentage": round((mapped_items / total_items) * 100, 2) if total_items > 0 else 0,
				"validation_enabled": validator.validation_enabled,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error in get_uom_validation_status API: {e!s}", "UOM SAT Validation API")
		return {"success": False, "message": f"Error: {e!s}"}
