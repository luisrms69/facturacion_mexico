"""Regresión: lookups de Customer cuando el docname contiene comillas u otros
caracteres especiales — cubre TODOS los call-sites detectados.

Bug original: varios lookups en JS leían campos del Customer con
`frappe.db.get_value("Customer", frm.doc.customer, [...])` pasando el docname como
STRING suelto. En el servidor, `frappe.client.get_value` pasa ese string por
`get_safe_filters()` → `orjson.loads()`. Si el docname es JSON válido (p.ej. envuelto en
comillas dobles: `"LOGISTICA Y TRANSPORTE MAXMEX"`), orjson lo interpreta como string JSON
y le QUITA las comillas → el `name` resultante ya no existe → resultado vacío. Efectos:
    - botón Timbrar oculto + "el RFC del cliente no está validado con SAT" (aunque =1);
    - defaults de Centro de Costos / Price List no se autollenan;
    - Uso CFDI default no se asigna;
    - visibilidad de venta mostrador (fm_allow_generic_rfc) mal calculada.

Fix: pasar el filtro como dict explícito `{ name: customer }`. `frappe.call` lo serializa a
JSON escapando las comillas, y `orjson` lo reconstruye intacto.

Estas pruebas reproducen fielmente el borde HTTP (`frappe.client.get_value`), que es la
función whitelisted donde vive `get_safe_filters`. La API Python directa
`frappe.db.get_value` NO pasa por ahí (usa param-binding) y es inmune — no se prueba aquí.

Call-sites cubiertos (post-fix, todos con filtro dict):
    sales_invoice.js  _check_rfc_and_show_timbrar   -> tax_id, fm_rfc_validated
    sales_invoice.js  apply_customer_defaults       -> fm_customer_default_cost_center, default_price_list
    sales_invoice.js  cost_center handler           -> default_price_list
    factura_fiscal_mexico.js  auto_assign_cfdi      -> fm_uso_cfdi_default
    factura_fiscal_mexico.js  venta mostrador       -> fm_allow_generic_rfc
"""

from typing import ClassVar

import frappe
from frappe.client import get_value as client_get_value
from frappe.tests.utils import FrappeTestCase
from frappe.utils import cint


def _filters_dict(name):
	"""Filtro tal como lo envía el JS corregido: dict serializado a JSON (comillas escapadas)."""
	return frappe.as_json({"name": name})


def _fields_arg(fields):
	"""fieldname tal como lo envía frappe.db.get_value cuando recibe una lista."""
	return frappe.as_json(fields) if isinstance(fields, list) else fields


