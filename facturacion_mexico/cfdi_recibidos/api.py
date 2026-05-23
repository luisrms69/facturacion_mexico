"""
API pública de CFDI Recibidos — Fase 1.

Endpoints:
    upload_xml — carga uno o varios XMLs CFDI y los persiste como CFDI Recibido.
"""

import frappe
from frappe import _

from facturacion_mexico.cfdi_recibidos.services.xml_ingestion import ingest_xml


@frappe.whitelist()
def upload_xml(company: str) -> list[dict]:
	"""
	Carga uno o varios XMLs CFDI 4.0 y los procesa como CFDI Recibido.

	Parámetros (form-data):
	    company   — nombre de la empresa en ERPNext
	    files     — uno o más archivos XML (campo "files" o "file")

	Retorna lista de resultados por archivo:
	    file_name     — nombre del archivo recibido
	    status        — "ok" | "duplicado" | "error"
	    cfdi_recibido — nombre del doc creado (None si duplicado sin doc nuevo)
	    uuid          — UUID extraído del XML
	    message       — descripción del resultado
	"""
	if not company:
		frappe.throw(_("El campo 'company' es obligatorio"), frappe.MandatoryError)

	# Frappe expone archivos subidos en frappe.request.files
	files = frappe.request.files
	if not files:
		frappe.throw(_("No se recibieron archivos XML"), frappe.ValidationError)

	results = []

	# Soporta campo "files" (múltiples) o "file" (singular)
	file_list = files.getlist("files") or files.getlist("file") or list(files.values())

	for uploaded_file in file_list:
		file_name = getattr(uploaded_file, "filename", "cfdi.xml") or "cfdi.xml"
		try:
			xml_bytes = uploaded_file.read()
			result = ingest_xml(xml_bytes, company, file_name=file_name)
		except Exception as e:
			result = {
				"status": "error",
				"cfdi_recibido": None,
				"uuid": None,
				"message": str(e),
			}

		results.append({"file_name": file_name, **result})

	return results
