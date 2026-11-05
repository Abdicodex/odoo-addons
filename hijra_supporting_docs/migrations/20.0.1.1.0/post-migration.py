from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Tell which expenditure types are services and which are goods, from their document lists:
    a completion certificate means a service, a delivery note / GRN means goods; both or none is left
    for the buyer to choose on the order."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for expenditure in env['expenditure.type'].with_context(active_test=False).search([]):
        names = expenditure.line_ids.mapped('document_type_id.name')
        service = any(name.startswith('Service rendered') for name in names)
        goods = any(name.startswith('Delivery note') for name in names)
        if service and not goods:
            expenditure.receipt_type = 'service'
        elif goods and not service:
            expenditure.receipt_type = 'goods'
