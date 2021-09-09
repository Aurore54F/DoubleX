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
    Pointer analysis; mapping a variable to where its value is defined.
"""

import logging

from . import js_operators
from .value_filters import get_node_computed_value, display_values
from . import node as _node


"""
In the following and if not stated otherwise,
    - node: Node
        Current node.
    - identifiers: list
        List of Identifier nodes whose values we aim at computing.
    - operator: None or str (e.g., '+=').
"""


def get_node_path(begin_node, destination_node, path):
    """
        Find the path between begin_node and destination_node.
        -------
        Parameters:
        - begin_node: Node
            Entry point, origin.
        - destination_node: Node
            Descendant of begin_node. Destination point.
        - path: list
            Path between begin_node and destination_node.
            Ex: [0, 0, 1] <=> begin_node.children[0].children[0].children[1] = destination_node.
    """

    if begin_node.id == destination_node.id:
        return True

    for i, _ in enumerate(begin_node.children):
        path.append(i)  # Child number i
        found = get_node_path(begin_node.children[i], destination_node, path)
        if found:
            return True
        del path[-1]
    return False


def find_node(var, begin_node, path):
    """ Find the node whose path from begin_node is given. """

    logging.debug('Trying to find the node symmetric from %s using the following path %s from %s',
                  var.name, path, begin_node.name)
    while path:
        child_nb = path.pop(0)
        try:
            begin_node = begin_node.children[child_nb]
        except IndexError:  # Case Asymmetric mapping, e.g., Array or Object mapped to an Identifier
            return begin_node, None

    if not path:  # begin_node is already the node we are looking for
        return begin_node, None

    # Case Asymmetric mapping, e.g., Identifier mapped to an Array or else
    logging.debug('Asymmetric mapping case')
    if begin_node.name in ('ArrayExpression', 'ObjectExpression', 'ObjectPattern', 'NewExpression'):
        value = begin_node
        logging.debug('The value corresponds to node %s', value.name)
        return None, value

    return begin_node, None


def get_member_expression(node):
    """ Returns:
        - if a MemberExpression node ascendant was found;
        - the furthest MemberExpression ascendant (if True) or node.
        - if we are in a window.node or this.node situation. """

    if node.parent.name != 'MemberExpression':
        return False, node, False

    while node.parent.name == 'MemberExpression':
        if node.parent.children[0].name == 'ThisExpression'\
                or get_node_computed_value(node.parent.children[0]) in _node.GLOBAL_VAR:
            return False, node, True
        node = node.parent
    return True, node, False


def map_var2value(node, identifiers, operator=None):
    """
        Map identifier nodes to their corresponding Literal/Identifier values.

        -------
        Parameters:
        - node: Node
            Entry point, either a VariableDeclaration or AssignmentExpression node.
            Therefore:  node.children[0] => Identifier = considered variable;
                        node.children[1] => Identifier/Literal = corresponding value
        - identifiers: list
            List of Identifier nodes to map to their values.

        Trick: Symmetry between AST left-hand side (declaration) and right-hand side (value).
    """

    if node.name != 'VariableDeclarator' and node.name != 'AssignmentExpression' \
            and node.name != 'Property':
        # Could be called on other Nodes because of assignment_expr_df which calculates DD on
        # right-hand side elements which may not be variable declarations/assignments anymore
        return

    var = node.children[0]
    init = node.children[1]

    for decl in identifiers:
        # Compute the value for each decl, as it might have changed
        logging.debug('Computing a value for the variable %s with id %s',
                      decl.attributes['name'], decl.id)

        decl.set_update_value(True)  # Will be updated when printed in display_temp
        member_expr, decl, this_window = get_member_expression(decl)

        path = list()
        get_node_path(var, decl, path)
        if this_window:
            path.pop()  # We jump over the MemberExpression parent to keep the symmetry

        if isinstance(init, _node.Identifier) and isinstance(init.value, _node.Node):
            try:
                logging.debug('The variable %s was initialized with the Identifier %s which already'
                              ' has a value', decl.attributes['name'], init.attributes['name'])
            except KeyError:
                logging.debug('The variable %s was initialized with the Identifier %s which already'
                              ' has a value', decl.name, init.name)
            value_node, value = find_node(var, init.value, path)
        else:
            if isinstance(decl, _node.Identifier):
                logging.debug('The variable %s was not initialized with an Identifier or '
                              'it does not already have a value', decl.attributes['name'])
            else:
                logging.debug('The %s %s was not initialized with an Identifier or '
                              'it does not already have a value', decl.name, decl.attributes)
            value_node, value = find_node(var, init, path)
            if value_node is not None:
                logging.debug('Got the node %s', value_node.name)

        if value is None:
            if isinstance(decl, _node.Identifier):
                logging.debug('Calculating the value of the variable %s', decl.attributes['name'])
            else:
                logging.debug('Calculating the value')
            if operator is None:
                logging.debug('Fetching the value')
                # We compute the value ourselves
                value = get_node_computed_value(value_node, initial_node=decl)
                if isinstance(decl, _node.Identifier):
                    decl.set_code(node)  # Add code

            else:
                logging.debug('Found the %s operator, computing the value ourselves', operator)
                # We compute the value ourselves: decl operator value_node
                value = js_operators.compute_operators(operator, decl, value_node,
                                                       initial_node=decl)
                if isinstance(decl, _node.Identifier):
                    decl.set_code(node)  # Add code

        else:
            decl.set_code(node)  # Add code

        if not member_expr:  # Standard case, assign the value to the Identifier node
            logging.debug('Assigning the value %s to %s', value, decl.attributes['name'])
            decl.set_value(value)
            if isinstance(value_node, _node.FunctionExpression):
                fun_name = decl
                if value_node.fun_intern_name is not None:
                    logging.debug('The variable %s refers to the (Arrow)FunctionExpresion %s',
                                  fun_name.attributes['name'],
                                  value_node.fun_intern_name.attributes['name'])
                else:
                    logging.debug('The variable %s refers to an anonymous (Arrow)FunctionExpresion',
                                  fun_name.attributes['name'])
                value_node.set_fun_name(fun_name)
            else:
                display_values(decl)  # Displays values
        else:  # MemberExpression case
            logging.debug('MemberExpression case')
            literal_value = update_member_expression(decl, initial_node=decl)
            if isinstance(literal_value, _node.Value):  # Everything is fine, can store value
                logging.debug('The object was defined, set the value of its property')
                literal_value.set_value(value)  # Modifies value of the node referencing the MemExpr
                literal_value.set_provenance_rec(value_node)  # Updates provenance
                display_values(literal_value)  # Displays values
            else:  # The object is probably a built-in object therefore no handle to get its prop
                logging.debug('The object was not defined, stored its property and set its value')
                obj, all_prop = define_obj_properties(decl, value, initial_node=decl)
                obj.set_value(all_prop)
                obj.set_provenance_rec(value_node)  # Updates provenance
                display_values(obj)


def compute_update_expression(node, identifier):
    """ Evaluates an UpdateExpression node. """

    identifier.set_update_value(True)  # Will be updated when printed in display_temp
    operator = node.attributes['operator']
    value = js_operators.compute_operators(operator, identifier, 0)
    identifier.set_value(value)
    identifier.set_code(node.parent)


def update_member_expression(member_expression_node, initial_node):
    """ If a MemberExpression is modified (i.e., left-hand side of an assignment),
    modifies the value of the node referencing the MemberExpression. """

    literal_value = js_operators.compute_member_expression(member_expression_node,
                                                           initial_node=initial_node, compute=False)
    return literal_value


def search_properties(node, tab):
    """ Searches the Identifier/Literal nodes properties of a MemberExpression node. """

    if node.name in ('Identifier', 'Literal'):
        if get_node_computed_value(node) not in _node.GLOBAL_VAR:  # do nothing if window &co
            tab.append(node)  # store left member as not window &co

    for child in node.children:
        search_properties(child, tab)


def define_obj_properties(member_expression_node, value, initial_node):
    """ Defines the properties of a built-in object. Returns the object + its properties. """

    properties = []
    search_properties(member_expression_node, properties)  # Got all prop

    obj = properties[0]
    obj_init = get_node_computed_value(obj, initial_node=initial_node)
    # The obj may already have some properties
    properties = properties[1:]
    properties_value = [get_node_computed_value(prop,
                                                initial_node=initial_node) for prop in properties]

    # Good for debugging to see dict content, but cannot be used as loses link to variables
    # if isinstance(value, _node.Node):
    #     if value.name in ('ObjectExpression', 'ObjectPattern'):
    #         value = js_operators.compute_object_expr(value)

    if isinstance(obj_init, dict):  # the obj already have properties
        all_prop = obj_init  # initialize obj with its existing properties
    elif isinstance(obj_init, str):  # the obj was previously defined with value obj_init
        all_prop = {obj_init: {}}  # store its previous value as a property to keep it
    else:
        all_prop = {}  # initialize with empty dict
    previous_prop = all_prop
    for i in range(len(properties_value) - 1):
        prop = properties_value[i]
        if prop not in previous_prop or not isinstance(previous_prop[prop], dict):
            previous_prop[prop] = {}  # previous_prop[prop] does not already exist
        previous_prop = previous_prop[prop]
    previous_prop[properties_value[-1]] = value  # prop0.prop1.prop2... = value

    return obj, all_prop
