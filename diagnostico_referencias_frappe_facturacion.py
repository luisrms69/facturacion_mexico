# apps/facturacion_mexico/diagnostico_referencias_frappe_facturacion.py

import json
import os

import frappe

APP_PATH = frappe.get_app_path("facturacion_mexico")
RESULTADOS = []


def buscar_en_archivo(filepath):
	resultados = []
	try:
		with open(filepath, "r", encoding="utf-8") as f:
			contenido = f.read()
			if "frappe.facturacion_mexico" in contenido:
				resultados.append(filepath)
	except Exception as e:
		resultados.append(f"{filepath} (ERROR AL LEER: {e})")
	return resultados


def main():
	global RESULTADOS
	extensiones = (".json", ".py", ".txt", ".md", ".js", ".ts", ".html")

	for root, dirs, files in os.walk(APP_PATH):
		for file in files:
			if file.endswith(extensiones):
				full_path = os.path.join(root, file)
				encontrados = buscar_en_archivo(full_path)
				if encontrados:
					RESULTADOS.extend(encontrados)

	if RESULTADOS:
		print("\n🔎 Referencias encontradas a 'frappe.facturacion_mexico':\n")
		for r in RESULTADOS:
			print(f"❌ {r}")
		frappe.msgprint(f"🚨 Se encontraron {len(RESULTADOS)} archivos con referencias erróneas.")
	else:
		print("✅ No se encontraron referencias a 'frappe.facturacion_mexico'.")
		frappe.msgprint("✅ Sin referencias incorrectas detectadas.")
