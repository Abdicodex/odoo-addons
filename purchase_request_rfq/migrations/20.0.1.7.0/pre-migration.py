LEGACY = (
    ('purchase_request', ('project_id', 'budget_id')),
    ('purchase_order', ('rfq_project_id',)),
)


def _has_column(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column))
    return bool(cr.fetchone())


def _drop_foreign_keys(cr, table, column):
    """The old foreign key points to a HIJRA code table: drop it from the set-aside column."""
    cr.execute("""
        SELECT c.conname FROM pg_constraint c
          JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
         WHERE c.contype = 'f' AND c.conrelid = %s::regclass AND a.attname = %s
    """, (table, column))
    for (name,) in cr.fetchall():
        cr.execute('ALTER TABLE "%s" DROP CONSTRAINT "%s"' % (table, name))


def migrate(cr, version):
    """Project and budget now point to the Project app.

    The old columns reference the HIJRA code tables, so they are set aside (renamed) before the
    new columns are created; the post-migration fills the new ones through the id mapping.
    """
    if not version:
        return
    for table, columns in LEGACY:
        for column in columns:
            legacy = 'legacy_' + column
            if _has_column(cr, table, column) and not _has_column(cr, table, legacy):
                cr.execute('ALTER TABLE "%s" RENAME COLUMN "%s" TO "%s"' % (table, column, legacy))
                _drop_foreign_keys(cr, table, legacy)
