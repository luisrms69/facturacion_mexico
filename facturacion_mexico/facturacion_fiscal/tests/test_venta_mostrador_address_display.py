"""Regresión issue #207 — coherencia dirección display/link en venta mostrador.

Ejerce el código de producción real `populate_billing_data()` (NO reimplementa la
lógica dentro del test). Demuestra que, con `fm_facturar_venta_mostrador = 1`, el
campo informativo `fm_direccion_principal_display` se deriva de la MISMA `Address`
del Customer plantilla que alimenta `fm_direccion_principal_link`, sin un segundo
lookup por el cliente real.

Antes del fix, el helper resolvía el display por `self.customer` (cliente real) y
divergía del link (Customer plantilla). Este test falla con el código previo y pasa
con el corregido.

Sin llamadas al PAC. Se ejecuta en test-facturacion.localhost.
"""

import frappe
from frappe.contacts.doctype.address.address import get_address_display
from frappe.tests import IntegrationTestCase

TEMPLATE_CUSTOMER = "VENTA MOSTRADOR"


def _leaf(doctype: str, fallback: str) -> str:
	"""Devolver un nodo hoja (is_group=0) del árbol, con fallback."""
	return frappe.db.get_value(doctype, {"is_group": 0}, "name") or fallback


def _make_customer(name: str) -> None:
	if frappe.db.exists("Customer", name):
		return
	frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": name,
			"customer_type": "Individual",
			"customer_group": _leaf("Customer Group", "Commercial"),
			"territory": _leaf("Territory", "All Territories"),
		}
	).insert(ignore_permissions=True)


def _make_primary_address(title: str, customer: str, line1: str, city: str, pincode: str):
	"""Crear una Address principal enlazada al customer y marcarla como su primaria."""
	addr = frappe.get_doc(
		{
			"doctype": "Address",
			"address_title": title,
			"address_type": "Billing",
			"address_line1": line1,
			"city": city,
			"state": "Jalisco",
			"country": "Mexico",
			"pincode": pincode,
			"is_primary_address": 1,
			"links": [{"link_doctype": "Customer", "link_name": customer}],
		}
	)
	addr.insert(ignore_permissions=True)
	# Anclar como dirección primaria del customer (ruta que consulta populate_billing_data).
	frappe.db.set_value("Customer", customer, "customer_primary_address", addr.name)
	return addr


class TestVentaMostradorAddressDisplay(IntegrationTestCase):
	def setUp(self):
		self.uid = frappe.generate_hash()[:6]

		# Customer plantilla fijo esperado por producción, con su propia dirección.
		_make_customer(TEMPLATE_CUSTOMER)
		self.template_addr = _make_primary_address(
			f"TPL-{self.uid}", TEMPLATE_CUSTOMER, "Av Plantilla 100", "Guadalajara", "44100"
		)

		# Cliente real, con una dirección DISTINTA a la de la plantilla.
		self.real_customer = f"TEST-207-{self.uid}"
		_make_customer(self.real_customer)
		self.real_addr = _make_primary_address(
			f"REAL-{self.uid}", self.real_customer, "Calle Cliente Real 999", "Zapopan", "45010"
		)

	def test_display_se_deriva_de_la_address_de_la_plantilla(self):
		tpl_display = get_address_display(self.template_addr.as_dict())
		real_display = get_address_display(self.real_addr.as_dict())
		# Sanity: las dos direcciones producen displays distintos (test significativo).
		self.assertNotEqual(tpl_display, real_display)

		# Ejercer el CÓDIGO REAL de producción.
		ffm = frappe.new_doc("Factura Fiscal Mexico")
		ffm.customer = self.real_customer
		ffm.fm_facturar_venta_mostrador = 1
		ffm.populate_billing_data()

		# 1) El link apunta a la Address del Customer plantilla.
		self.assertEqual(ffm.fm_direccion_principal_link, self.template_addr.name)

		# 2) El display se deriva de esa MISMA Address (plantilla).
		self.assertEqual(ffm.fm_direccion_principal_display, tpl_display)

		# 3) No hay segundo lookup capaz de seleccionar la dirección del cliente real.
		self.assertNotEqual(ffm.fm_direccion_principal_display, real_display)
		self.assertNotEqual(ffm.fm_direccion_principal_link, self.real_addr.name)
