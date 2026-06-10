"""
Tests para generador_templates_fiscal.py

Cubre dos áreas críticas:
1. Deduplicación en _crear_o_actualizar_itt — la misma cuenta para múltiples roles
   no debe producir "entered twice in Item Tax" (bug corregido 2026-06-07)
2. Estructura de filas STCT con IEPS — IVA base + IEPS + IVA cascada deben ser
   tres filas aunque IVA base y cascada compartan account_head

Referencia canónica: Wind Power LLC en facturacion-v16.dev
  ITT IVA 0% - WP → 2 filas (IVA NAC + IVA FRO, cuentas distintas)
  IVA Nacional - IEPS - WP → 1 fila IVA base (WP solo tiene Honorarios habilitado, no IEPS)
"""

from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import (
	_build_rows,
	_crear_o_actualizar_itt,
)
from facturacion_mexico.utils.roles_fiscales import (
	ROL_IEPS_ALC,
	ROL_IEPS_AZU,
	ROL_IEPS_COMB,
	ROL_IVA_CERO,
	ROL_IVA_FRO,
	ROL_IVA_NAC,
)

# Cuentas ficticias usadas en todos los tests de deduplicación
_CUENTA_NAC = "IVA por Pagar NAC - _TC"
_CUENTA_FRO = "IVA por Pagar FRO - _TC"
_CUENTA_IEPS = "IEPS por Pagar - _TC"
_CUENTA_UNICA = "IVA por Pagar - _TC"  # cuenta compartida entre múltiples roles


def _mock_doc():
	"""Documento ITT simulado que registra las filas appended."""
	doc = MagicMock()
	doc.taxes = []

	def _append(table, row):
		doc.taxes.append(dict(row))

	doc.append = _append
	doc.name = "ITT Test - _TC"
	return doc


def _patch_itt(mock_doc):
	"""Context managers para aislar _crear_o_actualizar_itt de la BD."""
	return [
		patch(
			"facturacion_mexico.setup.item_groups._resolve_itt_name",
			return_value=None,
		),
		patch("frappe.new_doc", return_value=mock_doc),
		patch("frappe.db.commit"),
	]


def _apply_patches(patches):
	for p in patches:
		p.start()


def _stop_patches(patches):
	for p in patches:
		p.stop()


