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
    Sensitive APIs in browser extensions that could lead to vulnerabilities.
"""

import logging

import pdg_js.node as _node

import utility
from get_pdg import get_node_computed_value_e

PRINT_DEBUG = utility.PRINT_DEBUG


class ApiInfo:
    """ Information regarding sensitive APIs detected. """

    def __init__(self, api_name, api_node, api_value):
        self.api_name = api_name  # API name
        self.api_node = api_node  # Node where the previous API was found
        self.api_value = api_value  # Value of the previous node (where the API was found)
        self.api_params = []  # Storing the parameters value (rather for the dangerous sinks)


class Danger:
    """ Dangerous sinks, several ways to exploit them depending on their type. """

    def __init__(self, direct, indirect, exfiltration):
        self.direct = direct  # Sensitive API + in sink directly exploited
        self.indirect = indirect  # Sensitive API + in sink + sent back to WA
        self.exfiltration = exfiltration  # Sink + sent back to WA


def add_danger(where, api_name, api_node, api_value, params=None):
    """ Adds a danger (in the form of an ApiInfo object) in the 'where' Danger property. """

    if not isinstance(params, list):
        where.append(ApiInfo(api_name, api_node, api_value))
    else:
        app_info = ApiInfo(api_name, api_node, api_value)
        app_info.api_params = params  # Storing the sink's parameters
        where.append(app_info)


class ExtensionAnalysis:
    """ Specific extension component. Storing the corresponding sinks + dangers. """

    def __init__(self, direct_sinks, indirect_sinks, exfiltration_sinks):
        self.dangers = Danger(direct=[], indirect=[], exfiltration=[])
        self.sinks = Danger(direct=direct_sinks, indirect=indirect_sinks,
                            exfiltration=exfiltration_sinks)


class Extension:
    """ Extension different components. Storing the corresponding sinks + dangers. """

    def __init__(self, apis):
        """ apis is a dict storing the sensitive APIs to consider. """
        self.cs = ExtensionAnalysis(direct_sinks=apis['cs']['direct_dangers'],
                                    indirect_sinks=apis['cs']['indirect_dangers'],
                                    exfiltration_sinks=None)
        self.bp = ExtensionAnalysis(direct_sinks=apis['bp']['direct_dangers'],
                                    indirect_sinks=apis['bp']['indirect_dangers'],
                                    exfiltration_sinks=apis['bp']['exfiltration_dangers'])


def get_sink_name(sink):
    """ Returns the sink name without '$.', 'jQuery.', or '()'. """

    if sink == 'XMLHttpRequest().open':
        return 'XMLHttpRequest.open'
    return sink.replace('$.', '').replace('jQuery.', '')
    # So that, e.g., $.ajax and jQuery.ajax will be stored as ajax


def check_dangerous_sinks(node, value, which_sinks):
    """ Checks if the value 'value' of node is part of a dangerous sink. """

    for sinks in which_sinks.values():
        for sink in sinks:
            found = False
            if sink in value:
                if value == sink:  # Perfect match
                    found = True
                else:
                    # sink = '.' + sink  # May be useful to change sink name for debug
                    if value.endswith('.' + sink):  # Sometimes the sink is used as X.sink
                        found = True
                if found:
                    logging.debug('The dangerous sink %s was called', sink)
                    if PRINT_DEBUG:
                        traverse(node)
                    return True, get_sink_name(sink)
    return False, None


def check_async_xhr(node, value, which_sinks):
    """ Checks if the value 'value' of node is part of an asynchronous XHR sink. """

    for sinks in which_sinks.values():
        for sink in sinks:
            if sink in ('XMLHttpRequest().open', 'XMLHttpRequest.open'):  # Check only for XHR
                if 'XMLHttpRequest' in value and '.open(' in value:
                    logging.debug('The dangerous sink %s was called', sink)
                    if PRINT_DEBUG:
                        traverse(node)
                    return True, get_sink_name(sink)
    return False, None


def search_call_params(node):
    """ Searches for the parameters of a CallExpression node. """

    params = []
    if node.name in ('CallExpression', 'TaggedTemplateExpression'):
        for child in node.children:
            if child.body in ('arguments', 'quasi'):
                params.append(child)
    return params


def which_param(api):
    """ Indicates which parameter would be relevant for an attacker. """
    # Note 1: beginning at 1.
    # Note 2: the exfiltration API are not considered here.

    apis_dict = {
        'ajax': [1, False],
        'downloads.download': [1, True],  # + check that 'url' attacker controllable
        'eval': [1, False],
        'get': [1, False],
        'fetch': [1, False],
        'management.setEnabled': [1, False],
        'post': [1, False],
        'setInterval': [1, True],  # + check that param not Function
        'setTimeout': [1, True],  # + check that param not Function
        'storage.local.get': [1, False],
        'storage.local.set': [1, False],
        'storage.sync.get': [1, False],
        'storage.sync.set': [1, False],
        'tabs.executeScript': [2, True],  # (could be 1) + check that 'code' attacker controllable
        'XMLHttpRequest.open': [2, False],
    }
    try:
        return apis_dict[api]
    except KeyError:
        return None


def get_relevant_param(node, api):
    """
    Collects the parameters "interesting" for an attacker. Discards the rest.
    :param node: CallExpression/TaggedTemplateExpression Node, corresponds to a sensitive API;
    :param api: str, sensitive API name (see apis_dict in which_param).
    :return: list, contains the sensitive API's parameters relevant to an attacker.
    """

    params = search_call_params(node)
    param_info = which_param(api)

    if param_info is None:
        return params  # Returns all params if do not know the interesting ones

    param_nb, further_analysis = param_info  # (relevant param number, need further analysis or not)

    try:
        relevant_param = params[param_nb-1]  # Because param_nb starts at 1
    except IndexError:
        if api == 'tabs.executeScript' and len(params) == 1:
            # tabs.executeScript may have only 1 param, see below
            relevant_param = params[0]
        else:
            return params

    if not further_analysis:  # No further analysis needed, we got the interesting param
        return [relevant_param]

    if api in ('setInterval', 'setTimeout'):
        if relevant_param.name in ('Literal', 'BinaryExpression', 'CallExpression',
                                   'TaggedTemplateExpression'):  # Only a string is interesting
            return [relevant_param]

    elif api == 'downloads.download':
        relevant_param = extract_obj_prop(relevant_param, 'url')  # Only url field is interesting
        if relevant_param is not None:
            return relevant_param

    elif api == 'tabs.executeScript':
        saved_relevant_param2 = relevant_param  # Save param for future use
        relevant_param = extract_obj_prop(relevant_param, 'code', key_avoid_value=True)
        # Only code field is interesting
        if relevant_param == 'file':  # Can be file or code, but not both
            return []  # So, nothing interesting here
        if relevant_param is not None:
            return relevant_param
        # tabs.executeScript(tabId, details{code: ...}, callback)
        relevant_param = params[0]  # tabId is optional, so interesting part could be first param
        saved_relevant_param1 = relevant_param  # Save param for future use
        relevant_param = extract_obj_prop(relevant_param, 'code', key_avoid_value=True)
        if relevant_param == 'file':
            return []
        if relevant_param is not None:
            return relevant_param
        # The details parameter could be aliased; to avoid FNs, reports all params (could lead
        # to FPs though). See hdanmfijddamndfaabibmcafmnhhmebi
        return [saved_relevant_param1, saved_relevant_param2]

    return []


def extract_obj_prop(relevant_param, key_expected_value, key_avoid_value=False):
    """ Specific to downloads.download (-> url) and tabs.executeScript (-> code) APIs.
    Returns the value corresponding to the url/code object's entry if any. None otherwise. """
    # For tabs.executeScript, if we spot the 'file' key, the 'code' property cannot coexist.

    if relevant_param.name == 'ObjectExpression':
        for prop in relevant_param.children:  # iterates over object's properties
            if len(prop.children) == 2:
                obj_key = prop.children[0]
                obj_value = prop.children[1]
                if obj_key.body == 'key' and obj_value.body == 'value':
                    if isinstance(obj_key, _node.Identifier) or obj_key.name == 'Literal':
                        if get_node_computed_value_e(obj_key) == key_expected_value:
                            return [obj_value]  # We are only interested in 'url'/'code' parameters
                        if key_avoid_value:  # To avoid the 'file' key
                            if get_node_computed_value_e(obj_key) == 'file':
                                return 'file'  # as 'file' implies no 'code'
    return None


def traverse(node):
    """ Traverses node and prints where its value is coming from and which values it influences. """

    if isinstance(node, _node.Value):
        print('  ' + node.name, node.attributes)
        print('> Coming from:')
        for p in node.provenance_parents:
            print(p.name, p.attributes, get_node_computed_value_e(p))
        print('> Will influence:')
        for c in node.provenance_children:
            print(c.name, c.attributes)
        print('--------')

    for child in node.children:
        traverse(child)
