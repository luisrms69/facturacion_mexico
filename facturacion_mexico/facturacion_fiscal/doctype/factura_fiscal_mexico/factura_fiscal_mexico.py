import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


class FacturaFiscalMexico(Document):
	"""Documento principal para facturas fiscales de México."""

	def validate(self):
		"""Validar factura fiscal antes de guardar."""
		self.validate_sales_invoice()
		self.validate_company_match()
		self.validate_status_transitions()

	def validate_sales_invoice(self):
		"""Validar que Sales Invoice existe y está submitted."""
		if not self.sales_invoice:
			frappe.throw(_("Sales Invoice es requerida"))

		if not frappe.db.exists("Sales Invoice", self.sales_invoice):
			frappe.throw(_("Sales Invoice {0} no existe").format(self.sales_invoice))

		sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

		if sales_invoice.docstatus != 1:
			frappe.throw(_("Sales Invoice debe estar enviada (submitted) para crear factura fiscal"))

		# Verificar que no exista ya una factura fiscal para esta Sales Invoice
		existing = frappe.db.exists(
			"Factura Fiscal Mexico",
			{
				"sales_invoice": self.sales_invoice,
				"name": ("!=", self.name),
				"status": ("not in", ["cancelled"]),
			},
		)

		if existing:
			frappe.throw(
				_("Ya existe una factura fiscal activa para la Sales Invoice {0}").format(self.sales_invoice)
			)

	def validate_company_match(self):
		"""Validar que la empresa coincida con la Sales Invoice."""
		if self.sales_invoice and self.company:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if sales_invoice.company != self.company:
				frappe.throw(_("La empresa debe coincidir con la Sales Invoice"))

	def validate_status_transitions(self):
		"""Validar transiciones de estado válidas."""
		if self.is_new():
			return

		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		old_status = old_doc.status
		new_status = self.status

		# Definir transiciones válidas
		valid_transitions = {
			"draft": ["stamped", "cancelled"],
			"stamped": ["cancel_requested", "cancelled"],
			"cancel_requested": ["cancelled", "stamped"],  # Puede fallar la cancelación
			"cancelled": [],  # Estado final
		}

		if new_status not in valid_transitions.get(old_status, []):
			frappe.throw(_("Transición de estado inválida: {0} → {1}").format(old_status, new_status))

	def before_save(self):
		"""Ejecutar antes de guardar."""
		# Si no hay empresa, obtenerla de Sales Invoice
		if not self.company and self.sales_invoice:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			self.company = sales_invoice.company

	def after_insert(self):
		"""Ejecutar después de insertar."""
		# Crear evento fiscal
		self.create_fiscal_event(
			"create", {"sales_invoice": self.sales_invoice, "company": self.company, "status": self.status}
		)

	def on_update(self):
		"""Ejecutar después de actualizar."""
		# Si el estado cambió, crear evento fiscal
		if self.has_value_changed("status"):
			self.create_fiscal_event(
				"status_change",
				{
					"old_status": self.get_doc_before_save().status
					if self.get_doc_before_save()
					else "draft",
					"new_status": self.status,
					"uuid": self.uuid,
					"facturapi_id": self.facturapi_id,
				},
			)

		# Actualizar Sales Invoice con información fiscal
		self.update_sales_invoice_fiscal_info()

	def create_fiscal_event(self, event_type, event_data):
		"""Crear evento fiscal para auditoría."""
		try:
			fiscal_event = frappe.new_doc("Fiscal Event MX")
			fiscal_event.event_type = event_type
			fiscal_event.reference_doctype = self.doctype
			fiscal_event.reference_name = self.name
			fiscal_event.event_data = frappe.as_json(event_data)
			fiscal_event.status = "success"
			fiscal_event.user_role = (
				frappe.get_roles(frappe.session.user)[0] if frappe.get_roles(frappe.session.user) else "Guest"
			)
			fiscal_event.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error creating fiscal event: {e!s}", "Fiscal Event Creation Error")

	def update_sales_invoice_fiscal_info(self):
		"""Actualizar información fiscal en Sales Invoice."""
		if not self.sales_invoice:
			return

		# Mapear estados para Sales Invoice
		status_map = {
			"draft": "Pendiente",
			"stamped": "Timbrada",
			"cancel_requested": "Cancelación Solicitada",
			"cancelled": "Cancelada",
		}

		try:
			frappe.db.set_value(
				"Sales Invoice",
				self.sales_invoice,
				{
					"fiscal_status": status_map.get(self.status, "Pendiente"),
					"uuid_fiscal": self.uuid,
					"factura_fiscal_mx": self.name,
				},
			)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure Sales Invoice fiscal info is persisted
		except Exception as e:
			frappe.log_error(f"Error updating Sales Invoice fiscal info: {e!s}", "Sales Invoice Update Error")

	def mark_as_stamped(self, facturapi_data):
		"""Marcar como timbrada con datos de FacturAPI."""
		self.status = "stamped"
		self.facturapi_id = facturapi_data.get("id")
		self.uuid = facturapi_data.get("uuid")
		self.serie = facturapi_data.get("serie")
		self.folio = facturapi_data.get("folio")
		self.total_fiscal = flt(facturapi_data.get("total", 0))
		self.fecha_timbrado = now_datetime()

		# Guardar archivos si están disponibles
		if facturapi_data.get("pdf_url"):
			self.attach_file_from_url(facturapi_data["pdf_url"], "pdf")

		if facturapi_data.get("xml_url"):
			self.attach_file_from_url(facturapi_data["xml_url"], "xml")

		self.save()

	def mark_as_cancelled(self, cancellation_reason=None):
		"""Marcar como cancelada."""
		self.status = "cancelled"
		if cancellation_reason:
			self.cancellation_reason = cancellation_reason
		self.cancellation_date = now_datetime()
		self.save()

	def attach_file_from_url(self, file_url, file_type):
		"""Adjuntar archivo desde URL."""
		try:
			import requests
			from frappe.utils.file_manager import save_file

			response = requests.get(file_url)
			response.raise_for_status()

			filename = f"{self.name}_{self.uuid}.{file_type}"
			file_doc = save_file(filename, response.content, self.doctype, self.name, is_private=1)

			# Actualizar campo correspondiente
			if file_type == "pdf":
				self.pdf_file = file_doc.file_url
			elif file_type == "xml":
				self.xml_file = file_doc.file_url

		except Exception as e:
			frappe.log_error(f"Error attaching {file_type} file: {e!s}", "File Attachment Error")

	@frappe.whitelist()
	def request_stamping(self):
		"""Solicitar timbrado fiscal."""
		if self.status != "draft":
			frappe.throw(_("Solo se pueden timbrar facturas en estado borrador"))

		# Aquí se integraría con FacturAPI.io
		# Por ahora solo cambiar el estado para testing
		frappe.msgprint(_("Solicitud de timbrado enviada"))
		return {"message": "Stamping requested"}

	@frappe.whitelist()
	def request_cancellation(self):
		"""Solicitar cancelación fiscal."""
		if self.status != "stamped":
			frappe.throw(_("Solo se pueden cancelar facturas timbradas"))

		self.status = "cancel_requested"
		self.save()
		frappe.msgprint(_("Solicitud de cancelación enviada"))
		return {"message": "Cancellation requested"}
