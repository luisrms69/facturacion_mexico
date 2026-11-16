#!/usr/bin/env python3
"""Pruebas de integridad de los fixtures de Custom Field.

Guardas de regresión para el error de migración
``LinkValidationError: Could not find Module (for export): Facturacion Mexico``:

1. La app no administra ``Address-is_your_company_address`` (campo propiedad de ERPNext).
2. Ningún Custom Field del fixture referencia un módulo inexistente.
3. Todo módulo usado por el fixture está declarado en ``modules.txt``.
4. Todo campo funcional nuevo respeta el prefijo ``fm_`` (los estructurales e
   históricos ya justificados quedan excluidos).

Conforme RG-003: pruebas simples, deterministas, sin red.
"""

import json
import unittest
from pathlib import Path

from facturacion_mexico.tests.legacy_allowlist import LEGACY_CF_ALLOWLIST

APP_DIR = Path(__file__).resolve().parents[1]
FIXTURE = APP_DIR / "fixtures" / "custom_field.json"
MODULES_TXT = APP_DIR / "modules.txt"

# Campo propiedad de ERPNext que la app no debe administrar.
ERPNEXT_OWNED_FIELD = "Address-is_your_company_address"

# Fieldtypes sin dato que no requieren prefijo fm_.
STRUCTURAL_FIELDTYPES = {"Section Break", "Column Break", "Tab Break", "HTML"}

# Campos históricos, sin prefijo fm_, justificados (por nombre exacto Custom Field).
HISTORICAL_NONFM_NAMES = {"Branch-company"}


def _load_fixture():
	return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _declared_modules():
	return {line.strip() for line in MODULES_TXT.read_text(encoding="utf-8").splitlines() if line.strip()}


def _hooks_custom_field_filter():
	"""Lista de nombres de Custom Field declarados en el filtro de fixtures de hooks.py."""
	from facturacion_mexico import hooks

	for entry in hooks.fixtures:
		if isinstance(entry, dict) and entry.get("dt") == "Custom Field":
			for flt in entry.get("filters", []):
				# formato: ["name", "in", [...]]
				if len(flt) == 3 and flt[0] == "name" and flt[1] == "in":
					return list(flt[2])
	return []


class TestFixturesModuleIntegrity(unittest.TestCase):
	def test_erpnext_owned_field_not_in_fixture(self):
		"""El campo de ERPNext no debe estar en custom_field.json."""
		names = {cf.get("name") for cf in _load_fixture()}
		self.assertNotIn(
			ERPNEXT_OWNED_FIELD,
			names,
			f"{ERPNEXT_OWNED_FIELD} es propiedad de ERPNext; no debe administrarse desde fixtures.",
		)

	def test_erpnext_owned_field_not_in_hooks_filter(self):
		"""El campo de ERPNext no debe estar en el filtro de hooks.py."""
		self.assertNotIn(
			ERPNEXT_OWNED_FIELD,
			_hooks_custom_field_filter(),
			f"{ERPNEXT_OWNED_FIELD} no debe estar en el filtro de Custom Field de hooks.py.",
		)

	def test_no_obsolete_module(self):
		"""Ningún Custom Field debe referenciar el módulo obsoleto 'Facturacion Mexico'."""
		offenders = [cf.get("name") for cf in _load_fixture() if cf.get("module") == "Facturacion Mexico"]
		self.assertEqual(
			offenders,
			[],
			f"Custom Fields con módulo obsoleto 'Facturacion Mexico': {offenders}. "
			"El módulo correcto es 'Facturacion Fiscal'.",
		)

	def test_fixture_modules_declared(self):
		"""Todo módulo usado por el fixture debe existir en modules.txt."""
		declared = _declared_modules()
		orphans = sorted({cf.get("module") for cf in _load_fixture() if cf.get("module")} - declared)
		self.assertEqual(
			orphans,
			[],
			f"Módulos usados por el fixture que no están en modules.txt: {orphans}.",
		)

	def test_prefix_rule_for_functional_fields(self):
		"""Los campos funcionales nuevos deben usar prefijo fm_ (o ffm_)."""
		bad = []
		for cf in _load_fixture():
			fieldname = (cf.get("fieldname") or "").strip()
			if not fieldname:
				continue
			if cf.get("fieldtype") in STRUCTURAL_FIELDTYPES:
				continue
			if cf.get("name") in HISTORICAL_NONFM_NAMES:
				continue
			if fieldname in LEGACY_CF_ALLOWLIST:
				continue
			if not (fieldname.startswith("fm_") or fieldname.startswith("ffm_")):
				bad.append(cf.get("name"))
		self.assertEqual(
			bad,
			[],
			f"Custom Fields funcionales sin prefijo 'fm_': {bad}.",
		)


if __name__ == "__main__":
	unittest.main()
