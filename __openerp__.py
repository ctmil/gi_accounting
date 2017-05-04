{
    'name': 'GI Accounting',
    'category': 'Sales',
    'version': '0.1',
    'depends': ['base','account','branches','l10n_ar_invoice','pagos_tarjeta_credito','l10n_ar_fpoc','account_voucher'],
    'data': [
	'account_view.xml',
	'account_report.xml',
	#'report_movimientos_caja.xml',
	'security/ir.model.access.csv',
    ],
    'demo': [
    ],
    'qweb': [],
    'installable': True,
}
