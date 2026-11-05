{
    'name': 'HIJRA Supporting Documents',
    'summary': 'Expenditure types with their required supporting documents, a checklist on every payment, and a printable pack',
    'description': """
The back-up documents a payment needs, by type of expenditure (from the Concern supporting documents
checklist):

* Expenditure types, each with its own list of supporting documents (standard or optional). Add types
  and change their documents at any time; only administrators edit them.
* A Supporting Documents tab on every payment: tick each document as available, upload it if you wish,
  or waive it with a note. Documents the system makes (requisition, quotes, evaluation, order, goods
  received or completion note, voucher) tick themselves.
* Posting is blocked while a standard document is missing, unless an override reason is written.
* Print Pack: a checklist cover sheet, then every document in order; uploaded PDFs and images are
  printed automatically.
    """,
    'version': '20.0.1.0.0',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['hijra_receipts', 'hijra_procurement_payment'],
    'data': [
        'security/ir.access.csv',
        'report/pack_report.xml',
        'views/supporting_views.xml',
        'views/finance_transaction_views.xml',
        'views/purchase_request_views.xml',
        'views/menus.xml',
        'data/supporting_docs_data.xml',
    ],
    'application': False,
    'installable': True,
}
