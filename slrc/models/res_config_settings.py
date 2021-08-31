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


class PosParametros(models.Model):
    _name = 'pos_parametro.parametros'

    dolar = fields.Float(string="Dolar", )


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    default_dolar = fields.Char(string="Dolar", default_model='pos_parametro.parametros')

    def set_values_pos(self):
        super(ResConfigSettings, self).set_values_pos()
        self.env['ir.config_parameter'].sudo().set_param('pos_parametro.parametros.cajero', self.default_dolar)