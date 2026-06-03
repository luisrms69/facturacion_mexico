import frappe
from frappe import _
from frappe.model.document import Document

from facturacion_mexico.cfdi_recibidos.services.item_validator import validate_expense_item
from facturacion_mexico.cfdi_recibidos.services.status_manager import compute_stage

_TERMINAL_STAGES = frozenset(
	["XML inválido", "No aplicable", "No procesar", "Convertido a PI", "Error conversión"]
)


class CFDIRecibido(Document):
	def validate(self):
		if not self.is_new() and not frappe.flags.get("in_cfdi_builder"):
			old_status = frappe.db.get_value("CFDI Recibido", self.name, "status")
			if old_status == "Convertido a PI":
				frappe.throw(
					_("CFDI Recibido en estado 'Convertido a PI' no puede modificarse."),
					frappe.ValidationError,
				)
		for concepto in self.conceptos or []:
			if not concepto.item_code:
				continue
			ok, reason = validate_expense_item(concepto.item_code)
			if not ok:
				frappe.throw(
					_("Concepto '{0}': {1}").format(concepto.item_code, reason),
					frappe.ValidationError,
				)
			concepto.item_group = frappe.db.get_value("Item", concepto.item_code, "item_group")
		self._validate_company_scoped_links()
		if self.status not in _TERMINAL_STAGES:
			self.status = compute_stage(self)

	def _validate_company_scoped_links(self):
		"""Valida que department, cost_center y project pertenezcan a la misma empresa."""
		if not self.company:
			return
		if self.department:
			dept_company = frappe.db.get_value("Department", self.department, "company")
			if dept_company and dept_company != self.company:
				frappe.throw(
					_("El Departamento '{0}' no pertenece a la empresa '{1}'.").format(
						self.department, self.company
					),
					frappe.ValidationError,
				)
		if self.cost_center:
			cc_company = frappe.db.get_value("Cost Center", self.cost_center, "company")
			if cc_company and cc_company != self.company:
				frappe.throw(
					_("El Centro de Costo '{0}' no pertenece a la empresa '{1}'.").format(
						self.cost_center, self.company
					),
					frappe.ValidationError,
				)
		if self.project:
			proj_company = frappe.db.get_value("Project", self.project, "company")
			if proj_company and proj_company != self.company:
				frappe.throw(
					_("El Proyecto '{0}' no pertenece a la empresa '{1}'.").format(
						self.project, self.company
					),
					frappe.ValidationError,
				)
