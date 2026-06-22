"""Prueba estática del botón 'Verificar estado en FacturAPI' (Paso 5).

Verifica el contrato del botón de reconciliación manual en el JS del FFM: texto, grupo, guardas
de visibilidad, método servidor, payload, recarga, y que NO contenga lógica fiscal (timbrado,
cancelación, escritura de campos). Es estática: lee el archivo, no ejecuta JS ni abre formularios.
"""

import os
import re
import unittest

APP_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FFM_JS = os.path.join(
	APP_ROOT, "facturacion_fiscal", "doctype", "factura_fiscal_mexico", "factura_fiscal_mexico.js"
)

_LABEL = "Verificar estado en FacturAPI"
_METHOD = "facturacion_mexico.facturacion_fiscal.services.ffm_reconciliation.reconcile_ffm"


def _strip_js_line_comments(source: str) -> str:
	"""Solo líneas de código (descarta comentarios `//`), para evaluar código ejecutable."""
	return "\n".join(line for line in source.splitlines() if not line.strip().startswith("//"))


class TestReconciliationButton(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		with open(FFM_JS, encoding="utf-8") as fh:
			cls.raw = fh.read()
		cls.code = _strip_js_line_comments(cls.raw)
		# Bloque del botón: desde su etiqueta hasta el cierre con el grupo "Comprobantes".
		start = cls.code.index(_LABEL)
		end = cls.code.index('Comprobantes")', start) + len('Comprobantes")')
		cls.block = cls.code[start:end]

	# 1 — existe el texto
	def test_existe_texto(self):
		self.assertIn(_LABEL, self.code)

	# 2 — pertenece al grupo Comprobantes
	def test_grupo_comprobantes(self):
		self.assertRegex(self.block, r'__\(\s*"Comprobantes"\s*\)\s*$')

	# 3 y 4 — exige documento guardado y facturapi_id (guarda de visibilidad)
	def test_guarda_guardado_y_facturapi_id(self):
		self.assertIn("!frm.is_new() && frm.doc.facturapi_id", self.code)
		# La guarda precede a la creación del botón.
		self.assertLess(self.code.index("!frm.is_new() && frm.doc.facturapi_id"), self.code.index(_LABEL))

	# 5 — llama exactamente a reconcile_ffm
	def test_llama_reconcile_ffm(self):
		self.assertIn(_METHOD, self.block)

	# 6 — envía ffm_name: frm.doc.name
	def test_payload_ffm_name(self):
		self.assertRegex(self.block, r"ffm_name:\s*frm\.doc\.name")

	# 7 — recarga el documento tras la consulta
	def test_recarga_documento(self):
		self.assertIn("frm.reload_doc()", self.block)

	# congelar interfaz / evitar doble clic
	def test_freeze_activo(self):
		self.assertIn("freeze: true", self.block)

	# 8 — sin llamadas a timbrado, cancelación ni cancelación de Sales Invoice
	def test_sin_timbrado_ni_cancelacion(self):
		prohibidos = ("timbrar", "create_invoice", "cancel_invoice", "cancelar", "cancel_ffm")
		for p in prohibidos:
			self.assertNotIn(p, self.block.lower(), f"El bloque no debe contener '{p}'")

	# 9 — no escribe campos fiscales directamente
	def test_no_escribe_campos_fiscales(self):
		for p in ("set_value", "db_set", "fm_sync_status", '"status"', "'status'"):
			self.assertNotIn(p, self.block, f"El bloque no debe escribir '{p}'")
		# Tampoco debe interpretar el estado remoto.
		for p in ("cancellation_status", "status ==", "status==="):
			self.assertNotIn(p, self.block, f"El bloque no debe interpretar '{p}'")

	# referencia: el método servidor existe en su módulo
	def test_metodo_servidor_existe(self):
		svc = os.path.join(APP_ROOT, "facturacion_fiscal", "services", "ffm_reconciliation.py")
		with open(svc, encoding="utf-8") as fh:
			self.assertTrue(re.search(r"def\s+reconcile_ffm\s*\(", fh.read()))
