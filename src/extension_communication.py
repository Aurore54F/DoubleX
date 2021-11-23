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
    Linking the PDG of the content script (CS) to the PDG of the background page (BP).
"""

import logging
import timeit
import json
import graphviz

import pdg_js.node as _node
from pdg_js.value_filters import display_values
import pdg_js.utility_df as utility_df

import get_pdg
from get_pdg import get_node_computed_value_e, get_node_value_e
# import display_extension
import browser_api
import chrome_api
import messages
import utility

PRINT_DEBUG = utility.PRINT_DEBUG


"""
In the following, if not stated otherwise:
    - node: Node
        Current node.
    - chrome: bool
        True if we are handling a Chromium-based extension, False otherwise.
    - sender: Node
        Node that sent the message.
    - receiver: Node
        Node that received the message.
    - all_messages: list of MessageType (can be WaAndCs, CsAndBp, or WaAndBp)
        Contains the different messages sent/received, organized per category, e.g., FF1 vs. FF2.
    - where / where1 / where2: str
        Possibilities: ('wa2cs', 'cs2wa', 'cs2bp', 'bp2cs', 'wa2bp', 'bp2wa')
        Indicates the:
            - current position (2 letters before '2');
            - communication partner (2 letters after '2').
        Ex: 'cs2bp' => we are in the content script and are communicating with the background page.
    - graph: graphviz object
        Graph object for the graphical representation of the PDGs.
