{
    'name': 'HIJRA Procurement Committee',
    'summary': 'Procurement bands, the fixed purchase committee, declarations, bid analysis, statement and minutes',
    'description': """
The committee step of HIJRA's procurement cycle, on top of the requisition and RFQ modules:

* Procurement bands: how many quotes, and whether the committee (and an observer from Concern
  Worldwide) is needed, by purchase value. The values are editable.
* The fixed purchase committee: chairperson, secretary and members, reviewed yearly.
* A committee session per RFQ: every member signs the Declaration of Impartiality and
  Confidentiality, the Summary of Bid Analysis, the Committee Statement and the Minutes in the
  system, with the signature from their employee profile.
* The four documents print in the HIJRA templates; the RFQ cannot be awarded before the
  committee has decided, and only to the vendor it selected.
    """,
    'version': '20.0.1.1.0',
    'category': 'Inventory/Purchase',
    'license': 'LGPL-3',
    'depends': ['purchase_request_rfq', 'hijra_base', 'project'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'data/bands.xml',
        'report/committee_report.xml',
        'views/band_views.xml',
        'views/committee_views.xml',
        'views/sign_wizard_views.xml',
        'views/rfq_views.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': False,
    'installable': True,
}
