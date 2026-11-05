{
    'name': 'HIJRA Base',
    'summary': 'Shared HIJRA setup: funds, locations, roles and budget codes on the Project app',
    'description': """
Shared HIJRA setup used across modules: funds and locations, the roles of the
procurement and finance flows, budget codes on the Project app's tasks (a task is a
budget line of its project), plus each employee's signature image.
    """,
    'version': '20.0.2.1.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'depends': ['base', 'hr', 'project'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'data/roles.xml',
        'views/codes_views.xml',
        'views/project_views.xml',
        'views/hr_views.xml',
    ],
    'application': False,
    'installable': True,
}
