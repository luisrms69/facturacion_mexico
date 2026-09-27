# Copyright (c) 2026, Buzola and contributors
"""Parser de REP (CFDI 4.0 tipo "P" + Complemento de Pago 2.0) — SOLO LECTURA.

Ningún parser existente maneja tipo "P" (`cfdi_recibidos` y `cfdi_emitidos` son solo "I").
Este parser lee la identidad del CFDI de pago, el nodo `pago20:Pago` y sus
`DoctoRelacionado` + impuestos, usando el helper seguro `secure_xml` (XXE-safe).

NO interpreta reglas fiscales ni escribe nada. NO deduce cancelación (ese estado viene de
una señal explícita del lote, no del XML).
"""

from facturacion_mexico.utils.secure_xml import secure_parse_xml

_NS_CFDI = "http://www.sat.gob.mx/cfd/4"
_NS_PAGO20 = "http://www.sat.gob.mx/Pagos20"
_NS_TFD = "http://www.sat.gob.mx/TimbreFiscalDigital"


def _ns_of(root):
	tag = root.tag if isinstance(root.tag, str) else ""
	return tag[tag.find("{") + 1 : tag.find("}")] if tag.startswith("{") else _NS_CFDI


def _txt(v):
	return (v or "").strip()


def parse_rep(raw: bytes) -> dict:
	"""Parsea un CFDI de pago (tipo P). Lanza ValueError si no es tipo P o falta estructura.

	Retorna dict con identidad, cfdi_relacionados (o None) y lista `pagos`.
	"""
	root = secure_parse_xml(raw, "lxml")
	ns = _ns_of(root)

	def q(name):
		return f"{{{ns}}}{name}"

	def qp(name):
		return f"{{{_NS_PAGO20}}}{name}"

	tipo = root.get("TipoDeComprobante", "")
	if tipo != "P":
		raise ValueError(f"CFDI no es tipo P (TipoDeComprobante={tipo!r})")

	emisor = root.find(q("Emisor"))
	receptor = root.find(q("Receptor"))
	if emisor is None or receptor is None:
		raise ValueError("CFDI de pago sin Emisor/Receptor")

	# TimbreFiscalDigital → UUID del REP
	tfd = root.find(f".//{{{_NS_TFD}}}TimbreFiscalDigital")
	uuid = _txt(tfd.get("UUID")) if tfd is not None else ""
	if not uuid:
		raise ValueError("CFDI de pago sin UUID (TimbreFiscalDigital)")

	# CfdiRelacionados (solo si viene; TipoRelacion 04 = sustitución)
	cfdi_rel = None
	rel = root.find(q("CfdiRelacionados"))
	if rel is not None:
		uuids = [_txt(r.get("UUID")) for r in rel.findall(q("CfdiRelacionado")) if _txt(r.get("UUID"))]
		cfdi_rel = {"tipo_relacion": _txt(rel.get("TipoRelacion")), "uuids": uuids}

	# Complemento → Pagos20 → Pago(s)
	pagos_node = root.find(f".//{qp('Pagos')}")
	if pagos_node is None:
		raise ValueError("CFDI de pago sin nodo pago20:Pagos")

	pagos = []
	for pago in pagos_node.findall(qp("Pago")):
		docs = []
		for dr in pago.findall(qp("DoctoRelacionado")):
			docs.append(
				{
					"id_documento": _txt(dr.get("IdDocumento")),
					"serie": _txt(dr.get("Serie")),
					"folio": _txt(dr.get("Folio")),
					"moneda_dr": _txt(dr.get("MonedaDR")),
					"equivalencia_dr": _txt(dr.get("EquivalenciaDR")) or "1",
					"num_parcialidad": _txt(dr.get("NumParcialidad")),
					"imp_saldo_ant": _txt(dr.get("ImpSaldoAnt")),
					"imp_pagado": _txt(dr.get("ImpPagado")),
					"imp_saldo_insoluto": _txt(dr.get("ImpSaldoInsoluto")),
					"objeto_imp_dr": _txt(dr.get("ObjetoImpDR")),
				}
			)
		pagos.append(
			{
				"fecha_pago": _txt(pago.get("FechaPago")),
				"forma_pago": _txt(pago.get("FormaDePagoP")),
				"moneda_p": _txt(pago.get("MonedaP")),
				"tipo_cambio_p": _txt(pago.get("TipoCambioP")) or "1",
				"monto": _txt(pago.get("Monto")),
				"num_operacion": _txt(pago.get("NumOperacion")),
				"rfc_emisor_cta_ord": _txt(pago.get("RfcEmisorCtaOrd")),
				"nom_banco_ord_ext": _txt(pago.get("NomBancoOrdExt")),
				"cta_ordenante": _txt(pago.get("CtaOrdenante")),
				"rfc_emisor_cta_ben": _txt(pago.get("RfcEmisorCtaBen")),
				"cta_beneficiario": _txt(pago.get("CtaBeneficiario")),
				"docs": docs,
				"impuestos_p": _parse_impuestos_p(pago, qp),
			}
		)

	return {
		"tipo": tipo,
		"version": root.get("Version", ""),
		"fecha": _txt(root.get("Fecha")),
		"lugar_expedicion": _txt(root.get("LugarExpedicion")),
		"emisor_rfc": _txt(emisor.get("Rfc")),
		"emisor_nombre": _txt(emisor.get("Nombre")),
		"receptor_rfc": _txt(receptor.get("Rfc")),
		"receptor_nombre": _txt(receptor.get("Nombre")),
		"uuid": uuid,
		"fecha_timbrado": _txt(tfd.get("FechaTimbrado")) if tfd is not None else "",
		"no_certificado_sat": _txt(tfd.get("NoCertificadoSAT")) if tfd is not None else "",
		"cfdi_relacionados": cfdi_rel,
		"pagos": pagos,
	}


def _parse_impuestos_p(pago, qp) -> list:
	"""Impuestos a nivel Pago (ImpuestosP → TrasladosP/RetencionesP). Lista de dicts, o []."""
	out = []
	imp = pago.find(qp("ImpuestosP"))
	if imp is None:
		return out
	for grupo, tipo in ((qp("TrasladosP"), "Traslado"), (qp("RetencionesP"), "Retencion")):
		cont = imp.find(grupo)
		if cont is None:
			continue
		child = qp("TrasladoP") if tipo == "Traslado" else qp("RetencionP")
		for t in cont.findall(child):
			out.append(
				{
					"tipo_impuesto": tipo,
					"impuesto": _txt(t.get("ImpuestoP")),
					"tipo_factor": _txt(t.get("TipoFactorP")),
					"tasa_cuota": _txt(t.get("TasaOCuotaP")),
					"base": _txt(t.get("BaseP")),
					"importe": _txt(t.get("ImporteP")),
				}
			)
	return out
