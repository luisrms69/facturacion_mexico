app_name = "facturacion_mexico"
app_title = "Facturación México"
app_publisher = "Buzola"
app_description = "Sistema de Facturación Legal México para ERPNext"
app_email = "it@buzola.mx"
app_license = "gpl-3.0"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "facturacion_mexico",
# 		"logo": "/assets/facturacion_mexico/logo.png",
# 		"title": "Facturacion Mexico",
# 		"route": "/facturacion_mexico",
# 		"has_permission": "facturacion_mexico.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/facturacion_mexico/css/facturacion_mexico.css"
# app_include_js = "/assets/facturacion_mexico/js/facturacion_mexico.js"

# include js, css files in header of web template
# web_include_css = "/assets/facturacion_mexico/css/facturacion_mexico.css"
# web_include_js = "/assets/facturacion_mexico/js/facturacion_mexico.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "facturacion_mexico/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"Sales Invoice": ["public/js/sales_invoice.js", "public/js/ereceipt_handler.js"],
	"Factura Fiscal Mexico": ["public/js/factura_fiscal_mexico.js"],
}

# include css in doctype views
doctype_css = {
	"Factura Fiscal Mexico": ["public/css/fiscal_dashboard.css"],
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "facturacion_mexico/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "facturacion_mexico.utils.jinja_methods",
# 	"filters": "facturacion_mexico.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "facturacion_mexico.install.before_install"
after_install = "facturacion_mexico.install.after_install"

# Custom Fields & SAT Catalogs Fixtures
# -------------
# Fixtures for custom fields - ISSUE #31 CRITICAL MIGRATION + SAT Catalogs Migration
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [
			[
				"name",
				"in",
				[
					# Branch custom fields (14 campos)
					"Branch-fm_fiscal_configuration_section",
					"Branch-fm_certificate_ids",
					"Branch-fm_enable_fiscal",
					"Branch-fm_enable_fiscal_test",
					"Branch-fm_folio_current",
					"Branch-fm_folio_end",
					"Branch-fm_folio_start",
					"Branch-fm_folio_warning_threshold",
					"Branch-fm_last_invoice_date",
					"Branch-fm_lugar_expedicion",
					"Branch-fm_monthly_average",
					"Branch-fm_serie_pattern",
					"Branch-fm_share_certificates",
					"Branch-fm_test_field_unique_2025",
					# Customer custom fields (11 campos - movidos a Tax tab)
					"Customer-fm_addenda_info_section",
					"Customer-fm_column_break_fiscal_customer",
					"Customer-fm_column_break_validacion",
					"Customer-fm_default_addenda_type",
					"Customer-fm_informacion_fiscal_mx_section",
					"Customer-fm_lista_69b_status",
					"Customer-fm_regimen_fiscal",
					"Customer-fm_requires_addenda",
					"Customer-fm_rfc_validated",
					"Customer-fm_rfc_validation_date",
					"Customer-fm_uso_cfdi_default",
					"Customer-fm_validacion_sat_section",
					# Item custom fields (2 existentes + 2 faltantes = 4 total)
					"Item-fm_clasificacion_sat_section",
					"Item-fm_producto_servicio_sat",
					"Item-fm_column_break_item_sat",
					# Payment Entry custom fields (5 campos)
					"Payment Entry-fm_complement_generated",
					"Payment Entry-fm_complemento_pago",
					"Payment Entry-fm_forma_pago_sat",
					"Payment Entry-fm_informacion_fiscal_section",
					"Payment Entry-fm_require_complement",
					# Sales Invoice custom fields (34 campos activos + 7 migrados)
					"Sales Invoice-fm_fiscal_attempts",
					"Sales Invoice-fm_addenda_column_break",
					"Sales Invoice-fm_addenda_errors",
					"Sales Invoice-fm_addenda_generated_date",
					"Sales Invoice-fm_addenda_required",
					"Sales Invoice-fm_addenda_section",
					"Sales Invoice-fm_addenda_status",
					"Sales Invoice-fm_addenda_type",
					"Sales Invoice-fm_addenda_xml",
					"Sales Invoice-fm_auto_selected_branch",
					"Sales Invoice-fm_branch",
					"Sales Invoice-fm_branch_health_status",
					"Sales Invoice-fm_certificate_info",
					# "Sales Invoice-fm_cfdi_use", # MIGRADO A Factura Fiscal Mexico
					"Sales Invoice-fm_column_break_fiscal",
					"Sales Invoice-fm_complementos_count",
					"Sales Invoice-fm_create_as_draft",
					"Sales Invoice-fm_draft_approved_by",
					"Sales Invoice-fm_draft_column_break",
					"Sales Invoice-fm_draft_created_date",
					"Sales Invoice-fm_draft_section",
					"Sales Invoice-fm_draft_status",
					"Sales Invoice-fm_ereceipt_column_break",
					"Sales Invoice-fm_ereceipt_expiry_date",
					"Sales Invoice-fm_ereceipt_expiry_days",
					"Sales Invoice-fm_ereceipt_expiry_type",
					"Sales Invoice-fm_ereceipt_mode",
					"Sales Invoice-fm_ereceipt_section",
					"Sales Invoice-fm_factorapi_draft_id",
					"Sales Invoice-fm_factura_fiscal_mx",
					# "Sales Invoice-fm_fiscal_status", # MIGRADO A Factura Fiscal Mexico
					"Sales Invoice-fm_folio_reserved",
					# "Sales Invoice-fm_informacion_fiscal_section", # ELIMINADO - Sección vacía migrada a Factura Fiscal Mexico
					# "Sales Invoice-fm_lugar_expedicion", # MIGRADO A Factura Fiscal Mexico
					"Sales Invoice-fm_multi_sucursal_column",
					"Sales Invoice-fm_multi_sucursal_section",
					# "Sales Invoice-fm_payment_method_sat", # MIGRADO A Factura Fiscal Mexico
					"Sales Invoice-fm_pending_amount",
					# "Sales Invoice-fm_serie_folio", # MIGRADO A Factura Fiscal Mexico
					"Sales Invoice-fm_timbrado_section",
					# "Sales Invoice-fm_uuid_fiscal", # MIGRADO A Factura Fiscal Mexico
					# Factura Fiscal Mexico custom fields (7 campos migrados)
					"Factura Fiscal Mexico-fm_cfdi_use",
					"Factura Fiscal Mexico-fm_fiscal_status",
					"Factura Fiscal Mexico-fm_forma_pago_timbrado",
					"Factura Fiscal Mexico-fm_lugar_expedicion",
					"Factura Fiscal Mexico-fm_payment_method_sat",
					"Factura Fiscal Mexico-fm_serie_folio",
					"Factura Fiscal Mexico-fm_uuid_fiscal",
				],
			]
		],
	},
	# SAT Catalogs Fixtures - Migration from install.py to fixtures (Temporarily disabled for fixtures export)
	# "facturacion_mexico/fixtures/sat_uso_cfdi.json",
	# "facturacion_mexico/fixtures/sat_regimen_fiscal.json",
	# "facturacion_mexico/fixtures/sat_forma_pago.json",
	# Mode of Payment SAT - Formas de pago con códigos SAT
	{"dt": "Mode of Payment", "filters": [["name", "like", "%-%"]]},
	# UOM SAT - Unidades de medida con códigos SAT (20 principales)
	{"dt": "UOM", "filters": [["uom_name", "like", "% - %"]]},
]

