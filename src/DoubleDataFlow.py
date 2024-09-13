import json


class DoubleDataFlow:
    """
    Represents two DataFlows eventually meeting in the same function call.

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
    * function call:               sendResponse(cookies);
    """
    def __init__(self, from_flow, to_flow):
        from_flow_final_call_expr = from_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"])
        to_flow_final_call_expr = to_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"])
        if (from_flow_final_call_expr != to_flow_final_call_expr
                or from_flow_final_call_expr is None
                or to_flow_final_call_expr is None):
            raise ValueError("from_flow and to_flow must both end in the same CallExpression or AssignmentExpression")

        self.from_flow = from_flow
        self.to_flow = to_flow
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
                "type": self.from_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"]).name,
                "location": self.from_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"])
                                    .get_location(),
                "filename": self.from_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"])
                                    .get_file(),
                "line_of_code": self.from_flow.last_node().get_ancestor(["CallExpression", "AssignmentExpression"])
                                    .get_whole_line_of_code_as_string()
            }
        }
        if self.data_flow_number is not None:
            result["data_flow_number"] = self.data_flow_number
        return result

    def __str__(self):
        return json.dumps(self.as_pretty_dict(), indent=4, sort_keys=False, skipkeys=True)
