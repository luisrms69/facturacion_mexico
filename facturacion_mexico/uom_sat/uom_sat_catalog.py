# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT Catalog - Sprint 6 Phase 2
Catálogo completo de Unidades de Medida SAT México
Integrado con validaciones CFDI 4.0 y sistema multi-sucursal
"""

from typing import Any, Optional

import frappe
from frappe import _


class UOMSATCatalog:
	"""
	Catálogo centralizado de Unidades de Medida SAT
	Gestiona validaciones, sincronización y conversiones
	"""

	def __init__(self):
		self._catalog_cache = None

	def get_sat_catalog(self, force_refresh: bool = False) -> list[dict]:
		"""
		Obtener catálogo completo de unidades SAT
		Implementa cache inteligente para performance
		"""
		try:
			if self._catalog_cache is None or force_refresh:
				self._catalog_cache = self._load_sat_catalog()

			return self._catalog_cache

		except Exception as e:
			frappe.log_error(f"Error getting SAT catalog: {e!s}", "UOM SAT Catalog")
			return []

	def validate_uom_sat_code(self, sat_code: str) -> tuple[bool, str, dict | None]:
		"""
		Validar código SAT de unidad de medida
		"""
		try:
			if not sat_code:
				return False, "Código SAT requerido", None

			catalog = self.get_sat_catalog()

			# Buscar en catálogo
			for uom_entry in catalog:
				if uom_entry.get("clave") == sat_code:
					return True, "Código SAT válido", uom_entry

			return False, f"Código SAT '{sat_code}' no encontrado en catálogo", None

		except Exception as e:
			frappe.log_error(f"Error validating UOM SAT code: {e!s}", "UOM SAT Validation")
			return False, f"Error de validación: {e!s}", None

	def suggest_sat_code_for_uom(self, uom_name: str) -> list[dict]:
		"""
		Sugerir códigos SAT basado en nombre de UOM
		Implementa fuzzy matching para mejores sugerencias
		"""
		try:
			catalog = self.get_sat_catalog()
			suggestions = []

			# Normalizar nombre para búsqueda
			uom_normalized = uom_name.lower().strip()

			# Búsqueda exacta por nombre
			for entry in catalog:
				if entry.get("nombre", "").lower() == uom_normalized:
					suggestions.append({**entry, "match_type": "exact", "confidence": 100})

			# Búsqueda parcial si no hay exacta
			if not suggestions:
				for entry in catalog:
					nombre_sat = entry.get("nombre", "").lower()
					descripcion_sat = entry.get("descripcion", "").lower()

					if (
						uom_normalized in nombre_sat
						or nombre_sat in uom_normalized
						or uom_normalized in descripcion_sat
					):
						suggestions.append({**entry, "match_type": "partial", "confidence": 75})

			# Ordenar por confianza
			suggestions.sort(key=lambda x: x.get("confidence", 0), reverse=True)

			return suggestions[:5]  # Top 5 sugerencias

		except Exception as e:
			frappe.log_error(f"Error suggesting SAT code for UOM: {e!s}", "UOM SAT Suggestions")
			return []

	def sync_uom_with_sat_codes(self, dry_run: bool = True) -> dict[str, Any]:
		"""
		Sincronizar UOMs existentes con códigos SAT
		"""
		try:
			results = {"processed": 0, "updated": 0, "errors": 0, "suggestions": [], "dry_run": dry_run}

			# Obtener todas las UOMs sin código SAT
			uoms_without_sat = frappe.get_all(
				"UOM",
				filters={
					"$or": [{"custom_clave_unidad_sat": ["is", "not set"]}, {"custom_clave_unidad_sat": ""}]
				},
				fields=["name", "uom_name", "custom_clave_unidad_sat"],
			)

			for uom in uoms_without_sat:
				results["processed"] += 1

				try:
					# REGLA #35: Defensive access pattern para dict/object compatibility
					# Buscar sugerencias para esta UOM
					if hasattr(uom, "get"):
						# Es un dict
						uom_name = uom.get("uom_name") or uom.get("name")
					else:
						# Es un objeto
						uom_name = getattr(uom, "uom_name", None) or getattr(uom, "name", None)

					suggestions = self.suggest_sat_code_for_uom(uom_name)

					if suggestions:
						best_suggestion = suggestions[0]

						if best_suggestion.get("confidence", 0) >= 90:
							# Auto-asignar si confianza alta
							if not dry_run:
								uom_name_key = (
									uom.get("name") if hasattr(uom, "get") else getattr(uom, "name", None)
								)
								frappe.db.set_value(
									"UOM",
									uom_name_key,
									"custom_clave_unidad_sat",
									best_suggestion["clave"],
								)
								results["updated"] += 1

							# REGLA #35: Defensive access para dict/object compatibility
							uom_name_key = (
								uom.get("name") if hasattr(uom, "get") else getattr(uom, "name", None)
							)
							uom_name_val = (
								uom.get("uom_name") if hasattr(uom, "get") else getattr(uom, "uom_name", None)
							)

							results["suggestions"].append(
								{
									"uom": uom_name_key,
									"uom_name": uom_name_val,
									"suggested_code": best_suggestion["clave"],
									"suggested_name": best_suggestion["nombre"],
									"confidence": best_suggestion["confidence"],
									"auto_assigned": best_suggestion.get("confidence", 0) >= 90,
								}
							)

				except Exception as e:
					results["errors"] += 1
					uom_name_for_error = (
						uom.get("name") if hasattr(uom, "get") else getattr(uom, "name", "Unknown")
					)
					frappe.log_error(f"Error processing UOM {uom_name_for_error}: {e!s}", "UOM SAT Sync")

			if not dry_run:
				frappe.db.commit()

			return results

		except Exception as e:
			frappe.log_error(f"Error syncing UOM with SAT codes: {e!s}", "UOM SAT Sync")
			return {"error": str(e), "processed": 0}

	def validate_sales_invoice_uom_codes(self, sales_invoice_doc: Any) -> tuple[bool, list[str]]:
		"""
		Validar códigos SAT en items de Sales Invoice
		"""
		try:
			errors = []

			for item in sales_invoice_doc.items:
				uom = item.uom

				# Obtener código SAT de la UOM
				sat_code = frappe.db.get_value("UOM", uom, "custom_clave_unidad_sat")

				if not sat_code:
					errors.append(f"Item {item.item_code}: UOM '{uom}' no tiene código SAT configurado")
					continue

				# Validar código SAT
				is_valid, message, _ = self.validate_uom_sat_code(sat_code)
				if not is_valid:
					errors.append(f"Item {item.item_code}: {message}")

			return len(errors) == 0, errors

		except Exception as e:
			frappe.log_error(f"Error validating sales invoice UOM codes: {e!s}", "UOM SAT Validation")
			return False, [f"Error de validación: {e!s}"]

	def _load_sat_catalog(self) -> list[dict]:
		"""
		Cargar catálogo SAT desde fuente oficial
		"""
		# Catálogo SAT oficial de Unidades de Medida (ejemplo principales)
		sat_catalog = [
			{
				"clave": "KGM",
				"nombre": "Kilogramo",
				"descripcion": "Unidad básica del Sistema Internacional de Unidades para medir masa",
				"simbolo": "kg",
				"activo": True,
			},
			{
				"clave": "GRM",
				"nombre": "Gramo",
				"descripcion": "Submúltiplo del kilogramo",
				"simbolo": "g",
				"activo": True,
			},
			{
				"clave": "H87",
				"nombre": "Pieza",
				"descripcion": "Unidad de medida para elementos individuales",
				"simbolo": "pza",
				"activo": True,
			},
			{
				"clave": "MTR",
				"nombre": "Metro",
				"descripcion": "Unidad básica del Sistema Internacional para medir longitud",
				"simbolo": "m",
				"activo": True,
			},
			{
				"clave": "CMT",
				"nombre": "Centímetro",
				"descripcion": "Submúltiplo del metro",
				"simbolo": "cm",
				"activo": True,
			},
			{
				"clave": "LTR",
				"nombre": "Litro",
				"descripcion": "Unidad de volumen del Sistema Internacional",
				"simbolo": "l",
				"activo": True,
			},
			{
				"clave": "MLT",
				"nombre": "Mililitro",
				"descripcion": "Submúltiplo del litro",
				"simbolo": "ml",
				"activo": True,
			},
			{
				"clave": "MTK",
				"nombre": "Metro cuadrado",
				"descripcion": "Unidad de superficie derivada del metro",
				"simbolo": "m²",
				"activo": True,
			},
			{
				"clave": "MTQ",
				"nombre": "Metro cúbico",
				"descripcion": "Unidad de volumen derivada del metro",
				"simbolo": "m³",
				"activo": True,
			},
			{
				"clave": "SEC",
				"nombre": "Segundo",
				"descripcion": "Unidad básica del Sistema Internacional para medir tiempo",
				"simbolo": "s",
				"activo": True,
			},
			{
				"clave": "MIN",
				"nombre": "Minuto",
				"descripcion": "Múltiplo del segundo",
				"simbolo": "min",
				"activo": True,
			},
			{
				"clave": "HUR",
				"nombre": "Hora",
				"descripcion": "Múltiplo del segundo",
				"simbolo": "h",
				"activo": True,
			},
			{
				"clave": "DAY",
				"nombre": "Día",
				"descripcion": "Período de 24 horas",
				"simbolo": "día",
				"activo": True,
			},
			{
				"clave": "WEE",
				"nombre": "Semana",
				"descripcion": "Período de 7 días",
				"simbolo": "semana",
				"activo": True,
			},
			{
				"clave": "MON",
				"nombre": "Mes",
				"descripcion": "Período de tiempo basado en ciclo lunar",
				"simbolo": "mes",
				"activo": True,
			},
			{
				"clave": "ANN",
				"nombre": "Año",
				"descripcion": "Período de 12 meses",
				"simbolo": "año",
				"activo": True,
			},
			{
				"clave": "E48",
				"nombre": "Servicio",
				"descripcion": "Unidad de medida para servicios",
				"simbolo": "servicio",
				"activo": True,
			},
			{
				"clave": "ACT",
				"nombre": "Actividad",
				"descripcion": "Unidad de medida para actividades",
				"simbolo": "actividad",
				"activo": True,
			},
			{
				"clave": "E51",
				"nombre": "Trabajo",
				"descripcion": "Unidad de medida para trabajos",
				"simbolo": "trabajo",
				"activo": True,
			},
			{
				"clave": "NA",
				"nombre": "No Aplica",
				"descripcion": "Para productos o servicios que no requieren unidad específica",
				"simbolo": "N/A",
				"activo": True,
			},
		]

		# TODO: En implementación real, esto vendría de un archivo JSON
		# o se descargaría del catálogo oficial SAT
		return sat_catalog


# APIs públicas


@frappe.whitelist()
def get_sat_uom_catalog(force_refresh: bool = False) -> dict:
	"""API para obtener catálogo de unidades SAT"""
	try:
		catalog = UOMSATCatalog()
		data = catalog.get_sat_catalog(force_refresh)
		return {"success": True, "data": data, "count": len(data)}
	except Exception as e:
		frappe.log_error(f"Error in get_sat_uom_catalog API: {e!s}", "UOM SAT API")
		return {"success": False, "message": f"Error: {e!s}", "data": []}


@frappe.whitelist()
def validate_sat_code(sat_code: str) -> dict:
	"""API para validar código SAT específico"""
	try:
		catalog = UOMSATCatalog()
		is_valid, message, entry = catalog.validate_uom_sat_code(sat_code)
		return {"success": True, "valid": is_valid, "message": message, "entry": entry}
	except Exception as e:
		frappe.log_error(f"Error in validate_sat_code API: {e!s}", "UOM SAT API")
		return {"success": False, "valid": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def suggest_sat_codes(uom_name: str) -> dict:
	"""API para obtener sugerencias de códigos SAT"""
	try:
		catalog = UOMSATCatalog()
		suggestions = catalog.suggest_sat_code_for_uom(uom_name)
		return {"success": True, "suggestions": suggestions, "count": len(suggestions)}
	except Exception as e:
		frappe.log_error(f"Error in suggest_sat_codes API: {e!s}", "UOM SAT API")
		return {"success": False, "suggestions": [], "message": f"Error: {e!s}"}


@frappe.whitelist()
def sync_uom_sat_codes(dry_run: bool = True) -> dict:
	"""API para sincronizar UOMs con códigos SAT"""
	try:
		catalog = UOMSATCatalog()
		results = catalog.sync_uom_with_sat_codes(dry_run)
		return {"success": True, **results}
	except Exception as e:
		frappe.log_error(f"Error in sync_uom_sat_codes API: {e!s}", "UOM SAT API")
		return {"success": False, "error": f"Error: {e!s}"}


def validate_invoice_uom_sat_codes(sales_invoice_doc) -> tuple[bool, list[str]]:
	"""
	Hook function para validar códigos SAT en Sales Invoice
	Para usar en hooks_handlers/sales_invoice_validate.py
	"""
	try:
		catalog = UOMSATCatalog()
		return catalog.validate_sales_invoice_uom_codes(sales_invoice_doc)
	except Exception as e:
		frappe.log_error(f"Error validating invoice UOM SAT codes: {e!s}", "UOM SAT Hook")
		return False, [f"Error de validación UOM-SAT: {e!s}"]
