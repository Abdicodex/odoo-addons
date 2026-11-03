{
    'name': 'Electricity Meter Billing Master',
    'summary': 'Master data for electricity meter billing: customers, geography, transformers, houses and meter readings',
    'description': """
Master configuration and setup for an electricity meter billing business.

* Customer types and reasons (activation, deactivation, meter reading update)
* Geographic hierarchy: Region > District > Zone > Sub-Zone > Village/Neighbourhood
* Transformers, meter types and sub meter types
* Houses with an auto-generated supply number (ZONE_CODE-SUB_ZONE_PREFIX-SEQ), activation and
  deactivation with reasons, and meter reading updates with a full history
* Customers (unique customer ID, supporting documents, houses), collectors and technicians
* Zone report (opening balance, billed, paid, total due) and the Meter Reading History report
    """,
    'version': '20.0.1.0.0',
    'category': 'Services',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'contacts', 'account', 'hr'],
    'data': [
        'security/groups.xml',
        'security/ir.access.csv',
        'data/sequences.xml',
        'views/master_views.xml',
        'views/house_views.xml',
        'views/partner_views.xml',
        'views/zone_report_views.xml',
        'views/wizard_views.xml',
        'report/meter_reading_history_report.xml',
        'views/menus.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
}
