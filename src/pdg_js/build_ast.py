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
    From JS source code to an Esprima AST exported in JSON.
    From JSON to ExtendedAst and Node objects.
    From Node objects to JSON.
    From JSON to JS source code using Escodegen.
"""

# Note: improved from HideNoSeek (bugs correction + semantic information to the nodes)


import logging
import json
import os
import subprocess

from . import node as _node
from . import extended_ast as _extended_ast

SRC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__)))


def get_extended_ast(input_file, json_path, remove_json=True):
    """
        JavaScript AST production.

        -------
        Parameters:
        - input_file: str
            Path of the file to produce an AST from.
        - json_path: str
            Path of the JSON file to temporary store the AST in.
        - remove_json: bool
            Indicates whether to remove or not the JSON file containing the Esprima AST.
            Default: True.

        -------
        Returns:
        - ExtendedAst
            The extended AST (i.e., contains type, filename, body, sourceType, range, comments,
            tokens, and possibly leadingComments) of input_file.
        - None if an error occurred.
    """

    try:
        produce_ast = subprocess.run(['node', os.path.join(SRC_PATH, 'parser.js'),
                                      input_file, json_path],
                                     stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        logging.critical('Esprima parsing error for %s', input_file)
        return None

    if produce_ast.returncode == 0:

        with open(json_path) as json_data:
            esprima_ast = json.loads(json_data.read())
        if remove_json:
            os.remove(json_path)

        extended_ast = _extended_ast.ExtendedAst()
        extended_ast.filename = input_file
        extended_ast.set_type(esprima_ast['type'])
        extended_ast.set_body(esprima_ast['body'])
        extended_ast.set_source_type(esprima_ast['sourceType'])
        extended_ast.set_range(esprima_ast['range'])
        extended_ast.set_tokens(esprima_ast['tokens'])
        extended_ast.set_comments(esprima_ast['comments'])
        if 'leadingComments' in esprima_ast:
            extended_ast.set_leading_comments(esprima_ast['leadingComments'])

        return extended_ast

    logging.critical('Esprima could not produce an AST for %s', input_file)
    return None


def indent(depth_dict):
    """ Indentation size. """
    return '\t' * depth_dict


def brace(key):
    """ Write a word between cases. """
    return '|<' + key + '>'


def print_dict(depth_dict, key, value, max_depth, delete_leaf):
    """ Print the content of a dict with specific indentation and braces for the keys. """
    if depth_dict <= max_depth:
        print('%s%s' % (indent(depth_dict), brace(key)))
        beautiful_print_ast(value, depth=depth_dict + 1, max_depth=max_depth,
                            delete_leaf=delete_leaf)


def print_value(depth_dict, key, value, max_depth, delete_leaf):
    """ Print a dict value with respect to the indentation. """
    if depth_dict <= max_depth:
        if all(dont_consider != key for dont_consider in delete_leaf):
            print(indent(depth_dict) + "| %s = %s" % (key, value))


def beautiful_print_ast(ast, delete_leaf, depth=0, max_depth=2 ** 63):
    """
        Walking through an AST and printing it beautifully

        -------
        Parameters:
        - ast: dict
            Contains an Esprima AST of a JS file, i.e., get_extended_ast(<input_file>, <json_path>)
            output or get_extended_ast(<input_file>, <json_path>).get_ast() output.
        - depth: int
            Initial depth of the tree. Default: 0.
        - max_depth: int
            Indicates the depth up to which the AST is printed. Default: 2**63.
        - delete_leaf: list
            Contains the leaf that should not be printed (e.g. 'range'). Default: [''],
            beware it is mutable.
    """

    for k, v in ast.items():  # Because need k everywhere
        if isinstance(v, dict):
            print_dict(depth, k, v, max_depth, delete_leaf)
        elif isinstance(v, list):
            if not v:
                print_value(depth, k, v, max_depth, delete_leaf)
            for el in v:
                if isinstance(el, dict):
                    print_dict(depth, k, el, max_depth, delete_leaf)
                else:
                    print_value(depth, k, el, max_depth, delete_leaf)
        else:
            print_value(depth, k, v, max_depth, delete_leaf)


def create_node(dico, node_body, parent_node, cond=False, filename=''):
    """ Node creation. """

    if dico is None:  # Not a Node, but needed a construct to store, e.g., [, a] = array
        node = _node.Node(name='None', parent=parent_node)
        parent_node.set_child(node)
        node.set_body(node_body)
        if cond:
            node.set_body_list(True)
        node.filename = filename

    elif 'type' in dico:
        if dico['type'] == 'FunctionDeclaration':
            node = _node.FunctionDeclaration(name=dico['type'], parent=parent_node)
        elif dico['type'] == 'FunctionExpression' or dico['type'] == 'ArrowFunctionExpression':
            node = _node.FunctionExpression(name=dico['type'], parent=parent_node)
        elif dico['type'] == 'ReturnStatement':
            node = _node.ReturnStatement(name=dico['type'], parent=parent_node)
        elif dico['type'] in _node.STATEMENTS:
            node = _node.Statement(name=dico['type'], parent=parent_node)
        elif dico['type'] in _node.VALUE_EXPR:
            node = _node.ValueExpr(name=dico['type'], parent=parent_node)
        elif dico['type'] == 'Identifier':
            node = _node.Identifier(name=dico['type'], parent=parent_node)
        else:
            node = _node.Node(name=dico['type'], parent=parent_node)

        if not node.is_comment():  # Otherwise comments are children and it is getting messy!
            parent_node.set_child(node)
        node.set_body(node_body)
        if cond:
            node.set_body_list(True)  # Some attributes are stored in a list even when they
            # are alone. If we do not respect the initial syntax, Escodegen cannot built the
            # JS code back.
        node.filename = filename
        ast_to_ast_nodes(dico, node)


def ast_to_ast_nodes(ast, ast_nodes=_node.Node('Program')):
    """
        Convert an AST to Node objects.

        -------
        Parameters:
        - ast: dict
            Output of get_extended_ast(<input_file>, <json_path>).get_ast().
        - ast_nodes: Node
            Current Node to be built. Default: ast_nodes=Node('Program'). Beware, always call the
            function indicating the default argument, otherwise the last value will be used
            (because the default parameter is mutable).

        -------
        Returns:
        - Node
            The AST in format Node object.
    """

    if 'filename' in ast:
        filename = ast['filename']
        ast_nodes.set_attribute('filename', filename)
    else:
        filename = ''

    for k in ast:
        if k == 'filename' or k == 'loc' or k == 'range' or k == 'value' \
                or (k != 'type' and not isinstance(ast[k], list)
                    and not isinstance(ast[k], dict)) or k == 'regex':
            ast_nodes.set_attribute(k, ast[k])  # range is a list but stored as attributes
        if isinstance(ast[k], dict):
            if k == 'range':  # Case leadingComments as range: {0: begin, 1: end}
                ast_nodes.set_attribute(k, ast[k])
            else:
                create_node(dico=ast[k], node_body=k, parent_node=ast_nodes, filename=filename)
        elif isinstance(ast[k], list):
            if not ast[k]:  # Case with empty list, e.g. params: []
                ast_nodes.set_attribute(k, ast[k])
            for el in ast[k]:
                if isinstance(el, dict):
                    create_node(dico=el, node_body=k, parent_node=ast_nodes, cond=True,
                                filename=filename)
                elif el is None:  # Case [None, {stuff about a}] for [, a] = array
                    create_node(dico=el, node_body=k, parent_node=ast_nodes, cond=True,
                                filename=filename)
    return ast_nodes


def print_ast_nodes(ast_nodes):
    """
        Print the Nodes of ast_nodes with their properties.
        Debug function.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).
    """

    for child in ast_nodes.children:
        print('Parent: ' + child.parent.name)
        print('Child: ' + child.name)
        print('Id: ' + str(child.id))
        print('Attributes:')
        print(child.attributes)
        print('Body: ' + str(child.body))
        print('Body_list: ' + str(child.body_list))
        print('Is-leaf: ' + str(child.is_leaf()))
        print('-----------------------')
        print_ast_nodes(child)


def build_json(ast_nodes, dico):
    """
        Convert an AST format Node objects to JSON format.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).
        - dico: dict
            Current dict to be built.

        -------
        Returns:
        - dict
            The AST in format JSON.
    """

    if ast_nodes.name != 'None':  # Nothing interesting in the None Node
        dico['type'] = ast_nodes.name
    if len(ast_nodes.children) >= 1:
        for child in ast_nodes.children:
            dico2 = {}
            if child.body_list:
                if child.body not in dico:
                    dico[child.body] = []  # Some attributes just have to be stored in a list.
                build_json(child, dico2)
                if not dico2:  # Case [, a] = array -> [None, {stuff about a}] (None and not {})
                    dico2 = None  # Not sure if it could not be legitimate sometimes
                    logging.warning('Transformed {} into None for Escodegen; was it legitimate?')
                dico[child.body].append(dico2)
            else:
                build_json(child, dico2)
                dico[child.body] = dico2
    elif ast_nodes.body_list == 'special':
        dico[ast_nodes.body] = []
    else:
        pass
    for att in ast_nodes.attributes:
        dico[att] = ast_nodes.attributes[att]
    return dico


def save_json(ast_nodes, json_path):
    """
        Stores an AST format Node objects in a JSON file.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).
        - json_path: str
            Path of the JSON file to store the AST in.
    """

    data = build_json(ast_nodes, dico={})
    with open(json_path, 'w') as json_data:
        json.dump(data, json_data, indent=4)


def get_code(json_path, code_path='1', remove_json=True, test=False):
    """
        Convert JSON format back to JavaScript code.

        -------
        Parameters:
        - json_path: str
            Path of the JSON file to build the code from.
        - code_path: str
            Path of the file to store the code in. If 1, then displays it to stdout.
        - remove_json: bool
            Indicates whether to remove or not the JSON file containing the Esprima AST.
            Default: True.
        - test: bool
            Indicates whether we are in test mode. Default: False.
    """

    try:
        code = subprocess.run(['node', os.path.join(SRC_PATH, 'generate_js.js'),
                               json_path, code_path],
                              stdout=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError:
        logging.exception('Something went wrong to get the code from the AST for %s', json_path)
        return None

    if remove_json:
        os.remove(json_path)
    if code.returncode != 0:
        logging.error('Something wrong happened while converting JS back to code for %s', json_path)
        return None

    if code_path == '1':
        if test:
            print((code.stdout.decode('utf-8')).replace('\n', ''))
        return (code.stdout.decode('utf-8')).replace('\n', '')

    return code_path
