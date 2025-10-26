#!/usr/bin/env python3
"""
Test de Sincronización - Roles Fiscales JSON ↔ Python.

PROPÓSITO:
----------
Validar que las opciones Select en JSON DocType coincidan exactamente con
TABLA_MAESTRA_ROLES_FISCALES en roles_fiscales.py.

RAZÓN:
------
Frappe framework requiere opciones Select en JSON (metadata estática).
No puede importar constantes Python dinámicamente.
Por tanto, existe duplicación técnica inevitable.

Este test FALLA si:
- Se agregan/modifican roles en Python pero NO en JSON
- Se agregan/modifican roles en JSON pero NO en Python
- Los nombres no coinciden exactamente (typos)

CUANDO SE EJECUTA:
------------------
Este test se ejecuta automáticamente en la suite regular:
    bench --site facturacion.dev run-tests --app facturacion_mexico

PROCESO AL MODIFICAR ROLES:
---------------------------
1. Actualizar TABLA_MAESTRA_ROLES_FISCALES en roles_fiscales.py
2. Actualizar opciones Select en mapeo_cuenta_fiscal_mexico.json
3. bench migrate (actualizar schema DocType)
4. Ejecutar script migración datos si hay cambios en BD
5. Este test valida que todo quedó sincronizado
"""

import json
import os

import frappe
from frappe.tests.utils import FrappeTestCase

from facturacion_mexico.utils.roles_fiscales import TODOS_LOS_ROLES


class TestSyncRolesFiscalesJSONPython(FrappeTestCase):
	"""Test para validar sincronización entre JSON DocType y constantes Python."""

	def test_json_doctype_sincronizado_con_constantes_python(self):
		"""
		Test crítico: opciones JSON deben coincidir EXACTAMENTE con TODOS_LOS_ROLES.

		FALLA SI:
		- Roles agregados en Python pero no en JSON
		- Roles agregados en JSON pero no en Python
		- Typos o diferencias en nombres
		"""
		# Leer opciones Select del JSON DocType
		json_path = os.path.join(
			frappe.get_app_path("facturacion_mexico"),
			"facturacion_fiscal",
			"doctype",
			"mapeo_cuenta_fiscal_mexico",
			"mapeo_cuenta_fiscal_mexico.json",
		)

		with open(json_path) as f:
			doctype_json = json.load(f)

		# Encontrar campo rol_fiscal
		rol_fiscal_field = None
		for field in doctype_json.get("fields", []):
			if field.get("fieldname") == "rol_fiscal":
				rol_fiscal_field = field
				break

		self.assertIsNotNone(
			rol_fiscal_field, "Campo 'rol_fiscal' no encontrado en JSON DocType"
		)

		# Parsear opciones Select (string separado por \n)
		json_options_str = rol_fiscal_field.get("options", "")
		json_options = [opt.strip() for opt in json_options_str.split("\n") if opt.strip()]

		# Comparar con constantes Python
		python_roles = set(TODOS_LOS_ROLES)
		json_roles = set(json_options)

		# Validar que son EXACTAMENTE iguales
		faltantes_en_json = python_roles - json_roles
		extras_en_json = json_roles - python_roles

		error_msg = []
		if faltantes_en_json:
			error_msg.append(
				f"\n❌ Roles en Python pero NO en JSON ({len(faltantes_en_json)}):\n"
				+ "\n".join(f"  - {rol}" for rol in sorted(faltantes_en_json))
			)

		if extras_en_json:
			error_msg.append(
				f"\n❌ Roles en JSON pero NO en Python ({len(extras_en_json)}):\n"
				+ "\n".join(f"  - {rol}" for rol in sorted(extras_en_json))
			)

		if error_msg:
			error_msg.insert(
				0,
				"\n" + "=" * 80 + "\n"
				"DESINCRONIZACIÓN DETECTADA: JSON ↔ Python\n"
				+ "=" * 80,
			)
			error_msg.append(
				"\n" + "=" * 80 + "\n"
				"PROCESO DE CORRECCIÓN:\n"
				"1. Actualizar TABLA_MAESTRA_ROLES_FISCALES en roles_fiscales.py\n"
				"2. Actualizar opciones Select en mapeo_cuenta_fiscal_mexico.json\n"
				"3. bench migrate\n"
				"4. Re-ejecutar este test\n"
				+ "=" * 80
			)
			self.fail("".join(error_msg))

		# Si llegamos aquí, todo sincronizado ✅
		print(f"\n✅ SINCRONIZACIÓN VÁLIDA: {len(python_roles)} roles coinciden")

	def test_orden_alfabetico_roles_en_json(self):
		"""
		Test recomendación: roles en JSON deberían estar ordenados alfabéticamente.

		ADVERTENCIA: No falla, solo informa si orden subóptimo.
		"""
		# Leer opciones JSON
		json_path = os.path.join(
			frappe.get_app_path("facturacion_mexico"),
			"facturacion_fiscal",
			"doctype",
			"mapeo_cuenta_fiscal_mexico",
			"mapeo_cuenta_fiscal_mexico.json",
		)

		with open(json_path) as f:
			doctype_json = json.load(f)

		rol_fiscal_field = next(
			(f for f in doctype_json.get("fields", []) if f.get("fieldname") == "rol_fiscal"),
			None,
		)

		if not rol_fiscal_field:
			return  # Skip si no hay campo

		json_options_str = rol_fiscal_field.get("options", "")
		json_options = [opt.strip() for opt in json_options_str.split("\n") if opt.strip()]

		# Verificar si está ordenado
		sorted_options = sorted(json_options, key=str.lower)

		if json_options != sorted_options:
			print(
				"\n⚠️ RECOMENDACIÓN: Roles en JSON no están ordenados alfabéticamente\n"
				"Esto no afecta funcionalidad, pero mejora legibilidad.\n"
				"Considerar reordenar para futuras actualizaciones."
			)
		else:
			print("\n✅ Roles en JSON ordenados alfabéticamente")

	def test_cantidad_roles_esperados(self):
		"""
		Test sanity check: validar que tenemos cantidad esperada de roles.

		Actualizar este número si se agregan/remueven categorías de roles.
		"""
		# Según TABLA_MAESTRA_ROLES_FISCALES debemos tener:
		# 4 IVA + 5 IEPS + 8 Retenciones (4 tipos × IVA+ISR) = 17 roles
		CANTIDAD_ESPERADA = 17

		cantidad_actual = len(TODOS_LOS_ROLES)

		self.assertEqual(
			cantidad_actual,
			CANTIDAD_ESPERADA,
			f"Cantidad de roles cambió: esperado {CANTIDAD_ESPERADA}, actual {cantidad_actual}. "
			"Si agregaste/removiste roles intencionalmente, actualiza CANTIDAD_ESPERADA en este test.",
		)

		print(f"\n✅ Cantidad de roles correcta: {cantidad_actual} roles")


if __name__ == "__main__":
	frappe.init(site="facturacion.dev")
	frappe.connect()

	import unittest

	unittest.main()
