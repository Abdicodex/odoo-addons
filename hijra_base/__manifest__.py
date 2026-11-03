{
    'name': 'HIJRA Base',
    'summary': 'Shared HIJRA codes: projects, budget codes, funds and locations',
    'description': """
Global lists used across HIJRA modules (requisitions, and later budgets,
payments and reports): projects, budget codes per project, funds and
locations, plus each employee's signature image.
    """,
    'version': '20.0.1.1.0',
    'category': 'Administration',
    'license': 'LGPL-3',
    'depends': ['base', 'hr'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'views/codes_views.xml',
        'views/hr_views.xml',
    ],
    'application': False,
    'installable': True,
}
