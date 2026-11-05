from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The stage and the next action are stored now: fill them in for every procurement file."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    env['procurement.file'].search([])._update_progress()
