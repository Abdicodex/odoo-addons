def _has_column(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    cr.execute("SELECT to_regclass('hijra_project_map'), to_regclass('hijra_budget_map')")
    project_map, budget_map = cr.fetchone()
    if not project_map or not budget_map:
        return
    for table in ('finance_transaction', 'finance_transaction_line'):
        for new, legacy, mapping in (('project_id', 'legacy_project_id', 'hijra_project_map'),
                                     ('budget_id', 'legacy_budget_id', 'hijra_budget_map')):
            if _has_column(cr, table, legacy):
                cr.execute(
                    'UPDATE "%(t)s" t SET "%(new)s" = m.new_id FROM %(map)s m WHERE t."%(old)s" = m.old_id'
                    % {'t': table, 'new': new, 'old': legacy, 'map': mapping})
