from typing import Optional, List

from .node import Node
from .Func import Func, FuncError


class JSClass:  # ToDo: handle ClassExpressions, too
    """
    An abstract representation of a JavaScript class.
    Wraps a ClassDeclaration Node:

    interface ClassDeclaration {
        id: Identifier | null;
        superClass: Identifier | null;
        body: ClassBody;
    }

    Each ClassDeclaration contains MethodDefinitions:

    interface MethodDefinition {
        key: Expression | null;
        computed: boolean;
        value: FunctionExpression | null;
        kind: 'method' | 'constructor';
        static: boolean;
    }
    """

    def __init__(self, node: Node):
        assert node.name == "ClassDeclaration"
        self.node = node

    def get_name(self) -> Optional[str]:
        _id: List[Node] = self.node.get("id")
        if len(_id) == 1:
            return _id[0].attributes['name']
        else:
            return None

    def get_class_body(self) -> Node:
        return self.node.get("body")[0]

    def get_constructor(self):
        raise NotImplementedError("todo")

    def get_method(self, static: bool, method_name: str, return_as_func: bool = False) -> Optional[Node] | Optional[Func]:
        """
        Returns:
            if return_as_func=False: a MethodDefinition Node, or None when no method with `method_name` was found.
            if return_as_func=True: a Func object, or None when no method with `method_name` was found, or when the
                                    MethodDefinition has no FunctionExpression 'value' (actually, I don't know when or
                                    even if that ever happens?)
        """
        method: Optional[Node] = None

        for method_definition in self.get_class_body().get_all_as_iter("MethodDefinition"):
            # interface MethodDefinition {
            #     key: Expression | null;  <---------- Identifier/method name
            #     computed: boolean;
            #     value: FunctionExpression | null;  <---------- parameters and body will be in here
            #     kind: 'method' | 'constructor';  <---------- has to be 'method'
            #     static: boolean;  <---------- has to be false
            # }
            # BEWARE: A ClassDeclaration may contain two methods with the same name,
            #         one static, one non-static!!!
            # BEWARE: A ClassDeclaration may contain two methods with the same name (both static),
            #         the latter will overwrite the former!!! (therefore we cannot(!) break once a match is found!!!)
            if (method_definition.attributes['kind'] == 'method'
                    and method_definition.attributes['static'] == static):
                key: List[Node] = method_definition.get("key")
                if (len(key) == 1
                        and key[0].name == "Identifier"
                        and key[0].attributes['name'] == method_name):
                    method = method_definition
                    # Do *not* break the loop here, there might be a second MethodDefinition with the same name
                    #   overwriting this one!!!

        if method is not None and return_as_func:
            value: List[Node] = method.get("value")
            if len(value) == 1 and value[0].name == "FunctionExpression":
                return Func(value[0])
            else:
                return None

        return method

    def get_static_method(self, method_name: str, return_as_func: bool = False) -> Optional[Node] | Optional[Func]:
        return self.get_method(static=True, method_name=method_name, return_as_func=return_as_func)

    def get_non_static_method(self, method_name: str, return_as_func: bool = False) -> Optional[Node] | Optional[Func]:
        return self.get_method(static=False, method_name=method_name, return_as_func=return_as_func)
