{
    'name': 'HIJRA Pay Vendor',
    'summary': 'Pay a purchase order from one button: it opens the finance transaction form, filled in',
    'description': """
Connects purchasing and finance so paying a vendor takes a few clicks:

* A Pay Vendor button on the confirmed purchase order opens the finance transaction with the vendor,
  the amount still to pay, the description, the project and the budget line filled in.
* The transaction keeps its purchase order; the order shows what has been paid and what is left.
* When the order has a posted vendor bill, the payment settles it automatically.
    """,
    'version': '20.0.1.0.0',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['hijra_procurement', 'hijra_finance'],
    'data': [
        'security/ir.access.csv',
        'views/finance_transaction_views.xml',
        'views/purchase_order_views.xml',
    ],
    'application': False,
    'installable': True,
}
