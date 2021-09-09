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
    Generation and storage of JavaScript PDGs.
"""

import os
import pickle
import logging
import timeit
import json

from . import node as _node
from . import build_ast
from . import utility_df
from . import control_flow
from . import data_flow
from . import scope as _scope

# Builds the JS code from the AST, or not, to check for possible bugs in the AST building process.
CHECK_JSON = utility_df.CHECK_JSON


def pickle_dump_process(dfg_nodes, store_pdg):
    """ Call to pickle.dump """
    pickle.dump(dfg_nodes, open(store_pdg, 'wb'))


def function_hoisting(node, entry):
    """ Hoists FunctionDeclaration at the beginning of a basic block = Function bloc. """

    # Will avoid problem if function first called and then defined
    for child in node.children:
        if child.name == 'FunctionDeclaration':
            child.adopt_child(step_daddy=entry)  # Sets new parent and deletes old one
            function_hoisting(child, entry=child)  # New basic block = FunctionDeclaration = child
        elif child.name == 'FunctionExpression':
            function_hoisting(child, entry=child)  # New basic block = FunctionExpression = child
        else:
            function_hoisting(child, entry=entry)  # Current basic block = entry


def traverse(node):
    """ Debug function, traverse node. """

    for child in node.children:
        print(child.name)
        traverse(child)


def get_data_flow(input_file, benchmarks, store_pdgs=None, check_var=False, beautiful_print=False,
                  check_json=CHECK_JSON):
    """
        Builds the PDG: enhances the AST with CF, DF, and pointer analysis for a given file.

        -------
        Parameters:
        - input_file: str
            Path of the file to analyze.
        - benchmarks: dict
            Contains the different micro benchmarks. Should be empty.
        - store_pdgs: str
            Path of the folder to store the PDG in.
            Or None to pursue without storing it.
        - check_var: bool
            Returns the unknown variables (not the PDG).
        - beautiful_print: bool
            Whether to beautiful print the AST or not.
        - check_json: bool
            Builds the JS code from the AST, or not, to check for bugs in the AST building process.

        -------
        Returns:
        - Node
            PDG of the file.
        - or None if problems to build the PDG.
        - or list of unknown variables if check_var is True.
    """

    start = timeit.default_timer()
    utility_df.limit_memory(20*10**9)  # Limiting the memory usage to 20GB
    if input_file.endswith('.js'):
        esprima_json = input_file.replace('.js', '.json')
    else:
        esprima_json = input_file + '.json'
    extended_ast = build_ast.get_extended_ast(input_file, esprima_json)

    if extended_ast is not None:
        start = utility_df.micro_benchmark('Successfully got Esprima AST in',
                                           timeit.default_timer() - start)
        ast = extended_ast.get_ast()
        if beautiful_print:
            build_ast.beautiful_print_ast(ast, delete_leaf=[])
        ast_nodes = build_ast.ast_to_ast_nodes(ast, ast_nodes=_node.Node('Program'))
        function_hoisting(ast_nodes, ast_nodes)  # Hoists FunDecl at a basic block's beginning

        start = utility_df.micro_benchmark('Successfully produced the AST in',
                                           timeit.default_timer() - start)

        cfg_nodes = control_flow.control_flow(ast_nodes)
        start = utility_df.micro_benchmark('Successfully produced the CFG in',
                                           timeit.default_timer() - start)

        unknown_var = []
        try:
            with utility_df.Timeout(600):  # Tries to produce DF within 10 minutes
                scopes = [_scope.Scope('Global')]
                dfg_nodes, scopes = data_flow.df_scoping(cfg_nodes, scopes=scopes,
                                                         id_list=[], entry=1)
                # This may have to be added if we want to make the fake hoisting work
                # dfg_nodes = data_flow.df_scoping(dfg_nodes, scopes=scopes, id_list=[], entry=1)[0]
        except utility_df.Timeout.Timeout:
            logging.critical('Building the PDG timed out for %s', input_file)
            return _node.Node('Program')  # Empty PDG to avoid trying to get the children of None

        utility_df.micro_benchmark('Successfully produced the PDG in',
                                   timeit.default_timer() - start)

        if check_json:  # Looking for possible bugs when building the AST / json doc in build_ast
            my_json = esprima_json.replace('.json', '-back.json')
            build_ast.save_json(dfg_nodes, my_json)
            print(build_ast.get_code(my_json))

        if check_var:
            for scope in scopes:
                for unknown in scope.unknown_var:
                    if not unknown.data_dep_parents:
                        # If DD: not unknown, can happen because of hoisting FunctionDeclaration
                        # After second function run, not unknown anymore
                        logging.warning('The variable %s is not declared in the scope %s',
                                        unknown.attributes['name'], scope.name)
                        unknown_var.append(unknown)
            return unknown_var

        if store_pdgs is not None:
            store_pdg = os.path.join(store_pdgs, os.path.basename(input_file.replace('.js', '')))
            pickle_dump_process(dfg_nodes, store_pdg)
            json_analysis = os.path.join(store_pdgs, os.path.basename(esprima_json))
            with open(json_analysis, 'w') as json_data:
                json.dump(benchmarks, json_data, indent=4, sort_keys=False, default=default,
                          skipkeys=True)
        return dfg_nodes
    return _node.Node('ParsingError')  # Empty PDG to avoid trying to get the children of None


def default(o):
    """ To avoid TypeError, conversion of problematic objects into str. """

    return str(o)
