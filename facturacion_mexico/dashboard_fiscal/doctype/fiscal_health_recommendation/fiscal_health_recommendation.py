# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

from datetime import date, timedelta

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalHealthRecommendation(Document):
	def validate(self):
		"""Validaciones de la recomendación"""
		self.validate_priority_and_days()
		self.validate_implementation_date()

	def validate_priority_and_days(self):
		"""Validar consistencia entre prioridad y días estimados"""
		if self.priority and self.estimated_days:
			if self.priority == "High" and self.estimated_days > 30:
				frappe.msgprint(
					_("Advertencia: Recomendación de alta prioridad con más de 30 días estimados")
				)
			elif self.priority == "Low" and self.estimated_days <= 1:
				frappe.msgprint(
					_("Advertencia: Recomendación de baja prioridad con muy pocos días estimados")
				)

	def validate_implementation_date(self):
		"""Validar fecha de implementación"""
		if self.implementation_date:
			if self.implementation_date < date.today():
				if self.status not in ["Completed", "Skipped"]:
					frappe.throw(
						_("Fecha de implementación no puede ser pasada para recomendaciones pendientes")
					)

	def auto_set_due_date(self):
		"""Calcular fecha sugerida basada en días estimados"""
		if self.estimated_days and not self.implementation_date:
			due_date = date.today() + timedelta(days=self.estimated_days)
			return due_date
		return None

	def get_urgency_level(self):
		"""Calcular nivel de urgencia basado en prioridad y días"""
		if self.priority == "High":
			if self.estimated_days <= 3:
				return "Critical"
			elif self.estimated_days <= 7:
				return "Urgent"
			else:
				return "High"
		elif self.priority == "Medium":
			return "Medium"
		else:
			return "Low"
