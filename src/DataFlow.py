import os
import sys
from typing import List, Self, Optional
import re

from DataFlowsConsidered import DataFlowsConsidered
from pdg_js.node import Node


def is_uxss_sanitizing_regex_pattern(pattern: str) -> bool:
    r"""
    The given regex pattern comes from a <source>.replaceAll(/pattern/g, ...) or <source>.replace(/pattern/g, ...)
    call, where <source> is some identifier coming out of a UXSS "from" data flow.

    Now the question is:
    Is the pattern sufficient to prevent *any* UXSS attack vector?
    We'd rather have false positives than false negatives in our end result, meaning that, when in doubt,
    we will assume that a regex pattern is *not* sufficient for sanitization!!!

    Our approach is simple: the given pattern must match all non-alphanumeric, non-underscore characters!

    Examples of sufficient sanitization patterns are:
        * \W
        * [^\w]
        * \D
        * [^\d]
        * [^a-zA-Z0-9_]
        * [^a-z]

    Parameters:
        the JavaScript regex pattern as a string (without leading and trailing "/")
    """
    bad_chars: str = r"""!"#$%&'()*+,-./:;<=>?[\]^`{|}~"""
    return re.sub(pattern, "", bad_chars) == ""


class DataFlow:
    def __init__(self, nodes: List[Node]):
        self.nodes = nodes

    def __str__(self):
        return " -> ".join(f"[{node.id}]" for node in self.nodes)

    def verbose_string(self) -> str:
        return " -> ".join(
            f'[{node.id}] [{node.name}:"{node.attributes.get('name')}"] <<< {node.body} '
            f'(line {node.get_line()}, parent: [{node.parent.id if node.parent is not None else None}])'
            for node in self.nodes
        )

    def pretty(self):  # => result is used later by json.dump()
        return [{
            "no": i+1,
            "location": self.nodes[i].get_location(),
            "filename": self.nodes[i].get_file(),
            "identifier": self.nodes[i].attributes['name']\
                            if 'name' in self.nodes[i].attributes else f"<{self.nodes[i].name}>",
            "line_of_code": self.nodes[i].get_whole_line_of_code_as_string()
        } for i in range(len(self.nodes))]

    @classmethod
    def from_node_list(cls, node_list: List[Node]):
        return DataFlow(node_list)

    @classmethod
    def beginning_at(cls, initial_node: Node) -> List[Self]:
        """
        Parameters:
            initial_node: the Identifier Node marking the beginning of a DataFlow;
                          alternatively: an ObjectPattern

        Returns:
            Returns a List of one DataFlow, unless the `initial_node` given is an ObjectPattern with >1 child, then
            this method will return one DataFlow for each Property of the given ObjectPattern!
        """
        if initial_node.name == "Identifier":
            return [DataFlow([initial_node])]
        elif initial_node.name == "ObjectPattern":
            # Example #1: "chrome.runtime.onMessage.addListener((msg, {url: sender_url}, sendResponse) => { sender_url });"
            # [1] [ObjectPattern] (1 child)
            #     [2] [Property] (2 children)
            #         [3] [Identifier:"url"] (0 children)
            #         [4] [Identifier:"sender_url"] (0 children) --data--> [...]
            # => Pretend as if it were "chrome.runtime.onMessage.addListener((msg, sender_url, sendResponse) => ...)",
            #    get_accessed_members() should still be able to recognize the "url" attribute access in the DataFlow as:
            #    1. node.parent.name == "Property"
            #    2. node.is_nth_child_of_parent(1)
            #    3. node.grandparent() is not None
            #    4. node.grandparent().name == "ObjectPattern"):
            if len(initial_node.children) == 1:
                return [DataFlow([initial_node.get_child("Property").children[1]])]

            # Example #2: "chrome.runtime.onMessage.addListener((msg, {origin, url: sender_url, tab}, sendResponse) => { sender_url });"
            # [1] [ObjectPattern] (3 children)
            # 		[2] [Property] (2 children)
            # 			[3] [Identifier:"origin"] (0 children)
            # 			[4] [Identifier:"origin"] (0 children) --data--> [...]
            # 		[5] [Property] (2 children)
            # 			[6] [Identifier:"url"] (0 children)
            # 			[7] [Identifier:"sender_url"] (0 children) --data--> [...]
            # 		[8] [Property] (2 children)
            # 			[9] [Identifier:"tab"] (0 children)
            # 			[10] [Identifier:"tab"] (0 children) --data--> [...]
            # => Start 3 different data flow at all 3 different Identifiers: [4], [7] and [10]
            return [DataFlow([child.children[1]]) for child in initial_node.children]
            # Note that an ObjectPattern can only have Properties as children! (cf. Esprima docs)
        else:
            raise TypeError(f"A data flow must begin at an Identifier or ObjectPattern, not a(n) {initial_node.name}")

    @classmethod
    def all_continued_beginning_at(cls, initial_node: Node,
                                   data_flows_considered: Optional[DataFlowsConsidered] = None) -> List[Self]:
        """
        Equivalent to
        ```
        DataFlow.beginning_at(initial_node)[0].get_continued_flows()
        ```
        when `DataFlow.beginning_at(initial_node)` only returns one DataFlow.
        `DataFlow.beginning_at(initial_node)` may return multiple DataFlows however, when given an ObjectPattern with
        >1 children. In this case, this function returns the concatenated result of calling get_continued_flows()
        on each of them.

        Just like get_continued_flows(), this method also takes an optional `data_flows_considered` parameter
        (cf. DataFlowsConsidered Enum).
        """
        all_data_flows_beginning_at_initial_node: List[DataFlow] = DataFlow.beginning_at(initial_node=initial_node)
        all_continued_data_flows: List[DataFlow] = []
        for df in all_data_flows_beginning_at_initial_node:
            all_continued_data_flows.extend(df.get_continued_flows(data_flows_considered=data_flows_considered))
        return all_continued_data_flows

    @classmethod
    def pseudo(cls, single_node: Node) -> Self:
        """
        Returns a pseudo data flow containing only a single node.
        Cannot be continued.
        """
        assert single_node.name not in ["Identifier", "ObjectPattern"]
        return DataFlow([single_node])

    def may_continue(self) -> bool:
        """
        Returns True iff this data flow may be continued.
        """
        return len(self.nodes[-1].data_dep_children()) > 0

    def continue_flow(self) -> Optional[List[Self]]:
        """
        Returns a list of all possible (1-step) continuations of this DataFlow (being DataFlows themselves),
        or `None` if this DataFlow cannot be continued any further.
        """
        result = []
        next = self.nodes[-1].data_dep_children()
        if len(next) == 0:
            return None  # indicate that this DataFlow cannot be continued any further
        for child_data_dep in next:
            result.append(DataFlow.from_node_list(self.nodes + [child_data_dep.extremity]))
        return result

    def get_all_continued_flows(self) -> List[Self]:
        """
        Returns a list of all possible (n-step) continuations of this DataFlow (being DataFlows themselves).
        Because of repeated branching, the list returned can, in theory, be arbitrarily long.

        Generate all data flows
            ... --data--> self.last_node()=x0 --data--> x1 --data--> x2 --data--> ... --data--> xn
        where xi != xj for 0<=i<=n, 0<=j<=n, i != j.

        IN FACT, THE NUMBER OF DATA FLOWS MIGHT BE MASSIVE, GROWING EXPONENTIALLY WITH EACH BRANCHING!!!
        THEREFORE, IT IS HIGHLY RECOMMENDED TO USE THE get_continued_flows() METHOD FOR ANY NON-TESTING
        PURPOSES INSTEAD!!!

        Returns `[self]` if this DataFlow cannot be continued any further.
        """
        print("[Warning] Using get_all_continued_flows() which has exponential runtime!!!", file=sys.stderr)

        return self.get_continued_flows(data_flows_considered=DataFlowsConsidered.ALL)

    def get_continued_flows(self,
                            data_flows_considered: Optional[DataFlowsConsidered] = None) -> List[Self]:
        """
        Returns a list of numerous possible (n-step) continuations of this DataFlow (being DataFlows themselves).
        Which continuations these will be is determined via the `data_flows_considered` parameter.
        By default (when the `data_flows_considered` parameter is not supplied or set to None), whatever the user
        supplied via the --data-flows-considered command line argument will be used. If that also wasn't supplied
        (e.g., when using this method in a test case), `DataFlowsConsidered.default()` will be used.
        Cf. doc comments of the DataFlowsConsidered enum for further info.
        But beware that some of the variants of DataFlowsConsidered will have worst-case exponential runtime!
        """
        from DataFlowGraph import DataFlowGraph

        last_node: Node = self.last_node()

        continuations: List[DataFlow] = DataFlowGraph(start_node=last_node).get_data_flows(
            data_flows_considered=(DataFlowsConsidered[
                os.environ.get('DATA_FLOWS_CONSIDERED', DataFlowsConsidered.default())  # string to enum
            ] if data_flows_considered is None else data_flows_considered)
        )

        if len(self.nodes) == 1:  # when this DataFlow has just been created => self.nodes[:-1] will be empty
            return continuations
        else:  # This case should be purely hypothetical and not actually occur in my code:
            return [DataFlow.from_node_list(self.nodes[:-1] + df.nodes) for df in continuations]

    def last_node(self):
        return self.nodes[-1]

    def get_sub_flow(self, first_node=None, last_node=None):
        """
        Returns this DataFlow but
        (a) starting only at the given `first_node` (inclusive),
        (b) cut off after the given `last_node` (inclusive).
        """
        if first_node is None and last_node is None:
            return self
        elif first_node is None:
            return DataFlow(self.nodes[:self.nodes.index(last_node) + 1])
        elif last_node is None:
            return DataFlow(self.nodes[self.nodes.index(first_node):])
        else:
            return DataFlow(self.nodes[self.nodes.index(first_node):self.nodes.index(last_node) + 1])

    def has_cycle(self):
        return len(set(self.nodes)) != len(self.nodes)

    def get_accessed_members(self, include_method_calls=False, include_last_node=True):
        r"""
        Along a data flow, multiple members/attributes of the initial variable may be accessed.
        This function returns a list of all of them, in order (i.e., in the order of the data flow).

        For example:
        ```
        let s = sender;
        let x = s.url;                     // [MemberExpression]
        y = x.replace(/^https:\/\//,"");   // [CallExpression] > [MemberExpression]
        let url_prefix = y.split("/")[0];
        ```

        Then this function returns the following list of strings (when include_method_calls=False):
        ["url"]

        Then this function returns the following list of strings (when include_method_calls=True):
        ["url", "replace()", "split()"]

        Note how array accesses like "[0]" or "[i]" will always be ignored!
        Only member accesses like "x['y']" will be considered as they're equivalent to "x.y"!

        Note: for an access like `s.tab.url`, ["tab", "url"] will be returned!
        """

        # First, some info on what member accesses look like in the PDG:
        #
        # * "x.y":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [MemberExpression] (2 children)
        # 			[3] [Identifier:"x"] (0 children)
        # 			[4] [Identifier:"y"] (0 children)
        #
        # * "x.y()":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [CallExpression] (1 child)
        # 			[3] [MemberExpression] (2 children)
        # 				[4] [Identifier:"x"] (0 children)
        # 				[5] [Identifier:"y"] (0 children)
        #
        # * "x.y.z":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [MemberExpression] (2 children)
        # 			[3] [MemberExpression] (2 children)
        # 				[4] [Identifier:"x"] (0 children)
        # 				[5] [Identifier:"y"] (0 children)
        # 			[6] [Identifier:"z"] (0 children)
        #
        # * "x.y.z()":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [CallExpression] (1 child)
        # 			[3] [MemberExpression] (2 children)
        # 				[4] [MemberExpression] (2 children)
        # 					[5] [Identifier:"x"] (0 children)
        # 					[6] [Identifier:"y"] (0 children)
        # 				[7] [Identifier:"z"] (0 children)
        #
        # * And now together with a data flow: "a = x.y"
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression] (2 children)
        # 			[3] [Identifier:"a"] (0 children)
        # 			[4] [MemberExpression] (2 children)
        # 				[5] [Identifier:"x"] (0 children) --data--> [3]
        # 				[6] [Identifier:"y"] (0 children) --data--> [3]
        #
        # * "a = x.y()":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression] (2 children)
        # 			[3] [Identifier:"a"] (0 children)
        # 			[4] [CallExpression] (1 child)
        # 				[5] [MemberExpression] (2 children)
        # 					[6] [Identifier:"x"] (0 children) --data--> [3]
        # 					[7] [Identifier:"y"] (0 children) --data--> [3]
        #
        # * "a = x.y.z":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression] (2 children)
        # 			[3] [Identifier:"a"] (0 children)
        # 			[4] [MemberExpression] (2 children)
        # 				[5] [MemberExpression] (2 children)
        # 					[6] [Identifier:"x"] (0 children) --data--> [3]
        # 					[7] [Identifier:"y"] (0 children) --data--> [3]
        # 				[8] [Identifier:"z"] (0 children) --data--> [3]
        #
        # * "a = x.y.z()":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression] (2 children)
        # 			[3] [Identifier:"a"] (0 children)
        # 			[4] [CallExpression] (1 child)
        # 				[5] [MemberExpression] (2 children)
        # 					[6] [MemberExpression] (2 children)
        # 						[7] [Identifier:"x"] (0 children) --data--> [3]
        # 						[8] [Identifier:"y"] (0 children) --data--> [3]
        # 					[9] [Identifier:"z"] (0 children) --data--> [3]
        #
        #
        # * "({url: sender_url} = sender)" should be handled in the same way as "sender_url = sender.url" as they're
        #     equivalent; with "({url} = sender)" also being equivalent to "({url: url} = sender)" (same PDG!):
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression:"="] (2 children)
        # 			[3] [ObjectPattern] (1 child)
        # 				[4] [Property] (2 children)
        # 					[5] [Identifier:"url"] (0 children)
        # 					[6] [Identifier:"sender_url"] (0 children) --data--> ...
        # 			[7] [Identifier:"sender"] (0 children) --data--> [5] --data--> [6]
        # Data Flow: [7] [Identifier:"sender"] --data--> [6] [Identifier:"sender_url"] --data--> ...
        #
        # * "({origin: sender_origin, url: sender_url, tab: sender_tab} = sender)":
        #
        # [1] [ExpressionStatement] (1 child)
        # 		[2] [AssignmentExpression:"="] (2 children)
        # 			[3] [ObjectPattern] (3 children)
        # 				[4] [Property] (2 children)
        # 					[5] [Identifier:"origin"] (0 children)
        # 					[6] [Identifier:"sender_origin"] (0 children)
        # 				[7] [Property] (2 children)
        # 					[8] [Identifier:"url"] (0 children)
        # 					[9] [Identifier:"sender_url"] (0 children) --data--> ...
        # 				[10] [Property] (2 children)
        # 					[11] [Identifier:"tab"] (0 children)
        # 					[12] [Identifier:"sender_tab"] (0 children)
        # 			[13] [Identifier:"sender"] (0 children) --data--> [5] --data--> [6] --data--> [8] --data--> [9] --data--> [11] --data--> [12]
        # Data Flow: [13] [Identifier:"sender"] --data--> [9] [Identifier:"sender_url"] (0 children) --data--> ...

        result = []

        for node in (self.nodes if include_last_node else self.nodes[:-1]):  # For each (Identifier) Node in the DataFlow:
            # If the (Identifier) Node `x` is the left part of a MemberExpression `x.y`
            #     (i.e., a member of it got accessed), add `y` to the list of accessed members inside this DataFlow:
            if node.parent.name == "MemberExpression" and node.is_nth_child_of_parent(0):
                current_node = node
                # Repeat in case the MemberExpression is a nested MemberExpression (e.g., x.y.z instead of x.y):
                while current_node.parent.name == "MemberExpression" and current_node.is_nth_child_of_parent(0):
                    # Skip function calls if include_method_calls=False:
                    is_method_call: bool = current_node.grandparent() is not None\
                            and current_node.grandparent().name == "CallExpression"\
                            and current_node.parent.is_nth_child_of_parent(0)  # difference between "x.y()" but not "foo(x.y)" !!!
                    if not include_method_calls and is_method_call:
                        # Go two(!) levels up the tree and then see if we're still (directly) inside a MemberExpression
                        #   (note that if we'd go up just 1 level we'd *definitely* be inside a CallExpression!):
                        current_node = current_node.parent.parent
                    else:
                        # Add the name of the accessed member to the result list; unless it's a "[0]" or "[i]" type of
                        #   access:
                        accessed_member = current_node.get_sibling(1)
                        if accessed_member.name == "Identifier" and current_node.parent.attributes['computed'] == False:  # e.g.: "x.y"
                            accessed_member_name: str = accessed_member.attributes['name']  # "y"
                            result.append(accessed_member_name + ("()" if is_method_call else ""))
                        elif accessed_member.name == "Literal" and isinstance(accessed_member.attributes['value'], str) and current_node.parent.attributes['computed'] == True:  # e.g.: "x['y']"
                            accessed_member_name: str = accessed_member.attributes['value']  # "y"
                            result.append(accessed_member_name + ("()" if is_method_call else ""))
                        else:  # e.g.: "x[y]" or "x[0]"
                            pass  # ignore/skip
                        # Go one level up the tree (or 2 when a method call) and then see if we're still (directly)
                        #     inside a MemberExpression:
                        current_node = current_node.parent.parent if is_method_call else current_node.parent

            # If the (Identifier) Node `x` is part of a `{y: x}` ObjectPattern, add `y` to the list of accessed members
            #     inside this DataFlow:
            elif (node.parent.name == "Property"
                  and node.is_nth_child_of_parent(1)
                  and node.grandparent() is not None
                  and node.grandparent().name == "ObjectPattern"):
                # Add the name of the accessed member to the result list:
                accessed_member_name: str = node.get_sibling(0).attributes["name"]  # maybe this will raise a KeyError in some cases, we shall see...
                result.append(accessed_member_name)

        return result

    def from_flow_is_correctly_uxss_sanitized(self) -> bool:
        for node in self.nodes:
            # UXSS-safe: <source>.replaceAll(/pattern/g, ...)    (where the "g" is actually required)
            #            <source>.replace(/pattern/g, ...)    where the "g" is crucial!!!
            #            => it's hard to say exactly how a string must be escaped as that depends on the context where it
            #               will be used, examples:
            #                 - string is assigned to el.innerHTML later on
            #                 - string will become part of an inserted script
            #                 - string will become part of a stylesheet
            #                 - ...
            #               => to simplify things (and prevent False Negatives), we just say that the pattern must
            #                  therefore include/match all non-alphanumeric ASCII chars
            #            => Syntax: replaceAll(pattern, replacement)
            #                       replace(pattern, replacement)
            if (node.is_lhs_of_a("MemberExpression") and
                    (node.get_sibling_relative(+1).is_identifier_named("replaceAll") or
                     node.get_sibling_relative(+1).is_identifier_named("replace"))):
                if node.parent.is_callee_of_a_call_expression():
                    call_expression: Node = node.grandparent()
                    assert call_expression.name == "CallExpression"
                    arguments: List[Node] = call_expression.get("arguments")
                    if len(arguments) > 0:
                        pattern = arguments[0]
                        if pattern.name == "Literal" and 'regex' in pattern.attributes:
                            if (node.get_sibling_relative(+1).is_identifier_named("replaceAll")
                                    or 'flags' in pattern.attributes['regex'] and 'g' in pattern.attributes['regex']['flags']):
                                regex_pattern: str = pattern.attributes['regex']['pattern']
                                if is_uxss_sanitizing_regex_pattern(regex_pattern):
                                    print(f"[Info] Correct UXSS sanitization using replace()/replaceAll() found "
                                          f"in file {node.get_file()}, line {node.get_line()}")
                                    return True

            # UXSS-safe: parseInt(<source>) and parseFloat(<source>)
            #            => returned value will be a number and therefore definitely safe
            if node.parent.name == "CallExpression":
                callee: Node = node.parent.get("callee")[0]
                if callee.is_identifier_named("parseInt") or callee.is_identifier_named("parseFloat"):
                    print(f"[Info] Correct UXSS sanitization using parseInt()/parseFloat() found "
                          f"in file {node.get_file()}, line {node.get_line()}")
                    return True

        return False

    def to_flow_is_correctly_uxss_sanitized(self) -> bool:
        return False
