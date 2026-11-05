{
    'name': 'HIJRA Goods and Services Received',
    'summary': 'Goods received note and service completion note for purchase orders',
    'description': """
The receiving step of HIJRA's procurement cycle:

* Goods Received Note (GRN) from a confirmed purchase order: quantities ordered and received (partial
  deliveries supported), the documents received, signed by the person who receives the goods and by a
  different person who checks them. Prints in the HIJRA template.
* Service Completion Note for services: drafted from the order (like the committee minutes) and edited,
  then approved by the programme manager. Prints in the HIJRA format.
* Both appear as steps of the procurement file and in its Print All Documents.
    """,
    'version': '20.0.1.0.0',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'depends': ['hijra_procurement'],
    'data': [
        'security/ir.access.csv',
        'data/sequence.xml',
        'report/receipts_report.xml',
        'views/grn_views.xml',
        'views/completion_views.xml',
        'views/purchase_order_views.xml',
        'views/menus.xml',
    ],
    'application': False,
    'installable': True,
}
