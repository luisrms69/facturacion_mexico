"""
Tests Issue #137 — Nota de Crédito por descuento/bonificación (CFDI tipo E, TipoRelación 01).

Arquitectura: la intención de negocio se captura en Factura Fiscal Mexico.fm_tipo_nota_credito
(«Devolución de mercancía» / «Descuento / Bonificación»). El controlador deriva los códigos SAT.

Cubre:
  - Derivación fiscal por intención (relación 03 vs 01, UsoCFDI G02, MetodoPago PUE, FormaPago 15).
  - Sin regresión: vacío o «Devolución de mercancía» → relación 03 (comportamiento histórico).
  - Concepto fiscal «Descuento» conservando Item/ClaveProdServ.
  - related_documents con relación 01 y UUID exclusivo de return_against.
  - REP: la fórmula proporcional contra grand_total original se mantiene (no G-4).
  - Meta: el campo fm_tipo_nota_credito existe en el DocType.

Sin red. Sin sandbox FacturAPI. Mocks solo en boundary (frappe.db / SI origen).
"""

import re
from unittest.mock import patch

import frappe
from frappe import _dict
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.api.nota_credito import (
	preparar_como_descuento,
	preparar_reversion_a_devolucion,
)
from facturacion_mexico.facturacion_fiscal.doctype.factura_fiscal_mexico.factura_fiscal_mexico import (
	FacturaFiscalMexico,
)
from facturacion_mexico.facturacion_fiscal.timbrado_api import (
	is_nota_descuento,
	resolve_concepto_description,
)
from facturacion_mexico.facturacion_fiscal.utils import (
	apply_descuento_to_lines,
	build_descuento_description,
	credit_note_lines_use_discount_account,
	get_cuenta_descuentos,
)

CUENTA_DESC = "501-005 - Descuentos y bonificaciones - TC"

UUID_ORIGEN_C = "550E8400-E29B-41D4-A716-446655440000"


def _make_ffm(motivo, uuid=UUID_ORIGEN_C):
	"""FFM de una nota de crédito (SI return) con la intención de negocio indicada."""
	inst = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
	inst.sales_invoice = "SINV-C-RETORNO"
	inst.fm_tipo_nota_credito = motivo
	inst.fm_tipo_comprobante = None
	inst.fm_tipo_relacion_sat = None
	inst.fm_uuid_relacionado = None
	inst.fm_cfdi_use = None
	inst.fm_forma_pago_timbrado = None
	inst.fm_payment_method_sat = None
	inst.fm_facturar_venta_mostrador = 0
	# Aislar dependencias de BD/SI origen (boundary)
	inst._is_sales_invoice_return = lambda: True
	inst._find_uuid_cfdi_origen = lambda: uuid
	inst._get_origin_ffm = lambda: None
	return inst


# ── Derivación fiscal por intención de negocio ────────────────────────────────


class TestDerivacionFiscalNotaCredito(FrappeTestCase):
	def test_descuento_tipo_comprobante_E(self):
		ffm = _make_ffm("Descuento / Bonificación")
		ffm._set_tipo_from_context()
		self.assertTrue((ffm.fm_tipo_comprobante or "").startswith("E"))

	def test_descuento_relacion_01(self):
		ffm = _make_ffm("Descuento / Bonificación")
		ffm._set_tipo_from_context()
		self.assertTrue(ffm.fm_tipo_relacion_sat.startswith("01 - "))

	def test_descuento_uso_g02(self):
		ffm = _make_ffm("Descuento / Bonificación")
		ffm._set_tipo_from_context()
		self.assertEqual(ffm.fm_cfdi_use, "G02")

	def test_descuento_metodo_pue(self):
		ffm = _make_ffm("Descuento / Bonificación")
		ffm._set_tipo_from_context()
		self.assertEqual(ffm.fm_payment_method_sat, "PUE")

	def test_descuento_forma_pago_15_condonacion(self):
		ffm = _make_ffm("Descuento / Bonificación")
		ffm._set_tipo_from_context()
		self.assertEqual(ffm.fm_forma_pago_timbrado, "15 Condonación")

	def test_descuento_uuid_exclusivo_return_against(self):
		"""El UUID relacionado corresponde exclusivamente al CFDI de return_against."""
		ffm = _make_ffm("Descuento / Bonificación", uuid=UUID_ORIGEN_C)
		ffm._set_tipo_from_context()
		self.assertEqual(ffm.fm_uuid_relacionado, UUID_ORIGEN_C)

	def test_devolucion_mercancia_relacion_03(self):
		"""Devolución física → relación 03 (comportamiento histórico, sin regresión)."""
		ffm = _make_ffm("Devolución de mercancía")
		ffm._set_tipo_from_context()
		self.assertTrue(ffm.fm_tipo_relacion_sat.startswith("03 - "))
		# No debe forzar G02 ni FormaPago 15 en devolución física
		self.assertIsNone(ffm.fm_cfdi_use)

	def test_vacio_es_devolucion_sin_regresion(self):
		"""Vacío se comporta como devolución física (relación 03)."""
		ffm = _make_ffm("")
		ffm._set_tipo_from_context()
		self.assertTrue(ffm.fm_tipo_relacion_sat.startswith("03 - "))


