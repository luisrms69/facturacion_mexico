"""
Generador de Templates Fiscales México - Adaptador del motor install.py con mapeo de cuentas.
Reemplaza hardcodes por mapeo real de cuentas específicas por empresa.
"""

from typing import Optional

import frappe
from frappe.utils import flt


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
			"tax_rules_generados": self._generar_tax_rules(),
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
		categories = ["General 16", "Zero 0", "Exempt"]

		if self.config_fiscal.enable_frontera:
			categories.append("Border 8")

		for category in categories:
			if not frappe.db.exists("Tax Category", category):
				tax_cat = frappe.get_doc({"doctype": "Tax Category", "name": category, "title": category})
				tax_cat.insert(ignore_permissions=True)

	def _generar_stct(self, mapeo_cuentas: dict[str, str]) -> list[str]:
		"""Generar Sales Taxes and Charges Templates."""
		stct_generados = []

		# Templates base según alcance
		templates_config = [
			{
				"title": "IVA 16% - México",
				"tax_category": "General 16",
				"is_default": 1,
				"taxes": [
					{
						"rol_fiscal": "IVA por Pagar (16%)",
						"charge_type": "On Net Total",
						"rate": 16.0,
						"description": "Impuesto al Valor Agregado 16%",
					}
				],
			},
			{
				"title": "IVA 0% - México",
				"tax_category": "Zero 0",
				"taxes": [
					{
						"rol_fiscal": "IVA por Pagar (0% exportación)",
						"charge_type": "On Net Total",
						"rate": 0.0,
						"description": "Impuesto al Valor Agregado 0% (Exportación)",
					}
				],
			},
			{
				"title": "Sin Impuestos - México",
				"tax_category": "Exempt",
				"taxes": [],  # Template exento sin filas
			},
		]

		# Agregar frontera si está habilitada
		if self.config_fiscal.enable_frontera:
			templates_config.append(
				{
					"title": "IVA 8% Frontera - México",
					"tax_category": "Border 8",
					"taxes": [
						{
							"rol_fiscal": "IVA por Pagar (8% frontera)",
							"charge_type": "On Net Total",
							"rate": 8.0,
							"description": "Impuesto al Valor Agregado 8% Frontera",
						}
					],
				}
			)

		# Generar cada template
		for template_config in templates_config:
			stct_name = self._crear_o_actualizar_stct(template_config, mapeo_cuentas)
			stct_generados.append(stct_name)

		return stct_generados

	def _crear_o_actualizar_stct(self, template_config: dict, mapeo_cuentas: dict[str, str]) -> str:
		"""Crear o actualizar un Sales Taxes and Charges Template."""
		title = f"{template_config['title']} - {self.company_abbr}"

		# Buscar existente
		existing = frappe.db.exists(
			"Sales Taxes and Charges Template", {"title": title, "company": self.company}
		)

		if existing:
			doc = frappe.get_doc("Sales Taxes and Charges Template", existing)
		else:
			doc = frappe.new_doc("Sales Taxes and Charges Template")

		# Configurar campos principales
		doc.update(
			{
				"title": title,
				"company": self.company,
				"is_default": template_config.get("is_default", 0),
				"taxes": [],
			}
		)

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

			doc.append(
				"taxes",
				{
					"charge_type": tax_config.get("charge_type", "On Net Total"),
					"account_head": cuenta_impuesto,
					"rate": flt(tax_config.get("rate", 0.0)),
					"description": tax_config.get("description", rol_fiscal),
					"add_deduct_tax": "Add",
					"idx": idx,
				},
			)

		doc.save(ignore_permissions=True)
		return doc.name

	def _generar_itt(self, mapeo_cuentas: dict[str, str]) -> list[str]:
		"""Generar Item Tax Templates."""
		itt_generados = []

		itt_configs = [
			{"title": "ITT IVA 16%", "taxes": [{"rol_fiscal": "IVA por Pagar (16%)", "tax_rate": 16.0}]},
			{
				"title": "ITT IVA 0%",
				"taxes": [{"rol_fiscal": "IVA por Pagar (0% exportación)", "tax_rate": 0.0}],
			},
			{"title": "ITT Exento", "taxes": [{"rol_fiscal": "IVA Exento", "tax_rate": 0.0}]},
		]

		# Agregar frontera si está habilitada
		if self.config_fiscal.enable_frontera:
			itt_configs.append(
				{
					"title": "ITT IVA 8% Frontera",
					"taxes": [{"rol_fiscal": "IVA por Pagar (8% frontera)", "tax_rate": 8.0}],
				}
			)

		for config in itt_configs:
			itt_name = self._crear_o_actualizar_itt(config, mapeo_cuentas)
			itt_generados.append(itt_name)

		return itt_generados

	def _crear_o_actualizar_itt(self, config: dict, mapeo_cuentas: dict[str, str]) -> str:
		"""Crear o actualizar Item Tax Template."""
		title = f"{config['title']} - {self.company_abbr}"

		# Buscar existente
		existing = frappe.db.exists("Item Tax Template", {"title": title, "company": self.company})

		if existing:
			doc = frappe.get_doc("Item Tax Template", existing)
		else:
			doc = frappe.new_doc("Item Tax Template")

		doc.update({"title": title, "company": self.company, "taxes": []})

		# Agregar filas tax
		for idx, tax_config in enumerate(config.get("taxes", []), start=1):
			rol_fiscal = tax_config["rol_fiscal"]
			cuenta_impuesto = mapeo_cuentas.get(rol_fiscal)

			if cuenta_impuesto:
				doc.append(
					"taxes",
					{
						"tax_type": cuenta_impuesto,  # CRÍTICO: debe coincidir exacto con account_head de STCT
						"tax_rate": flt(tax_config.get("tax_rate", 0.0)),
						"idx": idx,
					},
				)

		doc.save(ignore_permissions=True)
		return doc.name

	def _generar_tax_rules(self) -> list[str]:
		"""Generar Tax Rules para selección automática."""
		rules_generados = []

		rules_config = [
			{"tax_category": "General 16", "priority": 10},
			{"tax_category": "Zero 0", "priority": 20},
			{"tax_category": "Exempt", "priority": 30},
		]

		if self.config_fiscal.enable_frontera:
			rules_config.append({"tax_category": "Border 8", "priority": 15})

		for rule_config in rules_config:
			rule_name = self._crear_o_actualizar_tax_rule(rule_config)
			if rule_name:
				rules_generados.append(rule_name)

		return rules_generados

	def _crear_o_actualizar_tax_rule(self, config: dict) -> str | None:
		"""Crear o actualizar Tax Rule."""
		tax_category = config["tax_category"]
		title = f"MX {tax_category} - {self.company}"

		# Buscar STCT correspondiente
		stct_name = frappe.db.get_value(
			"Sales Taxes and Charges Template",
			{"company": self.company, "tax_category": tax_category},
			"name",
		)

		if not stct_name:
			frappe.msgprint(f"No se encontró STCT para Tax Category {tax_category}")
			return None

		# Buscar existente
		existing = frappe.db.exists("Tax Rule", {"name": title})

		if existing:
			doc = frappe.get_doc("Tax Rule", existing)
		else:
			doc = frappe.new_doc("Tax Rule")

		doc.update(
			{
				"name": title,
				"company": self.company,
				"tax_type": "Sales",
				"tax_category": tax_category,
				"priority": config.get("priority", 10),
				"sales_taxes_and_charges_template": stct_name,
			}
		)

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

	return {
		"stct_preview": [
			f"IVA 16% - México - {generador.company_abbr}",
			f"IVA 0% - México - {generador.company_abbr}",
			f"Sin Impuestos - México - {generador.company_abbr}",
		],
		"itt_preview": [
			f"ITT IVA 16% - {generador.company_abbr}",
			f"ITT IVA 0% - {generador.company_abbr}",
			f"ITT Exento - {generador.company_abbr}",
		],
		"mapeo_cuentas": mapeo_cuentas,
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
		},
	}
