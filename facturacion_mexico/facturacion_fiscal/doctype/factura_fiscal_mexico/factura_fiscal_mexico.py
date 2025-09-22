import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_address_display
from frappe.model.document import Document
from frappe.utils import flt, now_datetime

from facturacion_mexico.sat.constants import TIPO_COMPROBANTE, TIPO_RELACION, parse_select_code

# Lista blanca de campos permisibles tras submit (operativos, no fiscales)
MUTABLE_AFTER_SUBMIT = {
	"fm_sync_status",  # Select: synced/pending/error
	"fm_sync_error",  # Texto de error técnico
	"fm_last_sync_ts",  # Timestamp último intento (si existe)
	"facturapi_response_log",  # Link al log
	"fm_pac_attempts",  # Contador interno (si existe)
	"fm_last_response_log",  # Link al último log de respuesta
	"fm_last_pac_sync",  # Timestamp última sincronización PAC
}

# Estados en los que el CFDI ya no debe alterarse
FISCAL_FROZEN_STATES = {"TIMBRADO", "CANCELADO", "PENDIENTE_CANCELACION"}

# Estados de sincronización permitidos (minúsculas)
ALLOWED_SYNC = {"synced", "pending", "error"}

# === START: FFM IMMUTABILITY CONSTANTS & HELPERS ===
# Campos de ENTRADA del usuario que NO deben cambiar post-submit
_LOCKED_AFTER_SUBMIT_FIELDS = [
	"fm_payment_method_sat",  # PUE / PPD (Método de Pago)
	"fm_forma_pago_timbrado",  # Forma de Pago
]

# Campos que devuelve/actualiza el SAT (SÍ deben poder cambiar por el proceso backend)
_SAT_UPDATABLE_FIELDS = [
	# Identificación fiscal
	"fm_uuid",  # UUID timbrado
	"fm_rfc_pac",  # RFC del PAC
	"fm_no_certificado_sat",  # No. certificado SAT
	# Serie/Folio/Fechas/Sellos
	"fm_serie_folio",  # Serie-Folio completo si lo guardan así
	"fm_serie",  # Serie (si lo guardan separado)
	"fm_folio",  # Folio (si lo guardan separado)
	"fm_fecha_timbrado",  # Fecha/hora de timbrado
	"fm_sello_sat",  # Sello SAT
	"fm_sello_cfd",  # Sello CFDI (si aplica)
	"fm_cadena_original",  # Cadena original del complemento timbre
	# Archivos/Representaciones
	"fm_xml_cfdi",  # XML CFDI (string/base64/path)
	"fm_xml_uuid",  # Si guardan xml específico por uuid
	"fm_qr",  # QR o datos para QR
	"fm_pdf_url",  # URL PDF si PAC lo provee
	"fm_xml_url",  # URL XML si PAC lo provee
	# Estado y sincronización que el backend controla
	"fm_fiscal_status",  # Estado fiscal (BORRADOR, ERROR, TIMBRADO, CANCELADO, …)
	"fm_sync_status",  # synced/pending/error (normalizado a minúsculas en before_validate)
	"fm_sync_error",  # último error textual de sincronización
]
# === END: FFM IMMUTABILITY CONSTANTS & HELPERS ===


