# -*- coding: utf-8 -*-
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    ucs_default_report_type = fields.Selection(
        [('variant', 'By Product Variant'), ('template', 'By Product Template')],
        string="Default Report Type",
        default='variant',
        config_parameter='low_sale_report_ucs.default_report_type',
        help="Define the default type for the low sales report. Should analysis be made for product templates in general or for product variants?"
    )
    ucs_default_critical_level = fields.Float(
        string="Default critical level (absolute quantity)",
        default=10.0,
        config_parameter='low_sale_report_ucs.default_critical_level',
        help="Define the default critical level for sales (default unit of measure), under which products are considered poorly performing."
    )
    ucs_default_period = fields.Selection(
        [
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('year', 'This Year'),
            ('last_week', 'Last Week'),
            ('last_month', 'Last Month'),
            ('last_year', 'Last Year'),
            ('custom', 'Custom'),
        ],
        string="Default analyzed period",
        default='month',
        config_parameter='low_sale_report_ucs.default_period',
        help="Define which period should be analyzed by default."
    )
