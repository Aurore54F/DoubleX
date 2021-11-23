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

# Additional permission under GNU GPL version 3 section 7
#
# If you modify this Program, or any covered work, by linking or combining it with
# graphviz (or a modified version of that library), containing parts covered by the
# terms of The Common Public License, the licensors of this Program grant you
# additional permission to convey the resulting work.


"""
    Display an Extension Dependence Graph (EDG) using the graphviz library.
"""

import copy
import graphviz

import pdg_js.node as _node


def append_leaf_attr(node, graph):
    """
        Append the leaf's attribute to the graph in graphviz format.

        -------
        Parameters:
        - node: Node
            Node.
        - graph: Digraph/Graph
            Graph object. Be careful it is mutable.
    """

    if node.is_leaf():
        leaf_id = str(node.id) + 'leaf_'
        graph.attr('node', style='filled', color='white', fillcolor='white')
        graph.attr('edge', color='grey', style='tapered')
        got_attr, node_attributes = node.get_node_attributes()
        if got_attr:  # Got attributes
            leaf_attr = str(node_attributes)
            graph.node(leaf_id, leaf_attr)
            graph.edge(str(node.id), leaf_id)


def produce_ast(ast_nodes, attributes, graph=graphviz.Digraph(comment='AST representation')):
    """
        Produce an AST in graphviz format.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).
        - graph: Graph
            Graph object. Be careful it is mutable.
        - attributes: bool
            Whether to display the leaf attributes or not.

        -------
        Returns:
        - graph
            graphviz formatted graph.
    """

    graph.attr('node', color='black', style='filled', fillcolor='lightgoldenrodyellow')
    graph.attr('edge', color='black')
    graph.node(str(ast_nodes.id), ast_nodes.name)
    for child in ast_nodes.children:
        graph.attr('node', color='black', style='filled', fillcolor='lightgoldenrodyellow')
        graph.attr('edge', color='black')
        graph.edge(str(ast_nodes.id), str(child.id))
        produce_ast(child, attributes, graph)
        if attributes:
            append_leaf_attr(child, graph)
    return graph


def draw_ast(ast_nodes, attributes=False, save_path=None):
    """
        Plot an AST.

        -------
        Parameters:
        - ast_nodes: Node
            Output of ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')).
        - save_path: str
            Path of the file to store the AST in.
        - attributes: bool
            Whether to display the leaf attributes or not. Default: False.
    """

    dot = produce_ast(ast_nodes, attributes)
    if save_path is None:
        dot.view()
    else:
        dot.render(save_path, view=False)
        graphviz.render(filepath=save_path, engine='dot', format='eps')
    dot.clear()


def cfg_type_node(child):
    """ Different form according to statement node or not. """

    if isinstance(child, _node.Statement) or child.is_comment():
        return ['box', 'mediumblue', 'lightblue', 'dotted']
    return ['ellipse', 'black', 'lightgoldenrodyellow', 'bold']


