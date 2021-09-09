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
    Operators computation for pointer analysis; computing values of variables.
"""

import logging

from . import node as _node

"""
In the following,
    - node: Node
        Current node.
    - initial_node: Node
        Node, which we leveraged to compute the value of node (for provenance purpose).
"""


def get_node_value(node, initial_node=None, recdepth=0, recvisited=None):
    """ Gets the value of node, depending on its type. """

    if recvisited is None:
        recvisited = set()

    if isinstance(node, _node.ValueExpr):
        if node.value is not None:  # Special case if node references a Node whose value changed
            return node.value

    got_attr, node_attributes = node.get_node_attributes()
    if got_attr:  # Got attributes, returns the value
        return node_attributes

    logging.debug('Getting the value from %s', node.name)

    if node.name == 'UnaryExpression':
        return compute_unary_expression(node, initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    if node.name in ('BinaryExpression', 'LogicalExpression'):
        return compute_binary_expression(node, initial_node=initial_node,
                                         recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'ArrayExpression':
        return node
    if node.name in ('ObjectExpression', 'ObjectPattern'):
        return node
    if node.name == 'MemberExpression':
        return compute_member_expression(node, initial_node=initial_node,
                                         recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'ThisExpression':
        return 'this'
    if isinstance(node, _node.FunctionExpression):
        return compute_function_expression(node)
    if node.name == 'CallExpression' and isinstance(node.children[0], _node.FunctionExpression):
        return node.children[0].fun_name  # Function called; mapping to the function name if any
    if node.name in _node.CALL_EXPR:
        return compute_call_expression(node, initial_node=initial_node,
                                       recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'ReturnStatement' or node.name == 'BlockStatement':
        if node.children:
            return get_node_computed_value(node.children[0], initial_node=initial_node,
                                           recdepth=recdepth + 1, recvisited=recvisited)
        return None
    if node.name == 'TemplateLiteral':
        return compute_template_literal(node, initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'ConditionalExpression':
        return compute_conditional_expression(node, initial_node=initial_node,
                                              recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'AssignmentExpression':
        return compute_assignment_expression(node, initial_node=initial_node,
                                             recdepth=recdepth + 1, recvisited=recvisited)
    if node.name == 'UpdateExpression':
        return get_node_computed_value(node.children[0], initial_node=initial_node,
                                       recdepth=recdepth + 1, recvisited=recvisited)

    for child in node.children:
        get_node_computed_value(child, initial_node=initial_node,
                                recdepth=recdepth + 1, recvisited=recvisited)

    logging.warning('Could not get the value of the node %s, whose attributes are %s',
                    node.name, node.attributes)

    return None


def get_node_computed_value(node, initial_node=None, keep_none=False, recdepth=0, recvisited=None):
    """ Computes the value of node, depending on its type. """

    if recvisited is None:
        recvisited = set()

    logging.debug("Visiting node: %s", node.attributes)

    if node in recvisited:
        if isinstance(node, _node.Value):
            logging.debug("Revisiting node: %s %s (value: %s)", node.attributes, initial_node,
                          node.value)
            return node.value
        logging.debug("Revisiting node: %s %s (none)", node.attributes, initial_node)
        return None
    recvisited.add(node)
    if recdepth > 1000:
        logging.debug("Recursion depth for get_node_computed_value exceeded: %s", node.attributes)
        if hasattr(node, "value"):
            return node.value
        return None

    value = None
    if isinstance(initial_node, _node.Value):
        logging.debug('%s is depending on %s', initial_node.attributes, node.attributes)
        initial_node.set_provenance(node)

    if isinstance(node, _node.Value):  # if we already know the value
        value = node.value  # might be directly a value (int/str) or a Node referring to the value
        logging.debug('Computing the value of an %s node, got %s', node.name, value)

        if isinstance(value, _node.Node):  # node.value is a Node
            # computing actual value
            if node.value != node:
                value = get_node_computed_value(node.value, initial_node=initial_node,
                                                recdepth=recdepth + 1, recvisited=recvisited)
                logging.debug('Its value is a node, computed it and got %s', value)

    if value is None and not keep_none:  # node is not an Identifier or is None
        # keep_none True is just for display_temp, to avoid having an Identifier variable with
        # None value being equal to the variable because of the call to get_node_value on itself
        value = get_node_value(node, initial_node=initial_node,
                               recdepth=recdepth + 1, recvisited=recvisited)
        logging.debug('The value should be computed, got %s', value)

    if isinstance(node, _node.Value) and node.name not in _node.CALL_EXPR:
        # Do not store value for CallExpr as could have changed and should be recomputed
        node.set_value(value)  # Stores the value so as not to compute it again

    return value


def compute_operators(operator, node_a, node_b, initial_node=None, recdepth=0, recvisited=None):
    """ Evaluates node_a operator node_b. """

    if isinstance(node_a, _node.Node):  # Standard case
        if isinstance(node_a, _node.Identifier):
            # If it is an Identifier, it should have a value, possibly None.
            # But the value should not be the Identifier's name.
            a = get_node_computed_value(node_a, initial_node=initial_node, keep_none=True,
                                        recdepth=recdepth + 1, recvisited=recvisited)
        else:
            a = get_node_computed_value(node_a, initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    else:  # Specific to compute_binary_expression
        a = node_a  # node_a may not be a Node but already a computed result
    if isinstance(node_b, _node.Node):  # Standard case
        if isinstance(node_b, _node.Identifier):
            b = get_node_computed_value(node_b, initial_node=initial_node, keep_none=True,
                                        recdepth=recdepth + 1, recvisited=recvisited)
        else:
            b = get_node_computed_value(node_b, initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    else:  # Specific to compute_binary_expression
        b = node_b  # node_b may not be a Node but already a computed result

    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
        if operator in ('+=', '+') and (isinstance(a, str) or isinstance(b, str)):
            return operator_plus(a, b)
        if a is None or b is None:
            return None
        if (not isinstance(a, str) or isinstance(a, str) and not '.' in a)\
                and (not isinstance(b, str) or isinstance(b, str) and not '.' in b):
            # So that if MemExpr could not be fully computed we do not take any hasty decisions
            # For ex: data.message.split(-).1.toUpperCase() == POST is undecidable for us
            # But abc == abc is not
            pass
        else:
            logging.warning('Unable to compute %s %s %s', a, operator, b)
            return None

    try:
        if operator in ('+=', '+'):
            return operator_plus(a, b)
        if operator in ('-=', '-'):
            return operator_minus(a, b)
        if operator in ('*=', '*'):
            return operator_asterisk(a, b)
        if operator in ('/=', '/'):
            return operator_slash(a, b)
        if operator in ('**=', '**'):
            return operator_2asterisk(a, b)
        if operator in ('%=', '%'):
            return operator_modulo(a, b)
        if operator == '++':
            return operator_plus_plus(a)
        if operator == '--':
            return operator_minus_minus(a)
        if operator in ('==', '==='):
            return operator_equal(a, b)
        if operator in ('!=', '!=='):
            return operator_different(a, b)
        if operator == '!':
            return operator_not(a)
        if operator == '>=':
            return operator_bigger_equal(a, b)
        if operator == '>':
            return operator_bigger(a, b)
        if operator == '<=':
            return operator_smaller_equal(a, b)
        if operator == '<':
            return operator_smaller(a, b)
        if operator == '&&':
            return operator_and(a, b)
        if operator == '||':
            return operator_or(a, b)
        if operator in ('&', '>>', '>>>', '<<', '^', '|', '&=', '>>=', '>>>=', '<<=', '^=', '|=',
                        'in', 'instanceof'):
            logging.warning('Currently not handling the operator %s', operator)
            return None

    except TypeError:
        logging.warning('Type problem, could not compute %s %s %s', a, operator, b)
        return None

    logging.error('Unknown operator %s', operator)
    return None


def compute_unary_expression(node, initial_node, recdepth=0, recvisited=None):
    """ Evaluates an UnaryExpression node. """

    compute_unary = get_node_computed_value(node.children[0], initial_node=initial_node,
                                            recdepth=recdepth + 1, recvisited=recvisited)
    if compute_unary is None:
        return None
    if isinstance(compute_unary, bool):
        return not compute_unary
    if isinstance(compute_unary, (int, float)):
        return - compute_unary
    if isinstance(compute_unary, str):  # So as not to lose the current compute_unary value
        return node.attributes['operator'] + compute_unary  # Adds the UnaryOp before value

    logging.warning('Could not compute the unary operation %s on %s',
                    node.attributes['operator'], compute_unary)
    return None


def compute_binary_expression(node, initial_node, recdepth=0, recvisited=None):
    """ Evaluates a BinaryExpression node. """

    operator = node.attributes['operator']
    node_a = node.children[0]
    node_b = node.children[1]

    # node_a operator node_b
    return compute_operators(operator, node_a, node_b, initial_node=initial_node,
                             recdepth=recdepth, recvisited=recvisited)


def compute_member_expression(node, initial_node, compute=True, recdepth=0, recvisited=None):
    """ Evaluates a MemberExpression node. """

    obj = node.children[0]
    prop = node.children[1]
    prop_value = get_node_computed_value(prop, initial_node=initial_node, recdepth=recdepth + 1,
                                         recvisited=recvisited)  # Computes the value
    obj_value = get_node_computed_value(obj, initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    if obj.name == 'ThisExpression' or obj_value in _node.GLOBAL_VAR:
        return prop_value

    if not isinstance(obj_value, _node.Node):
        # Specific case if we changed an Array/Object type
        # var my_array = [[1]]; my_array[0] = 18; e = my_array[0][0]; -> e undefined hence None
        # If ArrayExpression or ObjectExpression, we are trying to access an element that does not
        # exist anymore, will be displayed as <node.ValueExpr>.prop
        # Otherwise: obj.prop
        if isinstance(obj_value, list):  # Special case for TaggedTemplateExpression
            if isinstance(prop_value, int):
                try:
                    return obj_value[prop_value]  # Params passed in obj_value, cf. data_flow
                except IndexError as e:
                    logging.exception(e)
                    logging.exception('Could not get the property %s of %s', prop_value, obj_value)
                    return None
        elif isinstance(obj_value, dict):  # Special case for already defined objects with new prop
            if prop_value in obj_value:
                return obj_value[prop_value]  # ex: localStorage.firstTime
            return None
        return display_member_expression_value(node, '', initial_node=initial_node)[0:-1]

    # obj_value.prop_value or obj_value[prop_value]
    if obj_value.name == 'Literal' or obj_value.name == 'Identifier':
        member_expression_value = obj_value  # We already have the value
    else:
        if isinstance(prop_value, str):  # obj_value.prop_value -> prop_value str = object property
            obj_prop_list = []
            search_object_property(obj_value, prop_value, obj_prop_list)
            if obj_prop_list:  # Stores all matches
                member_expression_value = None
                for obj_prop in obj_prop_list:
                    member_expression_value, worked = get_property_value(obj_prop,
                                                                         initial_node=initial_node,
                                                                         recdepth=recdepth + 1,
                                                                         recvisited=recvisited)
                    if worked:  # Takes the first one that is working
                        break
            else:
                member_expression_value = None
                logging.warning('Could not get the property %s of the %s with value %s',
                                prop_value, obj.name, obj_value)
        elif isinstance(prop_value, int):  # obj_value[prop_value] -> prop_value int = array index
            if len(obj_value.children) > prop_value:
                member_expression_value = obj_value.children[prop_value]  # We fetch the value
            else:
                member_expression_value = display_member_expression_value\
                                              (node, '', initial_node=initial_node)[0:-1]
        else:
            logging.error('Expected an str or an int, got a %s', type(prop_value))
            member_expression_value = None

    if compute and isinstance(member_expression_value, _node.Node):
        # Computes the value
        return get_node_computed_value(member_expression_value, initial_node=initial_node,
                                       recdepth=recdepth + 1)

    return member_expression_value  # Returns the node referencing the value


def search_object_property(node, prop, found_list):
    """ Search in an object definition where a given property (-> prop = str) is defined.
    Storing all the matches in case the first one is not the right one, e.g.,
    var obj = {
        f1: function(a) {obj.f2(1)},
        f2: function(a) {}
    };
    obj.f2();
    By looking for f2, the 1st match is wrong and will lead to an error, the 2nd one is correct."""

    if 'name' in node.attributes:
        if isinstance(prop, str):
            if node.attributes['name'] == prop:
                # prop is already the value
                found_list.append(node)
    elif 'value' in node.attributes:
        if isinstance(prop, str):
            if node.attributes['value'] == prop:
                # prop is already the value
                found_list.append(node)

    for child in node.children:
        search_object_property(child, prop, found_list)


def get_property_value(node, initial_node, recdepth=0, recvisited=None):
    """ Get the value of an object's property. """

    if (isinstance(node, _node.Identifier) or node.name == 'Literal')\
            and node.parent.name == 'Property':
        prop_value = node.parent.children[1]
        if prop_value.name == 'Literal':
            return prop_value, True
        return get_node_computed_value(prop_value, initial_node=initial_node, recdepth=recdepth + 1,
                                       recvisited=recvisited), True

    logging.warning('Trying to get the property value of %s whose parent is %s',
                    node.name, node.parent.name)
    return None, False


