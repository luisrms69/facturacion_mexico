"""
CFDI Global Builder - Sprint 4 Semana 1
Constructor de datos CFDI para facturas globales en FacturAPI.io
"""

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt, format_date

from facturacion_mexico.facturacion_fiscal.api_client import get_facturapi_client


class CFDIGlobalBuilder:
	"""Constructor de datos CFDI para facturas globales."""

	def __init__(self, factura_global_doc):
		"""Inicializar con documento Factura Global MX."""
		self.global_doc = factura_global_doc
		self.company = factura_global_doc.company
		self.company_doc = frappe.get_doc("Company", self.company)
		self.cs = self._load_company_settings()

	def _load_company_settings(self):
		"""Cargar Company Settings y validar campos requeridos para Factura Global."""
		cs = frappe.db.get_value(
			"Facturacion Mexico Company Settings",
			{"company": self.company},
			["global_customer", "global_item", "global_payment_form_default"],
			as_dict=True,
		)
		if not cs:
			frappe.throw(
				_(
					"No existe configuración para la Company '{0}'. "
					"Configure Facturacion Mexico Company Settings."
				).format(self.company)
			)
		if not cs.global_customer:
			frappe.throw(
				_(
					"Falta configurar 'Customer Público en General' en Facturacion Mexico Company Settings para la Company '{0}'."
				).format(self.company)
			)
		if not cs.global_item:
			frappe.throw(
				_(
					"Falta configurar 'Item Concepto Factura Global' en Facturacion Mexico Company Settings para la Company '{0}'."
				).format(self.company)
			)
		return cs

	def build_global_invoice_data(self) -> dict[str, Any]:
		"""Construir datos completos para FacturAPI.io."""
		self.client = get_facturapi_client(company=self.company)

		cfdi_data = {
			"type": "I",
			"customer": self._build_customer_data(),
			"items": self._build_items_data(),
			"payment_form": self._get_payment_form(),
			"payment_method": "PUE",
			"use": "S01",  # Sin efectos fiscales — obligatorio para factura global
			"external_id": self.global_doc.name,
			"date": self._get_invoice_date(),
			"global": self._build_global_object(),
		}

		return cfdi_data

	def _build_customer_data(self) -> dict[str, Any]:
		"""Construir datos del receptor desde Customer configurado en Company Settings."""
		customer = frappe.get_doc("Customer", self.cs.global_customer)

		# Validar que es RFC público general
		rfc = customer.get("tax_id") or ""
		if rfc != "XAXX010101000":
			frappe.throw(
				_(
					"El Customer '{0}' no tiene RFC XAXX010101000. Configure el Customer correcto en Facturacion Mexico Company Settings."
				).format(self.cs.global_customer)
			)

		# Validar régimen fiscal
		regimen = (customer.get("fm_tax_regime") or "").split(" - ")[0].strip()
		if regimen != "616":
			frappe.throw(
				_("El Customer '{0}' no tiene régimen fiscal 616. Configure el Customer correcto.").format(
					self.cs.global_customer
				)
			)

		# CP desde la dirección primaria del Customer, si existe
		zip_code = self._get_customer_zip(customer)

		customer_data = {
			"legal_name": customer.customer_name or "PUBLICO EN GENERAL",
			"tax_id": "XAXX010101000",
			"tax_system": "616",
			"address": {"country": "MEX", "zip": zip_code},
		}

		email = customer.get("email_id") or customer.get("fm_email") or ""
		if email:
			customer_data["email"] = email

		return customer_data

	def _get_customer_zip(self, customer_doc) -> str:
		"""Obtener CP desde la dirección del Customer o del emisor como fallback."""
		# Intentar obtener de la dirección primaria del Customer
		if customer_doc.get("customer_primary_address"):
			cp = frappe.db.get_value("Address", customer_doc.customer_primary_address, "pincode")
			if cp:
				return cp

		# Fallback: CP fiscal del emisor desde Configuracion Fiscal Mexico
		cp_emisor = frappe.db.get_value(
			"Configuracion Fiscal Mexico", {"company": self.company}, "lugar_expedicion"
		)
		if cp_emisor:
			return cp_emisor

		# Fallback final: CP de la Company
		cp_company = frappe.db.get_value("Company", self.company, "zip_code")
		return cp_company or "01000"

	def _build_items_data(self) -> list[dict[str, Any]]:
		"""Construir items de la factura global desde el Item configurado en Company Settings."""
		item_doc = frappe.get_doc("Item", self.cs.global_item)

		# Validar campos SAT del item
		product_key = item_doc.get("fm_producto_servicio_sat")
		unit_key = item_doc.get("fm_unidad_sat")
		if not product_key:
			frappe.throw(
				_("El Item '{0}' no tiene clave SAT (fm_producto_servicio_sat) configurada.").format(
					self.cs.global_item
				)
			)
		if not unit_key:
			frappe.throw(
				_("El Item '{0}' no tiene unidad SAT (fm_unidad_sat) configurada.").format(
					self.cs.global_item
				)
			)

		# Extraer código de la unidad SAT si tiene formato "H87 - Pieza"
		if " - " in str(unit_key):
			unit_key = unit_key.split(" - ")[0].strip()

		description = (
			item_doc.description
			or f"Ventas período {format_date(self.global_doc.periodo_inicio)} al {format_date(self.global_doc.periodo_fin)}"
		)

		items = []
		tax_groups = self._group_receipts_by_tax()

		for tax_rate, group_data in tax_groups.items():
			item = {
				"quantity": group_data["quantity"],
				"product": {
					"description": description,
					"product_key": product_key,
					"price": group_data["unit_price"],
					"unit_key": unit_key,
					"sku": item_doc.item_code,
				},
				"taxes": self._build_item_taxes(tax_rate),
			}
			items.append(item)

		return items

	def _group_receipts_by_tax(self) -> dict[str, dict[str, Any]]:
		"""Agrupar receipts por tasa de impuesto."""
		groups = {}

		for detail in self.global_doc.receipts_detail:
			if not detail.included_in_cfdi:
				continue

			receipt_doc = frappe.get_doc("EReceipt MX", detail.ereceipt)

			# IEPS bloquea antes de cualquier otra validación (issue #182 para soporte completo)
			if receipt_doc.get("has_ieps"):
				frappe.throw(
					_(
						"El E-Receipt '{0}' tiene IEPS. Factura Global con IEPS aún no está soportada; "
						"se requiere modelo line-level de impuestos (issue #182)."
					).format(detail.ereceipt)
				)

			# tax_rate sin default silencioso — None bloquea (ver issue #182 para modelo definitivo)
			tax_rate_raw = receipt_doc.get("tax_rate")
			if tax_rate_raw is None:
				frappe.throw(
					_(
						"El E-Receipt '{0}' no tiene tasa IVA definida. "
						"Recrea el recibo desde una Sales Invoice con plantilla de impuestos configurada."
					).format(detail.ereceipt)
				)
			tax_rate = flt(tax_rate_raw)

			rate_key = f"tax_{tax_rate}"

			if rate_key not in groups:
				groups[rate_key] = {
					"tax_rate": tax_rate,
					"quantity": 0,
					"total_amount": 0,
					"total_tax": 0,
					"receipts": [],
				}

			groups[rate_key]["quantity"] += 1
			groups[rate_key]["total_amount"] += flt(detail.monto)
			groups[rate_key]["total_tax"] += flt(receipt_doc.get("tax_amount", 0))
			groups[rate_key]["receipts"].append(detail)

		# Calcular precio unitario para cada grupo
		for group in groups.values():
			if group["quantity"] > 0:
				# Precio unitario = monto base / cantidad
				base_amount = group["total_amount"] - group["total_tax"]
				group["unit_price"] = flt(base_amount / group["quantity"], 6)

		return groups

	def _build_item_taxes(self, tax_rate: float) -> list[dict[str, Any]]:
		"""Construir impuestos del item."""
		taxes = []

		if tax_rate > 0:
			# IVA Trasladado
			taxes.append({"type": "IVA", "factor": "Tasa", "rate": tax_rate / 100, "withholding": False})

		return taxes

	def _get_payment_form(self) -> str:
		"""Obtener forma de pago: receipts → Company Settings → fallback '01'."""
		# Intentar obtener de los Sales Invoices subyacentes
		si_names = [
			frappe.db.get_value("EReceipt MX", d.ereceipt, "sales_invoice")
			for d in self.global_doc.receipts_detail
			if d.get("ereceipt")
		]
		si_names = [s for s in si_names if s]

		if si_names:
			# Buscar Payment Entries vinculadas
			modes = set()
			for si in si_names:
				pe = frappe.db.get_value(
					"Payment Entry Reference",
					{"reference_doctype": "Sales Invoice", "reference_name": si},
					"parent",
				)
				if pe:
					mode = frappe.db.get_value("Payment Entry", pe, "mode_of_payment")
					if mode:
						sat_code = frappe.db.get_value("Mode of Payment", mode, "fm_codigo_sat")
						if sat_code:
							modes.add(sat_code)

			if len(modes) == 1:
				return modes.pop()  # Todos los receipts tienen la misma forma de pago

		if not self.cs.global_payment_form_default:
			frappe.throw(
				_(
					"Falta configurar 'Forma de Pago Global por Defecto' en "
					"Facturacion Mexico Company Settings para la Company '{0}'."
				).format(self.company)
			)
		return self.cs.global_payment_form_default

	def _get_invoice_date(self) -> str:
		"""Obtener fecha de la factura."""
		# Usar el último día del período como fecha de factura
		return self.global_doc.periodo_fin.strftime("%Y-%m-%d")

	def _build_global_object(self) -> dict[str, Any]:
		"""Construir objeto 'global' requerido por FacturAPI para facturas globales.

		Estructura esperada por FacturAPI:
		  global.periodicity — código SAT de periodicidad (01-04)
		  global.months — mes(es) del período en formato "01"-"12"
		  global.year — año fiscal
		"""
		fecha_fin = (
			self.global_doc.periodo_fin
			if hasattr(self.global_doc.periodo_fin, "strftime")
			else frappe.utils.getdate(self.global_doc.periodo_fin)
		)

		return {
			"periodicity": self._map_periodicidad(),
			"months": fecha_fin.strftime("%m"),
			"year": fecha_fin.year,
		}

	def _map_periodicidad(self) -> str:
		"""Mapear periodicidad a código SAT."""
		mapping = {"Diaria": "01", "Semanal": "02", "Quincenal": "03", "Mensual": "04"}
		return mapping.get(self.global_doc.periodicidad, "04")

	# _add_company_settings eliminado — datos migrados a _build_customer_data y _load_company_settings

	def validate_cfdi_data(self) -> dict[str, Any]:
		"""Validar datos CFDI antes de enviar."""
		validation = {"is_valid": True, "errors": [], "warnings": []}

		try:
			cfdi_data = self.build_global_invoice_data()

			# Validaciones básicas
			if not cfdi_data.get("items"):
				validation["errors"].append("No hay items en la factura")
				validation["is_valid"] = False

			if not cfdi_data.get("customer"):
				validation["errors"].append("Datos de cliente faltantes")
				validation["is_valid"] = False

			# Validar montos
			total_amount = sum(
				item["quantity"] * item["product"]["price"] for item in cfdi_data.get("items", [])
			)

			if total_amount <= 0:
				validation["errors"].append("Monto total debe ser mayor a cero")
				validation["is_valid"] = False

			if total_amount != flt(self.global_doc.total_periodo):
				validation["warnings"].append(
					f"Monto calculado ({total_amount}) difiere del registrado ({self.global_doc.total_periodo})"
				)

			# Validar período
			if self.global_doc.periodo_inicio > self.global_doc.periodo_fin:
				validation["errors"].append("Período inválido: fecha inicio posterior a fecha fin")
				validation["is_valid"] = False

			# Validar receipts
			if not self.global_doc.receipts_detail:
				validation["errors"].append("No hay E-Receipts incluidos")
				validation["is_valid"] = False

		except Exception as e:
			validation["errors"].append(f"Error validando datos CFDI: {e!s}")
			validation["is_valid"] = False

		return validation

	def get_preview_data(self) -> dict[str, Any]:
		"""Obtener datos de preview sin generar CFDI."""
		try:
			cfdi_data = self.build_global_invoice_data()
			validation = self.validate_cfdi_data()

			preview = {
				"cfdi_data": cfdi_data,
				"validation": validation,
				"summary": {
					"total_items": len(cfdi_data.get("items", [])),
					"total_receipts": self.global_doc.cantidad_receipts,
					"total_amount": self.global_doc.total_periodo,
					"period": f"{self.global_doc.periodo_inicio} - {self.global_doc.periodo_fin}",
					"periodicity": self.global_doc.periodicidad,
				},
			}

			return preview

		except Exception as e:
			return {"error": str(e), "cfdi_data": None, "validation": {"is_valid": False, "errors": [str(e)]}}
