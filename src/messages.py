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
    Definition of the classes MessageAPI, Messages, and MessageType with its subclasses
    AppAndCs, CsAndBp, and WaAndBp  to represent the different messages exchanged between:
        - web application and content script;
        - content script and background page;
        - web application and background page.
"""

import logging

from get_pdg import get_node_computed_value_e


class MessageApi:
    """ To store the message API with the line number. """

    def __init__(self, api_value, api_line):
        self.api_value = api_value
        self.api_line = api_line


class Messages:
    """ To store the different messages depending on sent/got_response/received/responded. """

    def __init__(self, mess_type_name):
        self.mess_type_name = mess_type_name
        self.sent = []
        self.api_sent = []
        self.got_response = []  # Sent a message and got a response
        self.api_got_response = []
        self.received = []
        self.api_received = []
        self.responded = []  # Received a message and responded
        self.api_responded = []

    def is_empty(self):
        """ Checks if the Messages object is empty, i.e., nothing sent nor received. """
        if not self.sent and not self.got_response and not self.received and not self.responded:
            return True
        return False

    def __print__(self):
        """ To debug, prints the content of a Messages object. """
        print('\tSent:')
        for el in self.sent:
            print('\t\t' + str(get_node_computed_value_e(el)))
        print('\tGot response:')
        for el in self.got_response:
            print('\t\t' + str(get_node_computed_value_e(el)))
        print('\tReceived:')
        for el in self.received:
            print('\t\t' + str(get_node_computed_value_e(el)))
        print('\tResponded:')
        for el in self.responded:
            print('\t\t' + str(get_node_computed_value_e(el)))

    def __to_dict__(self, my_dict):
        """ To debug, stored the content of a Messages object in a dict. """
        my_dict['sent'] = self.sent
        my_dict['api-sent'] = [(el.api_value, el.api_line) for el in self.api_sent]
        my_dict['got-response'] = self.got_response
        my_dict['api-got-response'] = [(el.api_value, el.api_line) for el in self.api_got_response]
        my_dict['received'] = self.received
        my_dict['api-received'] = [(el.api_value, el.api_line) for el in self.api_received]
        my_dict['responded'] = self.responded
        my_dict['api-responded'] = [(el.api_value, el.api_line) for el in self.api_responded]


class MessageType:
    """ To store the message characteristics per message type so that messages belonging to
    the same category are directly stored together. """

    def __init__(self, name):
        self.name = name  # category = message type

    @staticmethod
    def initiate_channel_dict(my_dict, channel_key, channel_name):
        """
        Initiates a channel dict.
        :param my_dict: dict, contains the messages detected so far;
        :param channel_key: str ('WA_CS', 'CS_BP', or 'WA_BP'), indicates between whom the
        messages are exchanged;
        :param channel_name: str (e.g., 'C', 'C1', 'C2', 'B'), indicates the channel.
        :return: dict, extended with the channel_key and channel_name.
        """
        if channel_key not in my_dict:
            my_dict[channel_key] = {channel_name: {}}
        else:
            if channel_name in my_dict[channel_key]:
                logging.error('Will overwrite %s with {}', my_dict[channel_key][channel_name])
            my_dict[channel_key][channel_name] = {}
        return my_dict[channel_key][channel_name]


def add_sent(where, message, api_message):
    """ Adds the message message sent by where to where's messages' sent list. """

    if message is not None:
        if isinstance(message, list):
            for m in message:
                add_sent(where, m, api_message)
        else:
            where.sent.append(message)
            where.api_sent.append(api_message)


def add_got_response(where, message, api_message):
    """ Adds the message message received by where to where's messages' received response list. """

    if message is not None:
        where.got_response.append(message)
        where.api_got_response.append(api_message)


def add_received(where, message, api_message):
    """ Adds the message message received by where to where's messages' received list. """

    if message is not None:
        where.received.append(message)
        where.api_received.append(api_message)


def add_responded(where, message, api_message):
    """ Adds the message message sent by where to where's messages' sent response list. """

    if message is not None:
        where.responded.append(message)
        where.api_responded.append(api_message)


class WaAndCs(MessageType):
    """ Messages exchanged between the web application and the content script. """

    def __init__(self, name):
        MessageType.__init__(self, name)
        self.wa = Messages(name)
        self.cs = Messages(name)

    def __print__(self):
        """ To debug, prints the content of the messages exchanged. """
        if self.name != 'Trash' and (not self.wa.is_empty() or not self.cs.is_empty()):
            print('Name: ' + self.name)
            print('WA')
            self.wa.__print__()
            print('CS')
            self.cs.__print__()

    def __to_dict__(self, my_dict):
        """ To debug, stores the content of the messages exchanged in a dict. """
        if self.name != 'Trash' and (not self.wa.is_empty() or not self.cs.is_empty()):
            channel_key = 'WA_CS'
            channel_dict = self.initiate_channel_dict(my_dict, channel_key, channel_name=self.name)
            wa_dict = channel_dict['WA'] = {}
            self.wa.__to_dict__(wa_dict)
            cs_dict = channel_dict['CS'] = {}
            self.cs.__to_dict__(cs_dict)


class CsAndBp(MessageType):
    """ Messages exchanged between the content script and the background page. """

    def __init__(self, name):
        MessageType.__init__(self, name)
        self.cs = Messages(name)
        self.bp = Messages(name)

    def __print__(self):
        """ To debug, prints the content of the messages exchanged. """
        if self.name != 'Trash':
            print('Name: ' + self.name)
            print('CS')
            self.cs.__print__()
            print('BP')
            self.bp.__print__()

    def __to_dict__(self, my_dict):
        """ To debug, stores the content of the messages exchanged in a dict. """
        if self.name != 'Trash':
            channel_key = 'CS_BP'
            channel_dict = self.initiate_channel_dict(my_dict, channel_key, channel_name=self.name)
            cs_dict = channel_dict['CS'] = {}
            self.cs.__to_dict__(cs_dict)
            bp_dict = channel_dict['BP'] = {}
            self.bp.__to_dict__(bp_dict)


class WaAndBp(MessageType):
    """ Messages exchanged between the web application and the background page. """

    def __init__(self, name):
        MessageType.__init__(self, name)
        self.wa = Messages(name)
        self.bp = Messages(name)

    def __print__(self):
        """ To debug, prints the content of the messages exchanged. """
        if self.name != 'Trash' and (not self.wa.is_empty() or not self.bp.is_empty()):
            print('Name: ' + self.name)
            print('WA')
            self.wa.__print__()
            print('BP')
            self.bp.__print__()

    def __to_dict__(self, my_dict):
        """ To debug, stores the content of the messages exchanged in a dict. """
        if self.name != 'Trash' and (not self.wa.is_empty() or not self.bp.is_empty()):
            channel_key = 'WA_BP'
            channel_dict = self.initiate_channel_dict(my_dict, channel_key, channel_name=self.name)
            wa_dict = channel_dict['WA'] = {}
            self.wa.__to_dict__(wa_dict)
            bp_dict = channel_dict['BP'] = {}
            self.bp.__to_dict__(bp_dict)
