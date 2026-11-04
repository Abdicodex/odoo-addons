{
    'name': 'HIJRA Terminology',
    'summary': 'Calls products "items" in the Purchase and Accounting screens',
    'description': """
HIJRA buys services and goods alike, so "product" reads wrongly. This module renames it to
"Item" in the Purchase menus, on the purchase order and on invoice lines.
    """,
    'version': '20.0.1.0.0',
    'category': 'Hidden',
    'license': 'LGPL-3',
    'depends': ['purchase', 'account'],
    'data': [
        'views/terms_views.xml',
    ],
    'application': False,
    'installable': True,
}
