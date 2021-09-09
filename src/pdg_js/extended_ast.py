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
    Definition of the class ExtendedAst: corresponds to the output of Esprima's parse function
    with the arguments: {range: true, loc: true, tokens: true, tolerant: true, comment: true}.
"""

# Note: slightly improved from HideNoSeek


class ExtendedAst:
    """ Stores the Esprima formatted AST into python objects. """

    def __init__(self):
        self.type = None
        self.filename = ''
        self.body = []
        self.source_type = None
        self.range = []
        self.comments = []
        self.tokens = []
        self.leading_comments = []

    def get_type(self):
        return self.type

    def set_type(self, root):
        self.type = root

    def get_body(self):
        return self.body

    def set_body(self, body):
        self.body = body

    def get_extended_ast(self):
        return {'type': self.get_type(), 'body': self.get_body(),
                'sourceType': self.get_source_type(), 'range': self.get_range(),
                'comments': self.get_comments(), 'tokens': self.get_tokens(),
                'filename': self.filename,
                'leadingComments': self.get_leading_comments()}

    def get_ast(self):
        return {'type': self.get_type(), 'body': self.get_body(), 'filename': self.filename}

    def get_source_type(self):
        return self.source_type

    def set_source_type(self, source_type):
        self.source_type = source_type

    def get_range(self):
        return self.range

    def set_range(self, ast_range):
        self.range = ast_range

    def get_comments(self):
        return self.comments

    def set_comments(self, comments):
        self.comments = comments

    def get_tokens(self):
        return self.tokens

    def set_tokens(self, tokens):
        self.tokens = tokens

    def get_leading_comments(self):
        return self.leading_comments

    def set_leading_comments(self, leading_comments):
        self.leading_comments = leading_comments
