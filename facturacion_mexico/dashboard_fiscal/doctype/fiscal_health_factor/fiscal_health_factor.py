# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalHealthFactor(Document):
	def validate(self):
		"""Validaciones del factor de salud fiscal"""
		self.validate_impact_score()

	def validate_impact_score(self):
		"""Validar que el impact_score esté en rango apropiado"""
		if self.impact_score:
			if abs(self.impact_score) > 10:
				frappe.throw(_("El impact_score debe estar entre -10 y +10"))

			# Asegurar que factores con descripción positiva tengan score positivo
			positive_keywords = ["excelente", "bueno", "alto", "óptimo", "exitoso"]
			negative_keywords = ["bajo", "error", "falta", "atrasado", "pendiente"]

			if self.description:
				desc_lower = self.description.lower()
				has_positive = any(keyword in desc_lower for keyword in positive_keywords)
				has_negative = any(keyword in desc_lower for keyword in negative_keywords)

				if has_positive and self.impact_score < 0:
					frappe.msgprint(
						_("Advertencia: La descripción parece positiva pero el score es negativo")
					)
				elif has_negative and self.impact_score > 0:
					frappe.msgprint(
						_("Advertencia: La descripción parece negativa pero el score es positivo")
					)
