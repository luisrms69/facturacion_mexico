"""
Generador de Templates Fiscales México - Adaptador del motor install.py con mapeo de cuentas.
Reemplaza hardcodes por mapeo real de cuentas específicas por empresa.
"""

from typing import Optional

import frappe
from frappe.utils import flt

from facturacion_mexico.facturacion_fiscal.config.constantes_fiscales import (
	ITT_TEMPLATES,
	MAPEO_ROLES_CONFIGURACION,
	STCT_TEMPLATES,
	TAX_CATEGORIES,
	es_impuesto_cascada,
	obtener_configuracion_por_rol,
)


class GeneradorTemplatesFiscales:
	"""
	Adaptador del motor fiscal existente para usar mapeo de cuentas específico.

	Funcionalidades principales:
	- Genera STCT usando cuentas mapeadas (no hardcode)
	- Genera ITT con tax_type coincidente exacto
	- Genera Tax Rules por Tax Category
	- Operación idempotente (actualiza sin duplicar)
	- Metadata managed_by para trazabilidad
	"""

	def __init__(self, company: str):
		self.company = company
		self.company_abbr = frappe.get_value("Company", company, "abbr")
		self.config_fiscal = self._obtener_configuracion_fiscal()

	def _obtener_configuracion_fiscal(self):
		"""Obtener configuración fiscal de la empresa."""
		config_name = frappe.get_value("Configuracion Fiscal Mexico", {"company": self.company}, "name")
		if not config_name:
			frappe.throw(
				f"No existe configuración fiscal para empresa {self.company}. Crear primero la configuración."
			)
		return frappe.get_doc("Configuracion Fiscal Mexico", config_name)

	def _obtener_mapeo_cuentas(self) -> dict[str, str]:
		"""Convertir mapeo de cuentas a diccionario rol → cuenta."""
		mapeo = {}
		for row in self.config_fiscal.mapeo_cuentas:
			if row.rol_fiscal and row.cuenta_impuesto:
				mapeo[row.rol_fiscal] = row.cuenta_impuesto
		return mapeo

	def generar_templates_completos(self) -> dict:
		"""
		Generar templates completos basado en configuración y mapeo.

		Returns:
			Dict con resultados de generación
		"""
		mapeo_cuentas = self._obtener_mapeo_cuentas()
		self._validar_mapeo_completo(mapeo_cuentas)

		# Crear Tax Categories necesarias primero
		self._crear_tax_categories()

		resultados = {
			"stct_generados": self._generar_stct(mapeo_cuentas),
			"itt_generados": self._generar_itt(mapeo_cuentas),
			# "tax_rules_generados": self._generar_tax_rules(),  # << removido (se hará en E1)
			"company": self.company,
			"timestamp": frappe.utils.now(),
			"version_esquema": self.config_fiscal.version_esquema,
		}

		# Actualizar estado configuración
		self._actualizar_estado_configuracion(resultados)

		return resultados

	def _validar_mapeo_completo(self, mapeo_cuentas: dict[str, str]):
		"""Validar que el mapeo tenga roles mínimos requeridos."""
		roles_minimos = ["IVA por Pagar (16%)", "IVA Exento"]

		# Agregar roles según alcance configurado
		if self.config_fiscal.enable_frontera:
			roles_minimos.append("IVA por Pagar (8% frontera)")
		if self.config_fiscal.enable_exportacion:
			roles_minimos.append("IVA por Pagar (0% exportación)")

		roles_faltantes = [rol for rol in roles_minimos if rol not in mapeo_cuentas]
		if roles_faltantes:
			frappe.throw(f"Faltan mapeos para roles obligatorios: {', '.join(roles_faltantes)}")

	def _crear_tax_categories(self):
		"""Crear Tax Categories necesarias para Tax Rules."""
		# Categories base siempre necesarias
		categories = ["General 16", "Zero 0", "Exempt"]

		# Categories condicionales según alcance
		if self.config_fiscal.enable_frontera:
			categories.append("Border 8")

		# Categories IEPS
		if self.config_fiscal.enable_ieps_alcohol:
			categories.append("IEPS Alcohol")
		if self.config_fiscal.enable_ieps_azucar:
			categories.append("IEPS Azucar")
		if self.config_fiscal.enable_ieps_combustibles:
			categories.append("IEPS Combustibles")
		if self.config_fiscal.enable_ieps_tabaco:
			categories.append("IEPS Tabaco")

		# Categories Retenciones
		if self.config_fiscal.enable_ret_honorarios:
			categories.append("Retenciones Honorarios")
		if self.config_fiscal.enable_ret_arrendamiento:
			categories.append("Retenciones Arrendamiento")
		if self.config_fiscal.enable_ret_autotransporte:
			categories.append("Retenciones Autotransporte")

		# Crear todas las categories necesarias
		for category in categories:
			if not frappe.db.exists("Tax Category", category):
				tax_cat = frappe.get_doc({"doctype": "Tax Category", "name": category, "title": category})
				tax_cat.insert(ignore_permissions=True)

	def _obtener_stct_opcion_b(self) -> list[dict]:
		"""
		Genera STCT consolidado (Opción B):
		- Pares IEPS_t + IVA sobre IEPS_t (contiguos)
		- IVA base (sobre neto)
		- Retenciones (Deduct)
		- IVA 0% y Exento (para mixto E1)
		Sin tax_category.
		"""
		# Detectar roles IEPS definidos en constantes (granulares)
		IEPS_TIPOS = [rol for rol in MAPEO_ROLES_CONFIGURACION.keys() if rol.startswith("IEPS por Pagar")]

		templates = []

		# ---------- IVA 16% ----------
		taxes_16 = []
		for rol_ieps in IEPS_TIPOS:
			# (1) IEPS tipo (rate 0; la tasa real llega por ITT del ítem)
			taxes_16.append(
				{
					"rol_fiscal": rol_ieps,
					"charge_type": "On Net Total",
					"rate": 0.0,
					"add_deduct_tax": "Add",
					"description": f"IEPS {rol_ieps.split('(')[1].rstrip(')')} - tasa via ITT",
				}
			)
			# (2) IVA 16% sobre IEPS tipo (cascada explícita)
			taxes_16.append(
				{
					"rol_fiscal": "IVA por Pagar (16%)",
					"charge_type": "On Previous Row Amount",
					"rate": 16.0,
					"add_deduct_tax": "Add",
					"description": f"IVA 16% sobre IEPS {rol_ieps.split('(')[1].rstrip(')')}",
				}
			)

		# (3) IVA 16% base (sobre neto)
		taxes_16.append(
			{
				"rol_fiscal": "IVA por Pagar (16%)",
				"charge_type": "On Net Total",
				"rate": 16.0,
				"add_deduct_tax": "Add",
				"description": "IVA 16% base (neto)",
			}
		)

		# (4) Retenciones (rate 0; la tasa real via ITT de cada ítem/servicio)
		taxes_16.append(
			{
				"rol_fiscal": "IVA Retenido (Servicios Profesionales)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Deduct",
				"description": "Retención IVA (servicios), tasa via ITT",
			}
		)
		taxes_16.append(
			{
				"rol_fiscal": "ISR Retenido (Honorarios)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Deduct",
				"description": "Retención ISR (honorarios), tasa via ITT",
			}
		)

		# (5) Mixto E1: 0% y Exento (neutralizan IVA por ítem vía ITT)
		taxes_16.append(
			{
				"rol_fiscal": "IVA por Pagar (0% exportación)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Add",
				"description": "IVA 0% - neutraliza IVA por ítem (E1 ITT 0%)",
			}
		)
		taxes_16.append(
			{
				"rol_fiscal": "IVA Exento",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Add",
				"description": "IVA Exento - neutraliza IVA por ítem (E1 ITT Exento)",
			}
		)

		templates.append(
			{
				"title": STCT_TEMPLATES.get("iva_general", "IVA 16% - México"),
				"is_default": 0,
				"taxes": taxes_16,
			}
		)

		# ---------- IVA 8% Frontera ----------
		taxes_8 = []
		for rol_ieps in IEPS_TIPOS:
			taxes_8.append(
				{
					"rol_fiscal": rol_ieps,
					"charge_type": "On Net Total",
					"rate": 0.0,
					"add_deduct_tax": "Add",
					"description": f"IEPS {rol_ieps.split('(')[1].rstrip(')')} - tasa via ITT",
				}
			)
			taxes_8.append(
				{
					"rol_fiscal": "IVA por Pagar (8% frontera)",
					"charge_type": "On Previous Row Amount",
					"rate": 8.0,
					"add_deduct_tax": "Add",
					"description": f"IVA 8% sobre IEPS {rol_ieps.split('(')[1].rstrip(')')}",
				}
			)

		taxes_8.append(
			{
				"rol_fiscal": "IVA por Pagar (8% frontera)",
				"charge_type": "On Net Total",
				"rate": 8.0,
				"add_deduct_tax": "Add",
				"description": "IVA 8% frontera base (neto)",
			}
		)

		taxes_8.append(
			{
				"rol_fiscal": "IVA Retenido (Servicios Profesionales)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Deduct",
				"description": "Retención IVA (servicios), tasa via ITT",
			}
		)
		taxes_8.append(
			{
				"rol_fiscal": "ISR Retenido (Honorarios)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Deduct",
				"description": "Retención ISR (honorarios), tasa via ITT",
			}
		)

		taxes_8.append(
			{
				"rol_fiscal": "IVA por Pagar (0% exportación)",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Add",
				"description": "IVA 0% - neutraliza IVA por ítem (E1 ITT 0%)",
			}
		)
		taxes_8.append(
			{
				"rol_fiscal": "IVA Exento",
				"charge_type": "On Net Total",
				"rate": 0.0,
				"add_deduct_tax": "Add",
				"description": "IVA Exento - neutraliza IVA por ítem (E1 ITT Exento)",
			}
		)

		templates.append(
			{
				"title": STCT_TEMPLATES.get("iva_frontera", "IVA 8% Frontera - México"),
				"is_default": 0,
				"taxes": taxes_8,
			}
		)

		return templates

	def _generar_stct(self, mapeo_cuentas: dict[str, str]) -> list[str]:
		"""Generar Sales Taxes and Charges Templates usando Opción B (consolidado)."""
		stct_generados = []

		# OPCIÓN B: STCT consolidados (IVA 16% + IVA 8% Frontera)
		# Cada uno con: IEPS granular + retenciones + mixto E1
		stct_configs = self._obtener_stct_opcion_b()

		# Generar cada template
		for template_config in stct_configs:
			stct_name = self._crear_o_actualizar_stct(template_config, mapeo_cuentas)
			stct_generados.append(stct_name)

		return stct_generados

	# ============================================================================
	# FUNCIONES OBSOLETAS ELIMINADAS (Opción B reemplaza arquitectura separada)
	# - _obtener_templates_iva_base() → eliminada
	# - _obtener_templates_ieps_cascada() → eliminada
	# - _obtener_templates_retenciones() → eliminada
	# ============================================================================

	def _crear_o_actualizar_stct(self, template_config: dict, mapeo_cuentas: dict[str, str]) -> str:
		"""Crear o actualizar un Sales Taxes and Charges Template."""
		title = f"{template_config['title']} - {self.company_abbr}"

		# Buscar existente
		existing = frappe.db.exists(
			"Sales Taxes and Charges Template", {"title": title, "company": self.company}
		)

		if existing:
			doc = frappe.get_doc("Sales Taxes and Charges Template", existing)

			# FIX: Normalizar name si tiene doble sufijo (name != title)
			if doc.name != title:
				frappe.rename_doc("Sales Taxes and Charges Template", doc.name, title, force=1)
				doc = frappe.get_doc("Sales Taxes and Charges Template", title)  # Recargar después de rename

			doc.taxes = []  # limpiar para rearmar
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Sales Taxes and Charges Template",
					"name": title,  # ← name fijo = title (evita doble sufijo)
					"title": title,
					"company": self.company,
					"is_default": template_config.get("is_default", 0),
				}
			)
			doc.taxes = []

		# Solo agregar tax_category si no está vacía (evitar problemas con templates sin categoria)
		if template_config.get("tax_category"):
			doc.tax_category = template_config.get("tax_category")

		# Agregar filas de impuestos
		for idx, tax_config in enumerate(template_config.get("taxes", []), start=1):
			rol_fiscal = tax_config["rol_fiscal"]
			cuenta_impuesto = mapeo_cuentas.get(rol_fiscal)

			if not cuenta_impuesto:
				frappe.msgprint(f"No se encontró cuenta para rol {rol_fiscal}, omitiendo...")
				continue

			charge_type = tax_config.get("charge_type", "On Net Total")

			tax_row = {
				"charge_type": charge_type,
				"account_head": cuenta_impuesto,
				"rate": flt(tax_config.get("rate", 0.0)),
				"description": tax_config.get("description", rol_fiscal),
				"add_deduct_tax": tax_config.get("add_deduct_tax", "Add"),
				"idx": idx,
			}

			if charge_type in ("On Previous Row Amount", "On Previous Row Total") and idx > 1:
				tax_row["row_id"] = str(idx - 1)  # referencia a la fila inmediatamente anterior

			doc.append("taxes", tax_row)

		# guardar
		if existing:
			doc.save(ignore_permissions=True)
		else:
			doc.insert(ignore_permissions=True)

		return doc.name

	def _generar_itt(self, mapeo_cuentas: dict[str, str]) -> list[str]:
		"""Generar Item Tax Templates usando constantes centralizadas."""
		itt_generados = []

		# ITT Base - IVA
		itt_configs = self._obtener_itt_base()

		# ITT IEPS - Según alcance
		itt_configs.extend(self._obtener_itt_ieps())

		# ITT Retenciones - Según alcance
		itt_configs.extend(self._obtener_itt_retenciones())

		for config in itt_configs:
			itt_name = self._crear_o_actualizar_itt(config, mapeo_cuentas)
			itt_generados.append(itt_name)
		return itt_generados

	def _obtener_itt_base(self) -> list[dict]:
		"""Obtener ITT base para IVA."""
		configs = []

		# ITT IVA 16%
		iva_general_config = obtener_configuracion_por_rol("IVA por Pagar (16%)")
		configs.append(
			{
				"title": ITT_TEMPLATES["iva_general"],
				"taxes": [{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": iva_general_config["tasa"]}],
			}
		)

		# ITT IVA 0% - Con 3 entradas para mixto (propuesta ChatGPT)
		configs.append(
			{
				"title": ITT_TEMPLATES["iva_exportacion"],
				"taxes": [
					{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 0},
					{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 0},
					{"rol_fiscal": "IVA por Pagar (0% exportación)", "tax_rate": 0},
				],
			}
		)

		# ITT Exento - Con 3 entradas para mixto (propuesta ChatGPT)
		configs.append(
			{
				"title": ITT_TEMPLATES["exento"],
				"taxes": [
					{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 0},
					{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 0},
					{"rol_fiscal": "IVA Exento", "tax_rate": 0},
				],
			}
		)

		# ITT IVA Frontera 8%
		if self.config_fiscal.enable_frontera:
			iva_frontera_config = obtener_configuracion_por_rol("IVA por Pagar (8% frontera)")
			configs.append(
				{
					"title": ITT_TEMPLATES["iva_frontera"],
					"taxes": [
						{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": iva_frontera_config["tasa"]}
					],
				}
			)

		return configs

	def _obtener_itt_ieps(self) -> list[dict]:
		"""Obtener ITT para IEPS según alcance."""
		configs = []

		# ITT IEPS Alcohol
		if self.config_fiscal.enable_ieps_alcohol:
			ieps_config = obtener_configuracion_por_rol("IEPS por Pagar (Alcohol)")
			configs.append(
				{
					"title": "ITT IEPS Alcohol",
					"taxes": [{"rol_fiscal": "IEPS por Pagar (Alcohol)", "tax_rate": ieps_config["tasa"]}],
				}
			)

		# ITT IEPS Azúcar
		if self.config_fiscal.enable_ieps_azucar:
			ieps_config = obtener_configuracion_por_rol("IEPS por Pagar (Azúcar/Bebidas)")
			configs.append(
				{
					"title": "ITT IEPS Azúcar",
					"taxes": [
						{"rol_fiscal": "IEPS por Pagar (Azúcar/Bebidas)", "tax_rate": ieps_config["tasa"]}
					],
				}
			)

		# ITT IEPS Combustibles
		if self.config_fiscal.enable_ieps_combustibles:
			ieps_config = obtener_configuracion_por_rol("IEPS por Pagar (Combustibles)")
			configs.append(
				{
					"title": "ITT IEPS Combustibles",
					"taxes": [
						{"rol_fiscal": "IEPS por Pagar (Combustibles)", "tax_rate": ieps_config["tasa"]}
					],
				}
			)

		# ITT IEPS Tabaco
		if self.config_fiscal.enable_ieps_tabaco:
			ieps_config = obtener_configuracion_por_rol("IEPS por Pagar (Tabaco)")
			configs.append(
				{
					"title": "ITT IEPS Tabaco",
					"taxes": [{"rol_fiscal": "IEPS por Pagar (Tabaco)", "tax_rate": ieps_config["tasa"]}],
				}
			)

		return configs

	def _obtener_itt_retenciones(self) -> list[dict]:
		"""Obtener ITT para retenciones según alcance."""
		configs = []

		# ITT Retenciones Honorarios
		if self.config_fiscal.enable_ret_honorarios:
			isr_config = obtener_configuracion_por_rol("ISR Retenido (Honorarios)")
			iva_config = obtener_configuracion_por_rol("IVA Retenido (Servicios Profesionales)")
			configs.extend(
				[
					{
						"title": "ITT ISR Honorarios",
						"taxes": [
							{"rol_fiscal": "ISR Retenido (Honorarios)", "tax_rate": isr_config["tasa"]}
						],
					},
					{
						"title": "ITT IVA Retenido Servicios",
						"taxes": [
							{
								"rol_fiscal": "IVA Retenido (Servicios Profesionales)",
								"tax_rate": iva_config["tasa"],
							}
						],
					},
				]
			)

		# ITT Retenciones Arrendamiento
		if self.config_fiscal.enable_ret_arrendamiento:
			isr_config = obtener_configuracion_por_rol("ISR Retenido (Arrendamiento)")
			iva_config = obtener_configuracion_por_rol("IVA Retenido (Arrendamiento)")
			configs.extend(
				[
					{
						"title": "ITT ISR Arrendamiento",
						"taxes": [
							{"rol_fiscal": "ISR Retenido (Arrendamiento)", "tax_rate": isr_config["tasa"]}
						],
					},
					{
						"title": "ITT IVA Retenido Arrendamiento",
						"taxes": [
							{"rol_fiscal": "IVA Retenido (Arrendamiento)", "tax_rate": iva_config["tasa"]}
						],
					},
				]
			)

		# ITT Retenciones Autotransporte
		if self.config_fiscal.enable_ret_autotransporte:
			isr_config = obtener_configuracion_por_rol("ISR Retenido (Autotransporte)")
			iva_config = obtener_configuracion_por_rol("IVA Retenido (Autotransporte)")
			configs.extend(
				[
					{
						"title": "ITT ISR Autotransporte",
						"taxes": [
							{"rol_fiscal": "ISR Retenido (Autotransporte)", "tax_rate": isr_config["tasa"]}
						],
					},
					{
						"title": "ITT IVA Retenido Autotransporte",
						"taxes": [
							{"rol_fiscal": "IVA Retenido (Autotransporte)", "tax_rate": iva_config["tasa"]}
						],
					},
				]
			)

		return configs

	def _obtener_itt_granular(self) -> list[dict]:
		"""Wrapper: devuelve TODOS los ITT (base + IEPS + retenciones)."""
		configs = list(self._obtener_itt_base() or [])
		configs.extend(self._obtener_itt_ieps() or [])
		configs.extend(self._obtener_itt_retenciones() or [])
		return configs

	def _crear_o_actualizar_itt(self, config: dict, mapeo_cuentas: dict[str, str]) -> str:
		"""Crear o actualizar Item Tax Template."""
		title = f"{config['title']} - {self.company_abbr}"

		# Buscar existente
		existing = frappe.db.exists("Item Tax Template", {"title": title, "company": self.company})

		if existing:
			doc = frappe.get_doc("Item Tax Template", existing)

			# FIX: Normalizar name si tiene doble sufijo (name != title)
			if doc.name != title:
				frappe.rename_doc("Item Tax Template", doc.name, title, force=1)
				doc = frappe.get_doc("Item Tax Template", title)  # Recargar después de rename

			doc.taxes = []  # limpiar para rearmar
		else:
			doc = frappe.get_doc(
				{
					"doctype": "Item Tax Template",
					"name": title,  # ← name fijo = title (evita doble sufijo)
					"title": title,
					"company": self.company,
				}
			)
			doc.taxes = []

		# común: reconstruir taxes
		for idx, tax_config in enumerate(config.get("taxes", []), start=1):
			rol_fiscal = tax_config["rol_fiscal"]
			cuenta_impuesto = mapeo_cuentas.get(rol_fiscal)
			if not cuenta_impuesto:
				continue
			doc.append(
				"taxes",
				{
					"tax_type": cuenta_impuesto,
					"tax_rate": flt(tax_config.get("tax_rate", 0.0)),
					"idx": idx,
				},
			)

		# guardar
		if existing:
			doc.save(ignore_permissions=True)
		else:
			doc.insert(ignore_permissions=True)

		return doc.name

	def _generar_tax_rules(self) -> list[str]:
		"""
		Generar Tax Rules SOLO para STCT existentes.

		Busca todos los STCT creados para la empresa y genera Tax Rules correspondientes.
		Esto evita errores "Tax Template is mandatory" al intentar crear reglas sin STCT.

		Returns:
			Lista de nombres de Tax Rules generadas
		"""
		tax_rules = []

		# Obtener todos los STCT existentes para esta empresa
		stct_existentes = frappe.get_all(
			"Sales Taxes and Charges Template",
			filters={"company": self.company},
			fields=["name", "tax_category"],
			order_by="tax_category",
		)

		if not stct_existentes:
			frappe.msgprint("No se encontraron STCT para generar Tax Rules")
			return tax_rules

		# Generar Tax Rule para cada STCT existente con prioridades específicas
		# Prioridades: General 16% (máxima) > Frontera > Zero 0 > Exempt > IEPS > Retenciones
		priority_map = {
			# Prioridades principales (más comunes)
			"General 16": 100,  # Máxima prioridad - default más común
			"Border 8": 90,  # Frontera - segunda prioridad
			"Zero 0": 80,  # Exportación - tercera prioridad
			"Exempt": 70,  # Exento - cuarta prioridad
			# Prioridades IEPS (casos específicos)
			"IEPS Alcohol": 60,  # IEPS + IVA
			"IEPS Azucar": 55,  # IEPS + IVA
			"IEPS Combustibles": 50,  # IEPS + IVA
			"IEPS Tabaco": 45,  # IEPS + IVA
			# Prioridades Retenciones (casos muy específicos)
			"Retenciones Honorarios": 40,  # Retenciones específicas
			"Retenciones Arrendamiento": 35,  # Retenciones específicas
			"Retenciones Autotransporte": 30,  # Retenciones específicas
		}

		for stct in stct_existentes:
			if not stct.tax_category:
				continue  # Skip STCT sin tax_category

			tax_category = stct.tax_category

			# Configuración base del Tax Rule con prioridad específica
			priority = priority_map.get(tax_category, 10)  # Default 10 si no está en el mapa
			config = {
				"tax_category": tax_category,
				"priority": priority,
				"sales_tax_template": stct.name,  # CORREGIDO: Campo correcto es sales_tax_template
			}

			try:
				rule_name = self._crear_o_actualizar_tax_rule(config)
				if rule_name:
					tax_rules.append(rule_name)

			except Exception as e:
				frappe.log_error(f"Error creando Tax Rule para {tax_category}: {e!s}")
				continue

		return tax_rules

	def _find_stct_by_tax_category(self, tax_category: str) -> str | None:
		"""
		Buscar STCT existente por tax_category y company.

		Args:
			tax_category: Categoría fiscal a buscar

		Returns:
			Nombre del STCT encontrado o None si no existe
		"""
		rows = frappe.get_all(
			"Sales Taxes and Charges Template",
			filters={"company": self.company, "tax_category": tax_category},
			fields=["name"],
			order_by="modified desc",
		)
		return rows[0].name if rows else None

	def _crear_o_actualizar_tax_rule(self, config: dict) -> str | None:
		"""
		Crear o actualizar Tax Rule con validación robusta de STCT.

		Args:
			config: Diccionario con configuración de la regla

		Returns:
			Nombre de la Tax Rule creada/actualizada o None si falla
		"""
		tax_category = config["tax_category"]
		title = f"MX {tax_category} - {self.company}"

		# 1. Resolver STCT por tax_category y validar existencia
		stct_name = config.get("sales_tax_template") or self._find_stct_by_tax_category(tax_category)

		if not stct_name:
			frappe.throw(
				f"No existe STCT para tax_category '{tax_category}'. Genera STCT antes del Tax Rule."
			)

		# Buscar regla existente
		existing = frappe.db.exists("Tax Rule", {"title": title, "company": self.company})

		if existing:
			doc = frappe.get_doc("Tax Rule", existing)
		else:
			doc = frappe.new_doc("Tax Rule")
			doc.title = title
			doc.company = self.company

		# 2. Configurar campos clave
		doc.tax_type = "Sales"
		doc.tax_category = tax_category
		doc.sales_tax_template = stct_name  # CORREGIDO: Campo correcto es sales_tax_template
		doc.priority = config.get("priority", 10)
		doc.enabled = 1

		# Configurar condiciones específicas
		if "customer_group" in config:
			doc.customer_group = config["customer_group"]

		if "item_group" in config:
			doc.item_group = config["item_group"]

		doc.save(ignore_permissions=True)
		return doc.name

	def _actualizar_estado_configuracion(self, resultados: dict):
		"""Actualizar estado de la configuración fiscal."""
		total_templates = len(resultados["stct_generados"]) + len(resultados["itt_generados"])

		self.config_fiscal.update(
			{
				"configuracion_completa": 1,
				"templates_generados": total_templates,
				"ultima_actualizacion": frappe.utils.now(),
			}
		)
		self.config_fiscal.save(ignore_permissions=True)


@frappe.whitelist()
def generar_templates_empresa(company: str) -> dict:
	"""
	API endpoint para generar templates fiscales de una empresa.

	Args:
		company: Nombre de la empresa

	Returns:
		Dict con resultados de la generación
	"""
	generador = GeneradorTemplatesFiscales(company)
	return generador.generar_templates_completos()


@frappe.whitelist()
def preview_templates_a_generar(company: str) -> dict:
	"""
	Preview de templates que se van a generar sin crear nada.

	Args:
		company: Nombre de la empresa

	Returns:
		Dict con preview de templates
	"""
	generador = GeneradorTemplatesFiscales(company)
	mapeo_cuentas = generador._obtener_mapeo_cuentas()

	# Generar preview dinámico basado en alcance
	stct_preview = []
	itt_preview = []

	# STCT Opción B (consolidado con IEPS + retenciones)
	templates_stct = generador._obtener_stct_opcion_b()
	for template in templates_stct:
		stct_preview.append(f"{template['title']} - {generador.company_abbr}")

	# ITT Preview (todos los tipos)
	itt_configs_all = generador._obtener_itt_granular()

	for config in itt_configs_all:
		itt_preview.append(f"{config['title']} - {generador.company_abbr}")

	return {
		"stct_preview": stct_preview,
		"itt_preview": itt_preview,
		"mapeo_cuentas": mapeo_cuentas,
		"estadisticas": {
			"total_stct": len(stct_preview),
			"total_itt": len(itt_preview),
			"total_templates": len(stct_preview) + len(itt_preview),
		},
		"alcance": {
			"frontera": generador.config_fiscal.enable_frontera,
			"exportacion": generador.config_fiscal.enable_exportacion,
			"ieps": any(
				[
					generador.config_fiscal.enable_ieps_alcohol,
					generador.config_fiscal.enable_ieps_azucar,
					generador.config_fiscal.enable_ieps_combustibles,
					generador.config_fiscal.enable_ieps_tabaco,
				]
			),
			"retenciones": any(
				[
					generador.config_fiscal.enable_ret_honorarios,
					generador.config_fiscal.enable_ret_arrendamiento,
					generador.config_fiscal.enable_ret_autotransporte,
				]
			),
		},
	}
