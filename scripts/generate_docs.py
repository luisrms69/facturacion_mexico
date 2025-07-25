#!/usr/bin/env python3
"""
Script de generación automática de documentación API para Frappe Apps.

Este script escanea la estructura de la app Frappe y genera documentación
automática usando mkdocstrings.
"""

import ast
import json
import os
import sys
from pathlib import Path
from typing import Any


def scan_python_files(app_path: str) -> list[str]:
	"""Escanea archivos Python en la app."""
	python_files = []
	app_dir = Path(app_path)

	for py_file in app_dir.rglob("*.py"):
		# Excluir archivos de test y setup
		if any(exclude in str(py_file) for exclude in ["test_", "__pycache__", "setup.py"]):
			continue
		python_files.append(str(py_file))

	return python_files


def analyze_module(file_path: str) -> dict[str, Any]:
	"""Analiza un módulo Python y extrae información."""
	try:
		with open(file_path, encoding="utf-8") as f:
			content = f.read()

		tree = ast.parse(content)

		module_info = {
			"file_path": file_path,
			"functions": [],
			"classes": [],
			"docstring": ast.get_docstring(tree),
			"has_frappe_import": "import frappe" in content,
		}

		for node in ast.walk(tree):
			if isinstance(node, ast.FunctionDef):
				func_info = {
					"name": node.name,
					"docstring": ast.get_docstring(node),
					"args": [arg.arg for arg in node.args.args],
					"is_public": not node.name.startswith("_"),
					"line_number": node.lineno,
				}
				module_info["functions"].append(func_info)

			elif isinstance(node, ast.ClassDef):
				class_info = {
					"name": node.name,
					"docstring": ast.get_docstring(node),
					"methods": [],
					"is_public": not node.name.startswith("_"),
					"line_number": node.lineno,
				}

				for item in node.body:
					if isinstance(item, ast.FunctionDef):
						method_info = {
							"name": item.name,
							"docstring": ast.get_docstring(item),
							"is_public": not item.name.startswith("_"),
						}
						class_info["methods"].append(method_info)

				module_info["classes"].append(class_info)

		return module_info

	except Exception as e:
		print(f"Error analizando {file_path}: {e}")
		return None


def generate_api_docs(app_name: str, app_path: str) -> None:
	"""Genera documentación API automática."""

	# Crear directorios
	docs_dir = Path(app_path) / "docs" / "api"
	docs_dir.mkdir(parents=True, exist_ok=True)

	# Escanear archivos Python
	python_files = scan_python_files(app_path)
	print(f"📁 Encontrados {len(python_files)} archivos Python")

	# Categorizar módulos
	module_categories = {"doctypes": [], "hooks": [], "api": [], "reports": [], "utils": [], "other": []}

	for py_file in python_files:
		module_info = analyze_module(py_file)
		if not module_info:
			continue

		# Categorizar basado en el path
		rel_path = os.path.relpath(py_file, app_path)

		if "doctype" in rel_path:
			module_categories["doctypes"].append((rel_path, module_info))
		elif "hooks" in rel_path or py_file.endswith("hooks.py"):
			module_categories["hooks"].append((rel_path, module_info))
		elif "report" in rel_path:
			module_categories["reports"].append((rel_path, module_info))
		elif "api" in rel_path or any(func["name"].startswith("api_") for func in module_info["functions"]):
			module_categories["api"].append((rel_path, module_info))
		elif "utils" in rel_path or "utilities" in rel_path:
			module_categories["utils"].append((rel_path, module_info))
		elif module_info["has_frappe_import"] and (module_info["functions"] or module_info["classes"]):
			module_categories["other"].append((rel_path, module_info))

	# Generar documentación por categoría
	generate_doctypes_docs(docs_dir, module_categories["doctypes"], app_name)
	generate_hooks_docs(docs_dir, module_categories["hooks"], app_name)
	generate_api_docs_files(docs_dir, module_categories["api"], app_name)
	generate_reports_docs(docs_dir, module_categories["reports"], app_name)
	generate_utils_docs(docs_dir, module_categories["utils"], app_name)
	generate_other_docs(docs_dir, module_categories["other"], app_name)

	# Generar índice principal
	generate_api_index(docs_dir, module_categories, app_name)

	print("✅ Documentación API generada automáticamente")


