{
    'name': 'HIJRA Finance Transactions',
    'summary': 'One simple form for payments and receipts, posted to the books as a journal entry',
    'description': """
A simple transaction form for the finance team: date, paid through (bank or cash), expense
or income account, vendor, project and the HIJRA codes. Saving it as posted creates the
double-entry journal entry, so nobody has to think in debits and credits.

* Expenses and income, with optional split lines (several accounts or projects)
* Approval before posting; finance managers can post directly
* One line per transaction in the list, with filters, grouping and pivot
* Printable payment voucher (HIJRA template) with the signatures of the people who signed
    """,
    'version': '20.0.1.0.0',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'depends': ['account', 'mail', 'hr', 'hijra_base', 'om_account_reconcile'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'data/sequence.xml',
        'report/transaction_report.xml',
        'views/finance_transaction_views.xml',
        'views/account_dashboard_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'installable': True,
}
