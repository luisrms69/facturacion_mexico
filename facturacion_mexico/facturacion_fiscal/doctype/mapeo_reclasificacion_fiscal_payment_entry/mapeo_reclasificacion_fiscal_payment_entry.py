"""
Mapeo Reclasificacion Fiscal Payment Entry

Define relaciones cuenta_origen → cuenta_destino para reclasificar
impuestos cuando se registra un cobro o pago via Payment Entry.

Cobro: IVA pendiente por cobrar → IVA efectivamente cobrado
Pago:  IVA pendiente por acreditar → IVA efectivamente pagado
"""

import frappe
from frappe import _
from frappe.model.document import Document


class MapeoReclasificacionFiscalPaymentEntry(Document):
	def validate(self):
		self._validar_cuentas_distintas()
		self._validar_cuenta("cuenta_origen")
		self._validar_cuenta("cuenta_destino")
		self._validar_sin_duplicado_activo()

	def _validar_cuentas_distintas(self):
		if self.cuenta_origen and self.cuenta_destino and self.cuenta_origen == self.cuenta_destino:
			frappe.throw(_("Cuenta Origen y Cuenta Destino no pueden ser la misma cuenta."))

	def _validar_cuenta(self, fieldname: str):
		cuenta = self.get(fieldname)
		if not cuenta:
			return

		label = self.meta.get_field(fieldname).label

		data = frappe.db.get_value(
			"Account",
			cuenta,
			["account_type", "company", "is_group", "disabled"],
			as_dict=True,
		)

		if not data:
			frappe.throw(_("{0}: la cuenta {1} no existe.").format(label, cuenta))

		if data.account_type != "Tax":
			frappe.throw(
				_("{0}: la cuenta {1} debe ser tipo Tax. Tipo actual: {2}.").format(
					label, cuenta, data.account_type or "Sin tipo"
				)
			)

		if data.company != self.company:
			frappe.throw(
				_("{0}: la cuenta {1} pertenece a {2}, no a {3}.").format(
					label, cuenta, data.company, self.company
				)
			)

		if data.is_group:
			frappe.throw(
				_("{0}: {1} es una cuenta grupo. Seleccione una cuenta específica.").format(label, cuenta)
			)

		if data.disabled:
			frappe.throw(_("{0}: la cuenta {1} está deshabilitada.").format(label, cuenta))

	def _validar_sin_duplicado_activo(self):
		if not self.activo:
			return

		filtros = {
			"company": self.company,
			"tipo_operacion": self.tipo_operacion,
			"cuenta_origen": self.cuenta_origen,
			"activo": 1,
		}
		if self.name:
			filtros["name"] = ["!=", self.name]

		existente = frappe.db.get_value("Mapeo Reclasificacion Fiscal Payment Entry", filtros, "name")
		if existente:
			frappe.throw(
				_("Ya existe un mapeo activo para {0} / {1} / {2}: {3}").format(
					self.company,
					self.tipo_operacion,
					self.cuenta_origen,
					existente,
				)
			)


def get_mapeo_reclasificacion(company: str, tipo_operacion: str, cuenta_origen: str) -> str | None:
	"""
	Obtener cuenta destino para reclasificación de impuesto.

	Args:
		company: Empresa
		tipo_operacion: "Cobro" o "Pago"
		cuenta_origen: Cuenta de impuesto al timbrar

	Returns:
		Nombre de la cuenta destino, o None si no hay mapeo activo
	"""
	return frappe.db.get_value(
		"Mapeo Reclasificacion Fiscal Payment Entry",
		{
			"company": company,
			"tipo_operacion": tipo_operacion,
			"cuenta_origen": cuenta_origen,
			"activo": 1,
		},
		"cuenta_destino",
	)
