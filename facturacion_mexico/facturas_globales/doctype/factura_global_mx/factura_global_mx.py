"""
Factura Global MX - Sprint 4 Semana 1
DocType para agrupar E-Receipts en facturas globales fiscales
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate, now_datetime


class FacturaGlobalMX(Document):
	"""Factura Global MX - Agrupación de E-Receipts para timbrado fiscal."""

	def autoname(self):
		"""Generar nombre automático siguiendo patrón FG-{company}-{YYYY}-{MM}-{####}."""
		if not self.company:
			frappe.throw(_("Company es requerido para generar el nombre"))

		# Obtener año y mes del período inicio
		fecha = getdate(self.periodo_inicio) if self.periodo_inicio else getdate()
		year = fecha.strftime("%Y")
		month = fecha.strftime("%m")

		# Generar nombre base
		prefix = f"FG-{self.company}-{year}-{month}-"

		# Obtener siguiente número
		count = (
			frappe.db.count(
				"Factura Global MX", filters={"company": self.company, "name": ["like", f"{prefix}%"]}
			)
			+ 1
		)

		self.name = f"{prefix}{count:04d}"

	def validate(self):
		"""Validaciones del documento."""
		self.validate_period_dates()
		self.validate_company_settings()
		self.check_period_overlaps()
		self.set_audit_fields()

	def before_save(self):
		"""Antes de guardar - calcular totales."""
		self.calculate_totals()

	def before_submit(self):
		"""Antes de enviar - validar receipts y generar CFDI."""
		self.validate_receipts_availability()
		self.lock_included_receipts()
		self.generate_global_cfdi()

	def on_submit(self):
		"""Al enviar - marcar receipts y crear evento fiscal."""
		self.mark_receipts_as_included()
		self.create_fiscal_event()

	def on_cancel(self):
		"""Al cancelar - liberar receipts y cancelar en FacturAPI."""
		self.release_receipts()
		self.cancel_in_facturapi()

	def validate_period_dates(self):
		"""Validar fechas del período."""
		if not self.periodo_inicio or not self.periodo_fin:
			frappe.throw(_("Período inicio y fin son requeridos"))

		if getdate(self.periodo_inicio) > getdate(self.periodo_fin):
			frappe.throw(_("Fecha de inicio no puede ser posterior a fecha fin"))

		# Validar que el período no sea futuro
		if getdate(self.periodo_inicio) > getdate():
			frappe.throw(_("No se pueden crear facturas globales para períodos futuros"))

		# Validar duración máxima según periodicidad
		max_days = {"Diaria": 1, "Semanal": 7, "Quincenal": 15, "Mensual": 31}

		days_diff = (getdate(self.periodo_fin) - getdate(self.periodo_inicio)).days + 1
		if self.periodicidad and days_diff > max_days.get(self.periodicidad, 31):
			frappe.throw(
				_(
					"El período de {0} días excede el máximo permitido para periodicidad {1} ({2} días)"
				).format(days_diff, self.periodicidad, max_days.get(self.periodicidad))
			)

	def validate_company_settings(self):
		"""Validar configuración de la empresa."""
		settings = frappe.get_single("Facturacion Mexico Settings")

		if not settings.enable_global_invoices:
			frappe.throw(_("Las facturas globales no están habilitadas en la configuración"))

		# Validar serie si está configurada
		if settings.global_invoice_serie:
			self.serie = settings.global_invoice_serie

	def check_period_overlaps(self):
		"""Verificar que no existan facturas globales con períodos solapados."""
		if self.is_new():
			overlapping = frappe.db.sql(
				"""
				SELECT name, periodo_inicio, periodo_fin
				FROM `tabFactura Global MX`
				WHERE company = %(company)s
				AND docstatus != 2
				AND (
					(periodo_inicio <= %(periodo_fin)s AND periodo_fin >= %(periodo_inicio)s)
				)
			""",
				{
					"company": self.company,
					"periodo_inicio": self.periodo_inicio,
					"periodo_fin": self.periodo_fin,
				},
				as_dict=True,
			)

			if overlapping:
				overlap_names = [d.name for d in overlapping]
				frappe.throw(
					_("Ya existe factura global con período solapado: {0}").format(", ".join(overlap_names))
				)

	def calculate_totals(self):
		"""Calcular totales basados en receipts incluidos."""
		if not self.receipts_detail:
			self.total_periodo = 0
			self.cantidad_receipts = 0
			return

		total = 0
		for detail in self.receipts_detail:
			if detail.monto:
				total += flt(detail.monto)

		self.total_periodo = total
		self.cantidad_receipts = len(self.receipts_detail)

	def validate_receipts_availability(self):
		"""Validar que todos los receipts estén disponibles."""
		if not self.receipts_detail:
			frappe.throw(_("No hay E-Receipts seleccionados para la factura global"))

		for detail in self.receipts_detail:
			if not detail.ereceipt:
				continue

			# Verificar que el receipt existe y está disponible
			receipt_doc = frappe.get_doc("EReceipt MX", detail.ereceipt)

			if receipt_doc.included_in_global:
				frappe.throw(
					_("E-Receipt {0} ya está incluido en otra factura global").format(detail.ereceipt)
				)

			if receipt_doc.docstatus == 2:
				frappe.throw(_("E-Receipt {0} está cancelado y no puede incluirse").format(detail.ereceipt))

	def lock_included_receipts(self):
		"""Bloquear receipts incluidos para evitar duplicación."""
		for detail in self.receipts_detail:
			if detail.ereceipt:
				frappe.db.set_value(
					"EReceipt MX", detail.ereceipt, "included_in_global", 1, update_modified=False
				)

	def generate_global_cfdi(self):
		"""Generar CFDI global en FacturAPI.io."""
		start_time = now_datetime()  # Inicializar al comienzo para garantizar disponibilidad

		try:
			from facturacion_mexico.facturas_globales.processors.cfdi_global_builder import CFDIGlobalBuilder

			self.status = "Processing"

			# Construir datos para FacturAPI
			builder = CFDIGlobalBuilder(self)
			cfdi_data = builder.build_global_invoice_data()

			# Timbrar en FacturAPI
			from facturacion_mexico.facturacion_fiscal.api import create_invoice_facturapi

			result = create_invoice_facturapi(cfdi_data)

			if result.get("success"):
				self.facturapi_id = result.get("facturapi_id")
				self.uuid = result.get("uuid")
				self.folio = result.get("folio")
				self.pdf_file = result.get("pdf_url")
				self.xml_file = result.get("xml_url")
				self.status = "Stamped"
			else:
				self.status = "Error"
				self.error_message = result.get("message", "Error desconocido en FacturAPI")
				frappe.throw(_("Error al timbrar factura global: {0}").format(self.error_message))

		except Exception as e:
			self.status = "Error"
			self.error_message = str(e)
			frappe.log_error(f"Error generando CFDI global {self.name}: {e}")
			frappe.throw(_("Error generando CFDI global: {0}").format(str(e)))

		finally:
			# Calcular tiempo de procesamiento
			end_time = now_datetime()
			self.processing_time = (end_time - start_time).total_seconds()

	def mark_receipts_as_included(self):
		"""Marcar receipts como incluidos en factura global."""
		for detail in self.receipts_detail:
			if detail.ereceipt:
				frappe.db.set_value(
					"EReceipt MX",
					detail.ereceipt,
					{"global_invoice": self.name, "available_for_global": 0},
					update_modified=False,
				)

	def release_receipts(self):
		"""Liberar receipts al cancelar factura global."""
		for detail in self.receipts_detail:
			if detail.ereceipt:
				frappe.db.set_value(
					"EReceipt MX",
					detail.ereceipt,
					{"included_in_global": 0, "global_invoice": None, "available_for_global": 1},
					update_modified=False,
				)

	def cancel_in_facturapi(self):
		"""Cancelar factura en FacturAPI.io."""
		if not self.facturapi_id:
			return

		try:
			from facturacion_mexico.facturacion_fiscal.api import cancel_invoice_facturapi

			result = cancel_invoice_facturapi(self.facturapi_id, "Cancelación de factura global")

			if not result.get("success"):
				frappe.log_error(
					f"Error cancelando factura global en FacturAPI: {result.get('message')}",
					"Factura Global Cancel Error",
				)

		except Exception as e:
			frappe.log_error(f"Error cancelando factura global {self.name}: {e}")

	def create_fiscal_event(self):
		"""Crear evento fiscal para auditoría."""
		try:
			fiscal_event = frappe.get_doc(
				{
					"doctype": "Fiscal Event",
					"event_type": "Factura Global Creada",
					"reference_doctype": "Factura Global MX",
					"reference_name": self.name,
					"company": self.company,
					"event_data": frappe.as_json(
						{
							"periodo_inicio": self.periodo_inicio,
							"periodo_fin": self.periodo_fin,
							"total_periodo": self.total_periodo,
							"cantidad_receipts": self.cantidad_receipts,
							"uuid": self.uuid,
						}
					),
					"fiscal_impact": self.total_periodo,
				}
			)
			fiscal_event.insert(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error creando evento fiscal para {self.name}: {e}")

	def set_audit_fields(self):
		"""Establecer campos de auditoría."""
		if self.is_new():
			self.created_by = frappe.session.user
			self.creation_timestamp = now_datetime()

		self.modified_by = frappe.session.user
		self.modified_timestamp = now_datetime()

	# Métodos helper para APIs

	def get_receipts_summary(self):
		"""Obtener resumen de receipts incluidos."""
		if not self.receipts_detail:
			return {}

		summary = {
			"total_receipts": len(self.receipts_detail),
			"total_amount": self.total_periodo,
			"receipts_by_day": {},
			"tax_breakdown": {},
		}

		# Agrupar por día
		for detail in self.receipts_detail:
			day = detail.fecha_receipt.strftime("%Y-%m-%d") if detail.fecha_receipt else "Sin fecha"
			if day not in summary["receipts_by_day"]:
				summary["receipts_by_day"][day] = {"count": 0, "amount": 0}

			summary["receipts_by_day"][day]["count"] += 1
			summary["receipts_by_day"][day]["amount"] += flt(detail.monto)

		return summary

	@staticmethod
	def get_available_receipts(company, periodo_inicio, periodo_fin):
		"""Obtener E-Receipts disponibles para factura global."""
		return frappe.db.sql(
			"""
			SELECT
				name as ereceipt,
				folio,
				receipt_date as fecha_receipt,
				total_amount as monto,
				customer_name,
				1 as available_for_global
			FROM `tabEReceipt MX`
			WHERE company = %(company)s
			AND receipt_date BETWEEN %(periodo_inicio)s AND %(periodo_fin)s
			AND docstatus = 1
			AND (included_in_global IS NULL OR included_in_global = 0)
			AND (available_for_global IS NULL OR available_for_global = 1)
			ORDER BY receipt_date, folio
		""",
			{"company": company, "periodo_inicio": periodo_inicio, "periodo_fin": periodo_fin},
			as_dict=True,
		)

	def test_configuration(self, dry_run=True):
		"""Probar configuración de factura global."""
		results = {"success": True, "validations": [], "warnings": [], "receipt_preview": [], "totals": {}}

		try:
			# Validar período
			self.validate_period_dates()
			results["validations"].append("✅ Período válido")

			# Validar configuración
			self.validate_company_settings()
			results["validations"].append("✅ Configuración de empresa válida")

			# Obtener receipts disponibles
			available_receipts = self.get_available_receipts(
				self.company, self.periodo_inicio, self.periodo_fin
			)

			if not available_receipts:
				results["warnings"].append("⚠️ No hay E-Receipts disponibles en el período")
			else:
				results["receipt_preview"] = available_receipts[:10]  # Primeros 10
				results["totals"] = {
					"total_receipts": len(available_receipts),
					"total_amount": sum(flt(r.monto) for r in available_receipts),
				}
				results["validations"].append(f"✅ {len(available_receipts)} receipts disponibles")

		except Exception as e:
			results["success"] = False
			results["validations"].append(f"❌ Error: {e!s}")

		return results
