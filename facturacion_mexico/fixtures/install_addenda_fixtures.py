"""
Installer de Fixtures para Addendas - Sprint 3
Script para instalar fixtures de Liverpool y Generic addenda types
"""

import json
import os
from typing import Any

import frappe
from frappe import _


class AddendaFixtureInstaller:
	"""Instalador de fixtures para el sistema de addendas."""

	def __init__(self):
		self.fixtures_path = os.path.dirname(os.path.abspath(__file__))
		self.installed_fixtures = []
		self.errors = []

	def install_all_fixtures(self, force_reinstall: bool = False) -> dict:
		"""Instalar todos los fixtures de addendas."""
		print("🚀 Iniciando instalación de fixtures de addendas...")

		results = {"success": True, "installed": [], "skipped": [], "errors": [], "summary": {}}

		# Orden de instalación (dependencias)
		fixture_order = [
			"addenda_fixtures.json",  # Addenda Types primero
			"addenda_field_definitions.json",  # Luego Field Definitions
			"addenda_templates.json",  # Finalmente Templates
		]

		for fixture_file in fixture_order:
			try:
				result = self.install_fixture_file(fixture_file, force_reinstall)
				results["installed"].extend(result["installed"])
				results["skipped"].extend(result["skipped"])
				results["errors"].extend(result["errors"])

			except Exception as e:
				error_msg = f"Error instalando {fixture_file}: {e!s}"
				results["errors"].append(error_msg)
				print(f"❌ {error_msg}")

		# Generar resumen
		results["summary"] = {
			"total_installed": len(results["installed"]),
			"total_skipped": len(results["skipped"]),
			"total_errors": len(results["errors"]),
		}

		results["success"] = len(results["errors"]) == 0

		self.print_installation_summary(results)
		return results

	def install_fixture_file(self, filename: str, force_reinstall: bool = False) -> dict:
		"""Instalar un archivo de fixtures específico."""
		filepath = os.path.join(self.fixtures_path, filename)

		if not os.path.exists(filepath):
			raise FileNotFoundError(f"Archivo de fixtures no encontrado: {filename}")

		print(f"📦 Instalando fixtures desde: {filename}")

		with open(filepath, encoding="utf-8") as f:
			fixtures_data = json.load(f)

		results = {"installed": [], "skipped": [], "errors": []}

		for fixture in fixtures_data:
			try:
				result = self.install_single_fixture(fixture, force_reinstall)

				if result["action"] == "installed":
					results["installed"].append(result["name"])
					print(f"  ✅ Instalado: {result['name']}")
				elif result["action"] == "updated":
					results["installed"].append(result["name"])
					print(f"  🔄 Actualizado: {result['name']}")
				elif result["action"] == "skipped":
					results["skipped"].append(result["name"])
					print(f"  ⏭️ Omitido: {result['name']}")

			except Exception as e:
				error_msg = f"Error en {fixture.get('name', 'Unknown')}: {e!s}"
				results["errors"].append(error_msg)
				print(f"  ❌ {error_msg}")

		return results

	def install_single_fixture(self, fixture_data: dict, force_reinstall: bool = False) -> dict:
		"""Instalar un fixture individual."""
		doctype = fixture_data.get("doctype")
		name = fixture_data.get("name")

		if not doctype or not name:
			raise ValueError("Fixture debe tener 'doctype' y 'name'")

		# Verificar si ya existe
		exists = frappe.db.exists(doctype, name)

		if exists and not force_reinstall:
			return {"action": "skipped", "name": name}

		try:
			if exists:
				# Actualizar documento existente
				doc = frappe.get_doc(doctype, name)
				doc.update(fixture_data)
				doc.save(ignore_permissions=True)
				action = "updated"
			else:
				# Crear nuevo documento
				doc = frappe.get_doc(fixture_data)
				doc.insert(ignore_permissions=True)
				action = "installed"

			frappe.db.commit()
			return {"action": action, "name": name}

		except Exception as e:
			frappe.db.rollback()
			raise e

	def validate_fixtures(self) -> dict:
		"""Validar que todos los fixtures estén correctamente instalados."""
		print("🔍 Validando fixtures instalados...")

		validation_results = {
			"valid": True,
			"addenda_types": {},
			"field_definitions": {},
			"templates": {},
			"errors": [],
		}

		# Validar Addenda Types
		expected_types = ["Generic", "Liverpool"]
		for addenda_type in expected_types:
			try:
				doc = frappe.get_doc("Addenda Type", addenda_type)
				validation_results["addenda_types"][addenda_type] = {
					"exists": True,
					"is_active": doc.is_active,
					"has_xsd": bool(doc.xsd_schema),
					"has_sample": bool(doc.xml_sample),
				}
				print(f"  ✅ Addenda Type '{addenda_type}' válido")
			except frappe.DoesNotExistError:
				validation_results["addenda_types"][addenda_type] = {"exists": False}
				validation_results["errors"].append(f"Addenda Type '{addenda_type}' no encontrado")
				print(f"  ❌ Addenda Type '{addenda_type}' no encontrado")

		# Validar Field Definitions
		for addenda_type in expected_types:
			if validation_results["addenda_types"][addenda_type].get("exists"):
				try:
					doc = frappe.get_doc("Addenda Type", addenda_type)
					field_count = len(doc.field_definitions) if hasattr(doc, "field_definitions") else 0
					validation_results["field_definitions"][addenda_type] = {
						"count": field_count,
						"has_definitions": field_count > 0,
					}
					print(f"  ✅ {field_count} definiciones de campo para '{addenda_type}'")
				except Exception as e:
					validation_results["errors"].append(
						f"Error validando field definitions para {addenda_type}: {e!s}"
					)

		# Validar Templates
		for addenda_type in expected_types:
			try:
				templates = frappe.get_all(
					"Addenda Template", filters={"addenda_type": addenda_type}, fields=["name", "is_default"]
				)

				default_templates = [t for t in templates if t.is_default]

				validation_results["templates"][addenda_type] = {
					"total_count": len(templates),
					"default_count": len(default_templates),
					"has_default": len(default_templates) > 0,
				}

				if len(default_templates) > 0:
					print(
						f"  ✅ {len(templates)} templates para '{addenda_type}' (default: {len(default_templates)})"
					)
				else:
					validation_results["errors"].append(f"No hay template por defecto para '{addenda_type}'")
					print(f"  ⚠️ {len(templates)} templates para '{addenda_type}' pero sin default")

			except Exception as e:
				validation_results["errors"].append(f"Error validando templates para {addenda_type}: {e!s}")

		validation_results["valid"] = len(validation_results["errors"]) == 0

		if validation_results["valid"]:
			print("🎉 Todos los fixtures están correctamente instalados y validados")
		else:
			print(f"❌ Validación falló con {len(validation_results['errors'])} errores")

		return validation_results

	def uninstall_fixtures(self) -> dict:
		"""Desinstalar todos los fixtures de addendas (para testing/desarrollo)."""
		print("🗑️ Desinstalando fixtures de addendas...")

		results = {"success": True, "removed": [], "errors": []}

		# Orden inverso para respetar dependencias
		removal_order = [
			("Addenda Template", ["Generic-Default", "Liverpool-Default", "Generic-Simple"]),
			("Addenda Field Definition", None),  # Eliminar todos los field definitions
			("Addenda Type", ["Generic", "Liverpool"]),
		]

		for doctype, names in removal_order:
			try:
				if names is None:
					# Eliminar todos los documentos del tipo
					all_docs = frappe.get_all(doctype, pluck="name")
					names = all_docs

				for name in names:
					try:
						if frappe.db.exists(doctype, name):
							frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
							results["removed"].append(f"{doctype}: {name}")
							print(f"  🗑️ Eliminado: {doctype} - {name}")
					except Exception as e:
						error_msg = f"Error eliminando {doctype} '{name}': {e!s}"
						results["errors"].append(error_msg)
						print(f"  ❌ {error_msg}")

			except Exception as e:
				error_msg = f"Error procesando {doctype}: {e!s}"
				results["errors"].append(error_msg)
				print(f"❌ {error_msg}")

		# Manual commit required for batch fixture uninstallation to ensure data persistence
		frappe.db.commit()  # nosemgrep

		results["success"] = len(results["errors"]) == 0
		print(
			f"✅ Desinstalación completada. Eliminados: {len(results['removed'])}, Errores: {len(results['errors'])}"
		)

		return results

	def print_installation_summary(self, results: dict):
		"""Imprimir resumen de la instalación."""
		print("\n" + "=" * 60)
		print("📋 RESUMEN DE INSTALACIÓN DE FIXTURES")
		print("=" * 60)

		summary = results["summary"]
		print(f"✅ Instalados: {summary['total_installed']}")
		print(f"⏭️ Omitidos: {summary['total_skipped']}")
		print(f"❌ Errores: {summary['total_errors']}")

		if results["success"]:
			print("\n🎉 ¡INSTALACIÓN EXITOSA!")
		else:
			print(f"\n💥 INSTALACIÓN FALLÓ CON {summary['total_errors']} ERRORES")
			print("\nErrores:")
			for error in results["errors"]:
				print(f"  - {error}")

		print("=" * 60)

	def create_sample_configuration(self, customer_name: str, addenda_type: str = "Generic") -> str:
		"""Crear configuración de muestra para testing."""
		print(f"🧪 Creando configuración de muestra para cliente '{customer_name}'...")

		# Verificar que el cliente existe
		if not frappe.db.exists("Customer", customer_name):
			raise ValueError(f"Cliente '{customer_name}' no existe")

		# Verificar que el tipo de addenda existe
		if not frappe.db.exists("Addenda Type", addenda_type):
			raise ValueError(f"Tipo de addenda '{addenda_type}' no existe")

		try:
			config = frappe.get_doc(
				{
					"doctype": "Addenda Configuration",
					"customer": customer_name,
					"addenda_type": addenda_type,
					"is_active": 1,
					"priority": 1,
					"auto_apply": 1,
					"validation_level": "Warning",
					"effective_date": frappe.utils.today(),
					"notify_on_error": 0,
				}
			)

			config.insert(ignore_permissions=True)
			frappe.db.commit()

			print(f"✅ Configuración de muestra creada: {config.name}")
			return config.name

		except Exception as e:
			frappe.db.rollback()
			raise e


