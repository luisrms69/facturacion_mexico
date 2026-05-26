"""
Tests de SupplierResolver — Fase 2.

unittest.TestCase con contexto Frappe activo.
Crea y limpia registros reales en BD de pruebas.
"""

import unittest

import frappe

from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
	generate_missing_suppliers,
	resolve_supplier,
)

TEST_RFC = "PROV9001011AA"
TEST_COMPANY = "_Test Company"
TEST_UUID_BASE = "SUPP0001-0001-0001-0001-"


def _get_or_create_supplier(rfc: str) -> str:
	"""Obtiene o crea un Supplier de prueba con el RFC dado."""
	existing = frappe.db.get_value("Supplier", {"tax_id": rfc}, "name")
	if existing:
		return existing

	supplier_group = frappe.db.get_value("Supplier Group", {"is_group": 0}, "name")
	if not supplier_group:
		sg = frappe.new_doc("Supplier Group")
		sg.supplier_group_name = "Test Suppliers"
		sg.insert(ignore_permissions=True)
		frappe.db.commit()
		supplier_group = sg.name

	sup = frappe.new_doc("Supplier")
	sup.supplier_name = f"Proveedor Test {rfc}"
	sup.supplier_group = supplier_group
	sup.tax_id = rfc
	sup.insert(ignore_permissions=True)
	frappe.db.commit()
	return sup.name


def _make_cfdi(uuid_suffix: str, supplier_rfc: str, company: str, status: str = "Parseado") -> str:
	"""Crea un CFDI Recibido mínimo para pruebas."""
	doc = frappe.new_doc("CFDI Recibido")
	doc.company = company
	doc.uuid = f"{TEST_UUID_BASE}{uuid_suffix}"
	doc.supplier_rfc = supplier_rfc
	doc.supplier_name = f"Proveedor Test {supplier_rfc}"
	doc.receiver_rfc = frappe.db.get_value("Company", company, "tax_id") or "RFC000000000"
	doc.status = status
	doc.cfdi_type = "I"
	doc.xml_hash = frappe.generate_hash()[:64]
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


def _cleanup_supplier(rfc: str):
	"""Elimina el Supplier con tax_id == rfc si existe."""
	name = frappe.db.get_value("Supplier", {"tax_id": rfc}, "name")
	if name:
		frappe.delete_doc("Supplier", name, force=True)
		frappe.db.commit()


def _cleanup(uuid_suffix: str):
	name = frappe.db.get_value("CFDI Recibido", {"uuid": f"{TEST_UUID_BASE}{uuid_suffix}"}, "name")
	if name:
		frappe.delete_doc("CFDI Recibido", name, force=True)
		frappe.db.commit()


