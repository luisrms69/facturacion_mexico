import frappe
from frappe import _
from frappe.model.document import Document

_FAMILIAS_SAT_VALIDAS = frozenset(
	[
		"601 Gastos generales",
		"602 Gastos de venta",
		"603 Gastos de administración",
		"604 Gastos de fabricación",
		# Soporte para valores legacy con solo el código numérico
		"601",
		"602",
		"603",
		"604",
	]
)


class ConfiguracionCFDIRecibidos(Document):
	def validate(self):
		self._auto_activate_rules_with_account()
		self._validate_accounts_belong_to_company()
		self._auto_populate_department_mapping()
		self._validate_mapeo_departamentos()

	def _auto_activate_rules_with_account(self):
		for row in self.reglas_impuesto:
			if row.cuenta_impuesto and not row.activo:
				row.activo = 1

	def _validate_accounts_belong_to_company(self):
		for row in self.reglas_impuesto:
			if not row.activo:
				continue
			if not row.cuenta_impuesto:
				frappe.throw(
					_("Fila {0} ({1}): la regla está activa pero no tiene cuenta contable asignada.").format(
						row.idx, row.descripcion or row.impuesto_sat
					),
					frappe.ValidationError,
				)
			account_company = frappe.db.get_value("Account", row.cuenta_impuesto, "company")
			if account_company != self.company:
				frappe.throw(
					_("Fila {0}: la cuenta '{1}' pertenece a '{2}', no a '{3}'").format(
						row.idx, row.cuenta_impuesto, account_company, self.company
					),
					frappe.ValidationError,
				)

	def _auto_populate_department_mapping(self):
		"""Agrega a la tabla todos los departamentos activos de la empresa que aún no estén mapeados.

		No modifica filas existentes — preserva cualquier familia_sat ya configurada.
		"""
		existing = {row.department for row in self.mapeo_departamentos}

		departments = frappe.get_all(
			"Department",
			filters={"disabled": 0, "company": self.company},
			pluck="name",
			order_by="name",
		)

		for dept_name in departments:
			if dept_name not in existing:
				self.append("mapeo_departamentos", {"department": dept_name})

	def _validate_mapeo_departamentos(self):
		seen_depts = set()
		for row in self.mapeo_departamentos:
			if row.department in seen_depts:
				frappe.throw(
					_("El departamento '{0}' está duplicado en el mapeo (fila {1}).").format(
						row.department, row.idx
					),
					frappe.ValidationError,
				)
			seen_depts.add(row.department)

			# familia_sat es opcional hasta que el departamento sea usado para clasificación
			if row.familia_sat and row.familia_sat not in _FAMILIAS_SAT_VALIDAS:
				frappe.throw(
					_("Fila {0}: familia SAT '{1}' no es válida. Use: 601, 602, 603 o 604.").format(
						row.idx, row.familia_sat
					),
					frappe.ValidationError,
				)

			if row.department:
				dept_company = frappe.db.get_value("Department", row.department, "company")
				if dept_company and dept_company != self.company:
					frappe.throw(
						_(
							"Fila {0}: el departamento '{1}' pertenece a la empresa '{2}', "
							"no a '{3}'. Use departamentos de esta empresa o sin empresa asignada."
						).format(row.idx, row.department, dept_company, self.company),
						frappe.ValidationError,
					)
