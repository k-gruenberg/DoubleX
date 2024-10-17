from typing import List, Optional, Self

from .node import Node


class FuncError(Exception):
    pass


class Func:
    """
    An abstract representation of a JavaScript function.

    Wraps one of the following three Node types:
    - FunctionDeclaration
    - FunctionExpression
    - ArrowFunctionExpression

    interface FunctionDeclaration {
        id: Identifier | null;
        params: FunctionParameter[];
        body: BlockStatement;
        generator: boolean;
        async: boolean;
        expression: false;
    }

    interface FunctionExpression {
        id: Identifier | null;
        params: FunctionParameter[];
        body: BlockStatement;
        generator: boolean;
        async: boolean;
        expression: boolean;
    }

    interface ArrowFunctionExpression {
        id: Identifier | null;
        params: FunctionParameter[];
        body: BlockStatement | Expression;
        generator: boolean;
        async: boolean;
        expression: false;
    }
    """

    def __init__(self, node: Node, use_df_edges: bool = True):
        """
        `node` may be any of the following:
        * a FunctionDeclaration
        * a FunctionExpression
        * an ArrowFunctionExpression
        * a CallExpression, whose 'callee' is a MemberExpression, whose 'object' is an (Arrow)FunctionExpression
          and whose 'property' is an Identifier named "bind"
          => example: foo(function() {}.bind(this))
          => cf. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function/bind
        * an Identifier referring to a declared function in scope
        * an Identifier referring to a variable in scope referring to a declared function
        * an Identifier referring to a variable in scope to which an (Arrow)FunctionExpression was assigned
          (with an optional '.bind()' being called on it, cf. above)

        When `node` is none of the above, or if identifier resolution fails, a FuncError is thrown!

        Parameters:
            node: the AST/PDG Node representing or pointing to a function
            use_df_edges:  when True, Identifier will only attempt to be resolved using existing data flow edges
                           (this is the default);
                           when False, Node.function_Identifier_get_FunctionDeclaration() will be used instead,
                           this method however may give false positives (as declared functions can be overridden by
                           other identifiers pointing to functions!); therefore:
                           ONLY set this to False if...
                           (a) data flows haven't been generated yet, and,
                           (b) you can live with false positives!
        """
        # (1) Remove any ".bind()":
        if node.name == "CallExpression":
            # interface CallExpression {
            #    callee: Expression | Import;
            #    arguments: ArgumentListElement[];
            # }
            # Example: "(function() {}).bind(this)":
            # [1] [Program] (1 child) <<< None
            # 	[2] [ExpressionStatement] (1 child) <<< body
            # 		[3] [CallExpression] (2 children) <<< expression
            # 			[4] [MemberExpression:"False"] (2 children) <<< callee
            # 				[5] [FunctionExpression::{'generator': False, 'async': False, 'expression': False}] (1 child) <<< object
            # 					[6] [BlockStatement] (0 children) <<< body
            # 				[7] [Identifier:"bind"] (0 children) <<< property
            # 			[8] [ThisExpression] (0 children) <<< arguments
            callee: Node = node.get("callee")[0]  # We don't care about the 'arguments' of the CallExpression!
            if callee.name == "MemberExpression" and callee.get("property")[0].is_identifier_named("bind"):
                node = callee.get("object")[0]
            else:
                raise FuncError(f"CallExpression in line {node.get_line()} isn't a .bind(...) call!")

        # (2) Resolve any Identifiers:
        if node.name == "Identifier":
            if use_df_edges:
                df_parent: Node = node.get_data_flow_parents_in_order_no_split()[-1]
                if df_parent.is_id_of_function_declaration():
                    node = df_parent.get_parent(["FunctionDeclaration"])
                elif df_parent.is_id_of_arrow_function_expression():
                    node = df_parent.get_parent(["FunctionExpression", "ArrowFunctionExpression"])
                elif (df_parent.is_lhs_of_a("VariableDeclarator", allow_missing_rhs=False)
                      or df_parent.is_lhs_of_a("AssignmentExpression", allow_missing_rhs=False)):
                    rhs: Node = df_parent.parent.rhs()  # (guaranteed to succeed because of check above)
                    if rhs.name in ["FunctionExpression", "ArrowFunctionExpression"]:
                        node = rhs
                    else:
                        raise FuncError(f"Identifier '{node.attributes['name']}' (line {node.get_line()}) "
                                        f"was eventually resolved as pointing to a(n) {rhs.name}, which is neither a "
                                        f"FunctionExpression nor an ArrowFunctionExpression!")
                else:
                    raise FuncError(f"Identifier '{node.attributes['name']}' (line {node.get_line()}) "
                                    f"was resolved to an Identifier '{df_parent.attributes['name']}' "
                                    f"(line {df_parent.get_line()}), which is neither the ID of a "
                                    f"FunctionDeclaration/(Arrow)FunctionExpression, "
                                    f"nor the LHS of a VariableDeclarator or AssignmentExpression!")
            else:
                # Attempt to use the Node.function_Identifier_get_FunctionDeclaration() method which does *not*
                #   rely on any existing data flow edges but may also return an incorrect result(!):
                func_decl: Optional[Node] = node.function_Identifier_get_FunctionDeclaration(False)
                # => printing a warning is not necessary, as we're already throwing an Exception (FuncError) in
                #    that case; the caller of Func() will then decide how to handle this FuncError and whether to
                #    print anything:
                if func_decl is None:
                    raise FuncError(f"Identifier '{node.attributes['name']}' (line {node.get_line()}) "
                                    f"cannot be resolved using "
                                    f"Node.function_Identifier_get_FunctionDeclaration()!")
                else:
                    node = func_decl  # WARNING: this might be incorrect !!!

        match node.name:
            case "FunctionDeclaration":
                self.node = node
            case "FunctionExpression":
                self.node = node
            case "ArrowFunctionExpression":
                self.node = node
            case node_name:
                raise FuncError(f"Node [{node.id}] is a '{node_name}', which is not a function!")

    def get(self) -> Node:
        """
        Returns the underlying FunctionDeclaration, FunctionExpression, or ArrowFunctionExpression of this `Func`.
        """
        return self.node

    def is_function_declaration(self) -> bool:
        """
        Returns true if this `Func` represents a FunctionDeclaration.
        Note that exactly one of is_function_declaration(), is_function_expression(), is_arrow_function_expression()
        will return True!
        """
        return self.node.name == "FunctionDeclaration"

    def is_function_expression(self) -> bool:
        """
        Returns true if this `Func` represents a FunctionExpression.
        Note that exactly one of is_function_declaration(), is_function_expression(), is_arrow_function_expression()
        will return True!
        """
        return self.node.name == "FunctionExpression"

    def is_arrow_function_expression(self) -> bool:
        """
        Returns true if this `Func` represents an ArrowFunctionExpression.
        Note that exactly one of is_function_declaration(), is_function_expression(), is_arrow_function_expression()
        will return True!
        """
        return self.node.name == "ArrowFunctionExpression"

    def get_params(self, resolve_params_to_identifiers: bool = False) -> List[Optional[Node]]:
        """
        Returns a list of all the parameters of this function.
        Note that while any simple parameters will be Identifier Nodes, more complex parameters may also be
        * AssignmentPatterns,
        * ArrayPatterns,
        * ObjectPatterns.

        Parameters:
            resolve_params_to_identifiers: for AssignmentPattern parameters, i.e., those with a default value, e.g.,
                                           "x=42" in "function f(x=42)", return the Identifier on the LHS of this
                                            assignment instead of the AssignmentPattern; if the parameter is an
                                            ArrayPattern or ObjectPattern, however, that cannot be resolved into a
                                            single parameter, the returned list will return `None` for that parameter
                                            instead of a Node object; the total length of the returned list will
                                            remain equal to the number of parameters however!

        Returns:
            When resolve_params_to_identifiers=False (default):
              the parameters of this Function as a list of Nodes, these Nodes may be Identifiers, AssignmentPattern,
              ArrayPatterns, or ObjectPatterns.
            When resolve_params_to_identifiers=True:
              the parameters of this Function as a list of Identifier Nodes / None values, all values in the returned
              list will be either an Identifier Node or `None`.
            Either way, the length of the returned list will be the same!
        """
        params = self.node.get("params")

        if resolve_params_to_identifiers:
            params = [param.function_param_get_identifier() for param in params]

        return params

    def get_nth_param(self, n: int, resolve_param_to_identifier: bool = False) -> Node:
        """
        Parameters:
            n: the (0-based) index of the parameter to retrieve; IndexError will be thrown when out of range!!!
            resolve_param_to_identifier: for AssignmentPattern parameters, i.e., those with a default value, e.g.,
                                         "x=42" in "function f(x=42)", return the Identifier on the LHS of this
                                         assignment instead of the AssignmentPattern;
                                         note that when resolve_param_to_identifier=True, this method may throw an
                                         AttributeError if the parameter is an ArrayPattern or ObjectPattern that
                                         cannot be resolved into a single parameter!!!

        Returns:
            the n-th parameter to this Function; will never(!) be None!

        Throws:
            - IndexError when `n` is out of range
            - AttributeError when resolve_param_to_identifier=True but resolving the n-th arg to a single Identifier
              Node failed (this is the case for destructuring function parameters!)
        """
        nth_param = self.node.get("params")[n]

        if resolve_param_to_identifier:
            nth_param = nth_param.function_param_get_identifier()
            if nth_param is None:
                raise AttributeError()

        return nth_param

    def get_all_param_identifiers(self) -> List[Node]:
        """
        Function parameters will usually look like this:
        * function foo(x) {}

        However, they may also look like this:
        * function foo(x=42) {}
        * function foo([x,y]) {}
        * function foo([x,y]=[1,2]) {}
        * function foo({x,y}) {}
        * function foo({x,y}={x:1,y:2}) {}
        * function foo({a:x,b:y}) {}
        * function foo({a:x,b:y}={a:1,b:2}) {}

        This method returns *all* LHS Identifiers of *all* parameters to this function; as a list.
        """
        identifiers: List[Node] = []

        for param in self.get_params():
            identifiers.extend(param.function_param_get_identifiers())

        return identifiers

    def get_param_identifiers(self, n: int) -> List[Node]:
        """
        Function parameters will usually look like this:
        * function foo(x) {}

        However, they may also look like this:
        * function foo(x=42) {}
        * function foo([x,y]) {}
        * function foo([x,y]=[1,2]) {}
        * function foo({x,y}) {}
        * function foo({x,y}={x:1,y:2}) {}
        * function foo({a:x,b:y}) {}
        * function foo({a:x,b:y}={a:1,b:2}) {}

        This method returns *all* LHS Identifiers of the n-th parameter to this function; as a list.
        """
        return self.get_nth_param(n=n).function_param_get_identifiers()

    def get_nth_param_or_none(self,
                              n: int,
                              resolve_params_to_identifiers: bool = False) -> Optional[Node]:
        """
        Returns the n-th parameter of this function (or `None` when this function has no n-th parameter).
        Note that while any simple parameters will be Identifier Nodes, more complex parameters may also be
        * AssignmentPatterns,
        * ArrayPatterns,
        * ObjectPatterns.

        Parameter:
            n: the index of the parameter to get (0-based)
            resolve_params_to_identifiers: whether to attempt to resolve the n-th param into a single(!) identifier;
                                           cf. `resolve_params_to_identifiers` parameter of Func.get_params()

        Returns:
            The n-th parameter of this function (or `None` when this function has no n-th parameter).
            If resolve_params_to_identifiers=False, the returned Node (if not None) may be an Identifier,
                                                    AssignmentPattern, ArrayPattern, or ObjectPattern.
            If resolve_params_to_identifiers=True, either an Identifier or None (when this function has no n-th
                                                   parameter or the n-th parameter is an ArrayPattern or ObjectPattern)
                                                   is returned.
        """
        params = self.get_params(resolve_params_to_identifiers=resolve_params_to_identifiers)
        if n < len(params):
            return params[n]
        else:
            return None

    def get_body(self) -> Node:
        """
        Get the function body.
        For a FunctionDeclaration or FunctionExpression, this is always a BlockStatement.
        For an ArrowFunctionExpression, however, this may *also* be an Expression!
        """
        return self.node.get("body")[0]

    def get_id_node(self) -> Optional[Node]:
        """
        Cf. Func.get_name() but this method returns the Identifier node representing the name of this function, instead
        of the function name as a plain string.

        If `f.get_id_node() is not None`, then `f.get_id_node().attributes['name'] == f.get_name()`.
        """
        return self.node.get("id")[0] if len(self.node.get("id")) > 0 else None

    def get_name(self) -> Optional[str]:
        """
        For FunctionDeclarations and named FunctionExpressions, returns the name of this function as a string.
        For unnamed FunctionExpressions as well as for ArrowFunctionExpressions, this method returns `None`.

        If `f.get_id_node() is not None`, then `f.get_id_node().attributes['name'] == f.get_name()`.
        """
        id_node: Node = self.get_id_node()
        if id_node is None:
            return None
        else:
            return id_node.attributes['name']

    def calls_itself_recursively(self) -> bool:
        """
        Returns True if this function calls itself recursively.

        There are multiple ways a function may call itself recursively:
        1. function f(n) {return n<=1 ? 1 : n*f(n-1)}                  (FunctionDeclarations & FunctionExpressions only)
        2. function f(n) {return n<=1 ? 1 : n*arguments.callee(n-1)}   (FunctionDeclarations & FunctionExpressions only)
        3. [var/let/const] f = (n) => {return n<=1 ? 1 : n*f(n-1);};   (FunctionExpressions  & ArrowFunctionExpressions)
        """

        # *** Ways only FunctionDeclarations and FunctionExpressions may call themselves recursively: ***
        # FunctionDeclaration                                       | FunctionExpression
        # ----------------------------------------------------------|---------------------------------------------------------------
        # function f(n) {return n<=1 ? 1 : n*f(n-1)}                | (function f(n) {return n<=1 ? 1 : n*f(n-1)})(4)
        # function f(n) {return n<=1 ? 1 : n*arguments.callee(n-1)} | (function f(n) {return n<=1 ? 1 : n*arguments.callee(n-1)})(4)

        if self.is_function_declaration() or self.is_function_expression():
            for call_expr in self.get_body().get_all_as_iter("CallExpression"):
                if call_expr.call_expression_get_full_function_name() in [self.get_name(), "arguments.callee"]:
                    return True

        # *** Ways FunctionExpressions & ArrowFunctionExpressions may call themselves recursively: ***
        #     [var/let/const] f = function(n) {return n<=1 ? 1 : n * f(n-1);};
        #     [var/let/const] f = (n) => {return n<=1 ? 1 : n * f(n-1);};

        if self.is_function_expression() or self.is_arrow_function_expression():
            # interface VariableDeclarator {
            #     id: Identifier | BindingPattern;
            #     init: Expression | null;
            # }
            # interface AssignmentExpression {
            #     operator: '=' | '*=' | '**=' | '/=' | '%=' | '+=' | '-=' |
            #               '<<=' | '>>=' | '>>>=' | '&=' | '^=' | '|=';
            #     left: Expression;
            #     right: Expression;
            # }
            if (self.node.is_rhs_of_a("VariableDeclarator") or
                    (self.node.is_rhs_of_a("AssignmentExpression") and self.node.parent.attributes['operator'] == '=')):
                lhs: Node = self.node.parent.lhs()  # Node.is_rhs_of_a() guarantees that #children == 2
                if lhs.name == "Identifier":
                    function_name: str = lhs.attributes['name']
                    for call_expr in self.get_body().get_all_as_iter("CallExpression"):
                        if call_expr.call_expression_get_full_function_name() == function_name:
                            return True

        return False

    def is_immediately_invoked(self) -> bool:
        # interface CallExpression {
        #      callee: Expression | Import;
        #      arguments: ArgumentListElement[];
        # }
        return ((self.is_function_expression() or self.is_arrow_function_expression())
                and self.node.parent is not None
                and self.node.parent.name == "CallExpression"
                and self.node == self.node.parent.get("callee")[0])

    def get_immediate_invocation(self) -> Node:
        """
        Asserts that `self.is_immediately_invoked()`.
        Returns the CallExpression Node of this immediate invocation.
        """
        assert self.is_immediately_invoked()
        return self.node.parent
