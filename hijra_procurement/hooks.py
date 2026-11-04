import logging

from odoo import Command

_logger = logging.getLogger(__name__)

# the committee of the HIJRA templates: (name to look up, role in the committee, position printed)
COMMITTEE = [
    ('Ayub', 'secretary', 'Procurement & Logistics Officer', 'Ayub Abdulkadir Abdulsalam'),
    ('Abdifitah', 'member', 'Finance Officer', 'Abdifitah Abdulle'),
    ('Fahmo', 'member', 'Admin & HR Officer', 'Fahmo Mohamud Nor'),
    ('Peter Mwaura', 'chair', 'Programme Director', 'Peter Mwaura'),
]


def post_init_hook(env):
    """Start with the committee named on the templates; it is edited under Procurement Committee."""
    Committee = env['procurement.committee']
    if Committee.search_count([]):
        return
    lines = []
    for sequence, (name, role, position, full_name) in enumerate(COMMITTEE, 1):
        users = env['res.users'].search([('name', 'ilike', name), ('share', '=', False)])
        if len(users) != 1:
            _logger.warning("Committee: found %d users matching '%s'", len(users), name)
            continue
        lines.append(Command.create({
            'user_id': users.id, 'role': role, 'position': position, 'full_name': full_name,
            'sequence': sequence * 10}))
    committee = Committee.create({'name': 'Procurement Committee', 'member_ids': lines})
    _logger.info("Procurement committee created with %d members", len(committee.member_ids))
