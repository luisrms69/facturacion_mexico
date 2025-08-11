def run():
    import frappe
    types = ("Stores", "Work In Progress", "Finished Goods", "Transit")
    created = []
    for wt in types:
        if not frappe.db.exists("Warehouse Type", wt):
            frappe.get_doc({"doctype": "Warehouse Type", "name": wt}).insert(ignore_permissions=True)
            created.append(wt)
    frappe.db.commit()
    print("CI_PRE_TESTS: Warehouse Types OK; created:", created)