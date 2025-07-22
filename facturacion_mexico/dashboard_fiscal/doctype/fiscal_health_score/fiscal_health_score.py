# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import time
from datetime import date, datetime, timedelta

import frappe
from frappe import _
from frappe.model.document import Document


class FiscalHealthScore(Document):
	def validate(self):
		"""Validaciones antes de guardar"""
		self.validate_score_date()
		if not self.overall_score:
			self.calculate_health_score()

	def validate_score_date(self):
		"""Validar que la fecha del score no sea futura"""
		if self.score_date and self.score_date > date.today():
			frappe.throw(_("La fecha del score no puede ser futura"))

	def calculate_health_score(self):
		"""Calcular score de salud fiscal completo"""
		start_time = time.time()

		try:
			# Limpiar factores y recomendaciones existentes
			self.factors_positive = []
			self.factors_negative = []
			self.recommendations = []

			# Calcular scores por módulo
			self.calculate_module_scores()

			# Calcular score general
			self.calculate_overall_score()

			# Generar factores de salud
			self.generate_health_factors()

			# Generar recomendaciones
			self.generate_recommendations()

			# Actualizar metadatos
			self.last_calculated = datetime.now()
			self.created_by = frappe.session.user

			# Calcular duración
			duration_ms = int((time.time() - start_time) * 1000)
			self.calculation_duration_ms = duration_ms

		except Exception as e:
			frappe.log_error(f"Error calculando health score: {e!s}", "Health Score Calculation")
			frappe.throw(_("Error al calcular el score de salud fiscal: {0}").format(str(e)))

	def calculate_module_scores(self):
		"""Calcular scores individuales por módulo"""

		# Score Timbrado
		self.timbrado_score = self.calculate_timbrado_score()

		# Score PPD
		self.ppd_score = self.calculate_ppd_score()

		# Score E-Receipts
		self.ereceipts_score = self.calculate_ereceipts_score()

		# Score Addendas
		self.addendas_score = self.calculate_addendas_score()

		# Score Facturas Globales
		self.global_invoices_score = self.calculate_global_invoices_score()

		# Score Cumplimiento Reglas
		self.rules_compliance_score = self.calculate_rules_compliance_score()

	def calculate_timbrado_score(self):
		"""Calcular score del módulo de timbrado"""
		try:
			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# Facturas totales en el período
			total_invoices = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [period_start, period_end]],
				},
			)

			if total_invoices == 0:
				return 100.0  # Sin facturas = score perfecto

			# Facturas timbradas exitosamente
			stamped_invoices = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [period_start, period_end]],
					"fm_timbrado_status": "Timbrada",
				},
			)

			# Facturas con errores
			error_invoices = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["between", [period_start, period_end]],
					"fm_timbrado_status": "Error",
				},
			)

			# Facturas pendientes (más de 24 horas)
			yesterday = date.today() - timedelta(days=1)
			pending_overdue = frappe.db.count(
				"Sales Invoice",
				filters={
					"company": self.company,
					"docstatus": 1,
					"posting_date": ["<", yesterday],
					"fm_timbrado_status": ["in", ["Pendiente", ""]],
				},
			)

			# Cálculo del score
			base_score = (stamped_invoices / total_invoices) * 100
			error_penalty = (error_invoices / total_invoices) * 20
			overdue_penalty = (pending_overdue / total_invoices) * 30

			final_score = base_score - error_penalty - overdue_penalty
			return max(0, min(100, final_score))

		except Exception as e:
			frappe.log_error(f"Error calculando timbrado score: {e!s}", "Timbrado Score")
			return 50.0  # Score neutro en caso de error

	def calculate_ppd_score(self):
		"""Calcular score del módulo PPD"""
		try:
			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# Pagos totales que requieren complemento
			total_payments = frappe.db.count(
				"Payment Entry",
				filters={
					"company": self.company,
					"docstatus": 1,
					"payment_type": "Receive",
					"posting_date": ["between", [period_start, period_end]],
				},
			)

			if total_payments == 0:
				return 100.0

			# Complementos completados
			completed_complements = frappe.db.count(
				"Payment Entry",
				filters={
					"company": self.company,
					"docstatus": 1,
					"payment_type": "Receive",
					"posting_date": ["between", [period_start, period_end]],
					"fm_ppd_status": "Completed",
				},
			)

			# Complementos vencidos (más de 30 días)
			month_ago = date.today() - timedelta(days=30)
			overdue_complements = frappe.db.count(
				"Payment Entry",
				filters={
					"company": self.company,
					"docstatus": 1,
					"payment_type": "Receive",
					"posting_date": ["<", month_ago],
					"fm_ppd_status": ["not in", ["Completed"]],
				},
			)

			# Cálculo del score
			base_score = (completed_complements / total_payments) * 100
			overdue_penalty = (overdue_complements / total_payments) * 40

			final_score = base_score - overdue_penalty
			return max(0, min(100, final_score))

		except Exception:
			return 50.0

	def calculate_ereceipts_score(self):
		"""Calcular score del módulo E-Receipts"""
		try:
			# Verificar si existe la tabla EReceipt MX
			if not frappe.db.exists("DocType", "EReceipt MX"):
				return 100.0  # Módulo no instalado = score perfecto

			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# E-Receipts totales
			total_ereceipts = frappe.db.count(
				"EReceipt MX",
				filters={
					"company": self.company,
					"docstatus": 1,
					"creation": ["between", [period_start, period_end]],
				},
			)

			if total_ereceipts == 0:
				return 100.0

			# E-Receipts procesados exitosamente
			processed_ereceipts = frappe.db.count(
				"EReceipt MX",
				filters={
					"company": self.company,
					"docstatus": 1,
					"creation": ["between", [period_start, period_end]],
					"status": "Completed",
				},
			)

			# E-Receipts con error
			error_ereceipts = frappe.db.count(
				"EReceipt MX",
				filters={
					"company": self.company,
					"docstatus": 1,
					"creation": ["between", [period_start, period_end]],
					"status": "Error",
				},
			)

			# Cálculo del score
			base_score = (processed_ereceipts / total_ereceipts) * 100
			error_penalty = (error_ereceipts / total_ereceipts) * 25

			final_score = base_score - error_penalty
			return max(0, min(100, final_score))

		except Exception:
			return 100.0  # Asumir módulo no instalado

	def calculate_addendas_score(self):
		"""Calcular score del módulo de Addendas"""
		try:
			# Verificar si existe la tabla Addenda Template
			if not frappe.db.exists("DocType", "Addenda Template"):
				return 100.0

			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# Facturas con addenda aplicable
			invoices_with_addenda = frappe.db.sql(
				"""
                SELECT COUNT(*) as count
                FROM `tabSales Invoice` si
                INNER JOIN `tabCustomer` c ON si.customer = c.name
                WHERE si.company = %s
                AND si.docstatus = 1
                AND si.posting_date BETWEEN %s AND %s
                AND c.fm_requires_addenda = 1
            """,
				(self.company, period_start, period_end),
			)

			total_addenda_invoices = invoices_with_addenda[0][0] if invoices_with_addenda else 0

			if total_addenda_invoices == 0:
				return 100.0

			# Facturas con addenda aplicada correctamente
			successful_addendas = frappe.db.sql(
				"""
                SELECT COUNT(*) as count
                FROM `tabSales Invoice` si
                INNER JOIN `tabCustomer` c ON si.customer = c.name
                WHERE si.company = %s
                AND si.docstatus = 1
                AND si.posting_date BETWEEN %s AND %s
                AND c.fm_requires_addenda = 1
                AND si.fm_addenda_applied = 1
            """,
				(self.company, period_start, period_end),
			)

			applied_addendas = successful_addendas[0][0] if successful_addendas else 0

			# Cálculo del score
			score = (applied_addendas / total_addenda_invoices) * 100
			return max(0, min(100, score))

		except Exception:
			return 100.0

	def calculate_global_invoices_score(self):
		"""Calcular score del módulo de Facturas Globales"""
		try:
			if not frappe.db.exists("DocType", "Factura Global MX"):
				return 100.0

			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# Facturas globales iniciadas
			total_global = frappe.db.count(
				"Factura Global MX",
				filters={"company": self.company, "creation": ["between", [period_start, period_end]]},
			)

			if total_global == 0:
				return 100.0

			# Facturas globales completadas
			completed_global = frappe.db.count(
				"Factura Global MX",
				filters={
					"company": self.company,
					"creation": ["between", [period_start, period_end]],
					"consolidation_status": "Completed",
					"billing_status": "Success",
				},
			)

			# Cálculo del score
			score = (completed_global / total_global) * 100
			return max(0, min(100, score))

		except Exception:
			return 100.0

	def calculate_rules_compliance_score(self):
		"""Calcular score de cumplimiento de reglas"""
		try:
			if not frappe.db.exists("DocType", "Rule Execution Log"):
				return 100.0

			period_start = date(self.score_date.year, self.score_date.month, 1)
			period_end = self.score_date

			# Ejecuciones de reglas totales
			total_executions = frappe.db.count(
				"Rule Execution Log", filters={"creation": ["between", [period_start, period_end]]}
			)

			if total_executions == 0:
				return 100.0

			# Ejecuciones exitosas
			successful_executions = frappe.db.count(
				"Rule Execution Log",
				filters={"creation": ["between", [period_start, period_end]], "execution_status": "Success"},
			)

			# Ejecuciones con warnings
			warning_executions = frappe.db.count(
				"Rule Execution Log",
				filters={"creation": ["between", [period_start, period_end]], "execution_status": "Warning"},
			)

			# Cálculo del score (warnings penalizan menos que errores)
			success_score = (successful_executions / total_executions) * 100
			warning_penalty = (warning_executions / total_executions) * 10

			final_score = success_score - warning_penalty
			return max(0, min(100, final_score))

		except Exception:
			return 100.0

	def calculate_overall_score(self):
		"""Calcular score general usando método configurado"""
		if self.calculation_method == "Simple Average":
			scores = [
				self.timbrado_score or 0,
				self.ppd_score or 0,
				self.ereceipts_score or 0,
				self.addendas_score or 0,
				self.global_invoices_score or 0,
				self.rules_compliance_score or 0,
			]
			self.overall_score = sum(scores) / len(scores)

		elif self.calculation_method == "Custom Formula":
			# Fórmula personalizada (placeholder)
			self.overall_score = self.calculate_custom_formula()

		else:  # Weighted Average (default)
			weights = {
				"timbrado": 0.25,
				"ppd": 0.20,
				"ereceipts": 0.15,
				"addendas": 0.15,
				"global_invoices": 0.10,
				"rules_compliance": 0.15,
			}

			weighted_sum = (
				(self.timbrado_score or 0) * weights["timbrado"]
				+ (self.ppd_score or 0) * weights["ppd"]
				+ (self.ereceipts_score or 0) * weights["ereceipts"]
				+ (self.addendas_score or 0) * weights["addendas"]
				+ (self.global_invoices_score or 0) * weights["global_invoices"]
				+ (self.rules_compliance_score or 0) * weights["rules_compliance"]
			)

			self.overall_score = weighted_sum

	def calculate_custom_formula(self):
		"""Fórmula personalizada de cálculo"""
		# Implementación básica - puede ser extendida
		critical_modules = [self.timbrado_score or 0, self.ppd_score or 0]
		optional_modules = [
			self.ereceipts_score or 0,
			self.addendas_score or 0,
			self.global_invoices_score or 0,
		]

		# Los módulos críticos tienen mayor peso
		critical_avg = sum(critical_modules) / len(critical_modules)
		optional_avg = sum(optional_modules) / len(optional_modules)
		rules_score = self.rules_compliance_score or 0

		# Fórmula: 50% críticos + 25% opcionales + 25% reglas
		return (critical_avg * 0.5) + (optional_avg * 0.25) + (rules_score * 0.25)

	def generate_health_factors(self):
		"""Generar factores positivos y negativos basados en scores"""

		# Factores positivos
		if self.timbrado_score and self.timbrado_score >= 90:
			self.append(
				"factors_positive",
				{
					"factor_type": "Timbrado",
					"description": f"Excelente tasa de timbrado ({self.timbrado_score:.1f}%)",
					"impact_score": 5,
				},
			)

		if self.ppd_score and self.ppd_score >= 85:
			self.append(
				"factors_positive",
				{
					"factor_type": "PPD",
					"description": f"Buen cumplimiento de complementos PPD ({self.ppd_score:.1f}%)",
					"impact_score": 4,
				},
			)

		if self.rules_compliance_score and self.rules_compliance_score >= 95:
			self.append(
				"factors_positive",
				{
					"factor_type": "Cumplimiento",
					"description": f"Alto cumplimiento regulatorio ({self.rules_compliance_score:.1f}%)",
					"impact_score": 3,
				},
			)

		# Factores negativos
		if self.timbrado_score and self.timbrado_score < 70:
			self.append(
				"factors_negative",
				{
					"factor_type": "Timbrado",
					"description": f"Baja tasa de timbrado ({self.timbrado_score:.1f}%)",
					"impact_score": -8,
				},
			)

		if self.ppd_score and self.ppd_score < 60:
			self.append(
				"factors_negative",
				{
					"factor_type": "PPD",
					"description": f"Complementos PPD atrasados ({self.ppd_score:.1f}%)",
					"impact_score": -6,
				},
			)

		if self.overall_score < 60:
			self.append(
				"factors_negative",
				{
					"factor_type": "General",
					"description": "Score general bajo requiere atención inmediata",
					"impact_score": -10,
				},
			)

	def generate_recommendations(self):
		"""Generar recomendaciones basadas en los scores"""

		if self.timbrado_score and self.timbrado_score < 80:
			self.append(
				"recommendations",
				{
					"category": "Timbrado",
					"recommendation": "Revisar configuración del PAC y resolver errores de timbrado pendientes",
					"priority": "High",
					"estimated_days": 3,
				},
			)

		if self.ppd_score and self.ppd_score < 75:
			self.append(
				"recommendations",
				{
					"category": "PPD",
					"recommendation": "Implementar proceso automatizado para generación de complementos PPD",
					"priority": "High",
					"estimated_days": 7,
				},
			)

		if self.ereceipts_score and self.ereceipts_score < 85:
			self.append(
				"recommendations",
				{
					"category": "E-Receipts",
					"recommendation": "Optimizar proceso de generación de E-Receipts y reducir errores",
					"priority": "Medium",
					"estimated_days": 5,
				},
			)

		if self.overall_score < 70:
			self.append(
				"recommendations",
				{
					"category": "General",
					"recommendation": "Plan de mejora integral del sistema fiscal - revisar todos los módulos",
					"priority": "High",
					"estimated_days": 14,
				},
			)
		elif self.overall_score < 85:
			self.append(
				"recommendations",
				{
					"category": "General",
					"recommendation": "Optimizar procesos fiscales para alcanzar excelencia operacional",
					"priority": "Medium",
					"estimated_days": 10,
				},
			)

	@frappe.whitelist()
	def recalculate_score(self):
		"""Recalcular el score de salud fiscal"""
		self.calculate_health_score()
		self.save()
		return {
			"success": True,
			"message": _("Score de salud fiscal recalculado exitosamente"),
			"overall_score": self.overall_score,
		}