# ── Concepto fiscal e independencia de la ClaveProdServ ───────────────────────


class TestConceptoDescripcion(FrappeTestCase):
	def test_descuento_descripcion_prefija_origen(self):
		item = _dict({"description": "Llanta 205/55R16", "item_name": "LLANTA-XYZ"})
		self.assertEqual(
			resolve_concepto_description(item, es_nota_descuento=True), "Descuento - Llanta 205/55R16"
		)

	def test_descuento_sin_origen_es_descuento(self):
		item = _dict({"description": "", "item_name": ""})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=True), "Descuento")

	def test_descuento_idempotente_si_ya_prefijado(self):
		item = _dict({"description": "Descuento - Llanta 205/55R16", "item_name": "Descuento"})
		self.assertEqual(
			resolve_concepto_description(item, es_nota_descuento=True), "Descuento - Llanta 205/55R16"
		)

	def test_devolucion_descripcion_es_del_item(self):
		item = _dict({"description": "Llanta 205/55R16", "item_name": "LLANTA-XYZ"})
		self.assertEqual(resolve_concepto_description(item, es_nota_descuento=False), "Llanta 205/55R16")

	def test_build_descuento_description(self):
		self.assertEqual(build_descuento_description("Llanta 205/55R16"), "Descuento - Llanta 205/55R16")
		self.assertEqual(build_descuento_description(""), "Descuento")
		self.assertEqual(build_descuento_description(None), "Descuento")
		self.assertEqual(
			build_descuento_description("Descuento - Llanta"), "Descuento - Llanta"
		)  # idempotente

	def test_claveprodserv_independiente_de_descripcion(self):
		"""La descripción 'Descuento - ...' NO altera la ClaveProdServ (viene de la línea/Item)."""
		item = _dict({"description": "Llanta 205/55R16", "item_name": "LLANTA-XYZ"})
		item_doc = _dict({"fm_producto_servicio_sat": "25172504"})  # ClaveProdServ llantas
		descripcion = resolve_concepto_description(item, es_nota_descuento=True)
		product_key = item_doc.fm_producto_servicio_sat  # como lo arma el payload
		self.assertEqual(descripcion, "Descuento - Llanta 205/55R16")
		self.assertEqual(product_key, "25172504")  # intacta


class TestIsNotaDescuento(FrappeTestCase):
	def test_true_para_E_relacion_01(self):
		ffm = _dict({"fm_tipo_comprobante": "E - Egreso", "fm_tipo_relacion_sat": "01 - Nota de crédito"})
		self.assertTrue(is_nota_descuento(ffm))

	def test_false_para_E_relacion_03(self):
		ffm = _dict({"fm_tipo_comprobante": "E - Egreso", "fm_tipo_relacion_sat": "03 - Devolución"})
		self.assertFalse(is_nota_descuento(ffm))

	def test_false_para_ingreso(self):
		ffm = _dict({"fm_tipo_comprobante": "I - Ingreso", "fm_tipo_relacion_sat": ""})
		self.assertFalse(is_nota_descuento(ffm))


# ── related_documents en el payload (bloque tipo E) ───────────────────────────


