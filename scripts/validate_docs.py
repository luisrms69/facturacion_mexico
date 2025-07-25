#!/usr/bin/env python3
"""
Script de validación completa del sistema de documentación.

Valida la integridad, calidad y funcionalidad de toda la documentación.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import markdown
import yaml


class DocumentationValidator:
	"""Validador completo de documentación."""

	def __init__(self, project_root: str):
		self.project_root = Path(project_root)
		self.docs_dir = self.project_root / "docs"
		self.errors = []
		self.warnings = []
		self.stats = {
			"total_files": 0,
			"valid_files": 0,
			"broken_links": 0,
			"missing_images": 0,
			"orphaned_files": 0,
		}

	def validate_all(self) -> bool:
		"""Ejecuta todas las validaciones."""
		print("🔍 Iniciando validación completa de documentación...")

		# Validaciones principales
		self.validate_structure()
		self.validate_mkdocs_config()
		self.validate_markdown_files()
		self.validate_links()
		self.validate_images()
		self.validate_code_blocks()
		self.validate_navigation()
		self.check_build_process()

		# Generar reporte
		self.generate_report()

		return len(self.errors) == 0

	def validate_structure(self):
		"""Valida la estructura de directorios."""
		print("📁 Validando estructura de directorios...")

		required_dirs = [
			"docs",
			"docs/user-guide",
			"docs/api",
			"docs/development",
			"docs/assets",
			"docs/assets/stylesheets",
			"docs/assets/javascripts",
		]

		for dir_path in required_dirs:
			full_path = self.project_root / dir_path
			if not full_path.exists():
				self.errors.append(f"Directorio requerido faltante: {dir_path}")
			elif not full_path.is_dir():
				self.errors.append(f"No es un directorio: {dir_path}")

		# Verificar archivos clave
		required_files = ["mkdocs.yml", "requirements-docs.txt", "docs/index.md"]

		for file_path in required_files:
			full_path = self.project_root / file_path
			if not full_path.exists():
				self.errors.append(f"Archivo requerido faltante: {file_path}")
			elif not full_path.is_file():
				self.errors.append(f"No es un archivo: {file_path}")

	def validate_mkdocs_config(self):
		"""Valida el archivo mkdocs.yml."""
		print("⚙️ Validando configuración MkDocs...")

		mkdocs_file = self.project_root / "mkdocs.yml"
		if not mkdocs_file.exists():
			self.errors.append("mkdocs.yml no encontrado")
			return

		try:
			with open(mkdocs_file, encoding="utf-8") as f:
				config = yaml.safe_load(f)

			# Validar campos requeridos
			required_fields = ["site_name", "nav", "theme"]
			for field in required_fields:
				if field not in config:
					self.errors.append(f"Campo requerido faltante en mkdocs.yml: {field}")

			# Validar tema Material
			if config.get("theme", {}).get("name") != "material":
				self.warnings.append("Se recomienda usar Material theme")

			# Validar navegación
			nav = config.get("nav", [])
			if not nav:
				self.errors.append("Navegación vacía en mkdocs.yml")
			else:
				self.validate_nav_structure(nav)

		except yaml.YAMLError as e:
			self.errors.append(f"Error en mkdocs.yml: {e}")
		except Exception as e:
			self.errors.append(f"Error leyendo mkdocs.yml: {e}")

	def validate_nav_structure(self, nav: list[Any]):
		"""Valida la estructura de navegación."""
		for item in nav:
			if isinstance(item, dict):
				for _key, value in item.items():
					if isinstance(value, str):
						# Es un archivo
						file_path = self.docs_dir / value
						if not file_path.exists():
							self.errors.append(f"Archivo referenciado en nav no existe: {value}")
					elif isinstance(value, list):
						# Es una sección con subsecciones
						self.validate_nav_structure(value)

	def validate_markdown_files(self):
		"""Valida todos los archivos Markdown."""
		print("📝 Validando archivos Markdown...")

		md_files = list(self.docs_dir.rglob("*.md"))
		self.stats["total_files"] = len(md_files)

		for md_file in md_files:
			try:
				with open(md_file, encoding="utf-8") as f:
					content = f.read()

				# Validar sintaxis Markdown
				try:
					markdown.markdown(content)
					self.stats["valid_files"] += 1
				except Exception as e:
					self.errors.append(
						f"Error de sintaxis Markdown en {md_file.relative_to(self.project_root)}: {e}"
					)

				# Validar frontmatter
				self.validate_frontmatter(md_file, content)

				# Validar estructura de headers
				self.validate_headers(md_file, content)

				# Validar contenido en español
				self.validate_language(md_file, content)

			except Exception as e:
				self.errors.append(f"Error leyendo {md_file.relative_to(self.project_root)}: {e}")

	def validate_frontmatter(self, file_path: Path, content: str):
		"""Valida el frontmatter YAML."""
		if content.startswith("---"):
			try:
				end_marker = content.find("---", 3)
				if end_marker > 0:
					frontmatter = content[3:end_marker].strip()
					yaml.safe_load(frontmatter)
			except yaml.YAMLError as e:
				self.warnings.append(
					f"Frontmatter inválido en {file_path.relative_to(self.project_root)}: {e}"
				)

	def validate_headers(self, file_path: Path, content: str):
		"""Valida la estructura de headers."""
		headers = re.findall(r"^(#{1,6})\s+(.+)$", content, re.MULTILINE)

		if not headers:
			self.warnings.append(f"Sin headers en {file_path.relative_to(self.project_root)}")
			return

		# Verificar que comience con H1
		first_header_level = len(headers[0][0])
		if first_header_level != 1:
			self.warnings.append(f"Debería comenzar con H1 en {file_path.relative_to(self.project_root)}")

		# Verificar jerarquía de headers
		prev_level = 0
		for header_marks, header_text in headers:
			level = len(header_marks)

			if level > prev_level + 1:
				self.warnings.append(
					f"Salto de nivel de header en {file_path.relative_to(self.project_root)}: {header_text}"
				)

			prev_level = level

	def validate_language(self, file_path: Path, content: str):
		"""Valida que el contenido esté principalmente en español."""
		# Contar palabras en inglés vs español (heurística simple)
		english_indicators = ["the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"]
		spanish_indicators = [
			"el",
			"la",
			"los",
			"las",
			"de",
			"del",
			"en",
			"con",
			"por",
			"para",
			"que",
			"es",
			"está",
		]

		words = re.findall(r"\b\w+\b", content.lower())

		english_count = sum(1 for word in words if word in english_indicators)
		spanish_count = sum(1 for word in words if word in spanish_indicators)

		if english_count > spanish_count and len(words) > 50:
			self.warnings.append(
				f"Contenido parece estar en inglés en {file_path.relative_to(self.project_root)}"
			)

	def validate_links(self):
		"""Valida todos los enlaces internos y externos."""
		print("🔗 Validando enlaces...")

		md_files = list(self.docs_dir.rglob("*.md"))

		for md_file in md_files:
			try:
				with open(md_file, encoding="utf-8") as f:
					content = f.read()

				# Encontrar enlaces Markdown
				links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)

				for link_text, link_url in links:
					self.validate_single_link(md_file, link_text, link_url)

			except Exception as e:
				self.errors.append(
					f"Error validando enlaces en {md_file.relative_to(self.project_root)}: {e}"
				)

	def validate_single_link(self, source_file: Path, link_text: str, link_url: str):
		"""Valida un enlace específico."""
		# Ignorar enlaces externos por ahora (requeriría requests)
		if link_url.startswith(("http://", "https://", "mailto:", "tel:")):
			return

		# Enlaces de anclaje
		if link_url.startswith("#"):
			return

		# Enlaces relativos
		if link_url.startswith("./") or not link_url.startswith("/"):
			target_path = source_file.parent / link_url
		else:
			target_path = self.docs_dir / link_url.lstrip("/")

		# Resolver path
		try:
			target_path = target_path.resolve()
		except Exception:
			self.errors.append(f"Enlace inválido en {source_file.relative_to(self.project_root)}: {link_url}")
			return

		if not target_path.exists():
			self.errors.append(f"Enlace roto en {source_file.relative_to(self.project_root)}: {link_url}")
			self.stats["broken_links"] += 1

	def validate_images(self):
		"""Valida todas las imágenes referenciadas."""
		print("🖼️ Validando imágenes...")

		md_files = list(self.docs_dir.rglob("*.md"))

		for md_file in md_files:
			try:
				with open(md_file, encoding="utf-8") as f:
					content = f.read()

				# Encontrar referencias de imágenes
				images = re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", content)

				for _alt_text, img_url in images:
					if not img_url.startswith(("http://", "https://")):
						# Imagen local
						if img_url.startswith("./") or not img_url.startswith("/"):
							img_path = md_file.parent / img_url
						else:
							img_path = self.docs_dir / img_url.lstrip("/")

						try:
							img_path = img_path.resolve()
							if not img_path.exists():
								self.errors.append(
									f"Imagen faltante en {md_file.relative_to(self.project_root)}: {img_url}"
								)
								self.stats["missing_images"] += 1
						except Exception:
							self.errors.append(
								f"Path de imagen inválido en {md_file.relative_to(self.project_root)}: {img_url}"
							)

			except Exception as e:
				self.errors.append(
					f"Error validando imágenes en {md_file.relative_to(self.project_root)}: {e}"
				)

	def validate_code_blocks(self):
		"""Valida bloques de código."""
		print("💻 Validando bloques de código...")

		md_files = list(self.docs_dir.rglob("*.md"))

		for md_file in md_files:
			try:
				with open(md_file, encoding="utf-8") as f:
					content = f.read()

				# Encontrar bloques de código con ```
				code_blocks = re.findall(r"```(\w+)?\n(.*?)\n```", content, re.DOTALL)

				for language, code in code_blocks:
					if language == "python":
						self.validate_python_code(md_file, code)
					elif language in ["bash", "sh"]:
						self.validate_bash_code(md_file, code)

			except Exception as e:
				self.errors.append(f"Error validando código en {md_file.relative_to(self.project_root)}: {e}")

	def validate_python_code(self, source_file: Path, code: str):
		"""Valida sintaxis de código Python."""
		try:
			compile(code, f"<{source_file.name}>", "exec")
		except SyntaxError as e:
			self.warnings.append(
				f"Error de sintaxis Python en {source_file.relative_to(self.project_root)}: {e}"
			)

	def validate_bash_code(self, source_file: Path, code: str):
		"""Valida sintaxis básica de código Bash."""
		# Validaciones básicas de bash
		lines = code.strip().split("\n")
		for line_num, line in enumerate(lines, 1):
			line = line.strip()
			if not line or line.startswith("#"):
				continue

			# Verificar comandos peligrosos
			dangerous_commands = ["rm -rf /", "format", "fdisk"]
			for cmd in dangerous_commands:
				if cmd in line:
					self.warnings.append(
						f"Comando peligroso en {source_file.relative_to(self.project_root)} línea {line_num}: {cmd}"
					)

	def validate_navigation(self):
		"""Valida que todos los archivos estén en la navegación."""
		print("🧭 Validando navegación...")

		# Cargar navegación de mkdocs.yml
		mkdocs_file = self.project_root / "mkdocs.yml"
		if not mkdocs_file.exists():
			return

		with open(mkdocs_file, encoding="utf-8") as f:
			config = yaml.safe_load(f)

		nav_files = self.extract_nav_files(config.get("nav", []))

		# Encontrar todos los archivos .md
		all_md_files = set()
		for md_file in self.docs_dir.rglob("*.md"):
			rel_path = md_file.relative_to(self.docs_dir)
			all_md_files.add(str(rel_path))

		# Excluir archivos que no deberían estar en nav
		excluded_patterns = ["audit/", "README.md", ".pages"]
		nav_files_set = set(nav_files)

		for md_file in all_md_files:
			if not any(pattern in md_file for pattern in excluded_patterns):
				if md_file not in nav_files_set:
					self.warnings.append(f"Archivo no incluido en navegación: {md_file}")
					self.stats["orphaned_files"] += 1

	def extract_nav_files(self, nav: list[Any]) -> list[str]:
		"""Extrae todos los archivos referenciados en la navegación."""
		files = []

		for item in nav:
			if isinstance(item, str):
				files.append(item)
			elif isinstance(item, dict):
				for _key, value in item.items():
					if isinstance(value, str):
						files.append(value)
					elif isinstance(value, list):
						files.extend(self.extract_nav_files(value))

		return files

	def check_build_process(self):
		"""Verifica que la documentación se pueda construir."""
		print("🔨 Verificando proceso de build...")

		try:
			# Intentar build con mkdocs
			result = subprocess.run(
				["mkdocs", "build", "--strict"], capture_output=True, text=True, cwd=self.project_root
			)

			if result.returncode != 0:
				self.errors.append(f"Error en build de MkDocs: {result.stderr}")
			else:
				print("✅ Build exitoso")

		except FileNotFoundError:
			self.warnings.append("MkDocs no está instalado para verificar build")
		except Exception as e:
			self.errors.append(f"Error ejecutando build: {e}")

	def generate_report(self):
		"""Genera reporte final de validación."""
		print("\n" + "=" * 60)
		print("📊 REPORTE DE VALIDACIÓN DE DOCUMENTACIÓN")
		print("=" * 60)

		print("\n📁 Estadísticas:")
		print(f"   Total archivos MD: {self.stats['total_files']}")
		print(f"   Archivos válidos: {self.stats['valid_files']}")
		print(f"   Enlaces rotos: {self.stats['broken_links']}")
		print(f"   Imágenes faltantes: {self.stats['missing_images']}")
		print(f"   Archivos huérfanos: {self.stats['orphaned_files']}")

		if self.errors:
			print(f"\n❌ ERRORES ({len(self.errors)}):")
			for i, error in enumerate(self.errors, 1):
				print(f"   {i}. {error}")

		if self.warnings:
			print(f"\n⚠️  ADVERTENCIAS ({len(self.warnings)}):")
			for i, warning in enumerate(self.warnings, 1):
				print(f"   {i}. {warning}")

		if not self.errors and not self.warnings:
			print("\n✅ ¡DOCUMENTACIÓN PERFECTA!")
			print("   No se encontraron errores ni advertencias.")
		elif not self.errors:
			print("\n✅ DOCUMENTACIÓN VÁLIDA")
			print("   Se encontraron advertencias pero no errores críticos.")
		else:
			print("\n❌ DOCUMENTACIÓN CON ERRORES")
			print("   Se deben corregir los errores antes del despliegue.")

		print("\n" + "=" * 60)

		# Guardar reporte en archivo
		report_file = self.project_root / "docs" / "audit" / "validation_report.md"
		self.save_report_to_file(report_file)

	def save_report_to_file(self, report_file: Path):
		"""Guarda el reporte en un archivo Markdown."""
		report_file.parent.mkdir(parents=True, exist_ok=True)

		with open(report_file, "w", encoding="utf-8") as f:
			f.write("# Reporte de Validación de Documentación\n\n")
			f.write(f"**Fecha:** {self._get_timestamp()}\n")
			f.write("**Proyecto:** Facturación México\n\n")

			f.write("## 📊 Estadísticas\n\n")
			f.write(f"- **Total archivos MD:** {self.stats['total_files']}\n")
			f.write(f"- **Archivos válidos:** {self.stats['valid_files']}\n")
			f.write(f"- **Enlaces rotos:** {self.stats['broken_links']}\n")
			f.write(f"- **Imágenes faltantes:** {self.stats['missing_images']}\n")
			f.write(f"- **Archivos huérfanos:** {self.stats['orphaned_files']}\n\n")

			if self.errors:
				f.write(f"## ❌ Errores ({len(self.errors)})\n\n")
				for i, error in enumerate(self.errors, 1):
					f.write(f"{i}. {error}\n")
				f.write("\n")

			if self.warnings:
				f.write(f"## ⚠️ Advertencias ({len(self.warnings)})\n\n")
				for i, warning in enumerate(self.warnings, 1):
					f.write(f"{i}. {warning}\n")
				f.write("\n")

			status = "✅ VÁLIDA" if not self.errors else "❌ CON ERRORES"
			f.write(f"## Estado Final: {status}\n\n")

			if not self.errors and not self.warnings:
				f.write("🎉 **¡Documentación perfecta!** No se encontraron errores ni advertencias.\n")
			elif not self.errors:
				f.write("✅ **Documentación válida** con advertencias menores.\n")
			else:
				f.write("❌ **Se deben corregir los errores** antes del despliegue.\n")

		print(f"📄 Reporte guardado en: {report_file}")

	def _get_timestamp(self) -> str:
		"""Obtiene timestamp actual."""
		from datetime import datetime

		return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def main():
	"""Función principal."""

	# Detectar directorio del proyecto
	current_dir = os.getcwd()

	print(f"🔍 Validando documentación en: {current_dir}")

	# Crear validador
	validator = DocumentationValidator(current_dir)

	# Ejecutar validación
	is_valid = validator.validate_all()

	# Exit code
	sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
	main()
