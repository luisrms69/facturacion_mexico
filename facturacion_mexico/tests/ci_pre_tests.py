def run():
    import frappe
    def log(msg):
        frappe.logger().info("CI_PRE: " + str(msg))

    # --- 1) Warehouse Types requeridos por ERPNext y tus tests ---
    for wt in ("Stores", "Work In Progress", "Finished Goods", "Transit"):
        if not frappe.db.exists("Warehouse Type", wt):
            frappe.get_doc({"doctype":"Warehouse Type", "name": wt}).insert(ignore_permissions=True)

    # --- 2) UOMs mínimos que piden tus tests ---
    for u in ("Nos", "Unit", "Piece"):
        if not frappe.db.exists("UOM", u):
            frappe.get_doc({"doctype":"UOM", "uom_name": u, "name": u}).insert(ignore_permissions=True)

    # --- 3) Customer Group raíz + hoja que usa tu test ---
    if not frappe.db.exists("Customer Group", "All Customer Groups"):
        frappe.get_doc({
            "doctype":"Customer Group",
            "name":"All Customer Groups",
            "customer_group_name":"All Customer Groups",
            "is_group":1
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Customer Group", "Individual"):
        frappe.get_doc({
            "doctype":"Customer Group",
            "name":"Individual",
            "customer_group_name":"Individual",
            "is_group":0,
            "parent_customer_group":"All Customer Groups"
        }).insert(ignore_permissions=True)

    # --- 4) Territory raíz + hoja que usan tus tests ---
    if not frappe.db.exists("Territory", "All Territories"):
        frappe.get_doc({
            "doctype":"Territory",
            "name":"All Territories",
            "territory_name":"All Territories",
            "is_group":1
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Territory", "Rest Of The World"):
        frappe.get_doc({
            "doctype":"Territory",
            "name":"Rest Of The World",
            "territory_name":"Rest Of The World",
            "is_group":0,
            "parent_territory":"All Territories"
        }).insert(ignore_permissions=True)

    # --- 5) Item Group raíz y una hoja básica ---
    if not frappe.db.exists("Item Group", "All Item Groups"):
        frappe.get_doc({
            "doctype":"Item Group",
            "name":"All Item Groups",
            "item_group_name":"All Item Groups",
            "is_group":1
        }).insert(ignore_permissions=True)
    if not frappe.db.exists("Item Group", "Products"):
        frappe.get_doc({
            "doctype":"Item Group",
            "name":"Products",
            "item_group_name":"Products",
            "is_group":0,
            "parent_item_group":"All Item Groups"
        }).insert(ignore_permissions=True)

    # --- 6) Price Lists básicos para Sales Invoice ---
    for currency in ("INR", "MXN"):
        pl_name = f"Standard Selling ({currency})"
        if not frappe.db.exists("Price List", pl_name):
            frappe.get_doc({
                "doctype":"Price List",
                "price_list_name": pl_name,
                "currency": currency,
                "enabled": 1,
                "selling": 1
            }).insert(ignore_permissions=True)

    # --- 7) Items mínimos que tus tests intentan usar ---
    for item_code in ("Test Item Default", "_Test Item"):
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc({
                "doctype":"Item",
                "item_code":item_code,
                "item_name":item_code,
                "item_group":"Products",
                "stock_uom":"Unit",  # Requerido por ERPNext
                "is_stock_item":0   # que no pida inventario
            }).insert(ignore_permissions=True)

    # --- 8) Addenda Types que reclaman tus pruebas (Link a "Addenda Type") ---
    try:
        for add_type in ("TEST_AUTOMOTIVE", "TEST_RETAIL", "TEST_GENERIC"):
            if not frappe.db.exists("Addenda Type", add_type):
                frappe.get_doc({
                    "doctype":"Addenda Type",
                    "name": add_type,
                    "description": add_type
                }).insert(ignore_permissions=True)
    except Exception as e:
        log(f"Addenda Types failed (non-critical): {e}")  # Skip if can't create

    # --- 9) Defaults suaves para evitar warnings de "lugar expedición" en branch factories ---
    #     (Si tus factories no los setean, al menos deja un postal general válido)
    frappe.db.set_default("country", "Mexico")
    frappe.db.commit()

    # Reporte rápido
    report = {
        "warehouse_types": [wt for wt in ("Stores","Work In Progress","Finished Goods","Transit") if frappe.db.exists("Warehouse Type", wt)],
        "uoms":            [u for u in ("Nos","Unit","Piece") if frappe.db.exists("UOM", u)],
        "customer_groups": [g for g in ("All Customer Groups","Individual") if frappe.db.exists("Customer Group", g)],
        "territories":     [t for t in ("All Territories","Rest Of The World") if frappe.db.exists("Territory", t)],
        "item_groups":     [g for g in ("All Item Groups","Products") if frappe.db.exists("Item Group", g)],
        "price_lists":     [p for p in ("Standard Selling (INR)","Standard Selling (MXN)") if frappe.db.exists("Price List", p)],
        "items_created":   [i for i in ("Test Item Default", "_Test Item") if frappe.db.exists("Item", i)],
        "addenda_types":   [a for a in ("TEST_AUTOMOTIVE","TEST_RETAIL","TEST_GENERIC") if frappe.db.exists("Addenda Type", a)],
    }
    print("CI_PRE_REPORT", report)