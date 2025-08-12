import frappe


def sync_ffm_summary_to_sales_invoice(ffm_doc, method=None):
	"""
	Sincronizar resumen FFM a Sales Invoice desde servidor.
	Llamar desde on_update de FFM. No toca el form abierto, solo BD.
	"""
	if not ffm_doc.sales_invoice:
		return

	try:
		# Construir valores para sincronizar
		vals = {
			"fm_ffm_estado": ffm_doc.fm_fiscal_status or "",
			"fm_ffm_numero": ffm_doc.fm_serie_folio or "",
			"fm_ffm_uuid": ffm_doc.fm_uuid or "",
			"fm_ffm_fecha": ffm_doc.fecha_timbrado,
			"fm_ffm_pac_msg": ffm_doc.fm_sync_error or "",
		}

		# Construir folio combinado si existe serie y folio por separado
		if not vals["fm_ffm_numero"] and ffm_doc.serie and ffm_doc.folio:
			vals["fm_ffm_numero"] = f"{ffm_doc.serie}-{ffm_doc.folio}"

		# Actualizar Sales Invoice sin modificar timestamp
		# allow_on_submit=1 permite actualizar después de submit
		# update_modified=False evita cambiar indicador visual
		frappe.db.set_value("Sales Invoice", ffm_doc.sales_invoice, vals, update_modified=False)

		frappe.logger().info(
			f"FFM Summary sincronizado a Sales Invoice {ffm_doc.sales_invoice} " f"desde FFM {ffm_doc.name}"
		)

	except Exception as e:
		frappe.logger().error(
			f"Error sincronizando FFM summary a Sales Invoice: "
			f"FFM={ffm_doc.name}, SI={ffm_doc.sales_invoice}, Error={e}"
		)
		# No lanzar error para no bloquear el save de FFM