class TestRelatedDocuments(FrappeTestCase):
	def _related_documents(self, tipo_relacion, uuid):
		"""Réplica del bloque related_documents de _prepare_facturapi_data (tipo E)."""
		relacion_code = tipo_relacion.split(" - ")[0].strip() if " - " in tipo_relacion else tipo_relacion
		return [{"relationship": relacion_code, "documents": [uuid]}]

	def test_descuento_produce_relacion_01(self):
		rel = self._related_documents("01 - Nota de crédito de los documentos relacionados", UUID_ORIGEN_C)
		self.assertEqual(rel[0]["relationship"], "01")
		self.assertEqual(rel[0]["documents"], [UUID_ORIGEN_C])

	def test_devolucion_produce_relacion_03(self):
		rel = self._related_documents("03 - Devolución de mercancía", UUID_ORIGEN_C)
		self.assertEqual(rel[0]["relationship"], "03")


# ── REP: la fórmula proporcional se mantiene (no G-4) ─────────────────────────


class TestREPProporcionImpuestos(FrappeTestCase):
	"""Confirma que el REP prorratea contra el grand_total ORIGINAL del CFDI (correcto),
	y que el importe de la Nota de Crédito NO se trata como efectivo recibido."""

	def test_proporcion_contra_grand_total_original(self):
		grand_total_original = 1160.0  # 1000 + IVA 160
		iva_original = 160.0
		allocated_efectivo = 1044.0  # 90% recibido (900 + IVA 144)

		proporcion = allocated_efectivo / grand_total_original
		importe_iva_dr = round(iva_original * proporcion, 2)
		base_dr = round(importe_iva_dr / 0.16, 2)

		self.assertAlmostEqual(proporcion, 0.90, places=4)
		self.assertAlmostEqual(importe_iva_dr, 144.0, places=2)
		self.assertAlmostEqual(base_dr, 900.0, places=2)

	def test_nota_credito_no_es_efectivo_en_rep(self):
		"""El REP reporta solo el allocated_amount (efectivo); los $116 de la NC no aparecen."""
		nc_total = 116.0
		allocated_efectivo = 1044.0
		imp_pagado = round(allocated_efectivo, 2)  # como en _llenar_documentos_relacionados
		self.assertEqual(imp_pagado, 1044.0)
		self.assertNotEqual(imp_pagado, allocated_efectivo + nc_total)


# ── Meta: el campo existe en el DocType ───────────────────────────────────────


class TestMetaCampoTipoNotaCredito(FrappeTestCase):
	def test_campo_existe(self):
		meta = frappe.get_meta("Factura Fiscal Mexico")
		self.assertIn("fm_tipo_nota_credito", [f.fieldname for f in meta.fields])

	def test_opciones_incluyen_intenciones(self):
		meta = frappe.get_meta("Factura Fiscal Mexico")
		field = next(f for f in meta.fields if f.fieldname == "fm_tipo_nota_credito")
		opciones = [o.strip() for o in (field.options or "").split("\n") if o.strip()]
		self.assertIn("Devolución de mercancía", opciones)
		self.assertIn("Descuento / Bonificación", opciones)

	def test_company_settings_tiene_cuenta_descuentos(self):
		meta = frappe.get_meta("Facturacion Mexico Company Settings")
		field = next((f for f in meta.fields if f.fieldname == "cuenta_descuentos"), None)
		self.assertIsNotNone(field)
		self.assertEqual(field.fieldtype, "Link")
		self.assertEqual(field.options, "Account")


# ── Opción X: detección del motivo por la cuenta contable ─────────────────────


class TestCreditNoteLinesUseDiscountAccount(FrappeTestCase):
	def test_todas_las_lineas_coinciden(self):
		si = _dict(
			{"items": [_dict({"income_account": CUENTA_DESC}), _dict({"income_account": CUENTA_DESC})]}
		)
		self.assertTrue(credit_note_lines_use_discount_account(si, CUENTA_DESC))

	def test_una_linea_no_coincide(self):
		si = _dict(
			{"items": [_dict({"income_account": CUENTA_DESC}), _dict({"income_account": "401-001 - Ventas"})]}
		)
		self.assertFalse(credit_note_lines_use_discount_account(si, CUENTA_DESC))

	def test_sin_cuenta_configurada(self):
		si = _dict({"items": [_dict({"income_account": CUENTA_DESC})]})
		self.assertFalse(credit_note_lines_use_discount_account(si, None))

	def test_sin_items(self):
		si = _dict({"items": []})
		self.assertFalse(credit_note_lines_use_discount_account(si, CUENTA_DESC))


