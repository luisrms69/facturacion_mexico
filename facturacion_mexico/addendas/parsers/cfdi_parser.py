"""
CFDI Parser - Sprint 3
Parser para extraer datos de CFDI y encontrar puntos de inserción para addendas
"""

import frappe
from frappe import _
from lxml import etree

from facturacion_mexico.utils.secure_xml import secure_parse_xml, validate_xml_size


class CFDIParser:
	"""Parser para documentos CFDI 4.0."""

	def __init__(self, xml_content):
		"""Inicializar con contenido XML del CFDI."""
		self.xml_content = xml_content
		self.root = None
		self.namespaces = {}
		self._parse_xml()

	def _parse_xml(self):
		"""Parsear el XML y extraer namespaces."""
		try:
			# Validar tamaño del XML
			validate_xml_size(self.xml_content, max_size_mb=5)

			# Usar parsing seguro para evitar XXE
			self.root = secure_parse_xml(self.xml_content, parser_type="lxml")

			# Extraer namespaces
			self.namespaces = self.root.nsmap.copy()

			# Asegurar namespace por defecto
			if None in self.namespaces:
				self.namespaces["cfdi"] = self.namespaces[None]
				del self.namespaces[None]

			# Agregar namespaces comunes si no existen
			if "cfdi" not in self.namespaces:
				self.namespaces["cfdi"] = "http://www.sat.gob.mx/cfd/4"

		except Exception as e:
			frappe.throw(_("Error al parsear XML CFDI: {0}").format(str(e)))

	def get_insert_point(self):
		"""Encontrar el punto de inserción para la addenda."""
		try:
			# La addenda debe ir después de los complementos y antes del cierre
			# Buscar la estructura correcta según CFDI 4.0

			# Punto 1: Después de Complemento (si existe)
			complemento = self.root.find(".//cfdi:Complemento", self.namespaces)
			if complemento is not None:
				return complemento.getparent(), complemento.getparent().index(complemento) + 1

			# Punto 2: Después de Conceptos
			conceptos = self.root.find(".//cfdi:Conceptos", self.namespaces)
			if conceptos is not None:
				return conceptos.getparent(), conceptos.getparent().index(conceptos) + 1

			# Punto 3: Como último recurso, antes del cierre del elemento raíz
			return self.root, len(self.root)

		except Exception as e:
			frappe.throw(_("Error al encontrar punto de inserción: {0}").format(str(e)))

	def insert_addenda(self, addenda_xml):
		"""Insertar addenda en el CFDI."""
		try:
			# Parsear la addenda
			addenda_element = secure_parse_xml(addenda_xml, parser_type="lxml")

			# Encontrar punto de inserción
			parent, index = self.get_insert_point()

			# Crear elemento Addenda si no existe
			addenda_container = parent.find(".//cfdi:Addenda", self.namespaces)
			if addenda_container is None:
				addenda_container = etree.Element(etree.QName(self.namespaces["cfdi"], "Addenda"))
				parent.insert(index, addenda_container)

			# Insertar contenido de addenda
			addenda_container.append(addenda_element)

			# Retornar XML modificado
			return etree.tostring(self.root, encoding="unicode", pretty_print=True, xml_declaration=True)

		except Exception as e:
			frappe.throw(_("Error al insertar addenda: {0}").format(str(e)))

	def get_cfdi_data(self):
		"""Extraer datos del CFDI para variables de template."""
		try:
			data = {}

			# Datos del comprobante principal
			comprobante = self.root
			data.update(
				{
					"cfdi_uuid": self._get_uuid(),
					"cfdi_version": comprobante.get("Version", ""),
					"cfdi_serie": comprobante.get("Serie", ""),
					"cfdi_folio": comprobante.get("Folio", ""),
					"cfdi_fecha": comprobante.get("Fecha", ""),
					"cfdi_tipo_comprobante": comprobante.get("TipoDeComprobante", ""),
					"cfdi_forma_pago": comprobante.get("FormaPago", ""),
					"cfdi_metodo_pago": comprobante.get("MetodoPago", ""),
					"cfdi_moneda": comprobante.get("Moneda", "MXN"),
					"cfdi_tipo_cambio": comprobante.get("TipoCambio", "1"),
					"cfdi_subtotal": comprobante.get("SubTotal", "0"),
					"cfdi_descuento": comprobante.get("Descuento", "0"),
					"cfdi_total": comprobante.get("Total", "0"),
				}
			)

			# Datos del emisor
			emisor = self.root.find(".//cfdi:Emisor", self.namespaces)
			if emisor is not None:
				data.update(
					{
						"emisor_rfc": emisor.get("Rfc", ""),
						"emisor_nombre": emisor.get("Nombre", ""),
						"emisor_regimen_fiscal": emisor.get("RegimenFiscal", ""),
					}
				)

			# Datos del receptor
			receptor = self.root.find(".//cfdi:Receptor", self.namespaces)
			if receptor is not None:
				data.update(
					{
						"receptor_rfc": receptor.get("Rfc", ""),
						"receptor_nombre": receptor.get("Nombre", ""),
						"receptor_uso_cfdi": receptor.get("UsoCFDI", ""),
						"receptor_residencia_fiscal": receptor.get("ResidenciaFiscal", ""),
						"receptor_regimen_fiscal": receptor.get("RegimenFiscalReceptor", ""),
					}
				)

			# Datos de conceptos (primer concepto como ejemplo)
			concepto = self.root.find(".//cfdi:Concepto", self.namespaces)
			if concepto is not None:
				data.update(
					{
						"concepto_cantidad": concepto.get("Cantidad", "0"),
						"concepto_unidad": concepto.get("Unidad", ""),
						"concepto_clave_unidad": concepto.get("ClaveUnidad", ""),
						"concepto_descripcion": concepto.get("Descripcion", ""),
						"concepto_valor_unitario": concepto.get("ValorUnitario", "0"),
						"concepto_importe": concepto.get("Importe", "0"),
						"concepto_clave_prodserv": concepto.get("ClaveProdServ", ""),
					}
				)

			return data

		except Exception as e:
			frappe.log_error(f"Error extrayendo datos CFDI: {e!s}")
			return {}

	def _get_uuid(self):
		"""Extraer UUID del TimbreFiscalDigital."""
		try:
			# Buscar en complementos
			tfd = self.root.find(
				".//tfd:TimbreFiscalDigital", {"tfd": "http://www.sat.gob.mx/TimbreFiscalDigital"}
			)

			if tfd is not None:
				return tfd.get("UUID", "")

			# Buscar con namespace genérico
			for elem in self.root.iter():
				if "TimbreFiscalDigital" in str(elem.tag):
					return elem.get("UUID", "")

			return ""

		except Exception:
			return ""

	def validate_cfdi_structure(self):
		"""Validar que el XML tenga estructura CFDI válida."""
		try:
			# Verificar elemento raíz
			if "Comprobante" not in str(self.root.tag):
				return False, _("XML no es un comprobante CFDI válido")

			# Verificar versión
			version = self.root.get("Version")
			if not version or not version.startswith("4."):
				return False, _("CFDI debe ser versión 4.0")

			# Verificar elementos obligatorios
			required_elements = ["Emisor", "Receptor", "Conceptos"]
			for element_name in required_elements:
				if self.root.find(f".//cfdi:{element_name}", self.namespaces) is None:
					return False, _("Elemento obligatorio faltante: {0}").format(element_name)

			return True, _("Estructura CFDI válida")

		except Exception as e:
			return False, _("Error validando estructura: {0}").format(str(e))

	def has_addenda(self):
		"""Verificar si el CFDI ya tiene addenda."""
		try:
			addenda = self.root.find(".//cfdi:Addenda", self.namespaces)
			return addenda is not None and len(addenda) > 0
		except Exception:
			return False

	def get_existing_addendas(self):
		"""Obtener lista de addendas existentes."""
		try:
			addendas = []
			addenda_container = self.root.find(".//cfdi:Addenda", self.namespaces)

			if addenda_container is not None:
				for child in addenda_container:
					addendas.append(
						{
							"tag": child.tag,
							"attributes": dict(child.attrib),
							"text": child.text or "",
							"xml": etree.tostring(child, encoding="unicode"),
						}
					)

			return addendas

		except Exception as e:
			frappe.log_error(f"Error obteniendo addendas existentes: {e!s}")
			return []

	def extract_line_items(self):
		"""Extraer información detallada de conceptos."""
		try:
			items = []
			conceptos = self.root.findall(".//cfdi:Concepto", self.namespaces)

			for i, concepto in enumerate(conceptos):
				item = {
					"line_number": i + 1,
					"cantidad": concepto.get("Cantidad", "0"),
					"unidad": concepto.get("Unidad", ""),
					"clave_unidad": concepto.get("ClaveUnidad", ""),
					"descripcion": concepto.get("Descripcion", ""),
					"valor_unitario": concepto.get("ValorUnitario", "0"),
					"importe": concepto.get("Importe", "0"),
					"clave_prodserv": concepto.get("ClaveProdServ", ""),
					"no_identificacion": concepto.get("NoIdentificacion", ""),
					"descuento": concepto.get("Descuento", "0"),
				}

				# Extraer impuestos si existen
				impuestos = concepto.find(".//cfdi:Impuestos", self.namespaces)
				if impuestos is not None:
					item["impuestos"] = self._extract_concepto_impuestos(impuestos)

				items.append(item)

			return items

		except Exception as e:
			frappe.log_error(f"Error extrayendo conceptos: {e!s}")
			return []

	def _extract_concepto_impuestos(self, impuestos_element):
		"""Extraer impuestos de un concepto."""
		try:
			impuestos = {"traslados": [], "retenciones": []}

			# Traslados
			traslados = impuestos_element.findall(".//cfdi:Traslado", self.namespaces)
			for traslado in traslados:
				impuestos["traslados"].append(
					{
						"base": traslado.get("Base", "0"),
						"impuesto": traslado.get("Impuesto", ""),
						"tipo_factor": traslado.get("TipoFactor", ""),
						"tasa_cuota": traslado.get("TasaOCuota", ""),
						"importe": traslado.get("Importe", "0"),
					}
				)

			# Retenciones
			retenciones = impuestos_element.findall(".//cfdi:Retencion", self.namespaces)
			for retencion in retenciones:
				impuestos["retenciones"].append(
					{
						"base": retencion.get("Base", "0"),
						"impuesto": retencion.get("Impuesto", ""),
						"tipo_factor": retencion.get("TipoFactor", ""),
						"tasa_cuota": retencion.get("TasaOCuota", ""),
						"importe": retencion.get("Importe", "0"),
					}
				)

			return impuestos

		except Exception:
			return {"traslados": [], "retenciones": []}
