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
                                    f"cannot be resolved, not even using "
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

    def get_params(self) -> List[Node]:
        """
        Returns a list of all the parameters of this function.
        Note that while any simple parameters will be Identifier Nodes, more complex parameters may also be
        * AssignmentPatterns,
        * ArrayPatterns,
        * ObjectPatterns.
        """
        return self.node.get("params")

    def get_nth_param(self, n: int) -> Node:
        return self.get_params()[n]

    def get_nth_param_or_none(self, n: int) -> Optional[Node]:
        params = self.get_params()
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