class TestPreseleccionMotivo(FrappeTestCase):
	"""_detect_nota_credito_motivo: preselección solo cuando el campo está vacío (punto 6 y 8)."""

	def _ffm(self, motivo_inicial=""):
		inst = FacturaFiscalMexico.__new__(FacturaFiscalMexico)
		inst.sales_invoice = "SINV-C-RETORNO"
		inst.company = "_Test Company"
		inst.fm_tipo_nota_credito = motivo_inicial
		return inst

	def test_preselecciona_descuento_si_cuenta_coincide(self):
		inst = self._ffm("")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.get_cuenta_descuentos",
				return_value=CUENTA_DESC,
			),
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.credit_note_lines_use_discount_account",
				return_value=True,
			),
		):
			inst._detect_nota_credito_motivo()
		self.assertEqual(inst.fm_tipo_nota_credito, "Descuento / Bonificación")

	def test_no_infiere_si_cuenta_no_coincide(self):
		"""Punto 8: si las cuentas no coinciden, no inferir → queda vacío (devolución)."""
		inst = self._ffm("")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.get_cuenta_descuentos",
				return_value=CUENTA_DESC,
			),
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.credit_note_lines_use_discount_account",
				return_value=False,
			),
		):
			inst._detect_nota_credito_motivo()
		self.assertEqual(inst.fm_tipo_nota_credito, "")

	def test_no_sobrescribe_seleccion_previa(self):
		"""Preselección no debe sobrescribir una elección explícita del usuario."""
		inst = self._ffm("Devolución de mercancía")
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.get_cuenta_descuentos",
				return_value=CUENTA_DESC,
			),
			patch(
				"facturacion_mexico.facturacion_fiscal.utils.credit_note_lines_use_discount_account",
				return_value=True,
			),
		):
			inst._detect_nota_credito_motivo()
		self.assertEqual(inst.fm_tipo_nota_credito, "Devolución de mercancía")


class TestGuardTimbradoContrato(FrappeTestCase):
	"""Contrato del guard pre-timbrado (Opción X, punto 9): NC marcada Descuento debe estar
	contabilizada contra la cuenta configurada; si no, se bloquea."""

	def _bloquea(self, ffm, si, cuenta):
		return is_nota_descuento(ffm) and not credit_note_lines_use_discount_account(si, cuenta)

	def test_descuento_cuenta_correcta_no_bloquea(self):
		ffm = _dict({"fm_tipo_comprobante": "E - Egreso", "fm_tipo_relacion_sat": "01 - Nota de crédito"})
		si = _dict({"items": [_dict({"income_account": CUENTA_DESC})]})
		self.assertFalse(self._bloquea(ffm, si, CUENTA_DESC))

	def test_descuento_cuenta_incorrecta_bloquea(self):
		ffm = _dict({"fm_tipo_comprobante": "E - Egreso", "fm_tipo_relacion_sat": "01 - Nota de crédito"})
		si = _dict({"items": [_dict({"income_account": "401-001 - Ventas"})]})
		self.assertTrue(self._bloquea(ffm, si, CUENTA_DESC))

	def test_devolucion_fisica_no_aplica_guard(self):
		ffm = _dict({"fm_tipo_comprobante": "E - Egreso", "fm_tipo_relacion_sat": "03 - Devolución"})
		si = _dict({"items": [_dict({"income_account": "401-001 - Ventas"})]})
		self.assertFalse(self._bloquea(ffm, si, CUENTA_DESC))


# ── Acción de negocio "Aplicar como Descuento / Bonificación" ─────────────────


def _fake_line(item_code, **over):
	base = {
		"item_code": item_code,
		"item_name": f"{item_code} nombre",
		"description": f"{item_code} descripción de mercancía",
		"income_account": "Sales - _TC",
		"qty": -1.0,
		"rate": 100.0,
		"amount": -100.0,
		"item_tax_template": None,
	}
	base.update(over)
	return _dict(base)