def _normalize_sync_status(val: str) -> str:
	"""Normalizar estado de sincronización a minúsculas válidas."""
	if not val:
		return "pending"
	v = str(val).strip().lower()
	return v if v in ALLOWED_SYNC else "pending"


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

	def before_validate(self):
		"""Ejecutar antes de validate() - timing crítico para Select."""
		# CRÍTICO: Se ejecuta ANTES de _validate_selects()
		self._normalize_sync()

		# Bloqueo de cambios manuales a PUE/PPD y Forma de Pago tras submit
		self._assert_payment_fields_immutable_after_submit()

	def before_save(self):
		"""Ejecutar antes de guardar."""
		# Redundancia defensiva por si algo se cuela después de before_validate
		self._normalize_sync()

		# Cargar datos desde Sales Invoice si no están establecidos
		if self.sales_invoice:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)

			# Si no hay empresa vendedora, obtenerla de Sales Invoice
			if not self.company:
				self.company = sales_invoice.company

			# Si no hay customer, obtenerlo de Sales Invoice
			if not self.customer:
				self.customer = sales_invoice.customer

	def before_insert(self):
		if not (self.fm_payment_method_sat or "").strip() or self.fm_payment_method_sat == "PUE":
			self.fm_payment_method_sat = (
				frappe.db.get_single_value("Facturacion Mexico Settings", "metodo_pago_default") or "PUE"
			)

		# Asignar fm_enviar_email_timbrado usando lógica cascade Customer/Settings
		try:
			from frappe.utils import cint

			flag = _resolve_auto_email_flag(self.customer)
			self.fm_enviar_email_timbrado = cint(flag)
		except Exception as e:
			# Si algo falla, NO forzar; dejar en 0 (seguro)
			self.fm_enviar_email_timbrado = 0
			frappe.logger().warning(f"[FFM before_insert] No se pudo resolver auto-email: {e}")

	def validate(self):
		"""Validar factura fiscal antes de guardar."""
		# NUEVAS VALIDACIONES: Inmutabilidad (normalización ya hecha en before_validate)

		# Establecer automáticamente el tipo según la SI origen
		self._set_tipo_from_context()

		# Validaciones tipo de comprobante
		self.validate_tipo_comprobante()

		# Validaciones existentes
		self.validate_sales_invoice()
		self.validate_company_match()
		self.validate_customer_fiscal_change()
		self.validate_status_transitions()

		# Validaciones fiscales migradas desde Sales Invoice
		self.validate_cfdi_use()
		self.validate_payment_method()
		self.validate_ppd_vs_forma_pago()

	def _normalize_sync(self):
		"""Normalizar estado de sincronización a minúsculas."""
		if hasattr(self, "fm_sync_status") and self.fm_sync_status:
			self.fm_sync_status = _normalize_sync_status(self.fm_sync_status)

	def _assert_payment_fields_immutable_after_submit(self):
		"""Bloquea cambios MANUALES a PUE/PPD y Forma de Pago cuando docstatus == 1.
		Permite escrituras del proceso SAT si se fija self.flags.fm_system_write = True."""
		if getattr(self, "docstatus", 0) != 1:
			return

		# Si viene del proceso de timbrado/SAT, permitir
		if getattr(self, "flags", None) and getattr(self.flags, "fm_system_write", False):
			return
		if frappe.flags.get("ignore_ffm_lock"):
			return

		if not self.name:
			return

		prev = frappe.db.get_value(self.doctype, self.name, _LOCKED_AFTER_SUBMIT_FIELDS, as_dict=True)
		if not prev:
			return

		changed = []
		for field in _LOCKED_AFTER_SUBMIT_FIELDS:
			old = prev.get(field)
			new = getattr(self, field, None)
			if old != new:
				changed.append((field, old, new))

		if changed:
			details = "<br>".join(
				[
					f"• {f}: {frappe.utils.escape_html(str(o))} → {frappe.utils.escape_html(str(n))}"
					for f, o, n in changed
				]
			)
			frappe.throw(
				_("No se permite modificar Método/Forma de Pago después de Submit.<br>{0}").format(details),
				frappe.ValidationError,
			)

	def validate_tipo_comprobante(self):
		"""Validar tipo de comprobante según propuesta ChatGPT."""
		# Reglas: solo I/E; T no implementado
		tipo = parse_select_code(self.fm_tipo_comprobante)
		if tipo not in ("I", "E"):
			frappe.throw(
				_("Traslado (T) no está habilitado en esta versión."),
				title=_("Tipo de comprobante no permitido"),
			)

		# SI normal => I
		if not self._is_sales_invoice_return() and tipo != "I":
			frappe.throw(_("Factura normal debe timbrarse como Ingreso (I)."), title=_("Validación FFM"))

		# SI retorno => E + relación obligatoria
		if self._is_sales_invoice_return():
			if tipo != "E":
				frappe.throw(
					_("Factura de retorno debe timbrarse como Egreso (E)."), title=_("Validación FFM")
				)
			# Relación
			rel = parse_select_code(self.fm_tipo_relacion_sat or "")
			if rel not in TIPO_RELACION:
				frappe.throw(_("Tipo de Relación SAT inválido o vacío."), title=_("Validación FFM"))
			if not self.fm_uuid_relacionado:
				frappe.throw(
					_("UUID relacionado es obligatorio para Egreso (nota de crédito)."),
					title=_("Validación FFM"),
				)
			self._validate_uuid_origen()

	def _is_sales_invoice_return(self) -> bool:
		"""Determinar si la Sales Invoice es un retorno."""
		if not self.sales_invoice:
			return False
		sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
		return bool(getattr(sales_invoice, "is_return", 0))

	def _set_tipo_from_context(self):
		"""Establecer tipo automáticamente según contexto."""
		if self._is_sales_invoice_return():
			self.fm_tipo_comprobante = "E - Egreso"
			# autollenar relación
			self.fm_tipo_relacion_sat = self.fm_tipo_relacion_sat or "01 - " + TIPO_RELACION["01"]
			self.fm_uuid_relacionado = self.fm_uuid_relacionado or self._find_uuid_cfdi_origen()
		else:
			self.fm_tipo_comprobante = "I - Ingreso"
			self.fm_tipo_relacion_sat = None
			self.fm_uuid_relacionado = None

	def _find_uuid_cfdi_origen(self) -> str | None:
		"""Buscar UUID del CFDI original."""
		# TODO: Implementar lógica que busque el UUID del CFDI original
		# 1) FFM relacionado a la SI origen, o
		# 2) Campo en la Sales Invoice original.
		return getattr(self, "uuid_origen", None)

	def _validate_uuid_origen(self):
		"""Validar UUID relacionado."""
		uuid = self.fm_uuid_relacionado
		if not uuid or len(uuid) < 36:
			frappe.throw(_("UUID relacionado no parece válido."), title=_("Validación FFM"))
		# TODO: Verificar en tabla/log de timbrados si ese UUID pertenece al receptor actual

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

		# M4-02/03/04: Solo bloquear si existe una FFM ACTIVA (no drafts, no canceladas)
		active_exists = frappe.db.exists(
			"Factura Fiscal Mexico",
			{
				"sales_invoice": self.sales_invoice,
				"name": ("!=", self.name),
				"docstatus": 1,  # Solo enviadas
				"fm_fiscal_status": ("in", ["TIMBRADO", "PENDIENTE_CANCELACION", "PROCESANDO"]),
			},
		)

		if active_exists:
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

		# Definir transiciones válidas - ARQUITECTURA RESILIENTE
		valid_transitions = {
			None: ["BORRADOR"],  # Documento nuevo puede ser BORRADOR
			"": ["BORRADOR"],  # Estado vacío puede ir a BORRADOR
			"BORRADOR": ["PROCESANDO", "TIMBRADO", "CANCELADO", "ERROR"],
			"PROCESANDO": ["TIMBRADO", "ERROR", "CANCELADO"],
			"TIMBRADO": ["CANCELADO", "PENDIENTE_CANCELACION"],
			"ERROR": ["BORRADOR", "PROCESANDO", "TIMBRADO"],  # Puede reintentarse
			"CANCELADO": [],  # Estado final
			"PENDIENTE_CANCELACION": ["CANCELADO", "TIMBRADO"],  # Puede confirmar cancelación o regresar
			"ARCHIVADO": [],  # Estado final
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

			if existing_status == "TIMBRADO":
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
				"fm_fiscal_status": "TIMBRADO",
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

		# Detectar cambio de customer y repoblar datos
		if self.has_value_changed("customer"):
			self.populate_billing_data()

		# NO actualizar campo status - es manejado por Frappe
		# self.calculate_status_from_fiscal_status() # DEPRECADO - no usar campo status estándar

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
					else "BORRADOR",
					"new_status": self.fm_fiscal_status,
					"uuid": self.fm_uuid,
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
		"""Crear evento fiscal - ELIMINACIÓN EN PROGRESO (FASE 0)."""
		try:
			# GUARD INMEDIATO: Verificar existencia DocType
			if not frappe.db.exists("DocType", "Fiscal Event MX"):
				# FALLBACK: Usar Response Log como única fuente verdad
				self._log_event_to_response_log(event_type, event_data)
				return None

			# Código original (si DocType existe - transición suave)
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
			# ERROR: También loggear en Response Log
			self._log_event_to_response_log(
				f"error_{event_type}", {"error": str(e), "original_data": event_data}
			)
			frappe.log_error(f"Error creating fiscal event: {e!s}", "Fiscal Event Creation Error")

	def _log_event_to_response_log(self, event_type, event_data):
		"""Fallback: usar Response Log para eventos fiscales."""
		try:
			import json

			from facturacion_mexico.facturacion_fiscal.doctype.facturapi_response_log.facturapi_response_log import (
				write_pac_response,
			)

			write_pac_response(
				self.sales_invoice or self.name,
				json.dumps({"event_type": event_type, "source": "fiscal_event_fallback"}),
				json.dumps(event_data),
				f"fiscal_event_{event_type}",
			)

			frappe.logger().info(f"Fiscal event logged to Response Log: {event_type} for {self.name}")

		except Exception as fallback_error:
			frappe.log_error(
				f"Error in fiscal event fallback: {fallback_error!s}\nOriginal event: {event_type}\nData: {event_data}",
				"Fiscal Event Fallback Error",
			)

	def update_sales_invoice_fiscal_info(self):
		"""Actualizar información fiscal en Sales Invoice."""
		if not self.sales_invoice:
			return

		# Mapear estados para Sales Invoice (ya están en español)
		status_map = {
			"BORRADOR": "BORRADOR",
			"PROCESANDO": "PROCESANDO",
			"TIMBRADO": "TIMBRADO",
			"ERROR": "ERROR",
			"CANCELADO": "CANCELADO",
			"PENDIENTE_CANCELACION": "PENDIENTE_CANCELACION",
			"ARCHIVADO": "ARCHIVADO",
		}

		try:
			frappe.db.set_value(
				"Sales Invoice",
				self.sales_invoice,
				{
					"fm_fiscal_status": status_map.get(self.fm_fiscal_status, "BORRADOR"),
					"fm_factura_fiscal_mx": self.name,
				},
			)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit - Required to ensure Sales Invoice fiscal info is persisted
		except Exception as e:
			frappe.log_error(f"Error updating Sales Invoice fiscal info: {e!s}", "Sales Invoice Update Error")

	def mark_as_stamped(self, facturapi_data):
		"""Marcar como timbrada con datos de FacturAPI."""
		self.fm_fiscal_status = "TIMBRADO"
		self.facturapi_id = facturapi_data.get("id")
		self.fm_uuid = facturapi_data.get("uuid")
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
		self.fm_fiscal_status = "CANCELADO"
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

			filename = f"{self.name}_{self.fm_uuid}.{file_type}"
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
		if self.fm_fiscal_status != "BORRADOR":
			frappe.throw(_("Solo se pueden timbrar facturas en estado BORRADOR"))

		# Aquí se integraría con FacturAPI.io
		# Por ahora solo cambiar el estado para testing
		frappe.msgprint(_("Solicitud de timbrado enviada"))
		return {"message": "Stamping requested"}

	@frappe.whitelist()
	def request_cancellation(self):
		"""Solicitar cancelación fiscal."""
		if self.fm_fiscal_status != "TIMBRADO":
			frappe.throw(_("Solo se pueden cancelar facturas timbradas"))

		self.fm_fiscal_status = "CANCELADO"
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
		if self.fm_fiscal_status == "BORRADOR" and self.is_new():
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
		# Solo si sigue vacío (no sobreescribir elección del usuario)
		if not (self.fm_payment_method_sat or "").strip():
			try:
				settings = frappe.get_single("Facturacion Mexico Settings")
				self.fm_payment_method_sat = (getattr(settings, "metodo_pago_default", None) or "PUE").strip()
			except Exception:
				self.fm_payment_method_sat = "PUE"

		# Validar que el método existe
		valid_methods = ["PUE", "PPD"]
		if self.fm_payment_method_sat not in valid_methods:
			frappe.throw(_("Método de pago SAT inválido. Use PUE o PPD"))

		# Validar coherencia con forma de pago
		if self.fm_payment_method_sat == "PPD" and self.sales_invoice:
			sales_invoice = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if sales_invoice.is_return:
				frappe.throw(_("Las notas de crédito no pueden usar método PPD"))

	def _ensure_payment_method_default(self):
		# Solo si sigue vacío (no sobreescribir elección del usuario)
		if not (self.fm_payment_method_sat or "").strip():
			try:
				settings = frappe.get_single("Facturacion Mexico Settings")
				self.fm_payment_method_sat = (getattr(settings, "metodo_pago_default", None) or "PUE").strip()
			except Exception:
				self.fm_payment_method_sat = "PUE"

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
			new_status = "BORRADOR"  # Estado por defecto

			if latest_log:
				operation_type = latest_log[0] if isinstance(latest_log, tuple) else latest_log

				# Mapear operaciones a estados
				status_map = {"Timbrado": "TIMBRADO", "Confirmación Cancelación": "CANCELADO"}

				new_status = status_map.get(operation_type, "BORRADOR")

			# Verificar si hay solicitudes de cancelación pendientes
			pending_cancellation = frappe.db.exists(
				"FacturAPI Response Log",
				{"factura_fiscal_mexico": self.name, "success": 1, "operation_type": "Solicitud Cancelación"},
			)

			# Si hay solicitud de cancelación pero no confirmación, estado intermedio
			if pending_cancellation and new_status == "TIMBRADO":
				confirmation_exists = frappe.db.exists(
					"FacturAPI Response Log",
					{
						"factura_fiscal_mexico": self.name,
						"success": 1,
						"operation_type": "Confirmación Cancelación",
					},
				)

				if not confirmation_exists:
					new_status = "PENDIENTE_CANCELACION"

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
				new_status = "ERROR"

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
			"BORRADOR": "draft",
			"PROCESANDO": "processing",
			"TIMBRADO": "stamped",
			"ERROR": "error",
			"CANCELADO": "cancelled",
			"PENDIENTE_CANCELACION": "pending_cancellation",
			"ARCHIVADO": "archived",
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
			self.fm_tax_system = "⚠️ SELECCIONA UN CLIENTE"
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

			# Tax System desde Tax Category (MIGRACIÓN ARQUITECTURAL)
			self.fm_tax_system = (
				self._extract_tax_system_from_customer(customer_doc) or "⚠️ FALTA TAX CATEGORY EN CUSTOMER"
			)
			# Tax system code extraído desde customer.tax_category

			# Buscar dirección principal
			primary_address = self._get_primary_address()
			# Obtener dirección principal del customer

			if primary_address:
				# Poblar datos desde dirección principal
				self.fm_cp_cliente = primary_address.pincode or "⚠️ FALTA CP EN DIRECCIÓN"
				self.fm_email_facturacion = primary_address.email_id or "⚠️ FALTA EMAIL EN DIRECCIÓN"
				self.fm_direccion_principal_link = primary_address.name
				self.fm_direccion_principal_display = self._get_primary_address_display()
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
			self.fm_tax_system = "❌ ERROR AL OBTENER TAX SYSTEM"
			self.fm_direccion_principal_link = ""
			self.fm_direccion_principal_display = f"❌ Error: {e!s}"

	def _get_primary_address(self):
		"""Usar la misma fuente que ERPNext: default address del Customer, con fallback a customer_primary_address y, por último, a links."""
		if not self.customer:
			return None

		# 1) Igual que ERPNext: default address (simulamos get_default_address ya que no está disponible en v15)
		addr_name = None
		try:
			# Buscar address marcada como is_primary_address para este customer
			primary_addresses = frappe.get_all("Address", filters={"is_primary_address": 1}, fields=["name"])

			for addr in primary_addresses:
				# Verificar si esta address está vinculada a nuestro customer
				linked = frappe.db.exists(
					"Dynamic Link",
					{
						"link_doctype": "Customer",
						"link_name": self.customer,
						"parent": addr.name,
						"parenttype": "Address",
					},
				)
				if linked:
					addr_name = addr.name
					break
		except Exception:
			pass

		# 2) Fallback: campo customer_primary_address si estuviera lleno
		if not addr_name:
			addr_name = frappe.db.get_value("Customer", self.customer, "customer_primary_address")

		# 3) Fallback final: primera Address ligada por Dynamic Link (como tenías)
		if not addr_name:
			linked = frappe.get_all(
				"Dynamic Link",
				filters={"link_doctype": "Customer", "link_name": self.customer, "parenttype": "Address"},
				pluck="parent",
			)
			if linked:
				addr_name = linked[0]

		return frappe.get_doc("Address", addr_name) if addr_name else None

	def _get_primary_address_display(self):
		"""Formateo estándar de Frappe, igual que en Customer UI."""
		addr = self._get_primary_address()
		if not addr:
			return ""
		return get_address_display(addr.as_dict()) or ""

	def _format_address(self, address_doc):
		"""Formatear dirección para display (DEPRECATED - usar _get_primary_address_display)."""
		if not address_doc:
			return ""
		# Delegar al método estándar para consistencia
		return get_address_display(address_doc.as_dict()) or ""

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

	def _extract_tax_system_from_customer(self, customer_doc):
		"""
		Extraer código de régimen fiscal desde Tax Category del cliente.

		MIGRACIÓN ARQUITECTURAL: fm_regimen_fiscal → tax_category
		Tax Category tiene formato "601 - General de Ley Personas Morales"
		Extraer código "601" para FacturAPI.

		Args:
			customer_doc: Documento Customer

		Returns:
			str: Código del régimen fiscal (ej: "601") o None si no disponible
		"""
		if not customer_doc or not hasattr(customer_doc, "tax_category"):
			return None

		tax_category = customer_doc.tax_category
		if not tax_category:
			return None

		# Tax Category tiene formato "601 - General de Ley Personas Morales"
		# Extraer código "601"
		if " - " in tax_category:
			code = tax_category.split(" - ")[0].strip()
			# Validar que el código sea numérico SAT (3 dígitos)
			if code.isdigit() and len(code) == 3:
				return code

		# Si no tiene formato esperado, retornar el valor completo limpio
		return tax_category.strip() if tax_category else None

	def before_cancel(self):
		"""Hook contextual: Permitir cancelación FFM solo si ya cancelada fiscalmente."""
		# BYPASS CONTROLADO: solo para FFM sin timbre, invocado por nuestro endpoint
		if not getattr(self, "fm_uuid", None) and getattr(self.flags, "allow_local_cancel", False):
			# No aplicar validaciones PAC; cancelación local permitida
			return

		if self.sales_invoice and self.fm_fiscal_status != "CANCELADO":
			frappe.throw(
				_(
					"No puede cancelarse la FFM: primero cancela fiscalmente en el PAC.<br><br>"
					"<b>Secuencia correcta:</b><br>"
					"1️⃣ Cancelar en FacturAPI (botón 'Cancelar en FacturAPI')<br>"
					"2️⃣ Cancelar FFM (botón 'Cancel' de Frappe)<br>"
					"3️⃣ Cancelar Sales Invoice (desde Sales Invoice)"
				),
				title=_("Secuencia de cancelación requerida"),
			)
		# Si fm_fiscal_status="CANCELADO" → permite cancelación DocType


@frappe.whitelist()
def sat_options():
	"""API para obtener opciones SAT centralizadas."""
	from facturacion_mexico.sat.constants import select_options_tipo_comprobante, select_options_tipo_relacion

	return {
		"tipo_comprobante_options": select_options_tipo_comprobante(),  # ["I - Ingreso","E - Egreso"]
		"tipo_relacion_options": select_options_tipo_relacion(),  # ["01 - Nota ...", "03 - ...", ...]
	}


@frappe.whitelist()
def get_sales_invoice_for_ffm(doctype, txt, searchfield, start, page_len, filters):
	"""
	Devuelve SOLO Sales Invoices elegibles para FFM:
	  - si.docstatus = 1 (enviadas)
	  - Customer con RFC validado (fm_rfc_validated = 1) y tax_id no vacío
	  - Sin FFM activa asociada (evita doble timbrado)
	  - (opcional) misma company si viene en filters
	"""
	company = (filters or {}).get("company")
	allowed = {"name", "customer", "posting_date"}
	sf = searchfield if searchfield in allowed else "name"
	return frappe.db.sql(
		f"""
		SELECT
			si.name, si.customer, si.posting_date
		FROM `tabSales Invoice` si
		INNER JOIN `tabCustomer` c ON c.name = si.customer
		LEFT JOIN `tabFactura Fiscal Mexico` ffm
			   ON ffm.sales_invoice = si.name AND ffm.docstatus < 2
		WHERE si.docstatus = 1
		  AND (%(company)s IS NULL OR si.company = %(company)s)
		  AND COALESCE(NULLIF(TRIM(c.tax_id), ''), '') <> ''
		  AND COALESCE(c.fm_rfc_validated, 0) = 1
		  AND ffm.name IS NULL
		  AND si.{sf} LIKE %(txt)s
		ORDER BY si.posting_date DESC
		LIMIT %(start)s, %(page_len)s
	""",
		{"company": company, "txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def check_si_customer_rfc_validated(si_name: str):
	"""Valida que la SI seleccionada tenga cliente con RFC validado (respaldo en on_change)."""
	if not si_name:
		return {"ok": False}
	row = frappe.db.sql(
		"""
		SELECT
			COALESCE(c.fm_rfc_validated,0) AS ok,
			COALESCE(NULLIF(TRIM(c.tax_id),''),'') AS rfc
		FROM `tabSales Invoice` si
		INNER JOIN `tabCustomer` c ON c.name = si.customer
		WHERE si.name = %s
	""",
		(si_name,),
		as_dict=True,
	)
	if not row:
		return {"ok": False}
	return {"ok": bool(row[0].ok and row[0].rfc)}


@frappe.whitelist()
def cancel_ffm_keep_si(ffm_name: str):
	"""Cancela SOLO la FFM (sin cfdi_uuid) y libera la Sales Invoice enlazada.
	- Requiere rol: System Manager o Facturacion Mexico System Manager
	- Deja la SI viva (docstatus=1) y sin link a FFM, lista para reintentar.
	"""
	frappe.only_for(("System Manager", "Facturacion Mexico System Manager"))

	ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
	if ffm.docstatus != 1 or getattr(ffm, "fm_uuid", None):
		frappe.throw(_("Solo disponible para FFM enviadas SIN timbre."))

	si_name = ffm.sales_invoice
	frappe.db.begin()
	try:
		# 1) Romper vínculo en SI (si existe)
		if si_name and frappe.db.get_value("Sales Invoice", si_name, "fm_factura_fiscal_mx"):
			frappe.db.set_value("Sales Invoice", si_name, "fm_factura_fiscal_mx", None)

		# 2) Cancelar FFM con flag de bypass
		ffm.add_comment("Workflow", _("Cancelación FFM (sin timbre). SI liberada para reintento."))
		ffm.flags.allow_local_cancel = True
		ffm.cancel()

		frappe.db.commit()
		return {"status": "ok", "ffm": ffm.name, "si": si_name}
	except Exception:
		frappe.db.rollback()
		frappe.log_error(frappe.get_traceback(), "cancel_ffm_keep_si failed")
		raise


# ========== EMAIL AUTOMATION LOGIC ==========


def _get_settings_email_defaults():
	"""Lee settings existentes (NO crear campos nuevos).
	Debe devolver:
		- default_on: 0/1 (enviar por defecto)
		- fallback_email: str o None
	"""
	from frappe.utils import cint

	settings = frappe.get_single("Facturacion Mexico Settings")
	# AJUSTAR nombres de fields existentes en settings
	default_on = cint(getattr(settings, "send_email_default", 0))
	fallback_email = getattr(settings, "customer_email_fallback", None)
	return default_on, (fallback_email or "").strip() or None


def _resolve_auto_email_flag(customer_name: str) -> int:
	"""Aplica la cascada Settings -> Customer tri-estado. Devuelve 0/1."""
	from frappe.utils import cint

	default_on, _ = _get_settings_email_defaults()

	opt = None
	if customer_name:
		opt = frappe.db.get_value("Customer", customer_name, "fm_envio_email_cliente")

	# Customer decide:
	if opt == "Enviar":
		return 1
	if opt == "No enviar":
		return 0
	# Default (usar settings) o None -> usar settings:
	return default_on


def _resolve_recipient_email(ffm_doc) -> str | None:
	"""Devuelve el email final según regla estricta:
	1) FFM.fm_email_facturacion
	2) Settings.customer_email_fallback
	3) None si no hay
	"""
	_, fallback = _get_settings_email_defaults()
	ffm_email = (getattr(ffm_doc, "fm_email_facturacion", "") or "").strip()
	result = ffm_email or fallback or None
	return result


def _send_cfdi_email(self, to_override: str | None = None) -> dict:
	"""Envía el CFDI por email usando el endpoint/método EXISTENTE.
	No inventa rutas nuevas; aquí solo orquestamos.
	"""

	# Visibilidad: sólo si está timbrada
	uuid_value = getattr(self, "fm_uuid", None)
	if not uuid_value:
		frappe.throw(_("La FFM no está timbrada (no tiene UUID)."))

	to_email = to_override or _resolve_recipient_email(self)
	if not to_email:
		self.add_comment("Comment", "No se envió CFDI: no hay destinatario (FFM ni fallback settings).")
		return {"sent": False, "reason": "no-recipient"}

	try:
		# BLOQUE A AJUSTAR a tu integración vigente
		from facturacion_mexico.facturacion_fiscal.api_client import FacturAPIClient

		api = FacturAPIClient()
		facturapi_id = getattr(self, "facturapi_id", None)
		if not facturapi_id:
			frappe.throw(_("No se encontró el identificador de FacturAPI para enviar el email."))

		api.send_invoice_email(facturapi_id, to_email)

		self.add_comment("Comment", f"CFDI enviado por email a: {to_email}")
		return {"sent": True, "to": to_email}
	except Exception as e:
		self.add_comment("Comment", f"Error al enviar CFDI por email: {e}")
		return {"sent": False, "error": str(e)}


@frappe.whitelist()
def action_send_cfdi_email(ffm_name: str, to: str | None = None):
	"""Whitelisted para el botón manual en FFM (usa el MISMO flujo).
	NO crea endpoints nuevos de integraciones; sólo orquesta.
	"""
	doc = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
	frappe.has_permission(doctype="Factura Fiscal Mexico", ptype="write", doc=doc, throw=True)
	out = _send_cfdi_email(doc, to_override=to)
	return out
