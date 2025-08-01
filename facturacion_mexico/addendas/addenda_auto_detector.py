# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Addenda Auto Detector - Sprint 6 Phase 3
Sistema de auto-detección de requerimientos de addenda por cliente
"""

import re
from typing import Any, Optional

import frappe
from frappe import _


class AddendaAutoDetector:
	"""
	Auto-detector de requerimientos de addenda basado en patterns de cliente
	Implementa algoritmo de matching fuzzy y rule-based
	"""

	def __init__(self):
		self.detection_rules = self._load_detection_rules()
		self.addenda_types = self._load_addenda_types()

	def detect_addenda_requirement(self, customer_name: str) -> dict[str, Any]:
		"""
		Detectar si un cliente requiere addenda basado en patterns

		Args:
		    customer_name: Nombre del cliente a analizar

		Returns:
		    dict con detected, addenda_type, confidence, reason
		"""
		try:
			customer_doc = frappe.get_cached_doc("Customer", customer_name)

			# Si ya tiene configuración manual, respetarla
			if customer_doc.get("fm_requires_addenda"):
				return {
					"detected": True,
					"addenda_type": customer_doc.get("fm_addenda_type"),
					"confidence": 100,
					"reason": "Configuración manual existente",
					"auto_detected": False,
				}

			# Ejecutar algoritmo de detección
			detection_result = self._run_detection_algorithm(customer_doc)

			return detection_result

		except frappe.DoesNotExistError:
			return {
				"detected": False,
				"addenda_type": None,
				"confidence": 0,
				"reason": "Cliente no encontrado",
				"auto_detected": False,
			}
		except Exception as e:
			frappe.log_error(f"Error in addenda auto-detection: {e!s}", "Addenda Auto Detector")
			return {
				"detected": False,
				"addenda_type": None,
				"confidence": 0,
				"reason": f"Error en detección: {e!s}",
				"auto_detected": False,
			}

	def _run_detection_algorithm(self, customer_doc) -> dict:
		"""Ejecutar algoritmo de detección con múltiples criterios"""
		best_match = {
			"detected": False,
			"addenda_type": None,
			"confidence": 0,
			"reason": "No se detectó patrón conocido",
			"auto_detected": True,
		}

		# 1. Búsqueda por nombre de empresa
		name_match = self._detect_by_company_name(customer_doc.customer_name)
		if name_match["confidence"] > best_match["confidence"]:
			best_match = name_match

		# 2. Búsqueda por RFC
		if customer_doc.get("tax_id"):
			rfc_match = self._detect_by_rfc(customer_doc.tax_id)
			if rfc_match["confidence"] > best_match["confidence"]:
				best_match = rfc_match

		# 3. Búsqueda por grupo de cliente
		if customer_doc.get("customer_group"):
			group_match = self._detect_by_customer_group(customer_doc.customer_group)
			if group_match["confidence"] > best_match["confidence"]:
				best_match = group_match

		# 4. Búsqueda por territorio
		if customer_doc.get("territory"):
			territory_match = self._detect_by_territory(customer_doc.territory)
			if territory_match["confidence"] > best_match["confidence"]:
				best_match = territory_match

		# 5. Aplicar reglas de negocio adicionales
		business_rules_match = self._apply_business_rules(customer_doc)
		if business_rules_match["confidence"] > best_match["confidence"]:
			best_match = business_rules_match

		return best_match

	def _detect_by_company_name(self, company_name: str) -> dict:
		"""Detectar por nombre de empresa usando patterns conocidos"""
		company_name_upper = company_name.upper()

		# Patterns de empresas conocidas (genérico, no hardcodeado)
		for rule in self.detection_rules.get("company_name_patterns", []):
			pattern = rule["pattern"].upper()
			addenda_type = rule["addenda_type"]
			confidence = rule.get("confidence", 80)

			if pattern in company_name_upper or re.search(pattern, company_name_upper):
				return {
					"detected": True,
					"addenda_type": addenda_type,
					"confidence": confidence,
					"reason": f"Patrón detectado en nombre: '{pattern}'",
					"auto_detected": True,
				}

		return {"detected": False, "confidence": 0, "addenda_type": None, "auto_detected": True}

	def _detect_by_rfc(self, rfc: str) -> dict:
		"""Detectar por RFC usando patterns conocidos"""
		rfc_upper = rfc.upper().strip()

		for rule in self.detection_rules.get("rfc_patterns", []):
			pattern = rule["pattern"].upper()
			addenda_type = rule["addenda_type"]
			confidence = rule.get("confidence", 90)

			if rfc_upper.startswith(pattern) or re.match(pattern, rfc_upper):
				return {
					"detected": True,
					"addenda_type": addenda_type,
					"confidence": confidence,
					"reason": f"Patrón RFC detectado: '{pattern}'",
					"auto_detected": True,
				}

		return {"detected": False, "confidence": 0, "addenda_type": None, "auto_detected": True}

	def _detect_by_customer_group(self, customer_group: str) -> dict:
		"""Detectar por grupo de cliente"""
		for rule in self.detection_rules.get("customer_group_patterns", []):
			if customer_group == rule["customer_group"]:
				return {
					"detected": True,
					"addenda_type": rule["addenda_type"],
					"confidence": rule.get("confidence", 70),
					"reason": f"Grupo de cliente: '{customer_group}'",
					"auto_detected": True,
				}

		return {"detected": False, "confidence": 0, "addenda_type": None, "auto_detected": True}

	def _detect_by_territory(self, territory: str) -> dict:
		"""Detectar por territorio (para addendas regionales)"""
		for rule in self.detection_rules.get("territory_patterns", []):
			if territory == rule["territory"]:
				return {
					"detected": True,
					"addenda_type": rule["addenda_type"],
					"confidence": rule.get("confidence", 60),
					"reason": f"Territorio: '{territory}'",
					"auto_detected": True,
				}

		return {"detected": False, "confidence": 0, "addenda_type": None, "auto_detected": True}

	def _apply_business_rules(self, customer_doc) -> dict:
		"""Aplicar reglas de negocio específicas"""
		# Ejemplo: Si el cliente tiene muchas transacciones grandes, podría requerir addenda específica
		try:
			# Obtener estadísticas del cliente
			total_invoices = frappe.db.count("Sales Invoice", {"customer": customer_doc.name, "docstatus": 1})

			if total_invoices > 100:  # Cliente frecuente
				avg_amount = (
					frappe.db.sql(
						"""
                    SELECT AVG(grand_total)
                    FROM `tabSales Invoice`
                    WHERE customer = %s AND docstatus = 1
                """,
						customer_doc.name,
					)[0][0]
					or 0
				)

				if avg_amount > 1000000:  # Facturas grandes (>1M)
					return {
						"detected": True,
						"addenda_type": "CORPORATIVO_PREMIUM",  # Tipo genérico
						"confidence": 50,
						"reason": "Cliente corporativo con transacciones grandes",
						"auto_detected": True,
					}

		except Exception as e:
			frappe.log_error(f"Error in business rules detection: {e!s}", "Business Rules Detection")

		return {"detected": False, "confidence": 0, "addenda_type": None, "auto_detected": True}

	def _load_detection_rules(self) -> dict:
		"""Cargar reglas de detección desde configuración"""
		try:
			# Intentar cargar desde custom settings o file
			rules_setting = frappe.get_single("Facturacion Mexico Settings")

			if hasattr(rules_setting, "addenda_detection_rules") and rules_setting.addenda_detection_rules:
				import json

				return json.loads(rules_setting.addenda_detection_rules)

			# Reglas por defecto (ejemplos genéricos)
			return {
				"company_name_patterns": [
					{"pattern": "WALMART", "addenda_type": "WALMART", "confidence": 95},
					{"pattern": "FEMSA", "addenda_type": "FEMSA", "confidence": 95},
					{"pattern": "SORIANA", "addenda_type": "SORIANA", "confidence": 95},
					{"pattern": "CHEDRAUI", "addenda_type": "CHEDRAUI", "confidence": 95},
					{"pattern": "COMERCIAL MEXICANA", "addenda_type": "COMERCI", "confidence": 90},
					{"pattern": "HOME DEPOT", "addenda_type": "HOME_DEPOT", "confidence": 90},
					{"pattern": "LIVERPOOL", "addenda_type": "LIVERPOOL", "confidence": 90},
				],
				"rfc_patterns": [
					{"pattern": "WME", "addenda_type": "WALMART", "confidence": 98},
					{"pattern": "FEM", "addenda_type": "FEMSA", "confidence": 98},
					{"pattern": "OSO", "addenda_type": "SORIANA", "confidence": 98},
				],
				"customer_group_patterns": [
					{"customer_group": "Retail Chains", "addenda_type": "RETAIL_GENERIC", "confidence": 60},
					{"customer_group": "Corporate", "addenda_type": "CORPORATIVO", "confidence": 50},
				],
				"territory_patterns": [],
			}

		except Exception as e:
			frappe.log_error(f"Error loading detection rules: {e!s}", "Detection Rules Loading")
			return {
				"company_name_patterns": [],
				"rfc_patterns": [],
				"customer_group_patterns": [],
				"territory_patterns": [],
			}

	def _load_addenda_types(self) -> list:
		"""Cargar tipos de addenda activos"""
		try:
			return frappe.get_all(
				"Addenda Type", filters={"is_active": 1}, fields=["name", "description", "version"]
			)
		except Exception as e:
			frappe.log_error(f"Error loading addenda types: {e!s}", "Addenda Types Loading")
			return []

	def apply_auto_detection_to_customer(self, customer_name: str) -> dict:
		"""Aplicar auto-detección y actualizar configuración del cliente"""
		try:
			detection_result = self.detect_addenda_requirement(customer_name)

			if detection_result["detected"] and detection_result["auto_detected"]:
				# Actualizar configuración del cliente
				frappe.db.set_value(
					"Customer",
					customer_name,
					{
						"fm_requires_addenda": 1,
						"fm_addenda_type": detection_result["addenda_type"],
						"fm_addenda_auto_detected": 1,
					},
				)

				frappe.db.commit()

				return {
					"success": True,
					"message": f"Auto-detección aplicada: {detection_result['reason']}",
					"detection_result": detection_result,
				}
			else:
				return {
					"success": False,
					"message": "No se detectó requerimiento de addenda",
					"detection_result": detection_result,
				}

		except Exception as e:
			frappe.log_error(f"Error applying auto-detection: {e!s}", "Auto Detection Application")
			return {"success": False, "message": f"Error: {e!s}", "detection_result": None}

	def bulk_auto_detect(self, limit: int = 100) -> dict:
		"""Ejecutar auto-detección en lote para clientes sin configuración"""
		try:
			# Obtener clientes sin configuración de addenda
			customers = frappe.get_all(
				"Customer",
				filters={"fm_requires_addenda": ["!=", 1]},
				fields=["name", "customer_name"],
				limit=limit,
			)

			results = {"processed": 0, "detected": 0, "errors": 0, "details": []}

			for customer in customers:
				try:
					result = self.apply_auto_detection_to_customer(customer.name)
					results["processed"] += 1

					if result["success"]:
						results["detected"] += 1

					results["details"].append(
						{
							"customer": customer.name,
							"success": result["success"],
							"message": result["message"],
						}
					)

				except Exception as e:
					results["errors"] += 1
					results["details"].append(
						{"customer": customer.name, "success": False, "message": f"Error: {e!s}"}
					)

			return results

		except Exception as e:
			frappe.log_error(f"Error in bulk auto-detection: {e!s}", "Bulk Auto Detection")
			return {
				"processed": 0,
				"detected": 0,
				"errors": 1,
				"details": [{"error": f"Error general: {e!s}"}],
			}


# APIs públicas
@frappe.whitelist()
def detect_customer_addenda_requirement(customer: str) -> dict:
	"""API para detectar requerimiento de addenda de un cliente"""
	try:
		detector = AddendaAutoDetector()
		result = detector.detect_addenda_requirement(customer)
		return {"success": True, "detection_result": result}
	except Exception as e:
		frappe.log_error(
			f"Error in detect_customer_addenda_requirement API: {e!s}", "Addenda Auto Detector API"
		)
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def apply_auto_detection(customer: str) -> dict:
	"""API para aplicar auto-detección a un cliente"""
	try:
		detector = AddendaAutoDetector()
		return detector.apply_auto_detection_to_customer(customer)
	except Exception as e:
		frappe.log_error(f"Error in apply_auto_detection API: {e!s}", "Addenda Auto Detector API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def bulk_auto_detect_customers(limit: int = 50) -> dict:
	"""API para auto-detección en lote"""
	try:
		detector = AddendaAutoDetector()
		return detector.bulk_auto_detect(limit)
	except Exception as e:
		frappe.log_error(f"Error in bulk_auto_detect_customers API: {e!s}", "Addenda Auto Detector API")
		return {"success": False, "message": f"Error: {e!s}"}


# Hook para auto-detección en creación/actualización de Customer
def customer_after_insert(doc, method):
	"""Hook que se ejecuta después de crear un cliente"""
	try:
		# Solo auto-detectar si no tiene configuración manual
		if not doc.get("fm_requires_addenda"):
			detector = AddendaAutoDetector()
			detection_result = detector.detect_addenda_requirement(doc.name)

			# Si se detecta con alta confianza (>80%), aplicar automáticamente
			if detection_result["detected"] and detection_result["confidence"] > 80:
				doc.fm_requires_addenda = 1
				doc.fm_addenda_type = detection_result["addenda_type"]
				doc.fm_addenda_auto_detected = 1
				doc.save()

				frappe.msgprint(
					_("Auto-detectado requerimiento de addenda: {0}").format(detection_result["reason"]),
					title=_("Addenda Auto-detectada"),
					indicator="blue",
				)

	except Exception as e:
		# No fallar la creación del cliente por error en auto-detección
		frappe.log_error(f"Error in customer auto-detection hook: {e!s}", "Customer Auto Detection Hook")