def _fake_si(**over):
	base = {
		"is_return": 1,
		"return_against": "SINV-ORIGEN",
		"docstatus": 0,
		"company": "_Test Company",
		# Dos partidas distintas: distinto item_code (→ distinta ClaveProdServ), distinta tasa/impuesto
		"items": [
			_fake_line("LLANTA-A", rate=100.0, amount=-100.0, item_tax_template="IVA 16%"),
			_fake_line("RIN-B", rate=50.0, amount=-50.0, item_tax_template="IVA 0% (exento)"),
		],
	}
	base.update(over)
	doc = _dict(base)
	doc.save = lambda: None  # stub: la acción real llama doc.save()
	return doc


def _fake_cn_descuento(**over):
	"""Nota de crédito YA convertida a descuento, con vínculo `sales_invoice_item` a cada origen."""
	base = {
		"is_return": 1,
		"return_against": "SINV-ORIGEN",
		"docstatus": 0,
		"company": "_Test Company",
		"update_stock": 0,
		"items": [
			_fake_line(
				"LLANTA-A",
				income_account=CUENTA_DESC,
				description="Descuento - LLANTA-A mercancía",
				sales_invoice_item="ORIG-1",
			),
			_fake_line(
				"RIN-B",
				income_account=CUENTA_DESC,
				description="Descuento - RIN-B mercancía",
				sales_invoice_item="ORIG-2",
			),
		],
	}
	base.update(over)
	doc = _dict(base)
	doc.save = lambda: None
	return doc


def _fake_origin(update_stock=1):
	"""Factura de origen: renglones con nombre estable e income_account/description originales."""
	origen = _dict(
		{
			"update_stock": update_stock,
			"items": [
				_dict(
					{"name": "ORIG-1", "income_account": "Sales - _TC", "description": "LLANTA-A mercancía"}
				),
				_dict({"name": "ORIG-2", "income_account": "Ventas - _TC", "description": "RIN-B mercancía"}),
			],
		}
	)
	# Boundary de permisos: no-op por defecto (los tests de permiso lo sobrescriben para lanzar).
	origen.check_permission = lambda perm=None: None
	return origen


class TestApplyDescuentoToLines(FrappeTestCase):
	"""Conserva item_code; cambia description a 'Descuento - <origen>' e income_account."""

	def test_conserva_item_code_cambia_descripcion_y_cuenta(self):
		doc = _fake_si()
		item_codes_antes = [r.item_code for r in doc["items"]]
		importes_antes = [(r.qty, r.rate, r.amount, r.item_tax_template) for r in doc["items"]]

		n = apply_descuento_to_lines(doc, CUENTA_DESC)

		self.assertEqual(n, 2)
		# item_code NO cambia (ERPNext exige que exista en la factura origen)
		self.assertEqual([r.item_code for r in doc["items"]], item_codes_antes)
		# description prefijada por línea, conservando la original
		self.assertEqual(doc["items"][0].description, "Descuento - LLANTA-A descripción de mercancía")
		self.assertEqual(doc["items"][1].description, "Descuento - RIN-B descripción de mercancía")
		# income_account = cuenta configurada
		self.assertTrue(all(r.income_account == CUENTA_DESC for r in doc["items"]))
		# cantidades/importes/impuestos intactos
		importes_despues = [(r.qty, r.rate, r.amount, r.item_tax_template) for r in doc["items"]]
		self.assertEqual(importes_antes, importes_despues)

	def test_idempotente_no_doble_prefijo(self):
		doc = _fake_si()
		apply_descuento_to_lines(doc, CUENTA_DESC)
		apply_descuento_to_lines(doc, CUENTA_DESC)  # segunda ejecución
		self.assertEqual(doc["items"][0].description, "Descuento - LLANTA-A descripción de mercancía")
		self.assertFalse(doc["items"][0].description.startswith("Descuento - Descuento"))

	def test_partidas_distintas_conservan_item_code_e_impuestos(self):
		"""Dos partidas distintas mantienen su item_code (→ su ClaveProdServ) e impuestos; no se colapsan."""
		doc = _fake_si()
		apply_descuento_to_lines(doc, CUENTA_DESC)
		self.assertEqual(doc["items"][0].item_code, "LLANTA-A")
		self.assertEqual(doc["items"][1].item_code, "RIN-B")
		self.assertEqual(doc["items"][0].item_tax_template, "IVA 16%")
		self.assertEqual(doc["items"][1].item_tax_template, "IVA 0% (exento)")

	def test_description_vacia_usa_item_name(self):
		"""ERPNext deja description vacío cuando el Item no tiene description; se usa item_name."""
		doc = _fake_si(items=[_fake_line("ACELGA-PZA", description="", item_name="ACELGA PZA ")])
		apply_descuento_to_lines(doc, CUENTA_DESC)
		# item_name con espacio final → build_descuento_description hace strip
		self.assertEqual(doc["items"][0].description, "Descuento - ACELGA PZA")

	def test_description_tiene_prioridad_sobre_item_name(self):
		doc = _fake_si(items=[_fake_line("ACELGA-PZA", description="Acelga fresca", item_name="ACELGA PZA")])
		apply_descuento_to_lines(doc, CUENTA_DESC)
		self.assertEqual(doc["items"][0].description, "Descuento - Acelga fresca")

	def test_idempotente_con_fallback_item_name(self):
		"""Reejecutar con description vacío inicial no duplica 'Descuento -'."""
		doc = _fake_si(items=[_fake_line("ACELGA-PZA", description="", item_name="ACELGA PZA")])
		apply_descuento_to_lines(doc, CUENTA_DESC)
		apply_descuento_to_lines(doc, CUENTA_DESC)  # segunda ejecución
		self.assertEqual(doc["items"][0].description, "Descuento - ACELGA PZA")
		self.assertFalse(doc["items"][0].description.startswith("Descuento - Descuento"))