def compute_function_expression(node):
    """ Computes a (Arrow)FunctionExpression node. """

    fun_name = node.fun_name
    if fun_name is not None:
        return fun_name  # Mapping to the function's name if any
    return node  # Otherwise mapping to the FunExpr handler


def compute_call_expression(node, initial_node, recdepth=0, recvisited=None):
    """ Gets the value of CallExpression with parameters. """

    if isinstance(initial_node, _node.Value):
        initial_node.set_provenance(node)

    callee = node.children[0]
    params = '('

    for arg in range(1, len(node.children)):
        # Computes the value of the arguments: a.b...(arg1, arg2...)
        params += str(get_node_computed_value(node.children[arg], initial_node=initial_node,
                                              recdepth=recdepth + 1, recvisited=recvisited))
        if arg < len(node.children) - 1:
            params += ', '

    params += ')'

    if isinstance(callee, _node.Identifier):
        return str(get_node_computed_value(callee, initial_node=initial_node,
                                           recdepth=recdepth + 1, recvisited=recvisited)) + params

    if callee.name == 'MemberExpression':
        value = display_member_expression_value(callee, '', initial_node=initial_node)
        value = value[0:-1] + params
        return value
        # return compute_member_expression(callee) + params  # To test if problems here

    if callee.name in _node.CALL_EXPR:
        if get_node_computed_value(callee, initial_node=initial_node, recdepth=recdepth + 1,
                                   recvisited=recvisited) is None or params is None:
            return None
        return get_node_computed_value(callee, initial_node=initial_node,
                                       recdepth=recdepth + 1, recvisited=recvisited) + params

    if callee.name == 'LogicalExpression':  # a || b, if a not False a otherwise b
        if get_node_computed_value(callee.children[0], initial_node=initial_node,
                                   recdepth=recdepth + 1, recvisited=recvisited) is False:
            return get_node_computed_value(callee.children[1], initial_node=initial_node,
                                           recdepth=recdepth + 1, recvisited=recvisited)
        return get_node_computed_value(callee.children[0], initial_node=initial_node,
                                       recdepth=recdepth + 1, recvisited=recvisited)

    logging.error('Got a CallExpression on %s with attributes %s and id %s',
                  callee.name, callee.attributes, callee.id)
    return None