"""


def generate_communication_channel(where, name):
    """ Generates the communication channel named name, between the 2 actors from where. """

    if where in ('wa2cs', 'cs2wa'):  # Communication between web app and content script
        return messages.WaAndCs(name)
    if where in ('cs2bp', 'bp2cs'):  # Communication between content script and background page
        return messages.CsAndBp(name)
    if where in ('wa2bp', 'bp2wa'):  # Communication between web app and background page
        return messages.WaAndBp(name)

    logging.error('Handling the communication between wa, cs and bp but got %s', where)
    return None


def message_type_from(message_type, where):
    """ Returns the messages sent and received by the considered actor for a given message_type. """

    if where == 'wa2cs':  # In web app. Communication with content script
        return message_type.wa
    if where == 'cs2wa':  # In content script. Communication with web app
        return message_type.cs
    if where == 'cs2bp':  # In content script. Communication with background page
        return message_type.cs
    if where == 'bp2cs':  # In background page. Communication with content script
        return message_type.bp
    if where == 'wa2bp':  # In web app. Communication with background page
        return message_type.wa
    if where == 'bp2wa':  # In background page. Communication with web app
        return message_type.bp

    logging.error('Handling the communication between wa, cs and bp but got %s', where)
    return None


def handle_message(node, mess_api, mess_info, all_messages, where):
    """
    Handles the message contained in the CallExpression / (Arrow)FunctionExpression node.

    :param node: Node, contains the message to handle;
    :param mess_api: str, a message passing API, key of the dict CS2BP / BP2CS / CS_BP...;
    :param mess_info: dict, the value corresponding to the previous key;
    :param all_messages: list of MessageType (WaAndCs, CsAndBp, WaAndBP), the messages found so far;
    :param where: str, indicates the current position + the communication partner, e.g., cs2bp.

    :return: str: mess_api.
    """

    mess_type = None

    for message_type in all_messages:  # Search if we already have a message of that type
        if message_type.name == mess_info['mess_type']:
            mess_type = message_type  # Yes = get a handler to it
            break
    if mess_type is None:
        name = mess_info['mess_type']
        mess_type = generate_communication_channel(where, name)  # No = create it
        all_messages.append(mess_type)  # Append it to our messages list

    handle_mess = mess_info['fun']
    # Handler to the messages sent and received by a given actor for a given message_type
    mess_type_from = message_type_from(mess_type, where)
    handle_mess(node, mess_type_from)  # Handle the message, cf. handle_message.py

    return mess_api


def get_message_api(chrome):
    """ Returns the message passing APIs for chrome vs. for the other browsers. """

    if chrome:
        return chrome_api
    return browser_api


def select_message_api_dict(where, chrome):
    """ Returns the dict containing the message passing APIs relevant for the communication
    channel where. """

    message_api = get_message_api(chrome)

    if where == 'wa2cs':  # In web app. Communication with content script
        return [message_api.WA_CS]
    if where == 'cs2wa':  # In content script. Communication with web app
        return [message_api.WA_CS]
    if where == 'cs2bp':  # In content script. Communication with background page
        return [message_api.CS2BP, message_api.CS_BP]
    if where == 'bp2cs':  # In background page. Communication with content script
        return [message_api.BP2CS, message_api.CS_BP]
    if where == 'wa2bp':  # In web app. Communication with background page
        return [message_api.WA2BP]
    if where == 'bp2wa':  # In background page. Communication with web app
        return [message_api.BP2WA]

    logging.error('Handling the communication between wa, cs and bp but got %s', where)
    return []


def find_message(node, value, all_messages, where, chrome):
    """ Checks if value is part of an API to send/receive messages. """

    found = None
    message_api = get_message_api(chrome)
    dict_list = select_message_api_dict(where, chrome=chrome)  # Message APIs to check

    for my_dict in dict_list:
        for (mess_api, mess_info) in my_dict.items():
            if mess_api in value:  # value is part of an API to exchange messages
                if not isinstance(mess_info, dict):  # Special case for postMessages
                    if mess_info:
                        mess_info = message_api.global_post_message(value)
                    else:
                        mess_info = message_api.port_post_message(value)

                # Handles the message sent/received
                try:
                    found = handle_message(node, mess_api, mess_info, all_messages, where)
                    break  # Only working if key order in dict is preserved; break inner loop
                except utility_df.Timeout.Timeout as e:
                    raise e  # Will be caught in vulnerability_detection
                except Exception as e:
                    logging.exception(e)
        else:
            continue  # Inner loop was not broken, continue iterating
        break  # Inner loop was broken, breaks outer loop

    if found is not None:
        logging.debug('Found the message %s', found)
        return value  # Message that has been found

    return None


def find_all_messages(node, all_messages, where, chrome):
    """ Finds all the nodes exchanging messages in a given PDG and stores them in all_messages. """

    for child in node.children:
        if child.name in ('CallExpression', 'TaggedTemplateExpression'):
            if len(child.children) > 0 and child.children[0].body in ('callee', 'tag'):
                callee = child.children[0]
                call_expr_value = get_node_computed_value_e(callee)
                if isinstance(call_expr_value, str):  # No need to check if it is not a str
                    child.set_value(get_node_computed_value_e(child))
                    # Checks if call_expr_value is part of an API to exchange messages
                    find_message(child, call_expr_value, all_messages, where=where, chrome=chrome)
                    # if find_message is not None: found a message to be sent/received

        elif where in ('cs2wa', 'wa2cs') and child.name == 'AssignmentExpression':
            # Detects the onmessage API
            detect_onmessage(child, all_messages, where, chrome)

        find_all_messages(child, all_messages, where, chrome=chrome)


def detect_onmessage(child, all_messages, where, chrome):
    """ Detects the onmessage API:
        - onmessage = function()
        - onmessage = f and the FunExpr/FunDecl f defined before
        """

    # if isinstance(child, _node.FunctionExpression):  # Case: onmessage = function()
    #     cond = True
    #     if child.fun_name is not None:
    #         fun_expr_value = get_node_computed_value_e(child.fun_name)  # Access to fun's name
    #         if isinstance(fun_expr_value, _node.Node):
    #             # If Id = FunExpr, value of Id is FunExpr, computing the value of FunExpr...
    #             # ... gives Id as FunExpr name, so needs to get Id's attributes hence:
    #             fun_expr_value = get_node_value_e(fun_expr_value)  # get_node_value_e
    #         if isinstance(fun_expr_value, str):  # No need to check if it is not a str
    #             # Checks if fun_expr_value is part of an API to exchange messages
    #             find_message(child, fun_expr_value, all_messages, where=where, chrome=chrome)

    # if where == 'cs2wa' and child.name == 'AssignmentExpression':
    if len(child.children) == 2:
        var = child.children[0]
        identifier_value = None
        if var.name == 'MemberExpression' and var.children[1].name == 'Identifier':
            if var.children[0].name != 'MemberExpression':  # Avoided X.port.onmessage cases
                # Let's see, we may have to look specifically for window/global/this.onmessage etc
                identifier_value = get_node_value_e(var.children[1])
        elif var.name == 'Identifier':
            identifier_value = get_node_value_e(var)
        if isinstance(identifier_value, str) and 'onmessage' in identifier_value:
            init = child.children[1]

            if isinstance(init, (_node.FunctionExpression, _node.FunctionDeclaration)):
                # Case: onmessage = function()
                handle_onmessage(init, all_messages, where, chrome)

            if not isinstance(init, _node.Identifier):
                return

            for data_dep_parent in init.data_dep_parents:
                # Case: onmessage = f and the FunExpr/FunDecl f defined before
                # We are looking for the function definition site
                fun_identifier = data_dep_parent.extremity
                fun_def = fun_identifier.fun
                if isinstance(fun_def, (_node.FunctionExpression, _node.FunctionDeclaration)):
                    handle_onmessage(fun_def, all_messages, where, chrome)


def handle_onmessage(fun_def, all_messages, where, chrome):
    """ Handles the onmessage API separately. fun_def is a handler to the FuncExpr/FunDecl. """

    try:
        message_api = get_message_api(chrome)
        handle_message(node=fun_def, mess_api='onmessage', mess_info=message_api.WA_CS['onmessage'],
                       all_messages=all_messages, where=where)
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except Exception as e:
        logging.exception(e)


def update_receiver_data_dep(receiver, updated_id):
    """ Updates the value of the DD from a receiver node with the sender's value. """

    # Recursively updates data flow
    for data_dep in receiver.data_dep_children:
        data_dep = data_dep.extremity
        data_dep.set_value(receiver.value)  # Updates with value of receiver coming from sender
        data_dep.set_provenance(receiver)  # data_dep is depending on receiver
        update_receiver_all_dep(data_dep, updated_id=updated_id)


