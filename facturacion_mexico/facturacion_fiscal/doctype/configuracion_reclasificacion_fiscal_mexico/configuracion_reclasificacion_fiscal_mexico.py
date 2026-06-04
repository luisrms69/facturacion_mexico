"""
Configuracion Reclasificacion Fiscal Mexico (CRFM)

Rector de mapeos de reclasificación fiscal.

Flujo:
  1. "Cargar Reglas" → reconstruye tabla desde CFM + MRFPE existentes
  2. Usuario edita cuenta_destino en la tabla
  3. "Aplicar" → crea o actualiza MRFPE según lo que cambió
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class ConfiguracionReclasificacionFiscalMexico(Document):
	def autoname(self):
		if self.company:
			self.name = f"CRFM-{self.company}"

	@frappe.whitelist()
	def cargar_reglas(self):
		"""Reconstruye la tabla desde CFM (Cobros) y CFDI Recibidos (Pagos). Preserva cuenta_destino."""
		if not self.company:
			frappe.throw(_("Seleccione una empresa primero."))

		cfm_name = f"CFM-{self.company}"
		if not frappe.db.exists("Configuracion Fiscal Mexico", cfm_name):
			frappe.throw(_("No existe Configuración Fiscal México para {0}.").format(self.company))

		cfm = frappe.get_doc("Configuracion Fiscal Mexico", cfm_name)

		# ── Bloque 1: Cobros (Ingresos / CFM) ─────────────────────────────────
		destino_previo_cobro = {
			r.cuenta_origen: r.cuenta_destino
			for r in self.reglas
			if r.source_type == "Ingresos / CFM" and r.tipo_operacion == "Cobro"
		}
		self.reglas = [
			r for r in self.reglas if not (r.source_type == "Ingresos / CFM" and r.tipo_operacion == "Cobro")
		]

		for row in cfm.mapeo_cuentas:
			if row.estado_validacion != "Válido" or not row.cuenta_impuesto:
				continue
			mrfpe_list = frappe.get_all(
				"Mapeo Reclasificacion Fiscal Payment Entry",
				filters={
					"company": self.company,
					"tipo_operacion": "Cobro",
					"cuenta_origen": row.cuenta_impuesto,
					"activo": 1,
				},
				fields=["name", "cuenta_destino"],
				limit=1,
				ignore_permissions=True,
			)
			mrfpe = mrfpe_list[0] if mrfpe_list else None
			if mrfpe:
				cuenta_destino = mrfpe.cuenta_destino or destino_previo_cobro.get(row.cuenta_impuesto, "")
				mrfpe_ref = mrfpe.name
			else:
				cuenta_destino = destino_previo_cobro.get(row.cuenta_impuesto, "")
				mrfpe_ref = None
			self.append(
				"reglas",
				{
					"source_type": "Ingresos / CFM",
					"tipo_operacion": "Cobro",
					"rol_fiscal": row.rol_fiscal,
					"cuenta_origen": row.cuenta_impuesto,
					"cuenta_destino": cuenta_destino,
					"mrfpe_ref": mrfpe_ref,
					"nota": row.rol_fiscal,
				},
			)

		# ── Bloque 2: Pagos (Gastos / CFDI Recibidos) ─────────────────────────
		cfdi_rec_name = f"CFDI-REC-CFG-{self.company}"
		if frappe.db.exists("Configuracion CFDI Recibidos", cfdi_rec_name):
			cfdi_rec = frappe.get_doc("Configuracion CFDI Recibidos", cfdi_rec_name)

			destino_previo_pago = {
				r.cuenta_origen: r.cuenta_destino
				for r in self.reglas
				if r.source_type == "Gastos / CFDI Recibidos" and r.tipo_operacion == "Pago"
			}
			self.reglas = [
				r
				for r in self.reglas
				if not (r.source_type == "Gastos / CFDI Recibidos" and r.tipo_operacion == "Pago")
			]

			cuentas_pago_vistas = set()
			for regla in cfdi_rec.reglas_impuesto:
				if not regla.activo or not regla.cuenta_impuesto:
					continue
				if regla.cuenta_impuesto in cuentas_pago_vistas:
					continue
				cuentas_pago_vistas.add(regla.cuenta_impuesto)

				mrfpe_list = frappe.get_all(
					"Mapeo Reclasificacion Fiscal Payment Entry",
					filters={
						"company": self.company,
						"tipo_operacion": "Pago",
						"cuenta_origen": regla.cuenta_impuesto,
						"activo": 1,
					},
					fields=["name", "cuenta_destino"],
					limit=1,
					ignore_permissions=True,
				)
				mrfpe = mrfpe_list[0] if mrfpe_list else None
				if mrfpe:
					cuenta_destino = mrfpe.cuenta_destino or destino_previo_pago.get(
						regla.cuenta_impuesto, ""
					)
					mrfpe_ref = mrfpe.name
				else:
					cuenta_destino = destino_previo_pago.get(regla.cuenta_impuesto, "")
					mrfpe_ref = None
				self.append(
					"reglas",
					{
						"source_type": "Gastos / CFDI Recibidos",
						"tipo_operacion": "Pago",
						"rol_fiscal": regla.descripcion,
						"cuenta_origen": regla.cuenta_impuesto,
						"cuenta_destino": cuenta_destino,
						"mrfpe_ref": mrfpe_ref,
						"nota": regla.descripcion,
					},
				)

		self.ultima_deteccion = now_datetime()
		self.save()
		return {"message": _("{0} cuentas cargadas.").format(len(self.reglas))}

	@frappe.whitelist()
	def aplicar(self):
		"""Crea o actualiza MRFPE según cuenta_destino de cada regla."""
		if not self.company:
			frappe.throw(_("Seleccione una empresa primero."))

		creados = 0
		actualizados = 0
		sin_cambios = 0
		sin_cuenta = 0

		for regla in self.reglas:
			if not regla.cuenta_destino:
				sin_cuenta += 1
				continue

			# Buscar MRFPE por referencia directa o por filtros
			mrfpe_data = None
			if regla.mrfpe_ref:
				cd_actual = frappe.db.get_value(
					"Mapeo Reclasificacion Fiscal Payment Entry",
					regla.mrfpe_ref,
					"cuenta_destino",
				)
				if cd_actual is not None:
					mrfpe_data = frappe._dict(name=regla.mrfpe_ref, cuenta_destino=cd_actual)

			if not mrfpe_data:
				resultados = frappe.get_all(
					"Mapeo Reclasificacion Fiscal Payment Entry",
					filters={
						"company": self.company,
						"tipo_operacion": regla.tipo_operacion,
						"cuenta_origen": regla.cuenta_origen,
						"activo": 1,
					},
					fields=["name", "cuenta_destino"],
					limit=1,
					ignore_permissions=True,
				)
				mrfpe_data = resultados[0] if resultados else None

			if mrfpe_data:
				if mrfpe_data.cuenta_destino == regla.cuenta_destino:
					regla.mrfpe_ref = mrfpe_data.name
					sin_cambios += 1
				else:
					frappe.db.set_value(
						"Mapeo Reclasificacion Fiscal Payment Entry",
						mrfpe_data.name,
						"cuenta_destino",
						regla.cuenta_destino,
					)
					regla.mrfpe_ref = mrfpe_data.name
					actualizados += 1
			else:
				mrfpe = frappe.new_doc("Mapeo Reclasificacion Fiscal Payment Entry")
				mrfpe.company = self.company
				mrfpe.tipo_operacion = regla.tipo_operacion
				mrfpe.cuenta_origen = regla.cuenta_origen
				mrfpe.cuenta_destino = regla.cuenta_destino
				mrfpe.activo = 1
				mrfpe.insert(ignore_permissions=True)
				regla.mrfpe_ref = mrfpe.name
				creados += 1

		self.ultima_generacion = now_datetime()
		self.save()

		partes = []
		if creados:
			partes.append(_("Creados: {0}").format(creados))
		if actualizados:
			partes.append(_("Actualizados: {0}").format(actualizados))
		if sin_cambios:
			partes.append(_("Sin cambios: {0}").format(sin_cambios))
		if sin_cuenta:
			partes.append(_("Sin cuenta destino: {0}").format(sin_cuenta))

		return {
			"creados": creados,
			"actualizados": actualizados,
			"message": " | ".join(partes) if partes else _("Sin cambios."),
		}
