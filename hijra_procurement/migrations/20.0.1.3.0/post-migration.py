from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Give every existing requisition its procurement file."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    requests = env['purchase.request'].with_context(active_test=False).search([])
    existing = env['procurement.file'].search([]).request_id
    missing = requests - existing
    if missing:
        env['procurement.file'].create([{'request_id': request.id} for request in missing])
