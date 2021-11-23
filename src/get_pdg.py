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


"""
    Gets or unpickles a PDG.
"""

import logging
import pickle

import pdg_js.node as _node
from pdg_js.build_pdg import get_data_flow
from pdg_js.js_operators import get_node_computed_value, get_node_value
import pdg_js.utility_df as utility_df


def get_pdg(file_path, res_dict, store_pdgs=None):
    """ Gets the PDG of a given file. """

    return get_data_flow(file_path, benchmarks=res_dict, store_pdgs=store_pdgs, save_path_pdg=False,
                         beautiful_print=False, check_json=False)


def unpickle_pdg(pdg_path):
    """ Tries to unpickle a given PDG. """

    logging.info('Unpickling %s', pdg_path)
    try:
        pdg = pickle.load(open(pdg_path, 'rb'))
        return pdg
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except:
        logging.exception('The PDG of %s could not be loaded', pdg_path)
    return _node.Node('Program')  # Empty PDG to avoid trying to get the children of None


def get_node_computed_value_e(node):
    """ Added Exception to traditional get_node_computed_value. """

    try:
        return get_node_computed_value(node)
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except Exception as e:
        logging.exception(e)
        logging.exception('Could not get the computed value of %s with id %s',
                          node.attributes, node.id)
        return None


def get_node_value_e(node):
    """ Added Exception to traditional get_node_value. """

    try:
        return get_node_value(node)
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except Exception as e:
        logging.exception(e)
        logging.exception('Could not get the value of %s with id %s', node.attributes, node.id)
        return None
