# Copyright (c) 2025, Buzola and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class IEPSCuotaSAT(Document):
	"""
	Tabla maestra de cuotas IEPS vigentes por producto SAT.

	Funcionalidades:
	- Almacena cuotas IEPS actualizables (combustibles semanalmente, bebidas por cambio)
	- Maneja vigencias con rangos de fechas
	- Evita solapamientos por producto/UOM/empresa
	- Link a cuenta IEPS para evitar mezclar combustibles/bebidas

	Campos principales:
		clave_prod_serv (Data): Clave SAT del producto
		uom (Link): Unidad de medida
		cuota (Currency): Cuota en pesos por unidad (6 decimales)
		cuenta_ieps (Link): Cuenta de impuesto IEPS
		vigencia_desde/hasta (Date): Rango de vigencia

	Validaciones:
		- No solapamientos de vigencias para mismo producto/UOM/empresa
		- Vigencia_desde <= vigencia_hasta (si está definida)
		- Cuenta IEPS debe ser tipo Tax

	Ejemplo:
		# Crear cuota gasolina
		cuota = frappe.new_doc("IEPS Cuota SAT")
		cuota.clave_prod_serv = "15101514"
		cuota.uom = "Nos"
		cuota.cuota = 5.49
		cuota.vigencia_desde = "2025-01-01"
		cuota.save()
	"""

	def validate(self):
		"""Validaciones antes de guardar."""
		self._validar_rango_vigencia()
		self._validar_cuenta_ieps()
		self._validar_no_solapamiento()

	def _validar_rango_vigencia(self):
		"""Validar que vigencia_desde <= vigencia_hasta."""
		if self.vigencia_hasta:
			desde = getdate(self.vigencia_desde)
			hasta = getdate(self.vigencia_hasta)

			if hasta < desde:
				frappe.throw(
					f"Vigencia Hasta ({hasta}) no puede ser anterior a Vigencia Desde ({desde})",
					title="Rango Vigencia Inválido",
				)

	def _validar_cuenta_ieps(self):
		"""Validar que cuenta_ieps sea tipo Tax si está configurada."""
		if not self.cuenta_ieps:
			return

		account_type = frappe.db.get_value("Account", self.cuenta_ieps, "account_type")
		if account_type != "Tax":
			frappe.throw(
				f"La cuenta {self.cuenta_ieps} debe ser de tipo 'Tax', actual: {account_type}",
				title="Tipo Cuenta Inválido",
			)

		# Validar que pertenezca a la empresa correcta
		account_company = frappe.db.get_value("Account", self.cuenta_ieps, "company")
		if account_company != self.company:
			frappe.throw(
				f"La cuenta {self.cuenta_ieps} pertenece a {account_company}, debe ser de {self.company}",
				title="Empresa Cuenta No Coincide",
			)

	def _validar_no_solapamiento(self):
		"""
		Validar que no exista otra cuota vigente para el mismo producto/UOM/empresa.

		Evita solapamientos de vigencias que causarían ambigüedad al buscar cuota.
		"""
		# Construir fecha fin efectiva (NULL = infinito)
		vigencia_hasta_efectiva = self.vigencia_hasta or "2099-12-31"

		# Buscar solapamientos
		overlaps = frappe.db.sql(
			"""
			SELECT name, vigencia_desde, vigencia_hasta
			FROM `tabIEPS Cuota SAT`
			WHERE name != %(self_name)s
			  AND company = %(company)s
			  AND clave_prod_serv = %(clave)s
			  AND uom = %(uom)s
			  AND vigencia_desde <= %(hasta)s
			  AND IFNULL(vigencia_hasta, '2099-12-31') >= %(desde)s
			  AND docstatus < 2
			""",
			{
				"self_name": self.name or "",
				"company": self.company,
				"clave": self.clave_prod_serv,
				"uom": self.uom,
				"desde": self.vigencia_desde,
				"hasta": vigencia_hasta_efectiva,
			},
			as_dict=True,
		)

		if overlaps:
			overlap = overlaps[0]
			frappe.throw(
				f"Ya existe una cuota vigente para este producto/UOM: {overlap.name}<br>"
				f"Vigencia existente: {overlap.vigencia_desde} - {overlap.vigencia_hasta or 'indefinido'}<br>"
				f"Vigencia nueva: {self.vigencia_desde} - {self.vigencia_hasta or 'indefinido'}",
				title="Solapamiento de Vigencias",
			)