def generate_doctypes_docs(docs_dir: Path, doctypes: list[tuple], app_name: str) -> None:
	"""Genera documentación de DocTypes."""
	if not doctypes:
		return

	doctypes_dir = docs_dir / "doctypes"
	doctypes_dir.mkdir(exist_ok=True)

	# Índice de DocTypes
	index_content = f"""# DocTypes - {app_name}

Documentación automática de los DocTypes del sistema.

## DocTypes Disponibles

"""

	for rel_path, module_info in doctypes:
		doctype_name = extract_doctype_name(rel_path)
		if doctype_name:
			index_content += f"- **[{doctype_name}]({doctype_name.lower().replace(' ', '_')}.md)**: "
			index_content += f"{module_info['docstring'] or 'DocType personalizado'}\n"

			# Generar archivo individual
			generate_doctype_file(doctypes_dir, doctype_name, rel_path, module_info, app_name)

	with open(doctypes_dir / "index.md", "w", encoding="utf-8") as f:
		f.write(index_content)


def generate_doctype_file(
	docs_dir: Path, doctype_name: str, rel_path: str, module_info: dict[str, Any], app_name: str
) -> None:
	"""Genera archivo de documentación para un DocType específico."""

	filename = doctype_name.lower().replace(" ", "_") + ".md"
	module_path = rel_path.replace("/", ".").replace(".py", "")

	content = f"""# {doctype_name}

{module_info['docstring'] or f'Documentación del DocType {doctype_name}'}

## Controlador

::: {app_name}.{module_path}
    options:
      show_source: true
      show_root_heading: false
      show_root_toc_entry: false
      docstring_style: google
      merge_init_into_class: true

"""

	# Agregar información de métodos si existen
	if module_info["classes"]:
		content += "## Métodos Principales\n\n"
		for class_info in module_info["classes"]:
			if class_info["is_public"]:
				content += f"### {class_info['name']}\n\n"
				if class_info["docstring"]:
					content += f"{class_info['docstring']}\n\n"

				for method in class_info["methods"]:
					if method["is_public"] and method["docstring"]:
						content += f"#### `{method['name']}`\n\n{method['docstring']}\n\n"

	with open(docs_dir / filename, "w", encoding="utf-8") as f:
		f.write(content)


def extract_doctype_name(rel_path: str) -> str:
	"""Extrae el nombre del DocType del path."""
	parts = rel_path.split("/")
	for part in parts:
		if part not in ["doctype", "__init__.py"] and not part.endswith(".py"):
			return part.replace("_", " ").title()
	return None


def generate_hooks_docs(docs_dir: Path, hooks: list[tuple], app_name: str) -> None:
	"""Genera documentación de Hooks."""
	if not hooks:
		return

	content = f"""# Hooks - {app_name}

Documentación de los hooks y eventos del sistema.

## Hooks Configurados

"""

	for rel_path, _module_info in hooks:
		module_path = rel_path.replace("/", ".").replace(".py", "")
		content += f"""
### {rel_path}

::: {app_name}.{module_path}
    options:
      show_source: true
      show_root_heading: false
      docstring_style: google

"""

	with open(docs_dir / "hooks.md", "w", encoding="utf-8") as f:
		f.write(content)


def generate_api_docs_files(docs_dir: Path, api_modules: list[tuple], app_name: str) -> None:
	"""Genera documentación de API endpoints."""
	if not api_modules:
		return

	content = f"""# API Endpoints - {app_name}

Documentación de los endpoints de API disponibles.

## Endpoints Disponibles

"""

	for rel_path, _module_info in api_modules:
		module_path = rel_path.replace("/", ".").replace(".py", "")
		content += f"""
### {rel_path}

::: {app_name}.{module_path}
    options:
      show_source: false
      show_root_heading: false
      docstring_style: google
      filters:
        - "!^_"

"""

	with open(docs_dir / "endpoints.md", "w", encoding="utf-8") as f:
		f.write(content)


def generate_reports_docs(docs_dir: Path, reports: list[tuple], app_name: str) -> None:
	"""Genera documentación de Reports."""
	if not reports:
		return

	content = f"""# Reports - {app_name}

Documentación de los reportes del sistema.

## Reportes Disponibles

"""

	for rel_path, _module_info in reports:
		module_path = rel_path.replace("/", ".").replace(".py", "")
		content += f"""
### {rel_path}

::: {app_name}.{module_path}
    options:
      show_source: false
      show_root_heading: false
      docstring_style: google

"""

	with open(docs_dir / "reports.md", "w", encoding="utf-8") as f:
		f.write(content)


