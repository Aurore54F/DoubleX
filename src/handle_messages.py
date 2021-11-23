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
    Handling the messages sent and received between the content script and the background page.
    Storage in a MessageType object so that messages of the same category are stored together.
"""

import logging

import pdg_js.node as _node

from get_pdg import get_node_computed_value_e
import messages


"""
In the following, if not stated otherwise:
    - node: Node
        Current CallExpression node.
    - mess_type_from: Messages
        Messages sent/received:
            - by a given actor (WA, CS, BP);
            - for a given communication channel (WaAndCs, CsAndBp, WaAndBp);
            - for a given category (B1 vs. B2, C1 vs. C2).
"""


def find_callback_def(handle_callback, param_nb):
    """ Finds the parameter number param_nb of a callback handle_callback which can directly be
    the FunctionExpression node or the name of the function which is defined somewhere else.
     Here, handle_callback is the function call site, we are looking for its definition."""

    orig_handle_callback = handle_callback

    if not isinstance(handle_callback, _node.Node):
        # Could happen because of get_node_computed_value_e in last else branch
        # Could be legitimate in chrome_runtime_sendMessage as we assume that the last param is the
        # callback but the function may not have a callback so we are not analyzing the right thing
        logging.warning('The callback should be a Node object but got %s', handle_callback)
        return None, None

    if isinstance(handle_callback, (_node.FunctionExpression, _node.FunctionDeclaration)):  # Fun
        try:
            message = handle_callback.fun_params[param_nb]  # params[param_nb] = message
            fun = handle_callback  # Handler to the function
        except IndexError:  # Do not know beforehand how many parameters the callback has
            message, fun = None, handle_callback

    elif handle_callback.name == 'ObjectExpression':  # ObjExpr
        if len(handle_callback.children) == 0:
            # observed as chrome.runtime.sendMessage({})
            return None, None
        prop = handle_callback.children[0]  # Should have only one child
        handle_callback = prop.children[1]  # child0 = obj name, child1 = obj content to analyze
        return find_callback_def(handle_callback, param_nb)  # handle_callback is a FunExpr or Id

    elif isinstance(handle_callback, _node.Identifier):
        if len(handle_callback.data_dep_parents) >= 1:  # Will look for the callback definition
            while handle_callback.data_dep_parents:
                handle_callback = handle_callback.data_dep_parents[0].extremity  # Identifier Node
            fun = handle_callback.fun  # Handler to the function?
            # Case1: if fun is not None, fun is a handler to the function
            # handle_callback was initially the function call site and is now the function def site
            # Case2: if fun is None, we did not find the function yet
            # handle_callback is probably the function's parameter, now we need its value
            if fun is None and hasattr(handle_callback, 'fun_param_children'):  # Case 2
                params = handle_callback.fun_param_children  # Gets parameter's values
                message_list = []
                for param in params:
                    logging.error('Should handle several calls to a message API')
                    if param == orig_handle_callback:
                        continue
                    message, fun = find_callback_def(param, param_nb)  # Should go to Case 1 now
                    message_list.append(message)
                    # print(len(message_list))
                    # print(message.attributes)  # TODO can be several messages
                    return message, fun
                # return message_list, fun
            try:
                if fun is not None:  # Case 1
                    message = fun.fun_params[param_nb]  # Gets param param_nb of fun
                else:
                    message = None  # Could not find the function
            except IndexError:  # Do not know beforehand how many parameters the callback has
                message, fun = None, None

        else:
            logging.error('The callback %s has been defined %s times...', handle_callback.id,
                          len(handle_callback.data_dep_children))
            message, fun = None, None

    else:
        message, fun = find_callback_def(get_node_computed_value_e(handle_callback), param_nb)
        # Case where the callback is stored, e.g., in a dict such as content-script1-aliasing.js.
        if message is None and fun is None:
            logging.warning('The callback is either not existing or is a %s', handle_callback.name)
            message, fun = None, None

    return message, fun


def find_callback_call(handle_callback, visited):
    """ Finds the first parameter of the callback handle_callback which can directly be
    the FunctionExpression node or the name of the function which is defined somewhere else.
    Here, handle_callback is the function definition, we are looking for its call site. """

    if handle_callback in visited:
        return None
    visited.add(handle_callback)

    if isinstance(handle_callback, _node.FunctionExpression):  # FunExpr
        logging.error('I do not think I handled that properly...')
        return handle_callback.fun_params[0]  # params[0] = message

    if isinstance(handle_callback, _node.ValueExpr):
        # arrow function, something strange occurs
        return None

    if not hasattr(handle_callback, "data_dep_children"):
        return None

    if handle_callback.data_dep_children:  # Will find where the callback is called
        messages_list = []
        for callback_called in handle_callback.data_dep_children:
            fun_handle_message = callback_called.extremity  # Identifier Node

            if hasattr(fun_handle_message, 'fun_param_parents'):  # Aliasing case, looks for params
                params = fun_handle_message.fun_param_parents  # Gets parameter's values
                for param in params:
                    # for some random reason, this creates an infinite recursion
                    if handle_callback != param:
                        responses = find_callback_call(param, visited)
                        # Got the response objects this time
                        if responses is not None:
                            messages_list.extend(responses)
                continue
                # return messages_list

            call_expr = fun_handle_message.parent  # children[0] = fun_handle_message
            if call_expr.name not in ('CallExpression', 'TaggedTemplateExpression'):
                if call_expr.name == 'VariableDeclarator':
                    # Case where the callback is stored in an alias, e.g., resp = sendResponse
                    if len(call_expr.children) > 0:
                        responses = find_callback_call(call_expr.children[0], visited)
                        if responses is not None:
                            messages_list.extend(responses)
                else:
                    logging.error('Expected a CallExpression node, got a %s node', call_expr.name)
            if len(call_expr.children) > 1:
                # as callback might be called without a parameter: sendResponse()
                messages_list.append(call_expr.children[1])  # children[1] = params[0] = message
        return messages_list

    logging.error('The callback %s has been called %s times...', handle_callback.id,
                  len(handle_callback.data_dep_children))
    return None


def find_promise_resolve(node):
    """ Finds the CallExpr Promise.resolve if any, and returns it in the 2nd position. """

    if node.name in ('CallExpression', 'TaggedTemplateExpression'):
        if len(node.children) > 0 and node.children[0].body in ('callee', 'tag'):
            callee = node.children[0]
            call_expr_value = get_node_computed_value_e(callee)
            if isinstance(call_expr_value, str) and 'Promise.resolve' in call_expr_value:
                return True, node

    for child in node.children:
        found, promise = find_promise_resolve(child)
        if found:
            return True, promise

    return False, None


def browser_runtime_sendMessage(node, mess_type_from):
    """ Handling browser_runtime_sendMessage. """

    if 'then' not in node.value:  # Message sent
        logging.debug('A browser_runtime_sendMessage message was sent')
        # Params can be (mess), (extensionId, mess), (extensionId, mess, options)
        if len(node.children) == 2:  # Number of children = CallExpr name + number parameters
            message = node.children[1]  # (mess)
        elif len(node.children) == 3:
            message = node.children[2]  # (extensionId, mess) Note: (mess, options) could happen
        elif len(node.children) == 4:
            message = node.children[2]  # (extensionId, mess, options)
        else:
            logging.error('browser_runtime_sendMessage has %s children', len(node.children) - 1)
            message = None

        # Sent a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_sent(mess_type_from, message=message, api_message=message_api)

    else:  # Got a response to the message sent
        logging.debug('A browser_runtime_sendMessage message got a response')
        # Format: .then(handleResponse, handleError)
        handle_response = node.children[1]  # Either a FunExpr or a callback
        response, _ = find_callback_def(handle_response, param_nb=0)  # First param = handleResponse

        # Got a response
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_got_response(mess_type_from, message=response, api_message=message_api)


def browser_runtime_connect(node, mess_type_from):
    """ API to get the port for long-term communication. """

    logging.debug('Handling browser_runtime_connect')
    callee = node.children[0]
    call_expr_value = get_node_computed_value_e(callee)
    if '.connect(' in call_expr_value:  # Otherwise could confound, e.g., connectNative with connect
        if '.postMessage' in call_expr_value:  # port.postMessage
            post_message(node, mess_type_from)
        elif '.onMessage.addListener' in call_expr_value:  # port.onMessage.addListener
            onMessage_addListener(node, mess_type_from)


def browser_tabs_sendMessage(node, mess_type_from):
    """ Handling browser_tabs_sendMessage. """

    if 'then' not in node.value:  # Message sent
        logging.debug('Handling browser_tabs_sendMessage')
        # Param can be (tabId, message, options), (tabId, message)
        if len(node.children) <= 4:
            message = node.children[2]
            # Sent a message
            message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
            messages.add_sent(mess_type_from, message=message, api_message=message_api)
        else:
            logging.error('browser_tabs_sendMessage has %s children', len(node.children) - 1)

    else:  # Got a response to the message sent
        logging.debug('A browser_tabs_sendMessage message got a response')
        # Format: .then(handleResponse, handleError)
        handle_response = node.children[1]  # Either a FunExpr or a callback
        response, _ = find_callback_def(handle_response, param_nb=0)  # First param = handleResponse

        # Got a response
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_got_response(mess_type_from, message=response, api_message=message_api)


def browser_tabs_connect(node, mess_type_from):
    """ API to get the port for long-term communication. """

    logging.debug('Handling browser_tabs_connect')
    browser_runtime_connect(node, mess_type_from)


def onMessage_addListener(node, mess_type_from):
    """ Handling onMessage_addListener. """

    logging.debug('Handling onMessage_addListener')
    # Param is (message)
    if len(node.children) == 2:  # Number of children = CallExpr name + number parameters
        callee = node.children[0]
        call_expr_value = get_node_computed_value_e(callee)
        if '.connect' in call_expr_value:
            if '.connect(' in call_expr_value:  # To avoid confounding connectNative with connect
                listener = node.children[1]  # listener is a callback function
                message, _ = find_callback_def(listener, param_nb=0)  # Message = first param
            else:
                message = None
        else:
            listener = node.children[1]  # listener is a callback function
            message, _ = find_callback_def(listener, param_nb=0)  # Message = first param

        # Received a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_received(mess_type_from, message=message, api_message=message_api)

    else:
        logging.error('onMessage_addListener has %s children', len(node.children) - 1)


def browser_runtime_onMessage_addListener(node, mess_type_from):
    """ Handling browser_runtime_onMessage_addListener. """

    logging.debug('Handling browser_runtime_onMessage_addListener')
    # Param is (listener)
    if len(node.children) == 2:  # Number of children = CallExpr name + number parameters
        listener = node.children[1]  # listener is a callback function
        # listener params can be (message, sender, sendResponse) or (message, sender) or (message)
        response, _ = find_callback_def(listener, param_nb=0)  # Message = first param
        # Received a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_received(mess_type_from, message=response, api_message=message_api)

        send_response, fun_handler = find_callback_def(listener, param_nb=2)
        # Handled exception if < 2 params
        if send_response is not None:  # There may be a response with the listener 3rd param
            send_response = find_callback_call(send_response, set())
            if send_response is not None:
                for send_response1 in send_response:
                    # Responded
                    message_api = messages.MessageApi(api_value=node.value,
                                                      api_line=node.get_line())
                    messages.add_responded(mess_type_from, message=send_response1,
                                           api_message=message_api)
                return send_response

        if send_response is None and fun_handler is not None:
            # There may be a response with Promise.resolve
            _, send_response = find_promise_resolve(fun_handler)  # CallExpr
            if send_response is not None:
                send_response = send_response.children[1]  # CallExpr arg = response
                # Responded
                message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
                messages.add_responded(mess_type_from, message=send_response,
                                       api_message=message_api)
                return send_response
        return None

    logging.error('browser_runtime_onMessage_addListener has %s children',
                  len(node.children) - 1)
    return None


def browser_runtime_onConnect_addListener(node, mess_type_from):
    """ API to get the port for long-term communication. """

    logging.debug('Handling browser_runtime_onConnect_addListener')
    """
    # Param is (listener)
    if len(node.children) == 2:  # Number of children = CallExpr name + number parameters
        listener = node.children[1]  # listener is a callback function on the port
        port, _ = find_callback_def(listener, param_nb=0)  # Port = first param
        print(port.attributes)
    logging.error('browser_runtime_onConnect_addListener has %s children', len(node.children) - 1)
    """
    # Complicated as port can be stored in a global variable


def post_message(node, mess_type_from):
    """ Handling postMessage. """

    # 2 possibilities:
    # - WA-CS: window.postMessage, postMessage, event.source.postMessage
    # - long-term (2): port.postMessage

    logging.debug('Handling postMessage')
    # Param is (message, targetOrigin, [transfer])
    if len(node.children) >= 2:  # Number of children = CallExpr name + number parameters
        callee = node.children[0]
        call_expr_value = get_node_computed_value_e(callee)
        if '.connect' in call_expr_value:
            if '.connect(' in call_expr_value:  # To avoid confounding connectNative with connect
                message = node.children[1]
            else:
                message = None
        else:
            message = node.children[1]
        # Sent a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_sent(mess_type_from, message=message, api_message=message_api)
    else:
        logging.error('postMessage has %s children', len(node.children) - 1)


def add_event_listener(node, mess_type_from):
    """ Handling addEventListener. """

    logging.debug('Handling addEventListener')
    global_obj = ['window', 'this', 'that', 'self', 'top', 'global', 'source']
    call_expr_value = node.value

    if '.addEventListener' not in call_expr_value or '.addEventListener' in call_expr_value \
            and (any(g in call_expr_value for g in global_obj)):
        # Param is ('message', listener, [options])
        if len(node.children) >= 3:  # Number of children = CallExpr name + number parameters
            if get_node_computed_value_e(node.children[1]) != 'message':
                logging.debug('The addEventListener is not listening on incoming messages')
            else:
                listener = node.children[2]
                response, _ = find_callback_def(listener, param_nb=0)  # Message = first param
                # Received a message
                message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
                messages.add_received(mess_type_from, message=response, api_message=message_api)

        else:
            logging.error('addEventListener has %s children', len(node.children) - 1)
    else:
        logging.debug('The addEventListener is not the global one, but %s', call_expr_value)


def onmessage(node, mess_type_from):
    """ Handling onmessage. """

    logging.debug('Handling onmessage')
    # Param is (event) and node already a (Arrow)FunctionExpression/Declaration
    response, _ = find_callback_def(node, param_nb=0)  # Message = first param
    # Received a message
    message_api = messages.MessageApi(api_value='onmessage', api_line=node.get_line())
    messages.add_received(mess_type_from, message=response, api_message=message_api)


def browser_runtime_onMessageExternal_addListener(node, mess_type_from):
    """ Handling browser_runtime_onMessageExternal_addListener. """

    logging.debug('Handling browser_runtime_onMessageExternal_addListener')
    browser_runtime_onMessage_addListener(node, mess_type_from)  # Exactly the same


def browser_runtime_onConnectExternal_addListener(node, mess_type_from):
    """ Handling browser_runtime_onConnectExternal_addListener. """

    logging.debug('Handling browser_runtime_onConnectExternal_addListener')
    while node.name != 'Program':
        node = node.parent
    # An onConnectExternal node exists
    setattr(node, 'onconnectexternal', True)  # Stored as attribute of graph root


def chrome_runtime_sendMessage(node, mess_type_from):
    """ Handling chrome_runtime_sendMessage. """

    logging.debug('Handling chrome_runtime_sendMessage')

    callback_response = node.children[-1]
    response, _ = find_callback_def(callback_response, param_nb=0)  # Message = only param
    # Got a response
    message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
    messages.add_got_response(mess_type_from, message=response, api_message=message_api)

    resp = False
    if response is not None:
        resp = True

    # Params can be (mess), (extensionId, mess), (extensionId, mess, options)
    # (mess, r), (extensionId, mess, r), (extensionId, mess, options, r)
    # Actually, (mess, options) could happen but only found once
    # (mess, options, r) could happen too, but did not find any extensions

    # Number of children = CallExpr name + number parameters
    if not resp and len(node.children) == 2 or resp and len(node.children) == 3:
        message = node.children[1]  # (mess (, r))
    elif not resp and len(node.children) == 3 or resp and len(node.children) == 4:
        message = node.children[2]  # (extensionId, mess (, r))
    elif not resp and len(node.children) == 4 or resp and len(node.children) == 5:
        message = node.children[2]  # (extensionId, mess, options (, r))
    else:
        logging.error('chrome_runtime_sendMessage has %s children', len(node.children) - 1)
        message = None

    message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
    messages.add_sent(mess_type_from, message=message, api_message=message_api)  # Sent a message


def chrome_runtime_sendRequest(node, mess_type_from):
    """ Handling chrome_runtime_sendRequest. """

    logging.debug('Handling chrome_runtime_sendRequest')

    callback_response = node.children[-1]
    response, _ = find_callback_def(callback_response, param_nb=0)  # Message = only param
    # Got a response
    message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
    messages.add_got_response(mess_type_from, message=response, api_message=message_api)

    resp = False
    if response is not None:
        resp = True

    # Params can be (mess), (extensionId, mess), (mess, r), (extensionId, mess, r)

    # Number of children = CallExpr name + number parameters
    if not resp and len(node.children) == 2 or resp and len(node.children) == 3:
        message = node.children[1]  # (mess (, r))
    elif not resp and len(node.children) == 3 or resp and len(node.children) == 4:
        message = node.children[2]  # (extensionId, mess (, r))
    else:
        logging.error('chrome_runtime_sendRequest has %s children', len(node.children) - 1)
        message = None

    message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
    messages.add_sent(mess_type_from, message=message, api_message=message_api)  # Sent a message


def chrome_runtime_connect(node, mess_type_from):
    """ Handling chrome_runtime_connect. """

    logging.debug('Handling chrome_runtime_connect')
    browser_runtime_connect(node, mess_type_from)


def chrome_tabs_sendMessage(node, mess_type_from):
    """ Handling chrome_tabs_sendMessage. """

    logging.debug('Handling chrome_tabs_sendMessage')

    # Param can be (tabId, message, options), (tabId, message)
    # (tabId, message, options, r), (tabId, message, r)
    if len(node.children) < 3:
        return
    if len(node.children) <= 5:
        message = node.children[2]
        # Sent a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_sent(mess_type_from, message=message, api_message=message_api)

        if len(node.children) > 3:  # To ensure that we do not consider the message received
            callback_response = node.children[-1]
            response, _ = find_callback_def(callback_response, param_nb=0)  # Message = only param
            # Got a response
            message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
            messages.add_got_response(mess_type_from, message=response, api_message=message_api)

    else:
        logging.error('chrome_tabs_sendMessage has %s children', len(node.children) - 1)


def chrome_tabs_sendRequest(node, mess_type_from):
    """ Handling chrome_tabs_sendRequest. """

    logging.debug('Handling chrome_tabs_sendRequest')

    # Param can be (tabId, message), (tabId, message, r)
    if len(node.children) <= 4:
        message = node.children[2]
        # Sent a message
        message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
        messages.add_sent(mess_type_from, message=message, api_message=message_api)

        if len(node.children) == 4:
            callback_response = node.children[3]
            response, _ = find_callback_def(callback_response, param_nb=0)  # Message = only param
            # Got a response
            message_api = messages.MessageApi(api_value=node.value, api_line=node.get_line())
            messages.add_got_response(mess_type_from, message=response, api_message=message_api)

    else:
        logging.error('chrome_tabs_sendRequest has %s children', len(node.children) - 1)


def chrome_tabs_connect(node, mess_type_from):
    """ Handling chrome_tabs_connect. """

    logging.debug('Handling chrome_tabs_connect')
    browser_tabs_connect(node, mess_type_from)


def chrome_runtime_onMessage_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onMessage_addListener. """

    logging.debug('Handling chrome_runtime_onMessage_addListener')
    browser_runtime_onMessage_addListener(node, mess_type_from)