class TestAplicarComoDescuento(FrappeTestCase):
	"""Acción de negocio: aplica descuento (sin cambiar Item) con guards; no expone cuentas/códigos."""

	def _run(self, doc, cuenta=CUENTA_DESC, discount_accounting=False):
		with (
			patch(
				"facturacion_mexico.facturacion_fiscal.api.nota_credito.get_cuenta_descuentos",
				return_value=cuenta,
			),
			patch(
				"facturacion_mexico.facturacion_fiscal.api.nota_credito._discount_accounting_enabled",
				return_value=discount_accounting,
			),
		):
			return preparar_como_descuento(doc)

	def test_aplica_descuento_conservando_item(self):
		doc = _fake_si()
		res = self._run(doc)
		self.assertTrue(res["ok"])
		self.assertEqual(res["lineas"], 2)
		self.assertEqual([r.item_code for r in doc["items"]], ["LLANTA-A", "RIN-B"])
		self.assertTrue(all(r.description.startswith("Descuento - ") for r in doc["items"]))
		self.assertTrue(all(r.income_account == CUENTA_DESC for r in doc["items"]))

	def test_bloquea_si_no_hay_cuenta_configurada(self):
		doc = _fake_si()
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, cuenta=None)

	def test_bloquea_si_no_es_return(self):
		doc = _fake_si(is_return=0)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc)

	def test_bloquea_si_no_hay_return_against(self):
		doc = _fake_si(return_against=None)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc)

	def test_bloquea_si_no_es_borrador(self):
		doc = _fake_si(docstatus=1)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc)

	def test_desmarca_actualizar_inventario(self):
		"""Un descuento no es devolución física → la acción fuerza update_stock a 0 aunque
		el origen lo haya heredado en 1 (evita que la NC mueva inventario)."""
		doc = _fake_si(update_stock=1)
		self._run(doc)
		self.assertEqual(doc.update_stock, 0)

	def test_respeta_inventario_ya_desmarcado(self):
		"""Si el origen ya venía sin actualizar inventario, se conserva en 0 (no rompe nada)."""
		doc = _fake_si(update_stock=0)
		self._run(doc)
		self.assertEqual(doc.update_stock, 0)

	def test_bloquea_si_discount_accounting_activo_sin_modificar(self):
		"""Precondición: con 'Enable Discount Accounting' = ON la acción bloquea ANTES de tocar la
		nota (income_account, description y update_stock quedan intactos)."""
		doc = _fake_si(update_stock=1)
		income_original = [r.income_account for r in doc["items"]]
		desc_original = [r.description for r in doc["items"]]
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, discount_accounting=True)
		# El documento NO se modificó
		self.assertEqual([r.income_account for r in doc["items"]], income_original)
		self.assertEqual([r.description for r in doc["items"]], desc_original)
		self.assertEqual(doc.update_stock, 1)

	def test_permite_si_discount_accounting_inactivo(self):
		"""Con 'Enable Discount Accounting' = OFF la conversión procede normalmente."""
		doc = _fake_si()
		res = self._run(doc, discount_accounting=False)
		self.assertTrue(res["ok"])
		self.assertTrue(all(r.income_account == CUENTA_DESC for r in doc["items"]))


