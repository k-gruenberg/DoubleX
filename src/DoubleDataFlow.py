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
        if from_flow.last_node().parent.id != to_flow.last_node().parent.id or\
                from_flow.last_node().parent.name != "CallExpression":
            raise ValueError("from_flow and to_flow must both end in the same function call/CallExpression")

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
            "function_call": {
                "location": self.from_flow.last_node().parent.get_location(),
                "filename": self.from_flow.last_node().parent.get_file(),
                "line_of_code": self.from_flow.last_node().parent.get_whole_line_of_code_as_string()
            }
        }
        if self.data_flow_number is not None:
            result["data_flow_number"] = self.data_flow_number
        return result

    def __str__(self):
        return json.dumps(self.as_pretty_dict(), indent=4, sort_keys=False, skipkeys=True)
