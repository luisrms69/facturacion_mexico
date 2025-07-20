import json
from datetime import datetime

import frappe
from frappe.model.document import Document
from frappe.model.naming import make_autoname


class ComplementoPagoMX(Document):
	def autoname(self):
		self.name = make_autoname(self.naming_series)

	def validate(self):
		self.validate_fecha_pago()
		self.validate_monto_positivo()
		self.validate_tipo_cambio()
		self.validate_documentos_relacionados()

	def validate_fecha_pago(self):
		if self.fecha_pago and self.fecha_pago > datetime.now():
			frappe.throw("La fecha de pago no puede ser mayor a la fecha actual")

	def validate_monto_positivo(self):
		if self.monto_p and self.monto_p <= 0:
			frappe.throw("El monto del pago debe ser mayor a cero")

	def validate_tipo_cambio(self):
		if self.moneda_p != "MXN" and not self.tipo_cambio_p:
			frappe.throw("Debe especificar el tipo de cambio para monedas extranjeras")

		if self.moneda_p == "MXN" and self.tipo_cambio_p and self.tipo_cambio_p != 1:
			frappe.throw("El tipo de cambio para pesos mexicanos debe ser 1")

	def validate_documentos_relacionados(self):
		if not self.documentos_relacionados:
			frappe.throw("Debe especificar al menos un documento relacionado al pago")

		total_documentos = sum([doc.imp_pagado for doc in self.documentos_relacionados])
		if abs(total_documentos - self.monto_p) > 0.01:
			frappe.throw(
				f"La suma de documentos relacionados ({total_documentos}) no coincide con el monto del pago ({self.monto_p})"
			)

	def before_submit(self):
		self.validate_folio_fiscal_unico()
		self.set_timbrado_info()

	def validate_folio_fiscal_unico(self):
		existing = frappe.db.get_value(
			"Complemento Pago MX", {"folio_fiscal": self.folio_fiscal, "name": ["!=", self.name]}, "name"
		)
		if existing:
			frappe.throw(f"Ya existe un complemento de pago con el folio fiscal {self.folio_fiscal}")

	def set_timbrado_info(self):
		if not self.fecha_timbrado:
			self.fecha_timbrado = datetime.now()
		if not self.estatus_sat:
			self.estatus_sat = "Vigente"

	def on_submit(self):
		self.actualizar_payment_entry()

	def actualizar_payment_entry(self):
		for doc in self.documentos_relacionados:
			if doc.tipo_documento == "Payment Entry" and doc.referencia_documento:
				payment_entry = frappe.get_doc("Payment Entry", doc.referencia_documento)
				payment_entry.add_comment("Comment", f"Complemento de pago timbrado: {self.folio_fiscal}")
				payment_entry.save()

	@frappe.whitelist()
	def generar_xml_complemento(self):
		xml_data = {
			"version": self.version,
			"fecha_pago": self.fecha_pago,
			"forma_pago": self.forma_pago_p,
			"moneda": self.moneda_p,
			"tipo_cambio": self.tipo_cambio_p,
			"monto": self.monto_p,
			"documentos_relacionados": [],
		}

		for doc in self.documentos_relacionados:
			xml_data["documentos_relacionados"].append(
				{
					"id_documento": doc.id_documento,
					"serie": doc.serie,
					"folio": doc.folio,
					"moneda_dr": doc.moneda_dr,
					"equivalencia_dr": doc.equivalencia_dr,
					"num_parcialidad": doc.num_parcialidad,
					"imp_saldo_ant": doc.imp_saldo_ant,
					"imp_pagado": doc.imp_pagado,
					"imp_saldo_insoluto": doc.imp_saldo_insoluto,
					"objeto_imp_dr": doc.objeto_imp_dr,
				}
			)

		return json.dumps(xml_data, indent=2, default=str)

	@frappe.whitelist()
	def consultar_estatus_sat(self):
		frappe.enqueue(
			"facturacion_mexico.complementos_pago.api.consultar_estatus_complemento",
			queue="short",
			timeout=60,
			complemento_id=self.name,
		)
		frappe.msgprint("Consulta de estatus SAT enviada. Se actualizará automáticamente.")