class TestCustomerDocnameSafeLookup(FrappeTestCase):
	# Docnames a cubrir: normal, envuelto-en-comillas (caso reportado), comillas embebidas,
	# apóstrofo, ampersand y acentos.
	# NOTA: el hash {h} va DENTRO de las comillas de cierre en el caso "envuelto" para que el
	# docname completo sea un string JSON válido ("...")— así reproduce la trampa real de orjson
	# (que solo mutila nombres JSON-parseables de extremo a extremo, como el docname productivo
	# "LOGISTICA Y TRANSPORTE MAXMEX"). Si el hash quedara fuera de la comilla, ya no sería JSON.
	NAME_TEMPLATES: ClassVar[list] = [
		"CLIENTE NORMAL {h}",
		'"LOGISTICA Y TRANSPORTE MAXMEX {h}"',
		'CLIENTE "SUCURSAL NORTE" {h}',
		"O'CONNOR TRANSPORTES {h}",
		"ACME & ASOCIADOS {h}",
		"CAFÉ MAÑANA SA {h}",
	]

	# Campos leídos por cada call-site (los que el fix debe devolver intactos).
	SCENARIO_FIELDS: ClassVar[dict] = {
		"boton_timbrar (tax_id + fm_rfc_validated)": ["tax_id", "fm_rfc_validated"],
		"apply_customer_defaults (CC + price list)": [
			"fm_customer_default_cost_center",
			"default_price_list",
		],
		"cost_center handler (default_price_list)": ["default_price_list"],
		"auto_assign_cfdi (fm_uso_cfdi_default)": ["fm_uso_cfdi_default"],
		"venta_mostrador (fm_allow_generic_rfc)": ["fm_allow_generic_rfc"],
	}

	def setUp(self):
		self.h = frappe.generate_hash()[:6]
		self.customer_group = frappe.db.get_value("Customer Group", {"is_group": 0}, "name")
		self.territory = frappe.db.get_value("Territory", {"is_group": 0}, "name")

		# Valores concretos existentes para los campos Link (si el site los tiene).
		self.cost_center = frappe.db.get_value("Cost Center", {"is_group": 0}, "name")
		self.price_list = frappe.db.get_value("Price List", {"selling": 1}, "name") or frappe.db.get_value(
			"Price List", {}, "name"
		)
		self.uso_cfdi = frappe.db.get_value("Uso CFDI SAT", {}, "name")

		# Valores esperados que se fijan en CADA customer (para aserciones de igualdad exacta).
		self.expected = {
			"tax_id": "XAXX010101000",
			"fm_rfc_validated": 1,
			"fm_allow_generic_rfc": 1,
			"fm_customer_default_cost_center": self.cost_center,
			"default_price_list": self.price_list,
			"fm_uso_cfdi_default": self.uso_cfdi,
		}

		self.names = []
		for i, tpl in enumerate(self.NAME_TEMPLATES):
			target = tpl.format(h=self.h)
			# Insertar con nombre plano y renombrar al docname objetivo: el docname queda con
			# los caracteres especiales sin depender de la config de naming de Customer.
			doc = frappe.get_doc(
				{
					"doctype": "Customer",
					"customer_name": f"TMP-{self.h}-{i}",
					"customer_type": "Company",
					"customer_group": self.customer_group,
					"territory": self.territory,
				}
			).insert(ignore_permissions=True)
			frappe.rename_doc("Customer", doc.name, target, force=True, show_alert=False)

			# Fijar valores por db.set_value (evita validación de formato RFC del controller).
			updates = {k: v for k, v in self.expected.items() if v is not None}
			for field, value in updates.items():
				frappe.db.set_value("Customer", target, field, value)
			self.names.append(target)

		frappe.db.commit()  # nosemgrep: frappe-manual-commit

	# ------------------------------------------------------------------ CENTRAL

	def test_todos_los_campos_por_escenario_con_dict(self):
		"""CENTRAL: para cada call-site y cada docname especial, el filtro dict encuentra al
		cliente y devuelve los campos con el valor fijado (nombre llega intacto)."""
		for scenario, fields in self.SCENARIO_FIELDS.items():
			for name in self.names:
				r = client_get_value("Customer", _fields_arg(fields), filters=_filters_dict(name))
				self.assertTrue(r, f"[{scenario}] lookup dict vacío para docname {name!r}")
				for field in fields:
					self.assertIn(field, r, f"[{scenario}] falta campo {field} para {name!r}")
					expected = self.expected.get(field)
					if expected is None:
						continue  # sin valor de referencia en el site; basta con haber encontrado al cliente
					got = r.get(field)
					if field in ("fm_rfc_validated", "fm_allow_generic_rfc"):
						got = cint(got)
					self.assertEqual(
						got,
						expected,
						f"[{scenario}] {field}={got!r} != esperado {expected!r} para {name!r}",
					)

	# ------------------------------------------------------------------ TRAMPA

	def test_string_suelto_pierde_nombre_entre_comillas(self):
		"""TRAMPA/REGRESIÓN: el docname envuelto en comillas dobles, como string suelto, es
		mutilado por get_safe_filters/orjson → vacío. Este es el bug que el fix elimina."""
		quoted = f'"LOGISTICA Y TRANSPORTE MAXMEX {self.h}"'
		self.assertIn(quoted, self.names)

		r_bad = client_get_value("Customer", "fm_rfc_validated", filters=quoted)
		self.assertFalse(
			r_bad,
			"El string suelto encontró al cliente: get_safe_filters ya no muta el nombre. "
			"Si esto cambió, revalidar si el fix de filtro dict sigue siendo necesario.",
		)

		r_ok = client_get_value("Customer", "fm_rfc_validated", filters=_filters_dict(quoted))
		self.assertEqual(cint(r_ok.get("fm_rfc_validated")), 1)

	def test_string_suelto_no_afecta_nombres_no_json(self):
		"""Docnames con apóstrofo/ampersand/acentos NO son JSON válido: el string suelto los
		deja pasar. Documenta que el defecto es específico de nombres JSON-parseables."""
		for name in self.names:
			if name.lstrip().startswith('"'):
				continue  # los envueltos en comillas sí se rompen (cubierto arriba)
			r = client_get_value("Customer", "fm_rfc_validated", filters=name)
			self.assertEqual(
				cint(r.get("fm_rfc_validated")),
				1,
				f"docname no-JSON {name!r} debería resolverse aún como string suelto",
			)

	# ------------------------------------------------------------------ BORDES

	def test_cliente_no_validado_sigue_bloqueado(self):
		"""fm_rfc_validated=0 debe devolver 0 (no habilita el botón)."""
		name = self.names[0]
		frappe.db.set_value("Customer", name, "fm_rfc_validated", 0)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		r = client_get_value("Customer", "fm_rfc_validated", filters=_filters_dict(name))
		self.assertEqual(cint(r.get("fm_rfc_validated")), 0)

	def test_resultado_vacio_no_es_validado(self):
		"""Docname inexistente → {} — nunca debe interpretarse como validado."""
		r = client_get_value("Customer", "fm_rfc_validated", filters=_filters_dict(f"NO-EXISTE-{self.h}"))
		self.assertFalse(r.get("fm_rfc_validated"))

	def test_sin_tax_id_no_muestra_boton(self):
		"""Sin RFC (tax_id vacío) el flujo del botón corta antes de evaluar validación."""
		name = self.names[2]
		frappe.db.set_value("Customer", name, "tax_id", "")
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		r = client_get_value(
			"Customer", _fields_arg(["tax_id", "fm_rfc_validated"]), filters=_filters_dict(name)
		)
		self.assertFalse(r.get("tax_id"))
