# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Branch Folio Manager - Sprint 6 Phase 2 Step 7
Sistema de gestión de series y folios por sucursal con semáforos
"""

from typing import Any, Optional

import frappe
from frappe import _


class BranchFolioManager:
	"""
	Gestor de folios y series por sucursal
	Implementa sistema de semáforos (verde/amarillo/rojo) y reserva/liberación
	"""

	def __init__(self, branch: str):
		self.branch = branch
		self.branch_doc = None
		self._folio_status_cache = None

	def get_folio_status(self) -> dict[str, Any]:
		"""
		Obtener estado actual de folios con sistema de semáforos
		"""
		try:
			if self._folio_status_cache is None:
				self._folio_status_cache = self._calculate_folio_status()

			return self._folio_status_cache

		except Exception as e:
			frappe.log_error(
				f"Error getting folio status for branch {self.branch}: {e!s}", "Branch Folio Manager"
			)
			return self._get_error_status()

	def reserve_next_folio(self, sales_invoice_name: str) -> dict[str, Any]:
		"""
		Reservar siguiente folio disponible para una factura
		"""
		try:
			# Verificar que la sucursal puede generar folios
			status = self.get_folio_status()
			if status["semaforo"] == "rojo":
				return {
					"success": False,
					"message": "La sucursal no tiene folios disponibles",
					"folio": None,
					"serie_folio": None,
				}

			# Obtener datos de la sucursal
			branch_doc = self._get_branch_doc()
			current_folio = branch_doc.get("fm_folio_current", 0)
			end_folio = branch_doc.get("fm_folio_end", 0)
			serie_pattern = branch_doc.get("fm_serie_pattern", "A{####}")

			# Calcular siguiente folio
			next_folio = current_folio + 1

			if end_folio > 0 and next_folio > end_folio:
				return {
					"success": False,
					"message": f"Se alcanzó el límite de folios ({end_folio})",
					"folio": None,
					"serie_folio": None,
				}

			# Generar serie y folio
			serie_folio = self._generate_serie_folio(serie_pattern, next_folio)

			# Actualizar folio actual en la sucursal
			frappe.db.set_value("Branch", self.branch, "fm_folio_current", next_folio)

			# Crear registro de reserva
			self._create_folio_reservation(sales_invoice_name, next_folio, serie_folio)

			# Limpiar cache
			self._folio_status_cache = None

			return {
				"success": True,
				"message": f"Folio {serie_folio} reservado exitosamente",
				"folio": next_folio,
				"serie_folio": serie_folio,
				"semaforo_status": self.get_folio_status()["semaforo"],
			}

		except Exception as e:
			frappe.log_error(
				f"Error reserving folio for branch {self.branch}: {e!s}", "Branch Folio Reservation"
			)
			return {
				"success": False,
				"message": f"Error reservando folio: {e!s}",
				"folio": None,
				"serie_folio": None,
			}

	def release_folio(self, sales_invoice_name: str) -> dict[str, Any]:
		"""
		Liberar folio reservado (en caso de cancelación de factura)
		"""
		try:
			# Buscar reserva existente
			reservation = frappe.db.get_value(
				"Branch Folio Reservation",
				{"sales_invoice": sales_invoice_name, "branch": self.branch, "status": "Reserved"},
				["name", "folio_number"],
				as_dict=True,
			)

			if not reservation:
				return {"success": False, "message": "No se encontró reserva de folio para esta factura"}

			# Marcar reserva como liberada
			frappe.db.set_value("Branch Folio Reservation", reservation.name, "status", "Released")
			frappe.db.set_value(
				"Branch Folio Reservation", reservation.name, "released_on", frappe.utils.now()
			)

			# Decrementar folio actual (si es el último)
			branch_doc = self._get_branch_doc()
			current_folio = branch_doc.get("fm_folio_current", 0)

			if reservation.folio_number == current_folio:
				frappe.db.set_value("Branch", self.branch, "fm_folio_current", current_folio - 1)

			# Limpiar cache
			self._folio_status_cache = None

			return {
				"success": True,
				"message": f"Folio {reservation.folio_number} liberado exitosamente",
				"folio_released": reservation.folio_number,
			}

		except Exception as e:
			frappe.log_error(f"Error releasing folio for branch {self.branch}: {e!s}", "Branch Folio Release")
			return {"success": False, "message": f"Error liberando folio: {e!s}"}

	def get_folio_reservations(self, status: str | None = None) -> list[dict]:
		"""
		Obtener reservas de folios para la sucursal
		"""
		try:
			filters = {"branch": self.branch}
			if status:
				filters["status"] = status

			reservations = frappe.get_all(
				"Branch Folio Reservation",
				filters=filters,
				fields=[
					"name",
					"sales_invoice",
					"folio_number",
					"serie_folio",
					"status",
					"reserved_on",
					"released_on",
				],
				order_by="folio_number desc",
			)

			return reservations

		except Exception as e:
			frappe.log_error(
				f"Error getting folio reservations for branch {self.branch}: {e!s}",
				"Branch Folio Reservations",
			)
			return []

	def validate_folio_integrity(self) -> dict[str, Any]:
		"""
		Validar integridad del sistema de folios
		"""
		try:
			branch_doc = self._get_branch_doc()
			current_folio = branch_doc.get("fm_folio_current", 0)

			# Verificar que no hay huecos en la secuencia
			reserved_folios = frappe.get_all(
				"Branch Folio Reservation",
				filters={"branch": self.branch, "status": "Reserved"},
				fields=["folio_number"],
				order_by="folio_number",
			)

			issues = []
			expected_folios = list(range(1, current_folio + 1))
			actual_folios = [r.folio_number for r in reserved_folios]

			# Detectar folios faltantes
			missing_folios = set(expected_folios) - set(actual_folios)
			if missing_folios:
				issues.append(f"Folios faltantes en reservas: {sorted(missing_folios)}")

			# Detectar folios duplicados
			duplicated_folios = []
			seen = set()
			for folio in actual_folios:
				if folio in seen:
					duplicated_folios.append(folio)
				seen.add(folio)

			if duplicated_folios:
				issues.append(f"Folios duplicados: {duplicated_folios}")

			return {
				"valid": len(issues) == 0,
				"issues": issues,
				"total_reserved": len(reserved_folios),
				"current_folio": current_folio,
				"expected_reservations": len(expected_folios),
			}

		except Exception as e:
			frappe.log_error(
				f"Error validating folio integrity for branch {self.branch}: {e!s}", "Branch Folio Integrity"
			)
			return {
				"valid": False,
				"issues": [f"Error de validación: {e!s}"],
				"total_reserved": 0,
				"current_folio": 0,
			}

	def _calculate_folio_status(self) -> dict[str, Any]:
		"""
		Calcular estado actual de folios con semáforos
		"""
		try:
			branch_doc = self._get_branch_doc()

			current_folio = branch_doc.get("fm_folio_current", 0)
			end_folio = branch_doc.get("fm_folio_end", 0)
			warning_threshold = branch_doc.get("fm_folio_warning_threshold", 100)

			if end_folio == 0:
				# Folios ilimitados
				return {
					"semaforo": "verde",
					"status": "unlimited",
					"message": "Folios ilimitados",
					"current_folio": current_folio,
					"remaining_folios": "∞",
					"percentage_used": 0,
					"can_generate": True,
				}

			remaining_folios = end_folio - current_folio
			percentage_used = (current_folio / end_folio) * 100

			# Determinar semáforo
			if remaining_folios <= 0:
				semaforo = "rojo"
				status = "agotado"
				message = "Folios agotados"
				can_generate = False
			elif remaining_folios <= warning_threshold:
				semaforo = "rojo"
				status = "critico"
				message = f"Folios críticos: quedan {remaining_folios}"
				can_generate = True
			elif percentage_used >= 80:
				semaforo = "amarillo"
				status = "advertencia"
				message = f"Advertencia: {percentage_used:.1f}% de folios utilizados"
				can_generate = True
			else:
				semaforo = "verde"
				status = "normal"
				message = f"Estado normal: {remaining_folios} folios disponibles"
				can_generate = True

			return {
				"semaforo": semaforo,
				"status": status,
				"message": message,
				"current_folio": current_folio,
				"end_folio": end_folio,
				"remaining_folios": remaining_folios,
				"percentage_used": round(percentage_used, 1),
				"warning_threshold": warning_threshold,
				"can_generate": can_generate,
			}

		except Exception as e:
			frappe.log_error(
				f"Error calculating folio status for branch {self.branch}: {e!s}", "Branch Folio Status"
			)
			return self._get_error_status()

	def _get_branch_doc(self):
		"""Obtener documento de la sucursal con cache"""
		if self.branch_doc is None:
			self.branch_doc = frappe.get_cached_doc("Branch", self.branch)
		return self.branch_doc

	def _generate_serie_folio(self, serie_pattern: str, folio_number: int) -> str:
		"""
		Generar serie y folio basado en el patrón
		Ejemplo: A{####} + 123 = A0123
		"""
		try:
			if "{" in serie_pattern and "}" in serie_pattern:
				# Extraer patrón de formateo
				start = serie_pattern.find("{") + 1
				end = serie_pattern.find("}")
				format_pattern = serie_pattern[start:end]

				# Contar número de # para determinar padding
				padding = format_pattern.count("#")
				if padding > 0:
					folio_str = str(folio_number).zfill(padding)
				else:
					folio_str = str(folio_number)

				# Reemplazar patrón
				serie_folio = serie_pattern.replace("{" + format_pattern + "}", folio_str)
			else:
				# Patrón simple sin formateo
				serie_folio = f"{serie_pattern}{folio_number}"

			return serie_folio

		except Exception as e:
			frappe.log_error(f"Error generating serie folio: {e!s}", "Serie Folio Generation")
			return f"A{folio_number}"

	def _create_folio_reservation(self, sales_invoice_name: str, folio_number: int, serie_folio: str):
		"""Crear registro de reserva de folio"""
		try:
			# Crear nuevo DocType si no existe
			if not frappe.db.exists("DocType", "Branch Folio Reservation"):
				self._create_folio_reservation_doctype()

			reservation_doc = frappe.get_doc(
				{
					"doctype": "Branch Folio Reservation",
					"branch": self.branch,
					"sales_invoice": sales_invoice_name,
					"folio_number": folio_number,
					"serie_folio": serie_folio,
					"status": "Reserved",
					"reserved_on": frappe.utils.now(),
				}
			)

			reservation_doc.insert(ignore_permissions=True)
			frappe.db.commit()

		except Exception as e:
			frappe.log_error(f"Error creating folio reservation: {e!s}", "Folio Reservation Creation")

	def _create_folio_reservation_doctype(self):
		"""Crear DocType Branch Folio Reservation si no existe"""
		try:
			doctype_doc = frappe.get_doc(
				{
					"doctype": "DocType",
					"name": "Branch Folio Reservation",
					"module": "Facturacion Mexico",
					"custom": 1,
					"fields": [
						{
							"fieldname": "branch",
							"fieldtype": "Link",
							"label": "Branch",
							"options": "Branch",
							"reqd": 1,
						},
						{
							"fieldname": "sales_invoice",
							"fieldtype": "Link",
							"label": "Sales Invoice",
							"options": "Sales Invoice",
							"reqd": 1,
						},
						{"fieldname": "folio_number", "fieldtype": "Int", "label": "Folio Number", "reqd": 1},
						{"fieldname": "serie_folio", "fieldtype": "Data", "label": "Serie Folio", "reqd": 1},
						{
							"fieldname": "status",
							"fieldtype": "Select",
							"label": "Status",
							"options": "Reserved\nUsed\nReleased",
							"default": "Reserved",
						},
						{"fieldname": "reserved_on", "fieldtype": "Datetime", "label": "Reserved On"},
						{"fieldname": "released_on", "fieldtype": "Datetime", "label": "Released On"},
					],
					"permissions": [
						{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
					],
				}
			)

			doctype_doc.insert(ignore_permissions=True)
			frappe.db.commit()

		except Exception as e:
			frappe.log_error(f"Error creating Branch Folio Reservation DocType: {e!s}", "DocType Creation")

	def _get_error_status(self) -> dict[str, Any]:
		"""Estado de error por defecto"""
		return {
			"semaforo": "rojo",
			"status": "error",
			"message": "Error obteniendo estado de folios",
			"current_folio": 0,
			"remaining_folios": 0,
			"percentage_used": 0,
			"can_generate": False,
		}


# APIs públicas


@frappe.whitelist()
def get_branch_folio_status(branch: str) -> dict:
	"""API para obtener estado de folios de una sucursal"""
	try:
		manager = BranchFolioManager(branch)
		status = manager.get_folio_status()
		return {"success": True, "data": status}
	except Exception as e:
		frappe.log_error(f"Error in get_branch_folio_status API: {e!s}", "Branch Folio API")
		return {"success": False, "message": f"Error: {e!s}", "data": {}}


@frappe.whitelist()
def reserve_folio_for_invoice(branch: str, sales_invoice: str) -> dict:
	"""API para reservar folio para factura"""
	try:
		manager = BranchFolioManager(branch)
		result = manager.reserve_next_folio(sales_invoice)
		return result
	except Exception as e:
		frappe.log_error(f"Error in reserve_folio_for_invoice API: {e!s}", "Branch Folio API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def release_folio_for_invoice(branch: str, sales_invoice: str) -> dict:
	"""API para liberar folio de factura"""
	try:
		manager = BranchFolioManager(branch)
		result = manager.release_folio(sales_invoice)
		return result
	except Exception as e:
		frappe.log_error(f"Error in release_folio_for_invoice API: {e!s}", "Branch Folio API")
		return {"success": False, "message": f"Error: {e!s}"}


@frappe.whitelist()
def get_branch_folio_reservations(branch: str, status: str | None = None) -> dict:
	"""API para obtener reservas de folios"""
	try:
		manager = BranchFolioManager(branch)
		reservations = manager.get_folio_reservations(status)
		return {"success": True, "data": reservations, "count": len(reservations)}
	except Exception as e:
		frappe.log_error(f"Error in get_branch_folio_reservations API: {e!s}", "Branch Folio API")
		return {"success": False, "message": f"Error: {e!s}", "data": []}