# Uninstallation
# ------------

# before_uninstall = "facturacion_mexico.uninstall.before_uninstall"
# after_uninstall = "facturacion_mexico.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "facturacion_mexico.utils.before_app_install"
# after_app_install = "facturacion_mexico.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "facturacion_mexico.utils.before_app_uninstall"
# after_app_uninstall = "facturacion_mexico.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "facturacion_mexico.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Sales Invoice": {
		"validate": [
			"facturacion_mexico.facturacion_fiscal.hooks_handlers.sales_invoice_validate.validate_fiscal_data",
			"facturacion_mexico.hooks_handlers.sales_invoice_validate.sales_invoice_validate",
			"facturacion_mexico.validaciones.sales_invoice.validate_ppd_vs_forma_pago",
		],
		"before_submit": "facturacion_mexico.validaciones.hooks_handlers.sales_invoice_validate.validate_lista_69b_customer",
		"on_submit": [
			"facturacion_mexico.hooks_handlers.sales_invoice_submit.sales_invoice_on_submit",
		],
		"on_cancel": "facturacion_mexico.facturacion_fiscal.hooks_handlers.sales_invoice_cancel.handle_fiscal_cancellation",
	},
	"Customer": {
		"validate": "facturacion_mexico.validaciones.hooks_handlers.customer_validate.validate_rfc_format",
		"before_save": "facturacion_mexico.validaciones.hooks_handlers.customer_validate.validate_rfc_format",
		"after_insert": "facturacion_mexico.validaciones.hooks_handlers.customer_validate.schedule_rfc_validation",
	},
	"Branch": {
		"validate": "facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.validate_branch_fiscal_configuration",
		"after_insert": "facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.after_branch_insert",
		"on_update": "facturacion_mexico.multi_sucursal.custom_fields.branch_fiscal_fields.on_branch_update",
	},
	"Payment Entry": {
		"validate": "facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_validate.check_ppd_requirement",
		"on_submit": "facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_submit.create_complement_if_required",
		"on_cancel": "facturacion_mexico.complementos_pago.hooks_handlers.payment_entry_cancel.cancel_related_complement",
	},
	"Complemento Pago MX": {
		"validate": "facturacion_mexico.complementos_pago.hooks_handlers.complemento_pago_validate.validate_payment_amounts",
		"before_save": "facturacion_mexico.complementos_pago.hooks_handlers.complemento_pago_validate.calculate_payment_balances",
		"after_insert": "facturacion_mexico.complementos_pago.hooks_handlers.complemento_pago_insert.create_fiscal_event",
		"on_submit": "facturacion_mexico.complementos_pago.hooks_handlers.complemento_pago_submit.update_payment_tracking",
	},
	"EReceipt MX": {
		"before_save": "facturacion_mexico.ereceipts.hooks_handlers.ereceipt_validate.calculate_expiry_date",
		"after_insert": "facturacion_mexico.ereceipts.hooks_handlers.ereceipt_insert.generate_facturapi_ereceipt",
	},
	"Factura Fiscal Mexico": {
		"after_insert": "facturacion_mexico.facturacion_fiscal.hooks_handlers.factura_fiscal_insert.create_fiscal_event",
		"on_update": "facturacion_mexico.facturacion_fiscal.hooks_handlers.factura_fiscal_update.register_status_changes",
	},
}

