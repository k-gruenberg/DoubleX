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
    Definition of classes:
        - Dependence;
        - Node;
        - Value;
        - Identifier(Node, Value);
        - ValueExpr(Node, Value);
        - Statement(Node);
        - ReturnStatement(Statement, Value);
        - Function;
        - FunctionDeclaration(Statement, Function);
        - FunctionExpression(Node, Function)
"""

# Note: going significantly beyond the node structure of HideNoSeek:
# semantic information to the nodes, which have different properties, e.g., DF on Identifier,
# parameter flows, value handling, provenance tracking, etc


import logging
import random
import itertools
import os
import re
from typing import Set, Tuple, Optional, Self, List

from . import utility_df

EXPRESSIONS = ['AssignmentExpression', 'ArrayExpression', 'ArrowFunctionExpression',
               'AwaitExpression', 'BinaryExpression', 'CallExpression', 'ClassExpression',
               'ConditionalExpression', 'FunctionExpression', 'LogicalExpression',
               'MemberExpression', 'NewExpression', 'ObjectExpression', 'SequenceExpression',
               'TaggedTemplateExpression', 'ThisExpression', 'UnaryExpression', 'UpdateExpression',
               'YieldExpression']

EPSILON = ['BlockStatement', 'DebuggerStatement', 'EmptyStatement',
           'ExpressionStatement', 'LabeledStatement', 'ReturnStatement',
           'ThrowStatement', 'WithStatement', 'CatchClause', 'VariableDeclaration',
           'FunctionDeclaration', 'ClassDeclaration']

CONDITIONAL = ['DoWhileStatement', 'ForStatement', 'ForOfStatement', 'ForInStatement',
               'IfStatement', 'SwitchCase', 'SwitchStatement', 'TryStatement',
               'WhileStatement', 'ConditionalExpression']

UNSTRUCTURED = ['BreakStatement', 'ContinueStatement']

STATEMENTS = EPSILON + CONDITIONAL + UNSTRUCTURED
CALL_EXPR = ['CallExpression', 'TaggedTemplateExpression', 'NewExpression']
VALUE_EXPR = ['Literal', 'ArrayExpression', 'ObjectExpression', 'ObjectPattern'] + CALL_EXPR
COMMENTS = ['Line', 'Block']

GLOBAL_VAR = ['window', 'this', 'self', 'top', 'global', 'that']

LIMIT_SIZE = utility_df.LIMIT_SIZE  # To avoid list values with over 1,000 characters


class Dependence:
    """ For control, data, comment, and statement dependencies. """

    def __init__(self, dependency_type, extremity, label, nearest_statement=None):
        self.type = dependency_type
        self.extremity = extremity
        self.nearest_statement = nearest_statement
        self.label = label


class Node:
    """ Defines a Node that is used in the AST. """

    id = random.randint(0, 2*32)  # To limit id collision between 2 ASTs from separate processes

    def __init__(self, name, parent=None, attributes=None):
        self.name = name
        self.id = Node.id
        Node.id += 1
        self.filename = ''
        self.attributes = {} if attributes is None else attributes
        self.body = None
        self.body_list = False
        self.parent = parent
        self.children = []
        self.statement_dep_parents = []
        self.statement_dep_children = []  # Between Statement and their non-Statement descendants
        self.is_wildcard = False  # <== ADDED BY ME

    # ADDED BY ME:
    def __eq__(self, other):
        return self.id == other.id

    # ADDED BY ME: # Otherwise, there's a "TypeError: unhashable type: 'Identifier'" in set_provenance_dd().....
    def __hash__(self):
        return hash(self.id)

    # ADDED BY ME:
    def lhs(self):
        """
        Returns the left of the 2 children of this Node (i.e., the LHS child).
        Raises an Exception when this Node has != 2 children!
        """
        if len(self.children) == 2:
            return self.children[0]
        else:
            raise TypeError(f"calling Node.lhs() on a Node with {len(self.children)} != 2 children")

    # ADDED BY ME:
    def rhs(self):
        """
        Returns the right of the 2 children of this Node (i.e., the RHS child).
        Raises an Exception when this Node has != 2 children!
        """
        if len(self.children) == 2:
            return self.children[1]
        else:
            raise TypeError(f"calling Node.rhs() on a Node with {len(self.children)} != 2 children")

    # ADDED BY ME:
    def equivalent(self, other):
        """
        Unlike == / __eq__, which checks the equality of the node ID, i.e., whether we're talking about the exact same
        subtree, this function tests for structural equivalence, e.g. to detect when an Expression is compared to itself
        as in "if (x + y == x + y) { ... }".

        For Identifiers, names are compared.
        For Literals, raw literal values are compared.
        For BinaryExpressions ('instanceof' | 'in' | '+' | '-' | '*' | '/' | '%' | '**' | '|' | '^' | '&' | '=='
                               | '!=' | '===' | '!==' | '<' | '>' | '<=' | '<<' | '>>' | '>>>'),
            LogicalExpressions ('||' | '&&'),
            UnaryExpressions ('+' | '-' | '~' | '!' | 'delete' | 'void' | 'typeof'),
            AssignmentExpressions ('=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' | '<<=' | '>>=' | '>>>=' | '&='
                                   | '^=' | '|=') and
            UpdateExpressions ('++' | '--'), operators are compared.
        Otherwise, number of children, order of children and child names are compared for equality.

        This method is equivalent to using the matches() method with all match_* arguments set to True
        and all allow_* arguments set to False!
        """
        return self.matches(other,
                            match_identifier_names=True,
                            match_literals=True,
                            match_operators=True,
                            allow_additional_children=False,
                            allow_different_child_order=False)

    # ADDED BY ME:
    def get_data_flow_parents(self, max_depth=1_000_000_000):
        """
        Returns all nodes [p] such that there exist nodes [x1], [x2], ..., [xn] such that:
        [p] --data--> [x1] --data--> [x2] --data--> ... --data--> [xn] --data--> [self]
        where `max_depth` specifies the maximum number of --data--> edges to follow.
        """
        if self.name != "Identifier":
            raise TypeError("get_data_flow_parents() may only be called on Identifiers")

        self_data_dep_parents = {self}
        current_depth = 0
        last_len_self_data_dep_parents = 1
        while current_depth < max_depth:
            for parent1 in self_data_dep_parents.copy():
                self_data_dep_parents.update(grandparent.extremity for grandparent in parent1.data_dep_parents)
                # Note: update() appends multiple elements to a set
            current_depth += 1
            if len(self_data_dep_parents) == last_len_self_data_dep_parents:
                break  # stop as soon a as fixed point has been reached :)
            else:
                last_len_self_data_dep_parents = len(self_data_dep_parents)

        return self_data_dep_parents

    # ADDED BY ME:
    def is_data_flow_equivalent_identifier(self, other, max_depth=1_000_000_000):
        """
        Sometimes, we may want to check equality/equivalence between two different Identifiers beyond just their raw
        variable names. This function returns True if both `self` and `other` have a common data flow parent.

        By default, max_depth=1_000_000_000, but you may set it to a lower value.
        You might want to use max_depth=1 for example if you only want to compare direct data flow parents, i.e.,
        no data flow grandparents.
        When setting max_depth=0, this function will simply return whether `self.id == other.id`.
        """
        if self.name != "Identifier" or other.name != "Identifier":
            raise TypeError("is_data_flow_equivalent_identifier(): both self and other need to be Identifiers!")

        self_data_dep_parents = self.get_data_flow_parents(max_depth=max_depth)
        other_data_dep_parents = other.get_data_flow_parents(max_depth=max_depth)

        return len(set.intersection(self_data_dep_parents, other_data_dep_parents)) > 0

    # ADDED BY ME:
    @classmethod
    def identifier(cls, name):
        n = cls("Identifier")
        n.attributes['name'] = name
        return n

    # ADDED BY ME:
    @classmethod
    def literal(cls, raw):
        n = cls("Literal")
        n.attributes['raw'] = raw
        return n

    # ADDED BY ME:
    @classmethod
    def wildcard(cls):
        """
        When used as a pattern supplied to the matches() function, the wildcard will match *anything*!
        """
        n = cls("*")
        n.is_wildcard = True
        return n

    # ADDED BY ME:
    def child(self, c):
        """
        Appends the given Node as a child and then returns itself again.
        """
        # Safety check first:
        if self.name in ["BinaryExpression", "LogicalExpression", "AssignmentExpression"] and len(self.children) >= 2:
            raise TypeError(f"calling Node.child(): a(n) {self.name} cannot have more than 2 children; use nested Nodes instead!")
        elif self.name in ["UnaryExpression", "UpdateExpression"] and len(self.children) >= 1:
            raise TypeError(f"calling Node.child(): a(n) {self.name} cannot have more than 1 child!")
        elif self.name in ["IfStatement"] and len(self.children) >= 3:
            raise TypeError(f"calling Node.child(): a(n) {self.name} cannot have more than 3 children!")

        self.children.append(c)
        c.parent = self
        return self

    # ADDED BY ME:
    def get_sibling(self, idx: int):
        sibling = self.parent.children[idx]
        # Safety check, when the programmer calls get_sibling(), he likely wants a *different* Node:
        assert sibling.id != self.id
        return sibling

    # ADDED BY ME:
    def get_sibling_relative(self, relative_index: int):
        """
        Cf. get_sibling() but the given index is *relative* to this node.

        Example:

        [1] parent
            [2] child A
            [3] child B
            [4] child C
            [5] child D
            [6] child E

        When being called on [4] child C, ...
        ...get_sibling_relative(-2) returns [2] child A
        ...get_sibling_relative(-1) returns [3] child B
        ...get_sibling_relative(0) returns [4] child C itself
        ...get_sibling_relative(1) returns [5] child D
        ...get_sibling_relative(2) returns [6] child E
        """
        self_index = self.parent.children.index(self)
        return self.parent.children[self_index + relative_index]

    # ADDED BY ME:
    def get_sibling_by_name(self, name: str):
        for sibling in self.parent.children:
            if sibling.name == name and sibling.id != self.id:
                return sibling
        return None

    # ADDED BY ME:
    def get_only_sibling(self):
        siblings = [c for c in self.parent.children if c.id != self.id]
        assert len(siblings) == 1
        return siblings[0]

    # ADDED BY ME:
    def has_sibling(self, name: str):
        return self.get_sibling_by_name(name=name) is not None

    # ADDED BY ME:
    def is_sibling_of(self, other):
        return self.parent is not None and self.parent == other.parent

    # ADDED BY ME:
    def count_siblings(self):
        return len(self.parent.children) -1

    # ADDED BY ME:
    def grandparent(self):
        if self.parent is None:  # No parent...
            return None  # ...no grandparent.
        return self.parent.parent  # (might be None)

    # ADDED BY ME:
    def great_grandparent(self):
        if self.parent is None:  # No parent...
            return None  # ...no great-grandparent.
        elif self.parent.parent is None:  # No grandparent...
            return None  # ...no great-grandparent.
        return self.parent.parent.parent  # (might be None)

    # ADDED BY ME:
    def get_parents(self):
        """
        Return the parent, grandparent, great-grandparent, etc. of this Node (in that order)
        until the root node is reached.
        """
        if self.parent is None:
            return []
        else:
            return [self.parent] + self.parent.get_parents()

    # ADDED BY ME:
    def get_parent(self, allowed_parent_names):
        """
        Returns `self.parent` but only if `self.parent.name in allowed_parent_names`, otherwise this function raises
        a LookupError.

        Use this function when getting the parent of a Node and already knowing what types it could possibly belong to,
        i.e., already knowing that it's either a "FunctionExpression" or "ArrowFunctionExpression":
        ```
        node.get_parent(["FunctionExpression", "ArrowFunctionExpression"])
        ```
        In case your design is mistaken/your assumptions were wrong, you will easily catch such an error then.

        If you don't know anything about the parent yet, simply access the attribute directly: `self.parent`
        """
        if self.parent.name in allowed_parent_names:
            return self.parent
        else:
            raise LookupError(f"parent of [{self.id}] has name '{self.parent.name}' but none of: {allowed_parent_names}")

    # ADDED BY ME:
    def get_parent_or_grandparent(self, allowed_ancestor_names):
        if self.parent.name in allowed_ancestor_names:
            return self.parent
        elif self.grandparent().name in allowed_ancestor_names:
            return self.grandparent()
        else:
            raise LookupError(f"neither parent nor grandparent of [{self.id}] has name in: {allowed_ancestor_names} "
                              f"(parent name: '{self.parent.name}', grandparent name: '{self.grandparent().name}')")

    # ADDED BY ME:
    def get_ancestor(self, allowed_ancestor_names):
        parent = self.parent
        while parent is not None:
            if parent.name in allowed_ancestor_names:
                return parent
            parent = parent.parent
        raise LookupError(f"no ancestor named '{allowed_ancestor_names}' found for node [{self.id}]")

    # ADDED BY ME:
    def has_ancestor(self, allowed_ancestor_names):
        parent = self.parent
        while parent is not None:
            if parent.name in allowed_ancestor_names:
                return True
            parent = parent.parent
        return False

    # ADDED BY ME:
    def __str__(self):
        str_repr = ""

        attributes_of_interest = {
            "Identifier": 'name',
            "Literal": ['raw', 'value'],
            "BinaryExpression": 'operator',      # 'instanceof' | 'in' | '+' | '-' | '*' | '/' | '%' | '**' |
                                                 # '|' | '^' | '&' | '==' | '!=' | '===' | '!==' |
                                                 # '<' | '>' | '<=' | '<<' | '>>' | '>>>'
            "LogicalExpression": 'operator',     # || or &&
            "AssignmentExpression": 'operator',  # '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
                                                 # '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|='
            "UnaryExpression": 'operator',       # '+' | '-' | '~' | '!' | 'delete' | 'void' | 'typeof'
            "UpdateExpression": 'operator',      # '++' or '--'
            "MemberExpression": 'computed'       # (boolean)  # ToDo: handle True/False cases differently in code (x.y vs. x[y])
        }

        if self.name in attributes_of_interest.keys():
            if isinstance(attributes_of_interest[self.name], list):
                str_repr = f"[{self.id}] [{self.name}::{str({attr: self.attributes[attr] for attr in attributes_of_interest[self.name]})}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"
            else:
                str_repr = f"[{self.id}] [{self.name}:\"{self.attributes[attributes_of_interest[self.name]]}\"] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"
        else:
            str_repr = f"[{self.id}] [{self.name}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"

        # cf. display_extension.py:
        if self.name in STATEMENTS:
            for cf_dep in self.control_dep_children:
                str_repr += f" --{cf_dep.label}--> [{cf_dep.extremity.id}]"

        # cf. display_extension.py:
        if self.name == "Identifier":
            for data_dep in self.data_dep_children:
                str_repr += f" --{data_dep.label}--> [{data_dep.extremity.id}]"

        str_repr += "\n"

        for child in self.children:
            str_repr += "\n".join(["\t" + line for line in child.__str__().splitlines()]) + "\n"
        return str_repr

    # ADDED BY ME:
    def contains_literal(self):
        """
        Does this subtree contain any Literal (Node)?
        """
        return self.get_literal() is not None

    # ADDED BY ME:
    def get_literal(self):
        """
        Returns the Literal contained inside this subtree.
        When there is no Literal to be found, `None` is returned.
        When there are multiple Literals, the first one encountered is returned.
        """
        if self.name == "Literal":
            return self.attributes['raw']
        elif len(self.children) == 0:
            return None
        else:
            for child in self.children:
                child_literal = child.get_literal()
                if child_literal is not None:
                    return child_literal  # return the first Literal found
            return None  # no child contains any Literal

    # ADDED BY ME:
    def get_all(self, node_name):
        """
        Returns all nodes of a given type/name, e.g. all "VariableDeclaration" nodes.
        """
        result = []
        if self.name == node_name:
            result.append(self)
        for child in self.children:
            result.extend(child.get_all(node_name))
        return result

    # ADDED BY ME:
    def get_all_identifiers(self):
        return self.get_all("Identifier")

    # ADDED BY ME:
    def get_identifier_by_name(self, name):
        """
        A function mostly for testing purposes, e.g., for use in unit tests.
        Raises a LookupError, unless the identifier with name `name` occurs exactly *once* inside this PDG!
        """
        result = [identifier for identifier in self.get_all("Identifier") if identifier.attributes['name'] == name]
        if len(result) == 1:
            return result[0]
        elif len(result) == 0:
            raise LookupError(f"get_identifier_by_name(): no identifier with name '{name}' found!")
        else:
            raise LookupError(f"get_identifier_by_name(): identifier name '{name}' is ambiguous, {len(result)} found!")

    # ADDED BY ME:
    def get_all_literals(self):
        return self.get_all("Literal")

    # ADDED BY ME:
    def get_all_if_statements_inside(self):
        """
        Returns all if-statements ("IfStatement" nodes) inside this piece of code as a list.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements) and will therefore be returned as well!
        """
        return self.get_all("IfStatement")

    # ADDED BY ME:
    def get_all_return_statements_inside(self):
        """
        Returns all return-statements ("ReturnStatement" nodes) inside this piece of code as a list.
        """
        return self.get_all("ReturnStatement")

    # ADDED BY ME:
    def has_child(self, child_name):
        for child in self.children:
            if child.name == child_name:
                return True
        return False

    # ADDED BY ME:
    def get_child(self, child_name):
        for child in self.children:
            if child.name == child_name:
                return child
        return None

    # ADDED BY ME:
    def get_only_child(self):
        assert len(self.children) == 1
        return self.children[0]

    # ADDED BY ME:
    def is_nth_child_of_parent(self, n) -> bool:
        sibling_ids = [sibling.id for sibling in self.parent.children]
        return self.id == sibling_ids[n]

    def is_nth_child_of_parent_ignoring_certain_siblings(self, n, siblings_names_to_ignore: List[str]) -> bool:
        sibling_ids = [sibling.id for sibling in self.parent.children if sibling.name not in siblings_names_to_ignore]
        return self.id == sibling_ids[n]

    # ADDED BY ME:
    def matches(self, pattern, match_identifier_names, match_literals, match_operators, allow_additional_children,
                allow_different_child_order):
        """
        Returns if this AST subtree matches another given AST tree (pattern), only comparing:
        * name of root
        * number of children (only if allow_additional_children == False)
        * names of children
        * "name" attributes of "Identifier" nodes (only if match_identifier_names == True)
        * "raw" attributes of "Literal" nodes (only if match_literals == True)
        """
        if pattern.is_wildcard:
            return True  # Note that the calls to all() below may also return True as all([]) is True!
        elif self.name != pattern.name:
            return False
        elif match_identifier_names and self.name == "Identifier" and self.attributes['name'] != pattern.attributes['name']:
            return False
        elif match_literals and self.name == "Literal" and self.attributes['raw'] != pattern.attributes['raw']:
            return False
        elif match_operators and self.name in ["UpdateExpression", "UnaryExpression", "BinaryExpression",
                                               "LogicalExpression", "AssignmentExpression"]\
                and self.attributes['operator'] != pattern.attributes['operator']:
            return False
        elif not allow_additional_children and len(self.children) != len(pattern.children):
            return False
        elif allow_additional_children and len(self.children) < len(pattern.children):  # pattern cannot be matched
            return False
        elif not allow_additional_children and allow_different_child_order and sorted([c.name for c in self.children]) != sorted([c.name for c in pattern.children]):
            return False
        elif not allow_additional_children and not allow_different_child_order and [c.name for c in self.children] != [c.name for c in pattern.children]:
            return False
        elif allow_additional_children and not set(c.name for c in pattern.children if not c.is_wildcard).issubset(set(c.name for c in self.children)):
            return False
        elif not allow_additional_children:
            if allow_different_child_order:  # If allow_different_child_order=True (and allow_additional_children=False)...
                permutations = itertools.permutations(pattern.children)  # ...allow all permutations of the children in the pattern (but not additional children).
            else:  # If allow_different_child_order=False (and allow_additional_children=False)...
                permutations = [pattern.children]  # ...allow only 1 permutation of children, namely the one in the pattern!

            # Iterate through all possible child permutations and try to find a match:
            return any(all(self.children[i].matches(permutation[i], match_identifier_names, match_literals, match_operators, allow_additional_children, allow_different_child_order)
                           for i in range(len(self.children)))
                           for permutation in permutations)
        else:  # allow_additional_children == True:
            # Fill pattern up with wildcards:
            pattern_children_plus_wildcards = pattern.children + [Node.wildcard()] * (len(self.children) - len(pattern.children))

            permutations = itertools.permutations(pattern_children_plus_wildcards)

            # Same as above:
            return any(all(self.children[i].matches(permutation[i], match_identifier_names, match_literals, match_operators, allow_additional_children, allow_different_child_order)
                           for i in range(len(self.children)))
                           for permutation in permutations
                           if allow_different_child_order or all([[el for el in permutation if not el.is_wildcard][i] == pattern.children[i] for i in range(len(pattern.children))]))
            # The last line skips permutations that changed the order of the non-wildcard nodes if allow_different_child_order=False.

        # Note:
        #
        # >>> all([])
        # True
        # >>> any([])
        # False
        # >>> [i for i in range(0)]
        # []
        # >>> [perm for perm in itertools.permutations([])]
        # [()]
        #
        # => Therefore:
        # >>> any(all(42 for i in range(0)) for perm in [()])
        # True
        # => For any two Nodes w/o any children and the same name (as well as the same Identifier name for Identifiers/
        #    the same raw Literal value for Literals), matches() will return True!

    # ADDED BY ME:
    def find_pattern(self, pattern, match_identifier_names, match_literals, match_operators, allow_additional_children,
                     allow_different_child_order):
        """
        Returns all subtrees of this PDG matching the given pattern `pattern`.
        Cf. `Node.matches()` function.
        """
        result = []
        all_match_candidates = self.get_all(pattern.name)
        for match_candidate in all_match_candidates:
            if match_candidate.matches(pattern,
                                       match_identifier_names=match_identifier_names,
                                       match_literals=match_literals,
                                       match_operators=match_operators,
                                       allow_additional_children=allow_additional_children,
                                       allow_different_child_order=allow_different_child_order):
                if os.environ.get('PRINT_PDGS') == "yes":
                    print(f"Pattern Match:\n{match_candidate}")
                result.append(match_candidate)
        return result

    # ADDED BY ME:
    def member_expression_to_string(self):
        """
        Turns a PDG MemberExpression back into a string.
        For something simple as the PDG representing "foo.bar.baz", "foo.bar.baz" is returned,
            corresponding to the source code.
        For more complex MemberExpressions, a simplified, standardized string form is returned, e.g.,
            a PDG representing this code: "foo.bar(x,y(z),w).baz.boo" becomes "foo.bar().baz.boo".
        Any literal will become "<literal>", e.g. "'foo'.length" will become "<literal>.length"
        """
        if self.name != "MemberExpression":
            raise TypeError("member_expression_to_string() may only be called on a MemberExpression")

        if self.lhs().name == "ThisExpression":
            return "this." + self.rhs().attributes['name']

        elif self.lhs().name == "Literal":  # e.g.: "foo".length
            return "<literal>." + self.rhs().attributes['name']
            # Note how "<literal>" is *NOT* a valid JavaScript identifier! (see https://mothereff.in/js-variables)

        elif self.lhs().name == "Identifier":
            return self.lhs().attributes['name'] + "." + self.rhs().attributes['name']

        elif self.lhs().name == "MemberExpression":
            return self.lhs().member_expression_to_string() + "." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "ThisExpression":
            return "this()." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "Identifier":
            return self.lhs().children[0].attributes['name'] + "()." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "MemberExpression":
            return self.lhs().children[0].member_expression_to_string() + "()." + self.rhs().attributes['name']

        else:
            raise TypeError(f"member_expression_to_string(): LHS of MemberExpression is neither a ThisExpression "
                            f"nor an Identifier nor a MemberExpression: {self.lhs()}")

    # ADDED BY ME:
    def call_expression_get_full_function_name(self) -> str:
        """
        For...

        [1] [CallExpression] (2 children)
            [2] [MemberExpression] (2 children)
                [3] [MemberExpression] (2 children)
                    [4] [Identifier:"foo"] (0 children)
                    [5] [Identifier:"bar"] (0 children)
                [6] [Identifier:"baz"] (0 children)
            [7] [Identifier:"x"] (0 children)

        ...this functions returns "foo.bar.baz" (as a string!) for example.

        Note that both "a[b](x,y,z)" and "a.b(x,y,z)" will result in the same output of "a.b" as the full function name!

        Note that the returned value may also be more complex:
        * call_expression_get_full_function_name("x().y()") ==returns==> "x().y"
        * call_expression_get_full_function_name("x(a,b).y()") ==returns==> "x().y"
        
        Raises an Exception when called on a Node that isn't a CallExpression!
        """
        if self.name != "CallExpression":
            raise TypeError("call_expression_get_full_function_name() may only be called on a CallExpression")

        # Out of the Esprima docs:
        #
        # interface CallExpression {
        #     type: 'CallExpression';
        #     callee: Expression | Import;
        #     arguments: ArgumentListElement[];
        # }

        callee = self.children[0]

        if callee.name == "Identifier":  # "foo(...)"
            return callee.attributes['name']  # return "foo"

        elif callee.name == "ThisExpression":  # "this(...)"
            return "this"

        elif callee.name == "MemberExpression":  # "foo.bar(...)", "foo.bar.baz(...)", etc.
            return callee.member_expression_to_string()

        elif callee.name == "CallExpression":  # "x()()"
            return callee.call_expression_get_full_function_name() + "()"

        else:
            raise TypeError(f"call_expression_get_full_function_name(): "
                            f"Unsupported type of callee Expression used for a CallExpression: {callee}")

    # ADDED BY ME:
    def call_expression_get_all_arguments(self) -> List[Self]:
        # interface CallExpression {
        #     callee: Expression | Import;
        #     arguments: ArgumentListElement[];
        # }
        assert self.name == "CallExpression"
        return self.children[1:]

    DEFAULT_SENSITIVE_APIS = ["chrome.cookies", "chrome.scripting", "chrome.tabs.executeScript", "indexedDB", "fetch"]

    # ADDED BY ME:
    def get_sensitive_apis_accessed(self, apis=DEFAULT_SENSITIVE_APIS) -> Set[Tuple[str, str]]:
        """
        Returns the set of all sensitive APIs accessed in the piece of code represented by this PDG Node.
        The returned set consists of pairs, the 1st element being the sensitive API and the 2nd element being the way
        it way accessed, e.g.: ("chrome.cookies", "chrome.cookies.getAll").
        """
        sensitive_apis_accessed = set()
        for call_expression in self.get_all("CallExpression"):
            full_function_name = call_expression.call_expression_get_full_function_name()
            if "()" not in full_function_name:  # do not consider any complex function names like "x().y().z()"!
                for api in apis:
                    if full_function_name.startswith(api):  # such that "chrome.cookies" catches "chrome.cookies.getAll" calls for example!
                        sensitive_apis_accessed.add((api, full_function_name))
        return sensitive_apis_accessed

    # ADDED BY ME:
    def get_statement(self):
        """
        If this Node isn't a Statement itself already, this function returns the Statement that this Node is a part of,
        by going up the PDG parent-by-parent until a Statement is found.

        This function is useful when dealing with control flow.

        Returns `None` when this Node isn't part of any Statement but that case should not actually occur!
        """
        if self.name in STATEMENTS:
            return self
        elif self.parent is not None:
            return self.parent.get_statement()
        else:
            return None

    # ADDED BY ME:
    def get_next_higher_up_statement(self):
        """
        This function returns the Statement that this Node is a part of,
        by going up the PDG parent-by-parent until a Statement is found.

        If this Node is a Statement *itself* does not matter here.
        If you need a function that returns the node itself when it's a Statement already, use get_statement() instead.

        Returns `None` when this Node doesn't have any higher up Statement above it, this may occur when you call this
        function on the root node of the tree!
        """
        if self.parent is not None:
            return self.parent.get_statement()
        else:
            return None

    # ADDED BY ME:
    def get_innermost_surrounding_if_statement(self):
        """
        Returns the innermost if-statement surrounding this piece of code,
        or `None` if there is no if-statement surrounding this piece of code.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements) and will therefore be considered as well!
        """
        if self.name == "IfStatement":
            return self
        elif self.parent is not None:
            return self.parent.get_surrounding_if_statement()
        else:
            return None

    # ADDED BY ME:
    def get_all_surrounding_if_statements(self):
        """
        Returns all if-statement surrounding this piece of code, from innermost to outermost, as a list.
        Returns the empty list `[]` if there is no if-statement surrounding this piece of code.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements) and will therefore be considered as well!
        """
        result = []
        current = self

        while True:
            if current.name == "IfStatement":
                result.append(current)
            if current.parent is None:
                break
            else:
                current = current.parent

        return result

    # ADDED BY ME:
    def is_return_statement(self):
        """
        Returns True iff this very Statement is a ReturnStatement itself.
        To check if this node is simply *inside* a ReturnStatement, use is_inside_return_statement() instead!
        """
        return self.name == "ReturnStatement"

    # ADDED BY ME:
    def is_inside_return_statement(self):
        """
        Returns True iff this node is either a ReturnStatement itself or is inside of one inside the AST, by
        traversing parent to parent until there is no parent anymore.
        """
        if self.name == "ReturnStatement":
            return True
        elif self.parent is not None:
            return self.parent.is_inside_return_statement()
        else:
            return False

    # ##### On if statements: #####
    #
    # * If statements can have 2 children (no else branch) or 3 children (else branch):
    #
    #   if (sender.url == "https://admin.com/") {    [1] [IfStatement] (2 children) --True--> [3]
    #       sendResponse(cookies);                       [2] [BinaryExpression] (2 children)
    #   }                                                [3] [BlockStatement] (1 child) --e--> [3.1]
    #
    #   if (sender.url == "https://admin.com/") {    [1] [IfStatement] (3 children) --True--> [3] --False--> [4]
    #       sendResponse(cookies);                       [2] [BinaryExpression] (2 children)
    #   } else {                                         [3] [BlockStatement] (1 child) --e--> [3.1]
    #       sendResponse("error");                       [4] [BlockStatement] (1 child) --e--> [4.1]
    #   }
    #
    # * Else-if branches are modelled as nested if statements, i.e., with another IfStatement in the else branch:
    #
    #   if (sender.url == "https://admin.com/") {           [1] [IfStatement] (3 children) --True--> [3] --False--> [4]
    #       sendResponse(cookies);                              [2] [BinaryExpression] (2 children)
    #   } else if (sender.url == "https://admin.com/") {        [3] [BlockStatement] (1 child) --e--> [3.1]
    #       sendResponse(cookies);                              [4] [IfStatement] (2 children) --True--> [6]
    #   }                                                           [5] [BinaryExpression] (2 children)
    #                                                               [6] [BlockStatement] (1 child) --e--> [6.1]
    #
    #   if (sender.url == "https://admin.com/") {           [1] [IfStatement] (3 children) --True--> [3] --False--> [4]
    #       sendResponse(cookies);                              [2] [BinaryExpression] (2 children)
    #   } else if (sender.url == "https://admin.com/") {        [3] [BlockStatement] (1 child) --e--> [3.1]
    #       sendResponse(cookies);                              [4] [IfStatement] (3 children) --True--> [6] --False--> [7]
    #   } else {                                                    [5] [BinaryExpression] (2 children)
    #       sendResponse("error");                                  [6] [BlockStatement] (1 child) --e--> [6.1]
    #   }                                                           [7] [BlockStatement] (1 child) --e--> [7.1]

    # ADDED BY ME:
    def is_if_statement(self):
        """
        Returns True iff this node is an "IfStatement" node.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements); therefore this function will *also* returned true when called on an IfStatement representing an
        else-if branch!

        All IfStatements have either 2 or 3 children (3 only when there's an else and/or else-if branch).
        """
        return self.name == "IfStatement"

    # ADDED BY ME:
    def if_statement_has_else_branch(self):
        """
        Returns True iff this IfStatement has an else branch.
        Raises an exception when this node isn't an "IfStatement" node; use is_if_statement() to check that beforehand.

        Else-if branches are *not* counted as else branches! Use if_statement_has_else_if_branch() for that instead.
        """
        return self.if_statement_get_else_branch() is not None

    # ADDED BY ME:
    def if_statement_get_else_branch(self):
        """
        Returns the else branch of this IfStatement (will always be of type "BlockStatement").
        Returns `None` when this IfStatement has no else branch.
        Raises an exception when this node isn't an "IfStatement" node; use is_if_statement() to check that beforehand.

        If you just want to know whether there *is* an else branch or not, you may also use if_statement_has_else_branch().
        """
        if not self.is_if_statement():
            raise TypeError("called if_statement_get_else_branch() on a Node that's not an IfStatement")
        elif len(self.children) == 2:  # if (...) { ... }
            return None  # There is no else branch, return `None`.
        elif len(self.children) == 3 and self.children[2].name == "BlockStatement":  # if (...) { ... } else { ... }
            return self.children[2]  # Return the else branch.
        elif len(self.children) == 3 and self.children[2].name == "IfStatement":  # if (...) { ... } else if ...
            return self.children[2].if_statement_get_else_branch()  # Recursion
        else:
            raise Exception(f"error in if_statement_get_else_branch(): if statement has unknown format:\n{self}")

    # ADDED BY ME:
    def if_statement_has_else_if_branch(self):
        if not self.is_if_statement():
            raise TypeError("called if_statement_has_else_if_branch() on a Node that's not an IfStatement")
        elif len(self.children) == 2:  # if (...) { ... }
            return False  # There is no else or else-if branch, return False.
        elif len(self.children) == 3 and self.children[2].name == "BlockStatement":  # if (...) { ... } else { ... }
            return False  # There's only an else branch, return False.
        elif len(self.children) == 3 and self.children[2].name == "IfStatement":  # if (...) { ... } else if ...
            return True  # There's an else-if branch (represented by another IfStatement Node), return True.
        else:
            raise Exception(f"error in if_statement_has_else_if_branch(): if statement has unknown format:\n{self}")

    # ##### ##### occurs_in_code_before() & occurs_in_code_after(): ##### #####
    # Note how simply comparing Node IDs isn't enough as the following example shows:
    # Code: "function foo() { function bar() {} }"
    # PDG:
    # [46] [Program] (1 child)
    # 	[47] [FunctionDeclaration] (3 children) --e--> [50] --e--> [49]
    # 		[50] [FunctionDeclaration] (2 children) --e--> [52]
    # 			[51] [Identifier:"bar"] (0 children)
    # 			[52] [BlockStatement] (0 children)
    # 		[48] [Identifier:"foo"] (0 children)
    # 		[49] [BlockStatement] (0 children)

    # ADDED BY ME:
    def occurs_in_code_before(self, other_node):
        assert self.get_file() == other_node.get_file()

        self_start_line = int(self.attributes['loc']['start']['line'])
        self_start_column = int(self.attributes['loc']['start']['column'])

        other_start_line = int(other_node.attributes['loc']['start']['line'])
        other_start_column = int(other_node.attributes['loc']['start']['column'])

        return self_start_line < other_start_line or\
                (self_start_line == other_start_line and self_start_column < other_start_column)

    # ADDED BY ME:
    def occurs_in_code_after(self, other_node):
        assert self.get_file() == other_node.get_file()

        self_start_line = int(self.attributes['loc']['start']['line'])
        self_start_column = int(self.attributes['loc']['start']['column'])

        other_start_line = int(other_node.attributes['loc']['start']['line'])
        other_start_column = int(other_node.attributes['loc']['start']['column'])

        return self_start_line > other_start_line or \
            (self_start_line == other_start_line and self_start_column > other_start_column)

    # ADDED BY ME:
    def lies_within(self, other_node):
        """
        Whether this node is a child, grand-child, great-grandchild, etc. of `other_node`.
        Returns False when self == other_node!
        """
        parent = self.parent
        while parent is not None:
            if parent.id == other_node.id:
                return True
            parent = parent.parent
        return False

    # Python regex recap (cf. https://docs.python.org/3/library/re.html):
    # re.search(pattern, string, flags=0) => Scan through str looking for the first loc where the regex produces a match
    # re.match(pattern, string, flags=0) => If zero or more characters at the beginning of string match the regex
    # re.fullmatch(pattern, string, flags=0) => If the whole string matches the regex pattern

    # ADDED BY ME:
    def string_literal_strip_quotation_marks(self):
        """
        When this is a String Literal, returns the literal string w/o quotation marks.
        Note that JavaScript has 3 different valid quotation marks: "", '' and ``
        """
        assert self.name == "Literal"
        raw = self.attributes['raw']
        if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
            string_inside_quotes = raw[1:-1]  # remove the quotation marks
            return string_inside_quotes
        else:
            raise TypeError("string_literal_strip_quotation_marks called on a non-string literal!")

    # ADDED BY ME:
    def string_literal_matches_full_regex(self, regex):
        assert self.name == "Literal"
        raw = self.attributes['raw']
        if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
            string_inside_quotes = raw[1:-1]  # remove the quotation marks
            if re.fullmatch(regex, string_inside_quotes):
                return True
        return False

    # ADDED BY ME:
    def string_literal_contains_regex(self, regex):
        assert self.name == "Literal"
        raw = self.attributes['raw']
        if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
            string_inside_quotes = raw[1:-1]  # remove the quotation marks
            if re.search(regex, string_inside_quotes):
                return True
        return False

    # ADDED BY ME:
    def any_literal_inside_matches_full_regex(self, regex):
        """
        Does any literal inside this subtree match the given regular expression?
        The entire raw literal has to match the given regular expression!
        Beware that literals may be string, integer or float literals!
        For string literals, you will need to include the quotation marks to match.
        If you want to match entire string literals but don't care about the type of quotation marks used,
        consider using any_string_literal_inside_matches_full_regex() instead.
        """
        for literal in self.get_all_literals():
            if re.fullmatch(regex, literal.attributes['raw']):
                return True
        return False

    # ADDED BY ME:
    def any_literal_inside_contains_regex(self, regex):
        """
        Does any literal inside this subtree match the given regular expression?
        Beware that literals may be string, integer or float literals!
        Unlike any_literal_inside_matches_full_regex(), the match found does *not* have to be the *full* literal!
        """
        for literal in self.get_all_literals():
            if re.search(regex, literal.attributes['raw']):
                return True
        return False

    # ADDED BY ME:
    def any_string_literal_inside_matches_full_regex(self, regex):
        """
        Tries to find a string literal matching the given regular expression, ignoring the leading and trailing
        quotation mark. Integer and float literals are ignored.
        Ignoring the quotations marks, the entire(!) string has to match the given regex (cf. re.fullmatch()).

        If you want to include the quotation marks in your regex or if you want to match integer/float literals,
        use any_literal_inside_matches_full_regex() instead.
        """
        # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String:
        # const string1 = "A string primitive";
        # const string2 = 'Also a string primitive';
        # const string3 = `Yet another string primitive`;
        for literal in self.get_all_literals():
            raw = literal.attributes['raw']
            if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
                string_inside_quotes = raw[1:-1]  # remove the quotation marks
                if re.fullmatch(regex, string_inside_quotes):
                    return True
        return False

    # ADDED BY ME:
    def any_string_literal_inside_contains_regex(self, regex):
        """
        Tries to find a string literal matching the given regular expression, ignoring the leading and trailing
        quotation mark. Integer and float literals are ignored.
        Unlike any_string_literal_inside_matches_full_regex(), the match found does *not* have to be the *full* literal!

        If you want to include the quotation marks in your regex or if you want to match integer/float literals,
        use any_literal_inside_contains_regex() instead.
        """
        # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/String:
        # const string1 = "A string primitive";
        # const string2 = 'Also a string primitive';
        # const string3 = `Yet another string primitive`;
        #     => not considered by us here; Espree generates a TemplateLiteral Node and not a Literal Node for those!
        for literal in self.get_all_literals():
            raw = literal.attributes['raw']
            if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
                string_inside_quotes = raw[1:-1]  # remove the quotation marks
                if re.search(regex, string_inside_quotes):
                    return True
        return False

    # ADDED BY ME:
    def get_height(self):
        if len(self.children) == 0:
            return 1
        else:
            return 1 + max(child.get_height() for child in self.children)

    # ADDED BY ME:
    def promise_returning_function_call_get_all_then_calls(self, resolve_function_references=True): # ToDo: use for chrome.cookies API as well!!!
        """
        Examples:

        Example #1:

        Code (taken from /pkehgijcmpdhfbdbbnkijodmdjhbjlgp-2021.11.23.1-Crx4Chrome.com/background.js):
        fetch(constants.CNAME_DOMAINS_LOCAL_URL)
                .then(response => response.json())
                .then(data => {
                    badger.cnameDomains = data;
                });

        Entire PDG:
        [1] [Program] (1 child)
            [2] [ExpressionStatement] (1 child)
                [3] [CallExpression] (2 children)
                    [4] [MemberExpression:"False"] (2 children)
                        [5] [CallExpression] (2 children)
                            [6] [MemberExpression:"False"] (2 children)
                                [7] [CallExpression] (2 children)
                                    [8] [Identifier:"fetch"] (0 children)
                                    [9] [MemberExpression:"False"] (2 children)
                                        [10] [Identifier:"constants"] (0 children)
                                        [11] [Identifier:"CNAME_DOMAINS_LOCAL_URL"] (0 children)
                                [12] [Identifier:"then"] (0 children)
                            [13] [ArrowFunctionExpression] (2 children)
                                [14] [Identifier:"response"] (0 children) --data--> [17]
                                [15] [CallExpression] (1 child)
                                    [16] [MemberExpression:"False"] (2 children)
                                        [17] [Identifier:"response"] (0 children)
                                        [18] [Identifier:"json"] (0 children)
                        [19] [Identifier:"then"] (0 children)
                    [20] [ArrowFunctionExpression] (2 children)
                        [21] [Identifier:"data"] (0 children) --data--> [28]
                        [22] [BlockStatement] (1 child) --e--> [23]
                            [23] [ExpressionStatement] (1 child)
                                [24] [AssignmentExpression:"="] (2 children)
                                    [25] [MemberExpression:"False"] (2 children)
                                        [26] [Identifier:"badger"] (0 children)
                                        [27] [Identifier:"cnameDomains"] (0 children)
                                    [28] [Identifier:"data"] (0 children) --data--> [26]

        Input (self):
        [7] [CallExpression] (2 children)
            which might be nested inside many MemberExpressions/CallExpressions due to repeated then() calls!

        Output #1:
        [13] [ArrowFunctionExpression] (2 children)
            [14] [Identifier:"response"] (0 children) --data--> [17]
            [15] [CallExpression] (1 child)
                [16] [MemberExpression:"False"] (2 children)
                    [17] [Identifier:"response"] (0 children)
                    [18] [Identifier:"json"] (0 children)

        Output #2:
        [20] [ArrowFunctionExpression] (2 children)
            [21] [Identifier:"data"] (0 children) --data--> [28]
            [22] [BlockStatement] (1 child) --e--> [23]
                [23] [ExpressionStatement] (1 child)
                    [24] [AssignmentExpression:"="] (2 children)
                        [25] [MemberExpression:"False"] (2 children)
                            [26] [Identifier:"badger"] (0 children)
                            [27] [Identifier:"cnameDomains"] (0 children)
                        [28] [Identifier:"data"] (0 children) --data--> [26]



        Example #2:

        Code (taken from https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/cookies/getAll):
        function logCookies(cookies) {
          for (const cookie of cookies) {
            console.log(cookie.value);
          }
        }

        chrome.cookies
          .getAll({
            name: "favorite-color",
          })
          .then(logCookies);
        """
        assert self.name == "CallExpression"

        result = []

        call_expression = self

        while (call_expression.name == "CallExpression"
               and call_expression.count_siblings() == 1
               and call_expression.has_sibling("Identifier")
               and call_expression.get_sibling_by_name("Identifier").attributes['name'] == "then"
               and call_expression.parent.count_siblings() == 1):

            then_call = call_expression.parent.get_only_sibling()  # = what's inside the then(...)
            if then_call.name in ["ArrowFunctionExpression", "FunctionExpression"]:
                result.append(then_call)
            elif then_call.name == "Identifier":  # "then(function_name)"
                if resolve_function_references:
                    function_declaration = then_call.function_Identifier_get_FunctionDeclaration()
                    if function_declaration is None:
                        result.append(then_call)
                    else:
                        assert function_declaration.name == "FunctionDeclaration"
                        result.append(function_declaration)
                else:
                    result.append(then_call)
            else:
                print(f"[Warning] .then() call in line {then_call.get_line()} of file {then_call.get_file()} "
                      f"contains something unexpected: a {then_call.name}")

            call_expression = call_expression.grandparent()

        return result

    # ADDED BY ME:
    def function_Identifier_get_FunctionDeclaration(self) -> Optional[Self]:
        """
        When this Node is an Identifier referencing a function, this method returns the corresponding
        FunctionDeclaration where said function is defined.

        When no FunctionDeclaration could be found, `None` is returned.

        When *more* than 1 corresponding FunctionDeclaration was found, an `AssertionError` is raised as a function
        shouldn't be able to be declared more than once!

        Also raises an `AssertionError` when `self.name != "Identifier"`

        Returns:
            (a) the FunctionDeclaration Node declaring the function referenced by this Identifier; or
            (b) None when no FunctionDeclaration could be found for this Identifier.
        """
        assert self.name == "Identifier"

        # Get all data flow parents:
        self_data_flow_parents = self.get_data_flow_parents()

        # Get all data flow parents that are function declarations
        #     (technically: whose parents are FunctionDeclaration Nodes):
        function_declaration_data_flow_parents = \
            [df_parent for df_parent in self_data_flow_parents if df_parent.parent.name == "FunctionDeclaration"
                            and df_parent.is_nth_child_of_parent_ignoring_certain_siblings(0, ["FunctionDeclaration"])]
        # The `df_parent.is_nth_child_of_parent(0)` check is very important to ensure that the function identifier
        #   is the 0th child of the FunctionDeclaration, i.e., that the FunctionDeclaration actually *defines* that
        #   function identifier and doesn't just take it as its argument (yes, functions may take other functions
        #   as arguments...)

        # If exactly 1 data flow parent was found that's a function declaration, return that one:
        if len(function_declaration_data_flow_parents) == 1:
            return function_declaration_data_flow_parents[0].get_parent("FunctionDeclaration")

        # If no declaring data flow parent for the function identifier was found, return None:
        elif len(function_declaration_data_flow_parents) == 0:
            # function reference couldn't be resolved, simply return None then:
            return None

        # If *MORE* than 1 corresponding function declaration was found, raise an AssertionError, as a function
        #    is not allowed to be declared twice(!):
        else:
            raise AssertionError(f"Identifier '{self.attributes['name']}' has >1 data flow parent, "
                                 f"even though functions may not be declared twice!")

    # ADDED BY ME:
    def function_param_get_identifier(self) -> Optional[Self]:
        """
        Function parameters will usually look like this:
        * function foo(x) {}

        However, they may also look like this, with a default value:
        * function foo(x=42) {}

        This method retrieves the Identifier corresponding to this function parameter, whether there's a default
        value or not.

        There are other possibilities as well, these are of destructuring nature however:
        * function foo([x,y]) {}
        * function foo([x,y]=[1,2]) {}
        * function foo({x,y}) {}
        * function foo({x,y}={x:1,y:2}) {}
        For all of these, this method simply returns `None`.
        If you want those returned as well, use the function_param_get_identifiers() instead!
        """
        if self.name == "Identifier":  # function foo(x) {}
            return self
        elif self.name == "AssignmentPattern" and self.lhs().name == "Identifier":  # function foo(x=42) {}
            return self.lhs()
        else:  # e.g., "function foo([x,y]) {}", or "function foo([x,y]=[1,2]) {}", or "function foo({x,y}) {}"
            return None

    # ADDED BY ME:
    def function_param_get_identifiers(self) -> List[Self]:
        """
        Function parameters will usually look like this:
        * function foo(x) {}

        However, they may also look like this:
        * function foo(x=42) {}
        * function foo([x,y]) {}
        * function foo([x,y]=[1,2]) {}
        * function foo({x,y}) {}
        * function foo({x,y}={x:1,y:2}) {}

        This method returns all LHS Identifiers corresponding to the function parameter represented by this Node.
        Returns an empty list on error.
        """

        # type FunctionParameter = AssignmentPattern | Identifier | BindingPattern;
        #
        # interface AssignmentPattern {
        #     left: Identifier | BindingPattern;
        #     right: Expression;
        # }
        #
        # type BindingPattern = ArrayPattern | ObjectPattern;
        #
        # interface ArrayPattern {
        #     elements: ArrayPatternElement[];
        # }
        #
        # type ArrayPatternElement = AssignmentPattern | Identifier | BindingPattern | RestElement | null;
        #
        # interface ObjectPattern {
        #     properties: Property[];
        # }
        #
        # interface Property {
        #     key: Expression;
        #     value: Expression | null;
        # }

        if self.name == "Identifier":  # function foo(x) {}
            return [self]
        elif self.name == "AssignmentPattern":
            if self.lhs().name == "Identifier":  # function foo(x=42) {}
                return [self.lhs()]
            elif self.lhs().name == "ArrayPattern":  # function foo([x,y]=[1,2]) {}
                return self.lhs().function_param_get_identifiers()
            elif self.lhs().name == "ObjectPattern":  # function foo({x,y}={x:1,y:2}) {}
                return self.lhs().function_param_get_identifiers()
            else:
                print(f"[Warning] function_param_get_identifiers(): unknown LHS of AssignmentPattern: "
                      f"{self.lhs().name}, line {self.lhs().get_line()}, file {self.lhs().get_file()}")
                return []
        elif self.name == "ArrayPattern":  # function foo([x,y]) {}
            return [child for child in self.children if child.name == "Identifier"]
        elif self.name == "ObjectPattern":  # function foo({a:x,b:y}) {}
            return [property_.children[1] for property_ in self.children if property_.children[1].name == "Identifier"]
        else:
            print(f"[Warning] function_param_get_identifiers(): unknown type of Node for function param: "
                  f"{self.lhs().name}, line {self.lhs().get_line()}, file {self.lhs().get_file()}")
            return []

    # ADDED BY ME:
    def function_declaration_get_params(self) -> List[Self]:
        # According to the Esprima docs, a FunctionDeclaration looks like this:
        # interface FunctionDeclaration {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        #     generator: boolean;
        #     async: boolean;
        #     expression: false;
        # }
        # where: type FunctionParameter = AssignmentPattern | Identifier | BindingPattern;
        #        type BindingPattern = ArrayPattern | ObjectPattern;
        #
        # However, in reality, functions inside of functions will be hoisted directly inside the Function Declaration,
        # for example the following code:
        #
        # function foo() {
        #     function bar() {}
        # }
        #
        # ...results in the following PDG:
        #
        # [708] [Program] (1 child)
        # 	[709] [FunctionDeclaration] (3 children) --e--> [712] --e--> [711]
        # 		[712] [FunctionDeclaration] (2 children) --e--> [714]
        # 			[713] [Identifier:"bar"] (0 children)
        # 			[714] [BlockStatement] (0 children)
        # 		[710] [Identifier:"foo"] (0 children)
        # 		[711] [BlockStatement] (0 children)
        #
        # Notice how the IDs of the children are *NOT* in ascending order!
        #
        # This function returns the parameters of this FunctionDeclaration only, no hoisted FunctionDeclarations,
        #   not the name of the declared function and not the BlockStatement!
        assert self.name == "FunctionDeclaration"
        identifiers = [param for param in self.children if param.name not in ["FunctionDeclaration", "BlockStatement"]]
        return identifiers[1:]  # ignore 1st Identifier as that's not a parameter but rather the name of the function!

    # ADDED BY ME:
    def arrow_function_expression_get_params(self) -> List[Self]:
        # From the Esprima docs:
        # interface ArrowFunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement | Expression;
        # }
        # interface FunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement; generator: boolean;
        # }
        # The "id" seems appears to be always null, however.
        assert self.name in ["FunctionExpression", "ArrowFunctionExpression"]
        return self.children[:-1]  # remove the body

    # ADDED BY ME:
    def function_declaration_get_nth_param(self, n) -> Self:
        assert self.name == "FunctionDeclaration"
        return self.function_declaration_get_params()[n]

    # ADDED BY ME:
    def then_call_get_param_identifiers(self) -> List[Self]:
        if self.name in ["ArrowFunctionExpression", "FunctionExpression"]:
            # [1] [ArrowFunctionExpression] (3 children)
            # 	[2] [Identifier:"response2"] (0 children)
            # 	[3] [Identifier:"response3"] (0 children)
            # 	...
            #
            # [1] [FunctionExpression] (3 children)
            # 	[2] [Identifier:"response2"] (0 children)
            # 	[3] [Identifier:"response3"] (0 children)
            # 	...
            params = self.children[:-1]  # [:-1] leaves out only the very last element
            identifiers = [identifier for param in params for identifier in param.function_param_get_identifiers()]
            return identifiers
        elif self.name == "FunctionDeclaration":
            # Example: "function foo(x,y,z) {}"
            # [1] [FunctionDeclaration] (5 children) --e--> [6]
            # 		[2] [Identifier:"foo"] (0 children) --data--> [...]
            # 		[3] [Identifier:"x"] (0 children)
            # 		[4] [Identifier:"y"] (0 children)
            # 		[5] [Identifier:"z"] (0 children)
            # 		[6] [BlockStatement] (0 children)
            params = self.function_declaration_get_params()  # unfortunately not as simple as [1:-1] when there are nested functions!
            identifiers = [identifier for param in params for identifier in param.function_param_get_identifiers()]
            return identifiers
        elif self.name == "Identifier":
            print(f"[Warning] Identifier {self.attributes['name']} in line {self.get_line()} in file "
                  f"{self.get_file()} could not be resolved to a function!")
            return []
        else:
            print(f"[Warning] Unexpected node in then(): {self.name}, line {self.get_line()}, "
                  f"file {self.get_file()}")
            return []

    def is_leaf(self):
        return not self.children

    def set_attribute(self, attribute_type, node_attribute):
        self.attributes[attribute_type] = node_attribute

    def set_body(self, body):
        self.body = body

    def set_body_list(self, bool_body_list):
        self.body_list = bool_body_list

    def set_parent(self, parent):
        self.parent = parent

    def set_child(self, child):
        self.children.append(child)

    def adopt_child(self, step_daddy):  # child = self changes parent
        old_parent = self.parent
        old_parent.children.remove(self)  # Old parent does not point to the child anymore
        step_daddy.children.insert(0, self)  # New parent points to the child
        self.set_parent(step_daddy)  # The child points to its new parent

    def set_statement_dependency(self, extremity):
        self.statement_dep_children.append(Dependence('statement dependency', extremity, ''))
        extremity.statement_dep_parents.append(Dependence('statement dependency', self, ''))

    # def set_comment_dependency(self, extremity):
        # self.statement_dep_children.append(Dependence('comment dependency', extremity, 'c'))
        # extremity.statement_dep_parents.append(Dependence('comment dependency', self, 'c'))

    def is_comment(self):
        if self.name in COMMENTS:
            return True
        return False

    def get_node_attributes(self):
        """ Get the attributes regex, value or name of a node. """
        node_attribute = self.attributes
        if 'regex' in node_attribute:
            regex = node_attribute['regex']
            if isinstance(regex, dict) and 'pattern' in regex:
                return True, '/' + str(regex['pattern']) + '/'
        if 'value' in node_attribute:
            value = node_attribute['value']
            if isinstance(value, dict) and 'raw' in value:
                return True, value['raw']
            return True, node_attribute['value']
        if 'name' in node_attribute:
            return True, node_attribute['name']
        return False, None  # Just None was a pb when used in get_node_value as value could be None

    def get_line(self):
        """ Gets the line number where a given node is defined. """
        try:
            line_begin = self.attributes['loc']['start']['line']
            line_end = self.attributes['loc']['end']['line']
            return str(line_begin) + ' - ' + str(line_end)
        except KeyError:
            return None

    # ADDED BY ME:
    def get_line_number_as_int(self):
        """ Gets the line number where a given node is defined (as an integer). """
        try:
            return self.attributes['loc']['start']['line']
        except KeyError:
            return None

    # ADDED BY ME:
    def get_whole_line_of_code_as_string(self):
        try:
            line_no = self.attributes['loc']['start']['line'] - 1  # counting from 1 vs. counting from 0 (here)
            filename = self.get_file()
            with open(filename, 'r') as f:
                for i, line in enumerate(f):
                    if i == line_no:
                        return line.rstrip()
        except Exception as e:
            return f"<error: {e}>"

    # ADDED BY ME: # (cf. Esprima documentation PDF, Section 3.1 Token Location)
    def get_location(self):
        """ Gets the exact location (line *and* column number) where a given node is defined. """
        try:
            start_line = self.attributes['loc']['start']['line']
            start_column = self.attributes['loc']['start']['column']
            end_line = self.attributes['loc']['end']['line']
            end_column = self.attributes['loc']['end']['column']
            return f"{start_line}:{start_column} - {end_line}:{end_column}"
        except KeyError:
            return None

    # ADDED BY ME:
    def functional_arg_get_arg(self, arg_index: int, resolve_arg_to_identifier: bool) -> Self: # ToDo: write custom Exception classes
        """
        Example 1 (used by get_all_sendResponse_sinks()):
            self                 = (message, sender, sendResponse) => { /* ... */ }
            arg_index            = 3
            return value         = sendResponse (Node)

        Example 2 (used by get_all_port_postMessage_sinks()):
            self                 = port => { /* ... */ }
            arg_index            = 0
            return value         = port (Node)

        Parameters:
            arg_index: which argument to get, zero-based index
            resolve_arg_to_identifier: resolve more complex arguments consisting of parameter name + default value
                                       (e.g., "function foo(x=42) {}") just into the Identifier.

        Returns:
            the Node representing the n-th argument of this functional argument (see examples above)

        Raises:
            a TypeError when this is neither a FunctionExpression nor an ArrowFunctionExpression nor an Identifier;
            a KeyError when this is an Identifier but the Identifier couldn't be resolved to a FunctionDeclaration;
            an IndexError when the given `arg_index` >= # of. arguments;
            an AttributeError when resolve_arg_to_identifier=True but resolving the arg to an Identifier failed
        """
        if self.name in ["FunctionExpression", "ArrowFunctionExpression"]:  # cases 1 and 2: (Arrow)FunctionExpression:
            # interface FunctionExpression {
            #     id: Identifier | null;       // == null
            #     params: FunctionParameter[];
            #     body: BlockStatement;
            # }
            # interface ArrowFunctionExpression {
            #     id: Identifier | null;             // == null
            #     params: FunctionParameter[];
            #     body: BlockStatement | Expression;
            # }
            if arg_index < (len(self.children) - 1):  # (arg, arg2, arg, block), but "block" is not an argument!
                return self.children[arg_index]  # (arg1, arg2, *arg3*)
            else:
                raise IndexError()

        elif self.name == "Identifier":  # case 3: Identifier (function reference):
            function_declaration = self.function_Identifier_get_FunctionDeclaration()
            if function_declaration is None:
                raise KeyError()
            else:
                assert function_declaration.name == "FunctionDeclaration"
                # interface FunctionDeclaration {
                #     id: Identifier | null;       // == null
                #     params: FunctionParameter[];
                #     body: BlockStatement;
                # }
                # Note that in case of nested functions, there might be additional FunctionDeclaration children(!!!)
                #
                # [1] [FunctionDeclaration] (5 children) --e--> [6]
                # 		[2] [Identifier:"msg_handler"] (0 children) --data--> [...]
                # 		[3] [Identifier:"msg"] (0 children)
                # 		[4] [Identifier:"sender"] (0 children) --data--> [...]
                # 		[5] [Identifier:"sendResponse"] (0 children) --data--> [...] --data--> [...]
                # 		[6] [BlockStatement]
                function_declaration_params = function_declaration.function_declaration_get_params()
                if arg_index < len(function_declaration_params):  # (arg1, arg2, arg3)
                    param = function_declaration_params[arg_index]  # (arg1, arg2, *arg3*)
                    if not resolve_arg_to_identifier:
                        return param
                    else:
                        # Instead of an Identifier, the FunctionParameter may also be an ArrayPattern or ObjectPattern, or
                        #     an AssignmentPattern (whose left hand side in turn may be
                        #     an Identifier, ArrayPattern or ObjectPattern; the right hand side may be any Expression):
                        # * ArrayPattern:                         function msg_handler(msg, sender, [sendResponse1, sendResponse2]) { ... }
                        # * ObjectPattern:                        function msg_handler(msg, sender, {x:x, y:y}) { ... }
                        # * AssignmentPattern, LHS=Identifier:    function msg_handler(msg, sender, sendResponse=null) { ... }
                        # * AssignmentPattern, LHS=ArrayPattern:  function msg_handler(msg, sender, [x,y]=[1,2]) { ... }
                        # * AssignmentPattern, LHS=ObjectPattern: function msg_handler(msg, sender, {x, y}={x:1,y:2}) { ... }
                        # => Here were only handle the AssignmentPattern, LHS=Identifier case using the
                        #    function_param_get_identifier() method:  # ToDo: also handle all the other cases!
                        identifier = param.function_param_get_identifier()  # necessary for "sendResponse=null" case (default param value)
                        if identifier is not None:
                            return identifier
                        else:
                            raise AttributeError()
                else:
                    raise IndexError()
        else:
            raise TypeError()

    # ADDED BY ME:
    def get_lowest_common_ancestor(self, other: Self) -> Self:
        self_ancestors = [self]
        while self_ancestors[-1].parent is not None:
            self_ancestors.append(self_ancestors[-1].parent)

        other_ancestors = [self]
        while other_ancestors[-1].parent is not None:
            other_ancestors.append(other_ancestors[-1].parent)

        for ancestor in self_ancestors:
            if ancestor in other_ancestors:
                return ancestor

        raise AssertionError("every two Nodes should have a common ancestor ([Program])")


    def get_file(self):
        parent = self
        while True:
            if parent is not None and parent.parent:
                parent = parent.parent
            else:
                break
        if parent is not None:
            if "filename" in parent.attributes:
                return parent.attributes["filename"]
        return ''


def literal_type(literal_node):
    """ Gets the type of a Literal node. """

    if 'value' in literal_node.attributes:
        literal = literal_node.attributes['value']
        if isinstance(literal, str):
            return 'String'
        if isinstance(literal, int):
            return 'Int'
        if isinstance(literal, float):
            return 'Numeric'
        if isinstance(literal, bool):
            return 'Bool'
        if literal == 'null' or literal is None:
            return 'Null'
    if 'regex' in literal_node.attributes:
        return 'RegExp'
    logging.error('The literal %s has an unknown type', literal_node.attributes['raw'])
    return None


def shorten_value_list(value_list, value_list_shortened, counter=0):
    """ When a value is a list, shorten it so that keep at most LIMIT_SIZE characters. """

    for el in value_list:
        if isinstance(el, list):
            value_list_shortened.append([])
            counter = shorten_value_list(el, value_list_shortened[-1], counter)
            if counter >= LIMIT_SIZE:
                return counter
        elif isinstance(el, str):
            counter += len(el)
            if counter < LIMIT_SIZE:
                value_list_shortened.append(el)
        else:
            counter += len(str(el))
            if counter < LIMIT_SIZE:
                value_list_shortened.append(el)
    return counter


def shorten_value_dict(value_dict, value_dict_shortened, counter=0, visited=None):
    """ When a value is a dict, shorten it so that keep at most LIMIT_SIZE characters. """

    if visited is None:
        visited = set()
    if id(value_dict) in visited:
        return counter
    visited.add(id(value_dict))

    for k, v in value_dict.items():
        if isinstance(k, str):
            counter += len(k)
        if isinstance(v, list):
            value_dict_shortened[k] = []
            counter = shorten_value_list(v, value_dict_shortened[k], counter)
            if counter >= LIMIT_SIZE:
                return counter
        elif isinstance(v, dict):
            value_dict_shortened[k] = {}
            if id(v) in visited:
                return counter
            counter = shorten_value_dict(v, value_dict_shortened[k], counter, visited)
            if counter >= LIMIT_SIZE:
                return counter
        elif isinstance(v, str):
            counter += len(v)
            if counter < LIMIT_SIZE:
                value_dict_shortened[k] = v
        else:
            counter += len(str(v))
            if counter < LIMIT_SIZE:
                value_dict_shortened[k] = v
    return counter


class Value:
    """ To store the value of a specific node. """

    def __init__(self):
        self.value = None
        self.update_value = True
        self.provenance_children = []
        self.provenance_parents = []
        self.provenance_children_set = set()
        self.provenance_parents_set = set()
        self.seen_provenance = set()

    def set_value(self, value):
        if isinstance(value, list):  # To shorten value if over LIMIT_SIZE characters
            value_shortened = []
            counter = shorten_value_list(value, value_shortened)
            if counter >= LIMIT_SIZE:
                value = value_shortened
                logging.warning('Shortened the value of %s %s', self.name, self.attributes)
        elif isinstance(value, dict):  # To shorten value if over LIMIT_SIZE characters
            value_shortened = {}
            counter = shorten_value_dict(value, value_shortened)
            if counter >= LIMIT_SIZE:
                value = value_shortened
                logging.warning('Shortened the value of %s %s', self.name, self.attributes)
        elif isinstance(value, str):  # To shorten value if over LIMIT_SIZE characters
            value = value[:LIMIT_SIZE]
        self.value = value

    def set_update_value(self, update_value):
        self.update_value = update_value

    def set_provenance_dd(self, extremity):  # Set Node provenance, set_data_dependency case
        # self is the origin of the DD while extremity is the destination of the DD
        if extremity.provenance_children:
            for child in extremity.provenance_children:
                if child not in self.provenance_children_set:
                    self.provenance_children_set.add(child)
                    self.provenance_children.append(child)
        else:
            if extremity not in self.provenance_children_set:  # NOTE BY ME: TypeError: unhashable type: 'Identifier'
                self.provenance_children_set.add(extremity)
                self.provenance_children.append(extremity)
        if self.provenance_parents:
            for parent in self.provenance_parents:
                if parent not in extremity.provenance_parents_set:
                    extremity.provenance_parents_set.add(parent)
                    extremity.provenance_parents.append(parent)
        else:
            if self not in extremity.provenance_parents_set:
                extremity.provenance_parents_set.add(self)
                extremity.provenance_parents.append(self)

    def set_provenance(self, extremity):  # Set Node provenance, computed value case
        """
        a.b = c
        """
        if extremity in self.seen_provenance:
            pass
        self.seen_provenance.add(extremity)
        # extremity was leveraged to compute the value of self
        if not isinstance(extremity, Node):  # extremity is None:
            if self not in self.provenance_parents_set:
                self.provenance_parents_set.add(self)
                self.provenance_parents.append(self)
        elif isinstance(extremity, Value):
            if extremity.provenance_parents:
                for parent in extremity.provenance_parents:
                    if parent not in self.provenance_parents_set:
                        self.provenance_parents_set.add(parent)
                        self.provenance_parents.append(parent)
            else:
                if extremity not in self.provenance_parents_set:
                    self.provenance_parents_set.add(extremity)
                    self.provenance_parents.append(extremity)
            if self.provenance_children:
                for child in self.provenance_children:
                    if child not in extremity.provenance_children_set:
                        extremity.provenance_children_set.add(child)
                        extremity.provenance_children.append(child)
            else:
                if self not in extremity.provenance_children_set:
                    extremity.provenance_children_set.add(self)
                    extremity.provenance_children.append(self)
        elif isinstance(extremity, Node):  # Otherwise very restrictive
            self.provenance_parents_set.add(extremity)
            self.provenance_parents.append(extremity)
            for extremity_child in extremity.children:  # Not necessarily useful
                self.set_provenance(extremity_child)

    def set_provenance_rec(self, extremity):
        self.set_provenance(extremity)
        for child in extremity.children:
            self.set_provenance_rec(child)


class Identifier(Node, Value):
    """ Identifier Nodes. DD is on Identifier nodes. """

    def __init__(self, name, parent):
        Node.__init__(self, name, parent)
        Value.__init__(self)
        self.code = None
        self.fun = None
        self.data_dep_parents = []
        self.data_dep_children = []

    def set_code(self, code):
        self.code = code

    def set_fun(self, fun):  # The Identifier node refers to a function ('s name)
        self.fun = fun

    def set_data_dependency(self, extremity, nearest_statement=None):
        if extremity not in [el.extremity for el in self.data_dep_children]:  # Avoids duplicates
            self.data_dep_children.append(Dependence('data dependency', extremity, 'data',
                                                     nearest_statement))
            extremity.data_dep_parents.append(Dependence('data dependency', self, 'data',
                                                         nearest_statement))
        self.set_provenance_dd(extremity)  # Stored provenance


class ValueExpr(Node, Value):
    """ Nodes from VALUE_EXPR which therefore have a value that should be stored. """

    def __init__(self, name, parent):
        Node.__init__(self, name, parent)
        Value.__init__(self)


class Statement(Node):
    """ Statement Nodes, see STATEMENTS. """

    def __init__(self, name, parent):
        Node.__init__(self, name, parent)
        self.control_dep_parents = []
        self.control_dep_children = []

    def set_control_dependency(self, extremity, label):
        self.control_dep_children.append(Dependence('control dependency', extremity, label))
        try:
            extremity.control_dep_parents.append(Dependence('control dependency', self, label))
        except AttributeError as e:
            logging.debug('Unable to build a CF to go up the tree: %s', e)

    def remove_control_dependency(self, extremity):
        for i, _ in enumerate(self.control_dep_children):
            elt = self.control_dep_children[i]
            if elt.extremity.id == extremity.id:
                del self.control_dep_children[i]
                try:
                    del extremity.control_dep_parents[i]
                except AttributeError as e:
                    logging.debug('No CF going up the tree to delete: %s', e)


class ReturnStatement(Statement, Value):
    """ ReturnStatement Node. It is a Statement that also has the attributes of a Value. """

    def __init__(self, name, parent):
        Statement.__init__(self, name, parent)
        Value.__init__(self)


class Function:
    """ To store function related information. """

    def __init__(self):
        self.fun_name = None
        self.fun_params = []
        self.fun_return = []
        self.retraverse = False  # Indicates if we are traversing a given node again
        self.called = False

    def set_fun_name(self, fun_name):
        self.fun_name = fun_name
        fun_name.set_fun(self)  # Identifier fun_name has a handler to the function declaration self

    def add_fun_param(self, fun_param):
        self.fun_params.append(fun_param)

    def add_fun_return(self, fun_return):
        # if fun_return.id not in [el.id for el in self.fun_return]:  # Avoids duplicates
        # Duplicates are okay, because we only consider the last return value from the list
        return_id_list = [el.id for el in self.fun_return]
        if not return_id_list:
            self.fun_return.append(fun_return)
        elif fun_return.id != return_id_list[-1]:  # Avoids duplicates if already considered one
            self.fun_return.append(fun_return)

    def set_retraverse(self):
        self.retraverse = True

    def call_function(self):
        self.called = True


class FunctionDeclaration(Statement, Function):
    """ FunctionDeclaration Node. It is a Statement that also has the attributes of a Function. """

    def __init__(self, name, parent):
        Statement.__init__(self, name, parent)
        Function.__init__(self)


class FunctionExpression(Node, Function):
    """ FunctionExpression and ArrowFunctionExpression Nodes. Have the attributes of a Function. """

    def __init__(self, name, parent):
        Node.__init__(self, name, parent)
        Function.__init__(self)
        self.fun_intern_name = None

    def set_fun_intern_name(self, fun_intern_name):
        self.fun_intern_name = fun_intern_name  # Name used if FunExpr referenced inside itself
        fun_intern_name.set_fun(self)  # fun_intern_name has a handler to the function declaration