def generate_utils_docs(docs_dir: Path, utils: list[tuple], app_name: str) -> None:
	"""Genera documentación de Utilidades."""
	if not utils:
		return

	content = f"""# Utilidades - {app_name}

Documentación de funciones de utilidad y helpers.

## Módulos de Utilidad

"""

	for rel_path, _module_info in utils:
		module_path = rel_path.replace("/", ".").replace(".py", "")
		content += f"""
### {rel_path}

::: {app_name}.{module_path}
    options:
      show_source: true
      show_root_heading: false
      docstring_style: google
      filters:
        - "!^_"

"""

	with open(docs_dir / "utils.md", "w", encoding="utf-8") as f:
		f.write(content)


def generate_other_docs(docs_dir: Path, other_modules: list[tuple], app_name: str) -> None:
	"""Genera documentación de otros módulos."""
	if not other_modules:
		return

	content = f"""# Otros Módulos - {app_name}

Documentación de módulos adicionales del sistema.

"""

	for rel_path, _module_info in other_modules:
		module_path = rel_path.replace("/", ".").replace(".py", "")
		content += f"""
## {rel_path}

::: {app_name}.{module_path}
    options:
      show_source: false
      show_root_heading: false
      docstring_style: google
      filters:
        - "!^_"

"""

	with open(docs_dir / "other.md", "w", encoding="utf-8") as f:
		f.write(content)


def generate_api_index(docs_dir: Path, categories: dict[str, Any], app_name: str) -> None:
	"""Genera índice principal de la documentación API."""

	content = f"""# API Reference - {app_name}

Documentación completa de la API del sistema generada automáticamente.

## 📊 Estadísticas

"""

	total_modules = sum(len(modules) for modules in categories.values())
	content += f"- **Total de módulos documentados**: {total_modules}\n"

	for category, modules in categories.items():
		if modules:
			content += f"- **{category.title()}**: {len(modules)} módulos\n"

	content += "\n## 📂 Categorías\n\n"

	if categories["doctypes"]:
		content += "### [DocTypes](doctypes/index.md)\n"
		content += "Modelos de datos y controladores personalizados.\n\n"

	if categories["hooks"]:
		content += "### [Hooks](hooks.md)\n"
		content += "Event handlers y integraciones con Frappe.\n\n"

	if categories["api"]:
		content += "### [API Endpoints](endpoints.md)\n"
		content += "Endpoints REST y funciones whitelisted.\n\n"

	if categories["reports"]:
		content += "### [Reports](reports.md)\n"
		content += "Reportes y consultas especializadas.\n\n"

	if categories["utils"]:
		content += "### [Utilidades](utils.md)\n"
		content += "Funciones auxiliares y helpers.\n\n"

	if categories["other"]:
		content += "### [Otros Módulos](other.md)\n"
		content += "Módulos adicionales del sistema.\n\n"

	content += """
---

!!! info "Generación Automática"
    Esta documentación se genera automáticamente desde los docstrings del código fuente.
    Para actualizar, ejecuta: `python scripts/generate_docs.py`

!!! tip "Contribuir"
    Para mejorar esta documentación, agrega o mejora los docstrings en el código fuente usando el formato Google Style.
"""

	with open(docs_dir / "index.md", "w", encoding="utf-8") as f:
		f.write(content)


def main():
	"""Función principal del script."""

	# Detectar app automáticamente
	current_dir = os.getcwd()
	app_name = os.path.basename(current_dir)

	print(f"🔍 Generando documentación para la app: {app_name}")
	print(f"📁 Directorio: {current_dir}")

	# Verificar que estamos en una app Frappe
	if not os.path.exists("hooks.py"):
		print("❌ Error: No se encontró hooks.py. ¿Estás en el directorio de una app Frappe?")
		sys.exit(1)

	# Generar documentación
	generate_api_docs(app_name, current_dir)

	print(f"✅ Documentación generada para {app_name}")
	print("📖 Archivos creados en docs/api/")


if __name__ == "__main__":
	main()
