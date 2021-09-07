# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta
from functools import partial

import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
from odoo.osv.expression import AND
import base64

import time
from datetime import datetime

_logger = logging.getLogger(__name__)


class MyPosConfig(models.Model):
    _inherit = ['pos.config']

    carril = fields.Integer()


class PosSessionDolares(models.Model):
    _inherit = ['pos.session']


class InformeExel(models.TransientModel):
    _name = 'informe.excel.wizard'
    _description = 'Reporte Personalizado de Excel'

    def _default_start_date(self):
        """ Find the earliest start_date of the latests sessions """
        # restrict to configs available to the user
        config_ids = self.env['pos.config'].search([]).ids
        # exclude configs has not been opened for 2 days
        self.env.cr.execute("""
               SELECT
               max(start_at) as start,
               config_id
               FROM pos_session
               WHERE config_id = ANY(%s)
               AND start_at > (NOW() - INTERVAL '2 DAYS')
               GROUP BY config_id
           """, (config_ids,))
        latest_start_dates = [res['start'] for res in self.env.cr.dictfetchall()]
        # earliest of the latest sessions
        return latest_start_dates and min(latest_start_dates) or fields.Datetime.now()

    start_date = fields.Datetime(required=True, default=_default_start_date)
    end_date = fields.Datetime(required=True, default=fields.Datetime.now)

    def imprimir_accion_excel(self):
        url = "/reporte_excel/reporte_excel/?id_informe=" + str(self.id)
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    @api.onchange('start_date')
    def _onchange_start_date(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            self.end_date = self.start_date

    @api.onchange('end_date')
    def _onchange_end_date(self):
        if self.end_date and self.end_date < self.start_date:
            self.start_date = self.end_date


class PosDetailsSrlc(models.TransientModel):
    _inherit = ['pos.details.wizard']
    
    '''def _default_start_date(self):
        fecha_dma3 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%Y-%m-%d %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%Y-%m-%d')
        print(fecha_dma3, ' fecha local MST ')

        hora = datetime.strftime(dt, '%H:%M:%S')
        print(hora)
        turno = ''
        if hora >= '00:00:00' and hora <= '07:59:59':
            fecha_dma3 = fecha_dma3 + ' 00:00:00'
        if hora >= '08:00:00' and hora <= '16:59:59':
            fecha_dma3 = fecha_dma3 + ' 08:00:00'
        if hora >= '16:00:00' and hora <= '23:59:59':
            fecha_dma3 = fecha_dma3 + ' 16:00:00'
        return fecha_dma3

    start_date = fields.Datetime(required=True, default=_default_start_date)
    end_date = fields.Datetime(required=True, default=fields.Datetime.now)'''
    
    def _default_administrador(self):
        user = self.env["res.users"].search([('partner_id.function', '=', 'ADMINISTRADOR')])
        for i in user:
            return i.id

    cajero = fields.Many2one('res.users',string="Cajero",) # default=_default_cajero
    jefe_operaciones = fields.Many2one('res.users', string="Jefe de Operaciones", default=lambda self: self.env.user)
    administrador = fields.Many2one('res.users', string="Administrador", default=_default_administrador )

    pos_config_srlc_ids = fields.Many2many('pos.config' ) # default=lambda s: s.env['pos.config'].search([])
    total_efectivo = fields.Float(string="Total de Efectivo Entregado por el Cajero(a):",  required=False, )
    tabla_cuotas = fields.Many2many('pos.tabla_emergentes')

    boleto_emergente = fields.Boolean(string="Activar Boletos Emergentes",  )

    @api.onchange('boleto_emergente')
    def onchange_boleto(self):
        if self.boleto_emergente is False:
            self.update({
                'tabla_cuotas': [[5]]
            })
        else:
            pass

    @api.onchange('cajero')
    def onchange_informe(self):
        self.update({
            'pos_config_srlc_ids': [[5]],
            'tabla_cuotas': [[5]]
        })
        print(self.cajero)
        if not self.cajero:
            pass
        else:

            fecha_hoy = fields.Datetime.now()

            fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
            dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
            old_tz = pytz.timezone('UTC')
            new_tz = pytz.timezone('MST')
            fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
            fecha_dma3 = datetime.strftime(fecha_dma3, '%Y-%m-%d')

            fecha_dma2 = datetime.strftime(fecha_hoy, '%Y-%m-%d')
            sesion = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma3) + ' 15:00:00'),
                                                    ('stop_at', '<=', str(fecha_dma3) + ' 23:59:59')]) # ('user_id.id', '=', self.cajero.id)[-1]

            print(fecha_dma3, 'hola', sesion)

            '''sesion2 = self.env["pos.session"].search([])
            for ss2 in sesion2:
                # fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", ss2.start_at)
                dt = datetime.strptime(str(ss2.start_at), '%Y-%m-%d %H:%M:%S')
                old_tz = pytz.timezone('UTC')
                new_tz = pytz.timezone('MST')
                fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
                fecha_dma3 = datetime.strftime(fecha_dma3, '%Y-%m-%d %H:%M:%S')
                print(fecha_dma3, '---', ss2.start_at, ss2.name)'''

            # UTC ('start_at', '>=', str(fecha_dma2) + ' 14:00:00'),
            # ('stop_at', '<=', str(fecha_dma2) + ' 22:59:59')

            if not sesion:
                pass
            else:
                acum = 0
                for ss in sesion:
                    print(ss.start_at, ss.name)
                    acum += 1
                    # EMERGENTES
                    boletos_search = self.env["pos.boletos_emergentes"].search([('sesion', '=', ss.id),
                                                                                ('cajero', '=', self.cajero.id)])
                    # boletos = self.env["pos.boletos_emergentes"].browse(res.id)
                    for i in boletos_search:
                        datos = {
                            'tabla_cuotas': [[4, i.id, {}]]
                        }
                        tabla = self.update(datos)

                    # SESIONES
                    if acum == 1:
                        self.start_date = ss.start_at
                    self.end_date = fecha_dma2
                    # print(sesion.config_id.id)
                    # datos_participantes = {'pos_config_srlc_ids': [[0,0 sesion.config_id.id]]}
                    datos = {
                        'pos_config_srlc_ids': [[4, ss.config_id.id, {}]]} # 'id': sesion.config_id.id, 'name': sesion.config_id.name
                    x = self.update(datos)
                    # self.update(datos_participantes)

    def generate_report(self):
        sesion = self.env["pos.session"].search([('user_id.id', '=', self.cajero.id)])[-1]
        if not sesion:
            pass
        else:
            data = {'date_start': self.start_date, 'date_stop': self.end_date, 'config_ids': self.pos_config_srlc_ids.ids}
            '''if self.boleto_emergente:
                modelo_boletos = self.env["pos.boletos_emergentes"]
                datos = {
                    'fecha_del': self.start_date,
                    'fecha_al': self.end_date,
                    'cajero': self.cajero.id,
                    'jefe_operaciones': self.jefe_operaciones.id,
                    'sesion': sesion.id,
                }
                res = modelo_boletos.create(datos) # CREAR REGISTRO DE BOLETOS
                boletos = self.env["pos.boletos_emergentes"].browse(res.id)
                for i in self.tabla_cuotas:
                    datos_tabla = {
                        'tabla_cuotas': [
                            [0, 0, {
                                'id_boleto_emergente': res.id,
                                'cuota': i.cuota.id,
                                'cantidad': i.cantidad,
                                'costo_cuota': i.costo_cuota,
                                'total': i.total,
                            }]]}
                    print(datos_tabla)
                    x = boletos.write(datos_tabla) # AGREGAR DATOS DE BOLETOS EMERGENTES A LA TABLA DEL REGISTRO
                    # ////////////////////////*  AGREGAR CUOTAS A POS.ORDER  *////////////////////////////////
                    ventas = self.env["pos.order"]
                    for venta in range(i.cantidad):
                        total_civa = ((i.costo_cuota * i.cuota.taxes_id.amount)/ 100) + i.costo_cuota
                        datos = {
                            # 'name': str(sesion.name),
                            'session_id': sesion.id,
                            # 'pos_reference': func_id,
                            # 'cashier': self.cajero.id,
                            'jefe_operaciones': self.jefe_operaciones.id,
                            'user_id': self.cajero.id,
                            'amount_total': total_civa,
                            'state': 'emergente',
                            'amount_tax': 0,
                            'amount_paid': 0,
                            'amount_return': 0,
                            'company_id': 1,
                            'payment_ids': [],
                            'pricelist_id': 1,
                        }
                        order = ventas.create(datos)

                        orden_creada = self.env['pos.order'].search([('id', '=', order.id)])
                        taxes = ''

                        tabla_productos = {'lines': [[0, 0, {
                            'product_id': i.cuota.id,
                            'qty': 1,
                            'discount': 0,
                            'price_unit': i.costo_cuota,
                            'tax_ids_after_fiscal_position': i.cuota.taxes_id.id,
                            'price_subtotal': total_civa,
                            'price_subtotal_incl': total_civa,
                        }]]}
                        agregar_tabla = orden_creada.write(tabla_productos)

                        payment = self.env['pos.payment']
                        tabla_pago = {
                            'pos_order_id': orden_creada.id,
                            'payment_method_id': 1,
                            'amount': total_civa,
                        }
                        agregar_tablax2 = payment.create(tabla_pago)'''

            return self.env.ref('point_of_sale.sale_details_report').report_action([], data=data)