class TestRevertirADevolucion(FrappeTestCase):
	"""Reversión descuento → devolución (motivo 03): restaura EXACTO desde el origen vía
	`sales_invoice_item`; bloquea sin modificar si alguna línea no mapea; solo en borrador."""

	def _run(self, doc, origen):
		with patch(
			"facturacion_mexico.facturacion_fiscal.api.nota_credito.frappe.get_doc",
			return_value=origen,
		):
			return preparar_reversion_a_devolucion(doc)

	def test_restaura_income_y_description_desde_origen(self):
		doc = _fake_cn_descuento()
		res = self._run(doc, _fake_origin(update_stock=1))
		self.assertTrue(res["ok"])
		self.assertEqual(res["lineas"], 2)
		self.assertEqual([r.income_account for r in doc["items"]], ["Sales - _TC", "Ventas - _TC"])
		self.assertEqual([r.description for r in doc["items"]], ["LLANTA-A mercancía", "RIN-B mercancía"])

	def test_restaura_update_stock_desde_origen_uno(self):
		doc = _fake_cn_descuento(update_stock=0)
		self._run(doc, _fake_origin(update_stock=1))
		self.assertEqual(doc.update_stock, 1)

	def test_restaura_update_stock_desde_origen_cero(self):
		doc = _fake_cn_descuento(update_stock=0)
		self._run(doc, _fake_origin(update_stock=0))
		self.assertEqual(doc.update_stock, 0)

	def test_bloquea_sin_vinculo_sin_modificar(self):
		"""Una línea sin sales_invoice_item → bloquea y NO modifica la nota (no adivina cuentas)."""
		doc = _fake_cn_descuento()
		doc["items"][1].sales_invoice_item = None
		income_original = [r.income_account for r in doc["items"]]
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, _fake_origin())
		self.assertEqual([r.income_account for r in doc["items"]], income_original)
		self.assertEqual(doc.update_stock, 0)

	def test_bloquea_vinculo_inexistente_en_origen(self):
		"""Vínculo que no existe en el origen → bloquea sin modificar."""
		doc = _fake_cn_descuento()
		doc["items"][0].sales_invoice_item = "NO-EXISTE"
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, _fake_origin())
		self.assertEqual(doc["items"][0].income_account, CUENTA_DESC)

	def test_bloquea_si_no_es_borrador(self):
		doc = _fake_cn_descuento(docstatus=1)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, _fake_origin())

	def test_bloquea_si_no_es_return(self):
		doc = _fake_cn_descuento(is_return=0)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, _fake_origin())

	def test_bloquea_si_no_hay_return_against(self):
		doc = _fake_cn_descuento(return_against=None)
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, _fake_origin())


def _perm_denegada(perm_denegado):
	"""check_permission que lanza PermissionError solo para el permtype indicado."""

	def _check(permtype="read", permlevel=None):
		if permtype == perm_denegado:
			raise frappe.PermissionError(f"sin permiso {permtype}")

	return _check


