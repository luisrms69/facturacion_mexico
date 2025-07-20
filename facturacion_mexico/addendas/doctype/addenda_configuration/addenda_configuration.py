"""
Addenda Configuration DocType - Sprint 3
Configuraciones de addenda por cliente y tipo
"""

from datetime import datetime
from typing import Any

import frappe
import frappe.utils
from frappe import _
from frappe.model.document import Document


class AddendaConfiguration(Document):
	"""DocType para configuraciones de addenda específicas por cliente."""

	def validate(self):
		"""Validaciones de la configuración."""
		self.validate_duplicate_configuration()
		self.validate_date_range()
		self.validate_email_recipients()
		self.validate_field_values()
		self.set_audit_fields()

	def validate_duplicate_configuration(self):
		"""Validar que no haya configuraciones duplicadas activas."""
		if not self.customer or not self.addenda_type:
			return

		# Verificar configuraciones activas para el mismo cliente y tipo
		existing = frappe.get_all(
			"Addenda Configuration",
			filters={
				"customer": self.customer,
				"addenda_type": self.addenda_type,
				"is_active": 1,
				"name": ["!=", self.name or ""],
			},
			fields=["name", "effective_date", "expiry_date"],
		)

		if existing:
			# Verificar solapamiento de fechas
			for config in existing:
				if self._date_ranges_overlap(config):
					frappe.throw(
						_(
							"Ya existe una configuración activa para el cliente '{0}' y tipo '{1}' "
							"con fechas que se solapan: {2}"
						).format(self.customer, self.addenda_type, config["name"])
					)

	def _date_ranges_overlap(self, other_config: dict) -> bool:
		"""Verificar si las fechas se solapan con otra configuración."""
		# Si no hay fechas definidas, asumir solapamiento total
		if not self.effective_date and not self.expiry_date:
			return True
		if not other_config.get("effective_date") and not other_config.get("expiry_date"):
			return True

		# Convertir fechas - manejar tanto objetos date como strings
		start1 = self._parse_date(self.effective_date) or datetime.min.date()
		end1 = self._parse_date(self.expiry_date) or datetime.max.date()
		start2 = self._parse_date(other_config.get("effective_date")) or datetime.min.date()
		end2 = self._parse_date(other_config.get("expiry_date")) or datetime.max.date()

		# Verificar solapamiento
		return start1 <= end2 and start2 <= end1

	def _parse_date(self, date_value):
		"""Convertir string o date a objeto date."""
		if not date_value:
			return None

		if isinstance(date_value, str):
			try:
				return frappe.utils.getdate(date_value)
			except Exception:
				return None

		# Ya es un objeto date o datetime
		return date_value

	def validate_date_range(self):
		"""Validar que las fechas sean lógicas."""
		if self.effective_date and self.expiry_date:
			if self.effective_date > self.expiry_date:
				frappe.throw(_("La fecha de inicio no puede ser posterior a la fecha de fin"))

		# Establecer fecha de inicio por defecto si no existe
		if not self.effective_date:
			self.effective_date = frappe.utils.today()

	def validate_email_recipients(self):
		"""Validar formato de emails para notificaciones."""
		if self.notify_on_error and self.error_recipients:
			emails = [email.strip() for email in self.error_recipients.split(",")]
			for email in emails:
				if email and not frappe.utils.validate_email_address(email):
					frappe.throw(_("Email inválido en destinatarios: {0}").format(email))

	def validate_field_values(self):
		"""Validar valores de campos configurados."""
		if not self.field_values:
			return

		# Verificar que todas las definiciones de campo sean válidas
		addenda_type_doc = frappe.get_doc("Addenda Type", self.addenda_type)
		valid_field_definitions = [fd.name for fd in addenda_type_doc.field_definitions]

		for field_value in self.field_values:
			if field_value.field_definition not in valid_field_definitions:
				frappe.throw(
					_("Definición de campo '{0}' no pertenece al tipo de addenda '{1}'").format(
						field_value.field_definition, self.addenda_type
					)
				)

	def set_audit_fields(self):
		"""Establecer campos de auditoría."""
		if self.is_new():
			self.created_by = frappe.session.user
			self.creation_date = frappe.utils.now()

		self.modified_by = frappe.session.user
		self.modified_date = frappe.utils.now()

	def is_active_for_date(self, check_date: str | None = None) -> bool:
		"""Verificar si la configuración está activa para una fecha específica."""
		if not self.is_active:
			return False

		if not check_date:
			check_date = frappe.utils.today()

		# Verificar rango de fechas
		if self.effective_date and check_date < self.effective_date:
			return False

		if self.expiry_date and check_date > self.expiry_date:
			return False

		return True

	def get_field_values_dict(self) -> dict[str, Any]:
		"""Obtener valores de campos como diccionario."""
		field_values = {}

		for field_value in self.field_values:
			field_values[field_value.field_definition] = {
				"value": field_value.field_value,
				"is_dynamic": field_value.is_dynamic,
				"dynamic_source": field_value.dynamic_source,
				"dynamic_field": field_value.dynamic_field,
				"transformation": getattr(field_value, "transformation", ""),
				"default_value": getattr(field_value, "default_value", ""),
			}

		return field_values

	def get_resolved_field_values(self, context_data: dict | None = None) -> dict[str, str]:
		"""Resolver todos los valores de campos con contexto."""
		if context_data is None:
			context_data = {}

		resolved_values = {}

		for field_value in self.field_values:
			resolved_values[field_value.field_definition] = field_value.get_resolved_value(context_data)

		return resolved_values

	def clone_configuration(self, new_customer: str, copy_field_values: bool = True) -> str:
		"""Clonar configuración para otro cliente."""
		new_doc = frappe.copy_doc(self)
		new_doc.customer = new_customer
		new_doc.is_active = 0  # Crear inactiva por defecto

		if not copy_field_values:
			new_doc.field_values = []

		new_doc.insert()
		return new_doc.name

	def test_configuration(self, sales_invoice: str | None = None) -> dict:
		"""Probar la configuración con una factura de ejemplo."""
		try:
			# Si no se proporciona factura, crear datos de prueba
			if sales_invoice:
				invoice_doc = frappe.get_doc("Sales Invoice", sales_invoice)
				if invoice_doc.customer != self.customer:
					return {
						"success": False,
						"message": _("La factura no pertenece al cliente de esta configuración"),
					}
			else:
				# Crear contexto de prueba
				invoice_doc = None

			# Resolver valores de campos
			context_data = self._build_test_context(invoice_doc)
			resolved_values = self.get_resolved_field_values(context_data)

			# Validar cada campo
			validation_results = []
			for field_value in self.field_values:
				is_valid, errors = field_value.validate_against_definition()
				validation_results.append(
					{
						"field": field_value.field_definition,
						"resolved_value": resolved_values.get(field_value.field_definition, ""),
						"is_valid": is_valid,
						"errors": errors,
					}
				)

			return {
				"success": True,
				"resolved_values": resolved_values,
				"validation_results": validation_results,
				"valid_fields": sum(1 for r in validation_results if r["is_valid"]),
				"total_fields": len(validation_results),
			}

		except Exception as e:
			return {"success": False, "message": _(f"Error durante prueba: {e!s}")}

	def _build_test_context(self, invoice_doc) -> dict:
		"""Construir contexto de prueba para resolución de valores."""
		context = {}

		if invoice_doc:
			context["sales_invoice"] = invoice_doc
			try:
				context["customer"] = frappe.get_doc("Customer", invoice_doc.customer)
			except Exception:
				# Ignorar si no se puede obtener datos del cliente - usar contexto sin customer
				pass

			if invoice_doc.items:
				try:
					context["item"] = frappe.get_doc("Item", invoice_doc.items[0].item_code)
				except Exception:
					# Ignorar si no se puede obtener datos del primer item - usar contexto sin item
					pass

		else:
			# Datos de prueba básicos
			context["custom_data"] = {
				"test_value": "Valor de Prueba",
				"test_number": "123.45",
				"test_date": frappe.utils.today(),
			}

		return context

	def get_usage_stats(self) -> dict:
		"""Obtener estadísticas de uso de la configuración."""
		try:
			# Contar facturas del cliente en el último mes
			recent_invoices = frappe.get_all(
				"Sales Invoice",
				filters={
					"customer": self.customer,
					"docstatus": 1,
					"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -30)],
				},
				limit=1000,
			)

			# Verificar si hay addendas generadas
			addenda_count = 0
			if hasattr(frappe.db, "count"):
				addenda_count = frappe.db.count(
					"Sales Invoice",
					filters={
						"customer": self.customer,
						"fm_addenda_required": 1,
						"fm_addenda_xml": ["!=", ""],
						"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -30)],
					},
				)

			return {
				"recent_invoices": len(recent_invoices),
				"addendas_generated": addenda_count,
				"configuration_age_days": frappe.utils.date_diff(frappe.utils.today(), self.creation_date),
				"last_modified_days": frappe.utils.date_diff(frappe.utils.today(), self.modified_date),
				"field_count": len(self.field_values),
				"is_currently_active": self.is_active_for_date(),
			}

		except Exception as e:
			frappe.log_error(f"Error obteniendo estadísticas de configuración: {e!s}")
			return {
				"recent_invoices": 0,
				"addendas_generated": 0,
				"configuration_age_days": 0,
				"last_modified_days": 0,
				"field_count": 0,
				"is_currently_active": False,
			}

	@staticmethod
	def get_active_configuration(customer: str, addenda_type: str | None = None) -> dict | None:
		"""Obtener configuración activa para un cliente."""
		today = frappe.utils.today()
		filters = {
			"customer": customer,
			"is_active": 1,
			"effective_date": ["<=", today],
		}

		if addenda_type:
			filters["addenda_type"] = addenda_type

		# Agregar filtro de fecha de fin (puede ser NULL)
		configurations = frappe.get_all(
			"Addenda Configuration",
			filters=filters,
			fields=[
				"name",
				"addenda_type",
				"priority",
				"auto_apply",
				"validation_level",
				"effective_date",
				"expiry_date",
			],
			order_by="priority, creation",
		)

		# Filtrar por fecha de fin manualmente (para manejar NULL)
		valid_configs = []
		for config in configurations:
			if not config.get("expiry_date") or config["expiry_date"] >= today:
				valid_configs.append(config)

		return valid_configs[0] if valid_configs else None

	def send_error_notification(self, error_message: str, sales_invoice: str | None = None):
		"""Enviar notificación de error por email."""
		if not self.notify_on_error or not self.error_recipients:
			return

		try:
			subject = _("Error en Addenda - Cliente {0}").format(self.customer)

			message = f"""
			<p>Se ha producido un error al procesar la addenda:</p>
			<p><strong>Cliente:</strong> {self.customer}</p>
			<p><strong>Tipo de Addenda:</strong> {self.addenda_type}</p>
			{f'<p><strong>Factura:</strong> {sales_invoice}</p>' if sales_invoice else ''}
			<p><strong>Error:</strong> {error_message}</p>
			<p><strong>Configuración:</strong> {self.name}</p>
			<p><strong>Fecha:</strong> {frappe.utils.now()}</p>
			"""

			recipients = [email.strip() for email in self.error_recipients.split(",")]

			frappe.sendmail(
				recipients=recipients,
				subject=subject,
				message=message,
				reference_doctype="Addenda Configuration",
				reference_name=self.name,
			)

		except Exception as e:
			frappe.log_error(f"Error enviando notificación de addenda: {e!s}")


# Métodos para hooks
def on_doctype_update():
	"""Ejecutar cuando se actualiza el DocType."""
	frappe.db.add_index("Addenda Configuration", ["customer", "addenda_type", "is_active"])
	frappe.db.add_index("Addenda Configuration", ["effective_date", "expiry_date"])


def get_permission_query_conditions(user):
	"""Condiciones de permisos para consultas."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	# Los usuarios solo pueden ver configuraciones de clientes activos
	return """(`tabAddenda Configuration`.`customer` in (
		select name from `tabCustomer` where disabled = 0
	))"""


def has_permission(doc, user):
	"""Verificar permisos específicos del documento."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	# Verificar que el cliente esté activo
	try:
		customer_doc = frappe.get_doc("Customer", doc.customer)
		return not customer_doc.disabled
	except Exception:
		return False
