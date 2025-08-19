import frappe
from frappe import _


@frappe.whitelist()
def cancel_sales_invoice_after_ffm(si_name: str):
	"""
	Orquestador seguro para cancelación Sales Invoice post-cancelación fiscal.

	Secuencia: PAC → FFM → SI

	Args:
		si_name (str): Nombre del Sales Invoice a cancelar

	Returns:
		dict: Resultado de la operación con detalles
	"""
	try:
		# 1. VALIDACIONES PREVIAS
		si = frappe.get_doc("Sales Invoice", si_name)

		# Verificar que SI no esté ya cancelado
		if si.docstatus == 2:
			return {
				"success": True,
				"already_cancelled": True,
				"message": _("Sales Invoice ya estaba cancelado"),
			}

		# Verificar que SI esté submitted
		if si.docstatus != 1:
			frappe.throw(_("Sales Invoice debe estar submitted para cancelar"))

		# Verificar permisos
		if not frappe.has_permission("Sales Invoice", "cancel", si):
			frappe.throw(_("Sin permisos para cancelar Sales Invoice"))

		ffm_name = si.get("fm_factura_fiscal_mx")

		# 2. CASO SIN FFM: Cancelación directa
		if not ffm_name:
			si.cancel()
			return {
				"success": True,
				"direct_cancel": True,
				"message": _("Sales Invoice cancelado (sin FFM vinculada)"),
			}

		# 3. VALIDAR ESTADO FISCAL
		ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)

		if ffm.fm_fiscal_status != "CANCELADO":
			frappe.throw(
				_(
					"Secuencia incorrecta: primero cancela fiscalmente en el PAC.<br><br>"
					"<b>Pasos faltantes:</b><br>"
					"1️⃣ Ir a Factura Fiscal Mexico {0}<br>"
					"2️⃣ Usar botón 'Cancelar en FacturAPI'<br>"
					"3️⃣ Regresar aquí para cancelar Sales Invoice"
				).format(ffm_name),
				title=_("Cancelación fiscal requerida"),
			)

		# 4. SECUENCIA SEGURA: FFM → SI
		if ffm.docstatus == 1:  # FFM aún submitted
			try:
				ffm.cancel()  # Ahora permitido por hook contextual
				frappe.db.commit()
			except Exception as e:
				frappe.throw(
					_(
						"Error cancelando FFM: {0}<br><br>" "Posible causa: FFM no está cancelada fiscalmente"
					).format(str(e)),
					title=_("Error en secuencia"),
				)

		# 5. CANCELAR SALES INVOICE (nativo Frappe)
		si.cancel()
		frappe.db.commit()

		return {
			"success": True,
			"cascade_success": True,
			"ffm_cancelled": ffm_name,
			"si_cancelled": si_name,
			"message": _("Sales Invoice y FFM cancelados exitosamente"),
		}

	except Exception as e:
		frappe.db.rollback()
		frappe.log_error(f"Error en cancel_sales_invoice_after_ffm: {e!s}", "Cancel Operations Error")

		# Re-raise para mostrar error al usuario
		if isinstance(e, frappe.exceptions.ValidationError):
			raise e
		else:
			frappe.throw(
				_("Error inesperado cancelando Sales Invoice: {0}").format(e),
				title=_("Error de cancelación"),
			)


@frappe.whitelist()
def get_cancellation_status(si_name: str):
	"""
	Verificar estado de cancelación de Sales Invoice.

	Útil para UI para mostrar botones apropiados.

	Args:
		si_name (str): Nombre del Sales Invoice

	Returns:
		dict: Estado actual y opciones disponibles
	"""
	try:
		si = frappe.get_doc("Sales Invoice", si_name)

		result = {
			"si_name": si_name,
			"si_docstatus": si.docstatus,
			"si_fiscal_status": si.get("fm_fiscal_status"),
			"can_cancel_si": False,
			"can_refacturar": False,
			"ffm_info": None,
		}

		ffm_name = si.get("fm_factura_fiscal_mx")

		if ffm_name:
			ffm = frappe.get_doc("Factura Fiscal Mexico", ffm_name)
			result["ffm_info"] = {
				"name": ffm_name,
				"fiscal_status": ffm.fm_fiscal_status,
				"docstatus": ffm.docstatus,
			}

			# Si FFM cancelada fiscalmente, permitir ambas opciones
			if ffm.fm_fiscal_status == "CANCELADO" and si.docstatus == 1:
				result["can_cancel_si"] = True
				result["can_refacturar"] = True

		return result

	except Exception as e:
		frappe.log_error(f"Error en get_cancellation_status: {e!s}", "Cancellation Status Error")
		return {"error": str(e)}