def compute_template_literal(node, initial_node, recdepth=0, recvisited=None):
    """ Gets the value of TemplateLiteral. """

    template_element = []  # Seems that TemplateElement = similar to Literal and in front
    expressions = []  # vs. Expressions has to be computed and are at the end
    template_literal = ''

    for child in node.children:
        if child.name == 'TemplateElement':  # Either that
            template_element.append(child)
        else:  # Or Expressions
            expressions.append(child)

    len_template_element = len(template_element)
    len_expressions = len(expressions)

    if len_template_element != len_expressions + 1:
        logging.error('Unexpected %s with %s TemplateElements and %s Expressions', node.type,
                      len_template_element, len_expressions)
        return None

    for i in range(len_expressions):
        # Will concatenate: 1 TemplateElement, 1 Expr, ..., 1 TemplateElement
        template_literal += str(get_node_computed_value(template_element[i],
                                                        initial_node=initial_node,
                                                        recdepth=recdepth + 1,
                                                        recvisited=recvisited)) \
                            + str(get_node_computed_value(expressions[i],
                                                          initial_node=initial_node,
                                                          recdepth=recdepth + 1,
                                                          recvisited=recvisited))
    template_literal += str(get_node_computed_value(template_element[len_template_element - 1],
                                                    initial_node=initial_node,
                                                    recdepth=recdepth + 1,
                                                    recvisited=recvisited))

    return template_literal


