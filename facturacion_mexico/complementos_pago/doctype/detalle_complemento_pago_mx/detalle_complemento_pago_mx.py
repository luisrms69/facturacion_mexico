import frappe
from frappe import _
from frappe.model.document import Document


class DetalleComplementoPagoMX(Document):
	def validate(self):
		self.validate_tipo_factor()
		self.calculate_importe()
		self.validate_base_positiva()

	def validate_tipo_factor(self):
		if self.tipo_factor == "Exento":
			self.tasa_cuota = 0.0
		elif self.tipo_factor in ["Tasa", "Cuota"] and not self.tasa_cuota:
			frappe.throw(_(f"Debe especificar la tasa o cuota para el tipo factor {self.tipo_factor}"))

	def calculate_importe(self):
		if self.base_dr and self.tasa_cuota is not None:
			if self.tipo_factor == "Tasa":
				self.importe_dr = self.base_dr * (self.tasa_cuota or 0)
			elif self.tipo_factor == "Cuota":
				self.importe_dr = self.tasa_cuota or 0
			elif self.tipo_factor == "Exento":
				self.importe_dr = 0.0
		else:
			self.importe_dr = 0.0

	def validate_base_positiva(self):
		if self.base_dr <= 0:
			frappe.throw(_("La base del impuesto debe ser mayor a cero"))

	def before_save(self):
		self.validate_documento_relacionado()

	def validate_documento_relacionado(self):
		if not self.documento_relacionado:
			frappe.throw(_("Debe especificar el ID del documento relacionado"))

		parent_doc = frappe.get_doc("Complemento Pago MX", self.parent)
		documento_exists = False

		for doc_rel in parent_doc.documentos_relacionados:
			if doc_rel.id_documento == self.documento_relacionado:
				documento_exists = True
				break

		if not documento_exists:
			frappe.throw(
				_(
					f"El documento relacionado {self.documento_relacionado} no existe en este complemento de pago"
				)
			)
