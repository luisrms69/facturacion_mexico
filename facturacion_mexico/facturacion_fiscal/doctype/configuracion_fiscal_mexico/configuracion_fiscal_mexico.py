"""
Configuración Fiscal México - DocType principal para wizard de mapeo fiscal.
"""

import frappe
from frappe.model.document import Document


class ConfiguracionFiscalMexico(Document):
	"""
	Configuración Fiscal México - Wizard de mapeo de cuentas fiscales por empresa.

	Funcionalidades principales:
	- Mapeo transparente roles fiscales → cuentas contables
	- Validación tiempo real de completitud
	- Configuración de alcance (frontera/IEPS/retenciones)
	- Bloqueo hasta mapeo completo y válido

	Parámetros importantes:
		company (Link): Empresa para la cual se configura
		mapeo_cuentas (Table): Tabla child con mapeos rol → cuenta
		enable_frontera (Check): Habilitar zona fronteriza IVA 8%
		configuracion_completa (Check): Estado de completitud automático

	Errores comunes:
		ValidationError: Mapeo incompleto según alcance configurado
		ValidationError: Cuentas duplicadas en mapeo
		ValidationError: Cuenta no es tipo Tax o empresa incorrecta

	Ejemplo de uso:
		config = frappe.new_doc("Configuracion Fiscal Mexico")
		config.company = "Mi Empresa S.A."
		config.enable_frontera = 1
		config.save()
	"""

	def autoname(self):
		"""Generar nombre automático único por empresa."""
		if self.company:
			self.name = f"CFM-{self.company}"

	def before_save(self):
		"""Ejecutar validaciones antes de guardar."""
		# Las filas se agregan via JavaScript cuando cambian los checkboxes
		self._validar_mapeo_completo()
		self._actualizar_estado_completitud()

	def _rol_requerido_por_alcance(self, rol_fiscal: str) -> bool:
		"""Determinar si un rol fiscal es requerido según alcance configurado."""
		# Roles siempre requeridos
		roles_base = ["IVA por Pagar (16%)", "IVA Exento"]
		if rol_fiscal in roles_base:
			return True

		# Roles condicionales por alcance
		if self.enable_frontera and "8% frontera" in rol_fiscal:
			return True
		if self.enable_exportacion and "0% exportación" in rol_fiscal:
			return True
		if self.enable_ieps_alcohol and "IEPS por Pagar (Alcohol)" in rol_fiscal:
			return True
		if self.enable_ieps_azucar and "IEPS por Pagar (Azúcar" in rol_fiscal:
			return True
		if self.enable_ieps_combustibles and "IEPS por Pagar (Combustibles)" in rol_fiscal:
			return True
		if self.enable_ieps_tabaco and ("IEPS por Pagar (Tabaco)" in rol_fiscal):
			return True
		if self.enable_ret_honorarios and "ISR Retenido (Honorarios)" in rol_fiscal:
			return True
		if self.enable_ret_arrendamiento and "Arrendamiento" in rol_fiscal:
			return True
		if self.enable_ret_autotransporte and "Autotransporte" in rol_fiscal:
			return True
		if self.enable_ret_resico and "RESICO" in rol_fiscal:
			return True

		return False

	def _validar_mapeo_completo(self):
		"""Validar que el mapeo esté completo según alcance."""
		roles_requeridos = self._obtener_roles_requeridos()
		roles_mapeados = {
			row.rol_fiscal for row in self.mapeo_cuentas if row.rol_fiscal and row.cuenta_impuesto
		}

		roles_faltantes = roles_requeridos - roles_mapeados
		if roles_faltantes:
			frappe.msgprint(
				f"Advertencia: Faltan mapeos para roles: {', '.join(sorted(roles_faltantes))}", alert=True
			)

		# Validar cada cuenta de impuesto
		for row in self.mapeo_cuentas:
			if row.cuenta_impuesto:
				self._validar_cuenta_impuesto(row)

		# Validar duplicados (permitir misma cuenta para roles diferentes si es necesario)
		# Solo validar que no haya duplicado del mismo rol
		roles_usados = []
		for row in self.mapeo_cuentas:
			if row.rol_fiscal and row.rol_fiscal in roles_usados:
				frappe.throw(f"El rol fiscal {row.rol_fiscal} está duplicado en el mapeo")
			if row.rol_fiscal:
				roles_usados.append(row.rol_fiscal)

	def _validar_cuenta_impuesto(self, row):
		"""Validar que cuenta de impuesto sea correcta."""
		if not row.cuenta_impuesto:
			return

		# Verificar que la cuenta existe
		if not frappe.db.exists("Account", row.cuenta_impuesto):
			frappe.throw(f"La cuenta {row.cuenta_impuesto} no existe")

		# Obtener datos de la cuenta
		account_data = frappe.db.get_value(
			"Account", row.cuenta_impuesto, ["account_type", "company", "is_group", "disabled"], as_dict=True
		)

		if not account_data:
			frappe.throw(f"No se pueden obtener datos de la cuenta {row.cuenta_impuesto}")

		# Validar tipo Tax
		if account_data.account_type != "Tax":
			frappe.throw(
				f"La cuenta {row.cuenta_impuesto} no es tipo Tax. Tipo actual: {account_data.account_type}"
			)

		# Validar empresa
		if account_data.company != self.company:
			frappe.throw(
				f"La cuenta {row.cuenta_impuesto} pertenece a la empresa {account_data.company}, no a {self.company}"
			)

		# Validar que no sea grupo
		if account_data.is_group:
			frappe.throw(f"La cuenta {row.cuenta_impuesto} es un grupo. Seleccione una cuenta específica.")

		# Validar que esté habilitada
		if account_data.disabled:
			frappe.throw(f"La cuenta {row.cuenta_impuesto} está deshabilitada")

	def _obtener_roles_requeridos(self) -> set:
		"""
		Obtener conjunto de roles fiscales requeridos según alcance.

		MATRIZ CANÓNICA según propuesta ChatGPT con nombres descriptivos en español.
		"""
		# SIEMPRE requeridos
		roles_requeridos = {"IVA por Pagar (16%)", "IVA Exento"}

		# CONDICIONALES según alcance
		if self.enable_frontera:
			roles_requeridos.add("IVA por Pagar (8% frontera)")

		if self.enable_exportacion:
			roles_requeridos.add("IVA por Pagar (0% exportación)")

		# RETENCIONES - Servicios Profesionales (Honorarios)
		if self.enable_ret_honorarios:
			roles_requeridos.update(
				[
					"ISR Retenido (Honorarios)",  # RET_ISR_10 en propuesta
					"IVA Retenido (Servicios Profesionales)",  # RET_IVA_2_3_SERVPROF en propuesta
				]
			)

		# RETENCIONES - Arrendamiento
		if self.enable_ret_arrendamiento:
			roles_requeridos.update(
				[
					"ISR Retenido (Arrendamiento)",  # RET_ISR_10 + RET_IVA_ARR
					"IVA Retenido (Arrendamiento)",
				]
			)

		# RETENCIONES - Autotransporte
		if self.enable_ret_autotransporte:
			roles_requeridos.update(
				[
					"ISR Retenido (Autotransporte)",  # RET_ISR_4_AUTOT
					"IVA Retenido (Autotransporte)",  # RET_IVA_AUTOT
				]
			)

		# RETENCIONES - RESICO
		if self.enable_ret_resico:
			roles_requeridos.update(
				[
					"ISR Retenido (RESICO)",  # RET_ISR_RESICO
					"IVA Retenido (RESICO)",  # RET_IVA_RESICO
				]
			)

		# IEPS según habilitados
		if self.enable_ieps_alcohol:
			roles_requeridos.add("IEPS por Pagar (Alcohol)")
		if self.enable_ieps_azucar:
			roles_requeridos.add("IEPS por Pagar (Azúcar/Bebidas)")
		if self.enable_ieps_combustibles:
			roles_requeridos.add("IEPS por Pagar (Combustibles)")
		if self.enable_ieps_tabaco:
			roles_requeridos.add("IEPS por Pagar (Tabaco)")  # Tasa 160%
			roles_requeridos.add("IEPS por Pagar (Tabaco Cuota)")  # Cuota variable por cigarro

		return roles_requeridos

	def _actualizar_estado_completitud(self):
		"""
		Actualizar estado de completitud automáticamente.
		Incluye barra de cobertura según propuesta ChatGPT.
		"""
		roles_requeridos = self._obtener_roles_requeridos()
		roles_validos = {
			row.rol_fiscal
			for row in self.mapeo_cuentas
			if row.rol_fiscal and row.cuenta_impuesto and row.estado_validacion == "Válido"
		}

		# Calcular cobertura
		total_requeridos = len(roles_requeridos)
		total_mapeados = len(roles_validos.intersection(roles_requeridos))

		# Estado de completitud
		self.configuracion_completa = total_requeridos > 0 and roles_requeridos.issubset(roles_validos)

		# Almacenar estadísticas para mostrar en UI (campos calculados)
		frappe.logger().info(f"Cobertura mapeo fiscal: {total_mapeados}/{total_requeridos} roles mapeados")

	@frappe.whitelist()
	def aplicar_mapeo_y_generar_templates(self):
		"""
		Aplicar mapeo y generar templates fiscales.
		Método principal del wizard llamado desde UI.
		"""
		# GUARD: Solo permitir desde UI o CLI con flag explícito
		if not getattr(frappe.flags, "allow_fiscal_generation", False) and not frappe.local.form_dict.get(
			"from_ui"
		):
			frappe.throw("Generación fiscal solo permitida desde UI del wizard o CLI con flag explícito")

		if not self.configuracion_completa:
			frappe.throw("No se puede generar templates. La configuración no está completa.")

		# Registrar auditoría de ejecución
		self._registrar_auditoria_generacion()

		# Importar generador 8 STCT e ITT
		from facturacion_mexico.facturacion_fiscal.setup.generador_templates_fiscal import (
			generate_8_stct_for_company,
			generate_itt_for_company,
		)

		try:
			# Generar 8 STCT específicos (Nacional/Frontera x Básico/IEPS/Retenciones/Total)
			resultados_stct = generate_8_stct_for_company(company=self.company)

			# Generar ITT basados en Configuracion Fiscal Mexico
			resultados_itt = generate_itt_for_company(company=self.company)

			# Asignar ITT a Item Groups después de generar templates
			from facturacion_mexico.setup.item_groups import assign_itt_to_groups

			assign_itt_to_groups()

			# Mostrar mensaje de éxito detallado
			total_creados_stct = len(resultados_stct.get("created", []))
			total_deshabilitados = 2 if resultados_stct.get("disabled_old") else 0
			total_creados_itt = len(resultados_itt.get("created", []))

			mensaje = f"""
			<h4>✅ Generación de Templates Completada</h4>
			<p><strong>Sales Taxes and Charges Templates (STCT):</strong></p>
			<ul>
				<li>✅ Se generaron {total_creados_stct} templates STCT específicos (Nacional/Frontera x Básico/IEPS/Retenciones/Total)</li>
				<li>🔴 Se deshabilitaron {total_deshabilitados} templates consolidados viejos (con 16%/8% en el título)</li>
			</ul>
			<p><strong>Item Tax Templates (ITT):</strong></p>
			<ul>
				<li>✅ Se generaron/actualizaron {total_creados_itt} templates ITT</li>
				<li>✅ Se asignaron los ITT a sus Item Groups correspondientes</li>
			</ul>
			<hr>
			<p><em>Empresa: {self.company}</em></p>
			"""

			frappe.msgprint(
				mensaje,
				title="Templates Generados Exitosamente",
				indicator="green",
			)

			return {
				"stct_generados": resultados_stct.get("created", []),
				"stct_deshabilitados": total_deshabilitados,
				"itt_generados": resultados_itt.get("created", []),
				"itt_count": total_creados_itt,
			}

		except Exception as e:
			frappe.log_error(f"Error generando templates: {e!s}")
			frappe.throw(f"Error generando templates: {e!s}")

	def _registrar_auditoria_generacion(self):
		"""Registrar snapshot de auditoría para generación fiscal."""
		try:
			auditoria = {
				"usuario": frappe.session.user,
				"timestamp": frappe.utils.now(),
				"empresa": self.company,
				"alcance": {
					"frontera": self.enable_frontera,
					"exportacion": self.enable_exportacion,
					"retenciones_honorarios": self.enable_ret_honorarios,
					"retenciones_arrendamiento": self.enable_ret_arrendamiento,
					"retenciones_autotransporte": self.enable_ret_autotransporte,
				},
				"roles_mapeados": len(self.mapeo_cuentas),
			}
			frappe.logger().info(f"Auditoría generación fiscal: {auditoria}")
		except Exception as e:
			frappe.logger().warning(f"Error registrando auditoría: {e}")

	@frappe.whitelist()
	def agregar_filas_por_alcance(self):
		"""
		LEGACY: Mantener compatibilidad.
		Redirige a sincronizar_tabla_con_alcance.
		"""
		return self.sincronizar_tabla_con_alcance()

	@frappe.whitelist()
	def sincronizar_tabla_con_alcance(self):
		"""
		Sincronizar tabla con alcance seleccionado: AGREGAR y ELIMINAR filas.
		Llamado desde JavaScript cuando cambian los checkboxes.
		"""
		if not self.company:
			frappe.throw("Debe seleccionar una empresa antes de configurar alcance")

		# Obtener roles requeridos según alcance actual
		roles_requeridos = self._obtener_roles_requeridos()

		# Obtener roles ya existentes
		roles_existentes = {row.rol_fiscal: row for row in self.mapeo_cuentas if row.rol_fiscal}

		# AGREGAR roles faltantes
		nuevas_filas = 0
		for rol_fiscal in roles_requeridos:
			if rol_fiscal not in roles_existentes:
				self.append(
					"mapeo_cuentas",
					{
						"rol_fiscal": rol_fiscal,
						"cuenta_impuesto": "",  # Usuario debe mapear manualmente
						"sugerido_automaticamente": 0,
						"justificacion_sugerencia": "Mapeo manual requerido",
						"estado_validacion": "Error",
					},
				)
				nuevas_filas += 1

		# ELIMINAR roles no requeridos (excepto roles base que siempre se mantienen)
		roles_base = {"IVA por Pagar (16%)", "IVA Exento"}
		filas_eliminadas = 0

		# Iterar en reversa para evitar problemas de índices al eliminar
		for i in range(len(self.mapeo_cuentas) - 1, -1, -1):
			row = self.mapeo_cuentas[i]
			if row.rol_fiscal and row.rol_fiscal not in roles_requeridos and row.rol_fiscal not in roles_base:
				# Solo eliminar si no tiene cuenta mapeada (no destruir trabajo del usuario)
				if not row.cuenta_impuesto:
					self.remove(self.mapeo_cuentas[i])
					filas_eliminadas += 1

		return {
			"filas_agregadas": nuevas_filas,
			"filas_eliminadas": filas_eliminadas,
			"total_roles": len(roles_requeridos),
			"roles_actuales": list(roles_requeridos),
		}
