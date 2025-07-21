"""
CFDI Global Builder - Sprint 4 Semana 1
Constructor de datos CFDI para facturas globales en FacturAPI.io
"""

from typing import Any, Optional

import frappe
from frappe import _
from frappe.utils import cstr, flt, format_date, getdate


class CFDIGlobalBuilder:
	"""Constructor de datos CFDI para facturas globales."""

	def __init__(self, factura_global_doc):
		"""Inicializar con documento Factura Global MX."""
		self.global_doc = factura_global_doc
		self.company_doc = frappe.get_doc("Company", factura_global_doc.company)
		self.settings = frappe.get_single("Facturacion Mexico Settings")

	def build_global_invoice_data(self) -> dict[str, Any]:
		"""Construir datos completos para FacturAPI.io."""
		cfdi_data = {
			"type": "I",  # Ingreso
			"customer": self._build_customer_data(),
			"items": self._build_items_data(),
			"payment_form": self._get_payment_form(),
			"payment_method": "PPD",  # Pago en parcialidades diferido (común para globales)
			"usage": "G01",  # Adquisición de mercancías
			"series": self.global_doc.serie or self.settings.global_invoice_serie,
			"external_id": self.global_doc.name,
			"date": self._get_invoice_date(),
			"complemento_global": self._build_global_complement(),
		}

		# Agregar configuraciones específicas de la empresa
		self._add_company_settings(cfdi_data)

		return cfdi_data

	def _build_customer_data(self) -> dict[str, Any]:
		"""Construir datos del receptor (cliente genérico para factura global)."""
		# Para facturas globales, normalmente se usa público general
		customer_data = {
			"legal_name": "PUBLICO EN GENERAL",
			"tax_id": "XAXX010101000",  # RFC genérico público general
			"tax_system": "616",  # Sin obligaciones fiscales
			"email": self.settings.get("default_email") or "facturacion@empresa.com",
			"address": {"country": "MEX", "zip": "01000"},
		}

		return customer_data

	def _build_items_data(self) -> list[dict[str, Any]]:
		"""Construir items de la factura global."""
		items = []

		# Agrupar receipts por tasa de impuesto para optimizar
		tax_groups = self._group_receipts_by_tax()

		for tax_rate, group_data in tax_groups.items():
			item = {
				"quantity": group_data["quantity"],
				"product": {
					"description": f"Servicios del período {format_date(self.global_doc.periodo_inicio)} al {format_date(self.global_doc.periodo_fin)}",
					"product_key": "84111506",  # Servicios de facturación
					"price": group_data["unit_price"],
					"unit_key": "ACT",  # Actividad
					"unit_name": "Actividad",
					"sku": f"GLOBAL-{self.global_doc.periodicidad}",
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

			# Obtener datos del receipt
			receipt_doc = frappe.get_doc("EReceipt MX", detail.ereceipt)
			tax_rate = flt(receipt_doc.get("tax_rate", 16))

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
		"""Obtener forma de pago."""
		# Para facturas globales, típicamente es efectivo o transferencia
		return self.settings.get("default_payment_form") or "01"  # Efectivo

	def _get_invoice_date(self) -> str:
		"""Obtener fecha de la factura."""
		# Usar el último día del período como fecha de factura
		return self.global_doc.periodo_fin.strftime("%Y-%m-%d")

	def _build_global_complement(self) -> dict[str, Any]:
		"""Construir complemento específico para factura global."""
		complement = {
			"type": "global",
			"period": {
				"start": self.global_doc.periodo_inicio.strftime("%Y-%m-%d"),
				"end": self.global_doc.periodo_fin.strftime("%Y-%m-%d"),
				"periodicity": self._map_periodicidad(),
			},
			"receipts_summary": {
				"total_receipts": self.global_doc.cantidad_receipts,
				"total_amount": flt(self.global_doc.total_periodo),
			},
		}

		# Agregar información de receipts incluidos
		receipts_info = []
		for detail in self.global_doc.receipts_detail:
			if detail.included_in_cfdi:
				receipt_doc = frappe.get_doc("EReceipt MX", detail.ereceipt)
				receipts_info.append(
					{
						"folio": detail.folio_receipt,
						"date": detail.fecha_receipt.strftime("%Y-%m-%d"),
						"amount": flt(detail.monto),
						"facturapi_id": receipt_doc.get("facturapi_id"),
					}
				)

		complement["receipts_detail"] = receipts_info

		return complement

	def _map_periodicidad(self) -> str:
		"""Mapear periodicidad a código SAT."""
		mapping = {"Diaria": "01", "Semanal": "02", "Quincenal": "03", "Mensual": "04"}
		return mapping.get(self.global_doc.periodicidad, "04")

	def _add_company_settings(self, cfdi_data: dict[str, Any]) -> None:
		"""Agregar configuraciones específicas de la empresa."""
		# Configuraciones de la compañía
		if hasattr(self.company_doc, "tax_id"):
			cfdi_data["issuer_tax_id"] = self.company_doc.tax_id

		# Configuraciones de FacturAPI
		if self.settings.facturapi_test_mode:
			cfdi_data["test_mode"] = True

		# Serie personalizada si existe
		if self.settings.global_invoice_serie:
			cfdi_data["series"] = self.settings.global_invoice_serie

		# Configuración de lugar de expedición
		if hasattr(self.settings, "lugar_expedicion"):
			cfdi_data["zip_code"] = self.settings.lugar_expedicion

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
