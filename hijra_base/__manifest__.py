{
    'name': 'HIJRA Base',
    'summary': 'Shared HIJRA codes: projects, budget codes, funds and locations',
    'description': """
Global lists used across HIJRA modules (requisitions, and later budgets,
payments and reports): projects, budget codes per project, funds and
locations.
    """,
    'version': '20.0.1.0.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'depends': ['base'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'views/codes_views.xml',
    ],
    'application': False,
    'installable': True,
}
