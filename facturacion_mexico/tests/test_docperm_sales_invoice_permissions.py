"""
Validación estática del fixture de permisos (docperm.json).

Lee el JSON del repositorio (sin BD, sin mocks) y verifica invariantes de Frappe y la decisión
autoritativa de permisos de cancelación de Sales Invoice:
  - Ninguna fila DocPerm puede tener cancel=1 con submit=0 (estado inválido en Frappe).
  - Los roles Manager/System Manager sobre Sales Invoice tienen submit=1 y cancel=1 (el flujo de
    cancelación nativo del app depende del permiso `cancel`, que a su vez exige `submit`).
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase


def _load_docperm():
	path = frappe.get_app_path("facturacion_mexico", "fixtures", "docperm.json")
	with open(path, encoding="utf-8") as fh:
		return json.load(fh)


class TestDocPermSalesInvoicePermissions(FrappeTestCase):
	def test_ninguna_fila_cancel_sin_submit(self):
		"""Frappe: cancel=1 exige submit=1. Ninguna fila del fixture puede violar ese invariante."""
		invalidas = [
			f"{p.get('parent')} / {p.get('role')}"
			for p in _load_docperm()
			if int(p.get("cancel") or 0) == 1 and int(p.get("submit") or 0) == 0
		]
		self.assertEqual(invalidas, [], f"Filas DocPerm con cancel=1 y submit=0 (inválidas): {invalidas}")

	def test_roles_manager_sales_invoice_submit_y_cancel(self):
		"""Manager y System Manager sobre Sales Invoice deben tener submit=1 y cancel=1."""
		roles = {"Facturacion Mexico Manager", "Facturacion Mexico System Manager"}
		filas = {
			p.get("role"): p
			for p in _load_docperm()
			if p.get("parent") == "Sales Invoice" and p.get("role") in roles
		}
		self.assertEqual(set(filas), roles, "Faltan filas DocPerm de Sales Invoice para los roles Manager")
		for role, p in filas.items():
			self.assertEqual(int(p.get("submit") or 0), 1, f"{role} sobre Sales Invoice: submit debe ser 1")
			self.assertEqual(int(p.get("cancel") or 0), 1, f"{role} sobre Sales Invoice: cancel debe ser 1")
