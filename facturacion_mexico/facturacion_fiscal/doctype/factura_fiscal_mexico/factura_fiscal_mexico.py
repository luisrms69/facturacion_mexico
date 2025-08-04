import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, now_datetime


def get_payment_entry_by_invoice(invoice_name):
	"""
	Función encapsulada para buscar Payment Entry por Sales Invoice.

	Práctica recomendada por experto Frappe para consultas child tables.
	Reutilizable en todo el sistema.

	Args:
		invoice_name (str): Nombre del Sales Invoice

	Returns:
		list: Lista de dict con name y mode_of_payment del Payment Entry
	"""
	return frappe.db.sql(
		"""
		SELECT pe.name, pe.mode_of_payment
		FROM `tabPayment Entry` pe
		WHERE pe.docstatus = 1
		  AND EXISTS (
			SELECT 1 FROM `tabPayment Entry Reference` per
			WHERE per.parent = pe.name
			  AND per.reference_doctype = %s
			  AND per.reference_name = %s
		  )
		LIMIT 1
	""",
		("Sales Invoice", invoice_name),
		as_dict=True,
	)


@frappe.whitelist()
def get_payment_entry_for_javascript(invoice_name):
	"""
	Wrapper para JavaScript - buscar Payment Entry por Sales Invoice.

	Permite a JavaScript usar la lógica SQL correcta sin problemas de sintaxis child tables.

	Args:
		invoice_name (str): Nombre del Sales Invoice

	Returns:
		dict: Resultado con payment entries o mensaje de error
	"""
	try:
		payment_entries = get_payment_entry_by_invoice(invoice_name)
		return {
			"success": True,
			"data": payment_entries,
			"message": f"Encontrados {len(payment_entries)} Payment Entry para {invoice_name}",
		}
	except Exception as e:
		frappe.log_error(
			f"Error buscando Payment Entry para {invoice_name}: {e!s}", "Payment Entry Search Error"
		)
		return {"success": False, "data": [], "message": f"Error buscando Payment Entry: {e!s}"}