def install_addenda_fixtures(force_reinstall: bool = False) -> dict:
	"""Función pública para instalar fixtures."""
	installer = AddendaFixtureInstaller()
	return installer.install_all_fixtures(force_reinstall)


def validate_addenda_fixtures() -> dict:
	"""Función pública para validar fixtures."""
	installer = AddendaFixtureInstaller()
	return installer.validate_fixtures()


def uninstall_addenda_fixtures() -> dict:
	"""Función pública para desinstalar fixtures."""
	installer = AddendaFixtureInstaller()
	return installer.uninstall_fixtures()


# Funciones para hooks de instalación
def after_install():
	"""Hook que se ejecuta después de la instalación de la app."""
	try:
		print("🔧 Ejecutando post-instalación de fixtures de addendas...")
		result = install_addenda_fixtures()

		if result["success"]:
			print("✅ Fixtures de addendas instalados correctamente")
		else:
			print("⚠️ Algunos fixtures de addendas no se pudieron instalar")

	except Exception as e:
		print(f"❌ Error en post-instalación de fixtures: {e!s}")


def after_migrate():
	"""Hook que se ejecuta después de migraciones."""
	try:
		print("🔄 Actualizando fixtures de addendas después de migración...")
		result = install_addenda_fixtures(force_reinstall=True)

		if result["success"]:
			print("✅ Fixtures de addendas actualizados correctamente")

	except Exception as e:
		print(f"❌ Error actualizando fixtures después de migración: {e!s}")


if __name__ == "__main__":
	# Ejecutar directamente
	installer = AddendaFixtureInstaller()
	installer.install_all_fixtures()
	installer.validate_fixtures()