def update_receiver_param_dep(receiver, updated_id):
    """ Updates the value of the param flow from a receiver node with the sender's value. """

    # Recursively updates parameter flow
    while receiver.parent.name == 'MemberExpression':
        receiver = receiver.parent
    if hasattr(receiver, 'fun_param_parents'):  # receiver = param at call site
        for def_param in receiver.fun_param_parents:  # Iterates over param at definition site
            if isinstance(receiver, _node.Value):
                def_param.set_value(receiver.value)  # Updates with value of receiver
            def_param.set_provenance(receiver)  # def_param is depending on receiver
            update_receiver_all_dep(def_param, updated_id=updated_id)


def update_receiver_all_dep(receiver, updated_id):
    """ Updates the value of both data and param flow from a receiver with the sender's value. """

    if receiver.id in updated_id:
        return  # To avoid infinite loops
    updated_id.append(receiver.id)
    try:
        update_receiver_data_dep(receiver, updated_id=updated_id)  # Recursively updates data flow
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except:
        logging.exception('Something went wrong to update the receiver value along data flow')

    try:
        # Recursively updates parameter flow
        update_receiver_param_dep(receiver, updated_id=updated_id)
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection
    except:
        logging.exception('Something went wrong to update the receiver value along parameter flow')


def set_message_flow(sender, receiver, graph):
    """ Sets a message flow from the sender to the receiver. """

    # Adds corresponding attributes
    setattr(sender, 'flow_children', [])
    setattr(receiver, 'flow_parents', [])

    # Adds flow in both directions
    sender.flow_children.append(receiver)
    receiver.flow_parents.append(sender)
    if isinstance(receiver, _node.Value):
        receiver.set_provenance(sender)  # receiver is depending on sender

        old_receiver_value = receiver.value
        if old_receiver_value is not None and not isinstance(old_receiver_value, str):
            logging.warning('The value %s will be overwritten', receiver.value)
        receiver.set_value(get_node_computed_value_e(sender))  # Receiver gets value of sender
        if isinstance(receiver, _node.Identifier):
            updated_id = list()
            # Receiver data and param flow get value of sender
            update_receiver_all_dep(receiver, updated_id=updated_id)
        if old_receiver_value is not None and not isinstance(old_receiver_value, str):
            logging.warning('The value %s has been overwritten by %s',
                            old_receiver_value, receiver.value)

    # To draw the extension's message flows
    if graph is not None:
        graph.attr('edge', color='limegreen', style='solid')
        graph.edge(str(sender.id), str(receiver.id), label='message')


