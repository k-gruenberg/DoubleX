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
import math
import random
import itertools
import os
import re
import statistics
from collections import defaultdict
from functools import total_ordering
from typing import Set, Tuple, Optional, Self, List, Any, Dict, DefaultDict

from . import utility_df
from .LHSException import LHSException
from .RHSException import RHSException
from .StaticEvalException import StaticEvalException

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
        self.body = None  # ADDED BY ME: e.g., "id", "params", "left", "right", etc.
        self.body_list = False
        self.parent = parent
        self.children = []
        self.statement_dep_parents = []
        self.statement_dep_children = []  # Between Statement and their non-Statement descendants
        self.is_wildcard = False  # <== ADDED BY ME
        self.is_identifier_regex = False  # <== ADDED BY ME

    # ADDED BY ME:
    def __eq__(self, other):
        if other is None:
            return False
        return self.id == other.id

    # ADDED BY ME: # Otherwise, there's a "TypeError: unhashable type: 'Identifier'" in set_provenance_dd().....
    def __hash__(self):
        return hash(self.id)

    # ADDED BY ME:
    def root(self) -> Self:
        """
        Returns the root Node of this tree.
        """
        if self.parent is None:
            return self
        else:
            return self.parent.root()

    # ADDED BY ME:
    def get(self, child_role: str) -> List[Self]: # todo: refactor code everywhere to use this method where applicable!
        """
        Example #1: `node` is a MemberExpression representing "x.y":
            node.get("object") yields the Node for "x"
            node.get("property") yields the Node for "y"

        Example #2: `node` is an AssignmentExpression representing "x=y":
            node.get("left") yields the Node for "x"
            node.get("right") yields the Node for "y"

        Example #3: `node` is a FunctionDeclaration representing "function foo(x,y) {return x;}":
            node.get("id") yields the Node for "foo"
            node.get("params") yields a list of 2 Nodes: ["x", "y"]
            node.get("body") yields the BlockStatement representing the function's body

        Cf. Esprima docs for all such namings!

        Note that this function always returns a list for consistency
        (which may be empty, have just 1, or any number of elements).
        """
        return [child for child in self.children if child.body == child_role]

    # ADDED BY ME:
    def all_nodes_iter(self):
        """
        Returns an iterator over all the nodes in this tree.
        """
        yield self
        for child in self.children:
            yield from child.all_nodes_iter()

    # ADDED BY ME:
    def lhs(self) -> Self:
        """
        Returns the left of the 2 children of this Node (i.e., the LHS child).
        Raises an LHSException when this Node has != 2 children!
        """
        if len(self.children) == 2:
            return self.children[0]
        else:
            raise LHSException(f"calling Node.lhs() on a Node with {len(self.children)} != 2 children")

    # ADDED BY ME:
    def rhs(self) -> Self:
        """
        Returns the right of the 2 children of this Node (i.e., the RHS child).
        Raises an RHSException when this Node has != 2 children!
        """
        if len(self.children) == 2:
            return self.children[1]
        else:
            raise RHSException(f"calling Node.rhs() on a Node with {len(self.children)} != 2 children")

    # ADDED BY ME:
    def diff(self, other: Self):
        """
        A function for debugging purposes.
        Prints differences it finds between `self` and `other` to console.
        Prints nothing when no differences are found!
        """
        if self.name != other.name:
            print(f"[Diff] self.name == '{self.name}' != '{other.name}' == other.name")
        elif len(self.children) != len(other.children):
            print(f"[Diff] "
                  f"len(self.children) == '{len(self.children)}' != '{len(other.children)}' == len(other.children)")
            return
        elif ({k: v for k,v in self.attributes.items() if k != 'filename'}
              != {k: v for k,v in other.attributes.items() if k != 'filename'}):
            print(f"[Diff] self.attributes == {self.attributes} != {other.attributes} == other.attributes")
        elif len(vars(self)) != len(vars(other)):
            print(f"[Diff] len(vars(self)) == {len(vars(self))} != {len(vars(other))} == len(vars(other))")
            self_keys = set(vars(self).keys())
            other_keys = set(vars(other).keys())
            if self_keys.issubset(other_keys):
                print(f"[Diff] other has keys that self doesn't have: {other_keys.difference(self_keys)}")
            elif other_keys.issubset(self_keys):
                print(f"[Diff] self has keys that other doesn't have: {self_keys.difference(other_keys)}")

        for key, value in vars(self).items():
            if key not in vars(other):
                print(f"[Diff] self has key '{self}' but other doesn't")
            elif isinstance(value, list):
                value_other = vars(other)[key]
                if not isinstance(value_other, list):
                    print(f"[Diff] self has key '{self}', which is a list, but for other it's not a list: {value_other}")
                elif len(value) != len(value_other):
                    print(f"[Diff] self.{key} == {value} != {value_other} == other.{key}")

        for i in range(len(self.children)):
            self.children[i].diff(other.children[i])

    # ADDED BY ME:
    def equivalent(self, other: Self) -> bool:
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
    def get_data_flow_parents(self, max_depth=1_000_000_000) -> Set[Self]:
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
    def is_data_flow_equivalent_identifier(self, other: Self, max_depth=1_000_000_000) -> bool:
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
    def identifier(cls, name: str) -> Self:
        n = cls("Identifier")
        n.attributes['name'] = name
        return n

    # ADDED BY ME:
    @classmethod
    def identifier_regex(cls, name_regex: str) -> Self:
        """
        Matches any Identifier whose name matches the given regex.
        Cf. Node.wildcard().

        Note: an `re.fullmatch` is performed.
        """
        n = cls("Identifier")
        n.attributes['name'] = name_regex
        n.is_identifier_regex = True
        return n

    # ADDED BY ME:
    @classmethod
    def literal(cls, raw: str) -> Self:
        n = cls("Literal")
        n.attributes['raw'] = raw
        return n

    # ADDED BY ME:
    @classmethod
    def wildcard(cls) -> Self:
        """
        When used as a pattern supplied to the matches() function, the wildcard will match *anything*!
        """
        n = cls("*")
        n.is_wildcard = True
        return n

    # ADDED BY ME:
    @classmethod
    def lower(cls, node1: Self, node2: Self) -> Self:
        """
        Given two Nodes, this class method returns the one which is lower in the tree.
        Returns `node1` when both nodes are equally low in the tree, i.e., when both have the same height,
        as returned by `.get_height()`.
        """
        if node1.get_height() <= node2.get_height():  # Height will be 1 for leaf nodes.
            return node1
        else:
            return node2

    # ADDED BY ME:
    def child(self, c: Self) -> Self:
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
    def get_sibling(self, idx: int) -> Self:
        sibling = self.parent.children[idx]
        # Safety check, when the programmer calls get_sibling(), he likely wants a *different* Node:
        assert sibling.id != self.id
        return sibling

    # ADDED BY ME:
    def get_sibling_relative(self, relative_index: int) -> Self:
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
    def get_sibling_relative_or_none(self, relative_index: int) -> Optional[Self]:
        """
        Cf. get_sibling_relative() but returns `None` instead of throwing an IndexError.
        Unlike get_sibling_relative() the index also doesn't wrap around back to the right when becoming
        negative.

        Use this method instead of get_sibling_relative() when you're unsure about the sibling's existence (!!!)

        Example:

        [1] parent
            [2] child A
            [3] child B
            [4] child C

        When being called on [3] child B, ...
        ...get_sibling_relative(-2) returns `None`
        ...get_sibling_relative(-1) returns [2] child A
        ...get_sibling_relative(0) returns [3] child B itself
        ...get_sibling_relative(1) returns [4] child C
        ...get_sibling_relative(2) returns `None`
        """
        self_index = self.parent.children.index(self)
        sibling_index = self_index + relative_index
        if 0 <= sibling_index < len(self.parent.children):
            return self.parent.children[self_index + relative_index]
        else:
            return None

    # ADDED BY ME:
    def get_sibling_by_name(self, name: str) -> Optional[Self]:
        for sibling in self.parent.children:
            if sibling.name == name and sibling.id != self.id:
                return sibling
        return None

    # ADDED BY ME:
    def get_only_sibling(self) -> Self:
        siblings = [c for c in self.parent.children if c.id != self.id]
        assert len(siblings) == 1
        return siblings[0]

    # ADDED BY ME:
    def has_sibling(self, name: str) -> bool:
        return self.get_sibling_by_name(name=name) is not None

    # ADDED BY ME:
    def is_sibling_of(self, other) -> bool:
        return self.parent is not None and self.parent == other.parent

    # ADDED BY ME:
    def count_siblings(self) -> int:
        return len(self.parent.children) - 1

    # ADDED BY ME:
    def siblings(self) -> List[Self]:
        """
        Returns all siblings of this Node, i.e., all the children of this Node's parent, except itself.
        """
        return [child for child in self.parent.children if child != self]

    # ADDED BY ME:
    def grandparent(self) -> Optional[Self]:
        if self.parent is None:  # No parent...
            return None  # ...no grandparent.
        return self.parent.parent  # (might be None)

    # ADDED BY ME:
    def great_grandparent(self) -> Optional[Self]:
        if self.parent is None:  # No parent...
            return None  # ...no great-grandparent.
        elif self.parent.parent is None:  # No grandparent...
            return None  # ...no great-grandparent.
        return self.parent.parent.parent  # (might be None)

    # ADDED BY ME:
    def get_parents(self) -> List[Self]:
        """
        Return the parent, grandparent, great-grandparent, etc. of this Node (in that order)
        until the root node is reached.
        """
        if self.parent is None:
            return []
        else:
            return [self.parent] + self.parent.get_parents()

    # ADDED BY ME:
    def is_inside(self, other: Self) -> bool:
        return other in self.get_parents()

    # ADDED BY ME:
    def is_inside_or_is(self, other: Self) -> bool:
        return self == other or self.is_inside(other)

    # ADDED BY ME:
    def get_parent(self, allowed_parent_names) -> Self:
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
    def get_parent_or_none(self, allowed_parent_names) -> Optional[Self]:
        if self.parent.name in allowed_parent_names:
            return self.parent
        else:
            return None

    # ADDED BY ME:
    def get_parent_or_grandparent(self, allowed_ancestor_names) -> Self:
        if self.parent.name in allowed_ancestor_names:
            return self.parent
        elif self.grandparent().name in allowed_ancestor_names:
            return self.grandparent()
        else:
            raise LookupError(f"neither parent nor grandparent of [{self.id}] has name in: {allowed_ancestor_names} "
                              f"(parent name: '{self.parent.name}', grandparent name: '{self.grandparent().name}')")

    # ADDED BY ME:
    def get_ancestor(self, allowed_ancestor_names) -> Self:
        """
        WARNING: This method raises a LookupError if no ancestor is found!
        Use get_ancestor_or_none() instead if you need a non-throwing variant of this method!!!
        """
        parent = self.parent
        while parent is not None:
            if parent.name in allowed_ancestor_names:
                return parent
            parent = parent.parent
        raise LookupError(f"no ancestor named '{allowed_ancestor_names}' found for node [{self.id}]")

    # ADDED BY ME:
    def get_ancestor_or_none(self, allowed_ancestor_names) -> Optional[Self]:
        parent = self.parent
        while parent is not None:
            if parent.name in allowed_ancestor_names:
                return parent
            parent = parent.parent
        return None

    # ADDED BY ME:
    def get_ancestor_or_self(self, allowed_ancestor_names) -> Self: # todo
        """
        WARNING: This method raises a LookupError if neither self nor any ancestor has one of the given names!
        Use get_ancestor_or_self_or_none() instead if you need a non-throwing variant of this method!!!
        """
        node = self
        while node is not None:
            if node.name in allowed_ancestor_names:
                return node
            node = node.parent
        raise LookupError(f"no ancestor (or self) named '{allowed_ancestor_names}' found for node [{self.id}]")

    # ADDED BY ME:
    def get_ancestor_or_self_or_none(self, allowed_ancestor_names) -> Optional[Self]: # todo
        node = self
        while node is not None:
            if node.name in allowed_ancestor_names:
                return node
            node = node.parent
        return None

    # ADDED BY ME:
    def has_ancestor(self, allowed_ancestor_names) -> bool:
        parent = self.parent
        while parent is not None:
            if parent.name in allowed_ancestor_names:
                return True
            parent = parent.parent
        return False

    # ADDED BY ME:
    def __str__(self) -> str:
        str_repr = ""

        attributes_of_interest = {
            "Identifier": 'name',
            "Literal": ['raw', 'value', 'regex'],  # note that 'regex' is an optional attribute of a Literal!
            "TemplateElement": ['value'],
            "BinaryExpression": 'operator',      # 'instanceof' | 'in' | '+' | '-' | '*' | '/' | '%' | '**' |
                                                 # '|' | '^' | '&' | '==' | '!=' | '===' | '!==' |
                                                 # '<' | '>' | '<=' | '<<' | '>>' | '>>>'
            "LogicalExpression": 'operator',     # || or &&
            "AssignmentExpression": 'operator',  # '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
                                                 # '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|='
            "UnaryExpression": 'operator',       # '+' | '-' | '~' | '!' | 'delete' | 'void' | 'typeof'
            "UpdateExpression": 'operator',      # '++' or '--'
            "MemberExpression": 'computed',      # (boolean)  # ToDo: handle True/False cases differently in code (x.y vs. x[y])
            "FunctionExpression": ['generator', 'async', 'expression'],  # (all booleans)
            "VariableDeclaration": 'kind',       # 'var' | 'const' | 'let'
            "Property": ['computed', 'method', 'shorthand'],
        }

        if self.name in attributes_of_interest.keys():
            if isinstance(attributes_of_interest[self.name], list):
                str_repr = f"[{self.id}] [{self.name}::{str({attr: self.attributes[attr] for attr in attributes_of_interest[self.name] if attr in self.attributes})}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"
            else:
                str_repr = f"[{self.id}] [{self.name}:\"{self.attributes[attributes_of_interest[self.name]]}\"] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"
        else:
            str_repr = f"[{self.id}] [{self.name}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"

        str_repr += f" <<< {self.body}"  # e.g., "body", "expression", "argument", "params", "left", "right", ...

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
    def mini_str(self) -> str:
        return f"[{self.id}] [{self.name}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"

    # ADDED BY ME:
    def contains_literal(self) -> bool:
        """
        Does this subtree contain any Literal (Node)?
        """
        return self.get_literal_raw() is not None

    # ADDED BY ME:
    def get_literal_raw(self) -> Optional[str]:
        """
        Returns the Literal contained inside this subtree.
        When there is no Literal to be found, `None` is returned.
        When there are multiple Literals, the first one encountered is returned.
        Returns the raw version of the literal, as it occurs in code, which is always a string
        (i.e., no conversion to integer/float/bool).
        """
        if self.name == "Literal":
            return self.attributes['raw']
        elif len(self.children) == 0:
            return None
        else:
            for child in self.children:
                child_literal = child.get_literal_raw()
                if child_literal is not None:
                    return child_literal  # return the first Literal found
            return None  # no child contains any Literal

    # ADDED BY ME:
    def get_all(self, node_name: str) -> List[Self]:
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
    def get_all_as_iter(self, node_name: Optional[str]):
        """
        Returns all nodes of a given type/name, e.g. all "VariableDeclaration" nodes.
        Unlike get_all(), which returns a list, this function returns an iterator.

        When `node_name` is `None`, returns *all* nodes!

        Performs a **pre-order** tree traversal:
            "foo(a+b, x+y)", or,
            [1] [Program] (1 child)
                [2] [ExpressionStatement] (1 child)
                    [3] [CallExpression] (3 children)
                        [4] [Identifier:"foo"] (0 children)
                        [5] [BinaryExpression:"+"] (2 children)
                            [6] [Identifier:"a"] (0 children)
                            [7] [Identifier:"b"] (0 children)
                        [8] [BinaryExpression:"+"] (2 children)
                            [9] [Identifier:"x"] (0 children)
                            [10] [Identifier:"y"] (0 children)
        ...becomes, in order (when calling `root.get_all_as_iter(None)`):
            [1] [Program]
            [2] [ExpressionStatement]
            [3] [CallExpression]
            [4] [Identifier:"foo"]
            [5] [BinaryExpression:"+"]
            [6] [Identifier:"a"]
            [7] [Identifier:"b"]
            [8] [BinaryExpression:"+"]
            [9] [Identifier:"x"]
            [10] [Identifier:"y"]
        """
        if node_name is None or self.name == node_name:
            yield self
        for child in self.children:
            yield from child.get_all_as_iter(node_name)

    # ADDED BY ME:
    def get_all_as_iter2(self, node_names: List[str]):
        """
        Like get_all_as_iter() but allows for retrieving multiple node names at once!

        Performs a **pre-order** tree traversal.

        Parameters:
            node_names: the list of Node names to retrieve, e.g., ["Identifier", "Literal"];
                        supplying the empty list `[]` will result in an empty generator being returned;
                        supplying `None` will result in an error.
        """
        if self.name in node_names:
            yield self
        for child in self.children:
            yield from child.get_all_as_iter2(node_names)

    # ADDED BY ME:
    def get_all_identifiers(self) -> List[Self]:
        return self.get_all("Identifier")

    # ADDED BY ME:
    def get_identifier_by_name(self, name: str) -> Self:
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
    def get_all_literals(self) -> List[Self]:
        return self.get_all("Literal")

    # ADDED BY ME:
    def get_all_if_statements_inside(self) -> List[Self]:
        """
        Returns all if-statements ("IfStatement" nodes) inside this piece of code as a list.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements) and will therefore be returned as well!
        """
        return self.get_all("IfStatement")

    # ADDED BY ME:
    def get_all_return_statements_inside(self) -> List[Self]:
        """
        Returns all return-statements ("ReturnStatement" nodes) inside this piece of code as a list.
        """
        return self.get_all("ReturnStatement")

    # ADDED BY ME:
    def has_child(self, child_name: str) -> bool:
        for child in self.children:
            if child.name == child_name:
                return True
        return False

    # ADDED BY ME:
    def get_child(self, child_name: str) -> Optional[Self]:
        for child in self.children:
            if child.name == child_name:
                return child
        return None

    # ADDED BY ME:
    def get_only_child(self) -> Self:
        assert len(self.children) == 1
        return self.children[0]

    # ADDED BY ME:
    def is_nth_child_of_parent(self, n: int) -> bool:
        sibling_ids = [sibling.id for sibling in self.parent.children]
        return self.id == sibling_ids[n]

    # ADDED BY ME:
    def is_nth_child_of_a(self, n: int, allowed_parent_names: List[str]) -> bool:
        if self.parent is None:
            return False
        if self.parent.name not in allowed_parent_names:
            return False
        sibling_ids = [sibling.id for sibling in self.parent.children]
        return self.id == sibling_ids[n]

    # ADDED BY ME:
    def is_within_the_nth_child_of_a(self, n: int, allowed_ancestor_names: List[str]) -> bool:
        if self.parent is None:
            return False

        prev_ancestor: Node = self
        ancestor: Node = self.parent
        while ancestor.name not in allowed_ancestor_names:
            prev_ancestor = ancestor
            ancestor = ancestor.parent
            if ancestor is None:
                return False
        assert ancestor.name in allowed_ancestor_names

        return prev_ancestor.is_nth_child_of_parent(n=n)

    # ADDED BY ME:
    def is_nth_child_of_parent_ignoring_certain_siblings(self, n: int, siblings_names_to_ignore: List[str]) -> bool:
        sibling_ids = [sibling.id for sibling in self.parent.children if sibling.name not in siblings_names_to_ignore]
        return self.id == sibling_ids[n]

    # ADDED BY ME:
    def matches(self,
                pattern: Self,
                match_identifier_names: bool,
                match_literals: bool,
                match_operators: bool,
                allow_additional_children: bool,
                allow_different_child_order: bool) -> bool:
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
        elif match_identifier_names and self.name == "Identifier" and not pattern.is_identifier_regex and pattern.attributes['name'] != self.attributes['name']:
            return False
        elif match_identifier_names and self.name == "Identifier" and pattern.is_identifier_regex and not re.fullmatch(pattern.attributes['name'], self.attributes['name']):
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
            assert len(self.children) >= len(pattern.children)  # (cf. elif check above)

            # Fill pattern up with wildcards:
            pattern_children_plus_wildcards = pattern.children + [Node.wildcard()] * (len(self.children) - len(pattern.children))
            assert len(pattern_children_plus_wildcards) == len(self.children)
            # IMPORTANT: Note that some wildcards might have already been present in the supplied pattern!!!

            permutations = itertools.permutations(pattern_children_plus_wildcards)

            # Cf. above:
            return any(all(self.children[i].matches(permutation[i], match_identifier_names, match_literals, match_operators, allow_additional_children, allow_different_child_order)
                           for i in range(len(self.children)))
                           for permutation in permutations
                           if allow_different_child_order
                              or    [el for el in permutation      if not el.is_wildcard]
                                 == [el for el in pattern.children if not el.is_wildcard]
                       )
            # The last check skips permutations that changed the order of the non-wildcard nodes if allow_different_child_order=False.

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
    def find_pattern(self,
                     pattern: Self,
                     match_identifier_names: bool,
                     match_literals: bool,
                     match_operators: bool,
                     allow_additional_children: bool,
                     allow_different_child_order: bool) -> List[Self]:
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
    def member_expression_to_string(self) -> str:
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

        elif self.lhs().name == "NewExpression":  # e.g.: "new RegExp(/^(http|https):\/\//).test" (followed by "(u[0])")
            return "<new_expression>"

        elif self.lhs().name == "Identifier":
            return self.lhs().attributes['name'] + "." + self.rhs().attributes['name']

        elif self.lhs().name == "MemberExpression": # ToDo: handle a[b] and a['b'] type member expressions as well!!!
            return self.lhs().member_expression_to_string() + "." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "ThisExpression":
            return "this()." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "Identifier":
            return self.lhs().children[0].attributes['name'] + "()." + self.rhs().attributes['name']

        elif self.lhs().name == "CallExpression" and self.lhs().children[0].name == "MemberExpression":
            return self.lhs().children[0].member_expression_to_string() + "()." + self.rhs().attributes['name']

        else:
            raise TypeError(f"member_expression_to_string(): LHS of MemberExpression in line {self.get_line()} "
                            f"is neither a ThisExpression "
                            f"nor an Identifier nor a MemberExpression: {self.lhs()}")

    # ADDED BY ME:
    def find_member_expressions_ending_in(self, suffix: str) -> List[Self]:
        result = []
        for member_expr in self.get_all_as_iter("MemberExpression"):
            if member_expr.member_expression_to_string().endswith(suffix):
                result.append(member_expr)
        return result

    # ADDED BY ME:
    def member_expression_get_leftmost_identifier(self) -> Self:
        """
        Note that the Node returned may not necessarily *be* an Identifier, so be sure to check that!
        (May also be a ThisExpression or FunctionExpression, for example.)
        """
        if self.name != "MemberExpression":
            raise TypeError("member_expression_get_leftmost_identifier() may only be called on a MemberExpression")
        elif len(self.children) == 0:
            raise TypeError("member_expression_get_leftmost_identifier() called on a MemberExpression w/o any children")

        leftmost_identifier = self.children[0]

        while leftmost_identifier.name == "MemberExpression":
            leftmost_identifier = leftmost_identifier.children[0]

        return leftmost_identifier

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
        => ToDo: fix!

        Note that the returned value may also be more complex:
        * call_expression_get_full_function_name("x().y()") ==returns==> "x().y"
        * call_expression_get_full_function_name("x(a,b).y()") ==returns==> "x().y"
        
        Raises an Exception when called on a Node that isn't a CallExpression!
        Returns "<function_expression>" when the CallExpression calls a FunctionExpression (IIFE)!
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

        elif callee.name == "FunctionExpression":  # "!function(x) {console.log(x)}(42)"
            return "<function_expression>"

        else:
            raise TypeError(f"call_expression_get_full_function_name(): "
                            f"Unsupported type of callee Expression used for a CallExpression "
                            f"in line {callee.get_line()}: {callee}")

    # ADDED BY ME:
    def call_expression_get_all_arguments(self) -> List[Self]:
        # interface CallExpression {
        #     callee: Expression | Import;
        #     arguments: ArgumentListElement[];
        # }
        assert self.name == "CallExpression"
        return self.children[1:]

    DEFAULT_SENSITIVE_APIS = ["chrome.cookies", "chrome.scripting", "chrome.tabs.executeScript",
                              "browser.cookies", "browser.scripting", "browser.tabs.executeScript",
                              "indexedDB", "fetch"]

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
    def get_statement(self) -> Optional[Self]:
        """
        If this Node isn't a Statement itself already, this function returns the Statement that this Node is a part of,
        by going up the PDG parent-by-parent until a Statement is found.

        This function is useful when dealing with control flow.

        Returns `None` when this Node isn't part of any Statement.
        """
        if self.name in STATEMENTS:
            return self
        elif self.parent is not None:
            return self.parent.get_statement()
        else:
            return None

    # ADDED BY ME:
    def get_next_higher_up_statement(self) -> Optional[Self]:
        """
        This function returns the Statement that this Node is a part of,
        by going up the PDG parent-by-parent until a Statement is found.

        If this Node is a Statement *itself* does not matter here.
        If you need a function that returns the node itself when it's a Statement already, use get_statement() instead.

        Returns `None` when this Node doesn't have any higher up Statement above it, e.g., when you call this
        function on the root node of the tree!
        """
        if self.parent is not None:
            return self.parent.get_statement()
        else:
            return None

    # ADDED BY ME:
    def get_innermost_surrounding_if_statement(self) -> Optional[Self]:
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
    def get_all_surrounding_if_statements(self) -> List[Self]:
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
    def is_return_statement(self) -> bool:
        """
        Returns True iff this very Statement is a ReturnStatement itself.
        To check if this node is simply *inside* a ReturnStatement, use is_inside_return_statement() instead!
        """
        return self.name == "ReturnStatement"

    # ADDED BY ME:
    def is_inside_return_statement(self) -> bool:
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
    def is_if_statement(self) -> bool:
        """
        Returns True iff this node is an "IfStatement" node.

        Note that else-if branches are modelled as nested IfStatements (IfStatements inside the else-branches of other
        IfStatements); therefore this function will *also* returned true when called on an IfStatement representing an
        else-if branch!

        All IfStatements have either 2 or 3 children (3 only when there's an else and/or else-if branch).
        """
        return self.name == "IfStatement"

    # ADDED BY ME:
    def if_statement_has_else_branch(self) -> bool:
        """
        Returns True iff this IfStatement has an else branch.
        Raises an exception when this node isn't an "IfStatement" node; use is_if_statement() to check that beforehand.

        Else-if branches are *not* counted as else branches! Use if_statement_has_else_if_branch() for that instead.
        """
        return self.if_statement_get_else_branch() is not None

    # ADDED BY ME:
    def if_statement_get_else_branch(self) -> Optional[Self]:
        """
        Returns the else branch of this IfStatement (will always be of type "BlockStatement").
        Returns `None` when this IfStatement has no else branch.
        Raises an exception when this node isn't an "IfStatement" node; use is_if_statement() to check that beforehand.

        If you just want to know whether there *is* an else branch or not, you may also use
        if_statement_has_else_branch().
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
    def if_statement_has_else_if_branch(self) -> bool:
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

    # ADDED BY ME:
    def occurs_in_code_before(self, other_node: Self) -> bool:
        assert self.get_file() == other_node.get_file()

        self_start_line = int(self.attributes['loc']['start']['line'])
        self_start_column = int(self.attributes['loc']['start']['column'])

        other_start_line = int(other_node.attributes['loc']['start']['line'])
        other_start_column = int(other_node.attributes['loc']['start']['column'])

        return self_start_line < other_start_line or\
                (self_start_line == other_start_line and self_start_column < other_start_column)

    # ADDED BY ME:
    def occurs_in_code_after(self, other_node: Self) -> bool:
        assert self.get_file() == other_node.get_file()

        self_start_line = int(self.attributes['loc']['start']['line'])
        self_start_column = int(self.attributes['loc']['start']['column'])

        other_start_line = int(other_node.attributes['loc']['start']['line'])
        other_start_column = int(other_node.attributes['loc']['start']['column'])

        return self_start_line > other_start_line or \
            (self_start_line == other_start_line and self_start_column > other_start_column)

    # ADDED BY ME:
    def might_occur_after(self, other_node: Self) -> bool:
        """
        Take a look at the following piece of JavaScript code:
            function foo() { x = [id2]; } [id1] = y; foo();
        Even though "[id1] = y" occurs after "x = [id2];" *in code*, it happens *before* it during execution.

        Other examples of this include:
            function foo() { x = [id2]; [id1] = y; } foo(); foo();

        This method is intended to allow for handling such cases.
        It returns True if `self` *might* occur after `other_node`, because...
        (a) `self` occurs inside a declared function that is called after `other_node`
        (b) `self` and `other_node` occur within the same function declaration/expression body (not talking about
            nested functions here but in the very *same* function!) and that function is called somewhere
            (in case of function expressions that has to be recursively)

        *** BEWARE: ***
        This method does NOT(!) check/do anything about Identifiers!
        It is more to be seen as an addition to Node.occurs_in_code_after()!
        For handling Identifiers, you likely have to check Node.identifier_is_in_scope_at() as well!
        """
        # (a) `self` occurs inside a declared function that is called after `other_node`:
        self_func_decl: Optional[Node] = self.get_ancestor_or_none(["FunctionDeclaration"])
        if self_func_decl is not None:
            self_func_decl_scope: Node = self_func_decl.function_declaration_get_scope()
            # Look for CallExpressions calling the function declared by `self_func_decl`:
            for call_expr in self_func_decl_scope.get_all_as_iter("CallExpression"):
                if (call_expr.children[0].name == "Identifier" and
                        call_expr.children[0].attributes['name'] == self_func_decl.function_declaration_get_name()):
                    if call_expr.occurs_in_code_after(other_node):
                        return True

        # (b) `self` and `other_node` occur within the same function declaration/expression body (not talking about
        #     nested functions here but in the very *same* function!) and that function is called somewhere
        #     (in case of function expressions that has to be recursively; note that ArrowFuncExpr cannot do that!):
        self_func: Optional[Node] = self.get_ancestor_or_none(
            ["FunctionDeclaration", "FunctionExpression"])
        other_func: Optional[Node] = other_node.get_ancestor_or_none(
            ["FunctionDeclaration", "FunctionExpression"])
        if self_func is not None and self_func == other_func:
            if self_func.name == "FunctionDeclaration":
                return self_func.function_declaration_is_called_anywhere()
            elif self_func.name == "FunctionExpression":
                return self_func.function_expression_calls_itself_recursively()

        return False

    # ADDED BY ME:
    def code_occurrence(self):
        """
        Returns a `CodeOccurrence` object that can be compared to other `CodeOccurrence` objects returned by this
        function using <, <=, >, >=, ==, != operators.
        """
        @total_ordering
        class CodeOccurrence:
            def __init__(self, line, column):
                self.line = line
                self.column = column

            def __eq__(self, other):
                if other is None:
                    return False
                return self.line == other.line and self.column == other.column

            def __lt__(self, other):  # implements the "<" operator; cf. logic in occurs_in_code_before()
                return self.line < other.line or (self.line == other.line and self.column < other.column)

        self_start_line = int(self.attributes['loc']['start']['line'])
        self_start_column = int(self.attributes['loc']['start']['column'])
        return CodeOccurrence(line=self_start_line, column=self_start_column)

    # ADDED BY ME:
    def lies_within(self, other_node: Self) -> bool:
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

    # ADDED BY ME:
    def lies_within_piece_of_code(self, other_start_line: int, other_start_col: int,
                                  other_end_line: int, other_end_col: int) -> bool:
        self_start_line, self_start_col, self_end_line, self_end_col = self.get_location_as_tuple()

        # Example: If other_start_line == other_end_line == self_start_line == self_end_line:
        # other_start_col ************************************************************ other_end_col
        #                            self_start_col ----------- self_end_col

        other_starts_before_self: bool = (other_start_line < self_start_line)\
                                         or (other_start_line == self_start_line and other_start_col <= self_start_col)
        self_ends_before_other: bool = (self_end_line < other_end_line)\
                                         or (self_end_line == other_end_line and self_end_col <= other_end_col)

        return other_starts_before_self and self_ends_before_other

    # Python regex recap (cf. https://docs.python.org/3/library/re.html):
    # re.search(pattern, string, flags=0) => Scan through str looking for the first loc where the regex produces a match
    # re.match(pattern, string, flags=0) => If zero or more characters at the beginning of string match the regex
    # re.fullmatch(pattern, string, flags=0) => If the whole string matches the regex pattern

    # ADDED BY ME:
    def string_literal_without_quotation_marks(self) -> str:
        """
        When this is a String Literal, returns the literal string w/o quotation marks.

        Raises an AssertionError when called on a non-Literal.
        Raises a TypeError when called on a non-string Literal.

        Note that JavaScript has 3 different valid quotation marks: "", '' and ``
        Backticks generate TemplateLiterals instead of Literals though and will therefore raise an AssertionError!
        """
        # Example JavaScript ExpressionStatement: "foo"
        # ...becomes: [1] [Literal::{'raw': '"foo"', 'value': 'foo'}] (0 children)
        assert self.name == "Literal"
        self_value = self.attributes['value']
        if isinstance(self_value, str):
            return self_value
        else:
            raise TypeError("Node.string_literal_without_quotation_marks() called on a non-string literal!")

    # ADDED BY ME:
    def string_literal_matches_full_regex(self, regex: str) -> bool:
        return re.fullmatch(regex, self.string_literal_without_quotation_marks()) is not None

    # ADDED BY ME:
    def string_literal_contains_regex(self, regex: str) -> bool:
        return re.search(regex, self.string_literal_without_quotation_marks()) is not None

    # ADDED BY ME:
    def any_literal_inside_matches_full_regex(self, regex: str) -> bool:
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
    def any_literal_inside_contains_regex(self, regex: str) -> bool:
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
    def any_string_literal_inside_matches_full_regex(self, regex: str) -> bool:
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
        # const string3 = `Yet another string primitive`; // <----- We do not consider template strings!
        for literal in self.get_all_literals():
            raw = literal.attributes['raw']
            if raw[0] == raw[-1] and raw[0] in ["\"", "'"]:  # literal is a (correct) string literal
                string_inside_quotes = raw[1:-1]  # remove the quotation marks
                if re.fullmatch(regex, string_inside_quotes):
                    return True
        return False

    # ADDED BY ME:
    def any_string_literal_inside_contains_regex(self, regex: str) -> bool:
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
    def get_height(self) -> int:
        """
        Height will be 1 for leaf nodes.
        """
        if len(self.children) == 0:
            return 1
        else:
            return 1 + max(child.get_height() for child in self.children)

    # ADDED BY ME:
    def promise_returning_function_call_get_all_then_calls(self, resolve_function_references=True) -> List[Self]:
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
                    function_declaration = then_call.function_Identifier_get_FunctionDeclaration(True)
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
    def data_flow_distance_to(self, other: Self) -> float:
        """
        Returns the "distance" of this Identifier to another Identifier,
        in terms of the number of data flow edges one has to traverse from `self`, in order to reach `other`.
        Returns an integer, unless there is no data flow from `self` to `other`, in that case it returns infinity.
        Returns the length of the shortest data flow path when there are multiple paths from `self` to `other`.
        """
        assert self.name == "Identifier" and other.name == "Identifier"
        if self == other:
            return 0
        elif len(self.data_dep_children) == 0:
            return float("inf")
        else:
            return 1 + min(data_flow_child.extremity.data_flow_distance_to(other)
                           for data_flow_child in self.data_dep_children)

    # ADDED BY ME:
    def function_Identifier_get_FunctionDeclaration(self,
                                                    print_warning_if_not_found: bool,
                                                    add_data_flow_edges=True) -> Optional[Self]:
        """
        When this Node is an Identifier referencing a function, this method returns the corresponding
        FunctionDeclaration where said function is defined.

        When no FunctionDeclaration could be found, `None` is returned and a warning message is printed to console
        (but only if the `print_warning_if_not_found` parameter was set to `True`).

        This function does *not* use data flow edges (which might be missing in more complex programs...).
        Instead, it looks for all FunctionDeclarations that are in scope and returns the one with the same name as
        this Identifier (or `None` if no FunctionDeclaration in scope has the same name as this Identifier).

        When there are *multiple* functions both in scope and with the same name, the function within the innermost
        scope shadows all the others and will therefore be the one returned; an example:

            function foo() {return 1;}
            function bar() {
                function foo() {return 2;}
                console.log(foo());
            }

        According to the Mozilla docs, "[t]he scope of a function declaration is the function in which it is declared
        (or the entire program, if it is declared at the top level)."
        => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions

        ***** DISCLAIMER: *****
        In JavaScript, named functions cannot just be declared using FunctionDeclarations, but also by assigning to an
        identifier (as functions are objects in JavaScript, too); take the following example:
            foo = ((x) => {return x;});
            foo(42);
        Moreover, there can be a function "foo" being declared in the regular way that is *overwritten* by such a
        more obscure function definition; take the following example:
            function foo() {return 1;}
            function bar() {
                var foo = (() => {return 2;});
                console.log(foo()); // prints 2 and not 1
            }
        WE DO NOT HANDLE THESE COMPLEX CASES!
        This has the following 2 consequences:
        1. This function may return `None`, even though there *is* a corresponding function for this function call
           identifier, it just isn't set via a "plain regular" FunctionDeclaration but rather in a manner as shown
           above.
        2. This function may return a FunctionDeclaration that *isn't* actually the function called with this function
           call because it is overshadowed by an identifier in local scope that isn't defined via a regular
           FunctionDeclaration.
        This means that there may be both *missing* and *incorrect* data flows, depending on the circumstances!
        ***** END OF DISCLAIMER *****

        Raises an `AssertionError` when:
        * `self.name != "Identifier"`

        Parameters:
            print_warning_if_not_found: whether to print a warning to console when no FunctionDeclaration could be
                                        found / `None` is returned; should only be set to True if you do not *expect*
                                        this function to return None, unless there's something wrong!
            add_data_flow_edges: when set to True (default), a data flow edge will be added to the PDG from
                                 FunctionDeclaration Identifier to the CallExpression Identifier (self); *if*
                                 a corresponding FunctionDeclaration was found for this function Identifier that is;
                                 when set to False, the PDG will remain unaltered.

        Returns:
            (a) the FunctionDeclaration Node declaring the function referenced by this Identifier; or
            (b) None when no FunctionDeclaration could be found for this Identifier.
        """

        # Examples:
        #
        # 1. function foo() { function bar() { function baz() {return 42;} return baz(); } return baz(); }
        #                                                                                         ^^^
        #    => throws: Uncaught ReferenceError: baz is not defined
        #    => FunctionDeclarations inside FunctionDeclaration siblings are *not* in scope!
        #
        #    - foo
        #        - bar      <--- scope of declaration: bar
        #            - baz  <--- declaration
        #        - baz()    <--- call: fails! (as it's not in 'bar')
        #
        # 2. function foo() {
        #        function bar() { function baz() {return boo();} return baz(); }
        #        function boo() { return 43; }           ^^^
        #        return bar();
        #    }
        #
        #    - foo                <--- scope of declaration: foo
        #        - bar
        #            - baz
        #                - boo()  <--- call: works! (as it *is* in 'foo')
        #        - boo            <--- declaration
        #
        #    => works; calling foo() returns 43
        #    => sibling FunctionDeclarations of an ancestor FunctionDeclaration *are* in scope!
        #
        # => "The scope of a function declaration is the function in which it is declared" (Mozilla docs)

        assert self.name == "Identifier"

        function_declarations_in_scope = [fd for fd in self.root().get_all_as_iter("FunctionDeclaration")
                                          if fd.function_declaration_get_name() == self.attributes['name']
                                          and self.is_inside(fd.function_declaration_get_scope())]

        if len(function_declarations_in_scope) == 0:
            if print_warning_if_not_found:
                print(f"[Warning] no function definition found for call to '{self.attributes['name']}' in line "
                      f"{self.get_line()} (file {self.get_file()})")
            return None

        elif len(function_declarations_in_scope) == 1:
            func_decl = function_declarations_in_scope[0]
            print(f"[Info] function declaration for call to '{self.attributes['name']}' in line "
                  f"{self.get_line()} (file {self.get_file()}) found in line "
                  f"{func_decl.get_line()}: '{func_decl.function_declaration_get_name()}'")
            if add_data_flow_edges:
                # While already at it, add a data flow edge on the fly:
                #     declaration identifier --data--> call identifier
                #     (DoubleX should add all of those but doesn't!)
                function_decl_identifier = func_decl.function_declaration_get_function_identifier()
                if function_decl_identifier.set_data_dependency(self):  # returns 1 if edge was added, 0 if existed
                    print(f"[Info] added missing data flow edge from function declaration identifier "
                          f"'{function_decl_identifier.attributes['name']}' in line "
                          f"{function_decl_identifier.get_line()} "
                          f"to function identifier '{self.attributes['name']}' in line {self.get_line()}")
                    # ToDo: doesn't this spam a bit too much sometimes?!
            return func_decl

        else:
            # Multiple FunctionDeclarations with the correct name are in scope.
            # An example for this would be this:
            #
            # function foo() {return 1;}      // <----- in scope
            # function bar() {
            #     function foo() {return 2;}  // <----- in scope (innermost)
            #     console.log(foo());         // <----- call/reference to a function named "foo"
            # }
            #
            # Resolve this issue by returning the innermost matching FunctionDeclaration in scope:
            innermost_func_decl = function_declarations_in_scope[0]
            innermost_func_decl_scope = innermost_func_decl.function_declaration_get_scope()
            for func_decl in function_declarations_in_scope[1:]:
                func_decl_scope = func_decl.function_declaration_get_scope()
                if func_decl_scope.is_inside(innermost_func_decl_scope):
                    innermost_func_decl = func_decl
                    innermost_func_decl_scope = func_decl_scope
            return innermost_func_decl

    # ADDED BY ME:
    def declaration_get_scope(self) -> Self:
        """
        When this Node is a Node acting as a declaration, namely one of the following...:
            - FunctionDeclaration
            - VariableDeclaration
            - ClassDeclaration
            - FunctionExpression
            - ArrowFunctionExpression
            - AssignmentExpression (note that this function does *not* check whether the given AssignmentExpression
              actually *does* act as an (implicit global) assignment!)
        ...returns the scope of said declaration.

        Cf.:
            - Node.function_declaration_get_scope()
            - Node.variable_declaration_get_scope()
            - Node.class_declaration_get_scope()
        """
        if self.name == "FunctionDeclaration":
            return self.function_declaration_get_scope()
        elif self.name == "VariableDeclaration":
            return self.variable_declaration_get_scope()
        elif self.name == "ClassDeclaration":
            return self.class_declaration_get_scope()
        elif self.name in ["FunctionExpression", "ArrowFunctionExpression"]:
            # Both names of FunctionExpressions and parameters of (Arrow)FunctionExpressions
            #   are in scope only within themselves(!):
            return self
        elif self.name == "AssignmentExpression":
            # If an AssignmentExpression acts as a *declaration*, it's an implicit declaration of a global variable(!):
            return self.root()
        else:
            raise AssertionError("Node.declaration_get_scope(self): self is not a declaration!")

    # ADDED BY ME:
    def function_declaration_get_scope(self) -> Self:
        """
        For a given FunctionDeclaration (self), returns the entire subtree in which said FunctionDeclaration is
        accessible/in scope.

        According to the Mozilla docs, "[t]he scope of a function declaration is the function in which it is declared
        (or the entire program, if it is declared at the top level)."
        => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Functions

        If the scope is indeed the entire program, the PDGs "Program" root node will be returned by this function!
        """
        assert self.name == "FunctionDeclaration"
        p = self.parent
        while p.name not in ["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression", "Program"]:
            p = p.parent
        return p
        # Don't forget that functions might be declared inside ArrowFunctionExpressions as well, the scope is going
        # to be that very ArrowFunctionExpression then:
        #     (() => {function foo() {return 42;} console.log(foo());})();

    # ADDED BY ME:
    def variable_declaration_get_scope(self) -> Self:
        """
        For a given VariableDeclaration (self), returns the entire subtree in which said VariableDeclaration is
        accessible/in scope.

        Note that the result depends on whether the VariableDeclaration is of kind 'var', 'const' or 'let':

        * for 'var' VariableDeclaration, the scope is either the function in which it is declared, or the entire
          program (cf. function_declaration_get_scope())
          => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/var
        * 'let' and 'const' VariableDeclarations, on the other hand, both declare "block-scoped local variables"
          => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/let
          => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/const
        """
        # interface VariableDeclaration {
        #     declarations: VariableDeclarator[];
        #     kind: 'var' | 'const' | 'let';
        # }
        assert self.name == "VariableDeclaration"

        if self.attributes['kind'] == 'var':
            parent_names = ["FunctionDeclaration", "FunctionExpression", "ArrowFunctionExpression", "Program"]
            # => cf. function_declaration_get_scope()
        elif self.attributes['kind'] in ['const', 'let']:
            parent_names = ["BlockStatement", "Program"]
        else:
            raise AssertionError("'kind' of VariableDeclaration not in ['var', 'const', 'let']")

        p = self.parent
        while p.name not in parent_names:
            p = p.parent
        return p

    # ADDED BY ME:
    def class_declaration_get_scope(self) -> Self:
        """
        For a given ClassDeclaration (self), returns the entire subtree in which said ClassDeclaration is
        accessible/in scope.

        Notes (taken from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/class):
            * "The class declaration is very similar to let"
            * "class declarations are commonly regarded as non-hoisted (unlike function declarations)"
            * "class declarations cannot be redeclared by any other declaration in the same scope."

        The following, for example, will *not* work:
            {class Bar {}}
            new Bar()       // raises: "Uncaught ReferenceError: Bar is not defined"
        """
        # interface ClassDeclaration {
        #     id: Identifier | null;
        #     superClass: Identifier | null;
        #     body: ClassBody;
        # }
        assert self.name == "ClassDeclaration"
        p = self.parent
        while p.name not in ["BlockStatement", "Program"]:
            p = p.parent
        return p

    # ADDED BY ME:
    def identifier_is_assigned_to_before(self, other: Self, scope: Self) -> bool:
        """
        Whether the Identifier represented by `self` is assigned to (i.e., is within the LHS of an AssignmentExpression)
        between `self` and `other`.

        *** IMPLEMENTATION DETAILS: ***
        Note that this function will also return True if `other` *itself* is part of such an AssignmentExpression
        (and `other` is an Identifier with the same name as `self`) !!!
        This function will return False however, if `other` itself *is* such an AssignmentExpression
        (i.e., `other.name == "AssignmentExpression"`) !!!

        Note that AssignmentExpressions that `self` is a part of will be ignored !!!
        If `self` itself is an AssignmentExpression, it will also be ignored !!!

        *** IMPORTANT: ***
        This method does *not* use data flow edges as it'll be used *during* data flow edge creation!
        Instead, it assumes that there's no overshadowing of the Identifier name between `self` and `other`!

        Edge cases:
        * when `self == other`, the entire `scope`, beginning at `self`, will be analyzed for AssignmentExpressions
          (i.e., `other` will be practically ignored)

        Parameters:
            other: the `other` Node
            scope: the scope of the Identifier `self`; `other` has to be inside this scope as well
        """
        assert self.name == "Identifier"
        if not self.is_inside(scope):
            raise AssertionError(f"self ([{self.mini_str()}) is not inside scope ({scope.mini_str()})")
        if not other.is_inside(scope):
            raise AssertionError(f"other ({other.mini_str()}) is not inside scope ({scope.mini_str()})")

        # [1] scope (of self)
        #     [2] A
        #     [3] B
        #     [4] Identifier: self (e.g., where it is declared)
        #     [5] C
        #     [6] AssignmentExpression: self = ...
        #     [7] D
        #     [8] Node: other
        #     [9] E

        encountered_self: bool = False

        for node in scope.get_all_as_iter(None):  # <= performs a pre-order tree traversal
            if node == self:
                encountered_self = True
            elif not encountered_self:
                continue
            elif node == other:
                # This check has to occur before the next check, otherwise the loop would continue if
                #     other.name == "AssignmentExpression"!
                return False
            elif node.name == "AssignmentExpression":
                # interface AssignmentExpression {
                #     operator: '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
                #               '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|=';
                #     left: Expression;
                #     right: Expression;
                # }
                for identifier in node.lhs().get_all_identifiers():
                    if identifier.attributes['name'] == self.attributes['name']:
                        return True

        # never encountered `other` => `other` comes before `self`
        #   => `self` can't possibly be assigned to before `other` => return False
        return False

    # ADDED BY ME:
    def get_identifiers_declared_in_scope(self,
                                          return_overshadowed_identifiers: bool,
                                          return_reassigned_identifiers: bool) -> List[Self]:
        """
        Returns all Identifiers that are in scope as seen from this Node.
        These may be Identifiers referring to variables, functions, function parameters, or classes.
        Returns the Identifier Nodes from each identifier's respective point of declaration.
        That point of declaration may be one of the following:
        * explicit declarations:
          - variables declared using "let" or "const" (scope=block)
          - variables declared using "var" (scope=function)
          - functions declared using "function" (scope=function)
          - classes declared using "class" (scope=block, same as "let")
          - parameters of declared functions (scope=only within the function itself)
          - named FunctionExpressions (scope=only within themselves)
          - parameters of FunctionExpressions and ArrowFunctionExpressions (scope=only within the function expr itself)
        * implicit declarations:
          - assignments to previously undeclared identifiers, implicitly creating a global variable with that name
            (scope=global)

        If this Node is an Identifier and you want to know what Identifier (declaration) it refers to,
        simply set return_overshadowed_identifiers=False and return_reassigned_identifiers=True and
        filter the output for all Identifiers with the same name.
        The Node.resolve_identifier() method does exactly that for you!
        ===> A note on this:
        Note that the declaration might be in scope but occur after this Node; this doesn't matter however
        because of hoisting (cf. https://developer.mozilla.org/en-US/docs/Glossary/Hoisting):
        (Example 1) FunctionDeclarations exhibit hoisting with type 1 behavior ("Value hoisting"):
            hoisted(); // Logs "foo"
            function hoisted() {
              console.log("foo");
            }
            // => Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/function
        (Example 2) "var" declarations exhibit hoisting with type 2 behavior ("Declaration hoisting"):
            bla = 2;
            var bla;
            // => Source: https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/var
        (Example 3) "let", "const" & "class" declarations exhibit hoisting with type 3 behavior ("temporal dead zone"):
            const x = 1;
            {
              console.log(x); // ReferenceError
              const x = 2;
            }
            // => Source: https://developer.mozilla.org/en-US/docs/Glossary/Hoisting

        Parameters:
            return_overshadowed_identifiers: whether to return Identifiers whose declaration *is* in scope but that
                                             have been overshadowed by other Identifiers with the same name
            return_reassigned_identifiers: whether to return Identifiers whose declaration *is* in scope but that
                                           have been reassigned since (this has nothing to do with the actual scope
                                           but is useful for handling data flows nonetheless)
        """
        # Note that we *have* to go through the *entire* AST/PDG tree for this!!!
        #   (even if we're deep into the tree, stuff from way *up* the tree might be in scope!)
        root: Node = self.root()
        if self == root:
            raise Exception("get_identifiers_declared_in_scope() may not be called on the root node, "
                            "it has to be some position in code of which you want to retrieve the identifiers in scope")

        declared_identifiers: DefaultDict[str, List[Tuple[Node, Node]]] = defaultdict(list)
        # => shall map all declared Identifiers that are in scope at `self` to the scopes that they're available in
        #    (for each such scope, `self.is_inside_or_is(scope)`); grouped by Identifier name
        # => todo: cache within `self` for better performance of repeated calls!!!

        # Go once through the *entire* AST/PDG and look for all declarations whose scope includes `self`:
        for node in root.get_all_as_iter(None):  # => performs a pre-order tree traversal
            match node.name:

                # - variables declared using "let" or "const" (scope=block):
                # - variables declared using "var" (scope=function):
                case "VariableDeclaration":
                    # interface VariableDeclaration {
                    #     declarations: VariableDeclarator[];
                    #     kind: 'var' | 'const' | 'let';
                    # }
                    scope: Node = node.variable_declaration_get_scope()  # handles "let", "const" *and* "var"!
                    if self.is_inside_or_is(scope):
                        for variable_declarator in node.get_all_as_iter("VariableDeclarator"):
                            # interface VariableDeclarator {
                            #     id: Identifier | BindingPattern;
                            #     init: Expression | null;
                            # }
                            for identifier in variable_declarator.children[0].get_all_as_iter("Identifier"):
                                declared_identifiers[identifier.attributes['name']].append((identifier, scope))

                # - functions declared using "function" (scope=function):
                # - parameters of declared functions (scope=only within the function itself):
                case "FunctionDeclaration":
                    # interface FunctionDeclaration {
                    #     id: Identifier | null;
                    #     params: FunctionParameter[];
                    #     body: BlockStatement;
                    # }
                    function_identifier_scope: Node = node.function_declaration_get_scope()
                    if self.is_inside_or_is(function_identifier_scope):
                        function_identifier: Node = node.function_declaration_get_function_identifier()
                        declared_identifiers[function_identifier.attributes['name']]\
                            .append((function_identifier, function_identifier_scope))
                    function_parameters_scope: Node = node
                    if self.is_inside_or_is(function_parameters_scope):
                        for param in node.function_declaration_get_params():
                            for identifier in param.function_param_get_identifiers():
                                declared_identifiers[identifier.attributes['name']]\
                                    .append((identifier, function_parameters_scope))

                # - classes declared using "class" (scope=block, same as "let"):
                case "ClassDeclaration":
                    # interface ClassDeclaration {
                    #     id: Identifier | null;
                    #     superClass: Identifier | null;
                    #     body: ClassBody;
                    # }
                    scope: Node = node.class_declaration_get_scope()
                    if self.is_inside_or_is(scope):
                        identifier: Node = node.class_declaration_get_class_identifier()
                        declared_identifiers[identifier.attributes['name']].append((identifier, scope))

                # - named FunctionExpressions (scope=only within themselves):
                # - parameters of FunctionExpressions (scope=only within the function expr itself):
                case "FunctionExpression":
                    # interface FunctionExpression {
                    #     id: Identifier | null;
                    #     params: FunctionParameter[];
                    #     body: BlockStatement;
                    #     generator: boolean;
                    #     async: boolean;
                    #     expression: boolean;
                    # }
                    scope: Node = node
                    if self.is_inside_or_is(scope):
                        func_expr_id: Optional[Node] = node.function_expression_get_id_node()
                        if func_expr_id is not None:
                            declared_identifiers[func_expr_id.attributes['name']].append((func_expr_id, scope))
                        for param in node.arrow_function_expression_get_params():
                            for identifier in param.function_param_get_identifiers():
                                declared_identifiers[identifier.attributes['name']].append((identifier, scope))

                # - parameters of ArrowFunctionExpressions (scope=only within the function expr itself)
                case "ArrowFunctionExpression":
                    # interface ArrowFunctionExpression {
                    #     id: Identifier | null;
                    #     params: FunctionParameter[];
                    #     body: BlockStatement | Expression;
                    #     generator: boolean;
                    #     async: boolean;
                    #     expression: false;
                    # }
                    scope: Node = node
                    if self.is_inside_or_is(scope):
                        for param in node.arrow_function_expression_get_params():
                            for identifier in param.function_param_get_identifiers():
                                declared_identifiers[identifier.attributes['name']].append((identifier, scope))

                # - assignments to previously undeclared identifiers,
                #   implicitly creating a **global** variable with that name (scope=global);
                #   note that this behavior is only exhibited in non-strict mode(!) (which is the default however):
                case "AssignmentExpression":  # todo: add a strict_mode parameter / a Node.strict_mode attribute?!
                    # interface AssignmentExpression {
                    #     operator: '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
                    #               '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|=';
                    #     left: Expression;
                    #     right: Expression;
                    # }
                    for identifier in node.lhs().get_all_identifiers():
                        # "If y is not a pre-existing variable, a global variable y is implicitly created in
                        #  non-strict mode, or a ReferenceError is thrown in strict mode."
                        # => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Assignment
                        identifier_name: str = identifier.attributes['name']
                        if identifier_name not in declared_identifiers:
                            # => this check works because of the pre-order tree traversal!
                            scope: Node = root  # scope=global !!!
                            declared_identifiers[identifier_name].append((identifier, scope))

                # all other nodes: skip...

        # declared_identifiers: DefaultDict[str, List[Tuple[Node, Node]]]
        #                                        now maps all declared Identifiers that are in scope at `self` to the
        #                                        scopes that they're available in (for each such scope,
        #                                        `self.is_inside_or_is(scope)`); grouped by Identifier name

        # Parameters:
        #     return_overshadowed_identifiers: whether to return Identifiers whose declaration *is* in scope but that
        #                                      have been overshadowed by other Identifiers with the same name
        #     return_reassigned_identifiers: whether to return Identifiers whose declaration *is* in scope but that
        #                                    have been reassigned since (this has nothing to do with the actual scope
        #                                    but is useful for handling data flows nonetheless)

        if return_overshadowed_identifiers:
            # Extract & return all the Identifier Nodes (0th tuple elements)
            #   from the DefaultDict[str, List[Tuple[Node, Node]]]:
            identifiers: List[Tuple[Node, Node]] =\
                [(identifier, scope)
                 for list_ in declared_identifiers.values()
                 for identifier, scope in list_]
        else:
            # Group all the identifiers in scope by their name (in fact, they already *are* grouped by their name)
            #   and for all identifiers in declared_identifiers with
            #   the same name, only keep the one from the innermost scope:
            identifiers: List[Tuple[Node, Node]] =\
                [min([(id_, scope) for id_, scope in list_], key=lambda id_scope: id_scope[1].get_height())
                 for identifier_name, list_ in declared_identifiers.items()]

        if not return_reassigned_identifiers:
            # For each identifier in scope, remove all those that have been in the LHS of an AssignmentExpression
            #   between their declaration and `self` (note that all identifiers in the list already *are* from their
            #   respective declarations):
            identifiers: List[Tuple[Node, Node]] =\
                [(identifier, scope)
                 for identifier, scope in identifiers
                 if not identifier.identifier_is_assigned_to_before(self, scope=scope)]

        return [identifier for identifier, scope in identifiers]

    # ADDED BY ME:
    def resolve_identifier(self) -> Optional[Self]:
        """
        Resolves this Identifier to its point of (explicit, or maybe implicit) declaration.
        Returns another Identifier Node again.

        Returns this very Node again, when this is already where the Identifier is being defined, e.g., for this 'x':
            let x = foo()

        Returns None on failure, for example for the following piece of code:
            foo(x)  // where is 'x' declared?! we don't know.

        Also works when there is overshadowing going on:
            let x = foo1();
            {
                let x = foo2();
                bar(x);          // resolving this 'x' will return the 'x' from the declaration one line above!
            }
        """
        assert self.name == "Identifier"
        identifiers_declared_in_scope_with_same_name: List[Self] =\
            [identifier_declared_in_scope for identifier_declared_in_scope
             in self.get_identifiers_declared_in_scope(return_overshadowed_identifiers=False,
                                                       return_reassigned_identifiers=True)
             if identifier_declared_in_scope.attributes['name'] == self.attributes['name']]
        if len(identifiers_declared_in_scope_with_same_name) == 0:
            return None
        elif len(identifiers_declared_in_scope_with_same_name) == 1:
            return identifiers_declared_in_scope_with_same_name[0]
        else:
            raise AssertionError(f"Node.get_identifiers_declared_in_scope() returned more than 1 Identifier with the "
                                 f"same name ('{self.attributes['name']}'), "
                                 f"even though return_overshadowed_identifiers=False! "
                                 f"An name may not be declared more than once within the same scope!")

    # ADDED BY ME:
    def identifier_is_in_scope_at(self,
                                  other_node: Self,
                                  allow_overshadowing: bool,
                                  allow_reassignment_after_decl: bool,
                                  allow_reassignment_after_self: bool) -> bool:
        r"""
        Is this Identifier in scope at the given `other_node`, i.e., if `other_node` were an Identifier having the same
        name as this Identifier, would it also refer to this Identifier?

        declaration ..... ..... ..... self ..... ..... ..... other_node
                           /|\                    /|\
                            |                      |
            reassignments allowed                 reassignments allowed
            if allow_reassignment_after_decl      if allow_reassignment_after_self

        *** Performance notes: ***
        Note that this function will take a little bit longer to run if
            allow_reassignment_after_decl != allow_reassignment_after_self,
        so try to avoid this if you can!
        This function will run the fastest if all three boolean parameters are set to True!

        Parameters:
            other_node: the place in the AST/PDG where we ask ourselves:
                        Is the Identifier represented by `self` in scope?
            allow_overshadowing: if True, this function will completely ignore the fact that identifiers may be
                                 overshadowed and will instead return whether this Identifier is *theoretically* in
                                 scope and not whether it is actually accessible at `other node`
            allow_reassignment_after_decl: if False, this function will return False even *if* this Identifier is in
                                           scope at `other_node` if there was any reassignment to this Identifier
                                           between its declaration and `other_node`; technically this doesn't have to
                                           do anything with scope but more with data flow.
            allow_reassignment_after_self: if False, this function will return False even *if* this Identifier is in
                                           scope at `other_node` if there was any reassignment to this Identifier
                                           between `self` and `other_node`; technically this doesn't have to
                                           do anything with scope but more with data flow.
        """
        assert self.name == "Identifier"

        declaration_identifier: Node = self.resolve_identifier()  # = the same as `self` but where it's declared
        declaration: Node = declaration_identifier.get_ancestor(
            ["FunctionDeclaration", "VariableDeclaration", "ClassDeclaration",
             "FunctionExpression", "ArrowFunctionExpression", "AssignmentExpression"]
        )
        declaration_scope: Node = declaration.declaration_get_scope()

        if not other_node.is_inside(declaration_scope):
            # No matter the values of allow_overshadowing, allow_reassignment_after_decl and
            #   allow_reassignment_after_self, the identifier isn't in scope @ other_node at all(!):
            return False

        if allow_overshadowing and allow_reassignment_after_decl and allow_reassignment_after_self:
            # If we do not care about possible overshadowing or reassignments at all, the question
            #     self.identifier_is_in_scope_at(other_node)?
            # ...has already been answered with:
            #    other_node.is_inside(declaration_scope) == True
            return True

        other_node_identifiers_declared_in_scope: List[Node] = other_node.get_identifiers_declared_in_scope(
            return_overshadowed_identifiers=allow_overshadowing,
            return_reassigned_identifiers=(allow_reassignment_after_decl or allow_reassignment_after_self)
        )
        # print(f"identifiers declared in scope @ other_node (line {other_node.get_line()}): "
        #       f"{other_node_identifiers_declared_in_scope}")

        # Only if we set return_reassigned_identifiers=True above, do we need to handle
        #   allow_reassignment_after_decl/allow_reassignment_after_self at all:
        if allow_reassignment_after_decl or allow_reassignment_after_self:
            if not allow_reassignment_after_decl:
                other_node_identifiers_declared_in_scope =\
                    [id_in_scope
                     for id_in_scope in other_node_identifiers_declared_in_scope
                     if not declaration_identifier.identifier_is_assigned_to_before(self, scope=declaration_scope)]
            if not allow_reassignment_after_self:
                other_node_identifiers_declared_in_scope = \
                    [id_in_scope
                     for id_in_scope in other_node_identifiers_declared_in_scope
                     if not self.identifier_is_assigned_to_before(other_node, scope=declaration_scope)]

        return declaration_identifier in other_node_identifiers_declared_in_scope

    # ADDED BY ME:
    def static_eval(self, allow_partial_eval: bool) -> str | int | float | bool | list | dict | None:  # todo: can I find other use cases for this function?!
        """
        Attempts to statically evaluate the value of this JavaScript expression.
        Returns the Python equivalent of the JavaScript value, which may be a string, an integer, a float, a boolean,
        a list, a dictionary or `None`.
        Note that `None` signifies that this JavaScript expression statically evaluates to JavaScript "null"!
        When static evaluation fails on the other hand, this method raises a (Python) StaticEvalException; so be sure
        to catch that!
        This method also raises a StaticEvalException when...
        (a) ...trying to statically evaluate a JavaScript regex literal!
        (b) ...trying to evaluate a "void ..." expression (which evaluates to undefined)!

        Parameters:
            allow_partial_eval: when this parameter is set to True, the returned Python object may be the result of an
                                incomplete evaluation, most notably it may be a dictionary where some keys, whose value
                                couldn't be statically evaluated, are mapped to `None`, or an array/list where some
                                items, whose value couldn't be statically evaluated, are mapped to `None`.

        Returns:
            the Python equivalent of this statically evaluated JavaScript expression
        """
        # From the Esprima docs:
        # type Expression = ThisExpression | Identifier | Literal |
        #                   ArrayExpression | ObjectExpression | FunctionExpression | ArrowFunctionExpression |
        #                   ClassExpression |
        #                   TaggedTemplateExpression | MemberExpression | Super | MetaProperty |
        #                   NewExpression | CallExpression | UpdateExpression | AwaitExpression |
        #                   UnaryExpression |
        #                   BinaryExpression | LogicalExpression | ConditionalExpression |
        #                   YieldExpression | AssignmentExpression | SequenceExpression;

        if self.name == "Literal":
            # interface Literal {
            #     value: boolean | number | string | RegExp | null;
            #     raw: string;
            #     regex?: { pattern: string, flags: string };
            # }
            if "regex" in self.attributes:
                raise StaticEvalException(f"static eval failed: cannot statically evaluate JavaScript RegEx literals!")
            return self.attributes['value']  # note that a JavaScript "null" will return `None` here!

        elif self.name == "ObjectExpression":
            # interface ObjectExpression {
            #     properties: Property[];
            # }
            result_dict = dict()
            for property_ in self.get("properties"):
                # interface Property {
                #     key: Expression; <--- Mozilla docs: "an identifier (either a name, a number, or a string literal)"
                #     computed: boolean;
                #     value: Expression | null;
                #     kind: 'get' | 'set' | 'init';
                #     method: false;
                #     shorthand: boolean;
                # }
                if property_.attributes['method']:
                    raise StaticEvalException(f"static eval failed: ObjectExpressions with methods not supported")
                key: Node = property_.get("key")[0]
                value: Node = property_.get("value")[0]
                try:
                    if key.name == "Identifier":  # e.g.: "{key: value}"
                        result_dict[key.attributes['name']] = None
                        result_dict[key.attributes['name']] = value.static_eval(allow_partial_eval=allow_partial_eval)
                    elif key.name == "Literal":  # e.g.: "{'key': value}" or "{1: value}"
                        result_dict[key.attributes['value']] = None
                        result_dict[key.attributes['value']] = value.static_eval(allow_partial_eval=allow_partial_eval)
                except StaticEvalException:
                    if allow_partial_eval:
                        continue
                    else:
                        raise
            return result_dict

        elif self.name == "ArrayExpression":
            # interface ArrayExpression {
            #     elements: ArrayExpressionElement[];
            # }
            # where:
            # type ArrayExpressionElement = Expression | SpreadElement;
            # and:
            # interface SpreadElement {
            #     argument: Expression;
            # }
            result: list = []
            for array_expr_el in self.get("elements"):
                if array_expr_el.name == "SpreadElement":
                    raise StaticEvalException(f"static eval failed: spread syntax is not supported")
                try:
                    result.append(array_expr_el.static_eval(allow_partial_eval=allow_partial_eval))
                except StaticEvalException:
                    if allow_partial_eval:
                        result.append(None)
                    else:
                        raise
            return result

        elif self.name == "BinaryExpression":
            # interface BinaryExpression {
            #     operator: 'instanceof' | 'in' | '+' | '-' | '*' | '/' | '%' | '**' |
            #               '|' | '^' | '&' | '==' | '!=' | '===' | '!==' |
            #               '<' | '>' | '<=' | '<<' | '>>' | '>>>';
            #     left: Expression;
            #     right: Expression;
            # }
            left: Node = self.get("left")[0]
            right: Node = self.get("right")[0]
            match self.attributes['operator']:
                case 'instanceof':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/instanceof:
                    # "The instanceof operator tests to see if the prototype property of a constructor appears
                    #  anywhere in the prototype chain of an object. The return value is a boolean value. Its
                    #  behavior can be customized with Symbol.hasInstance."
                    # Examples:
                    #     * console.log(auto instanceof Car); // Expected output: true
                    #     * console.log(auto instanceof Object); // Expected output: true
                    raise StaticEvalException(f"static eval failed: cannot handle 'instanceof' statically")
                case 'in':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/in:
                    # "The in operator returns true if the specified property is in the specified object or its
                    #  prototype chain. The in operator cannot be used to search for values in other collections.
                    #  To test if a certain value exists in an array, use Array.prototype.includes().
                    #  For sets, use Set.prototype.has()."
                    # Example:
                    #     const car = { make: 'Honda', model: 'Accord', year: 1998 };
                    #     console.log('make' in car); // Expected output: true
                    right_evaluated = right.static_eval(allow_partial_eval=allow_partial_eval)
                    if isinstance(right_evaluated, dict):
                        # >> 'make' in {'make':1}
                        # true
                        # >> 1 in {1:2}
                        # true
                        left_evaluated = left.static_eval(allow_partial_eval=allow_partial_eval)
                        return left_evaluated in right_evaluated
                    elif isinstance(right_evaluated, list):
                        # >> 'make' in []
                        # false
                        # >> 'make' in ['make']
                        # false
                        return False
                    else:
                        # >> 'make' in 1
                        # Uncaught TypeError: right-hand side of 'in' should be an object, got number
                        # >> 'make' in null
                        # Uncaught TypeError: right-hand side of 'in' should be an object, got null
                        raise StaticEvalException(f"static eval failed: right-hand side of 'in' should be an object")
                case '+':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Addition:
                    # "The addition (+) operator produces the sum of numeric operands or string concatenation.":
                    #
                    #                   | JavaScript            | Python
                    # ------------------|-----------------------|-----------
                    # "foo" + 42        | "foo42"               | TypeError: can only concatenate str (not "int") to str
                    # 42 + "foo"        | "42foo"               | TypeError: unsupported operand type(s) for +: 'int' and 'str'
                    # "foo" + 3.14      | "foo3.14"             | TypeError: can only concatenate str (not "float") to str
                    # 3.14 + "foo"      | "3.14foo"             | TypeError: unsupported operand type(s) for +: 'float' and 'str'
                    # "foo" + false     | "foofalse"            | TypeError: can only concatenate str (not "bool") to str
                    # "foo" + true      | "footrue"             | TypeError: can only concatenate str (not "bool") to str
                    # false + "foo"     | "falsefoo"            | TypeError: unsupported operand type(s) for +: 'bool' and 'str'
                    # true + "foo"      | "truefoo"             | TypeError: unsupported operand type(s) for +: 'bool' and 'str'
                    # 42 + false        | 42                    | 42
                    # 42 + true         | 43                    | 43
                    # false + 42        | 42                    | 42
                    # true + 42         | 43                    | 43
                    # false + false     | 0                     | 0
                    # false + true      | 1                     | 1
                    # true + false      | 1                     | 1
                    # true + true       | 2                     | 2
                    # "foo" + [1,2,3]   | "foo1,2,3"            | TypeError: can only concatenate str (not "list") to str
                    # [1,2,3] + "foo"   | "1,2,3foo"            | TypeError: can only concatenate list (not "str") to list
                    # "foo" + {}        | "foo[object Object]"  | TypeError: can only concatenate str (not "dict") to str
                    # "foo" + {"a":1}   | "foo[object Object]"  | TypeError: can only concatenate str (not "dict") to str
                    # {} + "foo"        | NaN                   | TypeError: unsupported operand type(s) for +: 'dict' and 'str'
                    # ({} + "foo")      | "[object Object]foo"  | TypeError: unsupported operand type(s) for +: 'dict' and 'str'
                    # x={} + "foo"      | "[object Object]foo"  | TypeError: unsupported operand type(s) for +: 'dict' and 'str'
                    # ({"a":1} + "foo") | "[object Object]foo"  | TypeError: unsupported operand type(s) for +: 'dict' and 'str'
                    # 42 + [1,2,3]      | "421,2,3"             | TypeError: unsupported operand type(s) for +: 'int' and 'list'
                    # [1,2,3] + 42      | "1,2,342"             | TypeError: can only concatenate list (not "int") to list
                    # 42 + [1]          | "421"                 | TypeError: unsupported operand type(s) for +: 'int' and 'list'
                    # [1]+42            | "142"                 | TypeError: can only concatenate list (not "int") to list
                    # 42 + []           | "42"                  | TypeError: unsupported operand type(s) for +: 'int' and 'list'
                    # [] + 42           | "42"                  | TypeError: can only concatenate list (not "int") to list
                    # [1,2]+[3,4]       | "1,23,4"              | [1, 2, 3, 4]
                    # [1,2]+{}          | "1,2[object Object]"  | TypeError: can only concatenate list (not "dict") to list
                    # [1,2]+{"a":1}     | "1,2[object Object]"  | TypeError: can only concatenate list (not "dict") to list
                    # ({}+[1,2])        | "[object Object]1,2"  | TypeError: unsupported operand type(s) for +: 'dict' and 'list'
                    # ({"a":1}+[1,2])   | "[object Object]1,2"  | TypeError: unsupported operand type(s) for +: 'dict' and 'list'
                    # null + null       | 0                     | TypeError: unsupported operand type(s) for +: 'NoneType' and 'NoneType'
                    # "foo" + null      | "foonull"             | TypeError: can only concatenate str (not "NoneType") to str
                    # 42 + null         | 42                    | TypeError: unsupported operand type(s) for +: 'int' and 'NoneType'
                    # false + null      | 0                     | TypeError: unsupported operand type(s) for +: 'bool' and 'NoneType'
                    # true + null       | 1                     | TypeError: unsupported operand type(s) for +: 'bool' and 'NoneType'
                    # 3.14 + null       | 3.14                  | TypeError: unsupported operand type(s) for +: 'float' and 'NoneType'
                    # [1,2] + null      | "1,2null"             | TypeError: can only concatenate list (not "NoneType") to list
                    # ({}+null)         | "[object Object]null" | TypeError: unsupported operand type(s) for +: 'dict' and 'NoneType'
                    # ({"a":1}+null)    | "[object Object]null" | TypeError: unsupported operand type(s) for +: 'dict' and 'NoneType'
                    # null + "foo"      | "nullfoo"             | TypeError: unsupported operand type(s) for +: 'NoneType' and 'str'
                    left_evaluated = left.static_eval(allow_partial_eval)
                    print(f"left_evaluated = {left_evaluated} (type: {type(left_evaluated)})") # todo: remove
                    right_evaluated = right.static_eval(allow_partial_eval)
                    print(f"right_evaluated = {right_evaluated} (type: {type(right_evaluated)})")  # todo: remove
                    if (
                            isinstance(left_evaluated, (int, float, bool, type(None)))
                        and isinstance(right_evaluated, (int, float, bool, type(None)))
                    ):
                        # Sum of numeric operands (treating null as 0):
                        return ((left_evaluated if left_evaluated is not None else 0)
                                + (right_evaluated if right_evaluated is not None else 0))
                    else:
                        # String concatenation:
                        left_as_str: str
                        if isinstance(left_evaluated, bool):
                            # => has to happen first because isinstance(True, int) returns True!!!
                            left_as_str = "true" if left_evaluated else "false"
                        elif isinstance(left_evaluated, (str, int, float)):
                            left_as_str = str(left_evaluated)
                        elif isinstance(left_evaluated, list):
                            left_as_str = ",".join([str(item) for item in left_evaluated])
                            # => todo: handle bools correctly
                        elif isinstance(left_evaluated, dict):
                            left_as_str = "[object Object]"
                        elif isinstance(left_evaluated, type(None)):
                            left_as_str = "null"
                        else:
                            raise StaticEvalException(f"static eval failed: "
                                                      f"LHS evaluated to unknown type: {left_evaluated}")

                        right_as_str: str
                        if isinstance(right_evaluated, bool):
                            # => has to happen first because isinstance(True, int) returns True!!!
                            right_as_str = "true" if right_evaluated else "false"
                        elif isinstance(right_evaluated, (str, int, float)):
                            right_as_str = str(right_evaluated)
                        elif isinstance(right_evaluated, list):
                            right_as_str = ",".join([str(item) for item in right_evaluated])
                            # => todo: handle bools correctly
                        elif isinstance(right_evaluated, dict):
                            right_as_str = "[object Object]"
                        elif isinstance(right_evaluated, type(None)):
                            right_as_str = "null"
                        else:
                            raise StaticEvalException(f"static eval failed: "
                                                      f"RHS evaluated to unknown type: {right_evaluated}")

                        return left_as_str + right_as_str
                case '-':
                    return left.static_eval(allow_partial_eval) - right.static_eval(allow_partial_eval)
                case '*':
                    return left.static_eval(allow_partial_eval) * right.static_eval(allow_partial_eval)
                case '/':
                    left_evaluated = left.static_eval(allow_partial_eval)
                    right_evaluated = right.static_eval(allow_partial_eval)
                    try:
                        return left_evaluated / right_evaluated
                    except ZeroDivisionError:
                        # In JavaScript:
                        # >> 1/0
                        # Infinity
                        # >> -1/0
                        # -Infinity
                        # >> 0/0
                        # NaN
                        if left_evaluated < 0:
                            return float('-inf')
                        elif left_evaluated == 0:
                            return float('nan')
                        elif left_evaluated > 0:
                            return float('inf')
                case '%':
                    return left.static_eval(allow_partial_eval) % right.static_eval(allow_partial_eval)
                case '**':  # Exponentiation (**)
                    return left.static_eval(allow_partial_eval) ** right.static_eval(allow_partial_eval)
                case '|':
                    return left.static_eval(allow_partial_eval) | right.static_eval(allow_partial_eval)
                case '^':
                    return left.static_eval(allow_partial_eval) ^ right.static_eval(allow_partial_eval)
                case '&':
                    return left.static_eval(allow_partial_eval) & right.static_eval(allow_partial_eval)
                case '==':
                    return left.static_eval(allow_partial_eval) == right.static_eval(allow_partial_eval)
                case '!=':
                    return left.static_eval(allow_partial_eval) != right.static_eval(allow_partial_eval)
                case '===':
                    return left.static_eval(allow_partial_eval) == right.static_eval(allow_partial_eval)
                case '!==':
                    return left.static_eval(allow_partial_eval) != right.static_eval(allow_partial_eval)
                case '<':
                    return left.static_eval(allow_partial_eval) < right.static_eval(allow_partial_eval)
                case '>':
                    return left.static_eval(allow_partial_eval) > right.static_eval(allow_partial_eval)
                case '<=':  # todo: handle cases like '"" <= 1' that raise a TypeError in Python but work in JS !!!
                    return left.static_eval(allow_partial_eval) <= right.static_eval(allow_partial_eval)
                case '>=':  # (missing in Esprima docs)
                    return left.static_eval(allow_partial_eval) >= right.static_eval(allow_partial_eval)
                case '<<':
                    return left.static_eval(allow_partial_eval) << right.static_eval(allow_partial_eval)
                case '>>':
                    return left.static_eval(allow_partial_eval) >> right.static_eval(allow_partial_eval)
                case '>>>':  # Unsigned right shift (>>>)
                    # https://stackoverflow.com/questions/11418112/python-unsigned-right-shift:
                    # "Integers in Java have a fixed number of bits, but those in Python don't, so an unsigned right
                    #   shift would be meaningless in Python."
                    # Note that, in JavaScript, all numbers are in double-precision 64-bit binary format IEEE 754.
                    #   => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Number
                    raise StaticEvalException(f"static eval failed: >>> operator not supported")  # todo: simulate
                case op:
                    raise StaticEvalException(f"static eval failed: unsupported operator in BinaryExpression: {op}")

        elif self.name == "LogicalExpression":
            # interface LogicalExpression {
            #     operator: '||' | '&&';
            #     left: Expression;
            #     right: Expression;
            # }
            left: Node = self.get("left")[0]
            right: Node = self.get("right")[0]
            match self.attributes['operator']:
                case '||':
                    return left.static_eval(allow_partial_eval) or right.static_eval(allow_partial_eval)
                case '&&':
                    return left.static_eval(allow_partial_eval) and right.static_eval(allow_partial_eval)
                case op:
                    raise StaticEvalException(f"static eval failed: unsupported operator in LogicalExpression: {op}")

        elif self.name == "ConditionalExpression":
            # interface ConditionalExpression {
            #     test: Expression;
            #     consequent: Expression;
            #     alternate: Expression;
            # }
            # => JavaScript: test ? consequent : alternate;
            # => Python:     consequent if test else alternate
            test: Node = self.get("test")[0]
            consequent: Node = self.get("consequent")[0]
            alternate: Node = self.get("alternate")[0]
            # There are 2 cases that we can handle statically:
            #   (1) first `test` can be evaluated statically and then either `consequent` or `alternate`, depending on
            #       the result of statically evaluating `test`
            #   (2) `test` cannot be evaluated statically but both `consequent` and `alternate` can and both them they
            #       evaluate to the same value
            try:
                # (1):
                test_evaluated = test.static_eval(allow_partial_eval=allow_partial_eval)
            except StaticEvalException:
                # (2):
                consequent_evaluated = consequent.static_eval(allow_partial_eval=allow_partial_eval)
                alternate_evaluated = alternate.static_eval(allow_partial_eval=allow_partial_eval)
                if consequent_evaluated == alternate_evaluated:  # Note: 0 == False and 1 == True in Python.
                    return consequent_evaluated
                else:  # neither (1) nor (2) worked:
                    raise StaticEvalException(f"static eval failed: static evaluation of ConditionalExpression failed: "
                                              f"both consequent and alternate could be evaluated but they differ and "
                                              f"test couldn't be evaluated")

            # (1):
            if test_evaluated:
                return consequent.static_eval(allow_partial_eval=allow_partial_eval)
            else:
                return alternate.static_eval(allow_partial_eval=allow_partial_eval)
            # Note: this lazy evaluation allows statically evaluating ConditionalExpressions even if one of
            #       "consequent" / "alternate" cannot be statically evaluated!

        elif self.name == "UnaryExpression":
            # interface UnaryExpression {
            #     operator: '+' | '-' | '~' | '!' | 'delete' | 'void' | 'typeof';
            #     argument: Expression;
            #     prefix: true;
            # }
            argument: Node = self.get("argument")[0]
            argument_evaluated = argument.static_eval(allow_partial_eval=allow_partial_eval)
            match self.attributes['operator']:
                case '+':
                    # PLUS:
                    #           | JavaScript |             | Python
                    # ----------|------------|-------------|--------
                    #  +0       |            | +0          |
                    #  +1       |            | +1          |
                    #  +2       |            | +2          |
                    #  +'x'     | NaN        | +'x'        | TypeError: bad operand type for unary +: 'str'
                    #  +''      | 0          | +''         | TypeError: bad operand type for unary +: 'str'
                    #  +0.0     |            | +0.0        |
                    #  +0.1     |            | +0.1        |
                    #  +{}      | NaN        | +{}         | TypeError: bad operand type for unary +: 'dict'
                    #  +{"a":1} | NaN        | +{"a":1}    | TypeError: bad operand type for unary +: 'dict'
                    #  +[]      | 0          | +[]         | TypeError: bad operand type for unary +: 'list'
                    #  +[42]    | 42         | +[42]       | TypeError: bad operand type for unary +: 'list'
                    #  +['']    | 0          | +['']       | TypeError: bad operand type for unary +: 'list'
                    #  +['x']   | NaN        | +['x']      | TypeError: bad operand type for unary +: 'list'
                    #  +false   | 0          | +False      | 0
                    #  +true    | 1          | +True       | 1
                    if argument_evaluated == "":
                        return 0  # Yes, "+''" evaluates to "0" in JavaScript...
                    elif isinstance(argument_evaluated, str) or isinstance(argument_evaluated, dict):
                        return float('nan')
                    elif isinstance(argument_evaluated, list):
                        if len(argument_evaluated) == 0:
                            return 0  # "+[]" evaluates to "0" in JavaScript...
                        elif argument_evaluated == [""]:
                            return 0  # "+['']" evaluates to "0" in JavaScript...
                        elif len(argument_evaluated) == 1 and isinstance(argument_evaluated[0], (int, float)):
                            return +argument_evaluated[0]  # "+[42]" evaluates to "42" in JavaScript...
                        else:
                            return float('nan')
                    else:
                        return +argument_evaluated
                case '-':
                    # MINUS:
                    #           | JavaScript |             | Python
                    # ----------|------------|-------------|--------
                    #  -0       |            | -0          |
                    #  -1       |            | -1          |
                    #  -2       |            | -2          |
                    #  -'x'     | NaN        | -'x'        | TypeError: bad operand type for unary -: 'str'
                    #  -''      | 0          | -''         | TypeError: bad operand type for unary -: 'str'
                    #  -0.0     |            | -0.0        |
                    #  -0.1     |            | -0.1        |
                    #  -{}      | NaN        | -{}         | TypeError: bad operand type for unary -: 'dict'
                    #  -{"a":1} | NaN        | -{"a":1}    | TypeError: bad operand type for unary -: 'dict'
                    #  -[]      | -0         | -[]         | TypeError: bad operand type for unary -: 'list'
                    #  -[42]    | -42        | -[42]       | TypeError: bad operand type for unary -: 'list'
                    #  -['']    | -0         | -['']       | TypeError: bad operand type for unary -: 'list'
                    #  -['x']   | NaN        | -['x']      | TypeError: bad operand type for unary -: 'list'
                    #  -false   | -0         | -False      | 0
                    #  -true    | -1         | -True       | -1
                    if argument_evaluated == "":
                        return 0  # Yes, "-''" evaluates to "0" in JavaScript... ("-0" actually...)
                    elif isinstance(argument_evaluated, str) or isinstance(argument_evaluated, dict):
                        return float('nan')
                    elif isinstance(argument_evaluated, list):
                        if len(argument_evaluated) == 0:
                            return 0  # "-[]" evaluates to "-0" in JavaScript...
                        elif argument_evaluated == [""]:
                            return 0  # "-['']" evaluates to "-0" in JavaScript...
                        elif len(argument_evaluated) == 1 and isinstance(argument_evaluated[0], (int, float)):
                            return -argument_evaluated[0]  # "-[42]" evaluates to "-42" in JavaScript...
                        else:
                            return float('nan')
                    else:
                        return -argument_evaluated
                case '~':  # tilde = bitwise flip, both in JavaScript and in Python!
                    # TILDE:
                    #           | JavaScript |             | Python
                    # ----------|------------|-------------|--------
                    #  ~0       | -1         | ~0          | -1
                    #  ~1       | -2         | ~1          | -2
                    #  ~2       | -3         | ~2          | -3
                    #  ~'x'     | -1         | ~'x'        | TypeError: bad operand type for unary ~: 'str'
                    #  ~'foo'   | -1         | ~'foo'      | TypeError: bad operand type for unary ~: 'str'
                    #  ~''      | -1         | ~''         | TypeError: bad operand type for unary ~: 'str'
                    #  ~0.0     | -1         | ~0.0        | TypeError: bad operand type for unary ~: 'float'
                    #  ~0.1     | -1         | ~0.1        | TypeError: bad operand type for unary ~: 'float'
                    #  ~1.1     | -2         | ~1.1        | TypeError: bad operand type for unary ~: 'float'
                    #  ~1.9     | -2         | ~1.9        | TypeError: bad operand type for unary ~: 'float'
                    #  ~2.0     | -3         | ~2.0        | TypeError: bad operand type for unary ~: 'float'
                    #  ~(-42.0) | 41         | ~(-42.0)    | TypeError: bad operand type for unary ~: 'float'
                    #  ~(-42.5) | 41         | ~(-42.5)    | TypeError: bad operand type for unary ~: 'float'
                    #  ~{}      | -1         | ~{}         | TypeError: bad operand type for unary ~: 'dict'
                    #  ~{"a":1} | -1         | ~{"a":1}    | TypeError: bad operand type for unary ~: 'dict'
                    #  ~[]      | -1         | ~[]         | TypeError: bad operand type for unary ~: 'list'
                    #  ~[42]    | -43        | ~[42]       | TypeError: bad operand type for unary ~: 'list'
                    #  ~['']    | -1         | ~['']       | TypeError: bad operand type for unary ~: 'list'
                    #  ~['x']   | -1         | ~['x']      | TypeError: bad operand type for unary ~: 'list'
                    #  ~false   | -1         | ~False      | -1
                    #  ~true    | -2         | ~True       | -2
                    if isinstance(argument_evaluated, (int, bool)):
                        return ~argument_evaluated
                    elif isinstance(argument_evaluated, float):
                        return ~math.floor(argument_evaluated)  # todo: fix, doesn't give correct result for ~(-42.5)
                    else:
                        return -1
                case '!':
                    # NOT:
                    #           | JavaScript |             | Python
                    # ----------|------------|-------------|--------
                    #  !0       | true       | not 0       | True
                    #  !1       | false      | not 1       | False
                    #  !2       | false      | not 2       | False
                    #  !'x'     | false      | not 'x'     | False
                    #  !''      | true       | not ''      | True
                    #  !0.0     | true       | not 0.0     | True
                    #  !0.1     | false      | not 0.1     | False
                    #  !{}      | false      | not {}      | True     <---- difference #1
                    #  !{"a":1} | false      | not {"a":1} | False
                    #  ![]      | false      | not []      | True     <---- difference #2
                    #  ![42]    | false      | not [42]    | False
                    #  !['']    | false      | not ['']    | False
                    #  !['x']   | false      | not ['x']   | False
                    #  !false   | true       | not False   | True
                    #  !true    | false      | not True    | False
                    if argument_evaluated == {} or argument_evaluated == []:
                        return False  # "not {}" would be True in Python but "!{}" is false in JavaScript!!!
                    else:
                        return not argument_evaluated
                case 'delete':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/delete:
                    # "The delete operator removes a property from an object. If the property's value is an object
                    #  and there are no more references to the object, the object held by that property is
                    #  eventually released automatically."
                    # Return value:
                    # "true for all cases except when the property is an own non-configurable property, in which case
                    #  false is returned in non-strict mode."
                    return True
                case 'void':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/void:
                    # "The void operator evaluates the given expression and then returns undefined."
                    raise StaticEvalException(f"static eval failed: expression evaluates to undefined.")
                case 'typeof':
                    # https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/typeof:
                    # "The typeof operator returns a string indicating the type of the operand's value."
                    # Examples:
                    #     typeof 42                 == "number"
                    #     typeof 3.14               == "number"
                    #     typeof ""                 == "string"
                    #     typeof 'blubber'          == "string"
                    #     typeof true               == "boolean"
                    #     typeof false              == "boolean"
                    #     typeof undeclaredVariable == "undefined"
                    #     typeof {}                 == "object"
                    #     typeof {1:2}              == "object"
                    #     typeof {"a":2}            == "object"
                    #     typeof []                 == "object"
                    #     typeof [1,2,3]            == "object"
                    #     typeof null               == "object"
                    #     typeof (0/0)              == "number"
                    if isinstance(argument_evaluated, (int, float)):
                        return "number"
                    elif isinstance(argument_evaluated, str):
                        return "string"
                    elif isinstance(argument_evaluated, bool):
                        return "boolean"
                    elif isinstance(argument_evaluated, (list, dict)):
                        return "object"
                    elif argument_evaluated is None:  # JavaScript "null" becomes "None" in Python
                        return "object"
                    else:
                        raise StaticEvalException(f"static eval failed: static_eval() returned something "
                                                  f"of an unexpected type: {argument_evaluated}")
                case op:
                    raise StaticEvalException(f"static eval failed: unsupported operator in UnaryExpression: {op}")

        elif self.name == "Identifier":
            # Check if the Identifier refers to a constant in scope:
            identifier_at_declaration: Optional[Node] = self.resolve_identifier()
            # print(f"static_eval(): resolved Identifier '{self.attributes['name']}' in line {self.get_line()} to "
            #       f"'{identifier_at_declaration.attributes['name'] if identifier_at_declaration is not None else ''}'"
            #       f" in line {identifier_at_declaration.get_line() if identifier_at_declaration is not None else ''}")
            if identifier_at_declaration is None:
                raise StaticEvalException(f"static eval failed: "
                                          f"couldn't resolve identifier '{self.attributes['name']}' "
                                          f"in line {self.get_line()}")
            else:
                # interface VariableDeclaration {
                #     declarations: VariableDeclarator[];
                #     kind: 'var' | 'const' | 'let';
                # }
                # with:
                # interface VariableDeclarator {
                #     id: Identifier | BindingPattern; <----- is `identifier_at_declaration` this?!
                #     init: Expression | null;
                # }
                variable_declarator: Node = identifier_at_declaration.parent
                if (variable_declarator is None or variable_declarator.name != "VariableDeclarator"
                        or [identifier_at_declaration] != variable_declarator.get("id")):
                    raise StaticEvalException(f"static eval failed: resolved identifier "
                                              f"'{identifier_at_declaration.attributes['name']}' "
                                              f"(line {identifier_at_declaration.get_line()}) "
                                              f"isn't the 'id' of a VariableDeclarator")
                else:
                    var_declaration: Node = variable_declarator.parent
                    assert var_declaration is not None and var_declaration.name == "VariableDeclaration"
                    if var_declaration.attributes['kind'] == 'const':
                        init_expr: List[Node] = variable_declarator.get("init")
                        if len(init_expr) == 0:
                            raise StaticEvalException(f"static eval failed: JavaScript SyntaxError: "
                                                      f"missing = in const declaration in line "
                                                      f"{variable_declarator.get_line()}")
                        else:
                            return init_expr[0].static_eval(allow_partial_eval=allow_partial_eval)
                    else:
                        raise StaticEvalException(f"static eval failed: identifier '{self.attributes['name']}' "
                                                  f"in line {self.get_line()} "
                                                  f"doesn't refer to a constant")

        elif self.name == "AssignmentExpression":
            # interface AssignmentExpression {
            #     operator: '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
            #               '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|=';
            #     left: Expression;
            #     right: Expression;
            # }
            # From the Mozilla JavaScript docs:
            #     "The assignment expression itself has a value, which is the assigned value."
            #     Examples:
            #     console.log((x = y + 1));
            #     console.log((x = x * y));
            # => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/Assignment
            right: Node = self.get("right")[0]
            return right.static_eval(allow_partial_eval=allow_partial_eval)

        elif self.name == "MemberExpression":
            # interface MemberExpression {
            #      computed: boolean;     <----- True for "[1,2,3][1]"; False for "[1,2,3].one"
            #      object: Expression;
            #      property: Expression;
            # }
            # (1) "[1,2,3][1]"
            #     -> computed: True
            #     -> property: Literal (int)
            # (2) "[1,2,3].length"
            #     -> computed: False
            #     -> property: Identifier
            # (3) "[1,2,3]['length']"
            #     -> computed: True
            #     -> property: Literal (string)
            object_: Node = self.get("object")[0]
            property_: Node = self.get("property")[0]
            computed: bool = self.attributes['computed']
            object_evaluated = object_.static_eval(allow_partial_eval=allow_partial_eval)
            if isinstance(object_evaluated, list):
                if computed:
                    property_evaluated = property_.static_eval(allow_partial_eval=allow_partial_eval)
                    if (isinstance(property_evaluated, int)
                            or (isinstance(property_evaluated, float)
                                and property_evaluated == int(property_evaluated))):
                        return object_evaluated[int(property_evaluated)]  # "[1,2,3][1]" or "[1,2,3][1.0]"
                    elif isinstance(property_evaluated, str) and property_evaluated == "length":
                        return len(object_evaluated)  # "[1,2,3]['length']"
                    else:
                        raise StaticEvalException(f"static eval failed: unsupported type of MemberExpression; "
                                                  f"only supporting RHS=integer or RHS='length'")
                else:
                    if property_.name == "Identifier" and property_.attributes['name'] == "length":
                        return len(object_evaluated)  # "[1,2,3].length"
                    else:
                        raise StaticEvalException(f"static eval failed: unsupported type of MemberExpression; "
                                                  f"only supporting <array>.length non-computed MemberExpressions")
            else:
                raise StaticEvalException(f"static eval failed: unsupported type of MemberExpression; "
                                          f"only supporting LHS=array")

        else:
            raise StaticEvalException(f"static eval failed: unsupported type of Expression: {self.name}")

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
        # DoubleX, however, hoists functions inside of functions directly inside the Function Declaration,
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
        params = [param for param in self.children if param.name not in ["FunctionDeclaration", "BlockStatement"]]
        return params[1:]  # ignore 1st Identifier as that's not a parameter but rather the name of the function!

    # ADDED BY ME:
    def function_declaration_get_nth_param(self, n: int) -> Self:
        assert self.name == "FunctionDeclaration"
        return self.function_declaration_get_params()[n]

    # ADDED BY ME:
    def function_declaration_get_nth_param_or_none(self, n: int) -> Optional[Self]:
        assert self.name == "FunctionDeclaration"
        params = self.function_declaration_get_params()
        if n < len(params):
            return params[n]
        else:
            return None

    # ADDED BY ME:
    def is_function_declaration_param(self) -> bool:
        """
        Returns True if and only if
        there exists a FunctionDeclaration `f` such that `self in f.function_declaration_get_params()`.
        """
        func_decl_parent: Optional[Node] = self.get_parent_or_none(["FunctionDeclaration"])
        if func_decl_parent is None:
            return False
        return self in func_decl_parent.function_declaration_get_params()

    # ADDED BY ME:
    def is_inside_any_function_declaration_param(self) -> bool:
        """
        Returns True if and only if there is a Node `p` such that
        `self.is_inside(p)` and
        there exists a FunctionDeclaration `f` such that `p in f.function_declaration_get_params()`.
        """
        func_decl_ancestor: Optional[Node] = self.get_ancestor_or_none(["FunctionDeclaration"])
        if func_decl_ancestor is None:
            return False
        return any(self.is_inside(param) for param in func_decl_ancestor.function_declaration_get_params())
        # Note how this assumes that parameters of FunctionDeclarations may not contain FunctionDeclarations themselves.

    # ADDED BY ME:
    def is_or_is_inside_any_function_declaration_param(self) -> bool:
        """
        Returns True if and only if there is a Node `p` such that
        `self.is_inside(p)` or `self == p` and
        there exists a FunctionDeclaration `f` such that `p in f.function_declaration_get_params()`.
        """
        func_decl_ancestor: Optional[Node] = self.get_ancestor_or_none(["FunctionDeclaration"])
        if func_decl_ancestor is None:
            return False
        return any(self.is_inside(param) or self == param for param in func_decl_ancestor.function_declaration_get_params())
        # Note how this assumes that parameters of FunctionDeclarations may not contain FunctionDeclarations themselves.

    # ADDED BY ME:
    def function_declaration_get_function_identifier(self) -> Self:
        # interface FunctionDeclaration {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        #     generator: boolean;
        #     async: boolean;
        #     expression: false;
        # }
        assert self.name == "FunctionDeclaration"
        params = [param for param in self.children if param.name not in ["FunctionDeclaration", "BlockStatement"]]
        assert params[0].name == "Identifier"
        return params[0]  # 1st non-declaration, non-block child = Identifier = the name of the function!

    # ADDED BY ME:
    def function_declaration_get_body(self) -> Self:
        # interface FunctionDeclaration {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        # where:
        # type FunctionParameter = AssignmentPattern | Identifier | BindingPattern;
        assert self.name == "FunctionDeclaration"
        return self.get_child("BlockStatement")

    # ADDED BY ME:
    def class_declaration_get_class_identifier(self) -> Self:
        # interface ClassDeclaration {
        #     id: Identifier | null;
        #     superClass: Identifier | null;
        #     body: ClassBody;
        # }
        assert self.name == "ClassDeclaration"
        assert self.children[0].name == "Identifier"
        return self.children[0]

    # ADDED BY ME:
    def function_declaration_get_name(self) -> str:
        return self.function_declaration_get_function_identifier().attributes['name']

    # ADDED BY ME:
    def function_declaration_is_called_anywhere(self) -> bool:
        assert self.name == "FunctionDeclaration"
        name: str = self.function_declaration_get_name()
        scope: Node = self.function_declaration_get_scope()
        for call_expr in scope.get_all_as_iter("CallExpression"):
            if call_expr.call_expression_get_full_function_name() == name:
                return True
        return False

    # ADDED BY ME:
    def class_declaration_get_name(self) -> str:
        return self.class_declaration_get_class_identifier().attributes['name']

    # ADDED BY ME:
    def arrow_function_expression_get_params(self) -> List[Self]:
        """
        Returns the parameters of this (Arrow)FunctionExpression.
        Note that this is non-trivial because FunctionExpression may also have a name!!!
        """

        # From the Esprima docs:
        # interface ArrowFunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement | Expression;
        # }
        # interface FunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        #
        # An example where id is null:
        #   !function(x,y){}(a,b)
        #
        # An example where id is not null:
        #   !function foo(x,y){}(a,b)

        assert self.name in ["FunctionExpression", "ArrowFunctionExpression"]
        # return self.children[:-1] will only work as long as id is null (!!!)
        # *** WARNING *** WARNING *** WARNING *** WARNING *** WARNING ***
        # While `self.fun_params` *is* set by DoubleX, counter-intuitively, it is only set during PDG generation.
        # The information however is obviously available as soon as the AST is available; the latter will work even
        #   when only working with the AST instead of the PDG (and hence also when I generate my *own* PDG):
        return self.get("params")

    # ADDED BY ME:
    def arrow_function_expression_get_nth_param(self, n: int) -> Self:
        assert self.name in ["FunctionExpression", "ArrowFunctionExpression"]
        params: List[Node] = self.arrow_function_expression_get_params()
        return params[n]

    # ADDED BY ME:
    def arrow_function_expression_get_nth_param_or_none(self, n: int) -> Optional[Self]:
        assert self.name in ["FunctionExpression", "ArrowFunctionExpression"]
        params: List[Node] = self.arrow_function_expression_get_params()
        if n < len(params):
            return params[n]
        else:
            return None

    # ADDED BY ME:
    def arrow_function_expression_get_body(self) -> Self:
        assert self.name in ["FunctionExpression", "ArrowFunctionExpression"]
        # From the Esprima docs:
        # interface ArrowFunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement | Expression;
        # }
        # interface FunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        return self.children[-1]

    # ADDED BY ME:
    def function_expression_get_id_node(self) -> Optional[Self]:
        assert self.name == "FunctionExpression"
        # Note that ArrowFunctionExpressions cannot have a name!
        # interface FunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        id_ = self.get("id")
        if len(id_) == 0:
            return None
        elif len(id_) == 1:
            assert id_[0].name == "Identifier"
            return id_[0]
        else:
            raise AssertionError(f"{self.name} in line {self.get_line()} has more than one 'id', this cannot be!")

    # ADDED BY ME:
    def function_expression_get_name(self) -> Optional[str]:
        id_node: Node = self.function_expression_get_id_node()
        if id_node is None:
            return None
        else:
            return id_node.attributes['name']

    # ADDED BY ME:
    def function_expression_calls_itself_recursively(self) -> bool:
        assert self.name == "FunctionExpression"

        # There are two ways a FunctionExpression may call itself recursively:
        #   (a) using a "Named function expression" and then simply referring to itself, just like a regular function
        #       => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/function
        #   (b) deprecated: using "arguments.callee"
        #       => https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/arguments/callee
        #       => Note that "arguments.callee" may be used, even when the FunctionExpression is named!
        #
        # Note that ArrowFunctionExpressions cannot call themselves recursively!
        #   (not even using "arguments.callee", cf.
        #    https://stackoverflow.com/questions/44676474/access-to-callee-in-arrow-functions)

        # Examples from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/arguments/callee:
        #
        # (a):
        #     [1, 2, 3, 4, 5].map(function factorial(n) {
        #         return n <= 1 ? 1 : factorial(n - 1) * n;
        #     });
        #
        # (b):
        #     [1, 2, 3, 4, 5].map(function (n) {
        #         return n <= 1 ? 1 : arguments.callee(n - 1) * n;
        #     });

        name: str = self.function_expression_get_name()
        body: Node = self.arrow_function_expression_get_body()

        for call_expr in body.get_all_as_iter("CallExpression"):
            if call_expr.call_expression_get_full_function_name() in [name, "arguments.callee"]:
                return True

        return False

    # ADDED BY ME:
    def is_id_of_arrow_function_expression(self) -> bool:
        # interface FunctionExpression {
        #     id: Identifier | null;        <----- is `self` this?
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        return (self.name == "Identifier"
                and self.parent is not None
                and self.parent.name in ["FunctionExpression", "ArrowFunctionExpression"]
                and self.is_nth_child_of_parent(0)
                and len(self.parent.get("id")) == 1
                and self == self.parent.get("id")[0])

    # ADDED BY ME:
    def is_arrow_function_expression_param(self) -> bool:
        """
        Returns True if and only if
        there exists an (Arrow)FunctionExpression `f` such that `self in f.arrow_function_expression_get_params()`.
        """
        func_expr_parent: Optional[Node] = self.get_parent_or_none(["FunctionExpression", "ArrowFunctionExpression"])
        if func_expr_parent is None:
            return False
        return self in func_expr_parent.arrow_function_expression_get_params()

    # ADDED BY ME:
    def is_inside_any_arrow_function_expression_param(self) -> bool:
        """
        Returns True if and only if there is a Node `p` such that
        `self.is_inside(p)` and
        there exists an (Arrow)FunctionExpression `f` such that `p in f.arrow_function_expression_get_params()`.
        """
        func_expr_ancestor: Optional[Node] = self.get_ancestor_or_none(["FunctionExpression", "ArrowFunctionExpression"])
        if func_expr_ancestor is None:
            return False
        return any(self.is_inside(param) for param in func_expr_ancestor.arrow_function_expression_get_params())
        # Note how this assumes that parameters of FunctionExpressions may not contain FunctionExpressions themselves.

    # ADDED BY ME:
    def is_or_is_inside_any_arrow_function_expression_param(self) -> bool:
        """
        Returns True if and only if there is a Node `p` such that
        `self.is_inside(p)` or `self == p` and
        there exists an (Arrow)FunctionExpression `f` such that `p in f.arrow_function_expression_get_params()`.
        """
        func_expr_ancestor: Optional[Node] = self.get_ancestor_or_none(["FunctionExpression", "ArrowFunctionExpression"])
        if func_expr_ancestor is None:
            return False
        return any(self.is_inside(param) or self == param for param in func_expr_ancestor.arrow_function_expression_get_params())
        # Note how this assumes that parameters of FunctionExpressions may not contain FunctionExpressions themselves.

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
            params = self.arrow_function_expression_get_params()
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

    # ADDED BY ME:
    def object_expression_get_property(self, property_name: str) -> Optional[Self]:
        assert self.name == "ObjectExpression"
        for child in self.children:
            if (child.name == "Property"
                    and len(child.children) >= 1
                    and child.children[0].name == "Identifier"
                    and child.children[0].attributes['name'] == property_name):
                return child
        return None

    # ADDED BY ME:
    def object_expression_get_property_value(self, property_name: str) -> Optional[Self]:
        assert self.name == "ObjectExpression"
        prop = self.object_expression_get_property(property_name)
        if prop is None:
            return None
        elif len(prop.children) < 2:
            return None
        else:
            return prop.children[1]

    def is_leaf(self) -> bool:
        return not self.children

    def set_attribute(self, attribute_type: str, node_attribute: Any):
        self.attributes[attribute_type] = node_attribute

    def set_body(self, body):
        self.body = body

    def set_body_list(self, bool_body_list):
        self.body_list = bool_body_list

    def set_parent(self, parent: Self):
        self.parent = parent

    def set_child(self, child: Self):
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

    def is_comment(self) -> bool:
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

    def get_line(self) -> Optional[str]:
        """ Gets the line number where a given node is defined. """
        try:
            line_begin = self.attributes['loc']['start']['line']
            line_end = self.attributes['loc']['end']['line']
            return str(line_begin) + ' - ' + str(line_end)
        except KeyError:
            return None

    # ADDED BY ME:
    def get_line_number_as_int(self) -> Optional[int]:
        """ Gets the line number where a given node is defined (as an integer). """
        try:
            return self.attributes['loc']['start']['line']
        except KeyError:
            return None

    # ADDED BY ME:
    def get_whole_line_of_code_as_string(self) -> str:
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
    def get_location(self) -> Optional[str]:
        """ Gets the exact location (line *and* column number) where a given node is defined. """
        try:
            start_line = self.attributes['loc']['start']['line']
            start_column = self.attributes['loc']['start']['column']
            end_line = self.attributes['loc']['end']['line']
            end_column = self.attributes['loc']['end']['column']
            return f"{start_line}:{start_column} - {end_line}:{end_column}"
        except KeyError:
            return None

    # ADDED BY ME: # (cf. Esprima documentation PDF, Section 3.1 Token Location)
    def get_location_as_tuple(self) -> Tuple[int, int, int, int]:
        """
        Gets the exact location (line *and* column number) where a given node is defined.
        Instead of returning the result as a string, as get_location() does, returns a tuple of 4 integers:
        start_line, start_column, end_line, end_column
        """
        try:
            start_line = self.attributes['loc']['start']['line']
            start_column = self.attributes['loc']['start']['column']
            end_line = self.attributes['loc']['end']['line']
            end_column = self.attributes['loc']['end']['column']
            return start_line, start_column, end_line, end_column
        except KeyError:
            return -1, -1, -1, -1

    # ADDED BY ME:
    def functional_arg_get_args(self, resolve_args_to_identifiers: bool) -> List[Self]:  # ToDo: write custom Exception classes?
        """
        Example 1:
            self                 = (message, sender, sendResponse) => { /* ... */ }
            returned list        = [message Node, sender Node, sendResponse Node]

        Example 2:
            self                 = port => { /* ... */ }
            returned list        = [port Node]

        Parameters:
            resolve_args_to_identifiers: resolve more complex arguments consisting of parameter name + default value
                                       (e.g., "function foo(x=42) {}") just into the Identifier.

        Returns:
            the list of Nodes representing the arguments of this functional argument (see examples above);
            when resolve_args_to_identifiers=True, the returned list will only contain Identifiers and None values as
            more complex parameters (e.g., "{}") cannot be resolved to a *single* identifier(!);
            in all cases, the returned list will contain *exactly* as many items as the function has parameters(!)

        Raises:
            a TypeError when this is neither a FunctionExpression nor an ArrowFunctionExpression nor an Identifier;
            a KeyError when this is an Identifier but the Identifier couldn't be resolved to a FunctionDeclaration
        """
        if self.name in ["FunctionExpression", "ArrowFunctionExpression"]:  # cases 1 and 2: (Arrow)FunctionExpression:
            params = self.arrow_function_expression_get_params()
        elif self.name == "Identifier":  # case 3: Identifier (function reference):
            function_declaration = self.function_Identifier_get_FunctionDeclaration(True)
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
                params = function_declaration.function_declaration_get_params()
        else:
            raise TypeError()

        if not resolve_args_to_identifiers:
            return params
        else:
            # Instead of an Identifier, the FunctionParameter may also be an ArrayPattern or ObjectPattern, or
            #     an AssignmentPattern (whose left hand side in turn may be
            #     an Identifier, ArrayPattern or ObjectPattern; the right hand side may be any Expression):
            # * ArrayPattern:                         function msg_handler(msg, sender, [sendResp1, sendResp2]) { ... }
            # * ObjectPattern:                        function msg_handler(msg, sender, {x:x, y:y}) { ... }
            # * AssignmentPattern, LHS=Identifier:    function msg_handler(msg, sender, sendResponse=null) { ... }
            # * AssignmentPattern, LHS=ArrayPattern:  function msg_handler(msg, sender, [x,y]=[1,2]) { ... }
            # * AssignmentPattern, LHS=ObjectPattern: function msg_handler(msg, sender, {x, y}={x:1,y:2}) { ... }
            # => Here were only handle the AssignmentPattern, LHS=Identifier case using the
            #    function_param_get_identifier() method:  # ToDo: also handle all the other cases!
            return [param.function_param_get_identifier() for param in params]
            # necessary for "sendResponse=null" cases (default param values)
            # for more complex cases (e.g., "{x, y}" destructurings), function_param_get_identifier() returns `None`

    # ADDED BY ME:
    def functional_arg_get_arg(self, arg_index: int, resolve_arg_to_identifier: bool) -> Self:  # ToDo: write custom Exception classes?
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
        args = self.functional_arg_get_args(resolve_args_to_identifiers=resolve_arg_to_identifier)
        # The call above may raise a TypeError, or a KeyError.

        if arg_index >= len(args):
            raise IndexError()
        else:
            arg = args[arg_index]  # (arg1, arg2, *arg3*)
            if arg is None:  # (can only occur if resolve_arg_to_identifier=True)
                raise AttributeError()
            return arg

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

    # ADDED BY ME:
    def get_all_nodes_within_code_excerpt(self, start_line: int, start_col: int,
                                          end_line: int, end_col: int) -> List[Self]:
        return [node for node in self.get_all_as_iter(None)
                if node.lies_within_piece_of_code(start_line, start_col, end_line, end_col)]

    # ADDED BY ME:
    def average_identifier_length(self) -> float:
        """
        Returns the average length of each Identifier name.
        """
        identifier_lengths: List[int] = []
        for identifier in self.get_all_as_iter("Identifier"):
            identifier_lengths.append(len(identifier.attributes['name']))
        if len(identifier_lengths) == 0:  # cannot compute the mean of an empty list!
            return -1
        else:
            return statistics.mean(identifier_lengths)

    # ADDED BY ME:
    def average_declared_variable_name_length(self) -> float:
        """
        Returns the average length of each name of each declared variable.
        """
        variable_name_lengths: List[int] = []
        for var_decl in self.get_all_as_iter("VariableDeclarator"):
            # interface VariableDeclarator {
            #     id: Identifier | BindingPattern;
            #     init: Expression | null;
            # }
            # (ignore BindingPatterns for simplicity)
            if len(var_decl.children) > 0:  # (just a safety check)
                identifier_node: Node = var_decl.children[0]
                if identifier_node.name == "Identifier":
                    variable_name: str = identifier_node.attributes['name']
                    variable_name_lengths.append(len(variable_name))
        if len(variable_name_lengths) == 0:  # cannot compute the mean of an empty list!
            return -1
        else:
            return statistics.mean(variable_name_lengths)

    # ADDED BY ME:
    def average_function_declaration_name_length(self) -> float:
        """
        Returns the average length of each name of each declared function.
        """
        function_name_lengths: List[int] = []
        for func_decl in self.get_all_as_iter("FunctionDeclaration"):
            function_name_lengths.append(len(func_decl.function_declaration_get_name()))
        if len(function_name_lengths) == 0:  # cannot compute the mean of an empty list!
            return -1
        else:
            return statistics.mean(function_name_lengths)

    # ADDED BY ME:
    def average_class_name_length(self) -> float:
        """
        Returns the average length of each name of each declared class.
        """
        # interface ClassDeclaration {
        #     id: Identifier | null;
        #     superClass: Identifier | null;
        #     body: ClassBody;
        # }
        class_name_lengths: List[int] = []
        for class_decl in self.get_all_as_iter("ClassDeclaration"):
            class_name_lengths.append(len(class_decl.class_declaration_get_name()))
        if len(class_name_lengths) == 0:  # cannot compute the mean of an empty list!
            return -1
        else:
            return statistics.mean(class_name_lengths)

    # ADDED BY ME:
    def one_character_identifier_percentage(self) -> int:
        """
        Returns the percentage of Identifiers whose name is just 1 character long.
        """
        total_no_of_identifiers: int = 0
        no_of_identifiers_with_1_char_name: int = 0

        for identifier in self.get_all_as_iter("Identifier"):
            total_no_of_identifiers += 1
            if len(identifier.attributes['name']) == 1:
                no_of_identifiers_with_1_char_name += 1

        if total_no_of_identifiers > 0:
            return (100 * no_of_identifiers_with_1_char_name) // total_no_of_identifiers
        else:
            return -1

    def get_file(self) -> str:
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

    def set_data_dependency(self, extremity, nearest_statement=None) -> int:  # return value newly added by me
        """
        Returns:
            0 if the data dependency edge already existed;
            1 if a new data dependency edge has been added.
        """
        return_value = 0
        if extremity not in [el.extremity for el in self.data_dep_children]:  # Avoids duplicates
            self.data_dep_children.append(Dependence('data dependency', extremity, 'data',
                                                     nearest_statement))
            extremity.data_dep_parents.append(Dependence('data dependency', self, 'data',
                                                         nearest_statement))
            return_value = 1
        self.set_provenance_dd(extremity)  # Stored provenance
        return return_value

    # ADDED BY ME:
    def remove_data_dependency(self, extremity: Node) -> int:
        """
        Sadly, DoubleX sometimes adds data flows where they don't belong (cf. remove_incorrect_data_flow_edges.py),
        therefore we need a way to remove them...

        Returns:
            the number of removed data dependency children
        """
        prev_no_data_dep_children = len(self.data_dep_children)

        self.data_dep_children = [el for el in self.data_dep_children if el.extremity != extremity]

        # Don't forget to also remove the extremity's data dependency parent(!):
        extremity.data_dep_parents = [el for el in extremity.data_dep_parents if el.extremity != self]

        return prev_no_data_dep_children - len(self.data_dep_children)  # the no. of removed data dependency children


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
