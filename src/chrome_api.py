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
    Message passing APIs for Chromium-based extensions.
"""

import browser_api
import handle_messages as m

GLOBAL_PM = browser_api.GLOBAL_PM


def global_post_message(node_value):
    """ Checks if the postMessage is the window.postMessage (WA - CS communication). """

    if any(pm in node_value for pm in GLOBAL_PM):
        return {'mess_type': 'C', 'fun': m.post_message}  # Sends
    if '.postMessage' in node_value:
        return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing as port.PM
    return {'mess_type': 'C', 'fun': m.post_message}  # Sends


def port_post_message(node_value):
    """ Checks if the postMessage is the port.postMessage (WA - BP and CS - BP communication). """

    if any(pm in node_value for pm in GLOBAL_PM):
        return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing, wrong PM
    if '.postMessage' in node_value:
        return {'mess_type': 'C2', 'fun': m.post_message}  # port.postMessage to send messages
    return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing, wrong PM


CS2BP = {'chrome.runtime.sendMessage': {'mess_type': 'C1',
                                        'fun': m.chrome_runtime_sendMessage},  # Sends
         'chrome.runtime.connect': {'mess_type': 'C2',
                                    'fun': m.chrome_runtime_connect},  # Gets port + message
         'chrome.extension.sendMessage': {'mess_type': 'C1',
                                          'fun': m.chrome_runtime_sendMessage},  # Sends
         'chrome.extension.connect': {'mess_type': 'C2',
                                      'fun': m.chrome_runtime_connect},  # Gets port + message
         'chrome.runtime.sendRequest': {'mess_type': 'C1-d',
                                        'fun': m.chrome_runtime_sendRequest},  # Sends
         'chrome.extension.sendRequest': {'mess_type': 'C1-d',
                                          'fun': m.chrome_runtime_sendRequest}}  # Sends

BP2CS = {'chrome.tabs.sendMessage': {'mess_type': 'C1',
                                     'fun': m.chrome_tabs_sendMessage},  # Sends
         'chrome.tabs.connect': {'mess_type': 'C2',
                                 'fun': m.chrome_tabs_connect},  # Gets port + message
         'chrome.tabs.sendRequest': {'mess_type': 'C1-d',
                                     'fun': m.chrome_tabs_sendRequest}}  # Sends

CS_BP = {'chrome.runtime.onMessage.addListener': {'mess_type': 'C1',
                                                  'fun': m.chrome_runtime_onMessage_addListener},
         '}.runtime.onMessage.addListener': {'mess_type': 'C1',
                                             'fun': m.chrome_runtime_onMessage_addListener},
         # Receives
         'chrome.runtime.onConnect.addListener': {'mess_type': 'C2',
                                                  'fun': m.chrome_runtime_onConnect_addListener},
         'chrome.extension.onMessage.addListener': {'mess_type': 'C1',
                                                    'fun': m.chrome_runtime_onMessage_addListener},
         '}.extension.onMessage.addListener': {'mess_type': 'C1',
                                               'fun': m.chrome_runtime_onMessage_addListener},
         # Receives
         'chrome.extension.onConnect.addListener': {'mess_type': 'C2',
                                                    'fun': m.chrome_runtime_onConnect_addListener},
         'chrome.runtime.onRequest.addListener': {'mess_type': 'C1-d',
                                                  'fun': m.chrome_runtime_onRequest_addListener},
         '}.runtime.onRequest.addListener': {'mess_type': 'C1-d',
                                             'fun': m.chrome_runtime_onRequest_addListener},
         'chrome.extension.onRequest.addListener': {'mess_type': 'C1-d',
                                                    'fun': m.chrome_runtime_onRequest_addListener},
         '}.extension.onRequest.addListener': {'mess_type': 'C1-d',
                                               'fun': m.chrome_runtime_onRequest_addListener},
         # Gets port --> port.postMessage / port.onMessage.addListener
         'postMessage': False,  # Checks which postMessage
         # port.onMessage.addListener to receive messages
         '.onMessage.addListener': {'mess_type': 'C2',
                                    'fun': m.onMessage_addListener}}

WA_CS = {'postMessage': True,  # Checks which postMessage
         'addEventListener': {'mess_type': 'C', 'fun': m.add_event_listener},  # Receives
         'onmessage': {'mess_type': 'C', 'fun': m.onmessage}}  # Receives

WA2BP = {'chrome.runtime.sendMessage': {'mess_type': 'C1',
                                        'fun': m.chrome_runtime_sendMessage},  # Sends
         'chrome.extension.sendMessage': {'mess_type': 'C1',
                                          'fun': m.chrome_runtime_sendMessage},  # Sends
         'chrome.runtime.sendRequest': {'mess_type': 'C1-d',
                                        'fun': m.chrome_runtime_sendRequest},  # Sends
         'chrome.extension.sendRequest': {'mess_type': 'C1-d',
                                          'fun': m.chrome_runtime_sendRequest},  # Sends
         'chrome.runtime.connect': {'mess_type': 'C2',
                                    'fun': m.chrome_runtime_connect},  # Gets port + message
         'chrome.extension.connect': {'mess_type': 'C2',
                                      'fun': m.chrome_runtime_connect}}  # Gets port + message

BP2WA = {'chrome.runtime.onMessageExternal.addListener':
             {'mess_type': 'C1', 'fun': m.chrome_runtime_onMessageExternal_addListener},  # Receives
         '}.runtime.onMessageExternal.addListener':
             {'mess_type': 'C1', 'fun': m.chrome_runtime_onMessageExternal_addListener},  # Receives
         'chrome.runtime.onConnectExternal.addListener':
             {'mess_type': 'C2', 'fun': m.chrome_runtime_onConnectExternal_addListener},  # Get port
         'chrome.extension.onMessageExternal.addListener':
             {'mess_type': 'C1', 'fun': m.chrome_runtime_onMessageExternal_addListener},  # Receives
         '}.extension.onMessageExternal.addListener':
             {'mess_type': 'C1', 'fun': m.chrome_runtime_onMessageExternal_addListener},  # Receives
         'chrome.extension.onConnectExternal.addListener':
             {'mess_type': 'C2', 'fun': m.chrome_runtime_onConnectExternal_addListener},  # Get port
         'chrome.runtime.onRequestExternal.addListener':
             {'mess_type': 'C1-d', 'fun': m.chrome_runtime_onRequestExternal_addListener},  # Receiv
         '}.runtime.onRequestExternal.addListener':
             {'mess_type': 'C1-d', 'fun': m.chrome_runtime_onRequestExternal_addListener},  # Receiv
         'chrome.extension.onRequestExternal.addListener':
             {'mess_type': 'C1-d', 'fun': m.chrome_runtime_onRequestExternal_addListener},  # Receiv
         '}.extension.onRequestExternal.addListener':
             {'mess_type': 'C1-d', 'fun': m.chrome_runtime_onRequestExternal_addListener},  # Receiv
         'postMessage': False,  # Checks which postMessage
         '.runtime.onMessage.addListener': {'mess_type': 'Trash', 'fun': m.do_nothing},
         '.extension.onMessage.addListener': {'mess_type': 'Trash', 'fun': m.do_nothing},
         # So that cannot be confounded with .onMessage.addListener
         # port.onMessage.addListener to receive messages
         '.onMessage.addListener': {'mess_type': 'C2', 'fun': m.onMessage_addListener}}

# C1: Chrome one-time channel
# C2: Chrome long-lived channel
# Trash: Empty, just to ensure that we are not matching wrong substrings