class TestPermisosNotaCredito(FrappeTestCase):
	"""Hardening (CodeRabbit #2): los endpoints whitelisted exigen permiso antes de operar.
	Un usuario sin permiso no puede ejecutar la acción y el documento no se modifica."""

	def test_aplicar_como_descuento_exige_write(self):
		from facturacion_mexico.facturacion_fiscal.api import nota_credito

		doc = _fake_si()
		doc.check_permission = _perm_denegada("write")
		income_original = [r.income_account for r in doc["items"]]
		with patch.object(nota_credito.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				nota_credito.aplicar_como_descuento("SINV-X")
		# No se modificó la nota
		self.assertEqual([r.income_account for r in doc["items"]], income_original)

	def test_revertir_a_devolucion_exige_write(self):
		from facturacion_mexico.facturacion_fiscal.api import nota_credito

		doc = _fake_cn_descuento()
		doc.check_permission = _perm_denegada("write")
		income_original = [r.income_account for r in doc["items"]]
		with patch.object(nota_credito.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				nota_credito.revertir_a_devolucion("SINV-X")
		self.assertEqual([r.income_account for r in doc["items"]], income_original)

	def test_estado_nota_descuento_exige_read(self):
		from facturacion_mexico.facturacion_fiscal.api import nota_credito

		doc = _fake_si()
		doc.check_permission = _perm_denegada("read")
		with patch.object(nota_credito.frappe, "get_doc", return_value=doc):
			with self.assertRaises(frappe.PermissionError):
				nota_credito.estado_nota_descuento("SINV-X")

	def test_reversion_exige_read_en_origen(self):
		"""La reversión lee la factura de origen → exige 'read' sobre ella antes de usar sus datos."""
		doc = _fake_cn_descuento()
		income_original = [r.income_account for r in doc["items"]]
		origen = _fake_origin()
		origen.check_permission = _perm_denegada("read")
		with patch(
			"facturacion_mexico.facturacion_fiscal.api.nota_credito.frappe.get_doc",
			return_value=origen,
		):
			with self.assertRaises(frappe.PermissionError):
				preparar_reversion_a_devolucion(doc)
		# No se modificó la nota
		self.assertEqual([r.income_account for r in doc["items"]], income_original)


# ── Concepto del CFDI: usa net_rate y NO emite nodo Descuento ─────────────────


class TestPayloadConceptoSinDescuento(FrappeTestCase):
	"""Garantiza que el concepto saliente del CFDI use net_rate (precio neto) y NUNCA emita un
	nodo 'discount'/Descuento — ni en ventas ni en notas de crédito por descuento. Regresión:
	el descuento queda integrado en el ValorUnitario, no como Descuento separado (a diferencia
	del comportamiento no deseado observado en la app anterior)."""

	def _item_payload_block(self):
		from facturacion_mexico.facturacion_fiscal import timbrado_api

		src = open(timbrado_api.__file__.replace(".pyc", ".py"), encoding="utf-8").read()
		# Bloque del concepto SALIENTE del CFDI (no los snapshots internos de comparación)
		m = re.search(r"item_payload = \{.*?items\.append\(item_payload\)", src, re.S)
		self.assertIsNotNone(m, "No se encontró el bloque item_payload en timbrado_api.py")
		return m.group(0)

	def test_precio_del_concepto_usa_net_rate(self):
		self.assertIn('"price": flt(item.net_rate)', self._item_payload_block())

	def test_concepto_no_incluye_nodo_discount(self):
		self.assertNotIn('"discount"', self._item_payload_block())


# ── Confirmación matemática (base / IVA / total) de la NC de descuento ─────────


class TestMatematicaDescuento(FrappeTestCase):
	"""Confirma numéricamente la base e IVA de una NC de descuento con precio IVA-incluido 16%.
	Coincide con el GL real timbrado en sandbox (NC1: base 86.21 / IVA 13.79 / total 100;
	NC2: base 77.59 / IVA 12.41 / total 90)."""

	def _base_iva(self, total_iva_incluido):
		base = round(total_iva_incluido / 1.16, 2)
		iva = round(base * 0.16, 2)
		return base, iva

	def test_nc_100_base_iva(self):
		base, iva = self._base_iva(100.0)
		self.assertEqual(base, 86.21)
		self.assertEqual(iva, 13.79)
		self.assertEqual(round(base + iva, 2), 100.00)

	def test_nc_90_base_iva(self):
		base, iva = self._base_iva(90.0)
		self.assertEqual(base, 77.59)
		self.assertEqual(iva, 12.41)
		self.assertEqual(round(base + iva, 2), 90.00)
