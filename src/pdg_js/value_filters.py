# Copyright (C) 2021 Aurore Fass
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


""" Prints variables with their corresponding value. And logs whether an insecure API was used. """

import logging
from . import node as _node
from .js_operators import get_node_computed_value, get_node_value
from . import utility_df

INSECURE = ['document.write']
DISPLAY_VAR = utility_df.DISPLAY_VAR  # To display the variables' value or not


def is_insecure_there(value):
    """ Checks if value is part of an insecure API. """

    for insecure in INSECURE:
        if insecure in value:
            logging.debug('Found a call to %s', insecure)


def display_values(var, keep_none=True, check_insecure=True, recompute=False):
    """ Print var = its value and checks whether the value is part of an insecure API. """

    if not DISPLAY_VAR:  # We do not want the values printed during large-scale analyses
        return

    if recompute:  # If we store ALL value sometimes we need to recompute them as could have changed
        # Currently not executed, check if set_value in get_node_computed_value
        value = get_node_value(var)
        var.set_value(value)
    else:
        value = var.value  # We store value so as not to compute it AGAIN
    if isinstance(value, _node.Node) or value is None:  # Only if necessary
        value = get_node_computed_value(var, keep_none=keep_none)  # Gets variable value

    if isinstance(var, _node.Identifier):
        variable = get_node_value(var)
        print('\t' + variable + ' = ' + str(value))  # Prints variable = value

    elif var.name in _node.CALL_EXPR + ['ReturnStatement']:
        print('\t' + var.name + ' = ' + str(value))  # Prints variable = value)

    if isinstance(value, _node.Node):
        print('\t' + value.name, value.attributes, value.id)

    elif isinstance(value, str) and check_insecure:
        is_insecure_there(value)  # Checks for usage of insecure APIs
