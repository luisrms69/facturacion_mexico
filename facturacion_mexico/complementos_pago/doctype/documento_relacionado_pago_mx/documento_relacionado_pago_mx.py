import frappe
from frappe import _
from frappe.model.document import Document


class DocumentoRelacionadoPagoMX(Document):
	def validate(self):
		self.validate_importes()
		self.calculate_saldo_insoluto()
		self.validate_parcialidad()

	def validate_importes(self):
		if self.imp_saldo_ant <= 0:
			frappe.throw(_("El importe saldo anterior debe ser mayor a cero"))

		if self.imp_pagado <= 0:
			frappe.throw(_("El importe pagado debe ser mayor a cero"))

		if self.imp_pagado > self.imp_saldo_ant:
			frappe.throw(_("El importe pagado no puede ser mayor al saldo anterior"))

	def calculate_saldo_insoluto(self):
		if self.imp_saldo_ant and self.imp_pagado:
			self.imp_saldo_insoluto = self.imp_saldo_ant - self.imp_pagado

	def validate_parcialidad(self):
		if self.num_parcialidad <= 0:
			frappe.throw(_("El número de parcialidad debe ser mayor a cero"))

		if self.id_documento and self.num_parcialidad:
			existing_parcialidades = frappe.db.sql(
				"""
				SELECT COUNT(*) as count
				FROM `tabDocumento Relacionado Pago MX` dr
				JOIN `tabComplemento Pago MX` cp ON dr.parent = cp.name
				WHERE dr.id_documento = %s
				AND dr.num_parcialidad = %s
				AND cp.docstatus = 1
				AND dr.name != %s
			""",
				(self.id_documento, self.num_parcialidad, self.name or ""),
				as_dict=True,
			)

			if existing_parcialidades[0].count > 0:
				frappe.throw(
					_(
						f"Ya existe una parcialidad {self.num_parcialidad} para el documento {self.id_documento}"
					)
				)

	def before_save(self):
		if self.moneda_dr == "MXN":
			self.equivalencia_dr = 1.0
		elif not self.equivalencia_dr:
			self.equivalencia_dr = 1.0
