# -*- coding: utf-8 -*-
{
    'name': 'Low Sale Report | Sales Performance Report (Low) | Sales Performance Report | Poorly Performing Products Report | Underperforming Products Report | Low Sales Analytics',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Spot poorly performing products in seconds, set critical sale quantity thresholds, filter by period, variant/template, category, and export styled XLSX reports',
    'description': """
Sales Performance Report (Low) / Low Sale Report
================================================
Spot poorly performing products in seconds. Set a critical sale quantity, choose a period, and instantly see which products or variants are falling behind - straight from Sales > Reporting.

Features
--------
* Critical Level Filter - define an absolute quantity below which a product is considered low performing.
* Flexible Periods - analyse the current Week, Month, Year, or set a fully Custom date range.
* Variant or Template - analyse sales by individual product variants or roll them up by product template.
* Category & Sales Team filters.
* Show results in a native Odoo pivot view, or export a fully styled XLSX report with KPI cards.
* Configurable defaults under Settings > Sales > Low Sales Report.
""",
    'author': 'Uncanny Consulting Services LLP',
    'website': 'https://uncannycs.com',
    'license': 'Other proprietary',
    'depends': ['sale_management'],
    'external_dependencies': {
        'python': ['xlsxwriter'],
    },
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/low_sale_report_wizard_views.xml',
        'views/menu_views.xml',
    ],
    'images': ['static/description/banner.gif'],
    'price': 30,
    'currency': 'USD',
    'installable': True,
    'application': True,
    'auto_install': False,
}
