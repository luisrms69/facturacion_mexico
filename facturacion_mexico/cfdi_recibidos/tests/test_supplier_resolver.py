"""
Tests de SupplierResolver — Fase 2.

IntegrationTestCase — aislamiento por rollback de clase (sin commits explícitos).
Crea registros reales en BD de pruebas; el rollback de clase limpia el site.
"""

import frappe
from frappe.tests import IntegrationTestCase

from facturacion_mexico.cfdi_recibidos.services.supplier_resolver import (
	generate_missing_suppliers,
	resolve_supplier,
)

TEST_COMPANY = "_Test Company"
TEST_UUID_BASE = "SUPP0001-0001-0001-0001-"


def _rfc() -> str:
	"""RFC ficticio único (no real) para un Supplier de prueba."""
	return "TST" + frappe.generate_hash(length=10).upper()


def _suffix() -> str:
	"""Sufijo único para el UUID de un CFDI Recibido de prueba."""
	return frappe.generate_hash(length=12).upper()


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
		supplier_group = sg.name

	sup = frappe.new_doc("Supplier")
	sup.supplier_name = f"Proveedor Test {rfc}"
	sup.supplier_group = supplier_group
	sup.tax_id = rfc
	sup.insert(ignore_permissions=True)
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
	frappe.db.set_value("CFDI Recibido", doc.name, "status", status)
	return doc.name


class TestSupplierResolverAuto(IntegrationTestCase):
	def setUp(self):
		self.rfc = _rfc()
		self.supplier = _get_or_create_supplier(self.rfc)
		self.cfdi = _make_cfdi(_suffix(), self.rfc, TEST_COMPANY)

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


class TestSupplierResolverSinMatch(IntegrationTestCase):
	def setUp(self):
		# RFC único sin Supplier asociado → no hay match posible.
		self.cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY)

	def test_status_falta_proveedor(self):
		result = resolve_supplier(self.cfdi)
		self.assertEqual(result["status"], "falta_proveedor")
		self.assertIsNone(result["supplier"])

	def test_doc_queda_falta_proveedor(self):
		resolve_supplier(self.cfdi)
		status = frappe.db.get_value("CFDI Recibido", self.cfdi, "status")
		self.assertEqual(status, "Falta proveedor")


class TestSupplierResolverManual(IntegrationTestCase):
	def setUp(self):
		self.supplier = _get_or_create_supplier(_rfc())
		# CFDI con RFC distinto al del supplier — solo vinculación manual puede resolverlo
		self.cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY)

	def test_vinculacion_manual_aunque_rfc_no_coincida(self):
		result = resolve_supplier(self.cfdi, supplier_override=self.supplier)
		self.assertEqual(result["status"], "ok")
		self.assertEqual(result["supplier"], self.supplier)

	def test_supplier_asignado_manualmente(self):
		resolve_supplier(self.cfdi, supplier_override=self.supplier)
		supplier_en_doc = frappe.db.get_value("CFDI Recibido", self.cfdi, "supplier")
		self.assertEqual(supplier_en_doc, self.supplier)


