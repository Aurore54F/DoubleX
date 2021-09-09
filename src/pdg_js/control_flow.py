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
    Adds control flow to the AST.
"""

# Note: slightly improved from HideNoSeek


from . import node as _node


def link_expression(node, node_parent):
    """ Non-statement node. """
    if node.is_comment():
        pass
    else:
        node_parent.set_statement_dependency(extremity=node)
    return node


def epsilon_statement_cf(node):
    """ Non-conditional statements. """
    for child in node.children:
        if isinstance(child, _node.Statement):
            node.set_control_dependency(extremity=child, label='e')
        else:
            link_expression(node=child, node_parent=node)


def do_while_cf(node):
    """ DoWhileStatement. """
    # Element 0: body (Statement)
    # Element 1: test (Expression)
    node.set_control_dependency(extremity=node.children[0], label=True)
    link_expression(node=node.children[1], node_parent=node)


def for_cf(node):
    """ ForStatement. """
    # Element 0: init
    # Element 1: test (Expression)
    # Element 2: update (Expression)
    # Element 3: body (Statement)
    """ ForOfStatement. """
    # Element 0: left
    # Element 1: right
    # Element 2: body (Statement)
    i = 0
    for child in node.children:
        if child.body != 'body':
            link_expression(node=child, node_parent=node)
        elif not child.is_comment():
            node.set_control_dependency(extremity=child, label=True)
        i += 1


def if_cf(node):
    """ IfStatement. """
    # Element 0: test (Expression)
    # Element 1: consequent (Statement)
    # Element 2: alternate (Statement)
    link_expression(node=node.children[0], node_parent=node)
    if len(node.children) > 1:  # Not sure why, but can happen...
        node.set_control_dependency(extremity=node.children[1], label=True)
        if len(node.children) > 2:
            if node.children[2].is_comment():
                pass
            else:
                node.set_control_dependency(extremity=node.children[2], label=False)


def try_cf(node):
    """ TryStatement. """
    # Element 0: block (Statement)
    # Element 1: handler (Statement) / finalizer (Statement)
    # Element 2: finalizer (Statement)
    node.set_control_dependency(extremity=node.children[0], label=True)
    if node.children[1].body == 'handler':
        node.set_control_dependency(extremity=node.children[1], label=False)
    else:  # finalizer
        node.set_control_dependency(extremity=node.children[1], label='e')
    if len(node.children) > 2:
        if node.children[2].body == 'finalizer':
            node.set_control_dependency(extremity=node.children[2], label='e')


def while_cf(node):
    """ WhileStatement. """
    # Element 0: test (Expression)
    # Element 1: body (Statement)
    link_expression(node=node.children[0], node_parent=node)
    node.set_control_dependency(extremity=node.children[1], label=True)


def switch_cf(node):
    """ SwitchStatement. """
    # Element 0: discriminant
    # Element 1: cases (SwitchCase)

    switch_cases = node.children
    link_expression(node=switch_cases[0], node_parent=node)
    if len(switch_cases) > 1:
        # SwitchStatement -> True -> SwitchCase for first one
        node.set_control_dependency(extremity=switch_cases[1], label='e')
        switch_case_cf(switch_cases[1])
        for i in range(2, len(switch_cases)):
            if switch_cases[i].is_comment():
                pass
            else:
                # SwitchCase -> False -> SwitchCase for the other ones
                switch_cases[i - 1].set_control_dependency(extremity=switch_cases[i], label=False)
                if i != len(switch_cases) - 1:
                    switch_case_cf(switch_cases[i])
                else:  # Because the last switch is executed per default, i.e. without condition 1st
                    switch_case_cf(switch_cases[i], last=True)
    # Otherwise, we could just have a switch(something) {}


def switch_case_cf(node, last=False):
    """ SwitchCase. """
    # Element 0: test
    # Element 1: consequent (Statement)
    nb_child = len(node.children)
    if nb_child > 1:
        if not last:  # As all switches but the last have to respect a condition to enter the branch
            link_expression(node=node.children[0], node_parent=node)
            j = 1
        else:
            j = 0
        for i in range(j, nb_child):
            if node.children[i].is_comment():
                pass
            else:
                node.set_control_dependency(extremity=node.children[i], label=True)
    elif nb_child == 1:
        node.set_control_dependency(extremity=node.children[0], label=True)


def conditional_statement_cf(node):
    """ For the conditional nodes. """
    if node.name == 'DoWhileStatement':
        do_while_cf(node)
    elif node.name == 'ForStatement' or node.name == 'ForOfStatement'\
            or node.name == 'ForInStatement':
        for_cf(node)
    elif node.name == 'IfStatement' or node.name == 'ConditionalExpression':
        if_cf(node)
    elif node.name == 'WhileStatement':
        while_cf(node)
    elif node.name == 'TryStatement':
        try_cf(node)
    elif node.name == 'SwitchStatement':
        switch_cf(node)
    elif node.name == 'SwitchCase':
        pass  # Already handled in SwitchStatement


def control_flow(ast_nodes):
    """
        Enhance the AST by adding statement and control dependencies to each Node.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).

        -------
        Returns:
        - Node
            With statement and control dependencies added.
    """

    for child in ast_nodes.children:
        if child.name in _node.EPSILON or child.name in _node.UNSTRUCTURED:
            epsilon_statement_cf(child)
        elif child.name in _node.CONDITIONAL:
            conditional_statement_cf(child)
        else:
            for grandchild in child.children:
                link_expression(node=grandchild, node_parent=child)
        control_flow(child)
    return ast_nodes