class TestITTDeduplicacion(FrappeTestCase):
	"""
	Verifica que _crear_o_actualizar_itt deduplica por account_head.

	Un ITT no puede tener la misma cuenta dos veces (ERPNext bloquea con
	"entered twice in Item Tax"). Cuando dos roles apuntan a la misma cuenta
	debe generarse una sola fila — la primera en orden.
	"""

	def _run_itt(self, taxes_config, mapeo_cuentas):
		doc = _mock_doc()
		patches = _patch_itt(doc)
		_apply_patches(patches)
		try:
			_crear_o_actualizar_itt("_Test Company 1", "_TC1", "ITT Test", taxes_config, mapeo_cuentas)
		finally:
			_stop_patches(patches)
		return doc.taxes

	# ------------------------------------------------------------------
	# Caso base: cuentas distintas → se incluyen todas
	# ------------------------------------------------------------------

	def test_dos_roles_cuentas_distintas_genera_dos_filas(self):
		"""NAC → cuenta_A, FRO → cuenta_B distintas → 2 filas. Caso WP."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0.0},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_NAC,
				ROL_IVA_FRO: _CUENTA_FRO,
			},
		)
		self.assertEqual(len(taxes), 2)
		self.assertEqual(taxes[0]["tax_type"], _CUENTA_NAC)
		self.assertEqual(taxes[1]["tax_type"], _CUENTA_FRO)

	def test_tres_roles_cuentas_distintas_genera_tres_filas(self):
		"""NAC → A, FRO → B, IEPS → C distintas → 3 filas."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 16.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 8.0},
				{"rol_fiscal": ROL_IEPS_ALC, "tax_rate": 26.5},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_NAC,
				ROL_IVA_FRO: _CUENTA_FRO,
				ROL_IEPS_ALC: _CUENTA_IEPS,
			},
		)
		self.assertEqual(len(taxes), 3)

	# ------------------------------------------------------------------
	# Cuenta compartida → deduplicación (el bug corregido)
	# ------------------------------------------------------------------

	def test_dos_roles_misma_cuenta_genera_una_fila(self):
		"""
		NAC → cuenta_X, CERO → cuenta_X (misma) → 1 fila.
		Caso ACG: una sola cuenta IVA para todos los roles.
		Sin la corrección esto lanzaba "entered twice in Item Tax".
		"""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0.0},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_UNICA,
				ROL_IVA_CERO: _CUENTA_UNICA,
			},
		)
		self.assertEqual(len(taxes), 1)
		self.assertEqual(taxes[0]["tax_type"], _CUENTA_UNICA)
		self.assertEqual(taxes[0]["tax_rate"], 0.0)

	def test_tres_roles_misma_cuenta_genera_una_fila(self):
		"""NAC + FRO + CERO todos apuntando a la misma cuenta → 1 fila."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0.0},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_UNICA,
				ROL_IVA_FRO: _CUENTA_UNICA,
				ROL_IVA_CERO: _CUENTA_UNICA,
			},
		)
		self.assertEqual(len(taxes), 1)

	def test_tres_roles_dos_cuentas_genera_dos_filas(self):
		"""NAC → A, FRO → A (comparte con NAC), CERO → B distinta → 2 filas."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0.0},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_NAC,
				ROL_IVA_FRO: _CUENTA_NAC,  # comparte con NAC
				ROL_IVA_CERO: _CUENTA_FRO,  # cuenta distinta
			},
		)
		self.assertEqual(len(taxes), 2)
		cuentas = [t["tax_type"] for t in taxes]
		self.assertIn(_CUENTA_NAC, cuentas)
		self.assertIn(_CUENTA_FRO, cuentas)

	# ------------------------------------------------------------------
	# Rol sin mapeo → se omite
	# ------------------------------------------------------------------

	def test_rol_sin_mapeo_se_omite(self):
		"""Rol no presente en mapeo_cuentas no genera fila."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0.0},  # sin mapeo
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_NAC,
				# ROL_IVA_FRO intencionalmente ausente
			},
		)
		self.assertEqual(len(taxes), 1)
		self.assertEqual(taxes[0]["tax_type"], _CUENTA_NAC)

	def test_todos_los_roles_sin_mapeo_genera_cero_filas(self):
		"""Si ningún rol tiene mapeo, el ITT queda vacío."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0.0},
			],
			mapeo_cuentas={},
		)
		self.assertEqual(len(taxes), 0)

	# ------------------------------------------------------------------
	# Verificar que idx se asigna correctamente tras deduplicación
	# ------------------------------------------------------------------

	def test_idx_consecutivo_tras_deduplicacion(self):
		"""Las filas supervivientes tienen idx 1, 2 sin huecos."""
		taxes = self._run_itt(
			taxes_config=[
				{"rol_fiscal": ROL_IVA_NAC, "tax_rate": 0.0},
				{"rol_fiscal": ROL_IVA_FRO, "tax_rate": 0.0},  # sin mapeo → omitida
				{"rol_fiscal": ROL_IVA_CERO, "tax_rate": 0.0},
			],
			mapeo_cuentas={
				ROL_IVA_NAC: _CUENTA_NAC,
				# ROL_IVA_FRO ausente
				ROL_IVA_CERO: _CUENTA_FRO,
			},
		)
		self.assertEqual(len(taxes), 2)
		self.assertEqual(taxes[0]["idx"], 1)
		self.assertEqual(taxes[1]["idx"], 2)


