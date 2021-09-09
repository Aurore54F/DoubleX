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
    Communication with an attacker (web application / another extension).
"""

import logging

import pdg_js.utility_df as utility_df

import extension_communication


class WaCommunication:
    """ Elements from the web application or sent back to the web application. """

    def __init__(self):
        self.received_list = []  # Messages sent from the web application
        self.sent_list = []  # Messages sent to the web application

    def add_received(self, content):
        self.received_list.extend(content)

    def add_sent(self, content):
        self.sent_list.extend(content)


def web_app_communication(pdg, whoami, with_wa, chrome, messages_dict=None):
    """ Returns the messages received and sent by whoami (communication with WA). """

    messages_list = []  # Collects the messages sent from the WA to whoami and the other way around
    channel = whoami + '2wa'  # whoami is communicating with the WA

    # Exchanged messages
    extension_communication.find_all_messages(pdg, messages_list, where=channel, chrome=chrome)

    onconnectexternal = False
    if whoami == 'bp':
        if hasattr(pdg, 'onconnectexternal'):  # Found an onConnectExternal node
            onconnectexternal = True

    for message in messages_list:
        if whoami == 'cs' or '2' not in message.name or whoami == 'bp' and onconnectexternal:
            # We are here if: 1) we are in the CS or 2) consider a short-lived connection in the BP,
            # or 3) consider a long-lived connection in the BP, i.e., with onConnectExternal
            # (Avoids FPs due to confusions between onConnect and onConnectExternal in the BP,
            # due to the port given as callback parameter)

            # message.__print__()  # For debug
            if messages_dict is not None:
                try:
                    message.__to_dict__(messages_dict)  # Stores communication in messages_dict
                except utility_df.Timeout.Timeout as e:
                    raise e  # Will be caught in vulnerability_detection
                except Exception:
                    logging.exception('Could not store the extensions messages in a dict')

            collected_messages = extension_communication.message_type_from(message, channel)
            with_wa.add_sent(collected_messages.sent)
            with_wa.add_received(collected_messages.received)
            with_wa.add_sent(collected_messages.responded)
            with_wa.add_received(collected_messages.got_response)
