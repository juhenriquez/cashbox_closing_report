from odoo import api, fields, models
import logging

_logger = logging.getLogger(__name__)


class CashboxReportCashier(models.AbstractModel):
    _name = 'report.cashbox_closing_report.report_cashbox_document'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['cashbox.closing'].browse(self._context.get(
            'active_id'))
        return {
            'doc_ids': docids,
            'doc_model': data['model'],
            'docs': docs,
            'data': data['data'],
        }
