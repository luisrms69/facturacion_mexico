# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
UOM SAT Mapper - Sprint 6 Phase 4
Motor de mapeo inteligente entre UOM de ERPNext y catálogo SAT
"""

import difflib
import re
from typing import Any, Optional

import frappe
from frappe import _


class UOMSATMapper:
	"""
	Motor de mapeo inteligente UOM-SAT con algoritmo fuzzy matching
	Implementa múltiples estrategias de matching para sugerir mapeos automáticos
	"""

	def __init__(self):
		self.sat_catalog = self._load_sat_catalog()
		self.mapping_rules = self._load_mapping_rules()
		self.confidence_threshold = 70

	def suggest_mapping(self, uom_name: str) -> dict[str, Any]:
		"""
		Sugerir mapeo SAT para una UOM basado en algoritmo inteligente

		Args:
		    uom_name: Nombre de la UOM a mapear

		Returns:
		    dict con suggested_mapping, confidence, reason
		"""
		try:
			# Normalizar nombre de UOM
			normalized_uom = self._normalize_uom_name(uom_name)

			# 1. Exact match (máxima confianza)
			exact_match = self._exact_match(normalized_uom)
			if exact_match:
				return {
					"suggested_mapping": exact_match["clave"],
					"confidence": 100,
					"reason": f"Coincidencia exacta con '{exact_match['descripcion']}'",
					"sat_description": exact_match["descripcion"],
				}

			# 2. Fuzzy match con threshold
			fuzzy_match = self._fuzzy_match(normalized_uom)
			if fuzzy_match and fuzzy_match["confidence"] >= self.confidence_threshold:
				return {
					"suggested_mapping": fuzzy_match["clave"],
					"confidence": fuzzy_match["confidence"],
					"reason": f"Coincidencia difusa con '{fuzzy_match['descripcion']}'",
					"sat_description": fuzzy_match["descripcion"],
				}

			# 3. Rule-based matching
			rule_match = self._rule_based_match(normalized_uom)
			if rule_match and rule_match["confidence"] >= self.confidence_threshold:
				return {
					"suggested_mapping": rule_match["clave"],
					"confidence": rule_match["confidence"],
					"reason": f"Regla aplicada: {rule_match['rule_name']}",
					"sat_description": rule_match["descripcion"],
				}

			# 4. Pattern matching
			pattern_match = self._pattern_match(normalized_uom)
			if pattern_match and pattern_match["confidence"] >= self.confidence_threshold:
				return {
					"suggested_mapping": pattern_match["clave"],
					"confidence": pattern_match["confidence"],
					"reason": f"Patrón detectado: {pattern_match['pattern']}",
					"sat_description": pattern_match["descripcion"],
				}

			return {
				"suggested_mapping": None,
				"confidence": 0,
				"reason": "No se encontró mapeo con confianza suficiente",
				"sat_description": None,
			}

		except Exception as e:
			frappe.log_error(f"Error en suggest_mapping: {e!s}", "UOM SAT Mapper")
			return {
				"suggested_mapping": None,
				"confidence": 0,
				"reason": f"Error en mapeo: {e!s}",
				"sat_description": None,
			}

	def bulk_map_uoms(self, confidence_threshold: int = 80, auto_apply: bool = False) -> dict:
		"""
		Mapear todas las UOMs sin clasificación SAT en lote

		Args:
		    confidence_threshold: Umbral mínimo de confianza
		    auto_apply: Si aplicar automáticamente los mapeos

		Returns:
		    dict con estadísticas del mapeo masivo
		"""
		try:
			# Obtener UOMs sin mapeo SAT
			unmapped_uoms = frappe.get_all(
				"UOM", filters={"fm_clave_sat": ["is", "not set"]}, fields=["name", "uom_name"]
			)

			results = {"processed": 0, "mapped": 0, "auto_applied": 0, "suggestions": [], "errors": 0}

			for uom in unmapped_uoms:
				try:
					suggestion = self.suggest_mapping(uom.uom_name)
					results["processed"] += 1

					if suggestion["confidence"] >= confidence_threshold:
						results["mapped"] += 1

						suggestion_data = {
							"uom": uom.name,
							"uom_name": uom.uom_name,
							"suggested_mapping": suggestion["suggested_mapping"],
							"confidence": suggestion["confidence"],
							"reason": suggestion["reason"],
							"sat_description": suggestion.get("sat_description"),
						}

						results["suggestions"].append(suggestion_data)

						# Auto-aplicar si se solicita y confianza es alta
						if auto_apply and suggestion["confidence"] >= 90:
							self._apply_mapping(uom.name, suggestion)
							results["auto_applied"] += 1

				except Exception as e:
					results["errors"] += 1
					frappe.log_error(f"Error mapeando UOM '{uom.name}': {e!s}", "Bulk UOM Mapping")

			return results

		except Exception as e:
			frappe.log_error(f"Error en bulk_map_uoms: {e!s}", "UOM SAT Mapper")
			return {"processed": 0, "mapped": 0, "auto_applied": 0, "suggestions": [], "errors": 1}

	def _exact_match(self, uom_name: str) -> dict | None:
		"""Búsqueda de coincidencia exacta"""
		for sat_uom in self.sat_catalog:
			if uom_name.lower() == sat_uom["descripcion"].lower():
				return sat_uom
			# También verificar por clave
			if uom_name.upper() == sat_uom["clave"].upper():
				return sat_uom
		return None

	def _fuzzy_match(self, uom_name: str) -> dict | None:
		"""Búsqueda difusa usando difflib"""
		best_match = None
		best_ratio = 0

		for sat_uom in self.sat_catalog:
			# Comparar con descripción
			ratio_desc = difflib.SequenceMatcher(
				None, uom_name.lower(), sat_uom["descripcion"].lower()
			).ratio()

			# Comparar con clave
			ratio_clave = difflib.SequenceMatcher(None, uom_name.upper(), sat_uom["clave"].upper()).ratio()

			# Tomar el mejor ratio
			ratio = max(ratio_desc, ratio_clave)

			if ratio > best_ratio:
				best_ratio = ratio
				best_match = sat_uom.copy()
				best_match["confidence"] = int(ratio * 100)

		# Solo retornar si supera umbral mínimo
		if best_match and best_match["confidence"] >= 60:
			return best_match

		return None

	def _rule_based_match(self, uom_name: str) -> dict | None:
		"""Aplicar reglas de mapeo predefinidas"""
		for rule in self.mapping_rules:
			if self._match_rule(uom_name, rule):
				# Buscar la unidad SAT correspondiente
				sat_uom = self._find_sat_by_clave(rule["target_clave"])
				if sat_uom:
					result = sat_uom.copy()
					result["confidence"] = rule["confidence"]
					result["rule_name"] = rule["name"]
					return result

		return None

	def _pattern_match(self, uom_name: str) -> dict | None:
		"""Detectar patrones comunes en nombres de UOM"""
		patterns = [
			# Patrones de peso
			{
				"pattern": r"\b(kg|kilo|kilogram)\b",
				"target_clave": "KGM",
				"confidence": 85,
				"name": "Peso - Kilogramo",
			},
			{
				"pattern": r"\b(g|gram|gramo)\b",
				"target_clave": "GRM",
				"confidence": 85,
				"name": "Peso - Gramo",
			},
			# Patrones de longitud
			{
				"pattern": r"\b(m|metro|meter)\b",
				"target_clave": "MTR",
				"confidence": 85,
				"name": "Longitud - Metro",
			},
			{
				"pattern": r"\b(cm|centimetro|centimeter)\b",
				"target_clave": "CMT",
				"confidence": 85,
				"name": "Longitud - Centímetro",
			},
			# Patrones de volumen
			{
				"pattern": r"\b(l|lt|ltr|litro|liter)\b",
				"target_clave": "LTR",
				"confidence": 85,
				"name": "Volumen - Litro",
			},
			# Patrones de cantidad
			{
				"pattern": r"\b(pz|pza|pieza|piece|unit)\b",
				"target_clave": "H87",
				"confidence": 80,
				"name": "Cantidad - Pieza",
			},
		]

		for pattern_def in patterns:
			if re.search(pattern_def["pattern"], uom_name.lower()):
				sat_uom = self._find_sat_by_clave(pattern_def["target_clave"])
				if sat_uom:
					result = sat_uom.copy()
					result["confidence"] = pattern_def["confidence"]
					result["pattern"] = pattern_def["name"]
					return result

		return None

	def _normalize_uom_name(self, uom_name: str) -> str:
		"""Normalizar nombre de UOM para comparación"""
		# Remover caracteres especiales y espacios extra
		normalized = re.sub(r"[^\w\s]", "", uom_name)
		normalized = re.sub(r"\s+", " ", normalized).strip()
		return normalized

	def _match_rule(self, uom_name: str, rule: dict) -> bool:
		"""Verificar si una UOM coincide con una regla"""
		rule_type = rule.get("type", "contains")

		if rule_type == "contains":
			return rule["pattern"].lower() in uom_name.lower()
		elif rule_type == "starts_with":
			return uom_name.lower().startswith(rule["pattern"].lower())
		elif rule_type == "ends_with":
			return uom_name.lower().endswith(rule["pattern"].lower())
		elif rule_type == "regex":
			return bool(re.search(rule["pattern"], uom_name, re.IGNORECASE))

		return False

	def _find_sat_by_clave(self, clave: str) -> dict | None:
		"""Buscar unidad SAT por clave"""
		for sat_uom in self.sat_catalog:
			if sat_uom["clave"] == clave:
				return sat_uom
		return None

	def _apply_mapping(self, uom_name: str, suggestion: dict):
		"""Aplicar mapeo sugerido a una UOM"""
		try:
			frappe.db.set_value(
				"UOM",
				uom_name,
				{
					"fm_clave_sat": suggestion["suggested_mapping"],
					"fm_mapping_confidence": suggestion["confidence"],
					"fm_mapping_source": "Auto",
					"fm_last_sync_date": frappe.utils.today(),
				},
			)
			frappe.db.commit()
		except Exception as e:
			frappe.log_error(f"Error aplicando mapeo a UOM '{uom_name}': {e!s}", "Apply UOM Mapping")

	def _load_sat_catalog(self) -> list[dict]:
		"""Cargar catálogo de unidades SAT"""
		try:
			# Intentar cargar desde DocType Unidad Medida SAT
			if frappe.db.exists("DocType", "Unidad Medida SAT"):
				return frappe.get_all(
					"Unidad Medida SAT",
					fields=["name as clave", "descripcion", "simbolo"],
					filters={"disabled": 0},
				)

			# Catálogo básico hardcoded como fallback
			return [
				{"clave": "H87", "descripcion": "Pieza", "simbolo": "Pza"},
				{"clave": "KGM", "descripcion": "Kilogramo", "simbolo": "kg"},
				{"clave": "GRM", "descripcion": "Gramo", "simbolo": "g"},
				{"clave": "MTR", "descripcion": "Metro", "simbolo": "m"},
				{"clave": "CMT", "descripcion": "Centímetro", "simbolo": "cm"},
				{"clave": "LTR", "descripcion": "Litro", "simbolo": "l"},
				{"clave": "MTQ", "descripcion": "Metro cúbico", "simbolo": "m³"},
				{"clave": "KWT", "descripcion": "Kilowatt", "simbolo": "kW"},
				{"clave": "HUR", "descripcion": "Hora", "simbolo": "hr"},
				{"clave": "DAY", "descripcion": "Día", "simbolo": "día"},
			]

		except Exception as e:
			frappe.log_error(f"Error cargando catálogo SAT: {e!s}", "UOM SAT Catalog")
			return []

	def _load_mapping_rules(self) -> list[dict]:
		"""Cargar reglas de mapeo personalizadas"""
		try:
			# Intentar cargar desde configuración
			settings = frappe.get_single("Facturacion Mexico Settings")
			if hasattr(settings, "uom_mapping_rules") and settings.uom_mapping_rules:
				import json

				return json.loads(settings.uom_mapping_rules)

			# Reglas por defecto
			return [
				{
					"name": "Unidades",
					"type": "contains",
					"pattern": "unidad",
					"target_clave": "H87",
					"confidence": 85,
				},
				{
					"name": "Piezas",
					"type": "contains",
					"pattern": "pieza",
					"target_clave": "H87",
					"confidence": 90,
				},
				{
					"name": "Cajas",
					"type": "contains",
					"pattern": "caja",
					"target_clave": "XBX",
					"confidence": 80,
				},
				{
					"name": "Paquetes",
					"type": "contains",
					"pattern": "paquete",
					"target_clave": "XPK",
					"confidence": 80,
				},
				{
					"name": "Servicios",
					"type": "contains",
					"pattern": "servicio",
					"target_clave": "E48",
					"confidence": 75,
				},
			]

		except Exception as e:
			frappe.log_error(f"Error cargando reglas de mapeo: {e!s}", "UOM Mapping Rules")
			return []


# APIs públicas
@frappe.whitelist()
def suggest_uom_mapping(uom_name: str) -> dict:
	"""API para sugerir mapeo SAT de una UOM"""
	try:
		mapper = UOMSATMapper()
		return {"success": True, "suggestion": mapper.suggest_mapping(uom_name)}
	except Exception as e:
		frappe.log_error(f"Error in suggest_uom_mapping API: {e!s}", "UOM SAT Mapper API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def bulk_map_uoms_api(confidence_threshold: int = 80, auto_apply: bool = False) -> dict:
	"""API para mapeo masivo de UOMs"""
	try:
		mapper = UOMSATMapper()
		results = mapper.bulk_map_uoms(confidence_threshold, auto_apply)
		return {"success": True, "results": results}
	except Exception as e:
		frappe.log_error(f"Error in bulk_map_uoms_api: {e!s}", "UOM SAT Mapper API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def apply_uom_mapping(uom_name: str, sat_clave: str, confidence: int = 100, source: str = "Manual") -> dict:
	"""API para aplicar mapeo SAT a una UOM"""
	try:
		frappe.db.set_value(
			"UOM",
			uom_name,
			{
				"fm_clave_sat": sat_clave,
				"fm_mapping_confidence": confidence,
				"fm_mapping_source": source,
				"fm_last_sync_date": frappe.utils.today(),
			},
		)
		frappe.db.commit()

		return {"success": True, "message": f"Mapeo aplicado exitosamente a UOM '{uom_name}'"}

	except Exception as e:
		frappe.log_error(f"Error in apply_uom_mapping API: {e!s}", "UOM SAT Mapper API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_uom_mapping_status() -> dict:
	"""API para obtener estado del mapeo UOM-SAT"""
	try:
		total_uoms = frappe.db.count("UOM")
		mapped_uoms = frappe.db.count("UOM", {"fm_clave_sat": ["is", "set"]})
		auto_mapped = frappe.db.count("UOM", {"fm_mapping_source": "Auto"})
		verified_mapped = frappe.db.count("UOM", {"fm_mapping_verified": 1})

		return {
			"success": True,
			"status": {
				"total_uoms": total_uoms,
				"mapped_uoms": mapped_uoms,
				"unmapped_uoms": total_uoms - mapped_uoms,
				"mapping_percentage": round((mapped_uoms / total_uoms) * 100, 2) if total_uoms > 0 else 0,
				"auto_mapped": auto_mapped,
				"verified_mapped": verified_mapped,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error in get_uom_mapping_status API: {e!s}", "UOM SAT Mapper API")
		return {"success": False, "message": f"Error: {e!s}"}