def link_message(pdg, sender, receiver, graph):
    """ Links the messages sent by the sender to the messages received by the receiver. """

    for sent in sender:
        for received in receiver:
            set_message_flow(sent, received, graph)
            update_call_expr(pdg)  # Debug, checks if CallExpression have been updated


def link_all_messages(pdg1, pdg2, where1, where2, benchmarks, chrome, graph=None,
                      messages_dict=None):
    """ Links all messages sent from pdg1/pdg2 to the recipient in the other one. """

    with utility_df.Timeout(600):  # Tries to link CS and BP PDG with messages within 10 minutes

        start = timeit.default_timer()
        all_messages = []
        # Stores all messages exchanged between pdg1 and pdg2
        find_all_messages(pdg1, all_messages, where=where1, chrome=chrome)
        find_all_messages(pdg2, all_messages, where=where2, chrome=chrome)

        benchmarks['collected messages'] = timeit.default_timer() - start
        start = utility_df.micro_benchmark('Successfully collected all messages exchanged in',
                                           timeit.default_timer() - start)

        for message_type in all_messages:  # Messages are organized per category, e.g., FF1 vs. FF2
            if PRINT_DEBUG:
                message_type.__print__()  # For debug
            if messages_dict is not None:
                try:
                    message_type.__to_dict__(messages_dict)  # Stores communication in messages_dict
                except utility_df.Timeout.Timeout as e:
                    raise e  # Will be caught in vulnerability_detection
                except Exception:
                    logging.exception('Could not store the messages in a dict')

            # Handler to the messages sent and received by a given actor for a given message_type
            partner1 = message_type_from(message_type, where1)
            partner2 = message_type_from(message_type, where2)

            # Add message flow from sender to receiver
            utility.print_separator()
            link_message(pdg2, partner1.sent, partner2.received, graph)  # A sends, B receives
            utility.print_separator()
            link_message(pdg1, partner2.sent, partner1.received, graph)
            utility.print_separator()
            link_message(pdg2, partner1.responded, partner2.got_response, graph)  # May respond
            utility.print_separator()
            link_message(pdg1, partner2.responded, partner1.got_response, graph)

        # Building the PDGs again to be sure that DF/provenance/values are up-to-date
        # utility.print_info('Rebuilding CS PDG:')
        # pdg1 = df_scoping(pdg1, scopes=[_scope.Scope('Global')], id_list=[], entry=1)[0]
        # utility.print_info('Rebuilding BP PDG:')
        # pdg2 = df_scoping(pdg2, scopes=[_scope.Scope('Global')], id_list=[], entry=1)[0]
        # utility.print_separator()

    try:
        with utility.Timeout(10):  # Updating provenance should be extra fast
            update_provenance(pdg1)  # Updates provenance by avoiding inconsistencies
    except utility.Timeout.Timeout:  # not a timeout but a warning for us
        logging.exception('Provenance update for %s', pdg1.get_file())
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection

    try:
        with utility.Timeout(10):  # Updating provenance should be extra fast
            update_provenance(pdg2)  # Updates provenance by avoiding inconsistencies
    except utility.Timeout.Timeout:  # not a timeout but a warning for us
        logging.exception('Provenance update for %s', pdg2.get_file())
    except utility_df.Timeout.Timeout as e:
        raise e  # Will be caught in vulnerability_detection

    benchmarks['linked messages'] = timeit.default_timer() - start
    utility_df.micro_benchmark('Successfully linked the messages sent and received in',
                               timeit.default_timer() - start)

    return pdg1, pdg2