def display_member_expression_value(node, value, initial_node):
    """ Displays the value of elements from a MemberExpression. """

    for child in node.children:
        if child.name == 'MemberExpression':
            value = display_member_expression_value(child, value, initial_node=initial_node)
        else:
            value += str(get_node_computed_value(child, initial_node=initial_node)) + '.'
    return value


def compute_object_expr(node, initial_node):
    """ For debug: displays the content of an ObjectExpression. """

    node_value = '{'

    for prop in node.children:
        key = prop.children[0]
        key_value = get_node_computed_value(key, initial_node=initial_node)
        value = prop.children[1]
        value_value = get_node_computed_value(value, initial_node=initial_node)

        prop_value = str(key_value) + ': ' + str(value_value)
        node_value += '\n\t' + prop_value

    node_value += '\n}'
    return node_value


def compute_conditional_expression(node, initial_node, recdepth=0, recvisited=None):
    """ Gets the value of a ConditionalExpression. """

    test = get_node_computed_value(node.children[0], initial_node=initial_node,
                                   recdepth=recdepth + 1, recvisited=recvisited)
    consequent = get_node_computed_value(node.children[1], initial_node=initial_node,
                                         recdepth=recdepth + 1, recvisited=recvisited)
    alternate = get_node_computed_value(node.children[2], initial_node=initial_node,
                                        recdepth=recdepth + 1, recvisited=recvisited)
    if not isinstance(test, bool):
        test = None  # So that must be either True, False or None
    if test is None:
        return [alternate, consequent]
    if test:
        return consequent
    return alternate


