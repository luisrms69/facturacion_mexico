# Copyright (c) 2026, Buzola and contributors
"""Parser genérico de CFDI 4.0 de Ingreso (emitido) para importación a Sales Invoice.

Extrae la cabecera y los conceptos necesarios para construir una Sales Invoice
histórica. NO reserializa el XML: los bytes originales son la evidencia (hash y
attachment) y se conservan aparte por el llamador.

Módulo genérico de `facturacion_mexico`: no contiene datos de ningún cliente.
"""

import hashlib
import xml.etree.ElementTree as ET

CFDI_NS = "http://www.sat.gob.mx/cfd/4"
TFD_NS = "http://www.sat.gob.mx/TimbreFiscalDigital"
_NS = {"cfdi": CFDI_NS, "tfd": TFD_NS}


class CFDIError(Exception):
	"""El archivo no es un CFDI 4.0 legible o le falta información esencial."""


def normalize_uuid(value):
	"""Representación canónica del UUID: mayúsculas, sin espacios.

	Misma normalización que usa la capa fiscal (`registrar_cfdi_externo`) para que
	ambas compartan la misma llave (Folio Fiscal SAT = UUID).
	"""
	return (str(value).strip().upper()) if value not in (None, "") else ""


def sha256_hex(raw_bytes):
	return hashlib.sha256(raw_bytes).hexdigest()


def _num(x):
	try:
		return float(x) if x not in (None, "") else 0.0
	except (TypeError, ValueError):
		return 0.0


def parse_cfdi(raw_bytes):
	"""Parsea los bytes originales de un CFDI 4.0. Lanza CFDIError si no es válido."""
	try:
		root = ET.fromstring(raw_bytes)
	except ET.ParseError as exc:
		raise CFDIError(f"XML ilegible: {exc}") from exc
	if root.tag != f"{{{CFDI_NS}}}Comprobante":
		raise CFDIError(f"Raíz no es Comprobante CFDI 4.0: {root.tag}")
	tfd = root.find(".//tfd:TimbreFiscalDigital", _NS)
	uuid = normalize_uuid(tfd.get("UUID")) if tfd is not None else ""
	if not uuid:
		raise CFDIError("CFDI sin TimbreFiscalDigital/UUID")
	receptor = root.find("cfdi:Receptor", _NS)
	emisor = root.find("cfdi:Emisor", _NS)
	imp = root.find("cfdi:Impuestos", _NS)
	conceptos = []
	for i, c in enumerate(root.findall("cfdi:Conceptos/cfdi:Concepto", _NS), 1):
		conceptos.append(
			{
				"idx": i,
				"noid": (c.get("NoIdentificacion") or "").strip(),
				"descripcion": c.get("Descripcion") or "",
				"clave_prod_serv": c.get("ClaveProdServ"),
				"clave_unidad": c.get("ClaveUnidad"),
				"cantidad": _num(c.get("Cantidad")),
				"valor_unitario": _num(c.get("ValorUnitario")),
				"importe": _num(c.get("Importe")),
				"descuento": _num(c.get("Descuento")),
				"objeto_imp": c.get("ObjetoImp"),
			}
		)
	return {
		"uuid": uuid,
		"serie": root.get("Serie"),
		"folio": root.get("Folio"),
		"fecha": root.get("Fecha"),
		"fecha_timbrado": tfd.get("FechaTimbrado") if tfd is not None else None,
		"tipo": root.get("TipoDeComprobante"),
		"moneda": root.get("Moneda"),
		"tipo_cambio": root.get("TipoCambio"),
		"metodo_pago": root.get("MetodoPago"),
		"forma_pago": root.get("FormaPago"),
		"lugar_expedicion": root.get("LugarExpedicion"),
		"uso_cfdi": receptor.get("UsoCFDI") if receptor is not None else None,
		"receptor_rfc": normalize_uuid(receptor.get("Rfc")) if receptor is not None else "",
		"receptor_nombre": receptor.get("Nombre") if receptor is not None else None,
		"receptor_num_reg_id_trib": (receptor.get("NumRegIdTrib") or "").strip()
		if receptor is not None
		else "",
		"receptor_residencia_fiscal": (receptor.get("ResidenciaFiscal") or "").strip().upper()
		if receptor is not None
		else "",
		"emisor_rfc": normalize_uuid(emisor.get("Rfc")) if emisor is not None else "",
		"subtotal": _num(root.get("SubTotal")),
		"descuento": _num(root.get("Descuento")),
		"total": _num(root.get("Total")),
		"total_traslados": _num(imp.get("TotalImpuestosTrasladados")) if imp is not None else 0.0,
		"total_retenciones": _num(imp.get("TotalImpuestosRetenidos")) if imp is not None else 0.0,
		"conceptos": conceptos,
	}


def is_ingreso(cfdi):
	return (cfdi.get("tipo") or "").strip().upper() == "I"