class ReporteQwebExtend(models.AbstractModel):
    _inherit = ['report.point_of_sale.report_saledetails']

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):
        """ Serialise the orders of the requested time period, configs and sessions.

        :param date_start: The dateTime to start, default today 00:00:00.
        :type date_start: str.
        :param date_stop: The dateTime to stop, default date_start + 23:59:59.
        :type date_stop: str.
        :param config_ids: Pos Config id's to include.
        :type config_ids: list of numbers.
        :param session_ids: Pos Config id's to include.
        :type session_ids: list of numbers.
        :returns: dict -- Serialised sales.
        """
        domain = [('state', 'in', ['paid', 'invoiced', 'done'])]
        if (session_ids):
            domain = AND([domain, [('session_id', 'in', session_ids)]])
        else:
            if date_start:
                date_start = fields.Datetime.from_string(date_start)
            else:
                # start by default today 00:00:00
                user_tz = pytz.timezone(self.env.context.get('tz') or self.env.user.tz or 'UTC')
                today = user_tz.localize(fields.Datetime.from_string(fields.Date.context_today(self)))
                date_start = today.astimezone(pytz.timezone('UTC'))

            if date_stop:
                date_stop = fields.Datetime.from_string(date_stop)
                # avoid a date_stop smaller than date_start
                if (date_stop < date_start):
                    date_stop = date_start + timedelta(days=1, seconds=-1)
            else:
                # stop by default today 23:59:59
                date_stop = date_start + timedelta(days=1, seconds=-1)

            domain = AND([domain,
                          [('date_order', '>=', fields.Datetime.to_string(date_start)),
                           ('date_order', '<=', fields.Datetime.to_string(date_stop))]
                          ])

            if config_ids:
                domain = AND([domain, [('config_id', 'in', config_ids)]])

        orders = self.env['pos.order'].search(domain) # ,order='amount_total asc'
        orders_count = self.env['pos.order'].search_count(domain)
        user_currency = self.env.company.currency_id

        total = 0.0
        products_sold = {}
        taxes = {}
        contador = 0
        folio_1 = ''
        folio_2 = ''
        for order in orders:
            contador += 1
            if contador == 1: # ENCUENTRA FOLIO XXX AL XXX
                folio_2 = order.folio
            if contador == orders_count:
                folio_1 = order.folio

            if user_currency != order.pricelist_id.currency_id:
                total += order.pricelist_id.currency_id._convert(
                    order.amount_total, user_currency, order.company_id, order.date_order or fields.Date.today())
            else:
                total += order.amount_total
            currency = order.session_id.currency_id
            # print(order.session_id.start_at)
            cont = 0
            for line in order.lines:
                if order.state == 'paid':
                    cont += 1
                else:
                    key = (line.product_id, line.price_unit, line.discount)
                    products_sold.setdefault(key, 0.0)
                    products_sold[key] += line.qty
                    if line.tax_ids_after_fiscal_position:
                        line_taxes = line.tax_ids_after_fiscal_position.compute_all(
                            line.price_unit * (1 - (line.discount or 0.0) / 100.0), currency, line.qty,
                            product=line.product_id, partner=line.order_id.partner_id or False)
                        for tax in line_taxes['taxes']:
                            taxes.setdefault(tax['id'], {'name': tax['name'], 'tax_amount': 0.0, 'base_amount': 0.0})
                            taxes[tax['id']]['tax_amount'] += tax['amount']
                            taxes[tax['id']]['base_amount'] += tax['base']
                    else:
                        taxes.setdefault(0, {'name': _('No Taxes'), 'tax_amount': 0.0, 'base_amount': 0.0})
                        taxes[0]['base_amount'] += line.price_subtotal_incl

        payment_ids = self.env["pos.payment"].search([('pos_order_id', 'in', orders.ids)]).ids

        cajero = ''
        jefe = ''
        administrador = ''
        fecha_apertura = ''
        carril = ''
        hora = ''
        total_efectivo = ''
        turno = ''
        boletos_emergentes = {}
        cc = self.env["pos.details.wizard"].search([])[-1]
        acum_total_cuota = 0
        for ccc in cc:
            # BOLETOS EMERGENTES
            for be in ccc.tabla_cuotas:
                acum_total_cuota += be.total
                key = (be.cuota, be.costo_cuota, be.total)
                boletos_emergentes.setdefault(key, 0.0)
                boletos_emergentes[key] += be.cantidad

            cajero = ccc.cajero.name
            jefe = ccc.jefe_operaciones.name
            administrador = ccc.administrador.name
            total_efectivo = ccc.total_efectivo
            for crl in ccc.pos_config_srlc_ids:
                carril = crl.carril
                sesion = self.env["pos.session"].search([('config_id.id', '=', crl.id)])[-1]  # ,('stop_at', '=', False)

                meses = ["Unknown",
                         "Enero",
                         "Febrero",
                         "Marzo",
                         "Abril",
                         "Mayo",
                         "Junio",
                         "Julio",
                         "Agosto",
                         "Septiembre",
                         "Octubre",
                         "Noviembre",
                         "Diciembre"]

                nombre_dias = [
                    "Unknown",
                    "Lunes",
                    "Martes",
                    "Miercoles",
                    "Jueves",
                    "Viernes",
                    "Sabado",
                    "Domingo"]

                nd = sesion.start_at.strftime("%A")
                if nd == 'Monday':
                    nd = nombre_dias[1]
                elif nd == 'Tuesday':
                    nd = nombre_dias[2]
                elif nd == 'Wednesday':
                    nd = nombre_dias[3]
                elif nd == 'Thursday':
                    nd = nombre_dias[4]
                elif nd == 'Friday':
                    nd = nombre_dias[5]
                elif nd == 'Saturday':
                    nd = nombre_dias[6]
                elif nd == 'Sunday':
                    nd = nombre_dias[7]
                # print(sesion.start_at.hour,sesion.start_at.minute, sesion.start_at)
                # matutino 12:00 am a 7:59 am
                # vespertino 8:00 am a 3:59 pm
                # nocturno 4:00 pm a 11:59 pm
                date_start_turno = ccc.start_date.strftime("%H:%M:%S")
                date_stop_turno = ccc.end_date.strftime("%H:%M:%S")
                if date_start_turno >= '00:00:00' and date_stop_turno <= '07:59:59':
                    turno = 'Matutino'
                elif date_start_turno >= '08:00:00' and date_stop_turno <= '16:59:59':
                    turno = 'Vespertino'
                elif date_start_turno >= '16:00:00' and date_stop_turno <= '23:59:59':
                    turno = 'Nocturno'
                fecha_apertura = str(nd) + " " + str(ccc.start_date.day) + " de " + meses[ccc.start_date.month] + ' a las ' + str(date_start_turno)
                print(fecha_apertura, ' ---- ', date_start_turno)

        if payment_ids:
            self.env.cr.execute("""
                    SELECT method.name, sum(amount) total
                    FROM pos_payment AS payment,
                         pos_payment_method AS method
                    WHERE payment.payment_method_id = method.id
                        AND payment.id IN %s
                    GROUP BY method.name
                """, (tuple(payment_ids),))
            payments = self.env.cr.dictfetchall()
        else:
            payments = []
        print('hola')
        data = {
            'currency_precision': user_currency.decimal_places,
            'total_paid': float(total),
            'payments': payments,
            'carril': carril,
            'fecha_apertura': fecha_apertura,
            'turno': turno,
            'nombre_cajero': cajero,
            'nombre_jefe': jefe,
            'total_boletos_emergentes': float("{:0.2f}".format(acum_total_cuota)),
            'total_efectivo': float("{:0.2f}".format(total_efectivo)),
            'folio_1': folio_1, # FOLIO DEL
            'folio_2': folio_2, # FOLIO AL
            'nombre_administrador': administrador,
            'company_name': self.env.company.name,
            'taxes': list(taxes.values()),
            'products': sorted([{
                'product_id': product.id,
                'product_name': product.name,
                'code': product.default_code,
                'quantity': int(qty),
                'price_unit': float("{:0.2f}".format(((price_unit * product.taxes_id.amount) / 100) + price_unit)),
                'discount': discount,
                'uom': product.uom_id.name,
                'cancelado': 0, # cancelados
                'total': float("%0.2f" % (((price_unit * product.taxes_id.amount) / 100) + price_unit)) * int(qty), # cantidad por precio
            } for (product, price_unit, discount), qty in products_sold.items()], key=lambda l: l['price_unit']),

            'boletos_emergentes': sorted([{
                'cuota': cuota.name,
                'cantidad': int(cantidad),
                'costo_cuota': float("{:0.2f}".format(costo_cuota)),
                'total_cuota': float("{:0.2f}".format(total)),
                # cantidad por precio
            } for (cuota, costo_cuota, total), cantidad in boletos_emergentes.items()], key=lambda l: l['cantidad'])
        }
        print(' Termino ', data)
        return data

    def _get_report_values(self, docids, data=None):
        data = dict(data or {})
        configs = self.env['pos.config'].browse(data['config_ids'])
        data.update(self.get_sale_details(data['date_start'], data['date_stop'],configs.ids))
        return data


class PosOrder(models.Model):
    _inherit = ['pos.order']

    folio = fields.Char('Folio')
    jefe_operaciones = fields.Many2one('res.users', string="Jefe de Operaciones Encargado de Subir los Boletos Emergentes")
    state = fields.Selection(
        [('draft', 'Nuevo'), ('cancel', 'Cancelado'), ('paid', 'Cobrado'), ('done', 'Terminado'), ('invoiced', 'Invoiced'),
         ('emergente', 'Emergente')],
        'Estatus', readonly=True, copy=False, default='draft')

    @api.model
    def create(self, values):
        session = self.env['pos.session'].browse(values['session_id'])
        values = self._complete_values_from_session(session, values)
        res = super(PosOrder, self).create(values)
        # values['folio'] = str(res.id).zfill(8)
        folio = str(res.id).zfill(8)
        datos = {
            'folio': folio,
        }
        b = self.env['pos.order'].browse(res.id)
        r = b.write(datos)
        return res