def compute_assignment_expression(node, initial_node, recdepth=0, recvisited=None):
    """ Computes the value of an AssignmentExpression node. """

    var = node.children[0]  # Value coming from the right: a = b = value, computing a knowing b
    if isinstance(var, _node.Value) and var.value is not None:
        return var.value
    return get_node_computed_value(var, initial_node=initial_node,
                                   recdepth=recdepth + 1, recvisited=recvisited)


def operator_plus(a, b):
    """ Evaluates a + b. """
    if isinstance(a, str) or isinstance(b, str):
        return str(a) + str(b)
    return a + b


def operator_minus(a, b):
    """ Evaluates a - b. """
    return a - b


def operator_asterisk(a, b):
    """ Evaluates a * b. """
    return a * b


def operator_slash(a, b):
    """ Evaluates a / b. """
    if b == 0:
        logging.warning('Trying to compute %s / %s', a, b)
        return None
    return a / b


def operator_2asterisk(a, b):
    """ Evaluates a ** b. """
    return a ** b


def operator_modulo(a, b):
    """ Evaluates a % b. """
    return a % b


def operator_plus_plus(a):
    """ Evaluates a++. """
    return a + 1


def operator_minus_minus(a):
    """ Evaluates a--. """
    return a - 1


def operator_equal(a, b):
    """ Evaluates a == b. """
    return a == b


def operator_different(a, b):
    """ Evaluates a != b. """
    return a != b


def operator_not(a):
    """ Evaluates !a. """
    return not a


def operator_bigger_equal(a, b):
    """ Evaluates a >= b. """
    return a >= b


def operator_bigger(a, b):
    """ Evaluates a > b. """
    return a > b


def operator_smaller_equal(a, b):
    """ Evaluates a <= b. """
    return a <= b


def operator_smaller(a, b):
    """ Evaluates a < b. """
    return a < b


def operator_and(a, b):
    """ Evaluates a and b. """
    return a and b


def operator_or(a, b):
    """ Evaluates a or b. """
    return a or b
