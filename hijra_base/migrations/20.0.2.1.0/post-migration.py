import logging

from odoo import Command, SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# the second signature is the programme manager (who is also the director), finance checks and verifies,
# and the administrative assistant is in HR & Admin: people already holding the first role also hold the second
LINKS = [
    ('officer_in_charge', 'programme_director'),
    ('fa_officer', 'finance_officer'),
    ('admin_assistant', 'admin_hr_officer'),
]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Role = env['hijra.role'].with_context(active_test=False)
    for target_code, source_code in LINKS:
        target = Role.search([('code', '=', target_code)], limit=1)
        source = Role.search([('code', '=', source_code)], limit=1)
        if target and source and source.user_ids - target.user_ids:
            target.user_ids = [Command.link(user.id) for user in source.user_ids]
            _logger.info("Role %s also given to the holders of %s", target_code, source_code)
