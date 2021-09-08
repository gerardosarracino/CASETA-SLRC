# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import logging
from datetime import timedelta
from functools import partial
import time
import psycopg2
import pytz

from odoo import api, fields, models, tools, _
from odoo.tools import float_is_zero
from odoo.exceptions import UserError
from odoo.http import request
from odoo.osv.expression import AND
import base64
from datetime import datetime

_logger = logging.getLogger(__name__)


class PosReportesTurnoSrlc(models.TransientModel):
    _name = 'pos.reportes_turno.wizard'



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

    @api.onchange('start_date')
    def _default_sesiones(self):
        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")
        # FECHA UTC
        fecha_dma2 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        print(fecha_dma2, ' fecha local UTC')
        fecha_dma2 = datetime.strftime(fecha_hoy, '%Y-%m-%d')

        # FECHA MST HERMOSILLO
        '''fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')
        print(fecha_dma3, ' fecha local MST ')'''

        fecha_hora = time.strftime(hora, time.localtime())
        dt = datetime.strptime(str(fecha_hora), '%H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_hora = old_tz.localize(dt).astimezone(new_tz)
        hora = datetime.strftime(fecha_hora, '%H:%M:%S')

        sesion = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00')])
        print(sesion, ' SESION ')
        x = []
        if not sesion:
            pass
        else:
            datos = {}
            for ss in sesion:
                datos = {
                    'pos_config_srlc_ids': [
                        [4, ss.id, {}]]}  # 'id': sesion.config_id.id, 'name': sesion.config_id.name
                x = self.update(datos)

                fecha_dma3 = ss.start_at # time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
                dt = datetime.strptime(str(fecha_dma3), '%Y-%m-%d %H:%M:%S')
                old_tz = pytz.timezone('UTC')
                new_tz = pytz.timezone('MST')
                fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
                # fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')
                print(fecha_dma3, ' fecha local MST ')

                hora = datetime.strftime(fecha_dma3, '%H:%M:%S')
                print(hora)
                turno = ''
                '''if hora >= '00:00:00' and hora <= '07:59:59':
                    turno = 'Matutino'
                    self.total_dolares_matutino += ss.dolares
                if hora >= '08:00:00' and hora <= '16:59:59':
                    turno = 'Vespertino'
                    self.total_dolares_vespertino += ss.dolares
                if hora >= '16:00:00' and hora <= '23:59:59':
                    turno = 'Nocturno'
                    self.total_dolares_nocturno += ss.dolares'''

                if hora >= '07:00:00' and hora <= '14:59:59':
                    turno = 'Matutino'
                    self.total_dolares_matutino += ss.dolares
                if hora >= '15:00:00' and hora <= '22:59:59':
                    turno = 'Vespertino'
                    self.total_dolares_vespertino += ss.dolares
                if hora >= '23:00:00' and hora <= '23:59:59' or hora >= '00:00:00' and hora <= '06:59:59':
                    turno = 'Nocturno'
                    self.total_dolares_nocturno += ss.dolares
                print(turno, ' TURNO ')

    cajero = fields.Many2one('res.users',string="Cajero",) # default=_default_cajero
    jefe_operaciones = fields.Many2one('res.users',string="Jefe de Operaciones", required=False, )
    administrador = fields.Many2one('res.users',string="Administrador", required=False, )

    pos_config_srlc_ids = fields.Many2many('pos.session', store=True) # default=lambda s: s.env['pos.config'].search([])

    tabla_cuotas = fields.Many2many('pos.tabla_emergentes')

    boleto_emergente = fields.Boolean(string="Activar Boletos Emergentes",  )

    total_dolares_matutino = fields.Float(store=True) # compute='_datos_reporte'
    total_dolares_vespertino = fields.Float(store=True) # compute='_datos_reporte'
    total_dolares_nocturno = fields.Float(store=True) # compute='_datos_reporte'

    def _datos_reporte(self, date_start=False, date_stop=False, config_ids=False, session_ids=False):
        print('datos reporte')
        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")
        '''if hora >= '00:00:00' and hora <= '07:59:59':
            turno = 'Matutino'
        elif hora >= '08:00:00' and hora <= '16:59:59':
            turno = 'Vespertino'
        elif hora >= '16:00:00' and hora <= '23:59:59':
            turno = 'Nocturno'''

        if hora >= '07:00:00' and hora <= '14:59:59':
            turno = 'Matutino'
        if hora >= '15:00:00' and hora <= '22:59:59':
            turno = 'Vespertino'
        if hora >= '23:00:00' and hora <= '23:59:59' or hora >= '00:00:00' and hora <= '06:59:59':
            turno = 'Nocturno'

        report = self.env["pos.reportes_turno.wizard"].search([])[-1]
        for r in report:
            for i in r.pos_config_srlc_ids:
                sesion = self.env["pos.session"].search([('config_id.id', '=', i.id)]) # ,('stop_at', '!=', '')
                for s in sesion:
                    print(s.name, s.config_id.carril)
        self.total_dolares_matutino = 1

    def generate_report_turnomat(self):
        print(' GENERAR REPORTE DEL TURNO MAT')

        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")

        '''dt = datetime.strptime(str(fecha_dma2), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma2 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma2 = datetime.strftime(fecha_dma2, '%d/%m/%Y')'''

        # FECHA UTC
        fecha_dma2 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        print(fecha_dma2, ' fecha local UTC')
        fecha_dma2 = datetime.strftime(fecha_hoy, '%Y-%m-%d')

        # FECHA MST HERMOSILLO
        fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')
        print(fecha_dma3, ' fecha local MST ')

        fecha_hora = time.strftime(hora, time.localtime())
        dt = datetime.strptime(str(fecha_hora), '%H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_hora = old_tz.localize(dt).astimezone(new_tz)
        hora = datetime.strftime(fecha_hora, '%H:%M:%S')

        buscar_ordenes = []
        turno = ""
        # if hora >= '00:00:00' and hora <= '07:59:59':
        turno = 'Matutino'

        buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                       ('date_order', '<=', str(fecha_dma2) + ' 13:59:59')])

        # BUSCAR LAS SESIONES QUE CORRESPONDAN A ESTE TURNO!

        '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])'''

        buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')], order='config_id asc')

        '''buscar_sesiones_matx = self.env["pos.session"].search([])
        for ici in buscar_sesiones_matx:
            print(ici.start_at, ' fecha ', fecha_dma2 + ' 07:00:00')'''

        acum_pago_mat = 0
        cum_pagoiva_matutino = 0

        folio_carril1_motocicleta = 0
        folio_carril2_motocicleta = 0
        folio_carril3_motocicleta = 0
        folio_carril4_motocicleta = 0
        folio_carril5_motocicleta = 0
        folio_carril6_motocicleta = 0
        # AUTO
        folio_carril1_auto = 0
        folio_carril2_auto = 0
        folio_carril3_auto = 0
        folio_carril4_auto = 0
        folio_carril5_auto = 0
        folio_carril6_auto = 0
        # AUTO 1 EJE
        folio_carril1_auto1eje = 0
        folio_carril2_auto1eje = 0
        folio_carril3_auto1eje = 0
        folio_carril4_auto1eje = 0
        folio_carril5_auto1eje = 0
        folio_carril6_auto1eje = 0
        # AUTO 2 EJE
        folio_carril1_auto2eje = 0
        folio_carril2_auto2eje = 0
        folio_carril3_auto2eje = 0
        folio_carril4_auto2eje = 0
        folio_carril5_auto2eje = 0
        folio_carril6_auto2eje = 0
        # AUTOBUS
        folio_carril1_autobus = 0
        folio_carril2_autobus = 0
        folio_carril3_autobus = 0
        folio_carril4_autobus = 0
        folio_carril5_autobus = 0
        folio_carril6_autobus = 0
        # CAMION 2 ejes
        folio_carril1_camion2eje = 0
        folio_carril2_camion2eje = 0
        folio_carril3_camion2eje = 0
        folio_carril4_camion2eje = 0
        folio_carril5_camion2eje = 0
        folio_carril6_camion2eje = 0
        # CAMION 3 EJES
        folio_carril1_camion3eje = 0
        folio_carril2_camion3eje = 0
        folio_carril3_camion3eje = 0
        folio_carril4_camion3eje = 0
        folio_carril5_camion3eje = 0
        folio_carril6_camion3eje = 0
        # CAMION 4 EJES
        folio_carril1_camion4eje = 0
        folio_carril2_camion4eje = 0
        folio_carril3_camion4eje = 0
        folio_carril4_camion4eje = 0
        folio_carril5_camion4eje = 0
        folio_carril6_camion4eje = 0
        # CAMION 5 EJES
        folio_carril1_camion5eje = 0
        folio_carril2_camion5eje = 0
        folio_carril3_camion5eje = 0
        folio_carril4_camion5eje = 0
        folio_carril5_camion5eje = 0
        folio_carril6_camion5eje = 0
        # CAMION 6 EJES
        folio_carril1_camion6eje = 0
        folio_carril2_camion6eje = 0
        folio_carril3_camion6eje = 0
        folio_carril4_camion6eje = 0
        folio_carril5_camion6eje = 0
        folio_carril6_camion6eje = 0
        # CAMION 7 EJES
        folio_carril1_camion7eje = 0
        folio_carril2_camion7eje = 0
        folio_carril3_camion7eje = 0
        folio_carril4_camion7eje = 0
        folio_carril5_camion7eje = 0
        folio_carril6_camion7eje = 0
        # RESIDENTE
        folio_carril1_residente = 0
        folio_carril2_residente = 0
        folio_carril3_residente = 0
        folio_carril4_residente = 0
        folio_carril5_residente = 0
        folio_carril6_residente = 0
        # RESIDENTE 1 EJE
        folio_carril1_residente1eje = 0
        folio_carril2_residente1eje = 0
        folio_carril3_residente1eje = 0
        folio_carril4_residente1eje = 0
        folio_carril5_residente1eje = 0
        folio_carril6_residente1eje = 0
        # RESIDENTE 2 EJES
        folio_carril1_residente2eje = 0
        folio_carril2_residente2eje = 0
        folio_carril3_residente2eje = 0
        folio_carril4_residente2eje = 0
        folio_carril5_residente2eje = 0
        folio_carril6_residente2eje = 0

        # TARIFAS
        motocicleta_cuota = 0
        auto_cuota = 0
        auto_1eje_cuota = 0
        auto_2eje_cuota = 0
        autobus_cuota = 0
        camion2eje_cuota = 0
        camion3eje_cuota = 0
        camion4eje_cuota = 0
        camion5eje_cuota = 0
        camion6eje_cuota = 0
        camion7eje_cuota = 0
        residente_cuota = 0
        residente1eje_cuota = 0
        residente2eje_cuota = 0
        motocicleta_tarifa_siva = 0
        motocicleta_tarifa_iva = 0
        auto_tarifa_siva = 0
        auto_tarifa_iva = 0
        auto_1eje_tarifa_siva = 0
        auto_1eje_tarifa_iva = 0
        auto_2eje_tarifa_siva = 0
        auto_2eje_tarifa_iva = 0
        autobus_tarifa_siva = 0
        autobus_tarifa_iva = 0
        camion2eje_tarifa_siva = 0
        camion2eje_tarifa_iva = 0
        camion3eje_tarifa_siva = 0
        camion3eje_tarifa_iva = 0
        camion4eje_tarifa_siva = 0
        camion4eje_tarifa_iva = 0
        camion5eje_tarifa_siva = 0
        camion5eje_tarifa_iva = 0
        camion6eje_tarifa_siva = 0
        camion6eje_tarifa_iva = 0
        camion7eje_tarifa_siva = 0
        camion7eje_tarifa_iva = 0
        residente_tarifa_iva = 0
        residente_tarifa_siva = 0
        residente1eje_tarifa_iva = 0
        residente1eje_tarifa_siva = 0
        residente2eje_tarifa_iva = 0
        residente2eje_tarifa_siva = 0


        for mat in buscar_sesiones_mat:
            # buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])
            # print(mat.name, mat.config_id.name)

            buscar_peajes_motocicleta = self.env["product.template"].search([('name', '=', "MOTOCICLETA")])
            buscar_peajes_auto = self.env["product.template"].search([('name', '=', "AUTO")])
            buscar_peajes_auto1eje = self.env["product.template"].search([('name', '=', "AUTO 1 EJE")])
            buscar_peajes_auto2eje = self.env["product.template"].search([('name', '=', "AUTO 2 EJE")])
            buscar_peajes_autobus = self.env["product.template"].search([('name', '=', "AUTOBUS")])
            buscar_peajes_camion2eje = self.env["product.template"].search([('name', '=', "CAMION 2 EJES")])
            buscar_peajes_camion3eje = self.env["product.template"].search([('name', '=', "CAMION 3 EJES")])
            buscar_peajes_camion4eje = self.env["product.template"].search([('name', '=', "CAMION 4 EJES")])
            buscar_peajes_camion5eje = self.env["product.template"].search([('name', '=', "CAMION 5 EJES")])
            buscar_peajes_camion6eje = self.env["product.template"].search([('name', '=', "CAMION 6 EJES")])
            buscar_peajes_camion7eje = self.env["product.template"].search([('name', '=', "CAMION + 7 EJES")])
            buscar_peajes_residente = self.env["product.template"].search([('name', '=', "RESIDENTE")])
            buscar_peajes_residente1eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 1 EJE")])
            buscar_peajes_residente2eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 2 EJES")])


            buscar_ordenes_folios = self.env["pos.order"].search([('session_id', '=', mat.id)])
            for bof in buscar_ordenes_folios:
                # print(bof.name, ' bof ')
                for bp in buscar_peajes_motocicleta:                                                   # MOTOCICLETA

                    motocicleta_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    # TARIFA SIN IVA
                    motocicleta_tarifa_siva = bp.list_price
                    # TARIFA IVA
                    motocicleta_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)


                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto:                                                   # AUTO
                    auto_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_tarifa_siva = float(bp.list_price)
                    auto_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto1eje:                                                   # AUTO 1 EJE
                    auto_1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_1eje_tarifa_siva = float(bp.list_price)
                    auto_1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto2eje:                                                   # AUTO 2 EJES
                    auto_2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_2eje_tarifa_siva = float(bp.list_price)
                    auto_2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_autobus:                                                   # AUTOBBUS
                    autobus_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    autobus_tarifa_siva = float(bp.list_price)
                    autobus_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion2eje:                                                   # CAMION 2 EJE
                    camion2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion2eje_tarifa_siva = float(bp.list_price)
                    camion2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion3eje:                                                   # CAMION 3 EJES
                    camion3eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion3eje_tarifa_siva = float(bp.list_price)
                    camion3eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion4eje:                                                   # CAMION 4 EJES
                    camion4eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion4eje_tarifa_siva = float(bp.list_price)
                    camion4eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion5eje:                                                   # CAMION 5 EJES
                    camion5eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion5eje_tarifa_siva = float(bp.list_price)
                    camion5eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion6eje:                                                   # CAMION 6 EJES
                    camion6eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion6eje_tarifa_siva = float(bp.list_price)
                    camion6eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion7eje:                                                   # CAMION 7 EJES
                    camion7eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion7eje_tarifa_siva = float(bp.list_price)
                    camion7eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente:                                                   # RESIDENTE
                    residente_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    residente_tarifa_siva = float(bp.list_price)
                    residente_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente1eje:                                                   # RESIDENTE 1 EJE
                    residente1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente1eje_tarifa_siva = float(bp.list_price)
                    residente1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente2eje:                                                   # RESIDENTE 2 EJE
                    residente2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente2eje_tarifa_siva = float(bp.list_price)
                    residente2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])


            '''for pagos in buscar_pagos:
                cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax'''

        print(buscar_sesiones_mat, ' si entro matutino ')


        data = {'date_start': self.start_date,
                'date_stop': self.end_date,
                'config_ids': self.pos_config_srlc_ids.ids,

                # PEAJES
                'motocicleta_cuota': motocicleta_cuota,
                'auto_cuota': auto_cuota,
                'auto_1eje_cuota': float(auto_1eje_cuota),
                'auto_2eje_cuota': auto_2eje_cuota,
                'autobus_cuota': autobus_cuota,
                'camion2eje_cuota': camion2eje_cuota,
                'camion3eje_cuota': camion3eje_cuota,
                'camion4eje_cuota': camion4eje_cuota,
                'camion5eje_cuota': camion5eje_cuota,
                'camion6eje_cuota': camion6eje_cuota,
                'camion7eje_cuota': camion7eje_cuota,
                'residente_cuota': residente_cuota,
                'residente1eje_cuota': residente1eje_cuota,
                'residente2eje_cuota': residente2eje_cuota,

                # FOLIOS POR CARRIL
                # CARRIL 1
                'folio_carril1_motocicleta': folio_carril1_motocicleta,
                'folio_carril1_auto': folio_carril1_auto,
                'folio_carril1_auto1eje': folio_carril1_auto1eje,
                'folio_carril1_auto2eje': folio_carril1_auto2eje,
                'folio_carril1_autobus': folio_carril1_autobus,
                'folio_carril1_camion2eje': folio_carril1_camion2eje,
                'folio_carril1_camion3eje': folio_carril1_camion3eje,
                'folio_carril1_camion4eje': folio_carril1_camion4eje,
                'folio_carril1_camion5eje': folio_carril1_camion5eje,
                'folio_carril1_camion6eje': folio_carril1_camion6eje,
                'folio_carril1_camion7eje': folio_carril1_camion7eje,
                'folio_carril1_residente': folio_carril1_residente,
                'folio_carril1_residente1eje': folio_carril1_residente1eje,
                'folio_carril1_residente2eje': folio_carril1_residente2eje,
                # CARRIL 2
                'folio_carril2_motocicleta': folio_carril2_motocicleta,
                'folio_carril2_auto': folio_carril2_auto,
                'folio_carril2_auto1eje': folio_carril2_auto1eje,
                'folio_carril2_auto2eje': folio_carril2_auto2eje,
                'folio_carril2_autobus': folio_carril2_autobus,
                'folio_carril2_camion2eje': folio_carril2_camion2eje,
                'folio_carril2_camion3eje': folio_carril2_camion3eje,
                'folio_carril2_camion4eje': folio_carril2_camion4eje,
                'folio_carril2_camion5eje': folio_carril2_camion5eje,
                'folio_carril2_camion6eje': folio_carril2_camion6eje,
                'folio_carril2_camion7eje': folio_carril2_camion7eje,
                'folio_carril2_residente': folio_carril2_residente,
                'folio_carril2_residente1eje': folio_carril2_residente1eje,
                'folio_carril2_residente2eje': folio_carril2_residente2eje,
                # CARRIL 3
                'folio_carril3_motocicleta': folio_carril3_motocicleta,
                'folio_carril3_auto': folio_carril3_auto,
                'folio_carril3_auto1eje': folio_carril3_auto1eje,
                'folio_carril3_auto2eje': folio_carril3_auto2eje,
                'folio_carril3_autobus': folio_carril3_autobus,
                'folio_carril3_camion2eje': folio_carril3_camion2eje,
                'folio_carril3_camion3eje': folio_carril3_camion3eje,
                'folio_carril3_camion4eje': folio_carril3_camion4eje,
                'folio_carril3_camion5eje': folio_carril3_camion5eje,
                'folio_carril3_camion6eje': folio_carril3_camion6eje,
                'folio_carril3_camion7eje': folio_carril3_camion7eje,
                'folio_carril3_residente': folio_carril3_residente,
                'folio_carril3_residente1eje': folio_carril3_residente1eje,
                'folio_carril3_residente2eje': folio_carril3_residente2eje,
                # CARRIL 4
                'folio_carril4_motocicleta': folio_carril4_motocicleta,
                'folio_carril4_auto': folio_carril4_auto,
                'folio_carril4_auto1eje': folio_carril4_auto1eje,
                'folio_carril4_auto2eje': folio_carril4_auto2eje,
                'folio_carril4_autobus': folio_carril4_autobus,
                'folio_carril4_camion2eje': folio_carril4_camion2eje,
                'folio_carril4_camion3eje': folio_carril4_camion3eje,
                'folio_carril4_camion4eje': folio_carril4_camion4eje,
                'folio_carril4_camion5eje': folio_carril4_camion5eje,
                'folio_carril4_camion6eje': folio_carril4_camion6eje,
                'folio_carril4_camion7eje': folio_carril4_camion7eje,
                'folio_carril4_residente': folio_carril4_residente,
                'folio_carril4_residente1eje': folio_carril4_residente1eje,
                'folio_carril4_residente2eje': folio_carril4_residente2eje,
                # CARRIL 5
                'folio_carril5_motocicleta': folio_carril5_motocicleta,
                'folio_carril5_auto': folio_carril5_auto,
                'folio_carril5_auto1eje': folio_carril5_auto1eje,
                'folio_carril5_auto2eje': folio_carril5_auto2eje,
                'folio_carril5_autobus': folio_carril5_autobus,
                'folio_carril5_camion2eje': folio_carril5_camion2eje,
                'folio_carril5_camion3eje': folio_carril5_camion3eje,
                'folio_carril5_camion4eje': folio_carril5_camion4eje,
                'folio_carril5_camion5eje': folio_carril5_camion5eje,
                'folio_carril5_camion6eje': folio_carril5_camion6eje,
                'folio_carril5_camion7eje': folio_carril5_camion7eje,
                'folio_carril5_residente': folio_carril5_residente,
                'folio_carril5_residente1eje': folio_carril5_residente1eje,
                'folio_carril5_residente2eje': folio_carril5_residente2eje,
                # CARRIL 6
                'folio_carril6_motocicleta': folio_carril6_motocicleta,
                'folio_carril6_auto': folio_carril6_auto,
                'folio_carril6_auto1eje': folio_carril6_auto1eje,
                'folio_carril6_auto2eje': folio_carril6_auto2eje,
                'folio_carril6_autobus': folio_carril6_autobus,
                'folio_carril6_camion2eje': folio_carril6_camion2eje,
                'folio_carril6_camion3eje': folio_carril6_camion3eje,
                'folio_carril6_camion4eje': folio_carril6_camion4eje,
                'folio_carril6_camion5eje': folio_carril6_camion5eje,
                'folio_carril6_camion6eje': folio_carril6_camion6eje,
                'folio_carril6_camion7eje': folio_carril6_camion7eje,
                'folio_carril6_residente': folio_carril6_residente,
                'folio_carril6_residente1eje': folio_carril6_residente1eje,
                'folio_carril6_residente2eje': folio_carril6_residente2eje,

                # TARIFAS
                # TARIFAS SIN IVA
                'motocicleta_tarifa_siva': motocicleta_tarifa_siva,
                'auto_tarifa_siva': auto_tarifa_siva,
                'auto_1eje_tarifa_siva': auto_1eje_tarifa_siva,
                'auto_2eje_tarifa_siva': auto_2eje_tarifa_siva,
                'autobus_tarifa_siva': autobus_tarifa_siva,
                'camion2eje_tarifa_siva': camion2eje_tarifa_siva,
                'camion3eje_tarifa_siva': camion3eje_tarifa_siva,
                'camion4eje_tarifa_siva': camion4eje_tarifa_siva,
                'camion5eje_tarifa_siva': camion5eje_tarifa_siva,
                'camion6eje_tarifa_siva': camion6eje_tarifa_siva,
                'camion7eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente_tarifa_siva': camion7eje_tarifa_siva,
                'residente1eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente2eje_tarifa_siva': camion7eje_tarifa_siva,

                # TARIFAS IVA
                'motocicleta_tarifa_iva': motocicleta_tarifa_iva,
                'auto_tarifa_iva': auto_tarifa_iva,
                'auto_1eje_tarifa_iva': auto_1eje_tarifa_iva,
                'auto_2eje_tarifa_iva': auto_2eje_tarifa_iva,
                'autobus_tarifa_iva': autobus_tarifa_iva,
                'camion2eje_tarifa_iva': camion2eje_tarifa_iva,
                'camion3eje_tarifa_iva': camion3eje_tarifa_iva,
                'camion4eje_tarifa_iva': camion4eje_tarifa_iva,
                'camion5eje_tarifa_iva': camion5eje_tarifa_iva,
                'camion6eje_tarifa_iva': camion6eje_tarifa_iva,
                'camion7eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente_tarifa_iva': camion7eje_tarifa_iva,
                'residente1eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente2eje_tarifa_iva': camion7eje_tarifa_iva,

                }
        return self.env.ref('slrc.matutino_report_button').report_action([], data=data)

    def generate_report_turnovesp(self):
        print(' GENERAR REPORTE DEL TURNO VESPERTINO')

        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")

        '''dt = datetime.strptime(str(fecha_dma2), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma2 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma2 = datetime.strftime(fecha_dma2, '%d/%m/%Y')'''

        # FECHA UTC
        fecha_dma2 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        fecha_dma2 = datetime.strftime(fecha_hoy, '%Y-%m-%d')

        # FECHA MST HERMOSILLO
        fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')

        fecha_hora = time.strftime(hora, time.localtime())
        dt = datetime.strptime(str(fecha_hora), '%H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_hora = old_tz.localize(dt).astimezone(new_tz)
        hora = datetime.strftime(fecha_hora, '%H:%M:%S')

        buscar_ordenes = []
        turno = ""
        # if hora >= '00:00:00' and hora <= '07:59:59':
        turno = 'Vespertino'

        buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 14:00:00'),
                                                       ('date_order', '<=', str(fecha_dma2) + ' 22:59:59')])

        # BUSCAR LAS SESIONES QUE CORRESPONDAN A ESTE TURNO!

        '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])'''

        print(fecha_dma3, ' ---- ', fecha_dma2)

        buscar_sesiones_vesp = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 14:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 22:59:59')], order='config_id asc')

        '''buscar_sesiones_matx = self.env["pos.session"].search([])
        for ici in buscar_sesiones_matx:
            print(ici.start_at, ' fecha ', fecha_dma2 + ' 07:00:00')'''

        acum_pago_mat = 0
        cum_pagoiva_matutino = 0

        folio_carril1_motocicleta = 0
        folio_carril2_motocicleta = 0
        folio_carril3_motocicleta = 0
        folio_carril4_motocicleta = 0
        folio_carril5_motocicleta = 0
        folio_carril6_motocicleta = 0
        # AUTO
        folio_carril1_auto = 0
        folio_carril2_auto = 0
        folio_carril3_auto = 0
        folio_carril4_auto = 0
        folio_carril5_auto = 0
        folio_carril6_auto = 0
        # AUTO 1 EJE
        folio_carril1_auto1eje = 0
        folio_carril2_auto1eje = 0
        folio_carril3_auto1eje = 0
        folio_carril4_auto1eje = 0
        folio_carril5_auto1eje = 0
        folio_carril6_auto1eje = 0
        # AUTO 2 EJE
        folio_carril1_auto2eje = 0
        folio_carril2_auto2eje = 0
        folio_carril3_auto2eje = 0
        folio_carril4_auto2eje = 0
        folio_carril5_auto2eje = 0
        folio_carril6_auto2eje = 0
        # AUTOBUS
        folio_carril1_autobus = 0
        folio_carril2_autobus = 0
        folio_carril3_autobus = 0
        folio_carril4_autobus = 0
        folio_carril5_autobus = 0
        folio_carril6_autobus = 0
        # CAMION 2 ejes
        folio_carril1_camion2eje = 0
        folio_carril2_camion2eje = 0
        folio_carril3_camion2eje = 0
        folio_carril4_camion2eje = 0
        folio_carril5_camion2eje = 0
        folio_carril6_camion2eje = 0
        # CAMION 3 EJES
        folio_carril1_camion3eje = 0
        folio_carril2_camion3eje = 0
        folio_carril3_camion3eje = 0
        folio_carril4_camion3eje = 0
        folio_carril5_camion3eje = 0
        folio_carril6_camion3eje = 0
        # CAMION 4 EJES
        folio_carril1_camion4eje = 0
        folio_carril2_camion4eje = 0
        folio_carril3_camion4eje = 0
        folio_carril4_camion4eje = 0
        folio_carril5_camion4eje = 0
        folio_carril6_camion4eje = 0
        # CAMION 5 EJES
        folio_carril1_camion5eje = 0
        folio_carril2_camion5eje = 0
        folio_carril3_camion5eje = 0
        folio_carril4_camion5eje = 0
        folio_carril5_camion5eje = 0
        folio_carril6_camion5eje = 0
        # CAMION 6 EJES
        folio_carril1_camion6eje = 0
        folio_carril2_camion6eje = 0
        folio_carril3_camion6eje = 0
        folio_carril4_camion6eje = 0
        folio_carril5_camion6eje = 0
        folio_carril6_camion6eje = 0
        # CAMION 7 EJES
        folio_carril1_camion7eje = 0
        folio_carril2_camion7eje = 0
        folio_carril3_camion7eje = 0
        folio_carril4_camion7eje = 0
        folio_carril5_camion7eje = 0
        folio_carril6_camion7eje = 0
        # RESIDENTE
        folio_carril1_residente = 0
        folio_carril2_residente = 0
        folio_carril3_residente = 0
        folio_carril4_residente = 0
        folio_carril5_residente = 0
        folio_carril6_residente = 0
        # RESIDENTE 1 EJE
        folio_carril1_residente1eje = 0
        folio_carril2_residente1eje = 0
        folio_carril3_residente1eje = 0
        folio_carril4_residente1eje = 0
        folio_carril5_residente1eje = 0
        folio_carril6_residente1eje = 0
        # RESIDENTE 2 EJES
        folio_carril1_residente2eje = 0
        folio_carril2_residente2eje = 0
        folio_carril3_residente2eje = 0
        folio_carril4_residente2eje = 0
        folio_carril5_residente2eje = 0
        folio_carril6_residente2eje = 0

        # TARIFAS
        motocicleta_cuota = 0
        auto_cuota = 0
        auto_1eje_cuota = 0
        auto_2eje_cuota = 0
        autobus_cuota = 0
        camion2eje_cuota = 0
        camion3eje_cuota = 0
        camion4eje_cuota = 0
        camion5eje_cuota = 0
        camion6eje_cuota = 0
        camion7eje_cuota = 0
        residente_cuota = 0
        residente1eje_cuota = 0
        residente2eje_cuota = 0
        motocicleta_tarifa_siva = 0
        motocicleta_tarifa_iva = 0
        auto_tarifa_siva = 0
        auto_tarifa_iva = 0
        auto_1eje_tarifa_siva = 0
        auto_1eje_tarifa_iva = 0
        auto_2eje_tarifa_siva = 0
        auto_2eje_tarifa_iva = 0
        autobus_tarifa_siva = 0
        autobus_tarifa_iva = 0
        camion2eje_tarifa_siva = 0
        camion2eje_tarifa_iva = 0
        camion3eje_tarifa_siva = 0
        camion3eje_tarifa_iva = 0
        camion4eje_tarifa_siva = 0
        camion4eje_tarifa_iva = 0
        camion5eje_tarifa_siva = 0
        camion5eje_tarifa_iva = 0
        camion6eje_tarifa_siva = 0
        camion6eje_tarifa_iva = 0
        camion7eje_tarifa_siva = 0
        camion7eje_tarifa_iva = 0
        residente_tarifa_iva = 0
        residente_tarifa_siva = 0
        residente1eje_tarifa_iva = 0
        residente1eje_tarifa_siva = 0
        residente2eje_tarifa_iva = 0
        residente2eje_tarifa_siva = 0

        for mat in buscar_sesiones_vesp:
            # buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])
            print(mat.name, mat.config_id.name)

            buscar_peajes_motocicleta = self.env["product.template"].search([('name', '=', "MOTOCICLETA")])
            buscar_peajes_auto = self.env["product.template"].search([('name', '=', "AUTO")])
            buscar_peajes_auto1eje = self.env["product.template"].search([('name', '=', "AUTO 1 EJE")])
            buscar_peajes_auto2eje = self.env["product.template"].search([('name', '=', "AUTO 2 EJE")])
            buscar_peajes_autobus = self.env["product.template"].search([('name', '=', "AUTOBUS")])
            buscar_peajes_camion2eje = self.env["product.template"].search([('name', '=', "CAMION 2 EJES")])
            buscar_peajes_camion3eje = self.env["product.template"].search([('name', '=', "CAMION 3 EJES")])
            buscar_peajes_camion4eje = self.env["product.template"].search([('name', '=', "CAMION 4 EJES")])
            buscar_peajes_camion5eje = self.env["product.template"].search([('name', '=', "CAMION 5 EJES")])
            buscar_peajes_camion6eje = self.env["product.template"].search([('name', '=', "CAMION 6 EJES")])
            buscar_peajes_camion7eje = self.env["product.template"].search([('name', '=', "CAMION + 7 EJES")])
            buscar_peajes_residente = self.env["product.template"].search([('name', '=', "RESIDENTE")])
            buscar_peajes_residente1eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 1 EJE")])
            buscar_peajes_residente2eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 2 EJES")])


            buscar_ordenes_folios = self.env["pos.order"].search([('session_id', '=', mat.id)])
            for bof in buscar_ordenes_folios:
                print(bof.name, ' bof ')
                for bp in buscar_peajes_motocicleta:                                                   # MOTOCICLETA

                    motocicleta_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    # TARIFA SIN IVA
                    motocicleta_tarifa_siva = bp.list_price
                    # TARIFA IVA
                    motocicleta_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)


                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto:                                                   # AUTO
                    auto_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_tarifa_siva = float(bp.list_price)
                    auto_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto1eje:                                                   # AUTO 1 EJE
                    auto_1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_1eje_tarifa_siva = float(bp.list_price)
                    auto_1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto2eje:                                                   # AUTO 2 EJES
                    auto_2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_2eje_tarifa_siva = float(bp.list_price)
                    auto_2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_autobus:                                                   # AUTOBBUS
                    autobus_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    autobus_tarifa_siva = float(bp.list_price)
                    autobus_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion2eje:                                                   # CAMION 2 EJE
                    camion2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion2eje_tarifa_siva = float(bp.list_price)
                    camion2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion3eje:                                                   # CAMION 3 EJES
                    camion3eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion3eje_tarifa_siva = float(bp.list_price)
                    camion3eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion4eje:                                                   # CAMION 4 EJES
                    camion4eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion4eje_tarifa_siva = float(bp.list_price)
                    camion4eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion5eje:                                                   # CAMION 5 EJES
                    camion5eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion5eje_tarifa_siva = float(bp.list_price)
                    camion5eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion6eje:                                                   # CAMION 6 EJES
                    camion6eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion6eje_tarifa_siva = float(bp.list_price)
                    camion6eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion7eje:                                                   # CAMION 7 EJES
                    camion7eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion7eje_tarifa_siva = float(bp.list_price)
                    camion7eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente:                                                   # RESIDENTE
                    residente_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    residente_tarifa_siva = float(bp.list_price)
                    residente_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente1eje:                                                   # RESIDENTE 1 EJE
                    residente1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente1eje_tarifa_siva = float(bp.list_price)
                    residente1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente2eje:                                                   # RESIDENTE 2 EJE
                    residente2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente2eje_tarifa_siva = float(bp.list_price)
                    residente2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

            '''for pagos in buscar_pagos:
                cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax'''

        print(buscar_sesiones_vesp, ' Sesiones Vespertino ', folio_carril1_auto)

        data = {'date_start': self.start_date,
                'date_stop': self.end_date,
                'config_ids': self.pos_config_srlc_ids.ids,

                # PEAJES
                'motocicleta_cuota': motocicleta_cuota,
                'auto_cuota': auto_cuota,
                'auto_1eje_cuota': float(auto_1eje_cuota),
                'auto_2eje_cuota': auto_2eje_cuota,
                'autobus_cuota': autobus_cuota,
                'camion2eje_cuota': camion2eje_cuota,
                'camion3eje_cuota': camion3eje_cuota,
                'camion4eje_cuota': camion4eje_cuota,
                'camion5eje_cuota': camion5eje_cuota,
                'camion6eje_cuota': camion6eje_cuota,
                'camion7eje_cuota': camion7eje_cuota,
                'residente_cuota': residente_cuota,
                'residente1eje_cuota': residente1eje_cuota,
                'residente2eje_cuota': residente2eje_cuota,

                # FOLIOS POR CARRIL
                # CARRIL 1
                'folio_carril1_motocicleta': folio_carril1_motocicleta,
                'folio_carril1_auto': folio_carril1_auto,
                'folio_carril1_auto1eje': folio_carril1_auto1eje,
                'folio_carril1_auto2eje': folio_carril1_auto2eje,
                'folio_carril1_autobus': folio_carril1_autobus,
                'folio_carril1_camion2eje': folio_carril1_camion2eje,
                'folio_carril1_camion3eje': folio_carril1_camion3eje,
                'folio_carril1_camion4eje': folio_carril1_camion4eje,
                'folio_carril1_camion5eje': folio_carril1_camion5eje,
                'folio_carril1_camion6eje': folio_carril1_camion6eje,
                'folio_carril1_camion7eje': folio_carril1_camion7eje,
                'folio_carril1_residente': folio_carril1_residente,
                'folio_carril1_residente1eje': folio_carril1_residente1eje,
                'folio_carril1_residente2eje': folio_carril1_residente2eje,
                # CARRIL 2
                'folio_carril2_motocicleta': folio_carril2_motocicleta,
                'folio_carril2_auto': folio_carril2_auto,
                'folio_carril2_auto1eje': folio_carril2_auto1eje,
                'folio_carril2_auto2eje': folio_carril2_auto2eje,
                'folio_carril2_autobus': folio_carril2_autobus,
                'folio_carril2_camion2eje': folio_carril2_camion2eje,
                'folio_carril2_camion3eje': folio_carril2_camion3eje,
                'folio_carril2_camion4eje': folio_carril2_camion4eje,
                'folio_carril2_camion5eje': folio_carril2_camion5eje,
                'folio_carril2_camion6eje': folio_carril2_camion6eje,
                'folio_carril2_camion7eje': folio_carril2_camion7eje,
                'folio_carril2_residente': folio_carril2_residente,
                'folio_carril2_residente1eje': folio_carril2_residente1eje,
                'folio_carril2_residente2eje': folio_carril2_residente2eje,
                # CARRIL 3
                'folio_carril3_motocicleta': folio_carril3_motocicleta,
                'folio_carril3_auto': folio_carril3_auto,
                'folio_carril3_auto1eje': folio_carril3_auto1eje,
                'folio_carril3_auto2eje': folio_carril3_auto2eje,
                'folio_carril3_autobus': folio_carril3_autobus,
                'folio_carril3_camion2eje': folio_carril3_camion2eje,
                'folio_carril3_camion3eje': folio_carril3_camion3eje,
                'folio_carril3_camion4eje': folio_carril3_camion4eje,
                'folio_carril3_camion5eje': folio_carril3_camion5eje,
                'folio_carril3_camion6eje': folio_carril3_camion6eje,
                'folio_carril3_camion7eje': folio_carril3_camion7eje,
                'folio_carril3_residente': folio_carril3_residente,
                'folio_carril3_residente1eje': folio_carril3_residente1eje,
                'folio_carril3_residente2eje': folio_carril3_residente2eje,
                # CARRIL 4
                'folio_carril4_motocicleta': folio_carril4_motocicleta,
                'folio_carril4_auto': folio_carril4_auto,
                'folio_carril4_auto1eje': folio_carril4_auto1eje,
                'folio_carril4_auto2eje': folio_carril4_auto2eje,
                'folio_carril4_autobus': folio_carril4_autobus,
                'folio_carril4_camion2eje': folio_carril4_camion2eje,
                'folio_carril4_camion3eje': folio_carril4_camion3eje,
                'folio_carril4_camion4eje': folio_carril4_camion4eje,
                'folio_carril4_camion5eje': folio_carril4_camion5eje,
                'folio_carril4_camion6eje': folio_carril4_camion6eje,
                'folio_carril4_camion7eje': folio_carril4_camion7eje,
                'folio_carril4_residente': folio_carril4_residente,
                'folio_carril4_residente1eje': folio_carril4_residente1eje,
                'folio_carril4_residente2eje': folio_carril4_residente2eje,
                # CARRIL 5
                'folio_carril5_motocicleta': folio_carril5_motocicleta,
                'folio_carril5_auto': folio_carril5_auto,
                'folio_carril5_auto1eje': folio_carril5_auto1eje,
                'folio_carril5_auto2eje': folio_carril5_auto2eje,
                'folio_carril5_autobus': folio_carril5_autobus,
                'folio_carril5_camion2eje': folio_carril5_camion2eje,
                'folio_carril5_camion3eje': folio_carril5_camion3eje,
                'folio_carril5_camion4eje': folio_carril5_camion4eje,
                'folio_carril5_camion5eje': folio_carril5_camion5eje,
                'folio_carril5_camion6eje': folio_carril5_camion6eje,
                'folio_carril5_camion7eje': folio_carril5_camion7eje,
                'folio_carril5_residente': folio_carril5_residente,
                'folio_carril5_residente1eje': folio_carril5_residente1eje,
                'folio_carril5_residente2eje': folio_carril5_residente2eje,
                # CARRIL 6
                'folio_carril6_motocicleta': folio_carril6_motocicleta,
                'folio_carril6_auto': folio_carril6_auto,
                'folio_carril6_auto1eje': folio_carril6_auto1eje,
                'folio_carril6_auto2eje': folio_carril6_auto2eje,
                'folio_carril6_autobus': folio_carril6_autobus,
                'folio_carril6_camion2eje': folio_carril6_camion2eje,
                'folio_carril6_camion3eje': folio_carril6_camion3eje,
                'folio_carril6_camion4eje': folio_carril6_camion4eje,
                'folio_carril6_camion5eje': folio_carril6_camion5eje,
                'folio_carril6_camion6eje': folio_carril6_camion6eje,
                'folio_carril6_camion7eje': folio_carril6_camion7eje,
                'folio_carril6_residente': folio_carril6_residente,
                'folio_carril6_residente1eje': folio_carril6_residente1eje,
                'folio_carril6_residente2eje': folio_carril6_residente2eje,

                # TARIFAS
                # TARIFAS SIN IVA
                'motocicleta_tarifa_siva': motocicleta_tarifa_siva,
                'auto_tarifa_siva': auto_tarifa_siva,
                'auto_1eje_tarifa_siva': auto_1eje_tarifa_siva,
                'auto_2eje_tarifa_siva': auto_2eje_tarifa_siva,
                'autobus_tarifa_siva': autobus_tarifa_siva,
                'camion2eje_tarifa_siva': camion2eje_tarifa_siva,
                'camion3eje_tarifa_siva': camion3eje_tarifa_siva,
                'camion4eje_tarifa_siva': camion4eje_tarifa_siva,
                'camion5eje_tarifa_siva': camion5eje_tarifa_siva,
                'camion6eje_tarifa_siva': camion6eje_tarifa_siva,
                'camion7eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente_tarifa_siva': camion7eje_tarifa_siva,
                'residente1eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente2eje_tarifa_siva': camion7eje_tarifa_siva,

                # TARIFAS IVA
                'motocicleta_tarifa_iva': motocicleta_tarifa_iva,
                'auto_tarifa_iva': auto_tarifa_iva,
                'auto_1eje_tarifa_iva': auto_1eje_tarifa_iva,
                'auto_2eje_tarifa_iva': auto_2eje_tarifa_iva,
                'autobus_tarifa_iva': autobus_tarifa_iva,
                'camion2eje_tarifa_iva': camion2eje_tarifa_iva,
                'camion3eje_tarifa_iva': camion3eje_tarifa_iva,
                'camion4eje_tarifa_iva': camion4eje_tarifa_iva,
                'camion5eje_tarifa_iva': camion5eje_tarifa_iva,
                'camion6eje_tarifa_iva': camion6eje_tarifa_iva,
                'camion7eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente_tarifa_iva': camion7eje_tarifa_iva,
                'residente1eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente2eje_tarifa_iva': camion7eje_tarifa_iva,

                }
        return self.env.ref('slrc.vespertino_report_button').report_action([], data=data)
    
    
    
    def generate_report_turnonoc(self):
        print(' GENERAR REPORTE DEL TURNO MAT')

        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")

        '''dt = datetime.strptime(str(fecha_dma2), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma2 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma2 = datetime.strftime(fecha_dma2, '%d/%m/%Y')'''

        # FECHA UTC
        fecha_dma2 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        print(fecha_dma2, ' fecha local UTC')
        fecha_dma2 = datetime.strftime(fecha_hoy, '%Y-%m-%d')

        # FECHA MST HERMOSILLO
        fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')
        print(fecha_dma3, ' fecha local MST ')

        fecha_hora = time.strftime(hora, time.localtime())
        dt = datetime.strptime(str(fecha_hora), '%H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_hora = old_tz.localize(dt).astimezone(new_tz)
        hora = datetime.strftime(fecha_hora, '%H:%M:%S')

        buscar_ordenes = []
        turno = ""
        # if hora >= '00:00:00' and hora <= '07:59:59':
        turno = 'Matutino'

        buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                       ('date_order', '<=', str(fecha_dma2) + ' 13:59:59')])

        # BUSCAR LAS SESIONES QUE CORRESPONDAN A ESTE TURNO!

        '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])'''

        buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                              ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')], order='config_id asc')

        '''buscar_sesiones_matx = self.env["pos.session"].search([])
        for ici in buscar_sesiones_matx:
            print(ici.start_at, ' fecha ', fecha_dma2 + ' 07:00:00')'''

        acum_pago_mat = 0
        cum_pagoiva_matutino = 0

        folio_carril1_motocicleta = 0
        folio_carril2_motocicleta = 0
        folio_carril3_motocicleta = 0
        folio_carril4_motocicleta = 0
        folio_carril5_motocicleta = 0
        folio_carril6_motocicleta = 0
        # AUTO
        folio_carril1_auto = 0
        folio_carril2_auto = 0
        folio_carril3_auto = 0
        folio_carril4_auto = 0
        folio_carril5_auto = 0
        folio_carril6_auto = 0
        # AUTO 1 EJE
        folio_carril1_auto1eje = 0
        folio_carril2_auto1eje = 0
        folio_carril3_auto1eje = 0
        folio_carril4_auto1eje = 0
        folio_carril5_auto1eje = 0
        folio_carril6_auto1eje = 0
        # AUTO 2 EJE
        folio_carril1_auto2eje = 0
        folio_carril2_auto2eje = 0
        folio_carril3_auto2eje = 0
        folio_carril4_auto2eje = 0
        folio_carril5_auto2eje = 0
        folio_carril6_auto2eje = 0
        # AUTOBUS
        folio_carril1_autobus = 0
        folio_carril2_autobus = 0
        folio_carril3_autobus = 0
        folio_carril4_autobus = 0
        folio_carril5_autobus = 0
        folio_carril6_autobus = 0
        # CAMION 2 ejes
        folio_carril1_camion2eje = 0
        folio_carril2_camion2eje = 0
        folio_carril3_camion2eje = 0
        folio_carril4_camion2eje = 0
        folio_carril5_camion2eje = 0
        folio_carril6_camion2eje = 0
        # CAMION 3 EJES
        folio_carril1_camion3eje = 0
        folio_carril2_camion3eje = 0
        folio_carril3_camion3eje = 0
        folio_carril4_camion3eje = 0
        folio_carril5_camion3eje = 0
        folio_carril6_camion3eje = 0
        # CAMION 4 EJES
        folio_carril1_camion4eje = 0
        folio_carril2_camion4eje = 0
        folio_carril3_camion4eje = 0
        folio_carril4_camion4eje = 0
        folio_carril5_camion4eje = 0
        folio_carril6_camion4eje = 0
        # CAMION 5 EJES
        folio_carril1_camion5eje = 0
        folio_carril2_camion5eje = 0
        folio_carril3_camion5eje = 0
        folio_carril4_camion5eje = 0
        folio_carril5_camion5eje = 0
        folio_carril6_camion5eje = 0
        # CAMION 6 EJES
        folio_carril1_camion6eje = 0
        folio_carril2_camion6eje = 0
        folio_carril3_camion6eje = 0
        folio_carril4_camion6eje = 0
        folio_carril5_camion6eje = 0
        folio_carril6_camion6eje = 0
        # CAMION 7 EJES
        folio_carril1_camion7eje = 0
        folio_carril2_camion7eje = 0
        folio_carril3_camion7eje = 0
        folio_carril4_camion7eje = 0
        folio_carril5_camion7eje = 0
        folio_carril6_camion7eje = 0
        # RESIDENTE
        folio_carril1_residente = 0
        folio_carril2_residente = 0
        folio_carril3_residente = 0
        folio_carril4_residente = 0
        folio_carril5_residente = 0
        folio_carril6_residente = 0
        # RESIDENTE 1 EJE
        folio_carril1_residente1eje = 0
        folio_carril2_residente1eje = 0
        folio_carril3_residente1eje = 0
        folio_carril4_residente1eje = 0
        folio_carril5_residente1eje = 0
        folio_carril6_residente1eje = 0
        # RESIDENTE 2 EJES
        folio_carril1_residente2eje = 0
        folio_carril2_residente2eje = 0
        folio_carril3_residente2eje = 0
        folio_carril4_residente2eje = 0
        folio_carril5_residente2eje = 0
        folio_carril6_residente2eje = 0

        # TARIFAS
        motocicleta_cuota = 0
        auto_cuota = 0
        auto_1eje_cuota = 0
        auto_2eje_cuota = 0
        autobus_cuota = 0
        camion2eje_cuota = 0
        camion3eje_cuota = 0
        camion4eje_cuota = 0
        camion5eje_cuota = 0
        camion6eje_cuota = 0
        camion7eje_cuota = 0
        residente_cuota = 0
        residente1eje_cuota = 0
        residente2eje_cuota = 0
        motocicleta_tarifa_siva = 0
        motocicleta_tarifa_iva = 0
        auto_tarifa_siva = 0
        auto_tarifa_iva = 0
        auto_1eje_tarifa_siva = 0
        auto_1eje_tarifa_iva = 0
        auto_2eje_tarifa_siva = 0
        auto_2eje_tarifa_iva = 0
        autobus_tarifa_siva = 0
        autobus_tarifa_iva = 0
        camion2eje_tarifa_siva = 0
        camion2eje_tarifa_iva = 0
        camion3eje_tarifa_siva = 0
        camion3eje_tarifa_iva = 0
        camion4eje_tarifa_siva = 0
        camion4eje_tarifa_iva = 0
        camion5eje_tarifa_siva = 0
        camion5eje_tarifa_iva = 0
        camion6eje_tarifa_siva = 0
        camion6eje_tarifa_iva = 0
        camion7eje_tarifa_siva = 0
        camion7eje_tarifa_iva = 0
        residente_tarifa_iva = 0
        residente_tarifa_siva = 0
        residente1eje_tarifa_iva = 0
        residente1eje_tarifa_siva = 0
        residente2eje_tarifa_iva = 0
        residente2eje_tarifa_siva = 0


        for mat in buscar_sesiones_mat:
            # buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])
            # print(mat.name, mat.config_id.name)

            buscar_peajes_motocicleta = self.env["product.template"].search([('name', '=', "MOTOCICLETA")])
            buscar_peajes_auto = self.env["product.template"].search([('name', '=', "AUTO")])
            buscar_peajes_auto1eje = self.env["product.template"].search([('name', '=', "AUTO 1 EJE")])
            buscar_peajes_auto2eje = self.env["product.template"].search([('name', '=', "AUTO 2 EJE")])
            buscar_peajes_autobus = self.env["product.template"].search([('name', '=', "AUTOBUS")])
            buscar_peajes_camion2eje = self.env["product.template"].search([('name', '=', "CAMION 2 EJES")])
            buscar_peajes_camion3eje = self.env["product.template"].search([('name', '=', "CAMION 3 EJES")])
            buscar_peajes_camion4eje = self.env["product.template"].search([('name', '=', "CAMION 4 EJES")])
            buscar_peajes_camion5eje = self.env["product.template"].search([('name', '=', "CAMION 5 EJES")])
            buscar_peajes_camion6eje = self.env["product.template"].search([('name', '=', "CAMION 6 EJES")])
            buscar_peajes_camion7eje = self.env["product.template"].search([('name', '=', "CAMION + 7 EJES")])
            buscar_peajes_residente = self.env["product.template"].search([('name', '=', "RESIDENTE")])
            buscar_peajes_residente1eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 1 EJE")])
            buscar_peajes_residente2eje = self.env["product.template"].search([('name', '=', "RESIDENTE + 2 EJES")])


            buscar_ordenes_folios = self.env["pos.order"].search([('session_id', '=', mat.id)])
            for bof in buscar_ordenes_folios:
                # print(bof.name, ' bof ')
                for bp in buscar_peajes_motocicleta:                                                   # MOTOCICLETA

                    motocicleta_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    # TARIFA SIN IVA
                    motocicleta_tarifa_siva = bp.list_price
                    # TARIFA IVA
                    motocicleta_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)


                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_motocicleta = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto:                                                   # AUTO
                    auto_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_tarifa_siva = float(bp.list_price)
                    auto_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto = self.env["pos.order.line"].search_count([('order_id.id', '=', bof.id),('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto1eje:                                                   # AUTO 1 EJE
                    auto_1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_1eje_tarifa_siva = float(bp.list_price)
                    auto_1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_auto2eje:                                                   # AUTO 2 EJES
                    auto_2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    auto_2eje_tarifa_siva = float(bp.list_price)
                    auto_2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_auto2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_autobus:                                                   # AUTOBBUS
                    autobus_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    autobus_tarifa_siva = float(bp.list_price)
                    autobus_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_autobus = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion2eje:                                                   # CAMION 2 EJE
                    camion2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion2eje_tarifa_siva = float(bp.list_price)
                    camion2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion3eje:                                                   # CAMION 3 EJES
                    camion3eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion3eje_tarifa_siva = float(bp.list_price)
                    camion3eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion3eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion4eje:                                                   # CAMION 4 EJES
                    camion4eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion4eje_tarifa_siva = float(bp.list_price)
                    camion4eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion4eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion5eje:                                                   # CAMION 5 EJES
                    camion5eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion5eje_tarifa_siva = float(bp.list_price)
                    camion5eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion5eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion6eje:                                                   # CAMION 6 EJES
                    camion6eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion6eje_tarifa_siva = float(bp.list_price)
                    camion6eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion6eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_camion7eje:                                                   # CAMION 7 EJES
                    camion7eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    camion7eje_tarifa_siva = float(bp.list_price)
                    camion7eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_camion7eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente:                                                   # RESIDENTE
                    residente_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                    residente_tarifa_siva = float(bp.list_price)
                    residente_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente1eje:                                                   # RESIDENTE 1 EJE
                    residente1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente1eje_tarifa_siva = float(bp.list_price)
                    residente1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente1eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])

                for bp in buscar_peajes_residente2eje:                                                   # RESIDENTE 2 EJE
                    residente2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(
                        bp.list_price)
                    residente2eje_tarifa_siva = float(bp.list_price)
                    residente2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)
                    # BUSCAR CANTIDAD DE FOLIOS VENDIDOS POR PRODUCTO Y CARRIL
                    if mat.config_id.name == 1:
                        folio_carril1_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 2:
                        folio_carril2_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 3:
                        folio_carril3_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 4:
                        folio_carril4_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 5:
                        folio_carril5_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])
                    if mat.config_id.name == 6:
                        folio_carril6_residente2eje = self.env["pos.order.line"].search_count(
                            [('order_id.id', '=', bof.id), ('product_id.id', '=', bp.id)])


            '''for pagos in buscar_pagos:
                cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax'''

        print(buscar_sesiones_mat, ' si entro matutino ')


        data = {'date_start': self.start_date,
                'date_stop': self.end_date,
                'config_ids': self.pos_config_srlc_ids.ids,

                # PEAJES
                'motocicleta_cuota': motocicleta_cuota,
                'auto_cuota': auto_cuota,
                'auto_1eje_cuota': float(auto_1eje_cuota),
                'auto_2eje_cuota': auto_2eje_cuota,
                'autobus_cuota': autobus_cuota,
                'camion2eje_cuota': camion2eje_cuota,
                'camion3eje_cuota': camion3eje_cuota,
                'camion4eje_cuota': camion4eje_cuota,
                'camion5eje_cuota': camion5eje_cuota,
                'camion6eje_cuota': camion6eje_cuota,
                'camion7eje_cuota': camion7eje_cuota,
                'residente_cuota': residente_cuota,
                'residente1eje_cuota': residente1eje_cuota,
                'residente2eje_cuota': residente2eje_cuota,

                # FOLIOS POR CARRIL
                # CARRIL 1
                'folio_carril1_motocicleta': folio_carril1_motocicleta,
                'folio_carril1_auto': folio_carril1_auto,
                'folio_carril1_auto1eje': folio_carril1_auto1eje,
                'folio_carril1_auto2eje': folio_carril1_auto2eje,
                'folio_carril1_autobus': folio_carril1_autobus,
                'folio_carril1_camion2eje': folio_carril1_camion2eje,
                'folio_carril1_camion3eje': folio_carril1_camion3eje,
                'folio_carril1_camion4eje': folio_carril1_camion4eje,
                'folio_carril1_camion5eje': folio_carril1_camion5eje,
                'folio_carril1_camion6eje': folio_carril1_camion6eje,
                'folio_carril1_camion7eje': folio_carril1_camion7eje,
                'folio_carril1_residente': folio_carril1_residente,
                'folio_carril1_residente1eje': folio_carril1_residente1eje,
                'folio_carril1_residente2eje': folio_carril1_residente2eje,
                # CARRIL 2
                'folio_carril2_motocicleta': folio_carril2_motocicleta,
                'folio_carril2_auto': folio_carril2_auto,
                'folio_carril2_auto1eje': folio_carril2_auto1eje,
                'folio_carril2_auto2eje': folio_carril2_auto2eje,
                'folio_carril2_autobus': folio_carril2_autobus,
                'folio_carril2_camion2eje': folio_carril2_camion2eje,
                'folio_carril2_camion3eje': folio_carril2_camion3eje,
                'folio_carril2_camion4eje': folio_carril2_camion4eje,
                'folio_carril2_camion5eje': folio_carril2_camion5eje,
                'folio_carril2_camion6eje': folio_carril2_camion6eje,
                'folio_carril2_camion7eje': folio_carril2_camion7eje,
                'folio_carril2_residente': folio_carril2_residente,
                'folio_carril2_residente1eje': folio_carril2_residente1eje,
                'folio_carril2_residente2eje': folio_carril2_residente2eje,
                # CARRIL 3
                'folio_carril3_motocicleta': folio_carril3_motocicleta,
                'folio_carril3_auto': folio_carril3_auto,
                'folio_carril3_auto1eje': folio_carril3_auto1eje,
                'folio_carril3_auto2eje': folio_carril3_auto2eje,
                'folio_carril3_autobus': folio_carril3_autobus,
                'folio_carril3_camion2eje': folio_carril3_camion2eje,
                'folio_carril3_camion3eje': folio_carril3_camion3eje,
                'folio_carril3_camion4eje': folio_carril3_camion4eje,
                'folio_carril3_camion5eje': folio_carril3_camion5eje,
                'folio_carril3_camion6eje': folio_carril3_camion6eje,
                'folio_carril3_camion7eje': folio_carril3_camion7eje,
                'folio_carril3_residente': folio_carril3_residente,
                'folio_carril3_residente1eje': folio_carril3_residente1eje,
                'folio_carril3_residente2eje': folio_carril3_residente2eje,
                # CARRIL 4
                'folio_carril4_motocicleta': folio_carril4_motocicleta,
                'folio_carril4_auto': folio_carril4_auto,
                'folio_carril4_auto1eje': folio_carril4_auto1eje,
                'folio_carril4_auto2eje': folio_carril4_auto2eje,
                'folio_carril4_autobus': folio_carril4_autobus,
                'folio_carril4_camion2eje': folio_carril4_camion2eje,
                'folio_carril4_camion3eje': folio_carril4_camion3eje,
                'folio_carril4_camion4eje': folio_carril4_camion4eje,
                'folio_carril4_camion5eje': folio_carril4_camion5eje,
                'folio_carril4_camion6eje': folio_carril4_camion6eje,
                'folio_carril4_camion7eje': folio_carril4_camion7eje,
                'folio_carril4_residente': folio_carril4_residente,
                'folio_carril4_residente1eje': folio_carril4_residente1eje,
                'folio_carril4_residente2eje': folio_carril4_residente2eje,
                # CARRIL 5
                'folio_carril5_motocicleta': folio_carril5_motocicleta,
                'folio_carril5_auto': folio_carril5_auto,
                'folio_carril5_auto1eje': folio_carril5_auto1eje,
                'folio_carril5_auto2eje': folio_carril5_auto2eje,
                'folio_carril5_autobus': folio_carril5_autobus,
                'folio_carril5_camion2eje': folio_carril5_camion2eje,
                'folio_carril5_camion3eje': folio_carril5_camion3eje,
                'folio_carril5_camion4eje': folio_carril5_camion4eje,
                'folio_carril5_camion5eje': folio_carril5_camion5eje,
                'folio_carril5_camion6eje': folio_carril5_camion6eje,
                'folio_carril5_camion7eje': folio_carril5_camion7eje,
                'folio_carril5_residente': folio_carril5_residente,
                'folio_carril5_residente1eje': folio_carril5_residente1eje,
                'folio_carril5_residente2eje': folio_carril5_residente2eje,
                # CARRIL 6
                'folio_carril6_motocicleta': folio_carril6_motocicleta,
                'folio_carril6_auto': folio_carril6_auto,
                'folio_carril6_auto1eje': folio_carril6_auto1eje,
                'folio_carril6_auto2eje': folio_carril6_auto2eje,
                'folio_carril6_autobus': folio_carril6_autobus,
                'folio_carril6_camion2eje': folio_carril6_camion2eje,
                'folio_carril6_camion3eje': folio_carril6_camion3eje,
                'folio_carril6_camion4eje': folio_carril6_camion4eje,
                'folio_carril6_camion5eje': folio_carril6_camion5eje,
                'folio_carril6_camion6eje': folio_carril6_camion6eje,
                'folio_carril6_camion7eje': folio_carril6_camion7eje,
                'folio_carril6_residente': folio_carril6_residente,
                'folio_carril6_residente1eje': folio_carril6_residente1eje,
                'folio_carril6_residente2eje': folio_carril6_residente2eje,

                # TARIFAS
                # TARIFAS SIN IVA
                'motocicleta_tarifa_siva': motocicleta_tarifa_siva,
                'auto_tarifa_siva': auto_tarifa_siva,
                'auto_1eje_tarifa_siva': auto_1eje_tarifa_siva,
                'auto_2eje_tarifa_siva': auto_2eje_tarifa_siva,
                'autobus_tarifa_siva': autobus_tarifa_siva,
                'camion2eje_tarifa_siva': camion2eje_tarifa_siva,
                'camion3eje_tarifa_siva': camion3eje_tarifa_siva,
                'camion4eje_tarifa_siva': camion4eje_tarifa_siva,
                'camion5eje_tarifa_siva': camion5eje_tarifa_siva,
                'camion6eje_tarifa_siva': camion6eje_tarifa_siva,
                'camion7eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente_tarifa_siva': camion7eje_tarifa_siva,
                'residente1eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente2eje_tarifa_siva': camion7eje_tarifa_siva,

                # TARIFAS IVA
                'motocicleta_tarifa_iva': motocicleta_tarifa_iva,
                'auto_tarifa_iva': auto_tarifa_iva,
                'auto_1eje_tarifa_iva': auto_1eje_tarifa_iva,
                'auto_2eje_tarifa_iva': auto_2eje_tarifa_iva,
                'autobus_tarifa_iva': autobus_tarifa_iva,
                'camion2eje_tarifa_iva': camion2eje_tarifa_iva,
                'camion3eje_tarifa_iva': camion3eje_tarifa_iva,
                'camion4eje_tarifa_iva': camion4eje_tarifa_iva,
                'camion5eje_tarifa_iva': camion5eje_tarifa_iva,
                'camion6eje_tarifa_iva': camion6eje_tarifa_iva,
                'camion7eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente_tarifa_iva': camion7eje_tarifa_iva,
                'residente1eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente2eje_tarifa_iva': camion7eje_tarifa_iva,

                }
        return self.env.ref('slrc.nocturno_report_button').report_action([], data=data)


    def generate_report(self):

        '''sesion = self.env["pos.config"].search([])
        print(sesion, ' SESION ')'''

        fecha_hoy = fields.Datetime.now()
        hora = fecha_hoy.strftime("%H:%M:%S")


        '''dt = datetime.strptime(str(fecha_dma2), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma2 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma2 = datetime.strftime(fecha_dma2, '%d/%m/%Y')'''

        # FECHA UTC
        fecha_dma2 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        print(fecha_dma2, ' fecha local UTC')
        fecha_dma2 = datetime.strftime(fecha_hoy, '%d/%m/%Y')

        # FECHA MST HERMOSILLO
        fecha_dma3 = time.strftime("%d-%m-%Y %H:%M:%S", time.localtime())
        dt = datetime.strptime(str(fecha_dma3), '%d-%m-%Y %H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_dma3 = old_tz.localize(dt).astimezone(new_tz)
        fecha_dma3 = datetime.strftime(fecha_dma3, '%d/%m/%Y')
        print(fecha_dma3, ' fecha local MST ')

        fecha_hora = time.strftime(hora, time.localtime())
        dt = datetime.strptime(str(fecha_hora), '%H:%M:%S')
        old_tz = pytz.timezone('UTC')
        new_tz = pytz.timezone('MST')
        fecha_hora = old_tz.localize(dt).astimezone(new_tz)
        hora = datetime.strftime(fecha_hora, '%H:%M:%S')

        # fecha_dma3 = time.strftime("%H:%M:%S", time.localtime())

        print(fecha_dma2, hora, ' hora  ---------- ')
        buscar_ordenes = []
        turno = ""
        cum_pagoiva_matutino = 0
        cum_pagoiva_vespertino = 0
        acum_pagoiva_nocturno = 0
        acum_pago_nocturno = 0
        acum_pago_mat = 0
        if hora >= '00:00:00' and hora <= '07:59:59':
            turno = 'Matutino'

            buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                           ('date_order', '<=', str(fecha_dma2) + ' 13:59:59')])

            # BUSCAR LAS SESIONES QUE CORRESPONDAN A ESTE TURNO!

            '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])'''

            buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 13:59:59')])

            acum_pago_mat = 0
            cum_pagoiva_matutino = 0
            for mat in buscar_sesiones_mat:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])

                for pagos in buscar_pagos:
                    cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                    print(cum_pagoiva_matutino, pagos.pos_order_id.amount_tax, ' revisar aqui ')
                    acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax

            print(buscar_sesiones_mat, ' si entro matutino ')

        if hora >= '08:00:00' and hora <= '16:59:59':
            turno = 'Vespertino'

            '''buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                           ('date_order', '<=', str(fecha_dma2) + ' 16:59:59')])'''

            buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                           ('date_order', '<=', str(fecha_dma2) + ' 20:59:59')])

            # BUSCAR LAS SESIONES QUE CORRESPONDAN A ESTE TURNO!
            '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])

            buscar_sesiones_vesp = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 08:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 16:59:59')])'''

            buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 07:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 14:59:59')])

            buscar_sesiones_vesp = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 15:00:00'),
                                                                   ('stop_at', '<=', str(fecha_dma2) + ' 22:59:59')])

            print(buscar_sesiones_vesp, ' sesiones vesp ', fecha_dma2)
            '''buscar_sesiones_vespxx1 = self.env["pos.order"].search([])
            for svp1 in buscar_sesiones_vespxx1:
                print(svp1.date_order,  ' sssssssssssxxxxxxxx')

            buscar_sesiones_vespxx = self.env["pos.session"].search([])
            for svp in buscar_sesiones_vespxx:
                print(svp.start_at, svp.stop_at, ' sssssssssss')'''

            acum_pago_mat = 0
            cum_pagoiva_matutino = 0
            for mat in buscar_sesiones_mat:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])

                for pagos in buscar_pagos:
                    cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                    acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax

            cum_pagoiva_vespertino = 0
            acum_pago_vesp = 0
            for vesp in buscar_sesiones_vesp:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', vesp.id)])

                for pagos in buscar_pagos:
                    cum_pagoiva_vespertino += pagos.pos_order_id.amount_tax
                    acum_pago_vesp += pagos.amount - pagos.pos_order_id.amount_tax

            acum_pago_nocturno = 0
            acum_pagoiva_nocturno = 0

        if hora >= '23:00:00' and hora <= '23:59:59' or hora >= '00:00:00' and hora <= '06:59:59':
            turno = 'Nocturno'

            

            buscar_ordenes = self.env["pos.order"].search([('date_order', '>=', str(fecha_dma3) + ' 07:00:00'),
                                                           ('date_order', '<=', str(fecha_dma2) + ' 23:59:59')])
            print(buscar_ordenes)

            # BUSCAR TODAS LAS SESIONES POR SER EL ULTIMO TURNO
            '''buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 00:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 07:59:59')])'''
            buscar_sesiones_mat = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma3) + ' 07:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma3) + ' 14:59:59')])

            '''buscar_sesiones_vesp = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 08:00:00'),
                                                                   ('stop_at', '<=', str(fecha_dma2) + ' 16:59:59')])'''

            buscar_sesiones_vesp = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma3) + ' 15:00:00'),
                                                                   ('stop_at', '<=', str(fecha_dma3) + ' 22:59:59')])



            '''buscar_sesiones_noc = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 16:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 23:59:59')])'''

            print(fecha_dma2, ' fffffffffffff NOCTURNO')
            buscar_sesiones_noc = self.env["pos.session"].search([('start_at', '>=', str(fecha_dma2) + ' 23:00:00'),
                                                                  ('stop_at', '<=', str(fecha_dma2) + ' 06:59:59')])

            '''buscar_sesiones_vespxx = self.env["pos.session"].search([])
            for svp in buscar_sesiones_vespxx:
                print(svp.start_at, svp.stop_at, ' sssssssssss')'''

            print('Matutino ' , buscar_sesiones_mat, '--- Vespertino ' , buscar_sesiones_vesp, '-- Nocturno: ', buscar_sesiones_noc)

            acum_pago_mat = 0
            cum_pagoiva_matutino = 0
            for mat in buscar_sesiones_mat:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', mat.id)])

                for pagos in buscar_pagos:
                    cum_pagoiva_matutino += pagos.pos_order_id.amount_tax
                    acum_pago_mat += pagos.amount - pagos.pos_order_id.amount_tax

            cum_pagoiva_vespertino = 0
            acum_pago_vesp = 0
            for vesp in buscar_sesiones_vesp:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', vesp.id)])

                for pagos in buscar_pagos:
                    cum_pagoiva_vespertino += pagos.pos_order_id.amount_tax
                    acum_pago_vesp += pagos.amount - pagos.pos_order_id.amount_tax

            acum_pago_nocturno = 0
            acum_pagoiva_nocturno = 0
            for noc in buscar_sesiones_noc:
                buscar_pagos = self.env["pos.payment"].search([('session_id', '=', noc.id)])

                for pagos in buscar_pagos:
                    acum_pagoiva_nocturno += pagos.pos_order_id.amount_tax
                    acum_pago_nocturno += pagos.amount - pagos.pos_order_id.amount_tax


        print(turno, ' ESTE ES EL TURNO ACTUAL ')

        # BUSCAR COSTOS DE PEAJES
        motocicleta_cuota = 0
        auto_cuota = 0
        auto_1eje_cuota = 0
        auto_2eje_cuota = 0
        autobus_cuota = 0
        camion2eje_cuota = 0
        camion3eje_cuota = 0
        camion4eje_cuota = 0
        camion5eje_cuota = 0
        camion6eje_cuota = 0
        camion7eje_cuota = 0
        residente_cuota = 0
        residente1eje_cuota = 0
        residente2eje_cuota = 0
        motocicleta_folios_vendidos = 0
        auto_folios_vendidos = 0
        auto1eje_folios_vendidos = 0
        auto2eje_folios_vendidos = 0
        autobus_folios_vendidos = 0
        camion2eje_folios_vendidos = 0
        camion3eje_folios_vendidos = 0
        camion4eje_folios_vendidos = 0
        camion5eje_folios_vendidos = 0
        camion6eje_folios_vendidos = 0
        camion7eje_folios_vendidos = 0
        residente_folios_vendidos = 0
        residente1eje_folios_vendidos = 0
        residente2eje_folios_vendidos = 0
        motocicleta_tarifa_siva = 0
        motocicleta_tarifa_iva = 0
        auto_tarifa_siva = 0
        auto_tarifa_iva = 0
        auto_1eje_tarifa_siva = 0
        auto_1eje_tarifa_iva = 0
        auto_2eje_tarifa_siva = 0
        auto_2eje_tarifa_iva = 0
        autobus_tarifa_siva = 0
        autobus_tarifa_iva = 0
        camion2eje_tarifa_siva = 0
        camion2eje_tarifa_iva = 0
        camion3eje_tarifa_siva = 0
        camion3eje_tarifa_iva = 0
        camion4eje_tarifa_siva = 0
        camion4eje_tarifa_iva = 0
        camion5eje_tarifa_siva = 0
        camion5eje_tarifa_iva = 0
        camion6eje_tarifa_siva = 0
        camion6eje_tarifa_iva = 0
        camion7eje_tarifa_siva = 0
        camion7eje_tarifa_iva = 0
        residente_tarifa_iva = 0
        residente_tarifa_siva = 0
        residente1eje_tarifa_iva = 0
        residente1eje_tarifa_siva = 0
        residente2eje_tarifa_iva = 0
        residente2eje_tarifa_siva = 0
        buscar_peajes = self.env["product.template"].search([])
        for bp in buscar_peajes:

            buscar_folios = 0

            # BUSCAR LAS CUOTAS DE CADA PRODUCTO PARA EL REPORTE DE FIN DE TURNO
            if bp.name == 'MOTOCICLETA':
                # CUOTA
                motocicleta_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                # TARIFA SIN IVA
                motocicleta_tarifa_siva = bp.list_price
                #TARIFA IVA
                motocicleta_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)


                # ////////// BUSCAMOS EL NUMERO DE FOLIOS VENDIDOS DE MOTOCICLETA
                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                         ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                motocicleta_folios_vendidos = acum_folios
                # ////////////////////////////////////////////////////////


            elif bp.name == 'AUTO':
                auto_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                auto_tarifa_siva = float(bp.list_price)
                auto_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                auto_folios_vendidos = acum_folios

            elif bp.name == 'AUTO + 1 EJE':
                auto_1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                auto_1eje_tarifa_siva = float(bp.list_price)
                auto_1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                auto1eje_folios_vendidos = acum_folios

            elif bp.name == 'AUTO + 2 EJE':
                auto_2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                auto_2eje_tarifa_siva = float(bp.list_price)
                auto_2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                auto2eje_folios_vendidos = acum_folios

            elif bp.name == 'AUTOBUS':
                autobus_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                autobus_tarifa_siva = float(bp.list_price)
                autobus_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                autobus_folios_vendidos = acum_folios

            elif bp.name == 'CAMION 2 EJES':
                camion2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion2eje_tarifa_siva = float(bp.list_price)
                camion2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion2eje_folios_vendidos = acum_folios

            elif bp.name == 'CAMION 3 EJES':
                camion3eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion3eje_tarifa_siva = float(bp.list_price)
                camion3eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion3eje_folios_vendidos = acum_folios


            elif bp.name == 'CAMION 4 EJES':
                camion4eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion4eje_tarifa_siva = float(bp.list_price)
                camion4eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion4eje_folios_vendidos = acum_folios

            elif bp.name == 'CAMION 5 EJES':
                camion5eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion5eje_tarifa_siva = float(bp.list_price)
                camion5eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion5eje_folios_vendidos = acum_folios

            elif bp.name == 'CAMION 6 EJES':
                camion6eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion6eje_tarifa_siva = float(bp.list_price)
                camion6eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion6eje_folios_vendidos = acum_folios

            elif bp.name == 'CAMION + 7 EJES':
                camion7eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                camion7eje_tarifa_siva = float(bp.list_price)
                camion7eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                camion7eje_folios_vendidos = acum_folios

            elif bp.name == 'RESIDENTE':
                residente_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                residente_tarifa_siva = float(bp.list_price)
                residente_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                print('RESIDENTE, ', bp.name, residente_cuota)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                          ('product_id.id', '=', bp.id)])
                    # print('buscar_folios', buscar_folios)
                    acum_folios += buscar_folios
                print(acum_folios, ' folios')
                residente_folios_vendidos = acum_folios

            elif bp.name == 'RESIDENTE + 1 EJE':
                residente1eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                residente1eje_tarifa_siva = float(bp.list_price)
                residente1eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                residente1eje_folios_vendidos = acum_folios

            elif bp.name == 'RESIDENTE + 2 EJES':
                residente2eje_cuota = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100) + float(bp.list_price)
                residente2eje_tarifa_siva = float(bp.list_price)
                residente2eje_tarifa_iva = (float(bp.list_price) * (float(bp.taxes_id.amount)) / 100)

                acum_folios = 0
                for ordenes in buscar_ordenes:
                    buscar_folios = self.env["pos.order.line"].search_count([('order_id.id', '=', ordenes.id),
                                                                             ('product_id.id', '=', bp.id)])
                    acum_folios += buscar_folios
                residente2eje_folios_vendidos = acum_folios

        print(turno, ' TURNO!', acum_pago_vesp)

        # FECHA DE RECAUDACION DE INICIO DEL MES ACTUAL AL DIA ACTUAL
        fecha_recaudacion_convert = datetime.strptime(fecha_dma3, '%d/%m/%Y')
        fecha_recaudacion_iniciomes = datetime.strptime(str(fecha_recaudacion_convert.replace(day=1)), "%Y-%m-%d %H:%M:%S")
        self.env.cr.execute(
            "SELECT COALESCE(SUM(amount),0) FROM pos_payment WHERE payment_date >= '" +
            str(fecha_recaudacion_iniciomes) + "' AND payment_date <= '" +
            str(fecha_dma2) + "00:00:00" + "'")

        '''fecha_recaudacion_iniciomes = datetime.strptime(str(fecha_recaudacion_iniciomes), '%Y-%m-%d %H:%M:%S')
        print(fecha_recaudacion_iniciomes, ' fecha_recaudacion_iniciomes')'''
        recaudado_acum_mes = 0
        res_total = self.env.cr.fetchall()
        for tt in res_total:
            recaudado_acum_mes = tt[0]

        # FECHA DE RECAUDACION DEL ANIO
        epoch_year = datetime.today().year
        year_start = datetime(epoch_year, 1, 1)
        # year_end = datetime(epoch_year, 12, 31)
        fecha_inicioyear_convert = datetime.strptime(str(year_start), '%Y-%m-%d %H:%M:%S')
        self.env.cr.execute(
            "SELECT COALESCE(SUM(amount),0) FROM pos_payment WHERE payment_date >= '" +
            str(fecha_inicioyear_convert) + "' AND payment_date <= '" +
            str(fecha_dma2) + "00:00:00" + "'")
        print(fecha_dma2, ' fecha_dma2')
        recaudado_acum_year = 0
        res_total = self.env.cr.fetchall()
        for tt in res_total:
            recaudado_acum_year = tt[0]

        # FECHA DE RECAUDACION DE TODOS LOS TIEMPOS
        self.env.cr.execute(
             "SELECT COALESCE(SUM(amount),0) FROM pos_payment WHERE payment_date >= '" +
            "01/01/1990 00:00:00" + "' AND payment_date <= '" +
            str(fecha_dma2) + "'")
        recaudado_todos_tiempos = 0
        res_total = self.env.cr.fetchall()
        for tt in res_total:
            recaudado_todos_tiempos = tt[0]

        jefe_operaciones = self.env.user.name
        administrador = ""
        b_administrador = self.env["res.users"].search([('partner_id.function', '=', 'ADMINISTRADOR')])
        for i in b_administrador:
            administrador = i.name

        dolar_tipo_cambio = self.env['ir.config_parameter'].sudo().get_param('pos_parametro.dolar')
        iva = self.env['ir.config_parameter'].sudo().get_param('pos_parametro.iva')

        data = {'date_start': self.start_date,
                'date_stop': self.end_date,
                'fecha_hoy_letra': datetime.now().strftime('%d %B %Y'),
                'config_ids': self.pos_config_srlc_ids.ids,
                'jefe_operaciones': jefe_operaciones,
                'administrador': administrador,
                # ACUMULADO DE CUOTAS
                'cuota_mn_mat': acum_pago_mat,
                'cuota_mn_vesp': acum_pago_vesp,
                'cuota_mn_nocturno': acum_pago_nocturno,
                'cuotaiva_mn_nocturno': acum_pagoiva_nocturno,
                'cuotaiva_mn_vespertino': cum_pagoiva_vespertino,
                'cuotaiva_mn_matutino': cum_pagoiva_matutino,

                # PEAJES
                'motocicleta_cuota': motocicleta_cuota,
                'auto_cuota': auto_cuota,
                'auto_1eje_cuota': auto_1eje_cuota,
                'auto_2eje_cuota': auto_2eje_cuota,
                'autobus_cuota': autobus_cuota,
                'camion2eje_cuota': camion2eje_cuota,
                'camion3eje_cuota': camion3eje_cuota,
                'camion4eje_cuota': camion4eje_cuota,
                'camion5eje_cuota': camion5eje_cuota,
                'camion6eje_cuota': camion6eje_cuota,
                'camion7eje_cuota': camion7eje_cuota,
                'residente_cuota': residente_cuota,
                'residente1eje_cuota': residente1eje_cuota,
                'residente2eje_cuota': residente2eje_cuota,
                # TARIFAS SIN IVA
                'motocicleta_tarifa_siva': motocicleta_tarifa_siva,
                'auto_tarifa_siva': auto_tarifa_siva,
                'auto_1eje_tarifa_siva': auto_1eje_tarifa_siva,
                'auto_2eje_tarifa_siva': auto_2eje_tarifa_siva,
                'autobus_tarifa_siva': autobus_tarifa_siva,
                'camion2eje_tarifa_siva': camion2eje_tarifa_siva,
                'camion3eje_tarifa_siva': camion3eje_tarifa_siva,
                'camion4eje_tarifa_siva': camion4eje_tarifa_siva,
                'camion5eje_tarifa_siva': camion5eje_tarifa_siva,
                'camion6eje_tarifa_siva': camion6eje_tarifa_siva,
                'camion7eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente_tarifa_siva': camion7eje_tarifa_siva,
                'residente1eje_tarifa_siva': camion7eje_tarifa_siva,
                'residente2eje_tarifa_siva': camion7eje_tarifa_siva,

                # TARIFAS IVA
                'motocicleta_tarifa_iva': motocicleta_tarifa_iva,
                'auto_tarifa_iva': auto_tarifa_iva,
                'auto_1eje_tarifa_iva': auto_1eje_tarifa_iva,
                'auto_2eje_tarifa_iva': auto_2eje_tarifa_iva,
                'autobus_tarifa_iva': autobus_tarifa_iva,
                'camion2eje_tarifa_iva': camion2eje_tarifa_iva,
                'camion3eje_tarifa_iva': camion3eje_tarifa_iva,
                'camion4eje_tarifa_iva': camion4eje_tarifa_iva,
                'camion5eje_tarifa_iva': camion5eje_tarifa_iva,
                'camion6eje_tarifa_iva': camion6eje_tarifa_iva,
                'camion7eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente_tarifa_iva': camion7eje_tarifa_iva,
                'residente1eje_tarifa_iva': camion7eje_tarifa_iva,
                'residente2eje_tarifa_iva': camion7eje_tarifa_iva,

                # FOLIOS VENDIDOS
                'motocicleta_folios_vendidos': motocicleta_folios_vendidos,
                'auto_folios_vendidos': auto_folios_vendidos,
                'auto1eje_folios_vendidos': auto1eje_folios_vendidos,
                'auto2eje_folios_vendidos': auto2eje_folios_vendidos,
                'autobus_folios_vendidos': autobus_folios_vendidos,
                'camion2eje_folios_vendidos': camion2eje_folios_vendidos,
                'camion3eje_folios_vendidos': camion3eje_folios_vendidos,
                'camion4eje_folios_vendidos': camion4eje_folios_vendidos,
                'camion5eje_folios_vendidos': camion5eje_folios_vendidos,
                'camion6eje_folios_vendidos': camion6eje_folios_vendidos,
                'camion7eje_folios_vendidos': camion7eje_folios_vendidos,
                'residente_folios_vendidos': residente_folios_vendidos,
                'residente1eje_folios_vendidos': residente1eje_folios_vendidos,
                'residente2eje_folios_vendidos': residente2eje_folios_vendidos,

                # RECAUDACION INICIO DEL MES A FECHA ACTUAL DEL MES
                'recaudado_acum_mes': recaudado_acum_mes,
                # FECHA DE INICIO DEL MES ACTUAL DE RECAUDACION
                'fecha_recaudacion_iniciomes': fecha_recaudacion_iniciomes,
                # RECAUDACION DEL ANIO
                'recaudado_acum_year': recaudado_acum_year,
                # ANIO DE INICIO acutal
                'fecha_inicioyear_convert': fecha_inicioyear_convert,
                # RECAUDACION DE TODOS LOS TIEMPOS
                'recaudado_todos_tiempos': recaudado_todos_tiempos,

                # DOLARES Y TIPO DE CAMBIO
                'tipo_cambio': float(dolar_tipo_cambio),
                'dolares_matutino': float(self.total_dolares_matutino),
                'dolares_vespertino': float(self.total_dolares_vespertino),
                'dolares_nocturno': float(self.total_dolares_nocturno),

                # IVA
                'iva': float(iva) ,
                }

        return self.env.ref('slrc.fin_turno_report_buttonx').report_action([], data=data)





