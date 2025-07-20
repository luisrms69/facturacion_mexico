"""
Addenda Product Mapping DocType - Sprint 3
Mapeo de productos para clientes con addendas específicas
"""

import json
from typing import Any, Dict, List, Optional

import frappe
from frappe import _
from frappe.model.document import Document


class AddendaProductMapping(Document):
	"""DocType para mapeo de productos específicos del cliente."""

	def validate(self):
		"""Validaciones del mapeo de productos."""
		self.validate_duplicate_mapping()
		self.validate_additional_data()
		self.set_audit_fields()

	def validate_duplicate_mapping(self):
		"""Validar que no haya mapeos duplicados."""
		if not self.customer or not self.item:
			return

		# Verificar duplicados activos
		existing = frappe.get_all(
			"Addenda Product Mapping",
			filters={"customer": self.customer, "item": self.item, "is_active": 1, "name": ["!=", self.name]},
			limit=1,
		)

		if existing:
			frappe.throw(
				_("Ya existe un mapeo activo para el cliente {0} y artículo {1}").format(
					self.customer, self.item
				)
			)

	def validate_additional_data(self):
		"""Validar datos adicionales en formato JSON."""
		if not self.additional_data:
			self.additional_data = "{}"
			return

		try:
			# Verificar que sea JSON válido
			data = json.loads(self.additional_data)

			# Validar estructura básica
			if not isinstance(data, dict):
				frappe.throw(_("Datos adicionales deben ser un objeto JSON"))

			# Verificar campos comunes requeridos por algunos clientes
			self._validate_common_fields(data)

		except json.JSONDecodeError as e:
			frappe.throw(_("Datos adicionales contienen JSON inválido: {0}").format(str(e)))

	def _validate_common_fields(self, data: Dict):
		"""Validar campos comunes en datos adicionales."""
		# Validaciones opcionales para campos específicos de clientes
		if "categoria" in data and not isinstance(data["categoria"], str):
			frappe.throw(_("Campo 'categoria' debe ser texto"))

		if "peso" in data:
			try:
				float(data["peso"])
			except (ValueError, TypeError):
				frappe.throw(_("Campo 'peso' debe ser numérico"))

		if "dimensiones" in data and not isinstance(data["dimensiones"], dict):
			frappe.throw(_("Campo 'dimensiones' debe ser un objeto"))

	def set_audit_fields(self):
		"""Establecer campos de auditoría."""
		if self.is_new():
			self.created_by = frappe.session.user
			self.created_date = frappe.utils.now()

		self.modified_by = frappe.session.user
		self.modified_date = frappe.utils.now()

	def get_mapping_data(self) -> Dict[str, Any]:
		"""Obtener datos completos del mapeo."""
		additional_data = {}

		try:
			if self.additional_data:
				additional_data = json.loads(self.additional_data)
		except json.JSONDecodeError:
			additional_data = {}

		return {
			"customer_code": self.customer_item_code,
			"customer_description": self.customer_item_description or "",
			"customer_uom": self.customer_uom or "",
			"additional_data": additional_data,
			"item_info": {
				"item_code": self.item_code,
				"item_name": self.item_name,
				"original_item": self.item,
			},
			"mapping_notes": self.mapping_notes or "",
		}

	def update_additional_data(self, new_data: Dict, merge: bool = True):
		"""Actualizar datos adicionales."""
		try:
			if merge and self.additional_data:
				current_data = json.loads(self.additional_data)
				current_data.update(new_data)
				self.additional_data = json.dumps(current_data, indent=2, ensure_ascii=False)
			else:
				self.additional_data = json.dumps(new_data, indent=2, ensure_ascii=False)

			self.save()

		except Exception as e:
			frappe.throw(_("Error actualizando datos adicionales: {0}").format(str(e)))

	def get_customer_info(self) -> Dict:
		"""Obtener información del cliente."""
		try:
			customer_doc = frappe.get_doc("Customer", self.customer)
			return {
				"customer_name": customer_doc.customer_name,
				"customer_group": customer_doc.customer_group,
				"territory": customer_doc.territory,
			}
		except:
			return {}

	def get_item_info(self) -> Dict:
		"""Obtener información del artículo."""
		try:
			item_doc = frappe.get_doc("Item", self.item)
			return {
				"item_group": item_doc.item_group,
				"stock_uom": item_doc.stock_uom,
				"description": item_doc.description,
				"item_defaults": item_doc.item_defaults,
			}
		except:
			return {}

	def get_usage_stats(self) -> Dict:
		"""Obtener estadísticas de uso del mapeo."""
		try:
			# Contar facturas que incluyen este item para este cliente
			invoices_count = frappe.db.count(
				"Sales Invoice Item",
				filters={
					"parent": [
						"in",
						frappe.get_all(
							"Sales Invoice",
							filters={
								"customer": self.customer,
								"docstatus": 1,
								"posting_date": [">", frappe.utils.add_days(frappe.utils.today(), -90)],
							},
							pluck="name",
						),
					],
					"item_code": self.item_code,
				},
			)

			return {
				"recent_invoices": invoices_count,
				"mapping_age_days": frappe.utils.date_diff(frappe.utils.today(), self.created_date),
				"last_modified_days": frappe.utils.date_diff(frappe.utils.today(), self.modified_date),
			}

		except Exception as e:
			frappe.log_error(f"Error obteniendo estadísticas de mapeo: {str(e)}")
			return {"recent_invoices": 0, "mapping_age_days": 0, "last_modified_days": 0}

	@staticmethod
	def get_customer_mappings(customer: str, active_only: bool = True) -> List[Dict]:
		"""Obtener todos los mapeos de un cliente."""
		filters = {"customer": customer}
		if active_only:
			filters["is_active"] = 1

		mappings = frappe.get_all(
			"Addenda Product Mapping",
			filters=filters,
			fields=[
				"name",
				"item",
				"item_code",
				"item_name",
				"customer_item_code",
				"customer_item_description",
				"customer_uom",
				"additional_data",
				"mapping_notes",
			],
		)

		# Procesar datos adicionales
		for mapping in mappings:
			try:
				mapping["additional_data"] = json.loads(mapping["additional_data"] or "{}")
			except:
				mapping["additional_data"] = {}

		return mappings

	@staticmethod
	def get_item_mappings(item: str, active_only: bool = True) -> List[Dict]:
		"""Obtener todos los mapeos de un artículo."""
		filters = {"item": item}
		if active_only:
			filters["is_active"] = 1

		return frappe.get_all(
			"Addenda Product Mapping",
			filters=filters,
			fields=[
				"name",
				"customer",
				"customer_item_code",
				"customer_item_description",
				"customer_uom",
				"additional_data",
				"mapping_notes",
			],
		)

	@staticmethod
	def find_mapping(customer: str, item: str) -> Optional[Dict]:
		"""Buscar mapeo específico para cliente e item."""
		mappings = frappe.get_all(
			"Addenda Product Mapping",
			filters={"customer": customer, "item": item, "is_active": 1},
			fields=[
				"name",
				"customer_item_code",
				"customer_item_description",
				"customer_uom",
				"additional_data",
				"mapping_notes",
			],
			limit=1,
		)

		if not mappings:
			return None

		mapping = mappings[0]

		try:
			mapping["additional_data"] = json.loads(mapping["additional_data"] or "{}")
		except:
			mapping["additional_data"] = {}

		return mapping

	@staticmethod
	def bulk_create_mappings(mappings_data: List[Dict]) -> Dict:
		"""Crear múltiples mapeos en lote."""
		results = {"created": 0, "errors": 0, "skipped": 0, "messages": []}

		for mapping_data in mappings_data:
			try:
				# Verificar si ya existe
				existing = AddendaProductMapping.find_mapping(
					mapping_data.get("customer"), mapping_data.get("item")
				)

				if existing:
					results["skipped"] += 1
					results["messages"].append(
						f"Mapeo ya existe: {mapping_data.get('customer')} - {mapping_data.get('item')}"
					)
					continue

				# Crear nuevo mapeo
				doc = frappe.new_doc("Addenda Product Mapping")
				doc.update(mapping_data)
				doc.insert()

				results["created"] += 1

			except Exception as e:
				results["errors"] += 1
				results["messages"].append(f"Error: {str(e)}")

		return results


# Métodos para hooks
def on_doctype_update():
	"""Ejecutar cuando se actualiza el DocType."""
	frappe.db.add_index("Addenda Product Mapping", ["customer", "item", "is_active"])


def get_permission_query_conditions(user):
	"""Condiciones de permisos para consultas."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	# Los usuarios solo pueden ver mapeos de clientes que pueden ver
	return """(`tabAddenda Product Mapping`.`customer` in (
		select name from `tabCustomer` where disabled = 0
	))"""


def has_permission(doc, user):
	"""Verificar permisos específicos del documento."""
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return True

	# Verificar que el cliente esté activo
	try:
		customer_doc = frappe.get_doc("Customer", doc.customer)
		return not customer_doc.disabled
	except:
		return False
