def _has_column(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Re-point requisitions, RFQs and budget products to the Project app records."""
    if not version:
        return
    cr.execute("SELECT to_regclass('hijra_project_map'), to_regclass('hijra_budget_map')")
    project_map, budget_map = cr.fetchone()
    if not project_map or not budget_map:
        return
    for table, new, legacy, mapping in (
            ('purchase_request', 'project_id', 'legacy_project_id', 'hijra_project_map'),
            ('purchase_request', 'budget_id', 'legacy_budget_id', 'hijra_budget_map'),
            ('purchase_order', 'rfq_project_id', 'legacy_rfq_project_id', 'hijra_project_map')):
        if _has_column(cr, table, legacy):
            cr.execute(
                'UPDATE "%(t)s" t SET "%(new)s" = m.new_id FROM %(map)s m WHERE t."%(old)s" = m.old_id'
                % {'t': table, 'new': new, 'old': legacy, 'map': mapping})
    # the RFQ product of a budget code now lives on its task
    if _has_column(cr, 'hijra_budget', 'purchase_product_id') and _has_column(cr, 'project_task', 'purchase_product_id'):
        cr.execute("""
            UPDATE project_task t SET purchase_product_id = b.purchase_product_id
              FROM hijra_budget b JOIN hijra_budget_map m ON m.old_id = b.id
             WHERE t.id = m.new_id AND b.purchase_product_id IS NOT NULL
        """)