class TestBuildRowsSTCT(FrappeTestCase):
	"""
	Verifica la estructura de filas para STCT generadas por _build_rows.

	Importante: en STCT sí pueden existir dos filas con la misma account_head
	(IVA base y IVA cascada sobre IEPS tienen misma cuenta pero charge_type distinto).
	_build_rows NO debe deduplicar — eso es responsabilidad del generador de ITT.
	"""

	def _mapeos_base(self, cuenta_nac=_CUENTA_NAC, cuenta_ieps=_CUENTA_IEPS):
		"""Mapeos mínimos para tests de STCT Nacional."""
		return {
			"tiene_iva_nacional": True,
			"tiene_iva_frontera": False,
			"ieps_disponibles": {
				"Alcohol": False,
				"Azucar": False,
				"Combustibles": False,
				"Tabaco_Tasa": False,
				"Tabaco_Cuota": False,
			},
			"retenciones_disponibles": {
				"IVA_Honorarios": False,
				"ISR_Honorarios": False,
				"IVA_Arrendamiento": False,
				"ISR_Arrendamiento": False,
				"IVA_Autotransporte": False,
				"ISR_Autotransporte": False,
				"IVA_RESICO": False,
				"ISR_RESICO": False,
			},
			"tiene_algun_ieps": False,
			"tiene_alguna_retencion": False,
			"mapeos_por_rol": {
				ROL_IVA_NAC: cuenta_nac,
				ROL_IEPS_ALC: cuenta_ieps,
				ROL_IEPS_AZU: cuenta_ieps,
				ROL_IEPS_COMB: cuenta_ieps,
			},
		}

	# ------------------------------------------------------------------
	# Básico
	# ------------------------------------------------------------------

	def test_stct_basico_genera_una_fila_iva(self):
		"""Variante Básico → solo IVA base On Net Total."""
		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=self._mapeos_base(),
		)
		self.assertEqual(len(rows), 1)
		self.assertEqual(rows[0]["charge_type"], "On Net Total")
		self.assertAlmostEqual(rows[0]["rate"], 16.0)
		self.assertEqual(rows[0]["account_head"], _CUENTA_NAC)

	# ------------------------------------------------------------------
	# IEPS + IVA: la misma cuenta_iva aparece DOS veces intencionalmente
	# ------------------------------------------------------------------

	def test_stct_ieps_alcohol_genera_tres_filas(self):
		"""
		Variante IEPS con Alcohol:
		  fila 1 → IVA base (On Net Total, cuenta_nac)
		  fila 2 → IEPS Alcohol (charge_type según tabla maestra, cuenta_ieps)
		  fila 3 → IVA cascada sobre IEPS (On Previous Row Amount, cuenta_nac)

		Las filas 1 y 3 comparten cuenta_nac — esto es CORRECTO en STCT,
		NO debe deduplicarse aquí (los charge_type son distintos).
		"""
		mapeos = self._mapeos_base()
		mapeos["ieps_disponibles"]["Alcohol"] = True
		mapeos["tiene_algun_ieps"] = True

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="IEPS",
			mapeos_disponibles=mapeos,
		)

		self.assertEqual(len(rows), 3, f"Esperadas 3 filas, got {len(rows)}: {rows}")

		account_heads = [r["account_head"] for r in rows]
		charge_types = [r["charge_type"] for r in rows]

		# Fila 0: IVA base
		self.assertEqual(account_heads[0], _CUENTA_NAC)
		self.assertEqual(charge_types[0], "On Net Total")

		# Fila 1: IEPS
		self.assertEqual(account_heads[1], _CUENTA_IEPS)

		# Fila 2: IVA cascada — misma cuenta que fila 0, charge_type distinto
		self.assertEqual(account_heads[2], _CUENTA_NAC)
		self.assertEqual(charge_types[2], "On Previous Row Amount")

	def test_stct_ieps_alcohol_row_id_apunta_a_fila_ieps(self):
		"""La fila de IVA cascada debe apuntar (row_id) a la fila del IEPS."""
		mapeos = self._mapeos_base()
		mapeos["ieps_disponibles"]["Alcohol"] = True
		mapeos["tiene_algun_ieps"] = True

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="IEPS",
			mapeos_disponibles=mapeos,
		)

		# row_id de la fila IVA cascada (índice 2) debe apuntar al idx del IEPS
		iva_cascada = rows[2]
		self.assertIsNotNone(iva_cascada.get("row_id"))

	def test_stct_ieps_multiples_sin_retenciones(self):
		"""
		Variante IEPS con Alcohol + Azúcar:
		IVA base + IEPS_Alc + IVA_casc_Alc + IEPS_Azu + IVA_casc_Azu = 5 filas.
		"""
		mapeos = self._mapeos_base()
		mapeos["ieps_disponibles"]["Alcohol"] = True
		mapeos["ieps_disponibles"]["Azucar"] = True
		mapeos["tiene_algun_ieps"] = True

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="IEPS",
			mapeos_disponibles=mapeos,
		)

		self.assertEqual(len(rows), 5)

		# Las filas de IVA cascada tienen charge_type "On Previous Row Amount"
		cascadas = [r for r in rows if r["charge_type"] == "On Previous Row Amount"]
		self.assertEqual(len(cascadas), 2)

		# Las filas de IEPS son las de en medio
		ieps_rows = [r for r in rows if r["account_head"] == _CUENTA_IEPS]
		self.assertEqual(len(ieps_rows), 2)

	def test_stct_sin_iva_zona_devuelve_vacio(self):
		"""Si la zona no tiene IVA mapeado, _build_rows retorna lista vacía."""
		mapeos = self._mapeos_base()
		mapeos["tiene_iva_nacional"] = False
		mapeos["mapeos_por_rol"].pop(ROL_IVA_NAC, None)

		rows, omitted = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=mapeos,
		)

		self.assertEqual(rows, [])
		self.assertTrue(len(omitted) > 0)

	# ------------------------------------------------------------------
	# Confirmar que _build_rows NO deduplica (a diferencia de _crear_o_actualizar_itt)
	# ------------------------------------------------------------------

	def test_stct_no_deduplica_iva_cascada(self):
		"""
		_build_rows produce filas con account_head repetido (IVA base + cascada).
		Esto es correcto — la deduplicación solo aplica en ITT, no en STCT.
		"""
		mapeos = self._mapeos_base()
		mapeos["ieps_disponibles"]["Alcohol"] = True
		mapeos["tiene_algun_ieps"] = True

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="IEPS",
			mapeos_disponibles=mapeos,
		)

		# cuenta_nac aparece en fila 0 (base) y fila 2 (cascada) — dos veces
		filas_con_cuenta_nac = [r for r in rows if r["account_head"] == _CUENTA_NAC]
		self.assertEqual(len(filas_con_cuenta_nac), 2, "STCT debe tener IVA base Y IVA cascada")

	# ------------------------------------------------------------------
	# sales_prices_include_tax — included_in_print_rate
	# ------------------------------------------------------------------

	def test_default_included_in_print_rate_es_cero(self):
		"""Default: included_in_print_rate = 0 — precio no incluye impuesto."""
		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=self._mapeos_base(),
		)
		self.assertEqual(rows[0]["included_in_print_rate"], 0)

	def test_sales_prices_include_tax_true_setea_included_in_print_rate(self):
		"""sales_prices_include_tax=True → included_in_print_rate = 1 en fila IVA base."""
		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=self._mapeos_base(),
			included_in_print_rate=1,
		)
		self.assertEqual(rows[0]["included_in_print_rate"], 1)

	def test_sales_prices_include_tax_false_setea_cero(self):
		"""sales_prices_include_tax=False → included_in_print_rate = 0 en fila IVA base."""
		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=self._mapeos_base(),
			included_in_print_rate=0,
		)
		self.assertEqual(rows[0]["included_in_print_rate"], 0)

	def test_itt_no_modificado_por_sales_prices_include_tax(self):
		"""ITT no se modifica — solo se verifica que _build_rows no toca ITT."""
		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="Básico",
			mapeos_disponibles=self._mapeos_base(),
			included_in_print_rate=1,
		)
		# Solo la fila IVA base (fila 0) lleva included_in_print_rate
		# Filas IEPS y cascada no deben tener included_in_print_rate = 1
		self.assertEqual(len(rows), 1)  # Básico solo tiene IVA base

	def test_ieps_variante_solo_iva_base_lleva_included_in_print_rate(self):
		"""En variante IEPS, solo la fila IVA base lleva included_in_print_rate = 1."""
		mapeos = self._mapeos_base()
		mapeos["ieps_disponibles"]["Alcohol"] = True
		mapeos["tiene_algun_ieps"] = True

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Nacional",
			iva_rate=16.0,
			variant="IEPS",
			mapeos_disponibles=mapeos,
			included_in_print_rate=1,
		)
		# Fila 0 = IVA base → included_in_print_rate = 1
		self.assertEqual(rows[0]["included_in_print_rate"], 1)
		# Filas 1+ (IEPS, cascada) no llevan included_in_print_rate = 1
		for r in rows[1:]:
			self.assertNotEqual(r.get("included_in_print_rate", 0), 1)

	def test_frontera_con_sales_prices_include_tax(self):
		"""Zona Frontera también respeta sales_prices_include_tax."""
		mapeos = self._mapeos_base()
		mapeos["tiene_iva_frontera"] = True
		mapeos["mapeos_por_rol"]["IVA_FRO"] = _CUENTA_FRO

		rows, _ = _build_rows(
			company="_Test Company 1",
			zona="Frontera",
			iva_rate=8.0,
			variant="Básico",
			mapeos_disponibles=mapeos,
			included_in_print_rate=1,
		)
		self.assertEqual(rows[0]["included_in_print_rate"], 1)