# Scheduled Tasks
# ---------------

# Scheduled Tasks
scheduler_events = {
	"hourly": [
		"facturacion_mexico.complementos_pago.api.process_pending_complements",
		"facturacion_mexico.ereceipts.api.expire_ereceipts",
	],
	"daily": [
		"facturacion_mexico.validaciones.api.bulk_validate_customers",
		"facturacion_mexico.validaciones.doctype.sat_validation_cache.sat_validation_cache.cleanup_expired_cache",
		"facturacion_mexico.ereceipts.doctype.ereceipt_mx.ereceipt_mx.bulk_expire_ereceipts",
	],
	"weekly": [
		"facturacion_mexico.complementos_pago.api.reconcile_payment_tracking",
		"facturacion_mexico.facturacion_fiscal.tasks.cleanup_old_fiscal_events",
	],
}

# Testing
# -------

before_tests = [
	"facturacion_mexico.install.before_tests",
	"facturacion_mexico.setup.testing.load_testing_fixtures",
]

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "facturacion_mexico.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "facturacion_mexico.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["facturacion_mexico.utils.before_request"]
# after_request = ["facturacion_mexico.utils.after_request"]

# Job Events
# ----------
# before_job = ["facturacion_mexico.utils.before_job"]
# after_job = ["facturacion_mexico.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"facturacion_mexico.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }
