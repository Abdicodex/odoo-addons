from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Group the quotations created before RFQ references existed.

    Each requisition that already has purchase orders gets one RFQ record
    holding them (the orders keep their own references).
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    Rfq = env['purchase.request.rfq']
    for request in env['purchase.request'].search([('rfq_ids', '!=', False)]):
        orders = request.rfq_ids.filtered(lambda order: not order.rfq_group_id)
        if not orders:
            continue
        group = Rfq.create({'request_id': request.id})
        orders.write({'rfq_group_id': group.id})
        confirmed = orders.filtered(lambda order: order.state in ('purchase', 'done'))[:1]
        if confirmed:
            group.write({'state': 'awarded', 'awarded_order_id': confirmed.id})
        elif all(order.state == 'cancel' for order in orders):
            group.state = 'cancelled'
