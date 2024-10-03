import unittest
import os

from src.pdg_js.Func import Func
from src.pdg_js.node import Node


os.environ['PARSER'] = "espree"
os.environ['SOURCE_TYPE'] = "module"
os.environ['DEBUG'] = "yes"
os.environ['TIMEOUT'] = "600"


def generate_pdg(code: str, ast_only=False) -> Node:
    res_dict = dict()
    benchmarks = res_dict['benchmarks'] = dict()

    return Node.pdg_from_string(
        js_code=code,
        benchmarks=benchmarks,
        add_my_data_flows=not ast_only,
    )


class TestFunc(unittest.TestCase):
    def test_func_declarations(self):
        for code in [
            """
            function print_square(x) {
                console.log(x**2);
            } 
            [1,2,3,4,5].forEach(print_square);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            [foo, bar] = [print_square, 42];
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            foo = 42;
            foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            foo = 42;
            [foo, bar] = [print_square, 42];
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            var foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            var foo = 42;
            foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            let foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            let foo = 42;
            foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """,

            """
            function print_square(x) {
                console.log(x**2);
            }
            const foo = print_square;
            [1,2,3,4,5].forEach(foo);
            """
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            for_each: Node = pdg.get_identifier_by_name("forEach")
            call_expr: Node = for_each.get_ancestor(["CallExpression"])
            arg: Node = call_expr.get("arguments")[0]
            func: Func = Func(arg)
            self.assertEqual(func.get().name, "FunctionDeclaration")
            self.assertTrue(func.is_function_declaration())
            self.assertFalse(func.is_function_expression())
            self.assertFalse(func.is_arrow_function_expression())
            self.assertEqual(func.get_name(), "print_square")
            self.assertEqual(func.get_id_node().attributes['name'], "print_square")
            self.assertEqual(len(func.get_params()), 1)
            self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
            self.assertIsNone(func.get_nth_param_or_none(1))
            self.assertIsNotNone(func.get_body())
            self.assertFalse(func.calls_itself_recursively())

    def test_overshadowing(self):
        code = """
        function compute_and_print(a,b) {
                console.log(x/2);
        }
        function main() {
            function compute_and_print(x) {
                console.log(x**2);
            } 
            [1,2,3,4,5].forEach(compute_and_print);
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        for_each: Node = pdg.get_identifier_by_name("forEach")
        call_expr: Node = for_each.get_ancestor(["CallExpression"])
        arg: Node = call_expr.get("arguments")[0]
        func: Func = Func(arg)
        self.assertEqual(func.get().name, "FunctionDeclaration")
        self.assertTrue(func.is_function_declaration())
        self.assertFalse(func.is_function_expression())
        self.assertFalse(func.is_arrow_function_expression())
        self.assertEqual(func.get_name(), "compute_and_print")
        self.assertEqual(func.get_id_node().attributes['name'], "compute_and_print")
        self.assertEqual(len(func.get_params()), 1)
        self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
        self.assertIsNone(func.get_nth_param_or_none(1))
        self.assertIsNotNone(func.get_body())
        self.assertFalse(func.calls_itself_recursively())

    def test_func_expressions(self):
        for code in [
            """
            [1,2,3,4,5].forEach(function print_square(x) { console.log(x**2); });
            """,

            """
            foo = function print_square(x) { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            var foo = function print_square(x) { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            let foo = function print_square(x) { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            const foo = function print_square(x) { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            for_each: Node = pdg.get_identifier_by_name("forEach")
            call_expr: Node = for_each.get_ancestor(["CallExpression"])
            arg: Node = call_expr.get("arguments")[0]
            func: Func = Func(arg)
            self.assertEqual(func.get().name, "FunctionExpression")
            self.assertFalse(func.is_function_declaration())
            self.assertTrue(func.is_function_expression())
            self.assertFalse(func.is_arrow_function_expression())
            self.assertEqual(func.get_name(), "print_square")
            self.assertEqual(func.get_id_node().attributes['name'], "print_square")
            self.assertEqual(len(func.get_params()), 1)
            self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
            self.assertIsNone(func.get_nth_param_or_none(1))
            self.assertIsNotNone(func.get_body())
            self.assertFalse(func.calls_itself_recursively())

        # Also test a FunctionExpression w/o a name:
        code = """
        [1,2,3,4,5].forEach(function(x) { console.log(x**2); });
        """
        pdg = generate_pdg(code)
        print(pdg)
        for_each: Node = pdg.get_identifier_by_name("forEach")
        call_expr: Node = for_each.get_ancestor(["CallExpression"])
        arg: Node = call_expr.get("arguments")[0]
        func: Func = Func(arg)
        self.assertEqual(func.get().name, "FunctionExpression")
        self.assertFalse(func.is_function_declaration())
        self.assertTrue(func.is_function_expression())
        self.assertFalse(func.is_arrow_function_expression())
        self.assertIsNone(func.get_name())
        self.assertIsNone(func.get_id_node())
        self.assertEqual(len(func.get_params()), 1)
        self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
        self.assertIsNone(func.get_nth_param_or_none(1))
        self.assertIsNotNone(func.get_body())
        self.assertFalse(func.calls_itself_recursively())

    def test_arrow_func_expressions(self):
        for code in [
            """
            [1,2,3,4,5].forEach((x) => { console.log(x**2); });
            """,

            """
            foo = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            var foo = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            let foo = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,

            """
            const foo = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(foo);
            """,
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            for_each: Node = pdg.get_identifier_by_name("forEach")
            call_expr: Node = for_each.get_ancestor(["CallExpression"])
            arg: Node = call_expr.get("arguments")[0]
            func: Func = Func(arg)
            self.assertEqual(func.get().name, "ArrowFunctionExpression")
            self.assertFalse(func.is_function_declaration())
            self.assertFalse(func.is_function_expression())
            self.assertTrue(func.is_arrow_function_expression())
            self.assertIsNone(func.get_name())
            self.assertEqual(len(func.get_params()), 1)
            self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
            self.assertIsNone(func.get_nth_param_or_none(1))
            self.assertIsNotNone(func.get_body())
            self.assertFalse(func.calls_itself_recursively())

    def test_bind(self):
        for code in [
            # FunctionDeclaration:
            """
            function print_square(x) {
                console.log(x**2);
            } 
            [1,2,3,4,5].forEach(print_square.bind(this));
            """,

            # FunctionExpression:
            """
            [1,2,3,4,5].forEach((function(x) { console.log(x**2); }).bind(this));
            """,

            # Named FunctionExpression:
            """
            [1,2,3,4,5].forEach((function print_square(x) { console.log(x**2); }).bind(this));
            """,

            # ArrowFunctionExpression:
            """
            [1,2,3,4,5].forEach(((x) => { console.log(x**2); }).bind(this));
            """,

            # Identifier:
            """
            f = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            f = function (x) { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            var f = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            var f = function (x) { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            let f = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            let f = function (x) { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            const f = (x) => { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
            """
            const f = function (x) { console.log(x**2); };
            [1,2,3,4,5].forEach(f.bind(this));
            """,
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            for_each: Node = pdg.get_identifier_by_name("forEach")
            call_expr: Node = for_each.get_ancestor(["CallExpression"])
            arg: Node = call_expr.get("arguments")[0]
            func: Func = Func(arg)
            self.assertEqual(len(func.get_params()), 1)
            self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
            self.assertIsNone(func.get_nth_param_or_none(1))
            self.assertIsNotNone(func.get_body())
            self.assertFalse(func.calls_itself_recursively())

    def test_calls_itself_recursively(self):
        for code in [
            # FunctionDeclarations that call themselves recursively:
            """
            function factorial(n) {
                    return n<=1 ? 1 : n * factorial(n-1);
            } 
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * arguments.callee(n-1);
            } 
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * factorial(n-1);
            }
            fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * arguments.callee(n-1);
            }
            fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * factorial(n-1);
            }
            var fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * arguments.callee(n-1);
            }
            var fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * factorial(n-1);
            }
            let fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * arguments.callee(n-1);
            }
            let fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * factorial(n-1);
            }
            const fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            """
            function factorial(n) {
                    return n<=1 ? 1 : n * arguments.callee(n-1);
            }
            const fun = factorial;
            console.log([1,2,3,4,5].map(fun));
            """,

            # FunctionExpressions that call themselves recursively:
            """
            factorial = function(n) {return n<=1 ? 1 : n * arguments.callee(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            var factorial = function(n) {return n<=1 ? 1 : n * arguments.callee(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            let factorial = function(n) {return n<=1 ? 1 : n * arguments.callee(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            const factorial = function(n) {return n<=1 ? 1 : n * arguments.callee(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            factorial = function(n) {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            var factorial = function(n) {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            let factorial = function(n) {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            const factorial = function(n) {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            # ArrowFunctionExpressions that call themselves recursively:
            """
            factorial = (n) => {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            var factorial = (n) => {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            let factorial = (n) => {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """,

            """
            const factorial = (n) => {return n<=1 ? 1 : n * factorial(n-1);};
            console.log([1,2,3,4,5].map(factorial));
            """
            # Note: ArrowFunctionExpressions do NOT(!) support arguments.callee !!!
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            map_node: Node = pdg.get_identifier_by_name("map")
            call_expr: Node = map_node.get_ancestor(["CallExpression"])
            arg: Node = call_expr.get("arguments")[0]
            func: Func = Func(arg)
            self.assertEqual(len(func.get_params()), 1)
            self.assertEqual(func.get_nth_param(0).attributes['name'], "n")
            self.assertIsNone(func.get_nth_param_or_none(1))
            self.assertIsNotNone(func.get_body())
            self.assertTrue(func.calls_itself_recursively())  # !!!!!

    def test_not_only_func_declarations_are_considered(self):
        code = """
        function compute_and_print(a,b) {
                console.log(x/2);
        }
        function main() {
            let compute_and_print = (x) => {console.log(x**2);}; 
            [1,2,3,4,5].forEach(compute_and_print);
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        for_each: Node = pdg.get_identifier_by_name("forEach")
        call_expr: Node = for_each.get_ancestor(["CallExpression"])
        arg: Node = call_expr.get("arguments")[0]
        func: Func = Func(arg)
        self.assertEqual(func.get().name, "ArrowFunctionExpression")
        self.assertFalse(func.is_function_declaration())
        self.assertFalse(func.is_function_expression())
        self.assertTrue(func.is_arrow_function_expression())
        self.assertIsNone(func.get_name())
        self.assertIsNone(func.get_id_node())
        self.assertEqual(len(func.get_params()), 1)
        self.assertEqual(func.get_nth_param(0).attributes['name'], "x")
        self.assertIsNone(func.get_nth_param_or_none(1))
        self.assertIsNotNone(func.get_body())
        self.assertFalse(func.calls_itself_recursively())

    def test_use_df_edges(self):
        code = """
        function f(x) {
            return x/2;
        }
        function main() {
            let f = (x) => x**2;
            console.log([1,2,3,4,5].map(f));
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        map_node: Node = pdg.get_identifier_by_name("map")
        call_expr: Node = map_node.get_ancestor(["CallExpression"])
        arg: Node = call_expr.get("arguments")[0]
        func: Func = Func(arg, use_df_edges=True)  # = default
        self.assertTrue(func.is_arrow_function_expression())
        func: Func = Func(arg, use_df_edges=False)
        self.assertTrue(func.is_function_declaration())  # = incorrect!

    def test_short_flow(self):
        code = """
        x = function (a,b,c) {}
        """
        pdg = generate_pdg(code)
        print(pdg)
        x: Node = pdg.get_identifier_by_name("x")
        func: Func = Func(x)
        self.assertEqual(func.get().name, "FunctionExpression")
        self.assertTrue(func.is_function_expression())

        self.assertEqual(len(func.get_params()), 3)
        self.assertEqual(func.get_nth_param(0).attributes['name'], "a")
        self.assertEqual(func.get_nth_param(1).attributes['name'], "b")
        self.assertEqual(func.get_nth_param(2).attributes['name'], "c")
        self.assertIsNotNone(func.get_body())
        self.assertFalse(func.calls_itself_recursively())


if __name__ == '__main__':
    unittest.main()
