import json
import os
from typing import List, Self

from pdg_js.node import Node
from DataFlow import DataFlow


class DoubleDataFlow:
    """
    Represents two DataFlows eventually meeting in the same rendezvous Node (e.g., a function call or assignment).

    Example:
    ```
    "chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
        chrome.cookies.getAll({},
            function(cookies) {
                sendResponse(cookies);
            }
        );
        return true;
    });"
    ```
    * 1st flow (from flow/source): cookies      -> cookies
    * 2nd flow (to flow/sink):     sendResponse -> sendResponse
    * rendezvous function call:    sendResponse(cookies);
    """
    def __init__(self,
                 from_flow: DataFlow,
                 to_flow: DataFlow,
                 rendezvous_nodes: List[str]):
        from_flow_final_expr = from_flow.last_node().get_ancestor_or_none(rendezvous_nodes)
        to_flow_final_expr = to_flow.last_node().get_ancestor_or_none(rendezvous_nodes)
        if (from_flow_final_expr != to_flow_final_expr
                or from_flow_final_expr is None
                or to_flow_final_expr is None):
            raise ValueError("from_flow and to_flow must both end in the same " + "/".join(rendezvous_nodes))

        self.from_flow = from_flow
        self.to_flow = to_flow
        self.rendezvous_nodes = rendezvous_nodes
        self.data_flow_number = "?/?"

    def as_pretty_dict(self):
        """
        Returns this DoubleDataFlow as a (JSON-dump-able) dictionary.
        Cf. generated `analysis_renderer_attacker.json` file.
        """
        result = {
            "from_flow": self.from_flow.pretty(),
            "to_flow": self.to_flow.pretty(),
            "rendezvous": {  # previously called "function_call" but doesn't have to be one; can also be an assignment!
                "type": self.from_flow.last_node().get_ancestor(self.rendezvous_nodes).name,
                "location": self.from_flow.last_node().get_ancestor(self.rendezvous_nodes)
                                    .get_location(),
                "filename": self.from_flow.last_node().get_ancestor(self.rendezvous_nodes)
                                    .get_file(),
                "line_of_code": self.from_flow.last_node().get_ancestor(self.rendezvous_nodes)
                                    .get_whole_line_of_code_as_string()
            }
        }
        if self.data_flow_number is not None:
            result["data_flow_number"] = self.data_flow_number
        return result

    def __str__(self):
        return json.dumps(self.as_pretty_dict(), indent=4, sort_keys=False, skipkeys=True)

    @classmethod
    def data_flows_into_sink(cls,
                             pdg: Node,
                             from_node: Node,
                             to_node: Node,
                             rendezvous_nodes: List[str],
                             rendezvous_forbidden_descendents: List[str] =
                                    ["FunctionExpression", "ArrowFunctionExpression", "BlockStatement",
                                     "FunctionDeclaration"],
                             return_multiple=True,
                             allow_unreachable_rendezvous=False,
                             allow_IIFE_rendezvous=False,
                             check_for_uxss_sanitization=False,
                             ) -> List[Self]:
        """
        Returns the empty list `[]` if no data flow exists from `from_node` to `to_node`.
        Otherwise, returns the data flow(s) from `from_node` to `to_node` as DoubleDataFlow objects.
        Each such DoubleDataFlow consists of:
        * a "from_flow" (from `from_node` to a rendezvous node, e.g., a "CallExpression" or "AssignmentExpression"), and
        * a "to_flow" (from `to_node` to the *same* rendezvous node).

        Parameters:
            pdg: the entire PDG
            from_node: an Identifier Node of a value containing sensitive data (e.g., cookies);
                       alternatively: an ObjectPattern (equivalent to calling this function on each Property/Identifier
                                                        in that ObjectPattern separately)
            to_node: an Identifier Node of a function representing a dangerous sink (e.g., sendResponse);
                     may also be a MemberExpression (e.g., port.postMessage),
                     no data flow will be followed then, however # todo: where to flow: before or after this?!
            rendezvous_nodes: the list of allowed rendezvous Node names as strings,
                              e.g.: ["CallExpression", "AssignmentExpression"]
            rendezvous_forbidden_descendents: the rendezvous node may not have any of these descendents (i.e., none of
                                              the names of its descendents may be inside this list); the purpose of
                                              this is to prevent overly complex rendezvous which are very likely false
                                              positives
            return_multiple: a boolean indicating whether to return multiple data flows if multiple data flows exist
                             from the given `from_node` to the given `to_node`; when set to False, the returned list
                             will either be empty or contain exactly 1 element; when set to True, the returned list
                             can have arbitrary length;
                             set to True when you later want to filter the returned data flows, e.g., only for the
                             unprotected/un-checked/un-sanitized ones (!!!)
            allow_unreachable_rendezvous: whether to allow the rendezvous to be unreachable (default: False)
            allow_IIFE_rendezvous: whether to allow the rendezvous CallExpression to be an IIFE; only has an effect
                                   when `"CallExpression" in rendezvous_nodes`
                                   (default: False, to prevent false positives!)
                                   (this type of false positive often occurred for the Kim+Lee extensions tested)
            check_for_uxss_sanitization: when this function is used to detect UXSS vulnerabilities/data flows, set this
                                         to True (the default is False) to check for correct methods of UXSS
                                         sanitization, correctly sanitized data flows won't be returned then

        Returns:
            Returns the empty list `[]` if no data flow exists from `from_node` to `to_node`.
            Otherwise, returns the data flow(s) from `from_node` to `to_node` as DoubleDataFlow objects.
        """
        # print(f"to_node.name = {to_node.name}")
        assert to_node.name in ["Identifier", "MemberExpression"]

        if os.environ.get('PRINT_PDGS') == "yes":
            print(f"Looking for data flow in PDG [{pdg.id}] from node [{from_node.id}] to function [{to_node.id}] ...")

        data_flows_from = DataFlow.all_continued_beginning_at(from_node)  # from_node may be an ObjectPattern

        data_flows_to = DataFlow.beginning_at(to_node)[0].get_continued_flows()\
                            if to_node.name == "Identifier"\
                            else [DataFlow.pseudo(to_node)]
        # No actual data flow may begin at a MemberExpression, hence a "pseudo" data flow!

        # Check if any data flow from `data_flows_from` and any data flow from `data_flows_to` end up in the same
        #   CallExpression; if so return both of these data flows:
        results = []
        for from_flow in data_flows_from:
            for to_flow in data_flows_to:
                # Check if both from_flow and to_flow end in the same rendezvous Node (e.g., a CallExpression or
                #   AssignmentExpression); if so, append to result:
                from_flow_final_expr = from_flow.last_node().get_ancestor_or_none(rendezvous_nodes)
                to_flow_final_expr = to_flow.last_node().get_ancestor_or_none(rendezvous_nodes)
                # => Q: What if data flow continues *beyond* the rendezvous node?
                #    A: This depends on the DataFlowsConsidered mode used, cf. the DataFlowsConsidered enum,
                #       DataFlowGraph.get_data_flows() and the --data-flows-considered command line argument.
                #       Using ALL or ONE_PER_NODE_SHORTEST, there will be always be a data flow
                #       start --data--> ... --data--> X, ending in X, generated, for each X that is reachable from
                #       `start` via data flow edges.
                #       This is *not* the case for all the other modes, however!!!
                if from_flow_final_expr == to_flow_final_expr and from_flow_final_expr is not None:
                    if (
                        (allow_unreachable_rendezvous or (not from_flow_final_expr.is_unreachable())) and
                        (allow_IIFE_rendezvous or (not from_flow_final_expr.is_IIFE_call_expression())) and
                        not from_flow_final_expr.has_descendent(rendezvous_forbidden_descendents) and
                        (not check_for_uxss_sanitization or (not from_flow.from_flow_is_correctly_uxss_sanitized() and
                                                             not to_flow.to_flow_is_correctly_uxss_sanitized() and
                                                             not from_flow_final_expr.rendezvous_is_correctly_uxss_sanitized()))
                    ):
                        result = DoubleDataFlow(from_flow=from_flow, to_flow=to_flow, rendezvous_nodes=rendezvous_nodes)
                        if return_multiple:
                            results.append(result)
                        else:
                            result.data_flow_number = f"1/1+"  # meaning: 1st data flow of 1 (or more) total data flows
                            return [result]

        for i in range(len(results)):
            results[i].data_flow_number = f"{i+1}/{len(results)}"

        return results
