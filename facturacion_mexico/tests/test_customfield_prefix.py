import json
import unittest
from pathlib import Path
from facturacion_mexico.tests.legacy_allowlist import LEGACY_CF_ALLOWLIST

class TestCustomFieldPrefix(unittest.TestCase):

    def test_custom_fields_prefix(self):
        """Test: Verificar que todos los custom fields nuevos usan prefijo fm_"""
        fixtures = Path("facturacion_mexico/fixtures/custom_field.json")
        if not fixtures.exists():
            return  # sin fixtures; no falla

        data = json.loads(fixtures.read_text(encoding="utf-8"))
        bad = []
        for cf in data:
            fieldname = (cf.get("fieldname") or "").strip()
            if not fieldname:
                continue
            if fieldname in LEGACY_CF_ALLOWLIST:
                continue
            if not fieldname.startswith("fm_"):
                bad.append(fieldname)

        self.assertEqual(len(bad), 0,
            f"Custom Fields sin prefijo 'fm_': {bad}. "
            "Para nuevos campos usa 'fm_'. "
            "Si es legado documentado, agrégalo a LEGACY_CF_ALLOWLIST."
        )