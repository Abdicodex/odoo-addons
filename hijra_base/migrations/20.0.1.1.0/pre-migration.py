def migrate(cr, version):
    """Signatures now live on the employee record: move any uploaded earlier.

    The first version kept them in a separate hijra.signature table. The
    pictures are file attachments, so re-pointing the attachment is enough.
    """
    cr.execute("SELECT to_regclass('hijra_signature'), to_regclass('hr_employee')")
    signature_table, employee_table = cr.fetchone()
    if not signature_table or not employee_table:
        return
    cr.execute("""
        UPDATE ir_attachment a
           SET res_model = 'hr.employee', res_field = 'hijra_signature', res_id = e.id
          FROM hijra_signature s
          JOIN hr_employee e ON e.user_id = s.user_id
         WHERE a.res_model = 'hijra.signature'
           AND a.res_field = 'image'
           AND a.res_id = s.id
           AND NOT EXISTS (
               SELECT 1 FROM ir_attachment b
                WHERE b.res_model = 'hr.employee'
                  AND b.res_field = 'hijra_signature'
                  AND b.res_id = e.id)
    """)
