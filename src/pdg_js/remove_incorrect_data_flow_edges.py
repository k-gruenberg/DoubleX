# I'd rather this code didn't need to exist.
# DoubleX sometimes adds incorrect data flow edges though; an example:
#
# (function(t) {
#     !function t() {}   // DoubleX adds exactly 1 data flow: from this "t"...
#     console.log(t);    // ...to this "t" and that data flow is WRONG!
# })(42);
#

from pdg_js.node import Node


def remove_incorrect_data_flow_edges(pdg: Node) -> int:
    data_flow_edges_removed: int = 0

    if pdg.name == "FunctionExpression":
        # interface FunctionExpression {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        #     generator: boolean;
        #     async: boolean;
        #     expression: boolean;
        # }

        block_statement: Node = pdg.get_child("BlockStatement")
        if block_statement is None:
            raise AssertionError(f"FunctionExpression in line {pdg.get_line()} (file {pdg.get_file()}) has no body!")

        # Names of named function expressions are local only to the function body
        #   (they are intended to allow for recursion,
        #   cf. https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Operators/function):
        for func_expr_child in pdg.children:
            if func_expr_child.name == "Identifier":
                for data_dep_child in func_expr_child.data_dep_children:
                    if not data_dep_child.extremity.is_inside(block_statement):
                        # There is a data flow from the identifier or a parameter of a FunctionExpression to *outside*
                        #   the FunctionExpression's body (and therefore scope), remove it:
                        data_flow_edges_removed += func_expr_child.remove_data_dependency(
                            extremity=data_dep_child.extremity)

    # Note that the DF edge from the LHS to the RHS in "x=x" might actually be needed when the "x=x" occurs inside a
    #   loop or inside a function that is repeatedly executed!

    return data_flow_edges_removed +\
        sum(remove_incorrect_data_flow_edges(child) for child in pdg.children)
