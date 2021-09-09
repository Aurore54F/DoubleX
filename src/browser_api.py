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
    Message passing APIs for all browsers except Chromium based.
"""

import handle_messages as m

GLOBAL_PM = ['window.postMessage', 'this.postMessage', 'that.postMessage', 'self.postMessage',
             'top.postMessage', 'global.postMessage', '.source.postMessage']


def global_post_message(node_value):
    """ Checks if the postMessage is the window.postMessage (WA - CS communication). """

    if any(pm in node_value for pm in GLOBAL_PM):
        return {'mess_type': 'B', 'fun': m.post_message}  # Sends
    if '.postMessage' in node_value:
        return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing as port.PM
    return {'mess_type': 'B', 'fun': m.post_message}  # Sends


def port_post_message(node_value):
    """ Checks if the postMessage is the port.postMessage (WA - BP and CS - BP communication). """

    if any(pm in node_value for pm in GLOBAL_PM):
        return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing, wrong PM
    if '.postMessage' in node_value:
        return {'mess_type': 'B2', 'fun': m.post_message}  # port.postMessage to send messages
    return {'mess_type': 'Trash', 'fun': m.do_nothing}  # Do nothing, wrong PM


CS2BP = {'browser.runtime.sendMessage': {'mess_type': 'B1',
                                         'fun': m.browser_runtime_sendMessage},  # Sends
         'browser.runtime.connect': {'mess_type': 'B2',
                                     'fun': m.browser_runtime_connect}}  # Gets port + message

BP2CS = {'browser.tabs.sendMessage': {'mess_type': 'B1',
                                      'fun': m.browser_tabs_sendMessage},  # Sends
         'browser.tabs.connect': {'mess_type': 'B2',
                                  'fun': m.browser_tabs_connect}}  # Gets port + message

CS_BP = {'browser.runtime.onMessage.addListener': {'mess_type': 'B1',
                                                   'fun': m.browser_runtime_onMessage_addListener},
         # Receives
         'browser.runtime.onConnect.addListener': {'mess_type': 'B2',
                                                   'fun': m.browser_runtime_onConnect_addListener},
         # Gets port --> port.postMessage / port.onMessage.addListener
         'postMessage': False,  # Checks which postMessage
         # port.onMessage.addListener to receive messages
         '.onMessage.addListener': {'mess_type': 'B2',
                                    'fun': m.onMessage_addListener}}

WA_CS = {'postMessage': True,  # Checks which postMessage
         'addEventListener': {'mess_type': 'B', 'fun': m.add_event_listener},  # Receives
         'onmessage': {'mess_type': 'B', 'fun': m.onmessage}}  # Receives

WA2BP = {'browser.runtime.sendMessage': {'mess_type': 'B1',
                                         'fun': m.browser_runtime_sendMessage},  # Sends
         'browser.runtime.connect': {'mess_type': 'B2',
                                     'fun': m.browser_runtime_connect}}  # Gets port + message

BP2WA = {'browser.runtime.onMessageExternal.addListener':
             {'mess_type': 'B1', 'fun': m.browser_runtime_onMessageExternal_addListener},  # Receive
         'browser.runtime.onConnectExternal.addListener':
             {'mess_type': 'B2', 'fun': m.browser_runtime_onConnectExternal_addListener},  # Getport
         'postMessage': False,  # Checks which postMessage
         '.runtime.onMessage.addListener': {'mess_type': 'Trash', 'fun': m.do_nothing},
         # So that cannot be confounded with .onMessage.addListener
         # port.onMessage.addListener to receive messages
         '.onMessage.addListener': {'mess_type': 'B2', 'fun': m.onMessage_addListener}}

# B1: Browsers except for chrome one-time channel
# B2: Browsers except for chrome long-lived channel
# Trash: Empty, just to ensure that we are not matching wrong substrings
