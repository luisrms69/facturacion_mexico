# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Branch Auto Selector - Sprint 6 Phase 2 Step 5
Auto-selección inteligente de sucursal por usuario en Sales Invoice
"""

from typing import Any

import frappe
from frappe import _

from .branch_manager import BranchManager


class BranchAutoSelector:
	"""
	Selector automático de sucursal para Sales Invoice
	Basado en usuario, configuraciones y disponibilidad de recursos
	"""

	def __init__(self, company: str, user: str | None = None):
		self.company = company
		self.user = user or frappe.session.user
		self.branch_manager = BranchManager(company)

	def select_best_branch_for_invoice(self, sales_invoice_doc: Any = None) -> dict[str, Any]:
		"""
		Seleccionar la mejor sucursal para una factura
		"""
		try:
			# Obtener sucursales fiscales disponibles
			available_branches = self.branch_manager.get_fiscal_branches()

			if not available_branches:
				return {
					"success": False,
					"message": "No hay sucursales fiscales configuradas",
					"branch": None,
					"auto_selected": False,
				}

			# Evaluar sucursales y seleccionar la mejor
			best_branch = self._evaluate_and_select_branch(available_branches, sales_invoice_doc)

			if best_branch:
				return {
					"success": True,
					"message": f"Sucursal {best_branch['name']} seleccionada automáticamente",
					"branch": best_branch["name"],
					"branch_name": best_branch["branch"],
					"lugar_expedicion": best_branch.get("fm_lugar_expedicion"),
					"auto_selected": True,
					"selection_criteria": best_branch.get("selection_reason", "Mejor opción disponible"),
				}
			else:
				return {
					"success": False,
					"message": "No se pudo seleccionar sucursal automáticamente",
					"branch": None,
					"auto_selected": False,
				}

		except Exception as e:
			frappe.log_error(f"Error in branch auto selection: {e!s}", "Branch Auto Selector")
			return {
				"success": False,
				"message": f"Error en auto-selección: {e!s}",
				"branch": None,
				"auto_selected": False,
			}

	def get_user_preferred_branches(self) -> list[dict]:
		"""
		Obtener sucursales preferidas por el usuario
		"""
		try:
			# Buscar en configuraciones del usuario
			user_preferences = frappe.get_all(
				"User Permission",
				filters={"user": self.user, "document_type": "Branch", "allow": "Branch"},
				fields=["for_value as branch"],
			)

			preferred_branches = []
			for pref in user_preferences:
				branch_data = frappe.get_value(
					"Branch",
					pref.branch,
					["name", "branch", "fm_enable_fiscal", "fm_lugar_expedicion"],
					as_dict=True,
				)

				if branch_data and branch_data.get("fm_enable_fiscal"):
					preferred_branches.append(branch_data)

			return preferred_branches

		except Exception as e:
			frappe.log_error(f"Error getting user preferred branches: {e!s}", "User Branch Preferences")
			return []

	def _evaluate_and_select_branch(
		self, available_branches: list[dict], sales_invoice_doc: Any = None
	) -> dict | None:
		"""
		Evaluar sucursales disponibles y seleccionar la mejor
		"""
		try:
			# Obtener sucursales preferidas del usuario
			user_preferred = self.get_user_preferred_branches()
			user_preferred_names = [b["name"] for b in user_preferred]

			# Lista de candidatos con puntuación
			candidates = []

			for branch in available_branches:
				score = self._calculate_branch_score(branch, user_preferred_names, sales_invoice_doc)
				candidates.append(
					{
						**branch,
						"score": score,
						"selection_reason": self._get_selection_reason(branch, score, user_preferred_names),
					}
				)

			# Ordenar por puntuación (descendente)
			candidates.sort(key=lambda x: x["score"], reverse=True)

			# Filtrar candidatos válidos (score > 0)
			valid_candidates = [c for c in candidates if c["score"] > 0]

			if not valid_candidates:
				return None

			# Retornar el mejor candidato
			return valid_candidates[0]

		except Exception as e:
			frappe.log_error(f"Error evaluating branches: {e!s}", "Branch Evaluation")
			return None

	def _calculate_branch_score(
		self, branch: dict, user_preferred_names: list[str], sales_invoice_doc: Any = None
	) -> int:
		"""
		Calcular puntuación para una sucursal
		"""
		try:
			score = 0

			# Base score for fiscal enabled branches
			if branch.get("fm_enable_fiscal"):
				score += 10

			# Bonus por preferencia del usuario
			if branch["name"] in user_preferred_names:
				score += 50

			# Evaluar estado de salud de la sucursal
			health_status = self._get_branch_health_status(branch["name"])

			if health_status.get("semaforo") == "verde":
				score += 30
			elif health_status.get("semaforo") == "amarillo":
				score += 15
			# Sucursales rojas obtienen penalización
			elif health_status.get("semaforo") == "rojo":
				score -= 20

			# Evaluar disponibilidad de folios
			folio_status = health_status.get("can_generate", False)
			if folio_status:
				score += 20
			else:
				score -= 30  # Penalización fuerte por no poder generar folios

			# Bonus por tener configuración de lugar de expedición
			if branch.get("fm_lugar_expedicion"):
				score += 10

			# Bonus por tener patrón de serie configurado
			if branch.get("fm_serie_pattern"):
				score += 5

			# Evaluación específica basada en la factura
			if sales_invoice_doc:
				invoice_score = self._calculate_invoice_specific_score(branch, sales_invoice_doc)
				score += invoice_score

			return max(0, score)  # Asegurar que el score no sea negativo

		except Exception as e:
			frappe.log_error(f"Error calculating branch score: {e!s}", "Branch Score Calculation")
			return 0

	def _get_branch_health_status(self, branch_name: str) -> dict:
		"""
		Obtener estado de salud de la sucursal usando BranchFolioManager
		"""
		try:
			from .branch_folio_manager import BranchFolioManager

			folio_manager = BranchFolioManager(branch_name)
			return folio_manager.get_folio_status()

		except Exception as e:
			frappe.log_error(f"Error getting branch health status: {e!s}", "Branch Health Status")
			return {"semaforo": "rojo", "can_generate": False}

	def _calculate_invoice_specific_score(self, branch: dict, sales_invoice_doc: Any) -> int:
		"""
		Calcular puntuación específica basada en características de la factura
		"""
		try:
			score = 0

			# Si la factura ya tiene una sucursal asignada, dar preferencia
			if hasattr(sales_invoice_doc, "fm_branch") and sales_invoice_doc.fm_branch == branch["name"]:
				score += 100  # Fuerte preferencia por sucursal ya asignada

			# Evaluar por monto de la factura
			if hasattr(sales_invoice_doc, "grand_total"):
				grand_total = sales_invoice_doc.grand_total or 0

				# Sucursales con más folios disponibles para facturas grandes
				if grand_total > 100000:  # Facturas grandes
					remaining_folios = branch.get("fm_folio_end", 0) - branch.get("fm_folio_current", 0)
					if remaining_folios > 1000:
						score += 15

			# Evaluar por cliente
			if hasattr(sales_invoice_doc, "customer"):
				# TODO: Implementar lógica de preferencia por cliente/zona geográfica
				pass

			return score

		except Exception as e:
			frappe.log_error(f"Error calculating invoice specific score: {e!s}", "Invoice Score Calculation")
			return 0

	def _get_selection_reason(self, branch: dict, score: int, user_preferred_names: list[str]) -> str:
		"""
		Obtener razón de selección para logging/debugging
		"""
		reasons = []

		if branch["name"] in user_preferred_names:
			reasons.append("preferencia del usuario")

		if score >= 80:
			reasons.append("estado excelente")
		elif score >= 50:
			reasons.append("estado bueno")
		elif score >= 20:
			reasons.append("estado aceptable")

		if branch.get("fm_lugar_expedicion"):
			reasons.append("lugar expedición configurado")

		if not reasons:
			reasons.append("opción por defecto")

		return ", ".join(reasons)

	def validate_branch_selection(self, branch_name: str, sales_invoice_doc: Any = None) -> tuple[bool, str]:
		"""
		Validar que una sucursal es válida para una factura
		"""
		try:
			# Verificar que la sucursal existe y está habilitada
			branch_doc = frappe.get_value(
				"Branch", branch_name, ["fm_enable_fiscal", "company"], as_dict=True
			)

			if not branch_doc:
				return False, f"Sucursal {branch_name} no encontrada"

			if not branch_doc.get("fm_enable_fiscal"):
				return False, f"Sucursal {branch_name} no está habilitada para facturación fiscal"

			if branch_doc.get("company") != self.company:
				return False, f"Sucursal {branch_name} no pertenece a la empresa {self.company}"

			# Verificar estado de salud
			health_status = self._get_branch_health_status(branch_name)
			if not health_status.get("can_generate", False):
				return (
					False,
					f"Sucursal {branch_name} no puede generar folios: {health_status.get('message', 'Estado crítico')}",
				)

			return True, "Sucursal válida para facturación"

		except Exception as e:
			frappe.log_error(f"Error validating branch selection: {e!s}", "Branch Selection Validation")
			return False, f"Error validando sucursal: {e!s}"


# APIs públicas


@frappe.whitelist()
def auto_select_branch_for_invoice(company: str, sales_invoice: str | None = None) -> dict:
	"""API para auto-selección de sucursal"""
	try:
		selector = BranchAutoSelector(company)

		# Cargar documento de factura si se proporciona
		sales_invoice_doc = None
		if sales_invoice:
			sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)

		result = selector.select_best_branch_for_invoice(sales_invoice_doc)
		return result

	except Exception as e:
		frappe.log_error(f"Error in auto_select_branch_for_invoice API: {e!s}", "Branch Auto Selector API")
		return {"success": False, "message": f"Error: {e!s}", "branch": None, "auto_selected": False}


@frappe.whitelist()
def get_user_preferred_branches(company: str) -> dict:
	"""API para obtener sucursales preferidas del usuario"""
	try:
		selector = BranchAutoSelector(company)
		branches = selector.get_user_preferred_branches()
		return {"success": True, "data": branches, "count": len(branches)}

	except Exception as e:
		frappe.log_error(f"Error in get_user_preferred_branches API: {e!s}", "Branch Auto Selector API")
		return {"success": False, "message": f"Error: {e!s}", "data": []}


@frappe.whitelist()
def validate_branch_for_invoice(company: str, branch: str, sales_invoice: str | None = None) -> dict:
	"""API para validar sucursal para factura"""
	try:
		selector = BranchAutoSelector(company)

		sales_invoice_doc = None
		if sales_invoice:
			sales_invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)

		is_valid, message = selector.validate_branch_selection(branch, sales_invoice_doc)
		return {"success": True, "valid": is_valid, "message": message}

	except Exception as e:
		frappe.log_error(f"Error in validate_branch_for_invoice API: {e!s}", "Branch Auto Selector API")
		return {"success": False, "valid": False, "message": f"Error: {e!s}"}
