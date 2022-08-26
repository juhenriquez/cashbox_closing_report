from datetime import date
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CashboxClosingReport(models.Model):
    _name = 'cashbox.closing'
    _description = 'Cashbox report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date'

    name = fields.Char(
        string="Referencia",
        required=True,
        readonly=True,
        copy=False,
        default='Nuevo',
    )
    date = fields.Date(string="Fecha", default=fields.Date.context_today)
    note = fields.Text(string="Observaciones", copy=False, )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Compañia',
        default=lambda self: self.env.user.company_id,
        required=True,
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Usuario',
        default=lambda self: self.env.user,
        required=True,
    )
    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diario',
        domain="[('type', '=', 'sale')]",
        required=True,
    )
    journal_bank_ids = fields.Many2many(
        comodel_name='account.journal',
        string='Diarios de pago',
        domain="[('type', 'in', ['cash', 'bank'])]",
        required=True,
    )
    state = fields.Selection(
        string="Estado",
        selection=[
            ('draft', 'Borrador'),
            ('confirmed', 'Confirmado'),
            ('accepted', 'Aceptado'),
            ('denied', 'Rechazado'),
            ('cancel', 'Cancelado'),
        ],
        required=False,
        default='draft',
        copy=False,
    )

    @api.model
    def create(self, values):
        if not values.get('name', False) or values['name'] == _('New'):
            values['name'] = self.env['ir.sequence'].next_by_code(
                'cashbox.report') or _('New')
        return super().create(values)

    def action_confirmed(self):
        self.write({'state': 'confirmed'})

    def action_accepted(self):
        self.write({'state': 'accepted'})

    def action_denied(self):
        self.write({'state': 'denied'})

    def action_cancel(self):
        for rec in self:
            if rec.state != 'draft':
                raise ValidationError("No puede cancelar un registro sino "
                                      "esta borrador.")
        self.write({'state': 'cancel'})

    def action_to_draft(self):
        self.write({'state': 'draft'})

    def _get_cash_invoice(self, invoice):
        if invoice.invoice_payment_term_id.id != 1:
            return False
        return True

    def _prepare_payment_info(self):
        totals = {}
        payment_details = []
        domain = [
            ('payment_date', '=', self.date),
            ('payment_type', '=', 'inbound'),
            ('journal_id', 'in', self.journal_bank_ids.ids),
            ('company_id', '=', self.env.user.company_id.id),
            ('state', 'in', ['posted', 'reconciled']),
        ]
        payments = self.env['account.payment'].search(domain)
        for payment in payments:
            payment_date = date.strftime(payment.payment_date, '%d/%m/%Y')
            payment_form = payment.journal_id.l10n_do_payment_form
            cash_amount = 0.0
            check_amount = 0.0

            if payment_form in ['cash', 'card']:
                cash_amount = payment.amount
            elif payment_form == 'bank':
                check_amount = payment.amount

            payment_details.append({
                'date': payment_date,
                'name': payment.name,
                'currency_id': payment.currency_id.ids,
                'partner': payment.partner_id.name,
                'cash': cash_amount,
                'check': check_amount,
                'total': payment.amount,
            })
            if payment.currency_id.name not in totals.keys():
                totals[payment.currency_id.name] = {
                    'currency_id': payment.currency_id.ids,
                    'cash': cash_amount,
                    'check': check_amount,
                    'total': payment.amount,
                }
            else:
                totals[payment.currency_id.name]['cash'] += cash_amount
                totals[payment.currency_id.name]['check'] += check_amount
                totals[payment.currency_id.name]['total'] += payment.amount

        return {'payment_details': payment_details, 'totals': totals}

    def _prepare_invoice_detail(self):
        invoice_details = {
            'cash': [],
            'credit': [],
            'total_by_currency': [],
        }
        domain = [
            ('type', 'in', ['out_invoice', 'out_refund']),
            ('invoice_date', '=', self.date),
            ('invoice_payment_state', 'in', ['not_paid', 'paid']),
            ('company_id', '=', self.env.user.company_id.id),
            ('journal_id', '=', self.journal_id.id)]
        invoices = self.env['account.move'].search(domain, order="name asc")

        for inv in invoices:
            cash_invoice = self._get_cash_invoice(inv)
            invoice_date = date.strftime(inv.invoice_date, '%d/%m/%Y')
            if cash_invoice and inv.type != 'out_refund':
                cash_invoice_dict = {
                    'id': inv.id,
                    'date': invoice_date,
                    'number': inv.name,
                    'currency_id': inv.currency_id.ids,
                    'currency_name': inv.currency_id.name,
                    'partner': inv.partner_id.name,
                    'salesman': inv.user_id.name,
                    'discount_amount': 0.0,
                    'discount_percent': 0.0,
                    'cash': 0.0,
                    'credit_card': 0.0,
                    'check': 0.0,
                    'credit_note': 0.0,
                    'total': 0.0,
                }

                for rec in inv._get_reconciled_info_JSON_values():
                    journal = self.env['account.journal'].search([
                        ('name', '=', rec.get('journal_name'))
                    ])
                    amount = rec.get('amount')
                    refund = True if rec.get('ref')[:3] == 'B04' else False

                    payment_form = journal.l10n_do_payment_form
                    if not refund and journal.type == 'cash':
                        cash_invoice_dict['cash'] += amount
                    elif not refund and journal.type == 'bank':
                        if payment_form == 'bank':
                            cash_invoice_dict['check'] += amount
                        elif payment_form == 'card':
                            cash_invoice_dict['credit_card'] += amount
                    elif refund:
                        cash_invoice_dict['credit_note'] += amount

                    cash_invoice_dict['total'] += amount

                invoice_details['cash'].append(cash_invoice_dict)
            else:
                invoice_details['credit'].append({
                    'id': inv.id,
                    'date': invoice_date,
                    'currency_id': inv.currency_id.ids,
                    'currency_name': inv.currency_id.name,
                    'number': inv.name,
                    'partner': inv.partner_id.name,
                    'salesman': inv.user_id.name,
                    'amount': inv.amount_total_signed,
                })

        cash_total, credit_total = {}, {}
        for key, value in invoice_details.items():
            if key == 'cash':
                for item in value:
                    code = item.get('currency_name')
                    if code not in cash_total.keys():
                        cash_total[code] = {
                            'currency_id': item.get('currency_id'),
                            'discount_amount': item.get('discount_amount'),
                            'discount_percent': item.get('discount_percent'),
                            'cash': item.get('cash'),
                            'credit_card': item.get('credit_card'),
                            'check': item.get('check'),
                            'credit_note': item.get('credit_note'),
                            'total': item.get('total'),
                        }
                    else:
                        cash_total[code]['discount_amount'] += item.get(
                            'discount_amount')
                        cash_total[code]['discount_percent'] += item.get(
                            'discount_percent')
                        cash_total[code]['cash'] += item.get('cash')
                        cash_total[code]['credit_card'] += item.get(
                            'credit_card')
                        cash_total[code]['check'] += item.get('check')
                        cash_total[code]['credit_note'] += item.get(
                            'credit_note')
                        cash_total[code]['total'] += item.get('total')
            else:
                for item in value:
                    code = item.get('currency_name')
                    if code not in credit_total.keys():
                        credit_total[code] = {
                            'currency_id': item.get('currency_id'),
                            'total_amount': item.get('amount'),
                        }
                    else:
                        credit_total[code]['total_amount'] += item.get('amount')

        invoice_details.update({
            'credit_total': credit_total,
            'cash_total': cash_total,
        })
        return invoice_details

    @api.model
    def prepare_data(self):
        invoice_details = self._prepare_invoice_detail()
        payment_data = self._prepare_payment_info()
        data = {
            'cash_invoices': invoice_details['cash'],
            'cash_invoice_totals': invoice_details['cash_total'],
            'credit_invoices': invoice_details['credit'],
            'credit_invoices_totals': invoice_details['credit_total'],
            'payments': payment_data['payment_details'],
            'payment_totals': payment_data['totals'],
        }
        return data

    def _print_report(self, data):
        report_name = 'cashbox_closing_report.action_cashbox_report'
        return self.env.ref(report_name).report_action(self, data=data)

    def check_report(self):
        self.ensure_one()
        data = {
            'data': self.prepare_data(),
            'ids': self.ids,
            'model': self._name,
        }

        return self._print_report(data)
