import unittest
import os

from src.pdg_js.add_missing_data_flow_edges import *
# from node_unittest2 import generate_pdg


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


def generate_ast(code):
    return generate_pdg(code, ast_only=True)


class TestAddMissingDataFlowEdges(unittest.TestCase):
    def test_add_basic_data_flow_edges(self):
        # Examples from doc comment of add_basic_data_flow_edges():

        code = """
        let x = foo();  // [id1]
        bar(x);         // [id2]
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

        code = """
        let x = 42;
        x = foo();   // [id1]
        bar(x);      // [id2]
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

        code = """
        x = 1
        y = x
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

        code = """
        function foo({x:a}) {
            console.log(a);
        }
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

        code = """
        function foo(x=1) {
            console.log(x);
        }
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

        code = """
        (function(t) {
            !function t() {}
            console.log(t);
        })(42);
        """
        ast = generate_ast(code)
        print(ast)
        self.assertEqual(1, add_basic_data_flow_edges(ast, debug=True))

    def test_add_basic_data_flow_edges_identifier_of_interest(self): # todo:
        code = """
        """

    def test_add_missing_data_flow_edges_function_parameters(self):
        # Basic example:
        code = """
        function foo(z) {
            console.log(z);
        }
        """
        ast = generate_ast(code)
        print(ast)
        # [59] [Program] (1 child)
        # 	[60] [FunctionDeclaration] (3 children)
        # 		[61] [Identifier:"foo"] (0 children)
        # 		[62] [Identifier:"z"] (0 children)
        # 		[63] [BlockStatement] (1 child)
        # 			[64] [ExpressionStatement] (1 child)
        # 				[65] [CallExpression] (2 children)
        # 					[66] [MemberExpression:"False"] (2 children)
        # 						[67] [Identifier:"console"] (0 children)
        # 						[68] [Identifier:"log"] (0 children)
        # 					[69] [Identifier:"z"] (0 children)
        self.assertEqual(1, add_missing_data_flow_edges_function_parameters(ast))
        function_declaration: Node = ast.get_child("FunctionDeclaration")
        first_z: Node = function_declaration.children[1]
        second_z: Node = (function_declaration
                          .get_child("BlockStatement")
                          .get_child("ExpressionStatement")
                          .get_child("CallExpression")
                          .get_child("Identifier"))
        self.assertEqual("z", first_z.attributes['name'])
        self.assertEqual("z", second_z.attributes['name'])
        self.assertEqual(1, len(first_z._data_dep_children))
        self.assertEqual(second_z, first_z._data_dep_children[0].extremity)
        self.assertEqual(0, len(second_z._data_dep_children))

        # Test ObjectPatterns as function parameters:
        code = """
        function foo({x:a}) {
            console.log(a);
        }
        """
        ast = generate_ast(code)
        print(ast)
        # [21] [Program] (1 child)
        # 	[22] [FunctionDeclaration] (3 children)
        # 		[23] [Identifier:"foo"] (0 children)
        # 		[24] [ObjectPattern] (1 child)
        # 			[25] [Property] (2 children)
        # 				[26] [Identifier:"x"] (0 children)
        # 				[27] [Identifier:"a"] (0 children)
        # 		[28] [BlockStatement] (1 child)
        # 			[29] [ExpressionStatement] (1 child)
        # 				[30] [CallExpression] (2 children)
        # 					[31] [MemberExpression:"False"] (2 children)
        # 						[32] [Identifier:"console"] (0 children)
        # 						[33] [Identifier:"log"] (0 children)
        # 					[34] [Identifier:"a"] (0 children)
        self.assertEqual(1, add_missing_data_flow_edges_function_parameters(ast))
        function_declaration: Node = ast.get_child("FunctionDeclaration")
        first_a: Node = function_declaration.get_child("ObjectPattern").get_child("Property").children[1]
        second_a: Node = (function_declaration.get_child("BlockStatement").get_child("ExpressionStatement")
                          .get_child("CallExpression").get_child("Identifier"))
        self.assertEqual("a", first_a.attributes['name'])
        self.assertEqual("a", second_a.attributes['name'])
        self.assertEqual(1, len(first_a._data_dep_children))
        self.assertEqual(second_a, first_a._data_dep_children[0].extremity)
        self.assertEqual(0, len(second_a._data_dep_children))

        # Test function parameters with default values:
        code = """
        function foo(x=1) {
            console.log(x);
        }
        """
        ast = generate_ast(code)
        print(ast)
        # [30] [Program] (1 child)
        # 	[31] [FunctionDeclaration] (3 children)
        # 		[32] [Identifier:"foo"] (0 children)
        # 		[33] [AssignmentPattern] (2 children)
        # 			[34] [Identifier:"x"] (0 children)
        # 			[35] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 		[36] [BlockStatement] (1 child)
        # 			[37] [ExpressionStatement] (1 child)
        # 				[38] [CallExpression] (2 children)
        # 					[39] [MemberExpression:"False"] (2 children)
        # 						[40] [Identifier:"console"] (0 children)
        # 						[41] [Identifier:"log"] (0 children)
        # 					[42] [Identifier:"x"] (0 children)
        self.assertEqual(1, add_missing_data_flow_edges_function_parameters(ast))
        function_declaration: Node = ast.get_child("FunctionDeclaration")
        first_x: Node = function_declaration.get_child("AssignmentPattern").children[0]
        second_x: Node = (function_declaration.get_child("BlockStatement").get_child("ExpressionStatement")
                          .get_child("CallExpression").get_child("Identifier"))
        self.assertEqual("x", first_x.attributes['name'])
        self.assertEqual("x", second_x.attributes['name'])
        self.assertEqual(1, len(first_x._data_dep_children))
        self.assertEqual(second_x, first_x._data_dep_children[0].extremity)
        self.assertEqual(0, len(second_x._data_dep_children))

        # Test function expressions:
        code = """
        (function(t) {
            !function t() {}
            console.log(t);
        })(42);
        """
        # => this example is inspired by real-world code from the "ClassLink OneClick Extension", version 10.6,
        #    extension ID jgfbgkjjlonelmpenhpfeeljjlcgnkpe
        ast = generate_ast(code)
        # [44] [Program] (1 child)
        # 	[45] [ExpressionStatement] (1 child)
        # 		[46] [CallExpression] (2 children)
        # 			[47] [FunctionExpression::{'generator': False, 'async': False, 'expression': False}] (2 children)
        # 				[48] [Identifier:"t"] (0 children)
        # 				[49] [BlockStatement] (2 children)
        # 					[50] [ExpressionStatement] (1 child)
        # 						[51] [UnaryExpression:"!"] (1 child)
        # 							[52] [FunctionExpression::{'generator': False, 'async': False, 'expression': False}] (2 children)
        # 								[53] [Identifier:"t"] (0 children)
        # 								[54] [BlockStatement] (0 children)
        # 					[55] [ExpressionStatement] (1 child)
        # 						[56] [CallExpression] (2 children)
        # 							[57] [MemberExpression:"False"] (2 children)
        # 								[58] [Identifier:"console"] (0 children)
        # 								[59] [Identifier:"log"] (0 children)
        # 							[60] [Identifier:"t"] (0 children)
        # 			[61] [Literal::{'raw': '42', 'value': 42}] (0 children)
        self.assertEqual(1, add_missing_data_flow_edges_function_parameters(ast))
        func_expr: Node = (ast
                           .get_child("ExpressionStatement")
                           .get_child("CallExpression")
                           .get_child("FunctionExpression"))
        first_t: Node = func_expr.get_child("Identifier")
        block_statement: Node = func_expr.get_child("BlockStatement")
        second_t: Node = (block_statement.children[0]
                          .get_child("UnaryExpression")
                          .get_child("FunctionExpression")
                          .get_child("Identifier"))
        third_t: Node = block_statement.children[1].get_child("CallExpression").get_child("Identifier")
        self.assertEqual("t", first_t.attributes['name'])
        self.assertEqual("t", second_t.attributes['name'])
        self.assertEqual("t", third_t.attributes['name'])
        self.assertEqual(1, len(first_t._data_dep_children))
        self.assertEqual(third_t, first_t._data_dep_children[0].extremity)
        self.assertEqual(0, len(second_t._data_dep_children))
        self.assertEqual(0, len(third_t._data_dep_children))

        # Test handling of identifier overshadowing:
        code = """
        function foo(w) { // ...and not this one!
            function bar(w) { // ...refers to this x...
                console.log(w); // This x...
            }
        }
        """
        ast = generate_ast(code)
        print(ast)
        # [17] [Program] (1 child)
        # 	[18] [FunctionDeclaration] (4 children)
        # 		[22] [FunctionDeclaration] (3 children)
        # 			[23] [Identifier:"bar"] (0 children)
        # 			[24] [Identifier:"x"] (0 children)
        # 			[25] [BlockStatement] (1 child)
        # 				[26] [ExpressionStatement] (1 child)
        # 					[27] [CallExpression] (2 children)
        # 						[28] [MemberExpression:"False"] (2 children)
        # 							[29] [Identifier:"console"] (0 children)
        # 							[30] [Identifier:"log"] (0 children)
        # 						[31] [Identifier:"x"] (0 children)
        # 		[19] [Identifier:"foo"] (0 children)
        # 		[20] [Identifier:"x"] (0 children)
        # 		[21] [BlockStatement] (0 children)
        self.assertEqual(1, add_missing_data_flow_edges_function_parameters(ast))
        ws: List[Node] = [id_ for id_ in ast.get_all("Identifier") if id_.attributes['name'] == "w"]
        ws.sort(key=lambda w: w.code_occurrence())
        first_w: Node = ws[0]
        second_w: Node = ws[1]
        third_w: Node = ws[2]
        self.assertEqual("w", first_w.attributes['name'])
        self.assertEqual("w", second_w.attributes['name'])
        self.assertEqual("w", third_w.attributes['name'])
        self.assertEqual(1, len(second_w._data_dep_children))
        self.assertEqual(third_w, second_w._data_dep_children[0].extremity)
        self.assertEqual(0, len(first_w._data_dep_children))
        self.assertEqual(0, len(third_w._data_dep_children))

    def test_add_missing_data_flow_edges_function_returns(self):
        # Case (A):
        #   relies on existing DF edges as it calls .data_dep_children():
        code = """
        let x = 42;
        function foo() {
            return x; // --data--> y
        }
        let y = foo();
        """

        ast = generate_ast(code)
        print(f"Before: {ast}")
        add_missing_data_flow_edges_declarations_and_assignments_RTL(ast)  # required for the next call to work!
        self.assertEqual(1, add_missing_data_flow_edges_function_returns(ast))
        print(f"After: {ast}")

        # Test identifier_of_interest_in:
        ast = generate_ast(code)
        y = ast.get_identifier_by_name("y")
        print(f"Before: {ast}")
        add_missing_data_flow_edges_declarations_and_assignments_RTL(ast)
        self.assertEqual(1, add_missing_data_flow_edges_function_returns(ast, identifier_of_interest_in=y))
        print(f"After: {ast}")

        # Test identifier_of_interest_out:
        ast = generate_ast(code)
        x2 = ast.get_all_identifiers_by_name("x")[1]
        print(f"Before: {ast}")
        add_missing_data_flow_edges_declarations_and_assignments_RTL(ast)
        self.assertEqual(1, add_missing_data_flow_edges_function_returns(ast, identifier_of_interest_out=x2))
        print(f"After: {ast}")

    def test_add_missing_data_flow_edges_IIFE_returns(self):
        # Case (B):
        #   does not rely on any existing DF edges:
        code = """
        let b = function() {return a;}();
        """
        ast = generate_ast(code)
        print(f"Before: {ast}")
        self.assertEqual(1, add_missing_data_flow_edges_IIFE_returns(ast))
        print(f"After: {ast}")

    def test_add_missing_data_flow_edges_standard_library_functions(self):
        # ##### ##### ##### ##### ##### Object.assign(): ##### ##### ##### ##### #####
        # Example from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/assign:
        code = """
        const target = { a: 1, b: 2 };
        const source = { b: 4, c: 5 };    
        const returnedTarget = Object.assign(target, source);   
        // console.log(target); // Expected output: Object { a: 1, b: 4, c: 5 }  
        // console.log(returnedTarget === target); // Expected output: true
        """
        ast = generate_ast(code)
        print(f"Before: {ast}")
        # add_missing_data_flow_edges_standard_library_functions() shall add a DF edge source --data--> target
        self.assertEqual(1, add_missing_data_flow_edges_standard_library_functions(ast))
        print(f"After: {ast}")
        all_df_edges = ast.get_all_data_flow_edges()
        print(all_df_edges)
        self.assertEqual(1, len(all_df_edges))
        self.assertEqual("source", all_df_edges[0][0].attributes['name'])
        self.assertEqual("target", all_df_edges[0][1].attributes['name'])

        # ##### ##### ##### ##### ##### Object.defineProperty(): ##### ##### ##### ##### #####
        # Example from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/defineProperty:
        code = """
        const object1 = {};
        Object.defineProperty(object1, 'property'+'1', {
          value: forty_two,
          writable: false,
        });
        // object1.property1 = 77; // Throws an error in strict mode    
        // console.log(object1.property1); // Expected output: 42
        """
        ast = generate_ast(code)
        print(f"Before: {ast}")
        # add_missing_data_flow_edges_standard_library_functions() shall add a DF edge forty_two --data--> object1
        self.assertEqual(1, add_missing_data_flow_edges_standard_library_functions(ast))
        print(f"After: {ast}")
        all_df_edges = ast.get_all_data_flow_edges()
        print(all_df_edges)
        self.assertEqual(1, len(all_df_edges))
        self.assertEqual("forty_two", all_df_edges[0][0].attributes['name'])
        self.assertEqual("object1", all_df_edges[0][1].attributes['name'])

        # ##### ##### ##### ##### ##### Object.defineProperties(): ##### ##### ##### ##### #####
        # Example from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/defineProperties:
        code = """
        const object1 = {};
        Object.defineProperties(object1, {
          property1: {
            value: forty_two,
            writable: true,
          },
          property2: {},
        });
        // console.log(object1.property1); // Expected output: 42
        """
        ast = generate_ast(code)
        print(f"Before: {ast}")
        # add_missing_data_flow_edges_standard_library_functions() shall add a DF edge forty_two --data--> object1
        self.assertEqual(1, add_missing_data_flow_edges_standard_library_functions(ast))
        print(f"After: {ast}")
        all_df_edges = ast.get_all_data_flow_edges()
        print(all_df_edges)
        self.assertEqual(1, len(all_df_edges))
        self.assertEqual("forty_two", all_df_edges[0][0].attributes['name'])
        self.assertEqual("object1", all_df_edges[0][1].attributes['name'])

    def test_add_missing_data_flow_edges_call_expressions(self):
        # ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### #####
        # ##### ##### ##### ##### ##### foo.bar() type call expressions: ##### ##### ##### ##### #####
        # ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### #####

        code = """
        function sink(x) {console.log(x);} 
        
        function bar(p, q) {
            sink(p);
        }
        
        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            foo(a, b) {
                bar(a, b);
            }
        }
        
        const c = new C(12, 34);
        const data = "data";
        c.foo(data);  // prints "data" // too few arguments supplied
        c.foo(data, 42); // prints "data"
        c['f'+'oo'](data, 42, 43);  // prints "data" // too many arguments supplied
        """
        pdg = generate_pdg(code)
        # Test whether each `data` identifier flows into each `p` identifier:
        for data in pdg.get_all_identifiers_by_name("data"):
            for p in pdg.get_all_identifiers_by_name("p"):
                print(f"data = {data} (line {data.get_line()})")
                print(f"p = {p} (line {p.get_line()})")
                self.assertIn(p, data.get_all_data_flow_descendents(sort=False))

        # BEWARE: A ClassDeclaration may contain two methods with the same name,
        #         one static, one non-static!!!
        code = """
        function sink(x) {console.log(x);} 
        
        function bar(p, q) {
            sink(p);
        }

        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            static foo(a, b) { // This static method is NEVER referred to!!!
                return a+b;
            }
            foo(a, b) {
                bar(a, b);
            }
        }

        const c = new C(12, 34);
        const data = "data";
        c.foo(data, 42); // prints "data"
        """
        pdg = generate_pdg(code)
        # Test whether each `data` identifier flows into each `p` identifier:
        for data in pdg.get_all_identifiers_by_name("data"):
            for p in pdg.get_all_identifiers_by_name("p"):
                self.assertIn(p, data.get_all_data_flow_descendents(sort=False))

        # The same example, with the order of methods swapped:
        code = """
        function sink(x) {console.log(x);}
        
        function bar(p, q) {
            sink(p);
        }

        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            foo(a, b) {
                bar(a, b);
            }
            static foo(a, b) { // This static method is NEVER referred to!!!
                return a+b;
            }
        }

        const c = new C(12, 34);
        const data = "data";
        c.foo(data, 42); // prints "data"
        """
        pdg = generate_pdg(code)
        # Test whether each `data` identifier flows into each `p` identifier:
        for data in pdg.get_all_identifiers_by_name("data"):
            for p in pdg.get_all_identifiers_by_name("p"):
                self.assertIn(p, data.get_all_data_flow_descendents(sort=False))

        # BEWARE: A ClassDeclaration may contain two methods with the same name (both non-static),
        #         the latter will overwrite the former!!!
        code = """
        function sink(x) {console.log(x);}
        
        function bar(p, q) {
            sink(p);
        }

        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            foo(a, b) { // This method is NEVER referred to as it is overwritten below!!!
                return a+b;
            }
            foo(a, b) {
                bar(a, b);
            }
        }

        const c = new C(12, 34);
        const data = "data";
        c.foo(data, 42); // prints "data"
        """
        pdg = generate_pdg(code)
        # Test whether each `data` identifier flows into each `p` identifier:
        for data in pdg.get_all_identifiers_by_name("data"):
            for p in pdg.get_all_identifiers_by_name("p"):
                self.assertIn(p, data.get_all_data_flow_descendents(sort=False))

        # ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### #####
        # ##### ##### ##### ##### ##### new Foo().bar() type call expressions: ##### ##### ##### ##### #####
        # ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### ##### #####

        code = """
        function sink(x) {console.log(x);} 

        function bar(p, q) {
            sink(p);
        }

        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            foo(a, b) {
                bar(a, b);
            }
        }

        const data = "data";
        new C(12, 34).foo(data);  // prints "data" // too few arguments supplied
        new C(12, 34).foo(data, 42); // prints "data"
        new C(12, 34)['f'+'oo'](data, 42, 43);  // prints "data" // too many arguments supplied
        """
        pdg = generate_pdg(code)
        # Test whether each `data` identifier flows into each `p` identifier:
        for data in pdg.get_all_identifiers_by_name("data"):
            for p in pdg.get_all_identifiers_by_name("p"):
                self.assertIn(p, data.get_all_data_flow_descendents(sort=False))