def create_health_score_for_company(company, score_date=None):
	"""Función utilitaria para crear score de salud para una empresa"""
	if not score_date:
		score_date = date.today()

	# Verificar si ya existe un score para esta fecha
	existing = frappe.db.exists("Fiscal Health Score", {"company": company, "score_date": score_date})

	if existing:
		return frappe.get_doc("Fiscal Health Score", existing)

	# Crear nuevo score
	health_score = frappe.new_doc("Fiscal Health Score")
	health_score.company = company
	health_score.score_date = score_date
	health_score.calculation_method = "Weighted Average"

	health_score.insert()
	return health_score


@frappe.whitelist()
def get_health_trend(company, months=6):
	"""Obtener tendencia de salud fiscal"""
	end_date = date.today()
	start_date = (
		date(end_date.year, end_date.month - months + 1, 1)
		if end_date.month > months
		else date(end_date.year - 1, 12 - (months - end_date.month) + 1, 1)
	)

	scores = frappe.db.get_all(
		"Fiscal Health Score",
		filters={"company": company, "score_date": ["between", [start_date, end_date]]},
		fields=["score_date", "overall_score"],
		order_by="score_date",
	)

	return {
		"success": True,
		"data": scores,
		"trend": calculate_trend(scores) if len(scores) >= 2 else "stable",
	}


def calculate_trend(scores):
	"""Calcular tendencia de scores"""
	if len(scores) < 2:
		return "stable"

	first_half = scores[: len(scores) // 2]
	second_half = scores[len(scores) // 2 :]

	avg_first = sum(s["overall_score"] for s in first_half) / len(first_half)
	avg_second = sum(s["overall_score"] for s in second_half) / len(second_half)

	if avg_second > avg_first + 5:
		return "improving"
	elif avg_second < avg_first - 5:
		return "declining"
	else:
		return "stable"
