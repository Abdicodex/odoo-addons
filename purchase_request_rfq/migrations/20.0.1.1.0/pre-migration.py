def migrate(cr, version):
    """Projects, budgets, funds, locations and departments moved to shared models.

    The old values pointed at tables that no longer exist, so clear them and let
    requestors pick them again from the shared lists.
    """
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'purchase_request'
    """)
    columns = {row[0] for row in cr.fetchall()}
    for column in ('project_id', 'budget_id', 'fund_id', 'location_id', 'department_id'):
        if column in columns:
            cr.execute(f'UPDATE purchase_request SET "{column}" = NULL')
