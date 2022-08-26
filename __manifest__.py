{
    'name': 'Reporte Cierre de Ventas',
    'version': '13.0.1.0.2',
    'category': '',
    'summary': "Reporte Cierre de Ventas",
    'author': 'Yasmany Castillo <yasmany003@gmail.com>',
    'license': 'AGPL-3',
    'depends': ['l10n_do_accounting'],
    'data': [
        'security/ir.model.access.csv',
        'data/cashbox_data.xml',
        'reports/cashbox_report.xml',
        'views/cashbox_closing_view.xml',
    ],
}
