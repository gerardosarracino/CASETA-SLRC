# -*- coding: utf-8 -*-
{
    'name': "slrc",

    'summary': """
        Modulo de personalización de POS para su uso en caseta de cobro
        San Luis Río Colorado
        """,

    'description': """
        Personalizar interfaz para su uso en caseta
    """,

    'author': "Galartec",
    'website': "http://www.galartec.com.com",

    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'point_of_sale'],

    'data': [
        'security/ir.model.access.csv',
        'views/pos_config.xml',
        'views/pos_order.xml',
        'views/boletos_emergentes.xml',
        'views/pos_informe_pdf.xml',
        'views/informe_excel.xml',
        'views/report_saledetails.xml',
        'data/paperformat.xml',
        'views/reporte_fin_turno.xml',
        'report/report_fin_turno.xml',
        'report/report_matutino.xml',
        'report/report_vespertino.xml',
        'report/report_nocturno.xml',
        'views/fin_turno_report.xml',
        'views/res_config_settings_views.xml',

    ],
    'qweb': [
        'static/src/xml/pos.xml',
        'static/src/xml/*.xml',

    ],
    # only loaded in demonstration mode
    'demo': [
        'demo/demo.xml',
    ],
}
