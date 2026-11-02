{
    'name': 'Purchase Requisitions',
    'summary': 'HIJRA purchase requisition form with approval, turned into RFQs',
    'description': """
Employees raise purchase requests, an approver reviews them and a buyer
turns approved requests into one RFQ per chosen vendor in the Purchase app.
    """,
    'version': '20.0.1.0.0',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'depends': ['purchase', 'mail'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'data/sequence.xml',
        'report/purchase_request_report.xml',
        'views/purchase_request_views.xml',
        'views/config_views.xml',
        'views/purchase_order_views.xml',
        'wizard/make_rfq_views.xml',
        'views/menus.xml',
    ],
    'application': False,
    'installable': True,
}
