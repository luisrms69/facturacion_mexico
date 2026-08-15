// Indicador de ambiente fiscal en el Desk (issue #171).
//
// Añade UNA clase al <body> según `frappe.boot.fm_environment` (fuente única de #215):
//   - "production"        → ninguna clase (interfaz sin cambios)
//   - "sandbox"           → fm-env-sandbox  (franja ámbar en la navbar, vía CSS)
//   - ausente / inválido  → fm-env-unset    (franja roja en la navbar, vía CSS)
//
// Sin AJAX ni polling: el valor ya viene en el boot. El estilo vive en fm_environment.css
// y solo toca la navbar del Desk; no agrega badges, mensajes ni elementos en los formularios.

frappe.after_ajax(() => {
	const env = ((frappe.boot && frappe.boot.fm_environment) || "")
		.toString()
		.trim()
		.toLowerCase();
	const body = document.body;
	if (!body) return;

	body.classList.remove("fm-env-sandbox", "fm-env-unset");

	if (env === "production") {
		return; // Producción: sin indicador visual.
	}
	body.classList.add(env === "sandbox" ? "fm-env-sandbox" : "fm-env-unset");
});
