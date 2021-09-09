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
    Adds data flow to the AST previously enhanced with control flow.
"""

# Note: new data flow analysis, going significantly beyond the one of HideNoSeek:
# pointer analysis, function argument passing, parameter flows, handling scope, etc


import logging
import copy

from . import node as _node
from . import js_reserved
from . import scope as _scope
from . import utility_df
from .build_ast import save_json, get_code
from .pointer_analysis import map_var2value, compute_update_expression, display_values
from .js_operators import get_node_computed_value, get_node_value

# To print the exceptions encountered while building the PDG, or not
PDG_EXCEPT = utility_df.PDG_EXCEPT
# If function called on itself, then max times to avoid infinite recursion
LIMIT_RETRAVERSE = utility_df.LIMIT_RETRAVERSE
# If iterating through a loop, then max times to avoid infinite loops
LIMIT_LOOP = utility_df.LIMIT_LOOP

"""
In the following,
    - scopes: list of Scope
        Stores the variables currently declared and where they should be referred to.
    - id_list: list
        Stores the id of the node already handled.
     - entry: int
        Indicates if we are in the global scope (1) or not (0).

If not stated otherwise,
    - node: Node
        Current node.

If not stated otherwise, the defined functions return a list of Scope.
"""


def get_pos_identifier(identifier_node, scopes):
    """ Position of identifier_node in the corresponding scope. """

    for scope_index, scope in reversed(list(enumerate(scopes))):
        # Search from local scopes to the global one, if no match found
        var_index = scope.get_pos_identifier(identifier_node)
        if var_index is not None:
            return var_index, scope_index  # Variable position, corresponding scope index
    return None, None


def get_nearest_statement(node, answer=None, fun_expr=False):
    """
        Gets the statement node nearest to node (using CF).

        -------
        Parameters:
        - answer: Node
            Such that isinstance(answer, _node.Statement) = True. Used to force taking a statement
            node parent of the nearest node (use case: boolean DF). Default: None.
        - fun_expr: bool
            Specific to FunctionExpression nodes. Default: False.

        -------
        Returns:
        - Node:
            answer, if given, otherwise the statement node nearest to node.
    """

    if answer is not None:
        return answer

    # else: answer is None

    if isinstance(node, _node.Statement)\
            or (fun_expr and isinstance(node, _node.FunctionExpression)):
        # To also get the code back from a FunctionExpression node (which is no Statement)
        return node

    if len(node.statement_dep_parents) > 1:
        logging.warning('Several statement dependencies are joining on the same node %s',
                        node.name)
    return get_nearest_statement(node.parent, fun_expr=fun_expr)


def set_data_dep(begin_data_dep, identifier_node, scopes, nearest_statement=None):
    """
        Sets the DD from begin_data_dep to identifier_node. Also updates the value of
        identifier_node with the value of begin_data_dep.

        -------
        Parameters:
        - begin_data_dep: Node
            Begin of the DF.
        - identifier_node: Node
            End of the DF.
        - nearest_statement: Node or None
            Nearest statement node stored or None.
    """

    begin_data_dep.set_data_dependency(extremity=identifier_node,
                                       nearest_statement=nearest_statement)  # Draws DD
    identifier_node.set_value(begin_data_dep.value)  # Initiates new node to previous value
    identifier_node.set_code(begin_data_dep.code)  # Initiates new node to previous code

    if begin_data_dep.fun is not None:  # The beginning of the DF is a function
        function_def = begin_data_dep.fun
        how_called = identifier_node.parent
        if how_called.name in _node.CALL_EXPR\
                and how_called.children[0].id == identifier_node.id:
            # Case from handle_call_expr
            pass
        else:
            # The function may be executed even without CallExpr/TaggedTemplateExpr, but with
            # a Promise or a callback; ensures that the function will be retraversed here
            logging.debug('Retraversing the function')
            # Traverse function again
            function_def.set_retraverse()  # Sets retraverse property to True
            function_scope(node=function_def, scopes=scopes, id_list=[])
            # Not sure if scopes properly handled...


def set_df(scope, var_index, identifier_node, scopes):
    """
        Sets the DD from the variable in scope at position var_index, to identifier_node.

        -------
        Parameters:
        - scope: Scope
            List of variables.
        - var_index: int
            Position of the variable considered in var.
        - identifier_node: Node
            End of the DF.
    """

    if not isinstance(scope, _scope.Scope):
        logging.error('The parameter given should be typed Scope. Got %s', str(scope))
    else:
        begin_df = get_nearest_statement(scope.var_list[var_index], scope.var_if2_list[var_index])
        begin_id_df = scope.var_list[var_index]
        if isinstance(begin_df, list):
            for i, _ in enumerate(begin_df):
                set_data_dep(begin_data_dep=begin_df[i], identifier_node=identifier_node,
                             scopes=scopes)
        else:
            set_data_dep(begin_data_dep=begin_id_df, identifier_node=identifier_node,
                         nearest_statement=begin_df, scopes=scopes)


def search_identifiers(node, id_list, tab, rec=True):
    """
        Searches the Identifier nodes children of node.

        -------
        Parameters:
        - tab: list
            To store the Identifier nodes found.
        - rec: Bool
            Indicates whether to go recursively in the node or not. Default: True (i.e. recursive).

        -------
        Returns:
        - list
            Stores the Identifier nodes found.
    """

    if node.name == 'ObjectExpression':  # Only consider the object name, no properties
        pass
    elif node.name in _node.CALL_EXPR:  # Don't want to go there, as param should not be detected
        pass
    elif node.name == 'Identifier':
        """
        MemberExpression can be:
        - obj.prop[.prop.prop...]: we consider only obj;
        - this.something or window.something: we consider only something.
        """
        if node.parent.name == 'MemberExpression':
            if node.parent.children[0] == node:  # left member
                if get_node_computed_value(node) in _node.GLOBAL_VAR:  # do nothing if window &co
                    id_list.append(node.id)  # As GLOBAL_VAR are still Identifiers
                    logging.debug('%s is not the variable\'s name', node.attributes['name'])

                else:
                    tab.append(node)  # store left member as not window &co

            elif node.parent.children[1] == node:  # right member
                if node.parent.children[0].name == 'ThisExpression'\
                        or get_node_computed_value(node.parent.children[0]) in _node.GLOBAL_VAR:
                    # left member is not a valid Identifier, what about right member?
                    if get_node_computed_value(node) in _node.GLOBAL_VAR:  # ignore right member too
                        id_list.append(node.id)  # As GLOBAL_VAR are still Identifiers
                        logging.debug('%s is not the variable\'s name', node.attributes['name'])

                    else:
                        tab.append(node)  # store right member as not window &co

                else:  # left member is a valid Identifier, consider right too only if bracket...
                    if node.parent.attributes['computed']:  # ... notation as could be an index
                        logging.debug('The variable %s was considered', node.attributes['name'])
                        tab.append(node)
        else:
            tab.append(node)  # Otherwise this is just a variable
    else:
        if rec:
            for child in node.children:
                search_identifiers(child, id_list, tab, rec)

    return tab


def assignment_df(identifier_node, scopes, update=False):
    """ Adds DD on Identifier nodes. """

    var_index, scope_index = get_pos_identifier(identifier_node, scopes)
    if var_index is not None:  # Position of identifier_node
        if scope_index == 0:  # Global scope
            logging.debug('The global variable %s was used', identifier_node.attributes['name'])
        else:
            logging.debug('The variable %s was used', identifier_node.attributes['name'])
        # Data dependency between last time variable used and now
        set_df(scopes[scope_index], var_index, identifier_node, scopes=scopes)
        if update:  # To update last Identifier handler with current one
            scopes[scope_index].update_var(var_index, identifier_node)

    elif identifier_node.attributes['name'].lower() not in js_reserved.KNOWN_WORDS_LOWER:
        logging.debug('The variable %s is unknown', identifier_node.attributes['name'])
        scopes[0].add_unknown_var(identifier_node)


def var_decl_df(node, scopes, entry, assignt=False, obj=False, let_const=False):
    """
        Handles the variables declared.

        -------
        Parameters:
        - node: Node
            Node whose name Identifier is.
        - assignt: Bool
            False if this is a variable declaration with var/let, True if with AssignmentExpression.
            Default: False.
        - obj: Bool
            True if node is an object, False if it is a variable. Default: False.
        - let_const: Bool
            Specific scope for variables declared with let/const keyword. Default: False.
    """

    if_else_assignt = False

    if let_const or 'let_const' in scopes[-1].name:
        # Specific scope for variables declared with let/const keyword
        current_scope = scopes[-1:]
    elif len(scopes) == 1 or entry == 1\
            or (assignt and get_pos_identifier(node, scopes[1:])[0] is None):
        # Only one scope or global scope or (directly assigned and not known as a local variable)
        current_scope = scopes[:1]  # Global scope
    else:
        current_scope = scopes[1:]  # Local scope

    var_index, scope_index = get_pos_identifier(node, current_scope)

    if var_index is None:
        current_scope[-1].add_var(node)  # Add variable in the list
        if not assignt:
            logging.debug('The variable %s was declared', node.attributes['name'])
        else:
            logging.debug('The global variable %s was declared', node.attributes['name'])
        # hoisting(node, scopes)  # Hoisting only for FunctionDeclaration

    else:
        if assignt:
            if obj:  # In the case of objects, we will always keep their AST order
                logging.debug('The object %s was used and modified', node.attributes['name'])
                # Data dependency between last time object used and now
                set_df(current_scope[scope_index], var_index, node, scopes=scopes)
            else:
                logging.debug('The variable %s was modified', node.attributes['name'])
                # To update variable provenance + DF (needed for True/False merged with other scope)
                current_scope[scope_index].add_var_if2(var_index, node)
                if_else_assignt = True
        else:
            logging.debug('The variable %s was redefined', node.attributes['name'])

        if not if_else_assignt:  # Otherwise already added in var_if2
            current_scope[scope_index].update_var(var_index, node)  # Update last time with current


def var_declaration_df(node, scopes, id_list, entry, let_const=False):
    """ Handles the node VariableDeclarator: 1) Element0: id, 2) Element1: init. """

    if node.name == 'VariableDeclarator':
        identifiers = search_identifiers(node.children[0], id_list, tab=[])  # Var definition

        if node.children[0].name != 'ObjectPattern':  # Traditional variable declaration
            for decl in identifiers:
                id_list.append(decl.id)
                var_decl_df(node=decl, scopes=scopes, entry=entry, let_const=let_const)
            if not identifiers:
                logging.warning('No identifier variable found')

        else:  # Specific case for ObjectPattern
            logging.debug('The node %s is an object pattern', node.name)
            scopes = obj_pattern_scope(node.children[0], scopes=scopes, id_list=id_list)

        if len(node.children) > 1:  # Variable initialized
            scopes = data_flow(node.children[1], scopes, id_list=id_list, entry=entry)
            map_var2value(node, identifiers)

        elif node.children[0].name != 'ObjectPattern':  # Var (so not objPattern) not initialized
            for decl in identifiers:
                logging.debug('The variable %s was not initialized', decl.attributes['name'])

        else:  # ObjectPattern not initialized
            logging.debug('The ObjectPattern %s was not initialized', node.children[0].attributes)

        if len(node.children) > 2:
            logging.warning('I did not expect a %s node to have more than 2 children', node.name)

    return scopes


def assignment_expr_df(node, scopes, id_list, entry, call_expr=False):
    """ Handles the node AssignmentExpression: 1) Element0: assignee, 2) Element1: assignt. """

    operator = None
    identifiers = search_identifiers(node.children[0], id_list, tab=[])
    for assignee in identifiers:
        id_list.append(assignee.id)

        # 1) To draw DD from old assignee version
        if 'operator' in assignee.parent.attributes:
            if assignee.parent.attributes['operator'] != '=':  # Could be += where assignee is used
                operator = assignee.parent.attributes['operator']
                assignment_df(identifier_node=assignee, scopes=scopes)

        # 2) The old assignee version can be replaced by the current one
        if (assignee.parent.name == 'MemberExpression'
                and assignee.parent.children[0].name != 'ThisExpression'
                and 'window' not in assignee.parent.children[0].attributes.values())\
                or (assignee.parent.name == 'MemberExpression'
                    and assignee.parent.parent.name == 'MemberExpression'):
            # assignee is an object, we excluded window/this.var, but not window/this.obj.prop
            # logging.warning(assignee.attributes['name'])
            if assignee.parent.attributes['computed']:  # Access through a table, could be an index
                # assignment_df(identifier_node=assignee, scopes=scopes)
                # if get_pos_identifier(assignee, scopes)[0] is not None:
                var_decl_df(node=assignee, scopes=scopes, assignt=True, obj=True, entry=entry)
            else:
                if call_expr:
                    # if get_pos_identifier(assignee, scopes)[0] is not None:
                    # Only if the obj assignee already defined, avoids DF on console.log
                    var_decl_df(node=assignee, scopes=scopes, assignt=True, obj=True,
                                entry=entry)
                else:
                    # if get_pos_identifier(assignee, scopes)[0] is not None:
                    var_decl_df(node=assignee, scopes=scopes, assignt=True, obj=True,
                                entry=entry)
        else:  # assignee is a variable
            var_decl_df(node=assignee, scopes=scopes, assignt=True, entry=entry)

    if not identifiers:
        logging.warning('No identifier assignee found')

    for i in range(1, len(node.children)):
        scopes = data_flow(node.children[i], scopes=scopes, id_list=id_list, entry=entry)
        map_var2value(node, identifiers, operator=operator)

    return scopes


def update_expr_df(node, scopes, id_list, entry):
    """ Handles the node UpdateExpression: Element0: argument. """

    arguments = search_identifiers(node.children[0], id_list, tab=[])
    for argument in arguments:
        # Variable used, modified, used to have 2 data dependencies, one on the original variable
        # and one of the variable modified that will be used after.
        assignment_df(identifier_node=argument, scopes=scopes)
        var_decl_df(node=argument, scopes=scopes, assignt=True, entry=entry)
        assignment_df(identifier_node=argument, scopes=scopes)
        compute_update_expression(node, argument)
        display_values(var=argument, keep_none=False)  # Display values

    if not arguments:
        logging.warning('No identifier assignee found')


def identifier_update(node, scopes, id_list, entry):
    """ Adds data flow to the considered node. """

    identifiers = search_identifiers(node, id_list, rec=False, tab=[])
    # rec=False so as to not get the same Identifier multiple times by going through its family.
    for identifier in identifiers:
        if identifier.parent.name == 'CatchClause':  # As an identifier can be used as a parameter
            # Ex: catch(err) {}, err has to be defined here
            var_decl_df(node=node, scopes=scopes, entry=entry)
        else:
            # Note: pointer analysis is wrong here because of update = True stuff...
            update = False
            check_callee = identifier
            while check_callee.parent.name == 'MemberExpression':
                check_callee = check_callee.parent
            if check_callee.name == 'MemberExpression' and 'callee' in check_callee.body:
                update = True
            # update is True for CallExpr callee, e.g., arr = []; arr.X(); we want the last arr to
            # be the handler for the arr variable, and not the first one
            # issue for object using their properties in themselves, perhaps store both
            assignment_df(identifier_node=identifier, scopes=scopes, update=update)


def hoisting(node, scopes):
    """ Checks if unknown variables are in fact function names which were hoisted. """

    for scope in scopes:
        unknown_var_copy = copy.copy(scope.unknown_var)
        for unknown in unknown_var_copy:
            if node.attributes['name'] == unknown.attributes['name']:
                logging.debug('Hoisting, %s was first used, then defined', node.attributes['name'])
                node.set_data_dependency(extremity=unknown)
                scope.remove_unknown_var(unknown)


def function_scope(node, scopes, id_list):
    """ Function scope. """

    fun_expr = False
    if isinstance(node, _node.FunctionExpression):
        fun_expr = True

    retraverse = node.retraverse  # True if we are retraversing the function, False if 1st traversal

    last_scope_inx = len(scopes)
    rec = 0
    for i in range(last_scope_inx):
        for j in range(i + 1, last_scope_inx):
            # The 2 functions' scope could be separated, e.g., by a Branch_true scope
            if scopes[i].function is not None and scopes[j].function is not None:
                if scopes[i].function.id == scopes[j].function.id:
                    rec += 1  # Count the number of identical Function scopes

    if rec < LIMIT_RETRAVERSE:  # To avoid infinite recursion if function called on itself

        scopes.append(_scope.Scope('Function'))  # Added function scope
        scopes[-1].set_function(node)  # Storing entry point to the function

        for child in node.children:
            if child.body == 'id':  # Function's name
                id_list.append(child.id)
                if not fun_expr:
                    if not retraverse:
                        node.set_fun_name(child)  # Function name so that can be used in upper scope
                    var_decl_df(node=child, scopes=scopes[:-1], entry=0)
                    if not retraverse:
                        hoisting(child, scopes)  # Only for FunDecl
                else:  # Name of a FunctionExpression so that it can be used in the function's scope
                    if not retraverse:
                        node.set_fun_intern_name(child)
                    var_decl_df(node=child, scopes=scopes, entry=0)

            if child.body == 'params':  # Function's parameters
                id_list.append(child.id)
                if not retraverse:
                    node.add_fun_param(child)
                if child.name == 'Identifier':
                    # var_decl_df(node=child, scopes=scopes, entry=0)  # No, param should be defined
                    scopes[-1].add_var(child)  # Add param variable in function's scope
                else:  # Could be, e.g., an ObjectPattern
                    build_dfg_content(child, scopes=scopes, id_list=id_list, entry=0)

            else:  # Function's block
                scopes = data_flow(child, scopes=scopes, id_list=id_list, entry=0)

        let_const_scope(node, scopes)  # Limit scope when going out of the block
        scopes.pop()  # Variables declared before entering the function + function name

        if not retraverse:
            for el in node.fun_return:
                el.set_value(get_node_value(el, initial_node=node))

        try:
            if not fun_expr:
                logging.debug('The function %s defined with following parameters %s returns %s',
                              node.fun_name.attributes['name'],
                              [el.attributes['name'] for el in node.fun_params],
                              [el.value for el in node.fun_return])
            else:
                logging.debug('The FunExpr defined with following parameters %s returns %s',
                              [el.attributes['name'] for el in node.fun_params],
                              [el.value for el in node.fun_return])

        except KeyError:  # If param is not an Identifier, could be, e.g., an ObjectPattern
            if not fun_expr:
                logging.debug('The function %s defined with following parameters %s returns %s',
                              node.fun_name.attributes['name'],
                              [el.name for el in node.fun_params],
                              [el.value for el in node.fun_return])
            else:
                logging.debug('The FunExpr defined with following parameters %s returns %s',
                              [el.name for el in node.fun_params],
                              [el.value for el in node.fun_return])

    return scopes


def obj_expr_scope(node, scopes, id_list):
    """ ObjectExpression scope. """

    scopes.append(_scope.Scope('ObjectExpression'))  # Added object scope

    for prop in node.children:
        for child in prop.children:
            if child.body == 'key':
                identifiers = search_identifiers(child, id_list, tab=[])
                for param in identifiers:
                    id_list.append(param.id)
                    # var_decl_df(node=param, scopes=scopes, entry=0)  # No need to store the key??
                    hoisting(param, scopes)

            else:
                scopes = data_flow(child, scopes=scopes, id_list=id_list, entry=0)
                node.set_provenance(child)

    let_const_scope(node, scopes)  # Limit scope when going out of the block
    scopes.pop()  # Back to the initial scope when we are not in the object anymore

    return scopes


def obj_pattern_scope(node, scopes, id_list):
    """ ObjectPattern scope. """

    for prop in node.children:
        for child in prop.children:
            if child.body == 'value':  # Actual property name is somewhere here
                if not isinstance(child, _node.Identifier):
                    scopes = data_flow(child, scopes=scopes, id_list=id_list, entry=0)
                else:  # Actual property name, considered as a variable
                    id_list.append(child.id)
                    var_decl_df(node=child, scopes=scopes, entry=0)

            elif child.body == 'key':  # Key, but very local to the object, not a variable
                pass
            else:
                logging.warning('The node %s had unexpected properties %s on %s', node.name,
                                child.body, child.name)

    let_const_scope(node, scopes)  # Limit scope when going out of the block

    return scopes


def get_var_branch(node_list, scopes, id_list, entry, scope_name):
    """
        Statement scope for boolean conditions.

        -------
        Parameters:
        - node_list: list of Nodes
            Current nodes to be handled.

        -------
        Returns:
        - initial_scope, and local_scope and global_scope from the considered branch
    """

    scopes.append(_scope.Scope(scope_name))  # scopes modified for the branch
    global_scope = scopes[0].copy_scope()

    for boolean_node in node_list:
        scopes = data_flow(boolean_node, scopes=scopes, id_list=id_list, entry=entry)

    local_scope_cf = scopes.pop()  # Scope modified in a True/False branch
    global_scope_cf = scopes.pop(0)  # Global scope modified in a True/False branch
    scopes.insert(0, global_scope)  # All scopes; do not contain variables declared in a True/False
    # branch, but may contain variables previously declared but modified in a True/False branch

    return scopes, local_scope_cf, global_scope_cf


def merge_var_boolean_cf(current_scope, scope_true, scope_false):
    """
        Merges in scope_true the variables declared in the true and false scope.

        -------
        Parameters:
        - current_scope: Scope
            Stores the variables declared before entering any conditions and where they should be
            referred to.
        - scope_true: Scope
            Stores the variables currently declared if cond = true and where they should be
            referred to.
        - scope_false: Scope
            Stores the variables currently declared if cond = false and where they should be
            referred to.

        -------
        Returns:
        - scope_true
    """

    # Merges variables declared/modified in a true/false scope in the true scope
    for node_false in scope_false.var_list:
        if not any(node_false.attributes['name'] == node_true.attributes['name']
                   for node_true in scope_true.var_list):
            logging.debug('The variable %s was added to the list', node_false.attributes['name'])
            scope_true.add_var(node_false)

        for node_true in scope_true.var_list:
            if node_false.attributes['name'] == node_true.attributes['name']\
                    and node_false.id != node_true.id:  # The var was modified in >=1 branch
                var_index = scope_true.get_pos_identifier(node_true)
                if any(node_true.id == node.id for node in current_scope.var_list):
                    logging.debug('The variable %s has been modified in the branch False',
                                  node_false.attributes['name'])
                    scope_true.update_var(var_index, node_false)
                elif any(node_false.id == node.id for node in current_scope.var_list):
                    logging.debug('The variable %s has been modified in the branch True',
                                  node_true.attributes['name'])
                    # Already handled, as we work on var_list_true
                else:  # Both were modified, we refer to the nearest common statement
                    logging.debug('The variable %s has been modified in the branches True and '
                                  'False', node_false.attributes['name'])
                    scope_true.update_var_if2(var_index, [node_true, node_false])

    return scope_true  # Merged variables declared in the True/False scope


def handle_several_branches(todo_true, todo_false, scopes, id_list, entry):
    """
        Statement scope.

        -------
        Parameters:
        - todo_true: list of Node
            From the True branch.
        - todo_false: list of Node
            From the False branch.
    """

    if todo_true or todo_false:
        scopes, local_scope_true, global_scope_true = get_var_branch(todo_true, scopes=scopes,
                                                                     id_list=id_list, entry=entry,
                                                                     scope_name='Branch_true')

        scopes, local_scope_false, global_scope_false = get_var_branch(todo_false, scopes=scopes,
                                                                       id_list=id_list, entry=entry,
                                                                       scope_name='Branch_false')

        if not global_scope_true.is_equal(global_scope_false):
            logging.debug('True and False global scopes are different')
            global_scope = merge_var_boolean_cf(scopes[0], global_scope_true, global_scope_false)
            scopes.pop(0)
            scopes.insert(0, global_scope)

        if not local_scope_true.is_equal(local_scope_false):
            logging.debug('True and False local scopes are different')
            current_scope = scopes[-1]

            # Merges variables declared in the True/False previous scopes
            cond_scope = merge_var_boolean_cf(current_scope, local_scope_true, local_scope_false)

            # Adds variables previously declared in the True/False scope in the current scope
            for cond_node in cond_scope.var_list:
                if not any(cond_node.attributes['name'] == current_node.attributes['name']
                           for current_node in current_scope.var_list):
                    logging.debug('The variable %s was added to the current variables\' list',
                                  cond_node.attributes['name'])
                    current_scope.add_var(cond_node)

            # Same for variables declared in both branches
            for cond_node_list in cond_scope.var_if2_list:
                if isinstance(cond_node_list, list):
                    current_scope.var_if2_list.extend(cond_node_list)

    # Finally scopes contains all variables defined in the true + false branches
    return scopes


def statement_scope(node, scopes, id_list, entry):
    """ Statement scope. """

    todo_true = []
    todo_false = []
    if_test = None

    # Statements that do belong after one another
    for child_statement_dep in node.statement_dep_children:
        child_statement = child_statement_dep.extremity
        logging.debug('The node %s has a statement dependency', child_statement.name)
        scopes = data_flow(child_statement, scopes=scopes, id_list=id_list, entry=entry)
        if child_statement.parent.name in ('IfStatement', 'ConditionalExpression'):
            # Checking if we can statically predict the outcome of the if test
            if_test = get_node_computed_value(child_statement, initial_node=node)
            if not isinstance(if_test, bool):  # Could be neither bool nor None
                if_test = None  # So that must be either True, False or None
            logging.debug('The If test is %s', if_test)

    for child_cf_dep in node.control_dep_children:  # Control flow statements
        child_cf = child_cf_dep.extremity
        if isinstance(child_cf_dep.label, bool):  # Several branches according to the cond
            logging.debug('The node %s has a boolean CF dependency', child_cf.name)
            if child_cf_dep.label and (if_test or if_test is None):
                todo_true.append(child_cf)  # SwitchCase: several True possible
            elif not child_cf_dep.label and (not if_test or if_test is None):
                todo_false.append(child_cf)

        else:  # Epsilon statements
            logging.debug('The node %s has an epsilon CF dependency', child_cf.name)
            scopes = data_flow(child_cf, scopes=scopes, id_list=id_list, entry=entry)

    # Separate variables if separate true/false branches
    scopes = handle_several_branches(todo_true=todo_true, todo_false=todo_false, scopes=scopes,
                                     id_list=id_list, entry=entry)

    let_const_scope(node, scopes)  # Limit scope when going out of the block

    return scopes


def let_const_scope(node, scopes):
    """ Pops scope specific to variables defined with let or const. """

    if len(scopes) > 1 and scopes[-1].name == "let_const" + str(node.id):
        scopes.pop()
    elif len(scopes) > 2 and "Branch" in scopes[-1].name\
            and scopes[-2].name == "let_const" + str(node.id):  # As special scope for True branches
        scopes.pop(-2)


def go_out_bloc(scopes, already_in_bloc):
    """ Go out of block statement. """

    if not already_in_bloc:  # If we already were in a bloc, we do not want to go out to early
        for scope in scopes[::-1]:  # In reverse order to check the last scope first
            if scope.bloc:
                scope.set_in_bloc(False)
                break


def handle_arg_tagged_template_expr(node, callee, saved_params):
    """
        Handles the arguments of a TaggedTemplateExpression node.

        -------
        Parameter:
        - callee: Node
            FunctionDeclaration or (Arrow)FunctionExpression.
        - saved_params: list
            If a fun is called inside itself with != params, need to store outer ones.
    """

    template_literal = node.children[1]
    template_element = []  # Seems that TemplateElement = similar to Literal and in front
    template_element_node = []  # Stores the TemplateElement nodes
    standard_param = []

    for child in template_literal.children:
        if child.name == 'TemplateElement':
            template_element_node.append(child)
            template_element.append(get_node_computed_value(child, initial_node=node))
        else:
            standard_param.append(child)
    params = [template_element]
    params.extend(standard_param)  # Params are like that: [all TemplateElement], rest

    for arg in range(1, len(callee.fun_params)):
        if arg <= len(standard_param):
            # Check if function call has less parameters than function definition
            param = get_node_computed_value(standard_param[arg - 1], initial_node=node)
            handle_function_params(callee.fun_params[arg], standard_param[arg - 1])
        else:
            param = None
        saved_params.append(get_node_computed_value(callee.fun_params[arg], initial_node=node))
        callee.fun_params[arg].set_value(param)  # Set value of function param from second one
    saved_params.append(get_node_computed_value(callee.fun_params[0], initial_node=node))
    callee.fun_params[0].set_value(template_element)  # Set value of first function param

    for param in template_element_node:  # Links parameters for the TemplateElement nodes
        handle_function_params(callee.fun_params[0], param)


def handle_function_params(def_param, call_param):
    """ Links the function parameter at the definition site with the value at the call site. """

    # Function parameter at the definition site depends on the value at the call site
    def_param.set_provenance(call_param)
    # _node.set_provenance_rec(def_param, call_param)

    # Defines the fun_param_X dependency, if it does not already exist to avoid resetting it to []
    if not hasattr(def_param, 'fun_param_children'):
        setattr(def_param, 'fun_param_children', [])

    if not hasattr(call_param, 'fun_param_parents'):
        setattr(call_param, 'fun_param_parents', [])

    # Links the function parameter definition site to the call site with a fun_param dependency
    if call_param.id not in [el.id for el in def_param.fun_param_children]:  # Avoids duplicates
        def_param.fun_param_children.append(call_param)
        call_param.fun_param_parents.append(def_param)


def handle_call_expr(node, scopes, callee, fun_expr=False, tagged_template=False):
    """
        Handling CallExpression nodes. Can be:
            - 1. FunDecl/Expr... CallExpr -> leveraging the data_dep for the mapping process;
            - 2. CallExpr... FunDecl -> but hoisted FunDecl to top, so back to case 1.;
            - 3. CallExpr(FunExpr) -> case fun_expr=True;
            - 4. nothing to do with a FunDecl/Expr -> not handled here because would not be called.

        -------
        Parameters:
        - callee: Node
            FunctionDeclaration or (Arrow)FunctionExpression.
        - fun_expr: bool
            True if CallExpr(FunExpr), otherwise False.
    """

    function_def = callee  # Handler to the function
    if not fun_expr:  # Case CallExpr and not CallExpr(FunExpr)
        function_def.call_function()  # It was called
    saved_params = []  # If a fun is called inside itself with != params, need to store outer ones

    # Arguments handling
    if tagged_template:
        handle_arg_tagged_template_expr(node, callee, saved_params)
    else:
        for arg, _ in enumerate(function_def.fun_params):
            if (1 + arg) < len(node.children):
                # Check if function call has less parameters than function definition
                saved_params.append(get_node_computed_value(function_def.fun_params[arg],
                                                            initial_node=node))
                param = get_node_computed_value(node.children[1 + arg], initial_node=node)
                handle_function_params(callee.fun_params[arg], node.children[1 + arg])
            else:
                param = None
            if isinstance(function_def.fun_params[arg], _node.Value):
                function_def.fun_params[arg].set_value(param)  # Set value of function param

    if function_def.fun_name is not None:  # FunDecl or var where FunExpr stored
        function_name = function_def.fun_name.attributes['name']
    else:  # FunExpr case, name used to reference the function inside itself
        if function_def.fun_intern_name is not None:
            function_name = function_def.fun_intern_name.attributes['name']
        else:
            function_name = 'Anonymous'

    logging.debug('The function %s was called with following parameters:',
                  function_name)
    for param in function_def.fun_params:
        try:
            logging.debug('\t- %s = %s', param.attributes['name'], param.value)
        except KeyError:  # If param is not an Identifier, could be, e.g., a CallExpression
            logging.debug('\t- %s = %s', param.name, param.value)

    # Traverse function again
    function_def.set_retraverse()  # Sets retraverse property to True
    scopes = function_scope(node=function_def, scopes=scopes, id_list=[])

    return_value = None
    if function_def.fun_return:
        return_value = get_node_value(function_def.fun_return[-1], initial_node=node)
        # Last in, only one out
        # Beware, NOT get_node_computed_value because we want to compute the value again: the
        # previously stored value is the returned value hard coded in the function def before exec
    logging.debug('The function %s returns %s', function_name, return_value)
    node.set_value(return_value)

    if len(function_def.fun_params) == len(saved_params):
        for arg, _ in enumerate(function_def.fun_params):
            function_def.fun_params[arg].set_value(saved_params[arg])  # Set old param value

    return scopes


def handle_foreach(node):
    """ Sets provenance for forEach construct. """

    if len(node.children) > 1 and node.children[0].body in ('callee', 'tag'):
        # arr.forEach(callback);
        callee = node.children[0]
        call_expr_value = get_node_computed_value(node)
        if call_expr_value is not None and '.forEach(' in call_expr_value:
            identifiers = []  # To store identifiers on which forEach is called (e.g., arr)
            for child in callee.children:
                search_identifiers(child, id_list=[], tab=identifiers)
            callback = node.children[1]  # callback, should be a FunctionExpression
            if isinstance(callback, _node.FunctionExpression):
                for param in callback.children:
                    if 'params' in param.body:
                        for arr in identifiers:
                            if isinstance(param, _node.Value):
                                param.set_provenance(arr)  # callback params depend on arr object


def handle_push(node):
    """ Sets provenance for push construct. """

    if len(node.children) > 1 and node.children[0].body in ('callee', 'tag'):
        # arr.push(elt1, ..., eltN);
        callee = node.children[0]
        call_expr_value = get_node_computed_value(node)
        if call_expr_value is not None and '.push(' in call_expr_value:
            identifiers = []  # To store identifiers on which push is called (e.g., arr)
            for child in callee.children:
                search_identifiers(child, id_list=[], tab=identifiers)
            elements = node.children[1:]  # elements to be pushed
            for element in elements:
                for arr in identifiers:
                    if isinstance(arr, _node.Value):
                        arr.set_provenance_rec(element)  # arr object depends on elements


def build_dfg_content(child, scopes, id_list, entry):
    """ Data dependency for a given node whatever it is. """

    if child.name == 'VariableDeclaration':  # VariableDeclaration data dependencies

        logging.debug('The node %s is a variable declaration', child.name)

        let_const = False
        if child.attributes['kind'] != 'var' and scopes[-1].bloc:  # let or const in a bloc
            let_const = True
            let_const_scope_name = 'let_const' + str(child.parent.id)
            if scopes[-1].name != let_const_scope_name:  # New block scope if not already defined
                scopes.append(_scope.Scope(let_const_scope_name))

        for grandchild in child.children:
            scopes = var_declaration_df(grandchild, scopes=scopes, id_list=id_list, entry=entry,
                                        let_const=let_const)

    ################################################################################################

    elif child.name == 'AssignmentExpression':  # AssignmentExpression data dependencies

        logging.debug('The node %s is an assignment expression', child.name)
        scopes = assignment_expr_df(child, scopes=scopes, id_list=id_list, entry=entry)

    ################################################################################################

    elif child.name in _node.CALL_EXPR:

        scopes = df_scoping(child, scopes=scopes, id_list=id_list)[1]
        callee = child.children[0]

        tagged_template = bool(child.name == 'TaggedTemplateExpression')

        if isinstance(callee, _node.FunctionExpression):  # Case CallExpr(FunExpr)
            scopes = handle_call_expr(child, scopes=scopes, callee=callee,
                                      tagged_template=tagged_template, fun_expr=True)

        elif isinstance(get_node_computed_value(callee, initial_node=child),
                        _node.FunctionExpression):
            # Case a = {}; a['b'] = function(){}; a['b'](); --> As a['b'] resolves to a FunExpr
            scopes = handle_call_expr(child, scopes=scopes,
                                      callee=get_node_computed_value(callee, initial_node=child),
                                      tagged_template=tagged_template, fun_expr=True)

        else:
            identifiers = search_identifiers(callee, id_list=[], tab=[])
            for identifier in identifiers:
                for data_dep in identifier.data_dep_parents:
                    if data_dep.extremity.fun is not None:  # Calling a fun that was defined before
                        callee = data_dep.extremity.fun
                        scopes = handle_call_expr(child, scopes=scopes, callee=callee,
                                                  tagged_template=tagged_template)
                        break

            handle_foreach(node=child)  # Sets provenance for forEach constructs
            handle_push(node=child)  # Sets provenance for push constructs

        display_values(var=child, keep_none=False, recompute=False)  # Display values

    ################################################################################################

    elif child.name == 'UpdateExpression':  # UpdateExpression data dependencies

        logging.debug('The node %s is an update expression', child.name)
        update_expr_df(child, scopes=scopes, id_list=id_list, entry=entry)

    ################################################################################################

    elif child.name == 'FunctionDeclaration' or isinstance(child, _node.FunctionExpression):
        # Functions data dependencies

        logging.debug('The node %s is a function', child.name)
        scopes = function_scope(node=child, scopes=scopes, id_list=id_list)
        # child.scopes = scopes  # Would not work because would lose current scoping info

    ################################################################################################

    elif child.name == 'ReturnStatement':  # ReturnStatement added to the corresponding fun + DD

        logging.debug('The node %s is a return statement', child.name)
        already_in_bloc = scopes[-1].bloc
        scopes[-1].set_in_bloc(True)  # We are in a block statement, relevant for let/const

        for scope in scopes[::-1]:  # In reverse order to check the last scope first
            if scope.name == 'Function':
                fun = scope.function  # Looking for the (Arrow)FunctionExpression/Declaration node
                if not isinstance(fun, _node.FunctionDeclaration) \
                        and not isinstance(fun, _node.FunctionExpression):
                    logging.error('Expected a Function, got a %s node', fun.name)
                    break

                fun.add_fun_return(child)  # Sets value of ReturnStatement

                break

        scopes = df_scoping(child, scopes=scopes, id_list=id_list)[1]
        go_out_bloc(scopes, already_in_bloc)  # We are not in the block statement anymore

    ################################################################################################

    elif child.name == 'ForStatement':  # ForStatement: init, test, update, body (Statement)

        logging.debug('The node %s is a for statement', child.name)
        already_in_bloc = scopes[-1].bloc
        scopes[-1].set_in_bloc(True)  # We are in a block statement, relevant for let/const

        if len(child.children) in (3, 4):
            scopes = data_flow(child.children[0], scopes, id_list, entry)  # init
            scopes = data_flow(child.children[1], scopes, id_list, entry)  # test
            identifiers = []
            search_identifiers(child.children[0], [], identifiers)
            loop = 0
            test = get_node_computed_value(child.children[1], initial_node=child)
            if test is not True:  # Could be None, or perhaps str, int whatever
                test = True  # So that go at least one time in the loop
            while get_node_computed_value(child.children[1], initial_node=child) or test:
                # while test do:
                test = False
                loop += 1
                if loop <= LIMIT_LOOP:  # To avoid infinite loops
                    if len(child.children) == 4:
                        scopes = data_flow(child.children[3], scopes, id_list, entry)  # body
                    scopes = data_flow(child.children[2], scopes, id_list, entry)  # update / body
                    for identifier in identifiers:
                        if len(identifier.data_dep_children) >= 3:
                            identifier.data_dep_children[0].extremity.set_value(
                                identifier.data_dep_children[2].extremity)  # updates test value
                else:
                    break  # To go out of the while!
            let_const_scope(child, scopes)  # Limit scope when going out of the block

        else:
            logging.warning('Expected a ForStatement with 3 or 4 children, got only %s',
                            len(child.children))
            scopes = statement_scope(node=child, scopes=scopes, id_list=id_list, entry=entry)

        go_out_bloc(scopes, already_in_bloc)  # We are not in the block statement anymore

    ################################################################################################

    elif child.name in ('ForOfStatement', 'ForInStatement'):  # ForOf/InStatement: left, right, body

        logging.debug('The node %s is a for statement', child.name)
        already_in_bloc = scopes[-1].bloc
        scopes[-1].set_in_bloc(True)  # We are in a block statement, relevant for let/const

        if len(child.children) == 3:
            scopes = data_flow(child.children[0], scopes, id_list, entry)  # left = var
            scopes = data_flow(child.children[1], scopes, id_list, entry)  # right = array
            identifiers = []
            search_identifiers(child.children[0], [], identifiers)
            # Reference to the ArrayExpr
            obj_value = get_node_computed_value(child.children[1], initial_node=child)
            if len(identifiers) > 1:
                logging.warning('Got %s variables declared in a %s', len(identifiers), child.name)
            for identifier in identifiers:
                if isinstance(obj_value, _node.Node):  # Otherwise cannot iterate over Array
                    for obj_value_el in obj_value.children:  # Iterate over the ArrayExpr elements
                        if obj_value_el.name == 'Property':
                            prop_value = get_node_computed_value(obj_value_el.children[0],
                                                                 initial_node=child)  # kvalue
                        else:
                            prop_value = get_node_computed_value(obj_value_el,
                                                                 initial_node=child)  # k value
                        identifier.set_value(prop_value)
                        # Thanks to DD from identifier, will iterate over k value
                        scopes = data_flow(child.children[2], scopes, id_list, entry)  # body

            if not identifiers or identifiers and\
                    (not isinstance(obj_value, _node.Node) or not obj_value.children):
                # So that body still handled
                scopes = data_flow(child.children[2], scopes, id_list, entry)  # body

            let_const_scope(child, scopes)  # Limit scope when going out of the block

        else:
            logging.warning('Expected a ForStatement with 3 children, got only %s',
                            len(child.children))
            scopes = statement_scope(node=child, scopes=scopes, id_list=id_list, entry=entry)

        go_out_bloc(scopes, already_in_bloc)  # We are not in the block statement anymore

    ################################################################################################

    elif isinstance(child, _node.Statement) or child.name == 'ConditionalExpression':
        # Statement (statement, epsilon, boolean) data dep and ConditionalExpr = same as IfStatement

        logging.debug('The node %s is a statement', child.name)
        already_in_bloc = scopes[-1].bloc
        scopes[-1].set_in_bloc(True)  # We are in a block statement, relevant for let/const

        scopes = statement_scope(node=child, scopes=scopes, id_list=id_list, entry=entry)
        go_out_bloc(scopes, already_in_bloc)  # We are not in the block statement anymore

    ################################################################################################

    elif child.name == 'ObjectExpression':  # Only consider the object name, no properties

        logging.debug('The node %s is an object expression', child.name)
        scopes = obj_expr_scope(child, scopes=scopes, id_list=id_list)

    ################################################################################################

    elif child.name == 'ObjectPattern':  # Only consider the object name, not the key or properties

        logging.debug('The node %s is an object pattern', child.name)
        scopes = obj_pattern_scope(child, scopes=scopes, id_list=id_list)

    ################################################################################################

    elif child.name == 'Identifier':  # Identifier data dependencies

        if child.id not in id_list:
            logging.debug('The variable %s has not been handled yet', child.attributes['name'])
            identifier_update(child, scopes=scopes, id_list=id_list, entry=entry)
        else:
            logging.debug('The variable %s has already been handled', child.attributes['name'])

    ################################################################################################

    else:
        scopes = df_scoping(child, scopes=scopes, id_list=id_list)[1]

    ################################################################################################

    # for scope in scopes:
        # display_temp('> ' + scope.name, [scope])
    # display_temp('> Local: ', scopes[1:])
    # display_temp('> Global: ', scopes[:1])

    return scopes


def data_flow(child, scopes, id_list, entry):
    """ Cf build_dfg_content. Added try/catch to see code snippets leading to problems and
    performing the analysis to the end. """

    # scopes = build_dfg_content(child, scopes, id_list, entry)

    try:
        scopes = build_dfg_content(child, scopes, id_list, entry)

    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in build_pdg

    except Exception as e:
        if PDG_EXCEPT:  # Prints the exceptions encountered while building the PDG
            logging.exception(e)
            logging.exception('Something went wrong with the following code snippet, %s', '')
            my_json = 'test.json'
            save_json(child, my_json)  # Won't work with multiprocessing
            print(get_code(my_json))
        else:
            pass

    return scopes


def df_scoping(cfg_nodes, scopes, id_list, entry=0):
    """
        Data dependency for the CFG.

        -------
        Parameters:
        - cfg_nodes: Node
            Output of produce_cfg(ast_to_ast_nodes(<ast>, ast_nodes=Node('Program'))).

        -------
        Returns:
        - Node
            With data flow dependencies added.
    """

    for child in cfg_nodes.children:
        scopes = data_flow(child, scopes=scopes, id_list=id_list, entry=entry)
    return [cfg_nodes, scopes]


def display_temp(title, scopes, print_var_value=True):
    """ Displays known variable names. """

    print(title)
    my_json = 'test.json'
    for scope in scopes:
        print('> ' + scope.name)
        for el in scope.var_list:
            variable = get_node_value(el)
            if not print_var_value:
                print(variable)
                # print(el.attributes['name'])
            else:
                value_node = el.value
                if el.update_value:  # To compute the value of NEW variables only
                    value = get_node_computed_value(el, keep_none=True)
                else:  # The value of old variables should not change with code occurring after them
                    value = value_node

                print(variable + ' = ' + str(value))  # Get variable value
                if isinstance(value, _node.Node):
                    print(value.name, value.attributes, value.id)
                el.set_update_value(False)

                # Get code
                if isinstance(value_node, _node.Node):
                    save_json(get_nearest_statement(value_node, fun_expr=True), my_json)
                    code = get_code(my_json)
                    print('\t' + code)
                else:  # Case "we don't know the value" or Literal we computed i.e. no Node obj
                    if el.code is not None:
                        save_json(el.code, my_json)
                        code = get_code(my_json)
                        print('\t' + code)


def display_temp2(title, scopes):
    """ Displays var_if2_list content. """

    print(title)
    for scope in scopes:
        print('> ' + scope.name)
        if scope.var_if2_list is not None:
            for el in scope.var_if2_list:
                print(el)
