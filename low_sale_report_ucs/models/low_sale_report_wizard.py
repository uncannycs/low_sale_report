# -*- coding: utf-8 -*-
import base64
from datetime import datetime, time
import io

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LowSaleReportWizard(models.TransientModel):
    _name = 'low.sale.report.wizard'
    _description = 'Low Sale Report Wizard'

    # ------------------------------------------------------------------
    # Defaults (pulled from Settings > Sales > Low Sales Report)
    # ------------------------------------------------------------------
    def _default_report_type(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'low_sale_report_ucs.default_report_type', 'variant')
        return param if param in ('template', 'variant') else 'variant'

    def _default_critical_level(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'low_sale_report_ucs.default_critical_level', '10.0')
        try:
            return float(param)
        except (TypeError, ValueError):
            return 10.0

    def _default_report_period(self):
        param = self.env['ir.config_parameter'].sudo().get_param(
            'low_sale_report_ucs.default_period', 'month')
        valid_periods = ('week', 'month', 'year', 'last_week', 'last_month', 'last_year', 'custom')
        return param if param in valid_periods else 'month'

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    report_type = fields.Selection(
        [
            ('template', 'By product template'),
            ('variant', 'By product variant'),
        ],
        string='Report Type', required=True, default=_default_report_type)

    report_period = fields.Selection(
        [
            ('week', 'This Week'),
            ('month', 'This Month'),
            ('year', 'This Year'),
            ('last_week', 'Last Week'),
            ('last_month', 'Last Month'),
            ('last_year', 'Last Year'),
            ('custom', 'Custom'),
        ],
        string='Report Period', required=True, default=_default_report_period)

    date_from = fields.Date(string='From')
    date_to = fields.Date(string='To')

    critical_level = fields.Float(
        string='Critical Level (Absolute Quantity)',
        required=True, default=_default_critical_level)

    product_category_ids = fields.Many2many(
        'product.category', string='Product Categories')
    team_ids = fields.Many2many('crm.team', string='Sales Teams')

    # ------------------------------------------------------------------
    # Period helpers
    # ------------------------------------------------------------------
    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        period = res.get('report_period') or self._default_report_period()
        date_from, date_to = self._compute_period_dates(period)
        res.update({'date_from': date_from, 'date_to': date_to})
        return res

    @api.onchange('report_period')
    def _onchange_report_period(self):
        if self.report_period and self.report_period != 'custom':
            date_from, date_to = self._compute_period_dates(self.report_period)
            self.date_from = date_from
            self.date_to = date_to

    def _compute_period_dates(self, period):
        today = fields.Date.context_today(self)
        if period == 'week':
            date_from = today - relativedelta(days=today.weekday())
            date_to = today
        elif period == 'last_week':
            start_last_week = today - relativedelta(days=today.weekday() + 7)
            date_from = start_last_week
            date_to = start_last_week + relativedelta(days=6)
        elif period == 'month':
            date_from = today.replace(day=1)
            date_to = today
        elif period == 'last_month':
            first_this_month = today.replace(day=1)
            last_day_last_month = first_this_month - relativedelta(days=1)
            date_from = last_day_last_month.replace(day=1)
            date_to = last_day_last_month
        elif period == 'year':
            date_from = today.replace(month=1, day=1)
            date_to = today
        elif period == 'last_year':
            last_year = today.year - 1
            date_from = today.replace(year=last_year, month=1, day=1)
            date_to = today.replace(year=last_year, month=12, day=31)
        elif period == 'custom':
            date_from = self.date_from or today.replace(day=1)
            date_to = self.date_to or today
        else:  # month
            date_from = today.replace(day=1)
            date_to = today
        return date_from, date_to

    # ------------------------------------------------------------------
    # Data computation
    # ------------------------------------------------------------------
    def _get_groupby_field(self):
        return 'product_id' if self.report_type == 'variant' else 'product_tmpl_id'

    def _get_base_domain(self):
        self.ensure_one()
        domain = [('state', 'in', ('sale', 'done'))]
        if self.date_from:
            domain.append(('date', '>=', self.date_from))
        if self.date_to:
            date_to_end = datetime.combine(self.date_to, time.max)
            domain.append(('date', '<=', date_to_end))
        if self.product_category_ids:
            domain.append(('categ_id', 'child_of', self.product_category_ids.ids))
        if self.team_ids:
            domain.append(('team_id', 'in', self.team_ids.ids))
        return domain

    def _get_low_performing_data(self):
        """Aggregate sold quantity per product (or template) for the
        selected period/filters, and keep only the ones at or below the
        critical level."""
        self.ensure_one()
        domain = self._get_base_domain()
        groupby_field = self._get_groupby_field()
        Report = self.env['sale.report']

        results = []
        try:
            groups = Report._read_group(
                domain,
                groupby=[groupby_field],
                aggregates=['product_uom_qty:sum', 'price_total:sum']
            )
            for rec, qty, revenue in groups:
                if not rec:
                    continue
                qty = qty or 0.0
                revenue = revenue or 0.0
                if qty <= self.critical_level:
                    results.append({
                        'id': rec.id,
                        'name': rec.display_name or rec.name or '',
                        'internal_ref': rec.default_code or '',
                        'category': rec.categ_id.display_name if rec.categ_id else '',
                        'qty': qty,
                        'revenue': revenue,
                    })
        except Exception:
            groups = Report.read_group(
                domain, ['product_uom_qty:sum', 'price_total:sum'], [groupby_field])
            for group in groups:
                rec_val = group.get(groupby_field)
                if not rec_val:
                    continue
                res_id = rec_val[0] if isinstance(rec_val, (tuple, list)) else rec_val
                qty = group.get('product_uom_qty', 0.0) or 0.0
                revenue = group.get('price_total', 0.0) or 0.0
                if qty <= self.critical_level:
                    model = 'product.product' if groupby_field == 'product_id' else 'product.template'
                    rec = self.env[model].browse(res_id)
                    results.append({
                        'id': res_id,
                        'name': rec.display_name or (group.get(groupby_field)[1] if isinstance(group.get(groupby_field), (tuple, list)) else ''),
                        'internal_ref': rec.default_code or '',
                        'category': rec.categ_id.display_name if rec.categ_id else '',
                        'qty': qty,
                        'revenue': revenue,
                    })

        results.sort(key=lambda r: (r['qty'], r['revenue']))
        return results

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_show_in_odoo(self):
        self.ensure_one()
        data = self._get_low_performing_data()
        if not data:
            raise UserError(_(
                'No underperforming products found for the selected criteria.'))

        groupby_field = self._get_groupby_field()
        ids = [d['id'] for d in data]
        domain = self._get_base_domain() + [(groupby_field, 'in', ids)]

        return {
            'name': _('Low Sale Pivot View Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.report',
            'view_mode': 'pivot',
            'views': [(False, 'pivot')],
            'domain': domain,
            'context': {
                'group_by': [groupby_field],
                'pivot_measures': ['price_total', 'product_uom_qty'],
                'pivot_column_groupby': [],
            },
            'target': 'current',
        }


    def action_export_xlsx(self):
        self.ensure_one()
        data = self._get_low_performing_data()
        if not data:
            raise UserError(_(
                'No underperforming products found for the selected criteria.'))

        xlsx_bytes = self._build_xlsx(data)
        attachment = self.env['ir.attachment'].create({
            'name': 'Low_Sales_Report.xlsx',
            'type': 'binary',
            'datas': base64.b64encode(xlsx_bytes),
            'res_model': self._name,
            'res_id': self.id,
            'mimetype': ('application/vnd.openxmlformats-officedocument'
                         '.spreadsheetml.sheet'),
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/%s?download=true' % attachment.id,
            'target': 'self',
        }

    # ------------------------------------------------------------------
    # XLSX builder
    # ------------------------------------------------------------------
    def _build_xlsx(self, data):
        import xlsxwriter

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet('Low Sales Report')

        title_fmt = workbook.add_format({
            'bold': True, 'font_size': 18, 'align': 'center',
            'valign': 'vcenter', 'font_color': '#5B2C6F',
        })
        label_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#F2E9F7', 'border': 1,
        })
        value_fmt = workbook.add_format({'border': 1})
        kpi_label_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#EDEDED', 'align': 'center', 'border': 1,
        })
        kpi_value_fmt = workbook.add_format({
            'bold': True, 'font_size': 16, 'align': 'center', 'border': 1,
        })
        kpi_sub_fmt = workbook.add_format({
            'italic': True, 'align': 'center', 'font_size': 8, 'border': 1,
        })
        header_fmt = workbook.add_format({
            'bold': True, 'bg_color': '#5B2C6F', 'font_color': 'white',
            'border': 1, 'align': 'center',
        })
        cell_fmt = workbook.add_format({'border': 1})
        cell_alt_fmt = workbook.add_format({'border': 1, 'bg_color': '#F7F2FA'})
        qty_fmt = workbook.add_format({'border': 1, 'num_format': '#,##0.00'})
        qty_alt_fmt = workbook.add_format({'border': 1, 'bg_color': '#F7F2FA', 'num_format': '#,##0.00'})
        money_fmt = workbook.add_format({'border': 1, 'num_format': '$#,##0.00'})
        money_alt_fmt = workbook.add_format({
            'border': 1, 'bg_color': '#F7F2FA', 'num_format': '$#,##0.00',
        })
        status_fmt = workbook.add_format({
            'border': 1, 'bold': True, 'font_color': '#B8860B', 'align': 'center',
        })
        total_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'bg_color': '#EDEDED',
        })
        total_qty_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'bg_color': '#EDEDED', 'num_format': '#,##0.00',
        })
        total_money_fmt = workbook.add_format({
            'bold': True, 'border': 1, 'bg_color': '#EDEDED', 'num_format': '$#,##0.00',
        })

        sheet.merge_range('A1:G2', 'LOW SALES REPORT', title_fmt)

        period_label = dict(self._fields['report_period'].selection).get(
            self.report_period, '')
        categories = ', '.join(
            self.product_category_ids.mapped('display_name')) or 'All Categories'
        teams = ', '.join(self.team_ids.mapped('name')) or 'All Sales Teams'
        analysis_type = ('By product variants' if self.report_type == 'variant'
                          else 'By product templates')

        row = 3
        meta_rows = [
            ('Report Period:', (period_label or '').upper(),
             'Critical Qty Level:', '<= %.2f' % self.critical_level),
            ('Date Period:', '%s to %s' % (self.date_from or '', self.date_to or ''),
             'Sales Team Filter:', teams),
            ('Product Category:', categories,
             'Analysis Type:', analysis_type),
        ]
        for label1, value1, label2, value2 in meta_rows:
            sheet.write(row, 0, label1, label_fmt)
            sheet.merge_range(row, 1, row, 2, value1, value_fmt)
            sheet.write(row, 3, label2, label_fmt)
            sheet.merge_range(row, 4, row, 6, value2, value_fmt)
            row += 1

        row += 1
        total_qty = sum(d['qty'] for d in data)
        total_revenue = sum(d['revenue'] for d in data)

        sheet.merge_range(row, 0, row, 1, 'UNDERPERFORMING PRODUCTS', kpi_label_fmt)
        sheet.merge_range(row, 2, row, 4, 'TOTAL SOLD QUANTITY', kpi_label_fmt)
        sheet.merge_range(row, 5, row, 6, 'TOTAL REVENUE', kpi_label_fmt)
        row += 1
        sheet.merge_range(row, 0, row, 1, len(data), kpi_value_fmt)
        sheet.merge_range(row, 2, row, 4, total_qty, kpi_value_fmt)
        sheet.merge_range(row, 5, row, 6, total_revenue, kpi_value_fmt)
        row += 1
        sheet.merge_range(row, 0, row, 1, 'items below critical level', kpi_sub_fmt)
        sheet.merge_range(row, 2, row, 4, 'units combined', kpi_sub_fmt)
        sheet.merge_range(row, 5, row, 6, 'total in USD ($)', kpi_sub_fmt)
        row += 2

        headers = ['#', 'Internal Ref / Code', 'Product / Variant', 'Category',
                   'Sold Quantity', 'Revenue', 'Status']
        for col, header in enumerate(headers):
            sheet.write(row, col, header, header_fmt)
        row += 1

        for idx, d in enumerate(data, start=1):
            is_alt = idx % 2 == 0
            fmt = cell_alt_fmt if is_alt else cell_fmt
            q_fmt = qty_alt_fmt if is_alt else qty_fmt
            m_fmt = money_alt_fmt if is_alt else money_fmt
            sheet.write(row, 0, idx, fmt)
            sheet.write(row, 1, d['internal_ref'], fmt)
            sheet.write(row, 2, d['name'], fmt)
            sheet.write(row, 3, d['category'], fmt)
            sheet.write(row, 4, d['qty'], q_fmt)
            sheet.write(row, 5, d['revenue'], m_fmt)
            sheet.write(row, 6, 'LOW', status_fmt)
            row += 1

        sheet.merge_range(row, 0, row, 3, 'GRAND TOTAL', total_fmt)
        sheet.write(row, 4, total_qty, total_qty_fmt)
        sheet.write(row, 5, total_revenue, total_money_fmt)
        sheet.write(row, 6, '', total_fmt)

        sheet.set_column('A:A', 6)
        sheet.set_column('B:B', 18)
        sheet.set_column('C:C', 32)
        sheet.set_column('D:D', 24)
        sheet.set_column('E:E', 16)
        sheet.set_column('F:F', 16)
        sheet.set_column('G:G', 12)
        sheet.freeze_panes(0, 0)

        workbook.close()
        output.seek(0)
        return output.read()
