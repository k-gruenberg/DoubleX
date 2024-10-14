from typing import List

from DataFlowsConsidered import DataFlowsConsidered
from .Func import Func
from .node import Node
from DataFlow import DataFlow


class MessageListener(Func):
    """
    A special type of `Func`, namely a message listener.
    There are 2 kinds of message listeners (which are further subclasses of `MessageListener`):
        1. RuntimeOnMessageListener: chrome.runtime.onMessage.addListener(...)
        2. PortOnMessageListener: port.onMessage.addListener(...)
    They differ slightly in the arguments that they take:
        1. RuntimeOnMessageListener:
               (message: any, sender: MessageSender, sendResponse: function) => boolean | undefined
               => https://developer.chrome.com/docs/extensions/reference/api/runtime#event-onMessage
        2. PortOnMessageListener:
               (message: any, port: Port) => void
               => https://developer.chrome.com/docs/extensions/reference/api/runtime?hl=en#type-Port
               where "Port" has attributes:
                   - name: string
                   - sender: MessageSender optional
                     => The documentation says:
                        "This property will only be present on ports passed to
                         onConnect / onConnectExternal / onConnectNative listeners."
                        => I tested it out however: The 'sender' property is *also* present for
                           (port.)onMessage listeners inside runtime.onConnect handlers!!!

    This subclass of `Func` provides an easy access to all "sender" identifiers using .get_all_sender_identifiers(),
    as well as an easy access to all "sender.url" / "sender.tab.url" identifiers using .get_all_url_identifiers().
    These are implemented differently, depending on the subclass (RuntimeOnMessageListener vs. PortOnMessageListener).

    A .get_all_message_identifiers() method is also provided.
    """

    def __init__(self, node: Node, use_df_edges: bool = True):
        super().__init__(node=node, use_df_edges=use_df_edges)

    def get_all_message_identifiers(self) -> List[Node]:
        if message_param := self.get_nth_param_or_none(n=0, resolve_params_to_identifiers=False):
            return message_param.function_param_get_identifiers()
        else:
            return []

    def get_all_sender_identifiers(self) -> List[Node]:
        raise NotImplementedError("implemented by sub-class")

    def get_all_url_identifiers(self) -> List[Node]:
        raise NotImplementedError("implemented by sub-class")


class RuntimeOnMessageListener(MessageListener):
    """
    The MessageListener Func of a chrome.runtime.onMessage.addListener(...) call.

    Arguments taken:
        (message: any, sender: MessageSender, sendResponse: function) => boolean | undefined
        => https://developer.chrome.com/docs/extensions/reference/api/runtime#event-onMessage
    """

    def __init__(self, node: Node, use_df_edges: bool = True):
        super().__init__(node=node, use_df_edges=use_df_edges)

    def get_all_sender_identifiers(self) -> List[Node]:
        if sender_param := self.get_nth_param_or_none(n=1, resolve_params_to_identifiers=True):
            return [sender_param]
        else:
            return []

    def get_all_url_identifiers(self) -> List[Node]:
        raise NotImplementedError("todo")


class PortOnMessageListener(MessageListener):
    """
    The MessageListener Func of a port.onMessage.addListener(...) call.

    Arguments taken:
        (message: any, port: Port) => void
        => https://developer.chrome.com/docs/extensions/reference/api/runtime?hl=en#type-Port
        where "Port" has attributes:
            - name: string
            - sender: MessageSender optional
              => The documentation says:
                 "This property will only be present on ports passed to
                  onConnect / onConnectExternal / onConnectNative listeners."
                 => I tested it out however: The 'sender' property is *also* present for
                    (port.)onMessage listeners inside runtime.onConnect handlers!!!
    """

    def __init__(self, node: Node, use_df_edges: bool = True):
        super().__init__(node=node, use_df_edges=use_df_edges)

    def get_all_sender_identifiers(self) -> List[Node]:
        if port_param_identifier := self.get_nth_param_or_none(n=1, resolve_params_to_identifiers=True):
            # Simple "port" or "port=some_redundant_default" parameter:
            data_flows: List[DataFlow] =\
                DataFlow.beginning_at(port_param_identifier)[0].get_continued_flows(
                    data_flows_considered=DataFlowsConsidered.ONE_PER_NODE_SHORTEST  # == enumeration of Dijkstra tree
                )
            return [df.last_node()
                    for df in data_flows
                    if df.get_accessed_members(include_last_node=False) == ["sender"]]

        elif port_param := self.get_nth_param_or_none(n=1, resolve_params_to_identifiers=False):
            # If the `port` argument is a destructuring ObjectPattern, this makes it a lot easier actually:
            #   - Either one of the destructured attributes is "sender", then return that Identifier.
            #   - Or none of the destructured attributes is "sender", then return the empty list [].
            if port_param.name == "AssignmentPattern":
                # interface AssignmentPattern {
                #     left: Identifier | BindingPattern; // type BindingPattern = ArrayPattern | ObjectPattern;
                #     right: Expression;
                # }
                port_param = port_param.lhs()
            if port_param.name == "ObjectPattern":
                if sender_identifier := port_param.object_expression_get_property_value("sender"):
                    return [sender_identifier]
                else:
                    # An ObjectPattern w/o the "sender" key is equivalent to there being no port parameter at all:
                    return []
            else:
                print(f"[Warning] 'port' parameter of a PortOnMessageListener got destructured into a(n) "
                      f"{port_param.name} (line {port_param.get_line()}, file {port_param.get_file()})")
                return []

        else:
            # No port parameter, PortOnMessageListener only takes 0 or 1 arguments:
            return []

    def get_all_url_identifiers(self) -> List[Node]:
        raise NotImplementedError("todo")