def produce_cfg_one_child(child, data_flow, attributes,
                          graph=graphviz.Digraph(comment='Control flow representation')):
    """
        Produce a CFG in graphviz format.

        -------
        Parameters:
        - child: Node
            Node to begin with.
        - data_flow: bool
            Whether to display the data flow or not. Default: False.
        - attributes: bool
            Whether to display the leaf attributes or not.
        - graph: Digraph
            Graph object. Be careful it is mutable.

        -------
        Returns:
        - graph
            graphviz formatted graph.
    """

    type_node = cfg_type_node(child)
    graph.attr('node', shape=type_node[0], style='filled', color=type_node[1],
               fillcolor=type_node[2])
    graph.attr('edge', color=type_node[1], style=type_node[3])
    graph.node(str(child.id), child.name)

    for child_statement_dep in child.statement_dep_children:
        child_statement = child_statement_dep.extremity
        type_node = cfg_type_node(child_statement)
        graph.attr('node', shape=type_node[0], color=type_node[1], fillcolor=type_node[2])
        graph.attr('edge', color=type_node[1], style=type_node[3])
        graph.edge(str(child.id), str(child_statement.id), label=child_statement_dep.label)
        produce_cfg_one_child(child_statement, data_flow=data_flow, attributes=attributes,
                              graph=graph)
        if attributes:
            append_leaf_attr(child_statement, graph)

    if isinstance(child, _node.Statement):
        for child_cf_dep in child.control_dep_children:
            child_cf = child_cf_dep.extremity
            type_node = cfg_type_node(child_cf)
            graph.attr('node', shape=type_node[0], color=type_node[1], fillcolor=type_node[2])
            graph.attr('edge', color='mediumblue', style=type_node[3])
            graph.edge(str(child.id), str(child_cf.id), label=str(child_cf_dep.label))
            produce_cfg_one_child(child_cf, data_flow=data_flow, attributes=attributes, graph=graph)
            if attributes:
                append_leaf_attr(child_cf, graph)

    if data_flow:
        graph.attr('edge', color='darkorange', style='dashed')
        if isinstance(child, _node.Identifier):
            for child_data_dep in child.data_dep_children:
                child_data = child_data_dep.extremity
                type_node = cfg_type_node(child)
                graph.attr('node', shape=type_node[0], color=type_node[1], fillcolor=type_node[2])
                graph.edge(str(child.id), str(child_data.id), label=child_data_dep.label)
                # No call to the func as already recursive for data/statmt dep on the same nodes
                # logging.info("Data dependency on the variable " + child_data.attributes['name'])
        graph.attr('edge', color='deepskyblue', style='dashed')
        if hasattr(child, 'fun_param_parents'):  # Function parameters flow
            for child_param in child.fun_param_parents:
                type_node = cfg_type_node(child)
                graph.attr('node', shape=type_node[0], color=type_node[1], fillcolor=type_node[2])
                graph.edge(str(child.id), str(child_param.id), label='param')

    return graph


def draw_cfg(cfg_nodes, attributes=False, save_path=None):
    """
        Plot a CFG.

        -------
        Parameters:
        - cfg_nodes: Node
            Output of produce_cfg(ast_to_ast_nodes(<ast>, ast_nodes=Node('Program'))).
        - save_path: str
            Path of the file to store the CFG in.
        - attributes: bool
            Whether to display the leaf attributes or not. Default: False.
    """

    dot = graphviz.Digraph()
    for child in cfg_nodes.children:
        dot = produce_cfg_one_child(child=child, data_flow=False, attributes=attributes)
    if save_path is None:
        dot.view()
    else:
        dot.render(save_path, view=False)
        graphviz.render(filepath=save_path, engine='dot', format='eps')
    dot.clear()


def draw_pdg(dfg_nodes, attributes=False, save_path=None):
    """
        Plot a PDG.

        -------
        Parameters:
        - dfg_nodes: Node
            Output of produce_dfg(produce_cfg(ast_to_ast_nodes(<ast>, ast_nodes=Node('Program')))).
        - save_path: str
            Path of the file to store the PDG in.
        - attributes: bool
            Whether to display the leaf attributes or not. Default: False.
    """

    dot = graphviz.Digraph()
    for child in dfg_nodes.children:
        dot = produce_cfg_one_child(child=child, data_flow=True, attributes=attributes)
    if save_path is None:
        dot.view()
    else:
        dot.render(save_path, view=False)
        graphviz.render(filepath=save_path, engine='dot', format='eps')
    dot.clear()


def draw_extensions(pdg_cs, pdg_bp, graph, attributes=True, save_path=None):
    """
        Display the Extension Dependence Graph (EDG). No links CS/BP yet.

        -------
        Parameters:
        - pdg_cs: Node
            PDG of the content script.
        - pdg_bp: Node
            PDG of the background page.
        - graph: graphviz object
            Graph object.
        - save_path: str
            Path of the file to store the EDG in.
        - attributes: bool
            Whether to display the leaf attributes or not. Default: True.
    """

    dot = graphviz.Digraph()
    pdg_extension = copy.copy(pdg_cs.children)
    pdg_extension.extend(pdg_bp.children)
    for node in pdg_extension:
        dot = produce_cfg_one_child(child=node, data_flow=True, graph=graph, attributes=attributes)
    try:
        if save_path is None:
            dot.view()
        else:
            dot.render(save_path, view=False)
            graphviz.render(filepath=save_path, engine='dot', format='eps')
        dot.clear()
    except:
        pass
