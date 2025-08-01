import frappe
from frappe.model.document import Document


class FiscalAttemptLog(Document):
	"""Log de intentos de timbrado fiscal."""

	def validate(self):
		"""Validación del log de intento."""
		if not self.attempt_datetime:
			self.attempt_datetime = frappe.utils.now()

	@staticmethod
	def create_attempt_log(
		parent_doc,
		attempt_type,
		status,
		pac_response_code=None,
		pac_message=None,
		request_data=None,
		response_data=None,
		error_details=None,
	):
		"""Crear un nuevo log de intento fiscal."""

		# Crear nuevo registro en la tabla hijo
		log_entry = parent_doc.append(
			"fm_fiscal_attempts",
			{
				"attempt_type": attempt_type,
				"status": status,
				"pac_response_code": pac_response_code,
				"pac_message": pac_message,
				"request_data": frappe.as_json(request_data) if request_data else None,
				"response_data": frappe.as_json(response_data) if response_data else None,
				"error_details": error_details,
				"attempt_datetime": frappe.utils.now(),
			},
		)

		# Guardar el documento padre para persistir el log
		parent_doc.save(ignore_permissions=True)

		return log_entry

	@staticmethod
	def get_last_successful_attempt(parent_docname, doctype="Sales Invoice"):
		"""Obtener el último intento exitoso de timbrado."""

		parent_doc = frappe.get_doc(doctype, parent_docname)

		for attempt in reversed(parent_doc.fm_fiscal_attempts):
			if attempt.status == "Exitoso" and attempt.attempt_type == "Timbrado":
				return attempt

		return None

	@staticmethod
	def get_attempt_summary(parent_docname, doctype="Sales Invoice"):
		"""Obtener resumen de intentos para mostrar en interfaz."""

		parent_doc = frappe.get_doc(doctype, parent_docname)

		summary = {
			"total_attempts": len(parent_doc.fm_fiscal_attempts),
			"successful_attempts": 0,
			"failed_attempts": 0,
			"last_attempt": None,
			"last_successful": None,
			"current_status": "Sin Intentos",
		}

		for attempt in parent_doc.fm_fiscal_attempts:
			if attempt.status == "Exitoso":
				summary["successful_attempts"] += 1
				summary["last_successful"] = attempt
			elif attempt.status in ["Error", "Rechazado"]:
				summary["failed_attempts"] += 1

		if parent_doc.fm_fiscal_attempts:
			summary["last_attempt"] = parent_doc.fm_fiscal_attempts[-1]
			summary["current_status"] = summary["last_attempt"].status

		return summary
