"""
EReceipt Aggregator - Sprint 4 Semana 1
Procesador para agrupar E-Receipts en facturas globales
"""

from typing import Any, Optional

import frappe
from frappe import _
from frappe.utils import cstr, flt, getdate


class EReceiptAggregator:
	"""Agregador de E-Receipts para facturas globales."""

	def __init__(self, periodo_inicio: str, periodo_fin: str, company: str):
		"""Inicializar con período y empresa."""
		self.periodo_inicio = getdate(periodo_inicio)
		self.periodo_fin = getdate(periodo_fin)
		self.company = company
		self.receipts = []
		self.aggregated_data = {}

	def get_available_receipts(self) -> list[dict[str, Any]]:
		"""Obtener receipts no facturados del período."""
		if self.receipts:
			return self.receipts

		self.receipts = frappe.db.sql(
			"""
			SELECT
				er.name,
				er.name as folio,
				er.date_issued as receipt_date,
				er.total as total_amount,
				(er.total * 0.16) as tax_amount,
				(er.total * 0.84) as base_amount,
				er.customer_name,
				'MXN' as currency,
				1.0 as exchange_rate,
				16.0 as tax_rate,
				er.facturapi_id,
				er.status,
				'Efectivo' as payment_method,
				'G01' as usage_cfdi,
				er.creation,
				16.0 as effective_tax_rate
			FROM `tabEReceipt MX` er
			WHERE er.company = %(company)s
			AND er.date_issued BETWEEN %(periodo_inicio)s AND %(periodo_fin)s
			AND er.docstatus = 1
			AND (er.included_in_global IS NULL OR er.included_in_global = 0)
			AND er.status != 'cancelled'
			ORDER BY er.date_issued, er.name
		""",
			{"company": self.company, "periodo_inicio": self.periodo_inicio, "periodo_fin": self.periodo_fin},
			as_dict=True,
		)

		return self.receipts

	def group_by_tax_rate(self) -> dict[str, list[dict[str, Any]]]:
		"""Agrupar por tasa de impuesto."""
		if not self.receipts:
			self.get_available_receipts()

		grouped = {}
		for receipt in self.receipts:
			tax_rate = flt(receipt.get("effective_tax_rate", receipt.get("tax_rate", 16)), 2)
			rate_key = f"tax_{tax_rate}"

			if rate_key not in grouped:
				grouped[rate_key] = {
					"tax_rate": tax_rate,
					"receipts": [],
					"totals": {"count": 0, "base_amount": 0, "tax_amount": 0, "total_amount": 0},
				}

			grouped[rate_key]["receipts"].append(receipt)
			grouped[rate_key]["totals"]["count"] += 1
			grouped[rate_key]["totals"]["base_amount"] += flt(
				getattr(receipt, "base_amount", receipt.get("base_amount", 0))
			)
			grouped[rate_key]["totals"]["tax_amount"] += flt(
				getattr(receipt, "tax_amount", receipt.get("tax_amount", 0))
			)
			grouped[rate_key]["totals"]["total_amount"] += flt(
				getattr(receipt, "total_amount", receipt.get("total_amount", 0))
			)

		return grouped

	def group_by_day(self) -> dict[str, list[dict[str, Any]]]:
		"""Agrupar por día."""
		if not self.receipts:
			self.get_available_receipts()

		grouped = {}
		for receipt in self.receipts:
			receipt_date = getattr(receipt, "receipt_date", receipt.get("receipt_date"))
			if hasattr(receipt_date, "strftime"):
				day_key = receipt_date.strftime("%Y-%m-%d")
			else:
				# Handle string dates
				from frappe.utils import getdate

				day_key = getdate(receipt_date).strftime("%Y-%m-%d")

			if day_key not in grouped:
				grouped[day_key] = {
					"date": receipt_date,
					"receipts": [],
					"totals": {"count": 0, "total_amount": 0, "tax_amount": 0},
				}

			grouped[day_key]["receipts"].append(receipt)
			grouped[day_key]["totals"]["count"] += 1
			grouped[day_key]["totals"]["total_amount"] += flt(
				getattr(receipt, "total_amount", receipt.get("total_amount", 0))
			)
			grouped[day_key]["totals"]["tax_amount"] += flt(
				getattr(receipt, "tax_amount", receipt.get("tax_amount", 0))
			)

		return grouped

	def group_by_customer(self) -> dict[str, list[dict[str, Any]]]:
		"""Agrupar por cliente."""
		if not self.receipts:
			self.get_available_receipts()

		grouped = {}
		for receipt in self.receipts:
			customer_key = getattr(receipt, "customer_name", receipt.get("customer_name", "Público General"))

			if customer_key not in grouped:
				grouped[customer_key] = {
					"customer_name": customer_key,
					"receipts": [],
					"totals": {"count": 0, "total_amount": 0},
				}

			grouped[customer_key]["receipts"].append(receipt)
			grouped[customer_key]["totals"]["count"] += 1
			grouped[customer_key]["totals"]["total_amount"] += flt(
				getattr(receipt, "total_amount", receipt.get("total_amount", 0))
			)

		return grouped

	def calculate_totals(self) -> dict[str, Any]:
		"""Calcular totales generales."""
		if not self.receipts:
			self.get_available_receipts()

		totals = {
			"count": len(self.receipts),
			"base_amount": 0,
			"tax_amount": 0,
			"total_amount": 0,
			"currencies": {},
			"payment_methods": {},
			"date_range": {
				"inicio": self.periodo_inicio,
				"fin": self.periodo_fin,
				"days": (self.periodo_fin - self.periodo_inicio).days + 1,
			},
		}

		for receipt in self.receipts:
			totals["base_amount"] += flt(getattr(receipt, "base_amount", receipt.get("base_amount", 0)))
			totals["tax_amount"] += flt(getattr(receipt, "tax_amount", receipt.get("tax_amount", 0)))
			totals["total_amount"] += flt(getattr(receipt, "total_amount", receipt.get("total_amount", 0)))

			# Contadores por moneda
			currency = getattr(receipt, "currency", receipt.get("currency", "MXN")) or "MXN"
			if currency not in totals["currencies"]:
				totals["currencies"][currency] = {"count": 0, "amount": 0}
			totals["currencies"][currency]["count"] += 1
			totals["currencies"][currency]["amount"] += flt(
				getattr(receipt, "total_amount", receipt.get("total_amount", 0))
			)

			# Contadores por método de pago
			payment_method = (
				getattr(receipt, "payment_method", receipt.get("payment_method", "Sin especificar"))
				or "Sin especificar"
			)
			if payment_method not in totals["payment_methods"]:
				totals["payment_methods"][payment_method] = {"count": 0, "amount": 0}
			totals["payment_methods"][payment_method]["count"] += 1
			totals["payment_methods"][payment_method]["amount"] += flt(
				getattr(receipt, "total_amount", receipt.get("total_amount", 0))
			)

		return totals

	def validate_continuous_folios(self) -> dict[str, Any]:
		"""Validar folios consecutivos."""
		if not self.receipts:
			self.get_available_receipts()

		validation = {
			"is_continuous": True,
			"missing_folios": [],
			"duplicate_folios": [],
			"invalid_folios": [],
			"folio_range": {"start": None, "end": None},
			"total_receipts": len(self.receipts),
		}

		# Extraer y validar folios
		folios = []
		folio_counts = {}

		for receipt in self.receipts:
			folio = getattr(receipt, "folio", receipt.get("folio", ""))
			if not folio:
				validation["invalid_folios"].append(
					{
						"receipt": getattr(receipt, "name", receipt.get("name", "Unknown")),
						"issue": "Folio vacío",
					}
				)
				continue

			# Intentar extraer número del folio
			try:
				# Asumiendo formato ER-NNNN o similar
				if "-" in folio:
					folio_number = int(folio.split("-")[-1])
				else:
					folio_number = int(folio)

				folios.append(folio_number)

				# Contar duplicados
				if folio in folio_counts:
					folio_counts[folio] += 1
				else:
					folio_counts[folio] = 1

			except (ValueError, IndexError):
				validation["invalid_folios"].append(
					{"receipt": receipt.name, "folio": folio, "issue": "Formato de folio inválido"}
				)

		# Identificar duplicados
		for folio, count in folio_counts.items():
			if count > 1:
				validation["duplicate_folios"].append({"folio": folio, "count": count})

		# Validar continuidad si hay folios válidos
		if folios:
			folios.sort()
			validation["folio_range"]["start"] = folios[0]
			validation["folio_range"]["end"] = folios[-1]

			# Verificar folios faltantes
			expected_range = range(folios[0], folios[-1] + 1)
			missing = [f for f in expected_range if f not in folios]

			if missing:
				validation["is_continuous"] = False
				validation["missing_folios"] = missing

		return validation

	def get_aggregation_summary(self) -> dict[str, Any]:
		"""Obtener resumen completo de agregación."""
		if not self.receipts:
			self.get_available_receipts()

		summary = {
			"period": {"inicio": self.periodo_inicio, "fin": self.periodo_fin, "company": self.company},
			"totals": self.calculate_totals(),
			"groupings": {
				"by_tax_rate": self.group_by_tax_rate(),
				"by_day": self.group_by_day(),
				"by_customer": self.group_by_customer(),
			},
			"validations": {"folio_continuity": self.validate_continuous_folios()},
			"recommendations": self._get_recommendations(),
		}

		return summary

	def _get_recommendations(self) -> list[str]:
		"""Obtener recomendaciones basadas en el análisis."""
		recommendations = []

		if not self.receipts:
			recommendations.append("No hay E-Receipts disponibles en el período seleccionado")
			return recommendations

		totals = self.calculate_totals()

		# Recomendaciones basadas en cantidad
		if totals["count"] > 1000:
			recommendations.append(
				"Alto volumen de receipts (>1000). Considere dividir en períodos más pequeños"
			)
		elif totals["count"] < 10:
			recommendations.append("Bajo volumen de receipts (<10). Considere ampliar el período")

		# Recomendaciones basadas en montos
		if totals["total_amount"] > 1000000:  # 1M MXN
			recommendations.append("Monto alto (>$1M). Verifique límites fiscales aplicables")

		# Recomendaciones basadas en folios
		folio_validation = self.validate_continuous_folios()
		if not folio_validation["is_continuous"]:
			recommendations.append("Folios no consecutivos detectados. Revise la secuencia")

		if folio_validation["duplicate_folios"]:
			recommendations.append("Folios duplicados detectados. Revise la numeración")

		# Recomendaciones basadas en tasas de impuesto
		tax_groups = self.group_by_tax_rate()
		if len(tax_groups) > 3:
			recommendations.append("Multiple tasas de impuesto detectadas. Verifique agrupación correcta")

		# Recomendaciones basadas en monedas
		if len(totals["currencies"]) > 1:
			recommendations.append("Múltiples monedas detectadas. Solo MXN soportado para facturas globales")

		return recommendations

	def create_factura_global_details(self) -> list[dict[str, Any]]:
		"""Crear detalles para Factura Global MX."""
		if not self.receipts:
			self.get_available_receipts()

		details = []
		for receipt in self.receipts:
			detail = {
				"ereceipt": receipt.name,
				"folio_receipt": receipt.folio,
				"fecha_receipt": receipt.receipt_date,
				"monto": flt(receipt.total_amount),
				"customer_name": receipt.customer_name or "Público General",
				"included_in_cfdi": 1,
			}
			details.append(detail)

		return details
