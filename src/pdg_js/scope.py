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
    Definition of class Scope to handle JS scoping rules.
"""

import copy


class Scope:
    """ To apply JS scoping rules. """

    def __init__(self, name=''):
        self.name = name
        self.var_list = []
        self.var_if2_list = []  # Specific to if constructs with 2 possible variables at the end
        self.unknown_var = set()  # Unknown variable in a given scope
        self.function = None
        self.bloc = False  # Indicates if we are in a block statement
        self.need_to_recompute_var_list = True
        self.id_name_list = set()

    def set_name(self, name):
        self.name = name

    def set_var_list(self, var_list):
        self.var_list = var_list
        self.need_to_recompute_var_list = True

    def set_var_if2_list(self, var_if2_list):
        self.var_if2_list = var_if2_list

    def set_unknown_var(self, unknown_var):
        self.unknown_var = unknown_var

    def set_function(self, function):
        self.function = function

    def add_var(self, identifier_node):
        self.var_list.append(identifier_node)
        self.need_to_recompute_var_list = True
        self.var_if2_list.append(None)

    def add_unknown_var(self, unknown):
        self.unknown_var.add(unknown)  # Set avoids duplicates

    def remove_unknown_var(self, unknown):
        self.unknown_var.remove(unknown)

    def update_var(self, index, identifier_node):
        self.var_list[index] = identifier_node
        self.need_to_recompute_var_list = True
        self.var_if2_list[index] = None

    def update_var_if2(self, index, identifier_node_list):
        self.var_if2_list[index] = identifier_node_list

    def add_var_if2(self, index, identifier_node):
        if not isinstance(self.var_if2_list[index], list):
            self.var_if2_list[index] = []
        self.var_if2_list[index].append(identifier_node)

    def is_equal(self, var_list2):
        if self.var_list == var_list2.var_list and self.var_if2_list == var_list2.var_if2_list:
            return True
        return False

    def copy_scope(self):
        scope = Scope()
        scope.set_name(copy.copy(self.name))
        scope.set_var_list(copy.copy(self.var_list))
        scope.set_var_if2_list(copy.copy(self.var_if2_list))
        scope.set_unknown_var(copy.copy(self.unknown_var))
        scope.set_function(copy.copy(self.function))
        return scope

    def get_pos_identifier(self, identifier_node):
        tmp_list = None
        if self.need_to_recompute_var_list:
            tmp_list = [elt.attributes['name'] for elt in self.var_list]
            self.id_name_list = set(tmp_list)
            self.need_to_recompute_var_list = False
        var_name = identifier_node.attributes['name']
        if var_name in self.id_name_list:
            if tmp_list is None:
                tmp_list = [elt.attributes['name'] for elt in self.var_list]
            return tmp_list.index(var_name)  # Position of identifier_node in var_list
        return None  # None if it is not in the list

    def set_in_bloc(self, bloc):
        self.bloc = bloc
