import logging

from odoo import Command, SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# who holds which role at the start, from the names on the HIJRA templates
ROLE_PEOPLE = {
    'procurement_officer': ['Ayub'],
    'finance_officer': ['Abdifitah'],
    'admin_hr_officer': ['Fahmo'],
    'programme_director': ['Peter Mwaura'],
    # not named on the templates: a starting guess, to be corrected under HIJRA Codes > Roles
    'officer_in_charge': ['Peter Mwaura'],
    'fa_officer': ['Fahmo'],
}


def migrate(cr, version):
    """Projects and budget codes move to the Project app.

    Every HIJRA project becomes a project (named with its code, e.g. AARAN) and every budget
    code becomes a task of that project. The old ids are kept in two mapping tables so the
    modules that pointed at the old records can re-point them; the old tables stay untouched.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _copy_codes(env)
    _assign_roles(env)


def _copy_codes(env):
    cr = env.cr
    cr.execute("SELECT to_regclass('hijra_project'), to_regclass('hijra_budget')")
    project_table, budget_table = cr.fetchone()
    if not project_table or not budget_table:
        return
    cr.execute("CREATE TABLE IF NOT EXISTS hijra_project_map (old_id integer PRIMARY KEY, new_id integer NOT NULL)")
    cr.execute("CREATE TABLE IF NOT EXISTS hijra_budget_map (old_id integer PRIMARY KEY, new_id integer NOT NULL)")

    quiet = dict(tracking_disable=True, mail_create_nolog=True, mail_create_nosubscribe=True,
                 mail_notrack=True, active_test=False)
    Project = env['project.project'].with_context(**quiet)
    Task = env['project.task'].with_context(**quiet)

    cr.execute("SELECT id, code, name, active FROM hijra_project ORDER BY id")
    for old_id, code, name, active in cr.fetchall():
        cr.execute("SELECT new_id FROM hijra_project_map WHERE old_id = %s", (old_id,))
        if cr.fetchone():
            continue
        project = Project.search([('name', '=', code)], limit=1)
        if not project:
            project = Project.create({
                'name': code,
                'description': '<p>%s</p>' % name if name else False,
                'active': bool(active),
                'user_id': False,
                'privacy_visibility': 'employees',
            })
        cr.execute("INSERT INTO hijra_project_map (old_id, new_id) VALUES (%s, %s)", (old_id, project.id))

    cr.execute("""
        SELECT b.id, m.new_id, b.code, b.name, b.active
          FROM hijra_budget b
          JOIN hijra_project_map m ON m.old_id = b.project_id
         ORDER BY b.id
    """)
    for old_id, project_id, code, name, active in cr.fetchall():
        cr.execute("SELECT new_id FROM hijra_budget_map WHERE old_id = %s", (old_id,))
        if cr.fetchone():
            continue
        task = Task.search([('project_id', '=', project_id), ('budget_code', '=', code)], limit=1)
        if not task:
            task = Task.create({
                'name': name or code,
                'project_id': project_id,
                'budget_code': code,
                'active': bool(active),
                'user_ids': [Command.clear()],
            })
        cr.execute("INSERT INTO hijra_budget_map (old_id, new_id) VALUES (%s, %s)", (old_id, task.id))
    _logger.info("HIJRA codes moved to the Project app")


def _assign_roles(env):
    Role = env['hijra.role'].with_context(active_test=False)
    Users = env['res.users']
    for code, names in ROLE_PEOPLE.items():
        role = Role.search([('code', '=', code)], limit=1)
        if not role or role.user_ids:
            continue
        for name in names:
            users = Users.search([('name', 'ilike', name), ('share', '=', False)])
            if len(users) == 1:
                role.user_ids = [Command.link(users.id)]
            else:
                _logger.warning("Role %s: found %d users matching '%s'", code, len(users), name)
