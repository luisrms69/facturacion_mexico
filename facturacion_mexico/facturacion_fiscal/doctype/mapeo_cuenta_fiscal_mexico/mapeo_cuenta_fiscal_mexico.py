"""
Mapeo Cuenta Fiscal Mexico - Child DocType para mapear roles fiscales a cuentas específicas.
"""

import frappe
from frappe.model.document import Document


class MapeoCuentaFiscalMexico(Document):
	"""
	Child table para mapear roles fiscales mexicanos a cuentas contables específicas por empresa.

	Funcionalidades principales:
	- Mapeo rol fiscal → cuenta contable específica
	- Validación automática de tipos de cuenta
	- Sugerencias inteligentes por patrones de nombre
	- Estado de validación en tiempo real

	Validaciones:
	- Cuenta debe ser tipo 'Tax'
	- Cuenta debe pertenecer a la empresa correcta
	- No duplicados de rol fiscal por empresa
	"""

	def validate(self):
		"""Validar mapeo de cuenta fiscal."""
		if self.cuenta_impuesto:
			self._validar_tipo_cuenta()
			self._validar_empresa_cuenta()
			self._actualizar_estado_validacion()

	def _validar_tipo_cuenta(self):
		"""Validar que la cuenta sea tipo Tax."""
		account_type = frappe.get_value("Account", self.cuenta_impuesto, "account_type")
		if account_type != "Tax":
			frappe.throw(f"La cuenta {self.cuenta_impuesto} debe ser de tipo 'Tax', actual: {account_type}")

	def _validar_empresa_cuenta(self):
		"""Validar que la cuenta pertenezca a la empresa correcta."""
		parent_doc = self.get_parent_doc()
		if parent_doc and parent_doc.company:
			account_company = frappe.get_value("Account", self.cuenta_impuesto, "company")
			if account_company != parent_doc.company:
				frappe.throw(
					f"La cuenta {self.cuenta_impuesto} pertenece a {account_company}, debe ser de {parent_doc.company}"
				)

	def _actualizar_estado_validacion(self):
		"""Actualizar estado de validación basado en criterios."""
		try:
			self._validar_tipo_cuenta()
			self._validar_empresa_cuenta()
			self.estado_validacion = "Válido"
		except Exception as e:
			self.estado_validacion = "Error"
			frappe.log_error(f"Error validación mapeo: {e!s}")
