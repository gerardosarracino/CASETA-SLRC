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

    def _default_administrador(self):
        user = self.env["res.users"].search([('partner_id.function', '=', 'ADMINISTRADOR')])
        for i in user:
            return i.id

    cajero = fields.Many2one('res.users',string="Cajero",) # default=_default_cajero
    jefe_operaciones = fields.Many2one('res.users', string="Jefe de Operaciones", default=lambda self: self.env.user)
    administrador = fields.Many2one('res.users', string="Administrador", default=_default_administrador )

    pos_config_srlc_ids = fields.Many2many('pos.session' ) # default=lambda s: s.env['pos.config'].search([])

    carril_pos = fields.Many2one('pos.config', string="Seleccionar Carril" ) # default=lambda s: s.env['pos.config'].search([])
    total_efectivo = fields.Float(string="Total de Efectivo Entregado por el Cajero(a):",  required=False, )

    tabla_cuotas = fields.Many2many('pos.tabla_emergentes', store=True)

    tabla_tarifas = fields.Many2many('pos.tabla_fin_turno')

    boleto_emergente = fields.Boolean(string="Activar Boletos Emergentes",  )

    dolares = fields.Float('Dolares')
    dolar_tipo_cambio = fields.Float('Divisa del dolar', store=True)
    dolares_pesos = fields.Float('Dolares en Pesos', store=True)

    '''@api.onchange('boleto_emergente')
    def onchange_boleto(self):
        if self.boleto_emergente is False:
            self.update({
                'tabla_cuotas': [[5]]
            })
        else:
            pass'''

    @api.onchange('tabla_cuotas')
    def onchange_emergente_tabla(self):
        for i in self.tabla_cuotas:
            cantidad_folio = i.folio_al - i.folio_del
            for tb in self.tabla_tarifas:
                if str(tb.tarifa.id) == str(i.cuota.id):
                    i.cantidad = tb.efectivos + cantidad_folio
                    i.total = i.cantidad * i.costo_cuota

    @api.onchange('dolares')
    def onchange_dolares(self):
        self.dolar_tipo_cambio = self.env['ir.config_parameter'].sudo().get_param('pos_parametro.dolar')
        self.dolares_pesos = self.dolares * self.dolar_tipo_cambio

    def _default_turno(self):
        fecha_dma3 = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%Y-%m-%d %H:%M:%S')
        hora = datetime.strftime(dt, '%H:%M:%S')
        turno = ''
        if hora >= '07:00:00' and hora <= '14:59:59':
            turno = 'Matutino'
        if hora >= '15:00:00' and hora <= '22:59:59':
            turno = 'Vespertino'
        if hora >= '23:00:00' and hora <= '23:59:59' or hora >= '00:00:00' and hora <= '06:59:59':
            turno = 'Nocturno'
        return turno

    turno = fields.Char('Turno', default=_default_turno )
    select_inf = [('general', 'INFORME DE FIN DE TURNO GENERAL'), ('suplente', 'INFORME DE CAJERO SUPLENTE DURANTE TURNO')]
    tipo_inf = fields.Selection(select_inf, string="SELECCIONAR INFORME", required=True, default='general')

    @api.onchange('tipo_inf')
    def onchange_tipo_informe(self):
        self.update({
            'pos_config_srlc_ids': [[5]],
            'tabla_tarifas': [[5]],
            'tabla_cuotas': [[5]]
        })
        self.carril_pos = ''
        self.cajero = ''
        self.carril_pos = ''

    @api.onchange('carril_pos', 'cajero', 'start_date', 'end_date', 'boleto_emergente')
    def onchange_informe(self):
        self.update({
            'pos_config_srlc_ids': [[5]],
            'tabla_tarifas': [[5]]
        })

        fecha_hoy = datetime.strftime(self.start_date, '%Y-%m-%d')

        sesion = self.env["pos.session"].search([('turno', '=', self.turno),
                                                 ('config_id', '=', self.carril_pos.id),
                                                 ('start_at', '>=',
                                                  fecha_hoy + ' 00:00:00'),
                                                 ('stop_at', '<=',
                                                  fecha_hoy + ' 23:59:59')
                                                 ])
        if not sesion:
            pass
        else:
            for ss in sesion:
                datos = {
                    'pos_config_srlc_ids': [[4, ss.id, {}]]}  # 'id': sesion.config_id.id, 'name': sesion.config_id.name
                x = self.update(datos)

        if not self.carril_pos:
            pass
        else:
            if self.tipo_inf == 'general':
                search_tarifas = self.env["product.template"].search([])
                for i in search_tarifas:
                    if self.boleto_emergente is False:
                        self.update({
                            'tabla_cuotas': [[5]]
                        })

                    efectivos_auto = 0
                    if i.name == 'AUTO':
                        search_efectivos_auto = 0
                        for sesiones in sesion:
                            search_efectivos_auto += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id),('order_id.session_id','=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno ), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])

                        if search_efectivos_auto == 0:
                            pass
                        else:
                            efectivos_auto = search_efectivos_auto

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos_auto,
                                'recaudado': efectivos_auto * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price) ,
                            }]]}
                            r = self.write(tabla_tarifas)

                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos_auto,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'AUTO + 1 EJE':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])

                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)

                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'AUTO + 2 EJE':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)

                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
                    if i.name == 'AUTOBUS':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
                    if i.name == 'CAMION 2 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
                    if i.name == 'CAMION 3 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])

                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos
                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'CAMION 4 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
                    if i.name == 'CAMION 5 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'CAMION 6 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'CAMION + 7 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'MOTOCICLETA':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
                    if i.name == 'EMERGENCIAS':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'RESIDENTE':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'RESIDENTE + 1 EJE':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)

                    if i.name == 'RESIDENTE + 2 EJES':
                        search_efectivos = 0
                        for sesiones in sesion:
                            search_efectivos += self.env["pos.order.line"].search_count([
                                ('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                ('order_id.session_id.turno', '=', self.turno), ('order_id.state', '!=', 'emergente'),
                                ('order_id.state', '!=', 'closed')])
                        if search_efectivos == 0:
                            pass
                        else:
                            efectivos = search_efectivos

                            tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                'tarifa': i.id,
                                'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                'efectivos': efectivos,
                                'recaudado': efectivos * ((i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                            }]]}
                            r = self.write(tabla_tarifas)
                            if self.boleto_emergente:
                                datos_tabla = {
                                    'tabla_cuotas': [
                                        [0, 0, {
                                            'cuota': i.id,
                                            'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                            'cantidad': efectivos,
                                        }]]}
                                x = self.write(datos_tabla)
            else:
                print('SUPLENTE')
                if not self.cajero:
                    pass
                else:
                    search_tarifas = self.env["product.template"].search([])
                    for i in search_tarifas:
                        if self.boleto_emergente is False:
                            self.update({
                                'tabla_cuotas': [[5]]
                            })

                        efectivos_auto = 0
                        if i.name == 'AUTO':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])

                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos_auto = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos_auto,
                                    'recaudado': efectivos_auto * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),
                                }]]}
                                r = self.write(tabla_tarifas)

                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos_auto,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'AUTO + 1 EJE':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])

                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)

                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'AUTO + 2 EJE':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)

                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)
                        if i.name == 'AUTOBUS':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)
                        if i.name == 'CAMION 2 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)
                        if i.name == 'CAMION 3 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])

                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos
                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'CAMION 4 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)
                        if i.name == 'CAMION 5 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'CAMION 6 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'CAMION + 7 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'MOTOCICLETA':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)
                        if i.name == 'EMERGENCIAS':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'RESIDENTE':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'RESIDENTE + 1 EJE':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

                        if i.name == 'RESIDENTE + 2 EJES':
                            search_efectivos = 0
                            for sesiones in sesion:
                                search_efectivos += self.env["pos.order.line"].search_count(
                                    [('product_id', '=', i.id), ('order_id.session_id', '=', sesiones.id),
                                     ('order_id.session_id.turno', '=', self.turno),
                                     ('order_id.state', '!=', 'emergente'), ('order_id.state', '!=', 'closed'),
                                     ('order_id.user_id', '=', self.cajero.id)])
                            if search_efectivos == 0:
                                pass
                            else:
                                efectivos = search_efectivos

                                tabla_tarifas = {'tabla_tarifas': [[0, 0, {
                                    'tarifa': i.id,
                                    'costo_cuota': (i.list_price * (i.taxes_id.amount / 100)) + i.list_price,
                                    'efectivos': efectivos,
                                    'recaudado': efectivos * (
                                                (i.list_price * (i.taxes_id.amount / 100)) + i.list_price),

                                }]]}
                                r = self.write(tabla_tarifas)
                                if self.boleto_emergente:
                                    datos_tabla = {
                                        'tabla_cuotas': [
                                            [0, 0, {
                                                'cuota': i.id,
                                                'costo_cuota': (i.list_price * (
                                                            i.taxes_id.amount / 100)) + i.list_price,
                                                'cantidad': efectivos,
                                            }]]}
                                    x = self.write(datos_tabla)

    def generate_report(self):
        sesion = self.env["pos.session"].search([('turno', '=', self.turno),
                                                 ('config_id', '=', self.carril_pos.id)])[0]
        if not sesion:
            pass
        else:
            data = {'date_start': self.start_date, 'date_stop': self.end_date, 'config_ids': self.pos_config_srlc_ids.ids}

            if self.boleto_emergente:
                modelo_boletos = self.env["pos.boletos_emergentes"]
                datos = {
                    'fecha_del': self.start_date,
                    'fecha_al': self.end_date,
                    'cajero': self.cajero.id,
                    'jefe_operaciones': self.jefe_operaciones.id,
                    'sesion': sesion.id,
                    'carril': self.carril_pos.id,
                }
                res = modelo_boletos.create(datos) # CREAR REGISTRO DE BOLETOS
                boletos = self.env["pos.boletos_emergentes"].browse(res.id)
                for i in self.tabla_cuotas:
                    datos_tabla = {
                        'tabla_cuotas': [
                            [0, 0, {
                                'id_boleto_emergente': res.id,
                                'cuota': i.cuota.id,
                                'cantidad': i.folio_al - i.folio_del,
                                'costo_cuota': i.costo_cuota,
                                'total': i.total,
                            }]]}
                    print(datos_tabla)
                    x = boletos.write(datos_tabla) # AGREGAR DATOS DE BOLETOS EMERGENTES A LA TABLA DEL REGISTRO
                    # ////////////////////////*  AGREGAR CUOTAS A POS.ORDER  *////////////////////////////////
                    ventas = self.env["pos.order"]
                    # for venta in range(i.cantidad):
                    total_civa = i.costo_cuota # (i.costo_cuota * (i.cuota.taxes_id.amount / 100)) + i.costo_cuota
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

                    # orden_creada = self.env['pos.order'].search([('id', '=', order.id)])
                    taxes = ''

                    tabla_productos = {'lines': [[0, 0, {
                        'product_id': i.cuota.id,
                        'order_id': order.id,
                        'qty': 1,
                        'discount': 0,
                        'price_unit': i.cuota.list_price,
                        'tax_ids_after_fiscal_position': i.cuota.taxes_id.id,
                        'price_subtotal': i.costo_cuota,
                        'price_subtotal_incl': i.costo_cuota,
                    }]]}
                    agregar_tabla = order.write(tabla_productos)

                    payment = self.env['pos.payment']
                    tabla_pago = {
                        'pos_order_id': order.id,
                        'payment_method_id': 1,
                        'amount': total_civa,
                    }
                    agregar_tablax2 = payment.create(tabla_pago)

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
        print(domain, 'DOMAIN')
        orders = self.env['pos.order'].search(domain) # ,order='amount_total asc'
        orders_count = self.env['pos.order'].search_count(domain)
        user_currency = self.env.company.currency_id
        print(orders)
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
        dolares = ''
        dolar_tipo_cambio = ''
        dolares_pesos = ''
        boletos_emergentes = {}
        tabla_tarifas = {}
        cc = self.env["pos.details.wizard"].search([])[-1]
        acum_total_cuota = 0
        acum_total_tarifas = 0
        acum_total_recaudado = 0
        boleto_emergente_activador = False
        for ccc in cc:
            dolares = ccc.dolares
            dolar_tipo_cambio = ccc.dolar_tipo_cambio
            dolares_pesos = ccc.dolares_pesos
            boleto_emergente_activador = ccc.boleto_emergente
            # BOLETOS EMERGENTES
            for be in ccc.tabla_cuotas:
                acum_total_cuota += be.total
                key = (be.cuota, be.costo_cuota, be.total, be.folio_del, be.folio_al)
                boletos_emergentes.setdefault(key, 0.0)
                boletos_emergentes[key] += be.cantidad

            # TABLA DE TARIFAS
            for be in ccc.tabla_tarifas:
                acum_total_tarifas += be.efectivos
                acum_total_recaudado += be.recaudado
                key = (be.tarifa, be.costo_cuota, be.efectivos, be.cancelados, be.evadidos, be.errores, be.recaudado)
                tabla_tarifas.setdefault(key, 0.0)
                tabla_tarifas[key] += be.efectivos

            cajero = ccc.cajero.name
            jefe = ccc.jefe_operaciones.name
            administrador = ccc.administrador.name
            total_efectivo = ccc.total_efectivo
            carril = ccc.carril_pos.carril

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

            nd = ccc.start_date.strftime("%A")
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
            # matutino 12:00 am a 7:59 am
            # vespertino 8:00 am a 3:59 pm
            # nocturno 4:00 pm a 11:59 pm
            date_start_turno = ccc.start_date.strftime("%H:%M:%S")
            date_stop_turno = ccc.end_date.strftime("%H:%M:%S")

            fecha_inicio_turno = ccc.start_date  # time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
            dt = datetime.strptime(str(fecha_inicio_turno), '%Y-%m-%d %H:%M:%S')
            old_tz = pytz.timezone('UTC')
            new_tz = pytz.timezone('MST')
            fecha_inicio_turno = old_tz.localize(dt).astimezone(new_tz)
            hora_inicio = datetime.strftime(fecha_inicio_turno, '%H:%M:%S')
            # fecha_inicio_turno = datetime.strftime(fecha_inicio_turno, '%Y/%m/%d')
            # print(hora_inicio, ' -- ', date_start_turno)
            if date_start_turno >= '07:00:00' and date_stop_turno <= '14:59:59':
                turno = 'Matutino'
            elif date_start_turno >= '15:00:00' and date_stop_turno <= '22:59:59':
                turno = 'Vespertino'
            elif date_start_turno >= '23:00:00' and date_stop_turno <= '06:59:59':
                turno = 'Nocturno'

            fecha_apertura = str(nd) + " " + str(ccc.start_date.day) + " de " + meses[ccc.start_date.month] \
                             + ' a las ' + str(hora_inicio) + ' ' + turno

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
            'boleto_emergente_activador': boleto_emergente_activador,
            'total_boletos_emergentes': float("{:0.2f}".format(acum_total_cuota)),
            'total_efectivos': int(acum_total_tarifas),
            'acum_total_recaudado': float("{:0.2f}".format(acum_total_recaudado)),
            'total_efectivo': float("{:0.2f}".format(total_efectivo)),
            'folio_1': folio_1, # FOLIO DEL
            'folio_2': folio_2, # FOLIO AL
            'nombre_administrador': administrador,
            'dolares': float("{:0.2f}".format(dolares)),
            'dolar_tipo_cambio': float("{:0.2f}".format(dolar_tipo_cambio)),
            'dolares_pesos': float("{:0.2f}".format(dolares_pesos)),
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
                'folio_del': folio_del,
                'folio_al': folio_al,
                'cantidad': int(cantidad),
                'costo_cuota': float("{:0.2f}".format(costo_cuota)),
                'total_cuota': float("{:0.2f}".format(total)),
                # cantidad por precio
            } for (cuota, costo_cuota, total, folio_del, folio_al), cantidad in boletos_emergentes.items()], key=lambda l: l['cantidad']),

            'tabla_tarifas': sorted([{
                'tarifa': tarifa.name,
                'costo_cuota': float("{:0.2f}".format(costo_cuota)),
                'efectivos': efectivos,
                'cancelados': cancelados,
                'evadidos': evadidos,
                'errores': errores,
                'recaudado': float("{:0.2f}".format(recaudado)),
                # cantidad por precio
            } for (tarifa, costo_cuota, efectivos, cancelados, evadidos, errores, recaudado),
                  efectivos in tabla_tarifas.items()], key=lambda l: l['efectivos'])

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