class TestSupplierResolverAuto(unittest.TestCase):
	def setUp(self):
		self.supplier = _get_or_create_supplier(TEST_RFC)
		self.cfdi = _make_cfdi("000A", TEST_RFC, TEST_COMPANY)

	def tearDown(self):
		_cleanup("000A")

	def test_resuelve_por_rfc(self):
		result = resolve_supplier(self.cfdi)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["supplier"], self.supplier)

	def test_asigna_supplier_al_doc(self):
		resolve_supplier(self.cfdi)
		supplier_en_doc = frappe.db.get_value("CFDI Recibido", self.cfdi, "supplier")
		self.assertEqual(supplier_en_doc, self.supplier)

	def test_status_avanza(self):
		resolve_supplier(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertNotEqual(status, "Falta proveedor")


class TestSupplierResolverSinMatch(unittest.TestCase):
	def setUp(self):
		self.cfdi = _make_cfdi("000B", "RFC_SIN_MATCH_999", TEST_COMPANY)

	def tearDown(self):
		_cleanup("000B")

	def test_status_falta_proveedor(self):
		result = resolve_supplier(self.cfdi)
		self.assertEqual(result["status"], "falta_proveedor")
		self.assertIsNone(result["supplier"])

	def test_doc_queda_falta_proveedor(self):
		resolve_supplier(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertEqual(status, "Falta proveedor")


class TestSupplierResolverManual(unittest.TestCase):
	def setUp(self):
		self.supplier = _get_or_create_supplier(TEST_RFC)
		# CFDI con RFC distinto al del supplier — solo vinculación manual puede resolverlo
		self.cfdi = _make_cfdi("000C", "RFC_DIFERENTE_ABC", TEST_COMPANY)

	def tearDown(self):
		_cleanup("000C")

	def test_vinculacion_manual_aunque_rfc_no_coincida(self):
		result = resolve_supplier(self.cfdi, supplier_override=self.supplier)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["supplier"], self.supplier)

	def test_supplier_asignado_manualmente(self):
		resolve_supplier(self.cfdi, supplier_override=self.supplier)
		supplier_en_doc = frappe.db.get_value("CFDI Recibido", self.cfdi, "supplier")
		self.assertEqual(supplier_en_doc, self.supplier)


# --- RFC únicos para Hito B (sin colisión con las clases anteriores) ---
RFC_B1 = "HITOB001AAAA"  # CFDI sin Supplier → crear
RFC_B2 = "HITOB002BBBB"  # CFDI con Supplier existente → asignar
RFC_B3 = "HITOB003CCCC"  # Dos CFDI mismo RFC
RFC_B4 = "HITOB004DDDD"  # Ejecución repetida


class TestGenerateMissingSuppliers(unittest.TestCase):
	"""Hito B — generate_missing_suppliers: 8 casos del plan."""

	def setUp(self):
		# Limpiar cualquier residuo de pruebas anteriores
		for rfc in [RFC_B1, RFC_B2, RFC_B3, RFC_B4]:
			_cleanup_supplier(rfc)
		for suffix in ["B01", "B02", "B03a", "B03b", "B04", "B05", "B06", "B07"]:
			_cleanup(suffix)

	def tearDown(self):
		for rfc in [RFC_B1, RFC_B2, RFC_B3, RFC_B4]:
			_cleanup_supplier(rfc)
		for suffix in ["B01", "B02", "B03a", "B03b", "B04", "B05", "B06", "B07"]:
			_cleanup(suffix)

	def test_crea_supplier_y_asigna(self):
		"""Caso 1: CFDI Falta proveedor sin Supplier → crea y asigna."""
		cfdi = _make_cfdi("B01", RFC_B1, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers()
		self.assertGreaterEqual(result["creados"], 1)
		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Proveedor encontrado")
		supplier = frappe.db.get_value("CFDI Recibido", cfdi, "supplier")
		self.assertIsNotNone(supplier)

	def test_asigna_supplier_existente_sin_duplicar(self):
		"""Caso 2: CFDI Falta proveedor con Supplier ya existente → asigna sin crear duplicado."""
		existing = _get_or_create_supplier(RFC_B2)
		cfdi = _make_cfdi("B02", RFC_B2, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers()
		self.assertGreaterEqual(result["ya_existian_y_asignados"], 1)
		self.assertEqual(result["creados"], 0)
		# Verificar que no se creó un segundo Supplier con el mismo RFC
		count = frappe.db.count("Supplier", {"tax_id": RFC_B2})
		self.assertEqual(count, 1)
		supplier_en_cfdi = frappe.db.get_value("CFDI Recibido", cfdi, "supplier")
		self.assertEqual(supplier_en_cfdi, existing)

	def test_proveedor_encontrado_va_a_omitidos(self):
		"""Caso 3: CFDI con status Proveedor encontrado → omitido."""
		cfdi = _make_cfdi("B03a", RFC_B1, TEST_COMPANY, status="Proveedor encontrado")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_no_aplicable_va_a_omitidos(self):
		"""Caso 4: CFDI No aplicable → omitido."""
		cfdi = _make_cfdi("B03b", RFC_B1, TEST_COMPANY, status="No aplicable")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_no_procesar_va_a_omitidos(self):
		"""Caso 5: CFDI no_procesar=1 → omitido."""
		cfdi = _make_cfdi("B04", RFC_B1, TEST_COMPANY, status="Falta proveedor")
		frappe.db.set_value("CFDI Recibido", cfdi, "no_procesar", 1)
		frappe.db.commit()
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_dos_cfdi_mismo_rfc_un_supplier(self):
		"""Caso 6: Dos CFDI con mismo RFC → un Supplier creado, ambos asignados."""
		cfdi_a = _make_cfdi("B05", RFC_B3, TEST_COMPANY, status="Falta proveedor")
		cfdi_b = _make_cfdi("B06", RFC_B3, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi_a, cfdi_b])
		self.assertEqual(result["creados"], 1)
		self.assertEqual(result["ya_existian_y_asignados"], 1)
		count = frappe.db.count("Supplier", {"tax_id": RFC_B3})
		self.assertEqual(count, 1)
		for cfdi in [cfdi_a, cfdi_b]:
			status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
			self.assertEqual(status, "Proveedor encontrado")

	def test_ejecucion_repetida_no_duplica(self):
		"""Caso 7: Segunda ejecución no crea Supplier duplicado."""
		cfdi = _make_cfdi("B07", RFC_B4, TEST_COMPANY, status="Falta proveedor")
		generate_missing_suppliers([cfdi])
		count_after_first = frappe.db.count("Supplier", {"tax_id": RFC_B4})
		# Segunda ejecución — el CFDI ya está en Proveedor encontrado, va a omitidos
		result2 = generate_missing_suppliers([cfdi])
		count_after_second = frappe.db.count("Supplier", {"tax_id": RFC_B4})
		self.assertEqual(count_after_first, count_after_second)
		self.assertEqual(result2["creados"], 0)
		self.assertEqual(result2["omitidos"], 1)

	def test_resumen_contiene_todos_los_campos(self):
		"""Caso 8: El resumen siempre contiene creados/asignados/omitidos/errores."""
		result = generate_missing_suppliers()
		for key in ["creados", "ya_existian_y_asignados", "omitidos", "errores"]:
			self.assertIn(key, result)
		self.assertIsInstance(result["errores"], list)