def _get_or_create_payment_terms(name: str) -> str:
	"""Obtiene o crea un Payment Terms Template mínimo para pruebas."""
	if frappe.db.exists("Payment Terms Template", name):
		return name
	doc = frappe.new_doc("Payment Terms Template")
	doc.template_name = name
	doc.append(
		"terms",
		{
			"payment_term": _get_or_create_payment_term(name),
			"invoice_portion": 100,
			"credit_days_based_on": "Day(s) after invoice date",
			"credit_days": 30,
		},
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _get_or_create_payment_term(name: str) -> str:
	if frappe.db.exists("Payment Term", name):
		return name
	doc = frappe.new_doc("Payment Term")
	doc.payment_term_name = name
	doc.invoice_portion = 100
	doc.credit_days_based_on = "Day(s) after invoice date"
	doc.credit_days = 30
	doc.insert(ignore_permissions=True)
	return doc.name


def _set_cfdi_rec_payment_terms(company: str, payment_terms: str | None):
	"""Escribe default_payment_terms_supplier en Configuracion CFDI Recibidos si existe."""
	config_name = f"CFDI-REC-CFG-{company}"
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		frappe.db.set_value(
			"Configuracion CFDI Recibidos",
			config_name,
			"default_payment_terms_supplier",
			payment_terms,
		)


def _create_minimal_cfdi_rec_cfg(company: str, payment_terms: str | None = None) -> str:
	"""Crea Configuracion CFDI Recibidos mínima para pruebas."""
	config_name = f"CFDI-REC-CFG-{company}"
	if frappe.db.exists("Configuracion CFDI Recibidos", config_name):
		_set_cfdi_rec_payment_terms(company, payment_terms)
		return config_name
	cfg = frappe.new_doc("Configuracion CFDI Recibidos")
	cfg.company = company
	if payment_terms:
		cfg.default_payment_terms_supplier = payment_terms
	cfg.insert(ignore_permissions=True)
	return config_name


class TestGenerateMissingSuppliers(IntegrationTestCase):
	"""Hito B — generate_missing_suppliers: 8 casos del plan."""

	def test_crea_supplier_y_asigna(self):
		"""Caso 1: CFDI Falta proveedor sin Supplier → crea y asigna."""
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		self.assertGreaterEqual(result["creados"], 1)
		status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
		self.assertEqual(status, "Proveedor encontrado")
		supplier = frappe.db.get_value("CFDI Recibido", cfdi, "supplier")
		self.assertIsNotNone(supplier)

	def test_asigna_supplier_existente_sin_duplicar(self):
		"""Caso 2: CFDI Falta proveedor con Supplier ya existente → asigna sin crear duplicado."""
		rfc = _rfc()
		existing = _get_or_create_supplier(rfc)
		cfdi = _make_cfdi(_suffix(), rfc, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		self.assertGreaterEqual(result["ya_existian_y_asignados"], 1)
		# No se creó un segundo Supplier con el mismo RFC (verificación acotada al RFC del test)
		count = frappe.db.count("Supplier", {"tax_id": rfc})
		self.assertEqual(count, 1)
		supplier_en_cfdi = frappe.db.get_value("CFDI Recibido", cfdi, "supplier")
		self.assertEqual(supplier_en_cfdi, existing)

	def test_proveedor_encontrado_va_a_omitidos(self):
		"""Caso 3: CFDI con status Proveedor encontrado → omitido."""
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Proveedor encontrado")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_no_aplicable_va_a_omitidos(self):
		"""Caso 4: CFDI No aplicable → omitido."""
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="No aplicable")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_no_procesar_va_a_omitidos(self):
		"""Caso 5: CFDI no_procesar=1 → omitido."""
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Falta proveedor")
		frappe.db.set_value("CFDI Recibido", cfdi, "no_procesar", 1)
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["omitidos"], 1)
		self.assertEqual(result["creados"], 0)

	def test_dos_cfdi_mismo_rfc_un_supplier(self):
		"""Caso 6: Dos CFDI con mismo RFC → un Supplier creado, ambos asignados."""
		rfc = _rfc()
		cfdi_a = _make_cfdi(_suffix(), rfc, TEST_COMPANY, status="Falta proveedor")
		cfdi_b = _make_cfdi(_suffix(), rfc, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi_a, cfdi_b])
		self.assertEqual(result["creados"], 1)
		self.assertEqual(result["ya_existian_y_asignados"], 1)
		count = frappe.db.count("Supplier", {"tax_id": rfc})
		self.assertEqual(count, 1)
		for cfdi in [cfdi_a, cfdi_b]:
			status = frappe.db.get_value("CFDI Recibido", cfdi, "status")
			self.assertEqual(status, "Proveedor encontrado")

	def test_ejecucion_repetida_no_duplica(self):
		"""Caso 7: Segunda ejecución no crea Supplier duplicado."""
		rfc = _rfc()
		cfdi = _make_cfdi(_suffix(), rfc, TEST_COMPANY, status="Falta proveedor")
		generate_missing_suppliers([cfdi])
		count_after_first = frappe.db.count("Supplier", {"tax_id": rfc})
		# Segunda ejecución — el CFDI ya está en Proveedor encontrado, va a omitidos
		result2 = generate_missing_suppliers([cfdi])
		count_after_second = frappe.db.count("Supplier", {"tax_id": rfc})
		self.assertEqual(count_after_first, count_after_second)
		self.assertEqual(result2["creados"], 0)
		self.assertEqual(result2["omitidos"], 1)

	def test_resumen_contiene_todos_los_campos(self):
		"""Caso 8: El resumen siempre contiene creados/asignados/omitidos/errores."""
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		for key in ["creados", "ya_existian_y_asignados", "omitidos", "errores"]:
			self.assertIn(key, result)
		self.assertIsInstance(result["errores"], list)