def chrome_runtime_onRequest_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onRequest_addListener. """

    logging.debug('Handling chrome_runtime_onRequest_addListener')
    browser_runtime_onMessage_addListener(node, mess_type_from)


def chrome_runtime_onConnect_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onConnect_addListener. """

    logging.debug('Handling chrome_runtime_onConnect_addListener')


def chrome_runtime_onMessageExternal_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onMessageExternal_addListener. """

    logging.debug('Handling chrome_runtime_onMessageExternal_addListener')
    chrome_runtime_onMessage_addListener(node, mess_type_from)


def chrome_runtime_onRequestExternal_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onRequestExternal_addListener. """

    logging.debug('Handling chrome_runtime_onRequestExternal_addListener')
    chrome_runtime_onMessage_addListener(node, mess_type_from)


def chrome_runtime_onConnectExternal_addListener(node, mess_type_from):
    """ Handling chrome_runtime_onConnectExternal_addListener. """

    logging.debug('Handling chrome_runtime_onConnectExternal_addListener')
    browser_runtime_onConnectExternal_addListener(node, mess_type_from)


def do_nothing(nothing1, nothing2):
    """ Does nothing. """

    pass


def search_depreciated_apis(node, depreciated_apis):
    """ Some other (depreciated APIs) may be used, such as chrome.extension.onRequest.
    Collecting them here for further analysis. """

    runtime = ('onMessage', 'sendMessage', 'onMessageExternal', 'onConnect', 'connect',
               'onConnectExternal')
    extension = ('onRequest', 'sendRequest', 'onRequestExternal')

    for child in node.children:
        if child.name in ('CallExpression', 'TaggedTemplateExpression'):
            if len(child.children) > 0 and child.children[0].body in ('callee', 'tag'):
                callee = child.children[0]
                call_expr_value = get_node_computed_value_e(callee)
                if isinstance(call_expr_value, str):  # No need to check if it is not a str
                    call_expr_value_all = get_node_computed_value_e(child)
                    if 'chrome.extension' in call_expr_value\
                            and (any(api in call_expr_value for api in runtime)
                                 or any(api in call_expr_value for api in extension)):
                        depreciated_apis.append(call_expr_value_all)
                    elif 'chrome.runtime' in call_expr_value\
                            and any(api in call_expr_value for api in extension):
                        depreciated_apis.append(call_expr_value_all)
                    elif 'chrome.tabs.sendRequest' in call_expr_value:
                        depreciated_apis.append(call_expr_value_all)

        search_depreciated_apis(child, depreciated_apis)
