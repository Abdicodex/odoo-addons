import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# the members named on the HIJRA templates: first name -> full name
FULL_NAMES = {
    'Ayub': 'Ayub Abdulkadir Abdulsalam',
    'Abdifitah': 'Abdifitah Abdulle',
    'Fahmo': 'Fahmo Mohamud Nor',
    'Peter': 'Peter Mwaura',
}


def migrate(cr, version):
    """Committee members print with their full name: fill in the ones saved with a first name only."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for member in env['procurement.committee.member'].search([]):
        name = (member.full_name or '').strip()
        if name and ' ' in name:
            continue
        first = (name or member.user_id.name or '').split(' ')[0]
        full = FULL_NAMES.get(first)
        if full:
            member.full_name = full
            _logger.info("Committee member %s printed as %s", first, full)