class TestGenerateSuppliersPaymentTerms(IntegrationTestCase):
	"""Hito C.1 — payment_terms por defecto al crear Suppliers desde CFDI Recibidos."""

	_pt_name = "_Test PT CFDI Recibidos"
	_cfm_created = False

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Crear Payment Terms Template de prueba
		_get_or_create_payment_terms(cls._pt_name)
		# Guardar valor previo del campo en Configuracion CFDI Recibidos si ya existe
		config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
		cls._cfm_existed = frappe.db.exists("Configuracion CFDI Recibidos", config_name)
		if cls._cfm_existed:
			cls._pt_prev = frappe.db.get_value(
				"Configuracion CFDI Recibidos",
				config_name,
				"default_payment_terms_supplier",
			)
		else:
			cls._pt_prev = None
			cls._cfm_created = True

	@classmethod
	def tearDownClass(cls):
		# Restaurar estado previo de Configuracion CFDI Recibidos
		config_name = f"CFDI-REC-CFG-{TEST_COMPANY}"
		if cls._cfm_created and frappe.db.exists("Configuracion CFDI Recibidos", config_name):
			frappe.delete_doc("Configuracion CFDI Recibidos", config_name, force=True)
		elif cls._cfm_existed:
			_set_cfdi_rec_payment_terms(TEST_COMPANY, cls._pt_prev)
		super().tearDownClass()

	def test_payment_terms_asignado_a_nuevo_supplier(self):
		"""C.1 Caso 1: CFM con payment_terms configurado → nuevo Supplier lo recibe."""
		_create_minimal_cfdi_rec_cfg(TEST_COMPANY, self._pt_name)
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["creados"], 1)
		supplier_name = frappe.db.get_value("CFDI Recibido", cfdi, "supplier")
		pt = frappe.db.get_value("Supplier", supplier_name, "payment_terms")
		self.assertEqual(pt, self._pt_name)

	def test_sin_payment_terms_configurado_no_bloquea(self):
		"""C.1 Caso 2: CFM sin payment_terms → Supplier se crea sin error."""
		_create_minimal_cfdi_rec_cfg(TEST_COMPANY, None)
		cfdi = _make_cfdi(_suffix(), _rfc(), TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		self.assertEqual(result["creados"], 1)
		self.assertEqual(len(result["errores"]), 0)

	def test_supplier_existente_payment_terms_no_sobrescrito(self):
		"""C.1 Caso 3: Supplier existente con payment_terms propios → no se sobreescriben."""
		_create_minimal_cfdi_rec_cfg(TEST_COMPANY, self._pt_name)
		# Crear Supplier con payment_terms diferente (mismo RFC que el CFDI → ya existe)
		rfc = _rfc()
		supplier = _get_or_create_supplier(rfc)
		original_pt = "_Test PT Original"
		_get_or_create_payment_terms(original_pt)
		frappe.db.set_value("Supplier", supplier, "payment_terms", original_pt)

		cfdi = _make_cfdi(_suffix(), rfc, TEST_COMPANY, status="Falta proveedor")
		result = generate_missing_suppliers([cfdi])
		self.assertGreaterEqual(result["ya_existian_y_asignados"], 1)
		# El payment_terms del Supplier existente no debe cambiar
		pt_after = frappe.db.get_value("Supplier", supplier, "payment_terms")
		self.assertEqual(pt_after, original_pt)
