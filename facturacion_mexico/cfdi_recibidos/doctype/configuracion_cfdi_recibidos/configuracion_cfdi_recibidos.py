import frappe
from frappe import _
from frappe.model.document import Document


class ConfiguracionCFDIRecibidos(Document):
	def validate(self):
		self._validate_accounts_belong_to_company()

	def _validate_accounts_belong_to_company(self):
		for row in self.reglas_impuesto:
			if not row.activo or not row.cuenta_impuesto:
				continue
			account_company = frappe.db.get_value("Account", row.cuenta_impuesto, "company")
			if account_company != self.company:
				frappe.throw(
					_("Fila {0}: la cuenta '{1}' pertenece a '{2}', no a '{3}'").format(
						row.idx, row.cuenta_impuesto, account_company, self.company
					),
					frappe.ValidationError,
				)