def produce_extension_pdg(cs_path, bp_path, benchmarks):
    """
    Builds the PDG of an extension, meaning 1) produce the PDG of the content script and the PDG
    of the background page, and 2) link them by leveraging the passing messaging APIs.

    :param cs_path: str, path of the content script;
    :param bp_path: str, path of the background page;
    :param benchmarks: dict, storing the time and ram info.

    :return: Node, Node: PDG of the CS and PDG of the BP.
    """

    # Builds the 2 PDGs
    utility.print_info('> PDG of ' + cs_path)
    pdg_cs = get_pdg.get_pdg(file_path=cs_path, res_dict=benchmarks)  # Builds CS PDG
    update_benchmarks_pdg(benchmarks=benchmarks, whoami='cs')

    utility.print_info('---\n> PDG of ' + bp_path)
    pdg_bp = get_pdg.get_pdg(file_path=bp_path, res_dict=benchmarks)
    update_benchmarks_pdg(benchmarks=benchmarks, whoami='bp')

    return pdg_cs, pdg_bp


def get_analysis(pdg_path, benchmarks, whoami):
    """ Loads a previously computed PDG and the corresponding benchmarks. """

    pdg = get_pdg.unpickle_pdg(pdg_path)  # Loads the PDG

    benchmarks_path = pdg_path + '.json'
    try:
        with open(benchmarks_path) as json_data:
            try:
                my_benchmarks = json.loads(json_data.read())
                update_benchmarks_pdg(benchmarks=my_benchmarks, whoami=whoami)
                for k, v in my_benchmarks.items():
                    benchmarks[k] = v
            except json.decoder.JSONDecodeError:
                logging.exception('Something went wrong to open %s', benchmarks_path)
    except FileNotFoundError:
        logging.exception('The file %s does not exist', benchmarks_path)

    return pdg


def fetch_extension_pdg(cs_pdg_path, bp_pdg_path, benchmarks):
    """
    Builds the PDG of an extension, meaning 1) fetch the PDG of the CS and the PDG of the BP which
    we previously generated, and 2) link them by leveraging the passing messaging APIs.

    :param cs_pdg_path: str, path of the PDG of the content script;
    :param bp_pdg_path: str, path of the PDG of the background page;
    :param benchmarks: dict, storing the time and ram info.

    :return: Node, Node: PDG of the CS and PDG of the BP.
    """

    # Fetches the 2 PDGs and benchmarks
    utility.print_info('> PDG of ' + cs_pdg_path)
    pdg_cs = get_analysis(pdg_path=cs_pdg_path, benchmarks=benchmarks, whoami='cs')

    utility.print_info('---\n> PDG of ' + bp_pdg_path)
    pdg_bp = get_analysis(pdg_path=bp_pdg_path, benchmarks=benchmarks, whoami='bp')

    return pdg_cs, pdg_bp


def build_extension_pdg(cs_path, bp_path, benchmarks, pdg, chrome, messages_dict):
    """
    Builds the PDG of an extension, meaning links the content script to the background page
    by leveraging the passing messaging APIs.

    :param cs_path: str, path of the (PDG of the) content script;
    :param bp_path: str, path of the (PDG of the) background page;
    :param benchmarks: dict, storing the time and ram info;
    :param pdg: bool, True if the PDGs have already been generated and are stored in cs_path/bp_path
        False if cs_path/bp_path are the path of the CS/BP;
    :param chrome: bool, True if we are handling a chrome extension, False for the rest.

    :return: Node, Node: PDG of the CS and PDG of the BP.
    """

    if pdg:  # The CS and BP PDGs have been generated previously, fetch and link them
        pdg_cs, pdg_bp = fetch_extension_pdg(cs_pdg_path=cs_path, bp_pdg_path=bp_path,
                                             benchmarks=benchmarks)
    else:  # Generate the CS and BP PDGs before linking them
        pdg_cs, pdg_bp = produce_extension_pdg(cs_path=cs_path, bp_path=bp_path,
                                               benchmarks=benchmarks)

    utility.print_info('---\n> Links messages')
    graph = graphviz.Digraph(comment='Extension Dependence Graph (EDG)')

    # Links CS and BP using their messages + builds PDGs again
    try:
        pdg_cs, pdg_bp = link_all_messages(pdg1=pdg_cs, pdg2=pdg_bp, where1='cs2bp',
                                           where2='bp2cs', benchmarks=benchmarks, chrome=chrome,
                                           graph=graph, messages_dict=messages_dict)
    except utility_df.Timeout.Timeout:
        logging.exception('Linking messages timed out for %s %s', cs_path, bp_path)
        if 'crashes' not in benchmarks:
            benchmarks['crashes'] = []
        benchmarks['crashes'].append('linking-messages-timeout')

    # Displays Extension Dependence Graph (EDG)
    # display_extension.draw_extensions(pdg_cs, pdg_bp, graph, save_path=None)
    # display_extension.draw_ast(pdg_bp, attributes=True, save_path=None)  # BP's AST

    return pdg_cs, pdg_bp


