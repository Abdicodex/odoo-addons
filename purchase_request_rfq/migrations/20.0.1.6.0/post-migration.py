def _columns(cr, table):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
    return {row[0] for row in cr.fetchall()}


def migrate(cr, version):
    """The RFQ details now live on each quotation (purchase order).

    Copy what earlier versions kept on the RFQ record and on the requisition.
    """
    orders = _columns(cr, 'purchase_order')
    groups = _columns(cr, 'purchase_request_rfq')
    if 'rfq_subject' not in orders:
        return
    if {'subject', 'validity_days', 'quotation_details'} <= groups:
        cr.execute("""
            UPDATE purchase_order po
               SET rfq_subject = COALESCE(po.rfq_subject, g.subject),
                   rfq_validity_days = COALESCE(g.validity_days, po.rfq_validity_days),
                   rfq_quotation_details = COALESCE(po.rfq_quotation_details, g.quotation_details)
              FROM purchase_request_rfq g
             WHERE po.rfq_group_id = g.id
        """)
    cr.execute("""
        UPDATE purchase_order po
           SET rfq_project_id = COALESCE(po.rfq_project_id, r.project_id),
               rfq_location_id = COALESCE(po.rfq_location_id, r.location_id)
          FROM purchase_request r
         WHERE po.purchase_request_id = r.id
    """)