class FacturaFiscalMexico(Document):
	"""Documento principal para facturas fiscales de México."""

	def validate(self):
		"""Validar factura fiscal antes de guardar."""
		self.validate_sales_invoice()
		self.validate_company_match()
		self.validate_customer_fiscal_change()
		self.validate_status_transitions()

		# Validaciones fiscales migradas desde Sales Invoice
		self.validate_cfdi_use()
		self.validate_payment_method()
		self.validate_ppd_vs_forma_pago()

	def validate_sales_invoice(self):
		"""Validar que Sales Invoice existe y está submitted."""
		if not self.sales_invoice:
			frappe.throw(_("Sales Invoice es requerida"))

		if not frappe.db.exists("Sales Invoice", self.sales_invoice):
			frappe.throw(_("Sales Invoice {0} no existe").format(self.sales_invoice))

		sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

		# PREVENCIÓN DOBLE FACTURACIÓN: Verificar que no exista otra Factura Fiscal timbrada
		self.validate_no_duplicate_timbrado()

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

	def validate_customer_fiscal_change(self):
		"""Validar y permitir cambio de cliente fiscal diferente al Sales Invoice."""
		if not self.sales_invoice or not self.customer:
			return

		# Obtener cliente del Sales Invoice
		sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
		sales_invoice_customer = sales_invoice.customer

		# Si el cliente fiscal es diferente al del Sales Invoice, crear log informativo
		if self.customer != sales_invoice_customer:
			# Log informativo para auditoría (no es error, es funcionalidad permitida)
			frappe.logger().info(
				f"Cliente fiscal diferente en {self.name}: "
				f"Sales Invoice customer: {sales_invoice_customer}, "
				f"Fiscal customer: {self.customer}. "
				f"Caso común: Público en General o cambio receptor fiscal."
			)

			# Opcional: Agregar mensaje informativo sin bloquear (solo primera vez)
			if self.is_new() and not hasattr(self, "_customer_change_notified"):
				frappe.msgprint(
					_(
						"Cliente fiscal ({0}) es diferente al cliente del Sales Invoice ({1}). "
						"Esto es permitido para casos como 'Público en General'."
					).format(self.customer, sales_invoice_customer),
					title=_("Cliente Fiscal Diferente"),
					indicator="orange",
					alert=True,
				)
				self._customer_change_notified = True

	def validate_status_transitions(self):
		"""Validar transiciones de estado válidas."""
		if self.is_new():
			return

		old_doc = self.get_doc_before_save()
		if not old_doc:
			return

		old_status = old_doc.fm_fiscal_status if hasattr(old_doc, "fm_fiscal_status") else None
		new_status = self.fm_fiscal_status

		# Si no hay cambio de estado, no validar
		if old_status == new_status:
			return

		# Definir transiciones válidas
		valid_transitions = {
			None: ["Pendiente"],  # Documento nuevo puede ser Pendiente
			"": ["Pendiente"],  # Estado vacío puede ir a Pendiente
			"Pendiente": ["Timbrada", "Cancelada", "Error"],
			"Timbrada": ["Cancelada"],
			"Cancelada": [],  # Estado final
			"Error": ["Pendiente", "Timbrada"],  # Puede reintentarse
		}

		if new_status not in valid_transitions.get(old_status, []):
			frappe.throw(
				_("Transición de estado inválida: {0} → {1}").format(old_status or "nuevo", new_status)
			)

	def validate_no_duplicate_timbrado(self):
		"""Prevenir doble timbrado del mismo Sales Invoice."""
		if not self.sales_invoice:
			return

		# Verificar campo directo en Sales Invoice
		existing_fiscal_doc = frappe.db.get_value("Sales Invoice", self.sales_invoice, "fm_factura_fiscal_mx")

		if existing_fiscal_doc and existing_fiscal_doc != self.name:
			# Verificar si el documento existente está timbrado
			existing_status = frappe.db.get_value(
				"Factura Fiscal Mexico", existing_fiscal_doc, "fm_fiscal_status"
			)

			if existing_status == "Timbrada":
				frappe.throw(
					_("Sales Invoice {0} ya ha sido timbrada en documento {1}").format(
						self.sales_invoice, existing_fiscal_doc
					)
				)

		# Validación cruzada - buscar otras Facturas Fiscales timbradas
		existing = frappe.get_all(
			"Factura Fiscal Mexico",
			filters={
				"sales_invoice": self.sales_invoice,
				"fm_fiscal_status": "Timbrada",
				"name": ["!=", self.name or "new-doc"],
			},
		)

		if existing:
			frappe.throw(
				_("Ya existe Factura Fiscal timbrada para Sales Invoice {0}: {1}").format(
					self.sales_invoice, existing[0].name
				)
			)

	def onload(self):
		"""Ejecutar al cargar el documento."""
		# Poblar datos de facturación al cargar
		self.populate_billing_data()

		# FASE 4: Auto-actualizar forma de pago al cargar documento existente
		# Caso: Usuario agregó Payment Entry después de crear Factura Fiscal
		if self.sales_invoice and not self.is_new():
			old_forma_pago = self.fm_forma_pago_timbrado
			self.auto_load_payment_method_from_sales_invoice()

			# Si cambió, marcar como modificado para que el usuario pueda guardar
			if old_forma_pago != self.fm_forma_pago_timbrado:
				frappe.logger().info(
					f"Auto-actualizada forma de pago en onload: {old_forma_pago} → {self.fm_forma_pago_timbrado}"
				)

	def before_save(self):
		"""Ejecutar antes de guardar."""
		# Cargar datos desde Sales Invoice si no están establecidos
		if self.sales_invoice:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

			# Si no hay empresa vendedora, obtenerla de Sales Invoice
			if not self.company:
				self.company = sales_invoice.company

			# Si no hay customer, obtenerlo de Sales Invoice
			if not self.customer:
				self.customer = sales_invoice.customer

		# Detectar cambio de customer y repoblar datos
		if self.has_value_changed("customer"):
			self.populate_billing_data()

		# Calcular status automáticamente basado en fm_fiscal_status
		self.calculate_status_from_fiscal_status()

		# Poblar datos de facturación desde customer
		self.populate_billing_data()

		# FASE 4: Auto-cargar forma de pago desde Payment Entry
		self.auto_load_payment_method_from_sales_invoice()

	def after_insert(self):
		"""Ejecutar después de insertar."""
		# Crear evento fiscal
		self.create_fiscal_event(
			"create",
			{"sales_invoice": self.sales_invoice, "company": self.company, "status": self.fm_fiscal_status},
		)

	def on_update(self):
		"""Ejecutar después de actualizar."""
		# Si el estado cambió, crear evento fiscal
		if self.has_value_changed("fm_fiscal_status"):
			self.create_fiscal_event(
				"status_change",
				{
					"old_status": self.get_doc_before_save().fm_fiscal_status
					if self.get_doc_before_save()
					else "Pendiente",
					"new_status": self.fm_fiscal_status,
					"uuid": self.uuid,
					"facturapi_id": getattr(self, "facturapi_id", None),
				},
			)

		# Actualizar Sales Invoice con información fiscal
		self.update_sales_invoice_fiscal_info()

		# FASE 1.1: Deshabilitar sync_facturapi_history() - funcionalidad duplicada
		# FacturAPI Response Log es la única fuente de verdad para historial
		# self.sync_facturapi_history()

		# Recalcular estado fiscal basado en logs
		self.calculate_fiscal_status_from_logs()

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

		# Mapear estados para Sales Invoice (ya están en español)
		status_map = {
			"Pendiente": "Pendiente",
			"Timbrada": "Timbrada",
			"Cancelada": "Cancelada",
			"Error": "Error",
		}

		try:
			frappe.db.set_value(
				"Sales Invoice",
				self.sales_invoice,
				{
					"fm_fiscal_status": status_map.get(self.fm_fiscal_status, "Pendiente"),
					"fm_factura_fiscal_mx": self.name,
				},
			)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure Sales Invoice fiscal info is persisted
		except Exception as e:
			frappe.log_error(f"Error updating Sales Invoice fiscal info: {e!s}", "Sales Invoice Update Error")

	def mark_as_stamped(self, facturapi_data):
		"""Marcar como timbrada con datos de FacturAPI."""
		self.fm_fiscal_status = "Timbrada"
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
		self.fm_fiscal_status = "Cancelada"
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
		if self.fm_fiscal_status != "Pendiente":
			frappe.throw(_("Solo se pueden timbrar facturas en estado Pendiente"))

		# Aquí se integraría con FacturAPI.io
		# Por ahora solo cambiar el estado para testing
		frappe.msgprint(_("Solicitud de timbrado enviada"))
		return {"message": "Stamping requested"}

	@frappe.whitelist()
	def request_cancellation(self):
		"""Solicitar cancelación fiscal."""
		if self.fm_fiscal_status != "Timbrada":
			frappe.throw(_("Solo se pueden cancelar facturas timbradas"))

		self.fm_fiscal_status = "Cancelada"
		self.save()
		frappe.msgprint(_("Solicitud de cancelación enviada"))
		return {"message": "Cancellation requested"}

	def auto_load_payment_method_from_sales_invoice(self):
		"""
		FASE 4: Auto-carga mejorada de forma de pago desde Payment Entry

		Para método PUE:
		- Buscar Payment Entry relacionada al Sales Invoice
		- Si existe: Cargar mode_of_payment automáticamente
		- Si no existe: Dejar vacío para selección manual

		Para método PPD:
		- Siempre asignar "99 - Por definir"
		"""
		if not self.sales_invoice or not self.fm_payment_method_sat:
			return

		# Para PPD: Siempre asignar "99 - Por definir"
		if self.fm_payment_method_sat == "PPD":
			if not self.fm_forma_pago_timbrado or self.fm_forma_pago_timbrado != "99 - Por definir":
				self.fm_forma_pago_timbrado = "99 - Por definir"
				frappe.logger().info(f"Auto-asignado PPD: 99 - Por definir para {self.name}")
			return

		# Para PUE: Buscar Payment Entry relacionada
		if self.fm_payment_method_sat == "PUE":
			# Solo auto-cargar si el campo está vacío (no sobrescribir selección manual)
			if self.fm_forma_pago_timbrado:
				return

			# Buscar Payment Entry relacionada (según especificación FASE 4)
			# Usar función encapsulada con SQL directo (práctica recomendada)
			payment_entries = get_payment_entry_by_invoice(self.sales_invoice)

			if payment_entries:
				payment_entry = payment_entries[0]
				if payment_entry.mode_of_payment:
					# Auto-cargar forma de pago desde Payment Entry
					self.fm_forma_pago_timbrado = payment_entry.mode_of_payment
					frappe.logger().info(
						f"Auto-cargado PUE: {payment_entry.mode_of_payment} "
						f"desde Payment Entry {payment_entry.name} para {self.name}"
					)
			else:
				# PUE sin Payment Entry - dejar vacío para selección manual
				frappe.logger().info(
					f"PUE sin Payment Entry para Sales Invoice {self.sales_invoice} "
					f"- usuario debe seleccionar manualmente"
				)

	def validate_cfdi_use(self):
		"""Validar uso de CFDI - MIGRADO desde Sales Invoice."""
		# Solo validar si no es un documento nuevo en estado pendiente
		if self.fm_fiscal_status == "Pendiente" and self.is_new():
			# Permitir guardar documentos nuevos sin CFDI para configuración posterior
			return

		# 1. VALIDACIÓN BLOQUEANTE: Uso CFDI es OBLIGATORIO (para timbrado)
		if not self.fm_cfdi_use:
			frappe.throw(
				_(
					"Uso de CFDI es obligatorio para facturación fiscal mexicana. "
					"Configure un default en el Cliente o seleccione manualmente."
				)
			)

		# 2. Validar que el uso de CFDI existe en catálogo SAT
		if not frappe.db.exists("Uso CFDI SAT", self.fm_cfdi_use):
			frappe.throw(_("El Uso de CFDI '{0}' no existe en el catálogo SAT").format(self.fm_cfdi_use))

		# 3. Validar que el uso de CFDI está activo
		uso_cfdi = frappe.get_doc("Uso CFDI SAT", self.fm_cfdi_use)
		if hasattr(uso_cfdi, "is_active") and not uso_cfdi.is_active():
			frappe.throw(_("El Uso de CFDI '{0}' no está activo en el catálogo SAT").format(self.fm_cfdi_use))

	def validate_payment_method(self):
		"""Validar método de pago SAT - MIGRADO desde Sales Invoice."""
		if not self.fm_payment_method_sat:
			# Asignar método por defecto
			self.fm_payment_method_sat = "PUE"  # Pago en una sola exhibición

		# Validar que el método existe
		valid_methods = ["PUE", "PPD"]
		if self.fm_payment_method_sat not in valid_methods:
			frappe.throw(_("Método de pago SAT inválido. Use PUE o PPD"))

		# Validar coherencia con forma de pago
		if self.fm_payment_method_sat == "PPD" and self.sales_invoice:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if sales_invoice.is_return:
				frappe.throw(_("Las notas de crédito no pueden usar método PPD"))

	def validate_ppd_vs_forma_pago(self):
		"""Validar compatibilidad entre PPD/PUE y forma de pago SAT - MIGRADO desde Sales Invoice."""
		if not self.fm_payment_method_sat or not self.sales_invoice:
			return

		sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

		# Obtener forma de pago desde Payment Entry relacionado
		forma_pago_sat = None

		if hasattr(sales_invoice, "payments") and sales_invoice.payments:
			# Buscar Payment Entry relacionado
			for payment_ref in sales_invoice.payments:
				if (
					payment_ref.reference_doctype == "Sales Invoice"
					and payment_ref.reference_name == sales_invoice.name
				):
					payment_entry = frappe.get_doc("Payment Entry", payment_ref.parent)

					if payment_entry.mode_of_payment:
						# Extraer código SAT del Mode of Payment (formato: "01 - Efectivo")
						mode_parts = payment_entry.mode_of_payment.split(" - ")
						if len(mode_parts) >= 2 and mode_parts[0].isdigit():
							forma_pago_sat = mode_parts[0]
							break

		if not forma_pago_sat:
			return

		# Determinar si es PPD basado en payment_terms_template
		is_ppd = bool(sales_invoice.payment_terms_template)

		if is_ppd:
			# PPD (Pago en Parcialidades Diferido): Solo permite "99 Por definir"
			if forma_pago_sat != "99":
				frappe.throw(
					_(
						f"Para facturas PPD (Pago en Parcialidades) solo se permite '99 - Por definir'. "
						f"Forma de pago detectada: {forma_pago_sat}"
					),
					title=_("Error Validación PPD"),
				)
		else:
			# PUE (Pago Una Exhibición): NO permite "99 Por definir"
			if forma_pago_sat == "99":
				frappe.throw(
					_(
						"Para facturas PUE (Pago Una Exhibición) no se permite '99 - Por definir'. "
						"Debe seleccionar una forma de pago específica (01, 02, 03, etc.)"
					),
					title=_("Error Validación PUE"),
				)

		frappe.logger().info(
			f"Validación PPD/PUE exitosa - Tipo: {'PPD' if is_ppd else 'PUE'}, Forma Pago: {forma_pago_sat}"
		)

	def sync_facturapi_history(self):
		"""Sincronizar historial de respuestas FacturAPI con child table."""
		try:
			# Obtener logs de FacturAPI Response Log
			logs = frappe.get_all(
				"FacturAPI Response Log",
				filters={"factura_fiscal_mexico": self.name},
				fields=[
					"timestamp",
					"operation_type",
					"success",
					"status_code",
					"error_message",
					"facturapi_response",
				],
				order_by="timestamp desc",
			)

			# Limpiar tabla actual usando set() (reconocido por semgrep)
			self.set("facturapi_response_history", [])

			# Agregar cada log como fila en child table
			for log in logs:
				# Crear resumen de respuesta
				response_summary = ""
				if log.facturapi_response:
					try:
						import json

						response_data = (
							log.facturapi_response
							if isinstance(log.facturapi_response, dict)
							else json.loads(log.facturapi_response)
						)

						# Extraer información clave
						key_info = []
						if response_data.get("id"):
							key_info.append(f"ID: {response_data['id']}")
						if response_data.get("uuid"):
							key_info.append(f"UUID: {response_data['uuid'][:8]}...")
						if response_data.get("status"):
							key_info.append(f"Status: {response_data['status']}")

						response_summary = " | ".join(key_info) if key_info else "Respuesta procesada"
					except Exception:
						response_summary = "Respuesta disponible"

				# Agregar fila a child table
				self.append(
					"facturapi_response_history",
					{
						"timestamp": log.timestamp,
						"operation_type": log.operation_type,
						"success": log.success,
						"status_code": log.status_code,
						"error_message": log.error_message[:100]
						if log.error_message
						else None,  # Truncar para UI
						"response_summary": response_summary,
					},
				)

			# Guardar cambios usando save() (reconocido por semgrep)
			self.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(
				f"Error sincronizando historial FacturAPI para {self.name}: {e!s}",
				"FacturAPI History Sync Error",
			)

	def calculate_fiscal_status_from_logs(self):
		"""Calcular estado fiscal automáticamente basado en logs de FacturAPI."""
		try:
			# Obtener último log exitoso de operaciones críticas
			latest_log = frappe.db.get_value(
				"FacturAPI Response Log",
				{
					"factura_fiscal_mexico": self.name,
					"success": 1,
					"operation_type": ("in", ["Timbrado", "Confirmación Cancelación"]),
				},
				["operation_type", "timestamp"],
				order_by="timestamp desc",
			)

			# Determinar nuevo estado basado en último log exitoso
			new_status = "Pendiente"  # Estado por defecto

			if latest_log:
				operation_type = latest_log[0] if isinstance(latest_log, tuple) else latest_log

				# Mapear operaciones a estados
				status_map = {"Timbrado": "Timbrada", "Confirmación Cancelación": "Cancelada"}

				new_status = status_map.get(operation_type, "Pendiente")

			# Verificar si hay solicitudes de cancelación pendientes
			pending_cancellation = frappe.db.exists(
				"FacturAPI Response Log",
				{"factura_fiscal_mexico": self.name, "success": 1, "operation_type": "Solicitud Cancelación"},
			)

			# Si hay solicitud de cancelación pero no confirmación, estado intermedio
			if pending_cancellation and new_status == "Timbrada":
				confirmation_exists = frappe.db.exists(
					"FacturAPI Response Log",
					{
						"factura_fiscal_mexico": self.name,
						"success": 1,
						"operation_type": "Confirmación Cancelación",
					},
				)

				if not confirmation_exists:
					new_status = "Solicitud Cancelación"

			# Verificar si hay errores recientes
			recent_error = frappe.db.get_value(
				"FacturAPI Response Log",
				{
					"factura_fiscal_mexico": self.name,
					"success": 0,
					"timestamp": (
						">",
						frappe.utils.add_days(frappe.utils.now_datetime(), -1),
					),  # Últimas 24 horas
				},
				["operation_type", "timestamp"],
				order_by="timestamp desc",
			)

			# Si hay error reciente y no hay éxito posterior, marcar como Error
			if recent_error and not latest_log:
				new_status = "Error"

			# Actualizar estado solo si cambió usando db_set (reconocido por semgrep)
			if self.fm_fiscal_status != new_status:
				old_status = self.fm_fiscal_status
				self.db_set("fm_fiscal_status", new_status)

				frappe.logger().info(
					f"Estado fiscal auto-calculado: {self.name} {old_status} → {new_status} "
					f"(basado en logs FacturAPI)"
				)

		except Exception as e:
			frappe.log_error(
				f"Error calculando estado fiscal para {self.name}: {e!s}",
				"FacturAPI Status Calculation Error",
			)

	def calculate_status_from_fiscal_status(self):
		"""Calcular status automáticamente basado en fm_fiscal_status."""
		# Mapear estados fiscales a status interno
		status_map = {
			"Pendiente": "draft",
			"Timbrada": "stamped",
			"Cancelada": "cancelled",
			"Error": "draft",  # Error vuelve a draft para reintento
			"Solicitud Cancelación": "cancel_requested",
		}

		new_status = status_map.get(self.fm_fiscal_status, "draft")

		# Solo actualizar si cambió
		if self.status != new_status:
			old_status = self.status
			self.status = new_status

			# Log del cambio automático
			frappe.logger().info(
				f"Status auto-calculado: {self.name} {old_status} → {new_status} "
				f"(basado en fm_fiscal_status: {self.fm_fiscal_status})"
			)

	def populate_billing_data(self):
		"""Poblar campos de datos de facturación desde el customer."""
		# Poblar datos de facturación desde customer

		if not self.customer:
			# Mostrar mensajes informativos si no hay customer
			self.fm_cp_cliente = "⚠️ SELECCIONA UN CLIENTE"
			self.fm_email_facturacion = "⚠️ SELECCIONA UN CLIENTE"
			self.fm_rfc_cliente = "⚠️ SELECCIONA UN CLIENTE"
			self.fm_direccion_principal_link = ""
			self.fm_direccion_principal_display = "⚠️ SELECCIONA UN CLIENTE"
			return

		try:
			# Obtener datos del customer
			customer_doc = frappe.get_doc("Customer", self.customer)
			# Customer encontrado, poblar datos

			# RFC desde Tax ID
			self.fm_rfc_cliente = customer_doc.tax_id or "⚠️ FALTA RFC EN CUSTOMER"
			# RFC asignado desde tax_id

			# Buscar dirección principal
			primary_address = self._get_primary_address()
			# Obtener dirección principal del customer

			if primary_address:
				# Poblar datos desde dirección principal
				self.fm_cp_cliente = primary_address.pincode or "⚠️ FALTA CP EN DIRECCIÓN"
				self.fm_email_facturacion = primary_address.email_id or "⚠️ FALTA EMAIL EN DIRECCIÓN"
				self.fm_direccion_principal_link = primary_address.name
				self.fm_direccion_principal_display = self._format_address(primary_address)
				# Datos poblados desde dirección principal
			else:
				# No hay dirección principal - marcar campos como faltantes
				self.fm_cp_cliente = "⚠️ FALTA DIRECCIÓN PRINCIPAL"
				self.fm_email_facturacion = "⚠️ FALTA DIRECCIÓN PRINCIPAL"
				self.fm_direccion_principal_link = ""
				self.fm_direccion_principal_display = "⚠️ FALTA DIRECCIÓN PRINCIPAL DEL CLIENTE"
				# No hay dirección principal - campos marcados como faltantes

			# Determinar estado de validación SAT para colores
			self._set_validation_status_color(customer_doc, primary_address)

		except Exception as e:
			frappe.log_error(f"Error poblando datos de facturación: {e!s}", "Billing Data Population Error")
			# En caso de error, mostrar mensajes de error
			self.fm_cp_cliente = "❌ ERROR AL OBTENER CP"
			self.fm_email_facturacion = "❌ ERROR AL OBTENER EMAIL"
			self.fm_rfc_cliente = "❌ ERROR AL OBTENER RFC"
			self.fm_direccion_principal_link = ""
			self.fm_direccion_principal_display = f"❌ Error: {e!s}"

	def _get_primary_address(self):
		"""Obtener la dirección principal del customer."""
		if not self.customer:
			return None

		# Buscar direcciones vinculadas al customer
		linked_addresses = frappe.get_all(
			"Dynamic Link",
			filters={"link_doctype": "Customer", "link_name": self.customer, "parenttype": "Address"},
			fields=["parent"],
			pluck="parent",
		)

		if not linked_addresses:
			return None

		# Buscar dirección marcada como principal
		for address_name in linked_addresses:
			address_doc = frappe.get_doc("Address", address_name)
			if address_doc.is_primary_address:
				return address_doc

		# Si no hay dirección principal, retornar la primera disponible
		if linked_addresses:
			return frappe.get_doc("Address", linked_addresses[0])

		return None

	def _format_address(self, address_doc):
		"""Formatear dirección para display."""
		if not address_doc:
			return ""

		parts = []
		if address_doc.address_line1:
			parts.append(address_doc.address_line1)
		if address_doc.address_line2:
			parts.append(address_doc.address_line2)
		if address_doc.city:
			parts.append(address_doc.city)
		if address_doc.state:
			parts.append(address_doc.state)
		if address_doc.pincode:
			parts.append(f"CP {address_doc.pincode}")
		if address_doc.country:
			parts.append(address_doc.country)

		return ", ".join(parts)

	def _set_validation_status_color(self, customer_doc, primary_address):
		"""Determinar color de sección Datos de Facturación basado en validación SAT."""
		# Verificar estado de validación SAT
		rfc_validated = getattr(customer_doc, "fm_rfc_validated", 0)

		# 1. VERDE: RFC validado exitosamente
		if rfc_validated:
			self._validation_status = "green"
			self._validation_message = "✅ DATOS FISCALES VALIDADOS"
			return

		# 2. VERIFICAR SI DATOS ESTÁN COMPLETOS PARA VALIDACIÓN
		# RFC debe existir
		if not customer_doc.tax_id:
			self._validation_status = "red"
			self._validation_message = "🔴 FALTA RFC"
			return

		# Dirección principal debe existir y estar completa
		if not primary_address:
			self._validation_status = "red"
			self._validation_message = "🔴 FALTA DIRECCIÓN PRINCIPAL"
			return

		# Verificar campos críticos de dirección
		missing_fields = []
		if not primary_address.address_line1:
			missing_fields.append("Calle")
		if not primary_address.pincode:
			missing_fields.append("CP")
		if not primary_address.city:
			missing_fields.append("Ciudad")
		if not primary_address.state:
			missing_fields.append("Estado")
		if not primary_address.country:
			missing_fields.append("País")

		if missing_fields:
			self._validation_status = "red"
			self._validation_message = f"🔴 FALTA EN DIRECCIÓN: {', '.join(missing_fields)}"
			return

		# 3. AMARILLO: Datos completos pero no validados
		self._validation_status = "yellow"
		self._validation_message = "🟡 LISTO PARA VALIDAR RFC/CSF"