def debug_wa_communication(wa_path, path2, who_is, chrome=True):
    """ Debug function to check the messages exchanged between WA and who_is = ('cs', 'bp'). """

    # Builds the 2 PDGs
    if wa_path is None:
        pdg_wa = _node.Node('Program')
    else:
        pdg_wa = get_pdg.get_pdg(wa_path, res_dict=dict())
    pdg2 = get_pdg.get_pdg(path2, res_dict=dict())

    graph = graphviz.Digraph(comment='Debug EDG')

    if who_is == 'cs':  # Links WA and CS through messages
        link_all_messages(pdg1=pdg_wa, pdg2=pdg2, where1='wa2cs', where2='cs2wa',
                          benchmarks=dict(), chrome=chrome, graph=graph)
    elif who_is == 'bp':  # Links WA and BP through messages
        link_all_messages(pdg1=pdg_wa, pdg2=pdg2, where1='wa2bp', where2='bp2wa',
                          benchmarks=dict(), chrome=chrome, graph=graph)
    else:
        logging.error('Expected \'cs\' or \'bp\', got %s', who_is)

    # Displays Extension Dependence Graph (EDG)
    # display_extension.draw_extensions(pdg_wa, pdg2, graph)


def update_call_expr(node):
    """ Debug function to check if the CallExpression's value has been updated. """

    for child in node.children:
        if child.name in ('CallExpression', 'TaggedTemplateExpression'):
            child.value = None  # Otherwise not recomputed and old cached value would be returned
            call_expr_value = get_node_computed_value_e(child)
            child.set_value(call_expr_value)
            display_values(var=child)
        update_call_expr(child)


def update_benchmarks_pdg(benchmarks, whoami):
    """ PDG generation benchmarks are generic, here we make the difference between CS and BP. """

    if 'errors' in benchmarks:
        if 'crashes' not in benchmarks:
            benchmarks['crashes'] = []
        crashes = benchmarks.pop('errors')
        for el in crashes:
            benchmarks['crashes'].append(whoami + ': ' + el)
    if 'got AST' in benchmarks:
        benchmarks[whoami + ': got AST'] = benchmarks.pop('got AST')
    if 'AST' in benchmarks:
        benchmarks[whoami + ': AST'] = benchmarks.pop('AST')
    if 'CFG' in benchmarks:
        benchmarks[whoami + ': CFG'] = benchmarks.pop('CFG')
    if 'PDG' in benchmarks:
        benchmarks[whoami + ': PDG'] = benchmarks.pop('PDG')


def update_provenance(node):
    """ Updates the provenance of nodes, not containing all nodes they are depending on.
    We focus on inconsistencies, e.g., A -> B -> C, meaning that C should depend on A. """

    if isinstance(node, _node.Value):  # C
        node_prov_parents = node.provenance_parents
        for prov in node_prov_parents:  # B
            if isinstance(prov, _node.Value):
                for prov_child in prov.provenance_parents:  # A
                    if prov_child not in node_prov_parents:  # if A not in C prov list
                        # Can happen, e.g., BP sends a message to CS. Even though we rebuild CS PDG,
                        # we may miss some provenance as we may only add them if we did not already
                        # compute a given value. This is a workaround to add the missing ones.
                        logging.debug('Whoops, %s is depending on %s',
                                      node.attributes, prov_child.attributes)
                        node.set_provenance(prov_child)
    for child in node.children:
        update_provenance(child)
