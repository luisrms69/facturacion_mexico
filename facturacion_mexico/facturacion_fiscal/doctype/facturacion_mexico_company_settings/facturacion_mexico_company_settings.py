import frappe
from frappe.model.document import Document


class FacturacionMexicoCompanySettings(Document):
	def validate(self):
		if self.pdf_nota_ppd:
			from facturacion_mexico.facturacion_fiscal.timbrado_api import render_pdf_note_template

			render_pdf_note_template(
				self.pdf_nota_ppd,
				company="",
				total="",
				due_date="",
			)
