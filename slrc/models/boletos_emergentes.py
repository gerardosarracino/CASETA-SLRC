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

_logger = logging.getLogger(__name__)


class BoletosEmergentes(models.Model):
    _name = 'pos.boletos_emergentes'
    _rec_name = 'sesion'

    sesion = fields.Many2one('pos.session', string="Sesion")
    cajero = fields.Many2one('res.users', string="Cajero")
    jefe_operaciones = fields.Many2one('res.users', string="Encargado de subir estos boletos emergentes")
    fecha_del = fields.Datetime(string="", required=False, )
    fecha_al = fields.Datetime(string="", required=False, )
    tabla_cuotas = fields.Many2many('pos.tabla_emergentes')

    def unlink(self):
        self.tabla_cuotas.unlink()
        return super(BoletosEmergentes, self).unlink()


class TablaEmergentes(models.Model):  # TABLA PARA ELEGIR PRODUCTOS EN EL APARTADO DE BOLETOS EMERGENTES
    _name = 'pos.tabla_emergentes'
    _rec_name = 'id_boleto_emergente'

    id_boleto_emergente = fields.Many2one('pos.boletos_emergentes', string="Id", store=True)
    cuota = fields.Many2one('product.template', string="Cuota", store=True)
    cantidad = fields.Integer('Cantidad', store=True)
    costo_cuota = fields.Float('Costo', related="cuota.list_price")
    total = fields.Float('Total', store=True)

    @api.onchange('cantidad')
    def onchange_total(self):
        self.total = self.cantidad * (self.costo_cuota * (self.cuota.taxes_id.amount/100) + self.costo_cuota)
