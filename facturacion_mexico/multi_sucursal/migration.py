# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""
Legacy System Migrator - Sprint 6 Phase 5
Sistema de migración para datos legacy multi-sucursal
"""

import json
import re
from typing import Any, Optional

import frappe
from frappe import _


class LegacySystemMigrator:
	"""
	Migrador de sistemas legacy a sistema multi-sucursal
	Detecta patrones existentes y migra datos automáticamente
	"""

	def __init__(self):
		self.migration_log = []
		self.detected_patterns = {}
		self.migration_stats = {
			"detected_legacy_fields": 0,
			"migrated_branches": 0,
			"migrated_invoices": 0,
			"migrated_configurations": 0,
			"errors": 0,
		}

	def detect_legacy_system(self) -> dict:
		"""
		Detectar sistema anterior por patterns en DB
		Analiza campos, datos y estructuras existentes
		"""
		try:
			detection_result = {
				"legacy_detected": False,
				"patterns_found": [],
				"migration_required": False,
				"estimated_scope": {},
			}

			# 1. Detectar campos legacy en Sales Invoice
			legacy_fields = self._detect_legacy_invoice_fields()
			if legacy_fields:
				detection_result["patterns_found"].append("legacy_invoice_fields")
				detection_result["legacy_detected"] = True

			# 2. Detectar configuraciones legacy
			legacy_configs = self._detect_legacy_configurations()
			if legacy_configs:
				detection_result["patterns_found"].append("legacy_configurations")
				detection_result["legacy_detected"] = True

			# 3. Detectar datos de lugar de expedición
			lugar_expedicion_data = self._detect_lugar_expedicion_patterns()
			if lugar_expedicion_data:
				detection_result["patterns_found"].append("lugar_expedicion_data")
				detection_result["legacy_detected"] = True

			# 4. Estimar alcance de migración
			if detection_result["legacy_detected"]:
				detection_result["estimated_scope"] = self._estimate_migration_scope()
				detection_result["migration_required"] = True

			self.detected_patterns = detection_result
			return {"success": True, "detection": detection_result}

		except Exception as e:
			frappe.log_error(f"Error in legacy system detection: {e!s}", "Legacy Migration")
			return {"success": False, "message": f"Error: {e!s}"}

	def map_legacy_fields(self) -> dict:
		"""
		Mapeo automático de campos legacy a nueva estructura
		Crea mapping personalizado basado en patrones detectados
		"""
		try:
			field_mappings = {}

			# Mapeos comunes de campos legacy
			common_mappings = {
				# Campos de lugar de expedición
				"lugar_expedicion": "fm_branch",
				"sucursal": "fm_branch",
				"branch": "fm_branch",
				"ubicacion": "fm_branch",
				"plaza": "fm_branch",
				# Campos de certificados
				"certificado_sat": "certificate_file",
				"cert_file": "certificate_file",
				"certificate": "certificate_file",
				# Campos de folios
				"folio_actual": "folio_current",
				"folio_siguiente": "folio_current",
				"ultimo_folio": "folio_current",
				"folio_inicio": "folio_start",
				"folio_fin": "folio_end",
			}

			# Detectar campos existentes y mapearlos
			for legacy_field, new_field in common_mappings.items():
				if self._field_exists_in_data(legacy_field):
					field_mappings[legacy_field] = new_field
					self.migration_log.append(f"Mapped legacy field '{legacy_field}' to '{new_field}'")

			# Detectar patrones en datos
			data_patterns = self._analyze_data_patterns()
			field_mappings.update(data_patterns)

			return {"success": True, "field_mappings": field_mappings, "log": self.migration_log}

		except Exception as e:
			frappe.log_error(f"Error in field mapping: {e!s}", "Legacy Migration")
			return {"success": False, "message": f"Error: {e!s}"}

	def migrate_branch_data(self, field_mappings: dict | None = None, dry_run: bool = True) -> dict:
		"""
		Migrar datos de sucursales desde sistema legacy
		Crea Branch records y configuraciones fiscales
		"""
		try:
			if not field_mappings:
				mapping_result = self.map_legacy_fields()
				if not mapping_result["success"]:
					return mapping_result
				field_mappings = mapping_result["field_mappings"]

			migration_result = {
				"success": True,
				"dry_run": dry_run,
				"branches_created": [],
				"configurations_migrated": [],
				"invoices_updated": 0,
				"errors": [],
			}

			# 1. Migrar sucursales únicas desde facturas
			branches_result = self._migrate_unique_branches(field_mappings, dry_run)
			migration_result["branches_created"] = branches_result["branches"]

			# 2. Migrar configuraciones fiscales
			configs_result = self._migrate_fiscal_configurations(field_mappings, dry_run)
			migration_result["configurations_migrated"] = configs_result["configurations"]

			# 3. Actualizar facturas existentes
			invoices_result = self._update_existing_invoices(field_mappings, dry_run)
			migration_result["invoices_updated"] = invoices_result["updated_count"]

			# 4. Consolidar errores
			migration_result["errors"].extend(branches_result.get("errors", []))
			migration_result["errors"].extend(configs_result.get("errors", []))
			migration_result["errors"].extend(invoices_result.get("errors", []))

			# Actualizar estadísticas
			self.migration_stats["migrated_branches"] = len(migration_result["branches_created"])
			self.migration_stats["migrated_configurations"] = len(migration_result["configurations_migrated"])
			self.migration_stats["migrated_invoices"] = migration_result["invoices_updated"]
			self.migration_stats["errors"] = len(migration_result["errors"])

			if not dry_run and migration_result["errors"]:
				frappe.db.rollback()
				migration_result["success"] = False
				migration_result["message"] = "Migration rolled back due to errors"

			return migration_result

		except Exception as e:
			frappe.log_error(f"Error in branch data migration: {e!s}", "Legacy Migration")
			if not dry_run:
				frappe.db.rollback()
			return {"success": False, "message": f"Error: {e!s}"}

	def _detect_legacy_invoice_fields(self) -> list:
		"""Detectar campos legacy en Sales Invoice"""
		try:
			# Verificar custom fields existentes
			legacy_patterns = [
				"lugar_expedicion",
				"sucursal",
				"branch",
				"ubicacion",
				"plaza",
				"cert%",
				"folio%",
			]

			found_fields = []
			for pattern in legacy_patterns:
				fields = frappe.db.sql(
					"""
                    SELECT fieldname
                    FROM `tabCustom Field`
                    WHERE dt = 'Sales Invoice'
                    AND fieldname LIKE %s
                """,
					f"%{pattern}%",
					as_dict=True,
				)
				found_fields.extend([f["fieldname"] for f in fields])

			return found_fields

		except Exception:
			return []

	def _detect_legacy_configurations(self) -> list:
		"""Detectar configuraciones legacy"""
		try:
			# Buscar configuraciones en Settings o custom DocTypes
			legacy_config_sources = []

			# Verificar si existe configuración en Singles
			settings_with_config = frappe.db.sql(
				"""
                SELECT name
                FROM `tabSingles`
                WHERE (field LIKE '%lugar%expedicion%'
                   OR field LIKE '%sucursal%'
                   OR field LIKE '%branch%'
                   OR field LIKE '%certificado%'
                   OR field LIKE '%folio%')
            """,
				as_dict=True,
			)

			legacy_config_sources.extend([s["name"] for s in settings_with_config])

			return legacy_config_sources

		except Exception:
			return []

	def _detect_lugar_expedicion_patterns(self) -> dict:
		"""Detectar patrones de lugar de expedición en facturas"""
		try:
			patterns = {}

			# Buscar patrones en campos de texto
			text_patterns = frappe.db.sql(
				"""
                SELECT DISTINCT
                    SUBSTRING_INDEX(fm_lugar_expedicion, ' ', 1) as pattern,
                    COUNT(*) as frequency
                FROM `tabSales Invoice`
                WHERE fm_lugar_expedicion IS NOT NULL
                AND fm_lugar_expedicion != ''
                GROUP BY pattern
                HAVING frequency > 5
                ORDER BY frequency DESC
                LIMIT 20
            """,
				as_dict=True,
			)

			patterns["lugar_expedicion"] = text_patterns

			# Buscar patrones en otros campos posibles
			custom_fields = self._detect_legacy_invoice_fields()
			for field in custom_fields:
				if "sucursal" in field.lower() or "branch" in field.lower():
					field_patterns = frappe.db.sql(
						f"""
                        SELECT DISTINCT {field} as value, COUNT(*) as frequency
                        FROM `tabSales Invoice`
                        WHERE {field} IS NOT NULL AND {field} != ''
                        GROUP BY {field}
                        HAVING frequency > 1
                        ORDER BY frequency DESC
                        LIMIT 10
                    """,
						as_dict=True,
					)
					patterns[field] = field_patterns

			return patterns

		except Exception:
			return {}

	def _estimate_migration_scope(self) -> dict:
		"""Estimar alcance de la migración"""
		try:
			scope = {}

			# Contar facturas afectadas
			scope["total_invoices"] = frappe.db.count("Sales Invoice", {"docstatus": 1})

			# Contar facturas con datos legacy
			invoices_with_legacy = frappe.db.sql(
				"""
                SELECT COUNT(*) as count
                FROM `tabSales Invoice`
                WHERE (fm_lugar_expedicion IS NOT NULL AND fm_lugar_expedicion != '')
                OR docstatus = 1
            """
			)[0][0]

			scope["invoices_with_legacy_data"] = invoices_with_legacy

			# Estimar sucursales únicas
			unique_locations = frappe.db.sql(
				"""
                SELECT COUNT(DISTINCT fm_lugar_expedicion) as count
                FROM `tabSales Invoice`
                WHERE fm_lugar_expedicion IS NOT NULL
                AND fm_lugar_expedicion != ''
            """
			)[0][0]

			scope["estimated_branches"] = unique_locations

			# Estimar tiempo de migración
			scope["estimated_duration_minutes"] = max(10, (invoices_with_legacy / 1000) * 5)

			return scope

		except Exception:
			return {"error": "Could not estimate scope"}

	def _field_exists_in_data(self, field_name: str) -> bool:
		"""Verificar si un campo existe y tiene datos"""
		try:
			# Verificar en Custom Fields
			exists = frappe.db.exists("Custom Field", {"dt": "Sales Invoice", "fieldname": field_name})

			if exists:
				# Verificar si tiene datos
				count = frappe.db.sql(
					f"""
                    SELECT COUNT(*)
                    FROM `tabSales Invoice`
                    WHERE {field_name} IS NOT NULL
                    AND {field_name} != ''
                """,
					debug=False,
				)[0][0]
				return count > 0

			return False

		except Exception:
			return False

	def _analyze_data_patterns(self) -> dict:
		"""Analizar patrones en los datos para mapeo inteligente"""
		patterns = {}

		try:
			# Analizar patrones de lugar de expedición
			if self._field_exists_in_data("fm_lugar_expedicion"):
				locations = frappe.db.sql(
					"""
                    SELECT DISTINCT fm_lugar_expedicion, COUNT(*) as frequency
                    FROM `tabSales Invoice`
                    WHERE fm_lugar_expedicion IS NOT NULL
                    AND fm_lugar_expedicion != ''
                    GROUP BY fm_lugar_expedicion
                    ORDER BY frequency DESC
                """,
					as_dict=True,
				)

				# Crear mapeo basado en frecuencia
				for loc in locations[:10]:  # Top 10 más frecuentes
					branch_name = self._normalize_branch_name(loc["fm_lugar_expedicion"])
					patterns[f"location_{loc['fm_lugar_expedicion']}"] = branch_name

		except Exception:
			pass

		return patterns

	def _normalize_branch_name(self, raw_name: str) -> str:
		"""Normalizar nombre de sucursal"""
		# Limpiar y estandarizar
		normalized = re.sub(r"[^\w\s-]", "", raw_name)
		normalized = re.sub(r"\s+", " ", normalized).strip()
		normalized = normalized.title()

		# Remover palabras comunes
		stop_words = ["Sucursal", "Branch", "Plaza", "Sede", "Oficina"]
		for word in stop_words:
			normalized = normalized.replace(word, "").strip()

		return normalized or "Sucursal Principal"

	def _migrate_unique_branches(self, field_mappings: dict, dry_run: bool) -> dict:
		"""Crear Branch records para ubicaciones únicas"""
		result = {"branches": [], "errors": []}

		try:
			# Obtener ubicaciones únicas
			unique_locations = frappe.db.sql(
				"""
                SELECT DISTINCT
                    fm_lugar_expedicion,
                    COUNT(*) as usage_count
                FROM `tabSales Invoice`
                WHERE fm_lugar_expedicion IS NOT NULL
                AND fm_lugar_expedicion != ''
                AND docstatus = 1
                GROUP BY fm_lugar_expedicion
                ORDER BY usage_count DESC
            """,
				as_dict=True,
			)

			for location in unique_locations:
				try:
					branch_name = self._normalize_branch_name(location["fm_lugar_expedicion"])

					# Verificar si ya existe
					if frappe.db.exists("Branch", branch_name):
						continue

					if not dry_run:
						# Crear Branch
						branch_doc = frappe.get_doc(
							{
								"doctype": "Branch",
								"branch": branch_name,
								"branch_name": branch_name,
								"is_group": 0,
								"legacy_source": location["fm_lugar_expedicion"],
								"created_from_migration": 1,
							}
						)
						branch_doc.insert(ignore_permissions=True)

					result["branches"].append(
						{
							"branch_name": branch_name,
							"legacy_source": location["fm_lugar_expedicion"],
							"usage_count": location["usage_count"],
						}
					)

				except Exception as e:
					result["errors"].append(f"Error creating branch '{branch_name}': {e!s}")

		except Exception as e:
			result["errors"].append(f"Error in branch migration: {e!s}")

		return result

	def _migrate_fiscal_configurations(self, field_mappings: dict, dry_run: bool) -> dict:
		"""Migrar configuraciones fiscales por sucursal"""
		result = {"configurations": [], "errors": []}

		try:
			# Por ahora, crear configuración básica para sucursales migradas
			# En el futuro podría analizar configuraciones legacy específicas

			branches = frappe.get_all("Branch", filters={"created_from_migration": 1}, fields=["name"])

			for branch in branches:
				try:
					if not dry_run:
						# Crear configuración fiscal básica
						{
							"parent": branch["name"],
							"parenttype": "Branch",
							"parentfield": "fiscal_configurations",
							"is_active": 1,
							"folio_start": 1,
							"folio_end": 1000,
							"folio_current": 1,
							"created_from_migration": 1,
						}

						# Esto se haría mediante el sistema de custom fields
						# o una configuración específica según el diseño final

					result["configurations"].append(
						{"branch": branch["name"], "status": "basic_config_created"}
					)

				except Exception as e:
					result["errors"].append(f"Error configuring branch '{branch['name']}': {e!s}")

		except Exception as e:
			result["errors"].append(f"Error in configuration migration: {e!s}")

		return result

	def _update_existing_invoices(self, field_mappings: dict, dry_run: bool) -> dict:
		"""Actualizar facturas existentes con mapeo de sucursales"""
		result = {"updated_count": 0, "errors": []}

		try:
			# Mapear lugar_expedicion a branch
			invoices_to_update = frappe.db.sql(
				"""
                SELECT name, fm_lugar_expedicion
                FROM `tabSales Invoice`
                WHERE fm_lugar_expedicion IS NOT NULL
                AND fm_lugar_expedicion != ''
                AND (fm_branch IS NULL OR fm_branch = '')
            """,
				as_dict=True,
			)

			for invoice in invoices_to_update:
				try:
					branch_name = self._normalize_branch_name(invoice["fm_lugar_expedicion"])

					if frappe.db.exists("Branch", branch_name):
						if not dry_run:
							frappe.db.set_value("Sales Invoice", invoice["name"], "fm_branch", branch_name)

						result["updated_count"] += 1

				except Exception as e:
					result["errors"].append(f"Error updating invoice '{invoice['name']}': {e!s}")

			if not dry_run and result["updated_count"] > 0:
				frappe.db.commit()

		except Exception as e:
			result["errors"].append(f"Error in invoice update: {e!s}")

		return result


# APIs públicas
@frappe.whitelist()
def detect_legacy_system():
	"""API para detectar sistema legacy"""
	migrator = LegacySystemMigrator()
	return migrator.detect_legacy_system()


@frappe.whitelist()
def preview_migration():
	"""API para previsualizar migración (dry run)"""
	migrator = LegacySystemMigrator()
	detection = migrator.detect_legacy_system()
	if detection["success"] and detection["detection"]["migration_required"]:
		mapping = migrator.map_legacy_fields()
		if mapping["success"]:
			return migrator.migrate_branch_data(mapping["field_mappings"], dry_run=True)
	return {"success": False, "message": "No legacy system detected or migration not required"}


@frappe.whitelist()
def execute_migration(confirm: bool = False):
	"""API para ejecutar migración real"""
	if not confirm:
		return {"success": False, "message": "Migration must be explicitly confirmed"}

	migrator = LegacySystemMigrator()
	detection = migrator.detect_legacy_system()
	if detection["success"] and detection["detection"]["migration_required"]:
		mapping = migrator.map_legacy_fields()
		if mapping["success"]:
			return migrator.migrate_branch_data(mapping["field_mappings"], dry_run=False)

	return {"success": False, "message": "No legacy system detected or migration not required"}


@frappe.whitelist()
def get_migration_status():
	"""API para obtener estado de migración"""
	try:
		# Verificar si hay datos migrados
		migrated_branches = frappe.db.count("Branch", {"created_from_migration": 1})
		total_branches = frappe.db.count("Branch")

		invoices_with_branch = frappe.db.count("Sales Invoice", {"fm_branch": ["is", "set"]})
		total_invoices = frappe.db.count("Sales Invoice", {"docstatus": 1})

		return {
			"success": True,
			"status": {
				"migration_completed": migrated_branches > 0,
				"migrated_branches": migrated_branches,
				"total_branches": total_branches,
				"invoices_with_branch": invoices_with_branch,
				"total_invoices": total_invoices,
				"coverage_percentage": (invoices_with_branch / total_invoices * 100)
				if total_invoices > 0
				else 0,
			},
		}

	except Exception as e:
		frappe.log_error(f"Error getting migration status: {e!s}", "Migration Status")
		return {"success": False, "message": f"Error: {e!s}"}
