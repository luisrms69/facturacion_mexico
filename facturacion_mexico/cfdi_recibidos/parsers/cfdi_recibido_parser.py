"""
Parser de CFDI Recibidos — extrae datos fiscales de un XML CFDI 4.0.

Clase independiente. Reutiliza utils/secure_xml.py para parseo seguro.
No hereda del parser de addendas/emisión (propósito distinto).
Solo soporta CFDI versión 4.0.
"""

import json
from typing import Any

import frappe
from frappe import _

from facturacion_mexico.utils.secure_xml import secure_parse_xml, validate_xml_size

# Namespaces estándar CFDI 4.0
NS_CFDI = "http://www.sat.gob.mx/cfd/4"
NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"

NAMESPACES = {
	"cfdi": NS_CFDI,
	"tfd": NS_TFD,
}

SUPPORTED_VERSION = "4.0"


class CFDIRecibidoParser:
	"""
	Parsea un XML CFDI recibido y extrae todos los datos fiscales.

	Uso:
	    parser = CFDIRecibidoParser(xml_bytes)
	    data = parser.parse()

	Lanza frappe.ValidationError si la versión no es 4.0 o el XML es inválido.
	"""

	def __init__(self, xml_content: bytes | str):
		if isinstance(xml_content, str):
			xml_content = xml_content.encode("utf-8")
		validate_xml_size(xml_content, max_size_mb=5)
		self._root = secure_parse_xml(xml_content, parser_type="lxml")
		self._ns = self._build_namespaces()

	def _build_namespaces(self) -> dict:
		"""Construye mapa de namespaces tolerando variaciones de emisor."""
		ns = dict(NAMESPACES)
		nsmap = getattr(self._root, "nsmap", {})
		if None in nsmap:
			ns["cfdi"] = nsmap[None]
		for prefix, uri in nsmap.items():
			if prefix and "TimbreFiscalDigital" in uri:
				ns["tfd"] = uri
		return ns

	# ------------------------------------------------------------------
	# Método público principal
	# ------------------------------------------------------------------

	def parse(self) -> dict[str, Any]:
		"""
		Extrae todos los datos fiscales del XML.
		Retorna dict listo para poblar CFDI Recibido + lista de conceptos.
		"""
		self._validate_version()

		root = self._root
		timbre = self._parse_timbre()
		emisor = self._parse_emisor()
		receptor = self._parse_receptor()
		conceptos, impuestos_json, totales_imp = self._parse_conceptos_e_impuestos()

		return {
			# Identificación fiscal
			"uuid": timbre.get("uuid", ""),
			"version": root.get("Version", ""),
			"cfdi_type": root.get("TipoDeComprobante", ""),
			"serie": root.get("Serie", ""),
			"folio": root.get("Folio", ""),
			"issue_date": self._parse_date(root.get("Fecha", "")),
			# Moneda
			"currency": root.get("Moneda", "MXN"),
			"exchange_rate": float(root.get("TipoCambio", "1") or "1"),
			# Pago SAT (datos fiscales del XML)
			"fm_payment_method_sat": root.get("MetodoPago", ""),
			"fm_payment_form_sat": root.get("FormaPago", ""),
			# Totales
			"subtotal": float(root.get("SubTotal", "0") or "0"),
			"discount": float(root.get("Descuento", "0") or "0"),
			"total": float(root.get("Total", "0") or "0"),
			"total_impuestos_trasladados": totales_imp["trasladados"],
			"total_impuestos_retenidos": totales_imp["retenidos"],
			"impuestos_json": json.dumps(impuestos_json, ensure_ascii=False),
			# Emisor
			"supplier_rfc": emisor.get("rfc", ""),
			"supplier_name": emisor.get("nombre", ""),
			"supplier_tax_regime": emisor.get("regimen", ""),
			# Receptor
			"receiver_rfc": receptor.get("rfc", ""),
			"receiver_name": receptor.get("nombre", ""),
			"uso_cfdi": receptor.get("uso_cfdi", ""),
			# Timbre
			"fecha_timbrado": timbre.get("fecha_timbrado", ""),
			"rfc_pac": timbre.get("rfc_pac", ""),
			"no_certificado_sat": timbre.get("no_certificado_sat", ""),
			"no_certificado_emisor": root.get("NoCertificado", ""),
			# Conceptos (lista de dicts)
			"conceptos": conceptos,
		}

	# ------------------------------------------------------------------
	# Validaciones
	# ------------------------------------------------------------------

	def _validate_version(self):
		version = self._root.get("Version", "")
		if version != SUPPORTED_VERSION:
			frappe.throw(
				_("CFDI versión {0} no soportada. Solo se aceptan CFDIs versión 4.0.").format(
					version or "desconocida"
				),
				frappe.ValidationError,
			)

	# ------------------------------------------------------------------
	# Sub-parsers
	# ------------------------------------------------------------------

	def _parse_timbre(self) -> dict:
		"""Extrae datos del nodo TimbreFiscalDigital."""
		ns = self._ns
		tfd = self._root.find(
			".//cfdi:Complemento/tfd:TimbreFiscalDigital",
			namespaces=ns,
		)
		# Fallback: buscar por URI explícita si el prefix varió
		if tfd is None:
			tfd = self._root.find(f"{{{NS_TFD}}}TimbreFiscalDigital")

		if tfd is None:
			return {}

		return {
			"uuid": tfd.get("UUID", ""),
			"fecha_timbrado": tfd.get("FechaTimbrado", ""),
			"rfc_pac": tfd.get("RfcProvCertif", ""),
			"no_certificado_sat": tfd.get("NoCertificadoSAT", ""),
		}

	def _parse_emisor(self) -> dict:
		emisor = self._root.find("cfdi:Emisor", namespaces=self._ns)
		if emisor is None:
			return {}
		return {
			"rfc": emisor.get("Rfc", ""),
			"nombre": emisor.get("Nombre", ""),
			"regimen": emisor.get("RegimenFiscal", ""),
		}

	def _parse_receptor(self) -> dict:
		receptor = self._root.find("cfdi:Receptor", namespaces=self._ns)
		if receptor is None:
			return {}
		return {
			"rfc": receptor.get("Rfc", ""),
			"nombre": receptor.get("Nombre", ""),
			"uso_cfdi": receptor.get("UsoCFDI", ""),
		}

	def _parse_conceptos_e_impuestos(self) -> tuple[list, dict, dict]:
		"""
		Extrae conceptos y construye impuestos_json global.
		Retorna (conceptos, impuestos_json, totales_dict).
		"""
		ns = self._ns
		conceptos_node = self._root.find("cfdi:Conceptos", namespaces=ns)
		conceptos = []

		if conceptos_node is not None:
			for concepto_node in conceptos_node.findall("cfdi:Concepto", namespaces=ns):
				conceptos.append(self._parse_concepto(concepto_node))

		# Impuestos a nivel de comprobante
		impuestos_node = self._root.find("cfdi:Impuestos", namespaces=ns)
		impuestos_json, totales = self._parse_impuestos_node(impuestos_node)

		return conceptos, impuestos_json, totales

	def _parse_concepto(self, node) -> dict:
		imp_node = node.find("cfdi:Impuestos", namespaces=self._ns)
		taxes_json, _ = self._parse_impuestos_node(imp_node)

		return {
			"sat_product_key": node.get("ClaveProdServ", ""),
			"no_identificacion": node.get("NoIdentificacion", ""),
			"description": node.get("Descripcion", ""),
			"quantity": float(node.get("Cantidad", "0") or "0"),
			"unit_key": node.get("ClaveUnidad", ""),
			"unit": node.get("Unidad", ""),
			"unit_price": float(node.get("ValorUnitario", "0") or "0"),
			"amount": float(node.get("Importe", "0") or "0"),
			"discount": float(node.get("Descuento", "0") or "0"),
			"tax_object": node.get("ObjetoImp", ""),
			"taxes_json": json.dumps(taxes_json, ensure_ascii=False),
		}

	def _parse_impuestos_node(self, node) -> tuple[dict, dict]:
		"""
		Parsea nodo cfdi:Impuestos.
		Retorna (impuestos_dict, {trasladados: float, retenidos: float}).
		"""
		if node is None:
			return {}, {"trasladados": 0.0, "retenidos": 0.0}

		ns = self._ns
		impuestos: dict[str, list] = {"traslados": [], "retenciones": []}
		total_trasladados = float(node.get("TotalImpuestosTrasladados", "0") or "0")
		total_retenidos = float(node.get("TotalImpuestosRetenidos", "0") or "0")

		traslados_node = node.find("cfdi:Traslados", namespaces=ns)
		if traslados_node is not None:
			for t in traslados_node.findall("cfdi:Traslado", namespaces=ns):
				impuestos["traslados"].append(
					{
						"impuesto": t.get("Impuesto", ""),
						"tipo_factor": t.get("TipoFactor", ""),
						"tasa_cuota": t.get("TasaOCuota", ""),
						"base": float(t.get("Base", "0") or "0"),
						"importe": float(t.get("Importe", "0") or "0"),
					}
				)

		retenciones_node = node.find("cfdi:Retenciones", namespaces=ns)
		if retenciones_node is not None:
			for r in retenciones_node.findall("cfdi:Retencion", namespaces=ns):
				impuestos["retenciones"].append(
					{
						"impuesto": r.get("Impuesto", ""),
						"tipo_factor": r.get("TipoFactor", ""),
						"tasa_cuota": r.get("TasaOCuota", ""),
						"base": float(r.get("Base", "0") or "0"),
						"importe": float(r.get("Importe", "0") or "0"),
					}
				)

		return impuestos, {"trasladados": total_trasladados, "retenidos": total_retenidos}

	@staticmethod
	def _parse_date(date_str: str) -> str:
		"""Convierte '2025-11-15T12:00:00' → '2025-11-15'."""
		if not date_str:
			return ""
		return date_str[:10]
