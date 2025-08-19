import frappe
from frappe import _


@frappe.whitelist()
def refacturar_misma_si(si_name: str):
	"""Genera una nueva Factura Fiscal Mexico (CFDI) para el mismo Sales Invoice,
	sólo si la FFM anterior está CANCELADA fiscalmente."""
	si = frappe.get_doc("Sales Invoice", si_name)

	# Precondiciones básicas
	if si.docstatus != 1:
		frappe.throw(_("El Sales Invoice debe estar 'Submitted' (docstatus=1)."))

	ffm_name = si.get("fm_factura_fiscal_mx")
	if ffm_name:
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
		if ffm.fm_fiscal_status != "CANCELADO":
			frappe.throw(_("No puedes re-facturar: la FFM ligada no está CANCELADA fiscalmente."))

	# Invoca la ruta estándar de timbrado de TU app.
	# Intenta primero el método usual; si no existe, usa fallback.
	new_ffm = None
	try:
		# Opción 1: si tienes un generador específico
		from facturacion_mexico.facturacion_fiscal.timbrado_api import timbrar_factura  # type: ignore

		res = timbrar_factura(sales_invoice=si.name)  # ajusta firma si aplica
		# res puede ser dict o doc; normaliza:
		if isinstance(res, dict):
			new_ffm = res.get("ffm") or res.get("name")
		elif hasattr(res, "name"):
			new_ffm = res.name
	except Exception:
		# Opción 2: nombre alterno común
		try:
			from facturacion_mexico.facturacion_fiscal.timbrado_api import (
				generar_factura_fiscal,  # type: ignore
			)

			res = generar_factura_fiscal(sales_invoice=si.name)
			if isinstance(res, dict):
				new_ffm = res.get("ffm") or res.get("name")
			elif hasattr(res, "name"):
				new_ffm = res.name
		except Exception:
			frappe.log_error(frappe.get_traceback(), "refacturar_misma_si")
			frappe.throw(_("No se pudo generar la nueva FFM. Revisa logs."))

	# Asegura que el SI ahora apunte a la nueva FFM (si tu API no lo hace por sí misma)
	if new_ffm:
		try:
			si.reload()
			if si.get("fm_factura_fiscal_mx") != new_ffm:
				si.db_set("fm_factura_fiscal_mx", new_ffm, update_modified=False)
		except Exception:
			pass

	return {"ok": True, "sales_invoice": si.name, "ffm": new_ffm}
