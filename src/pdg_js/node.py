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
    def is_data_flow_equivalent_identifier(self, other, max_depth=1_000_000_000): # ToDo
        """
        Sometimes, we may want to check equality/equivalence between two different Identifiers beyond just their raw
        variable names. This function returns True if both `self` and `other` have a common data flow parent.

        By default, max_depth=1_000_000_000, but you may set it to a lower value.
        You might want to use max_depth=1 for example if you only want to compare direct data flow parents, i.e.,
        no data flow grandparents.
        When setting max_depth=0, this function will simply return whether `self.id == other.id`.
        """
        if not isinstance(self, Identifier) or not isinstance(other, Identifier):
            raise TypeError("is_data_flow_equivalent_identifier(): both self and other need to be Identifiers!")

        self_data_dep_parents = {self}
        other_data_dep_parents = {other}
        current_depth = 0
        last_len_self_data_dep_parents = 1
        last_len_other_data_dep_parents = 1
        while current_depth < max_depth:
            for parent1 in self_data_dep_parents.copy():
                self_data_dep_parents.update(grandparent.extremity for grandparent in parent1.data_dep_parents)
                # Note: update() appends multiple elements to a set
            for parent2 in other_data_dep_parents.copy():
                other_data_dep_parents.update(grandparent.extremity for grandparent in parent2.data_dep_parents)
            current_depth += 1
            if len(self_data_dep_parents) == last_len_self_data_dep_parents\
                    and len(other_data_dep_parents) == last_len_other_data_dep_parents:
                break  # stop as soon a as fixed point has been reached :)
            else:
                last_len_self_data_dep_parents = len(self_data_dep_parents)
                last_len_other_data_dep_parents = len(other_data_dep_parents)

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
        return self

    # ADDED BY ME:
    def get_sibling(self, idx):
        sibling = self.parent.children[idx]
        # Safety check, when the programmer calls get_sibling(), he likely wants a *different* Node:
        assert sibling.id != self.id
        return sibling

    # ADDED BY ME:
    def is_sibling_of(self, other):
        return self.parent is not None and self.parent == other.parent

    # ADDED BY ME:
    def grandparent(self):
        if self.parent is None:  # No parent...
            return None  # ...no grandparent.
        return self.parent.parent  # (might be None)

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
    def __str__(self):
        str_repr = ""

        attributes_of_interest = {
            "Identifier": 'name',
            "Literal": 'raw',
            "BinaryExpression": 'operator',      # 'instanceof' | 'in' | '+' | '-' | '*' | '/' | '%' | '**' |
                                                 # '|' | '^' | '&' | '==' | '!=' | '===' | '!==' |
                                                 # '<' | '>' | '<=' | '<<' | '>>' | '>>>'
            "LogicalExpression": 'operator',     # || or &&
            "AssignmentExpression": 'operator',  # '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
                                                 # '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|='
            "UnaryExpression": 'operator',       # '+' | '-' | '~' | '!' | 'delete' | 'void' | 'typeof'
            "UpdateExpression": 'operator'       # '++' or '--'
        }

        if self.name in attributes_of_interest.keys():
            str_repr = f"[{self.id}] [{self.name}:\"{self.attributes[attributes_of_interest[self.name]]}\"] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"
        else:
            str_repr = f"[{self.id}] [{self.name}] ({len(self.children)} child{'ren' if len(self.children) != 1 else ''})"

        # cf. display_extension.py:
        if isinstance(self, Statement):
            for cf_dep in self.control_dep_children:
                str_repr += f" --{cf_dep.label}--> [{cf_dep.extremity.id}]"

        # cf. display_extension.py:
        if isinstance(self, Identifier):
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
    def is_nth_child_of_parent(self, n):
        sibling_ids = [sibling.id for sibling in self.parent.children]
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
    def get_statement(self):
        """
        If this Node isn't a Statement itself already, this function returns the Statement that this Node is a part of,
        by going up the PDG parent-by-parent until a Statement is found.

        This function is useful when dealing with control flow.

        Returns `None` when this Node isn't part of any Statement but that case should not actually occur!
        """
        if isinstance(self, Statement):
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
