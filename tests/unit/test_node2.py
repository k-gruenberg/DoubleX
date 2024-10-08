import os
import unittest
import math
from typing import List

from src.pdg_js.node import Node
from src.pdg_js.StaticEvalException import StaticEvalException

# from add_missing_data_flow_edges_unittest import generate_ast

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


def expr(expr_code: str) -> Node:
    return generate_pdg(expr_code).get_child("ExpressionStatement").get("expression")[0]


class TestNodeClass2(unittest.TestCase):
    def test_get(self):
        # Examples from doc comment of Node.get():

        # interface MemberExpression {
        #     object: Expression;
        #     property: Expression;
        # }
        pdg = generate_pdg("x.y")
        print(pdg)
        # [1] [Program] (1 child) <<< None
        # 	[2] [ExpressionStatement] (1 child) <<< body
        # 		[3] [MemberExpression:"False"] (2 children) <<< expression
        # 			[4] [Identifier:"x"] (0 children) <<< object
        # 			[5] [Identifier:"y"] (0 children) <<< property
        member_expr = pdg.get_child("ExpressionStatement").get_child("MemberExpression")
        self.assertEqual("x", member_expr.get("object")[0].attributes['name'])
        self.assertEqual("y", member_expr.get("property")[0].attributes['name'])

        # interface AssignmentExpression {
        #     left: Expression;
        #     right: Expression;
        # }
        pdg = generate_pdg("x=y")
        print(pdg)
        # [34] [Program] (1 child) <<< None
        # 	[35] [ExpressionStatement] (1 child) <<< body
        # 		[36] [AssignmentExpression:"="] (2 children) <<< expression
        # 			[37] [Identifier:"x"] (0 children) <<< left
        # 			[38] [Identifier:"y"] (0 children) <<< right --data--> [37]
        assignment_expr = pdg.get_child("ExpressionStatement").get_child("AssignmentExpression")
        self.assertEqual("x", assignment_expr.get("left")[0].attributes['name'])
        self.assertEqual("y", assignment_expr.get("right")[0].attributes['name'])

        # interface FunctionDeclaration {
        #     id: Identifier | null;
        #     params: FunctionParameter[];
        #     body: BlockStatement;
        # }
        pdg = generate_pdg("function foo(x,y) {return x;}")
        print(pdg)
        func_decl = pdg.get_child("FunctionDeclaration")
        self.assertEqual("foo", func_decl.get("id")[0].attributes['name'])
        self.assertEqual(["x", "y"], [param.attributes['name'] for param in func_decl.get("params")])
        self.assertEqual(["BlockStatement"], [body.name for body in func_decl.get("body")])

    def test_is_data_flow_equivalent_identifier(self):
        pdg = generate_pdg("x = y; if (x == 1 || x == 2) {}")
        print(pdg)
        # [1] [Program] (2 children)
        # 	[2] [ExpressionStatement] (1 child)
        # 		[3] [AssignmentExpression:"="] (2 children)
        # 			[4] [Identifier:"x"] (0 children) --data--> [9] --data--> [12]
        # 			[5] [Identifier:"y"] (0 children) --data--> [4]
        # 	[6] [IfStatement] (2 children) --True--> [14]
        # 		[7] [LogicalExpression:"||"] (2 children)
        # 			[8] [BinaryExpression:"=="] (2 children)
        # 				[9] [Identifier:"x"] (0 children)
        # 				[10] [Literal:"1"] (0 children)
        # 			[11] [BinaryExpression:"=="] (2 children)
        # 				[12] [Identifier:"x"] (0 children)
        # 				[13] [Literal:"2"] (0 children)
        # 		[14] [BlockStatement] (0 children)
        x1 = pdg.get_child("ExpressionStatement").get_child("AssignmentExpression").children[0]
        x2 = pdg.get_child("IfStatement").get_child("LogicalExpression").children[0].children[0]
        x3 = pdg.get_child("IfStatement").get_child("LogicalExpression").children[1].children[0]
        self.assertNotEqual(x2, x3)
        self.assertTrue(x2.is_data_flow_equivalent_identifier(x3))
        self.assertTrue(x3.is_data_flow_equivalent_identifier(x2))
        self.assertTrue(x2.is_data_flow_equivalent_identifier(x3, max_depth=2))
        self.assertTrue(x3.is_data_flow_equivalent_identifier(x2, max_depth=2))
        self.assertTrue(x2.is_data_flow_equivalent_identifier(x3, max_depth=1))
        self.assertTrue(x3.is_data_flow_equivalent_identifier(x2, max_depth=1))
        self.assertFalse(x2.is_data_flow_equivalent_identifier(x3, max_depth=0))
        self.assertFalse(x3.is_data_flow_equivalent_identifier(x2, max_depth=0))

    def test_member_expression_to_string(self):
        pdg = generate_pdg("foo.bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar")

        pdg = generate_pdg("foo['bar']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar")

        pdg = generate_pdg("const x='b'+'ar'; foo[x]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar")

        pdg = generate_pdg("foo[42]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[42]")

        pdg = generate_pdg("foo[42.0]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[42]")

        pdg = generate_pdg("foo[false]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[False]")

        pdg = generate_pdg("foo[true]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[True]")

        pdg = generate_pdg("foo[null]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[None]")

        pdg = generate_pdg("foo[[1,2]]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[[1, 2]]")

        pdg = generate_pdg("foo[{'a':1}]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[{'a': 1}]")

        pdg = generate_pdg("foo[3.14]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[3.14]")

        pdg = generate_pdg("foo[function() {}]")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[<FunctionExpression>]")

        pdg = generate_pdg('foo["bar"]')
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar")

        pdg = generate_pdg("foo.bar.baz")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz")

        pdg = generate_pdg("foo['bar'].baz")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz")

        pdg = generate_pdg("foo[42].baz")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[42].baz")

        pdg = generate_pdg("foo.bar['baz']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz")

        pdg = generate_pdg("foo[42]['baz']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo[42].baz")

        pdg = generate_pdg("foo['bar']['baz']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz")

        pdg = generate_pdg("foo.bar.baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz.boo")

        # More complex examples:

        pdg = generate_pdg("foo.bar().baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo['bar']().baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo.bar()['baz'].boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo.bar().baz['boo']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo.bar(x).baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo.bar(x,y).baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo.bar(x,y(z),w).baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar().baz.boo")

        pdg = generate_pdg("foo().bar().baz().boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo().bar().baz().boo")

        # Test handling of ThisExpression:

        pdg = generate_pdg("this.bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this.bar")

        pdg = generate_pdg("this['bar']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this.bar")

        pdg = generate_pdg('this["bar"]')
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this.bar")

        pdg = generate_pdg("this().bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this().bar")

        pdg = generate_pdg("this(x,y,z).bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this().bar")

        # Test handling of Literals:
        pdg = generate_pdg("'foo'.length")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<Literal>.length")

        pdg = generate_pdg("'foo'['length']")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<Literal>.length")

        # Test handling of NewExpressions:
        pdg = generate_pdg(r"new RegExp(/^(http|https):\/\//).test")  # (real-world example)
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<NewExpression>.test")

        # Test handling of FunctionExpressions:
        pdg = generate_pdg("(function foo() { return 42; }).bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<FunctionExpression>.bar")

        # Test handling of AssignmentExpressions:
        pdg = generate_pdg("(x='foo').length")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<AssignmentExpression>.length")

    def test_call_expression_get_full_function_name(self):
        pdg = generate_pdg("foo(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo")

        pdg = generate_pdg("foo.bar(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar")

        pdg = generate_pdg("foo.bar.baz(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz")

        pdg = generate_pdg("foo.bar.baz.boo(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        # Test handling of computed MemberExpressions (with statically evaluate-able strings):

        pdg = generate_pdg("foo['bar'].baz(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz")

        pdg = generate_pdg("foo[bar].baz(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo[<Identifier>].baz")

        pdg = generate_pdg("foo.bar['baz'](x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz")

        pdg = generate_pdg('foo["bar"].baz.boo(x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        pdg = generate_pdg('foo.bar["baz"].boo(x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        pdg = generate_pdg('foo.bar.baz["boo"](x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        pdg = generate_pdg('foo.bar["baz"]["boo"](x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        pdg = generate_pdg('foo["bar"].baz["boo"](x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        pdg = generate_pdg('foo["bar"]["baz"]["boo"](x)')
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(), "foo.bar.baz.boo")

        # Note that the returned value may also be more complex:
        #     * call_expression_get_full_function_name("x().y()") ==returns==> "x().y"
        #     * call_expression_get_full_function_name("x(a,b).y()") ==returns==> "x().y"

        pdg = generate_pdg("x().y()")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "x().y")

        pdg = generate_pdg("x(a,b).y()")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "x().y")

        pdg = generate_pdg("foo(a,b).bar(c,d).baz(e,f).boo(x)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "foo().bar().baz().boo")

        pdg = generate_pdg("x()()")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "x()")

        pdg = generate_pdg("!function(x) {console.log(x)}(42)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "<FunctionExpression>")

        # A real-world example from the "ClassLink OneClick Extension",
        #   version 10.6, extension ID jgfbgkjjlonelmpenhpfeeljjlcgnkpe:
        pdg = generate_pdg("!function(t, n, e) { f.apply(this, arguments) }(l, t.data, n.frameId)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "<FunctionExpression>")

    def test_get_sensitive_apis_accessed(self):
        # No sensitive API:
        pdg = generate_pdg("some(harmless, code); no(sensitive, api, usage);")
        self.assertEqual(len(pdg.get_sensitive_apis_accessed()), 0)

        # Sensitive API fetch():
        code_with_fetch = """
        chrome.runtime.onMessage.addListener(function (request, sender, sendResponse) {    
            if (request.contentScriptQuery == "getdata") {
                var url = request.url;
                fetch(url)
                    .then(response => response.text())
                    .then(response => sendResponse(response))
                    .catch()
                return true;
            }
        });
        """
        pdg = generate_pdg(code_with_fetch)
        print(pdg)
        # example code above taken from:
        #   https://stackoverflow.com/questions/53405535/how-to-enable-fetch-post-in-chrome-extension-contentscript
        sensitive_apis_accessed = pdg.get_sensitive_apis_accessed()
        self.assertEqual(len(sensitive_apis_accessed), 1)
        self.assertEqual(list(sensitive_apis_accessed)[0], ("fetch", "fetch"))

        # Sensitive API chrome.cookies:
        code_with_chrome_cookies = """
        chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
            chrome.cookies.getAll({},
                function(cookies) {
                    sendResponse(cookies);
                }
            );
            return true;
        });
        """
        pdg = generate_pdg(code_with_chrome_cookies)
        sensitive_apis_accessed = pdg.get_sensitive_apis_accessed()
        self.assertEqual(len(sensitive_apis_accessed), 1)
        self.assertEqual(list(sensitive_apis_accessed)[0], ("chrome.cookies", "chrome.cookies.getAll"))

        # 2 sensitive APIs: fetch() *AND* chrome.cookies:
        pdg = generate_pdg(code_with_fetch + code_with_chrome_cookies)
        sensitive_apis_accessed = pdg.get_sensitive_apis_accessed()
        self.assertEqual(len(sensitive_apis_accessed), 2)
        self.assertTrue(list(sensitive_apis_accessed) in\
                        [[("fetch", "fetch"), ("chrome.cookies", "chrome.cookies.getAll")],
                         [("chrome.cookies", "chrome.cookies.getAll"), ("fetch", "fetch")]])

        # Sensitive API indexedDB:
        code_with_indexedDB = """
        chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
            const openReq = indexedDB.open("account_db", 2);
            openReq.onsuccess = (event) => {
                const db = event.target.result;
                db.transaction("accounts")
                  .objectStore("accounts")
                  .get("Alice").onsuccess = (event) => {
                    sendResponse(event.target.result.pw);
                };
            };
            return true;
        });
        """
        pdg = generate_pdg(code_with_indexedDB)
        sensitive_apis_accessed = pdg.get_sensitive_apis_accessed()
        self.assertEqual(len(sensitive_apis_accessed), 1)
        self.assertEqual(list(sensitive_apis_accessed)[0], ("indexedDB", "indexedDB.open"))

    def test_get_height(self):
        code = """1 + (2 + 3)"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (1 child)
        # 	[2] [ExpressionStatement] (1 child)
        # 		[3] [BinaryExpression:"+"] (2 children)
        # 			[4] [Literal:"1"] (0 children)
        # 			[5] [BinaryExpression:"+"] (2 children)
        # 				[6] [Literal:"2"] (0 children)
        # 				[7] [Literal:"3"] (0 children)
        # 1  2   3   4   5
        self.assertEqual(pdg.get_height(), 5)

    def test_promise_returning_function_call_get_all_then_calls(self):
        # Example #1 (fetch):
        code = """
        fetch(constants.CNAME_DOMAINS_LOCAL_URL)
                        .then(response => response.json())
                        .then(data => {
                            badger.cnameDomains = data;
                        });
        """  # taken from: /pkehgijcmpdhfbdbbnkijodmdjhbjlgp-2021.11.23.1-Crx4Chrome.com/background.js
        pdg = generate_pdg(code)
        print(pdg)
        promise_returning_function = pdg.get_identifier_by_name("fetch").get_parent(["CallExpression"])
        all_then_calls = promise_returning_function.promise_returning_function_call_get_all_then_calls()
        self.assertEqual(len(all_then_calls), 2)
        print(all_then_calls[0])
        print(all_then_calls[1])
        self.assertEqual(all_then_calls[0].name, "ArrowFunctionExpression")
        self.assertEqual(all_then_calls[0].children[0].name, "Identifier")
        self.assertEqual(all_then_calls[0].children[0].attributes['name'], "response")
        self.assertEqual(all_then_calls[1].name, "ArrowFunctionExpression")
        self.assertEqual(all_then_calls[1].children[0].name, "Identifier")
        self.assertEqual(all_then_calls[1].children[0].attributes['name'], "data")

        # Example #2 (chrome.cookies.getAll):
        code = """
        function logCookies(cookies) {
            for (const cookie of cookies) {
                console.log(cookie.value);
            }
        }
        
        chrome.cookies.getAll({name: "favorite-color"}).then(logCookies);
        """  # taken from: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/cookies/getAll
        pdg = generate_pdg(code)
        print(pdg)
        # ...
        # [1] [CallExpression] (2 children)
        # 	[2] [MemberExpression:"False"] (2 children)
        # 		[3] [MemberExpression:"False"] (2 children)
        # 			[4] [Identifier:"chrome"] (0 children)
        # 			[5] [Identifier:"cookies"] (0 children)
        #       [6] [Identifier:"getAll"] (0 children)
        #   [7] [ObjectExpression] (1 child)
        #       [8] [Property] (2 children)
        #           [9] [Identifier:"name"] (0 children)
        #           [10] [Literal::{'raw': '"favorite-color"', 'value': 'favorite-color'}] (0 children)
        # ...
        promise_returning_function = pdg.get_identifier_by_name("chrome").great_grandparent()
        all_then_calls = promise_returning_function.promise_returning_function_call_get_all_then_calls(
            resolve_function_references=True)
        self.assertEqual(len(all_then_calls), 1)
        self.assertEqual(all_then_calls[0].name, "FunctionDeclaration")
        all_then_calls = promise_returning_function.promise_returning_function_call_get_all_then_calls(
            resolve_function_references=False)
        self.assertEqual(len(all_then_calls), 1)
        self.assertEqual(all_then_calls[0].name, "Identifier")
        self.assertEqual(all_then_calls[0].attributes['name'], "logCookies")

    def test_get_sibling_relative(self):
        code = """function foo(x,y,z) {}"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (1 child)
        # 	[2] [FunctionDeclaration] (5 children) --e--> [55]
        # 		[3] [Identifier:"foo"] (0 children)
        # 		[4] [Identifier:"x"] (0 children)
        # 		[5] [Identifier:"y"] (0 children)
        # 		[6] [Identifier:"z"] (0 children)
        # 		[7] [BlockStatement] (0 children)
        x_identifier = pdg.get_child("FunctionDeclaration").children[1]
        y_identifier = pdg.get_child("FunctionDeclaration").children[2]
        z_identifier = pdg.get_child("FunctionDeclaration").children[3]

        self.assertEqual(x_identifier.get_sibling_relative(0), x_identifier)
        self.assertEqual(x_identifier.get_sibling_relative(1), y_identifier)
        self.assertEqual(x_identifier.get_sibling_relative(2), z_identifier)

        self.assertEqual(y_identifier.get_sibling_relative(-1), x_identifier)
        self.assertEqual(y_identifier.get_sibling_relative(0), y_identifier)
        self.assertEqual(y_identifier.get_sibling_relative(1), z_identifier)

        self.assertEqual(z_identifier.get_sibling_relative(-2), x_identifier)
        self.assertEqual(z_identifier.get_sibling_relative(-1), y_identifier)
        self.assertEqual(z_identifier.get_sibling_relative(0), z_identifier)

    def test_get_sibling_relative_or_none(self):
        code = """function foo(x,y,z) {}"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (1 child)
        # 	[2] [FunctionDeclaration] (5 children) --e--> [55]
        # 		[3] [Identifier:"foo"] (0 children)
        # 		[4] [Identifier:"x"] (0 children)
        # 		[5] [Identifier:"y"] (0 children)
        # 		[6] [Identifier:"z"] (0 children)
        # 		[7] [BlockStatement] (0 children)
        x_identifier = pdg.get_child("FunctionDeclaration").children[1]
        y_identifier = pdg.get_child("FunctionDeclaration").children[2]
        z_identifier = pdg.get_child("FunctionDeclaration").children[3]

        self.assertEqual(x_identifier.get_sibling_relative_or_none(0), x_identifier)
        self.assertEqual(x_identifier.get_sibling_relative_or_none(1), y_identifier)
        self.assertEqual(x_identifier.get_sibling_relative_or_none(2), z_identifier)

        self.assertEqual(y_identifier.get_sibling_relative_or_none(-1), x_identifier)
        self.assertEqual(y_identifier.get_sibling_relative_or_none(0), y_identifier)
        self.assertEqual(y_identifier.get_sibling_relative_or_none(1), z_identifier)

        self.assertEqual(z_identifier.get_sibling_relative_or_none(-2), x_identifier)
        self.assertEqual(z_identifier.get_sibling_relative_or_none(-1), y_identifier)
        self.assertEqual(z_identifier.get_sibling_relative_or_none(0), z_identifier)

        # Additional test cases for Node.get_sibling_relative_or_none():
        self.assertIsNone(x_identifier.get_sibling_relative_or_none(-2))
        self.assertIsNone(x_identifier.get_sibling_relative_or_none(4))
        self.assertIsNone(y_identifier.get_sibling_relative_or_none(-3))
        self.assertIsNone(y_identifier.get_sibling_relative_or_none(3))
        self.assertIsNone(z_identifier.get_sibling_relative_or_none(-4))
        self.assertIsNone(z_identifier.get_sibling_relative_or_none(2))

    def test_data_flow_distance_to(self):
        code = """x = 42; y = x;"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (2 children)
        # 	[2] [ExpressionStatement] (1 child)
        # 		[3] [AssignmentExpression:"="] (2 children)
        # 			[4] [Identifier:"x"] (0 children) --data--> [9]
        # 			[5] [Literal::{'raw': '42', 'value': 42}] (0 children)
        # 	[6] [ExpressionStatement] (1 child)
        # 		[7] [AssignmentExpression:"="] (2 children)
        # 			[8] [Identifier:"y"] (0 children)
        # 			[9] [Identifier:"x"] (0 children) --data--> [8]
        first_x_identifier = pdg.children[0].get_child("AssignmentExpression").get_child("Identifier")
        second_x_identifier = pdg.children[1].get_child("AssignmentExpression").children[1]
        y_identifier = pdg.children[1].get_child("AssignmentExpression").children[0]

        self.assertEqual(first_x_identifier.data_flow_distance_to(first_x_identifier), 0)
        self.assertEqual(second_x_identifier.data_flow_distance_to(second_x_identifier), 0)
        self.assertEqual(y_identifier.data_flow_distance_to(y_identifier), 0)

        self.assertEqual(first_x_identifier.data_flow_distance_to(y_identifier), 2)
        self.assertEqual(second_x_identifier.data_flow_distance_to(y_identifier), 1)

        self.assertEqual(y_identifier.data_flow_distance_to(first_x_identifier), float("inf"))
        self.assertEqual(y_identifier.data_flow_distance_to(second_x_identifier), float("inf"))

    def test_code_occurrence(self):
        code = """x = 42; y = x;"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (2 children)
        # 	[2] [ExpressionStatement] (1 child)
        # 		[3] [AssignmentExpression:"="] (2 children)
        # 			[4] [Identifier:"x"] (0 children) --data--> [9]
        # 			[5] [Literal::{'raw': '42', 'value': 42}] (0 children)
        # 	[6] [ExpressionStatement] (1 child)
        # 		[7] [AssignmentExpression:"="] (2 children)
        # 			[8] [Identifier:"y"] (0 children)
        # 			[9] [Identifier:"x"] (0 children) --data--> [8]
        first_x_identifier = pdg.children[0].get_child("AssignmentExpression").get_child("Identifier")
        second_x_identifier = pdg.children[1].get_child("AssignmentExpression").children[1]
        y_identifier = pdg.children[1].get_child("AssignmentExpression").children[0]
        identifiers = {first_x_identifier, second_x_identifier, y_identifier}

        # == operator:
        self.assertTrue(first_x_identifier.code_occurrence() == first_x_identifier.code_occurrence())
        self.assertTrue(second_x_identifier.code_occurrence() == second_x_identifier.code_occurrence())
        self.assertTrue(y_identifier.code_occurrence() == y_identifier.code_occurrence())

        # < operator:
        self.assertTrue(first_x_identifier.code_occurrence() < y_identifier.code_occurrence())
        self.assertTrue(y_identifier.code_occurrence() < second_x_identifier.code_occurrence())
        self.assertTrue(first_x_identifier.code_occurrence() < second_x_identifier.code_occurrence())

        # <= operator:
        self.assertTrue(first_x_identifier.code_occurrence() <= first_x_identifier.code_occurrence())
        self.assertTrue(second_x_identifier.code_occurrence() <= second_x_identifier.code_occurrence())
        self.assertTrue(y_identifier.code_occurrence() <= y_identifier.code_occurrence())
        self.assertTrue(first_x_identifier.code_occurrence() <= y_identifier.code_occurrence())
        self.assertTrue(y_identifier.code_occurrence() <= second_x_identifier.code_occurrence())
        self.assertTrue(first_x_identifier.code_occurrence() <= second_x_identifier.code_occurrence())

        # >= operator:
        self.assertTrue(first_x_identifier.code_occurrence() >= first_x_identifier.code_occurrence())
        self.assertTrue(second_x_identifier.code_occurrence() >= second_x_identifier.code_occurrence())
        self.assertTrue(y_identifier.code_occurrence() >= y_identifier.code_occurrence())

        # > operator:
        self.assertTrue(y_identifier.code_occurrence() > first_x_identifier.code_occurrence())
        self.assertTrue(second_x_identifier.code_occurrence() > y_identifier.code_occurrence())
        self.assertTrue(second_x_identifier.code_occurrence() > first_x_identifier.code_occurrence())

        # test min():
        self.assertEqual(
            min(identifiers, key=lambda identifier: identifier.code_occurrence()),
            first_x_identifier
        )

        # test max():
        self.assertEqual(
            max(identifiers, key=lambda identifier: identifier.code_occurrence()),
            second_x_identifier
        )

    def test_all_nodes_iter(self):
        code = """x = 1"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (1 child)
        # 	[2] [ExpressionStatement] (1 child)
        # 		[3] [AssignmentExpression:"="] (2 children)
        # 			[4] [Identifier:"x"] (0 children)
        # 			[5] [Literal::{'raw': '1', 'value': 1}] (0 children)
        all_nodes = [node.id for node in pdg.all_nodes_iter()]
        print(all_nodes)
        self.assertEqual(len(all_nodes), 5)

    def test_function_declaration_get_name(self):
        code = """function foo() {}"""
        pdg = generate_pdg(code)
        print(pdg)
        # [1] [Program] (1 child)
        # 	[2] [FunctionDeclaration] (2 children) --e--> [4]
        # 		[3] [Identifier:"foo"] (0 children)
        # 		[4] [BlockStatement] (0 children)
        function_declaration = pdg.get_child("FunctionDeclaration")
        self.assertEqual(function_declaration.function_declaration_get_name(), "foo")

    def test_function_Identifier_get_FunctionDeclaration(self):
        # A very simple test:
        code = """
        function foo(x) {return x;}
        foo(42);
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [57] [Program] (2 children)
        # 	[58] [FunctionDeclaration] (3 children) --e--> [61]
        # 		[59] [Identifier:"foo"] (0 children) --data--> [66]
        # 		[60] [Identifier:"x"] (0 children) --data--> [63]
        # 		[61] [BlockStatement] (1 child) --e--> [62]
        # 			[62] [ReturnStatement] (1 child)
        # 				[63] [Identifier:"x"] (0 children)
        # 	[64] [ExpressionStatement] (1 child)
        # 		[65] [CallExpression] (2 children)
        # 			[66] [Identifier:"foo"] (0 children)
        # 			[67] [Literal::{'raw': '42', 'value': 42}] (0 children)
        foos = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "foo"]
        self.assertEqual(len(foos), 2)
        function_identifier = [foo for foo in foos if foo.parent.name == "CallExpression"][0]
        correct_function_declaration = [foo.parent for foo in foos if foo.parent.name == "FunctionDeclaration"][0]
        print(f"function_identifier = {function_identifier}")
        print(f"correct_function_declaration = {correct_function_declaration}")

        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=True),
            correct_function_declaration
        )
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=False),
            correct_function_declaration
        )

        # Test a somewhat complex scope: Function called is declared within the scope of "foo", 2 scopes above the
        #   scope of the call:
        code = """
        function foo() {
            function bar() { function baz() {return boo();} return baz(); }
            function boo() { return 43; } //        ^^^
            return bar();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [55] [Program] (1 child)
        # 	[56] [FunctionDeclaration] (4 children) --e--> [71] --e--> [59] --e--> [58]
        # 		[71] [FunctionDeclaration] (2 children) --e--> [73]
        # 			[72] [Identifier:"boo"] (0 children) --data--> [67]
        # 			[73] [BlockStatement] (1 child) --e--> [74]
        # 				[74] [ReturnStatement] (1 child)
        # 					[75] [Literal::{'raw': '43', 'value': 43}] (0 children)
        # 		[59] [FunctionDeclaration] (3 children) --e--> [62] --e--> [61]
        # 			[62] [FunctionDeclaration] (2 children) --e--> [64]
        # 				[63] [Identifier:"baz"] (0 children) --data--> [70]
        # 				[64] [BlockStatement] (1 child) --e--> [65]
        # 					[65] [ReturnStatement] (1 child)
        # 						[66] [CallExpression] (1 child)
        # 							[67] [Identifier:"boo"] (0 children)
        # 			[60] [Identifier:"bar"] (0 children) --data--> [78]
        # 			[61] [BlockStatement] (1 child) --e--> [68]
        # 				[68] [ReturnStatement] (1 child)
        # 					[69] [CallExpression] (1 child)
        # 						[70] [Identifier:"baz"] (0 children)
        # 		[57] [Identifier:"foo"] (0 children)
        # 		[58] [BlockStatement] (1 child) --e--> [76]
        # 			[76] [ReturnStatement] (1 child)
        # 				[77] [CallExpression] (1 child)
        # 					[78] [Identifier:"bar"] (0 children)
        boos = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "boo"]
        function_identifier = [boo for boo in boos if boo.parent.name == "CallExpression"][0]
        function_declaration = [boo for boo in boos if boo.parent.name == "FunctionDeclaration"][0].parent
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=True),
            function_declaration
        )
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=False),
            function_declaration
        )

        # Test the fact that functions defined in higher scopes may be shadowed/overwritten in lower scopes:
        code = """
        function foo() {return 1;}
        function bar() {
            function foo() {return 2;}
            console.log(foo());
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [117] [Program] (2 children) <<< None
        # 	[118] [FunctionDeclaration] (2 children) <<< body
        # 		[119] [Identifier:"foo"] (0 children) <<< id
        # 		[120] [BlockStatement] (1 child) <<< body
        # 			[121] [ReturnStatement] (1 child) <<< body
        # 				[122] [Literal::{'raw': '1', 'value': 1}] (0 children) <<< argument
        # 	[123] [FunctionDeclaration] (2 children) <<< body
        # 		[124] [Identifier:"bar"] (0 children) <<< id
        # 		[125] [BlockStatement] (2 children) <<< body
        # 			[126] [FunctionDeclaration] (2 children) <<< body
        # 				[127] [Identifier:"foo"] (0 children) <<< id --data--> [137]     <----- ...should refer to this!
        # 				[128] [BlockStatement] (1 child) <<< body
        # 					[129] [ReturnStatement] (1 child) <<< body
        # 						[130] [Literal::{'raw': '2', 'value': 2}] (0 children) <<< argument
        # 			[131] [ExpressionStatement] (1 child) <<< body
        # 				[132] [CallExpression] (2 children) <<< expression
        # 					[133] [MemberExpression:"False"] (2 children) <<< callee
        # 						[134] [Identifier:"console"] (0 children) <<< object
        # 						[135] [Identifier:"log"] (0 children) <<< property
        # 					[136] [CallExpression] (1 child) <<< arguments
        # 						[137] [Identifier:"foo"] (0 children) <<< callee      <----- This...
        foos = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "foo"]
        self.assertEqual(len(foos), 3)
        function_identifier = [foo for foo in foos if foo.parent.name == "CallExpression"][0]
        correct_function_declaration = [foo.parent for foo in foos if foo.grandparent().name == "BlockStatement"][0]
        print(f"function_identifier = {function_identifier}")
        print(f"correct_function_declaration = {correct_function_declaration}")

        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=True),
            correct_function_declaration
        )
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=False),
            correct_function_declaration
        )

        # Test the fact that "[t]he scope of a function declaration is the function in which it is declared" and *not*
        #   the block:
        code = """
        function foo() {return 1;}
        function bar() {
            {function foo() {return 2;}} // <--- note the difference to the test above: the "{" and the "}"
            console.log(foo());
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        foos = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "foo"]
        self.assertEqual(len(foos), 3)
        function_identifier = [foo for foo in foos if foo.parent.name == "CallExpression"][0]
        correct_function_declaration = [foo.parent for foo in foos if foo.grandparent().name == "BlockStatement"][0]
        print(f"function_identifier = {function_identifier}")
        print(f"correct_function_declaration = {correct_function_declaration}")

        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=True),
            correct_function_declaration
        )
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=False),
            correct_function_declaration
        )

        # Test a (simplified) real-world example from content script of the "Binance Wallet" extension
        #   (extension ID fhbohimaelbohpjbbldcngcnapndodjp, version 2.12.2)
        #   which, for some reason, caused trouble for DoubleX's data flow creation:
        code = """
        !function(e, r, t) {
            function s(e) {
                v(e)           // <---------- usage
            }
        
            function u(e, r, t, n) {
                var o = Object.getPrototypeOf(r);
                !function(e, r, t) {
                        (r[t] = function() {
                            var v = r.level;
                            l(this, {}, u)
                        })
                    }(e, r, t)
            }
        
            function a(e, r, t, i) {
                return e, r, t, i
            }
        
            function c(e, r, t, n) {
                return e, r, t, n
            }
        
            function d(e, r, t) {
                return e, r, t
            }
        
            function l(e, r, t) {
                return e, r, t
            }
        
            function f(e) {
                return e
            }
        
            function v(e) {  // <---------- declaration
                return e
            }
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [103] [Program] (1 child)
        # 	[104] [ExpressionStatement] (1 child)
        # 		[105] [UnaryExpression:"!"] (1 child)
        # 			[106] [FunctionExpression] (12 children)
        # 				[218] [FunctionDeclaration] (3 children) --e--> [221]
        # 					[219] [Identifier:"v"] (0 children) --data--> [117]
        # 					[220] [Identifier:"e"] (0 children) --data--> [223]
        # 					[221] [BlockStatement] (1 child) --e--> [222]
        # 						[222] [ReturnStatement] (1 child)
        # 							[223] [Identifier:"e"] (0 children)
        # 				...
        # 				[111] [FunctionDeclaration] (3 children) --e--> [114]
        # 					[112] [Identifier:"s"] (0 children)
        # 					[113] [Identifier:"e"] (0 children) --data--> [118]
        # 					[114] [BlockStatement] (1 child) --e--> [115]
        # 						[115] [ExpressionStatement] (1 child)
        # 							[116] [CallExpression] (2 children)
        # 								[117] [Identifier:"v"] (0 children)
        # 								[118] [Identifier:"e"] (0 children) --data--> [220]
        # 				[107] [Identifier:"e"] (0 children)
        # 				[108] [Identifier:"r"] (0 children)
        # 				[109] [Identifier:"t"] (0 children)
        # 				[110] [BlockStatement] (0 children)
        vs = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "v"]
        self.assertEqual(len(vs), 3)
        function_identifier = [v for v in vs if v.parent.name == "CallExpression"][0]
        correct_function_declaration = [v.parent for v in vs if v.parent.name == "FunctionDeclaration"][0]
        print(f"function_identifier = {function_identifier}")
        print(f"correct_function_declaration = {correct_function_declaration}")

        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=True),
            correct_function_declaration
        )
        self.assertEqual(
            function_identifier.function_Identifier_get_FunctionDeclaration(print_warning_if_not_found=True,
                                                                            add_data_flow_edges=False),
            correct_function_declaration
        )

    def test_get_all_as_iter(self):
        code = """a + b + c + d + e"""
        pdg = generate_pdg(code)
        print(pdg)
        # [55] [Program] (1 child)
        # 	[56] [ExpressionStatement] (1 child)
        # 		[57] [BinaryExpression:"+"] (2 children)
        # 			[58] [BinaryExpression:"+"] (2 children)
        # 				[59] [BinaryExpression:"+"] (2 children)
        # 					[60] [BinaryExpression:"+"] (2 children)
        # 						[61] [Identifier:"a"] (0 children)
        # 						[62] [Identifier:"b"] (0 children)
        # 					[63] [Identifier:"c"] (0 children)
        # 				[64] [Identifier:"d"] (0 children)
        # 			[65] [Identifier:"e"] (0 children)
        all_identifiers1 = pdg.get_all("Identifier")
        self.assertEqual(len(all_identifiers1), 5)
        all_identifiers2 = [identifier for identifier in pdg.get_all_as_iter("Identifier")]
        self.assertEqual(len(all_identifiers2), 5)
        self.assertEqual(set(all_identifiers1), set(all_identifiers2))

    def test_get_all_as_iter2(self):
        # Test whether get_all_as_iter2() behaves just like get_all_as_iter() when the list contains just 1 string:
        code = """a + b + c + d + e"""
        pdg = generate_pdg(code)
        print(pdg)
        # [55] [Program] (1 child)
        # 	[56] [ExpressionStatement] (1 child)
        # 		[57] [BinaryExpression:"+"] (2 children)
        # 			[58] [BinaryExpression:"+"] (2 children)
        # 				[59] [BinaryExpression:"+"] (2 children)
        # 					[60] [BinaryExpression:"+"] (2 children)
        # 						[61] [Identifier:"a"] (0 children)
        # 						[62] [Identifier:"b"] (0 children)
        # 					[63] [Identifier:"c"] (0 children)
        # 				[64] [Identifier:"d"] (0 children)
        # 			[65] [Identifier:"e"] (0 children)
        all_identifiers1 = pdg.get_all("Identifier")
        self.assertEqual(len(all_identifiers1), 5)
        all_identifiers2 = [identifier for identifier in pdg.get_all_as_iter2(["Identifier"])]
        self.assertEqual(len(all_identifiers2), 5)
        self.assertEqual(set(all_identifiers1), set(all_identifiers2))

        # Test get_all_as_iter2() with a list of two elements (["Identifier", "Literal"]):
        code = """one + 1"""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(2, len([identifier for identifier in pdg.get_all_as_iter2(["Identifier", "Literal"])]))

    def test_object_expression_get_property(self):
        code = """foo({a: 1, b: 2, c: 3})"""
        pdg = generate_pdg(code)
        print(pdg)
        # [56] [Program] (1 child)
        # 	[57] [ExpressionStatement] (1 child)
        # 		[58] [CallExpression] (2 children)
        # 			[59] [Identifier:"foo"] (0 children)
        # 			[60] [ObjectExpression] (3 children)
        # 				[61] [Property] (2 children)
        # 					[62] [Identifier:"a"] (0 children)
        # 					[63] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 				[64] [Property] (2 children)
        # 					[65] [Identifier:"b"] (0 children)
        # 					[66] [Literal::{'raw': '2', 'value': 2}] (0 children)
        # 				[67] [Property] (2 children)
        # 					[68] [Identifier:"c"] (0 children)
        # 					[69] [Literal::{'raw': '3', 'value': 3}] (0 children)
        object_expression = pdg.get_child("ExpressionStatement")\
                             .get_child("CallExpression")\
                             .get_child("ObjectExpression")
        self.assertEqual(object_expression.object_expression_get_property("a").children[1].attributes['value'], 1)
        self.assertEqual(object_expression.object_expression_get_property("b").children[1].attributes['value'], 2)
        self.assertEqual(object_expression.object_expression_get_property("c").children[1].attributes['value'], 3)
        self.assertIsNone(object_expression.object_expression_get_property("d"))
        self.assertIsNone(object_expression.object_expression_get_property("e"))

    def test_object_expression_get_property_value(self):
        code = """foo({a: 1, b: 2, c: 3})"""
        pdg = generate_pdg(code)
        print(pdg)
        # [56] [Program] (1 child)
        # 	[57] [ExpressionStatement] (1 child)
        # 		[58] [CallExpression] (2 children)
        # 			[59] [Identifier:"foo"] (0 children)
        # 			[60] [ObjectExpression] (3 children)
        # 				[61] [Property] (2 children)
        # 					[62] [Identifier:"a"] (0 children)
        # 					[63] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 				[64] [Property] (2 children)
        # 					[65] [Identifier:"b"] (0 children)
        # 					[66] [Literal::{'raw': '2', 'value': 2}] (0 children)
        # 				[67] [Property] (2 children)
        # 					[68] [Identifier:"c"] (0 children)
        # 					[69] [Literal::{'raw': '3', 'value': 3}] (0 children)
        object_expression = pdg.get_child("ExpressionStatement") \
            .get_child("CallExpression") \
            .get_child("ObjectExpression")
        self.assertEqual(object_expression.object_expression_get_property_value("a").attributes['value'], 1)
        self.assertEqual(object_expression.object_expression_get_property_value("b").attributes['value'], 2)
        self.assertEqual(object_expression.object_expression_get_property_value("c").attributes['value'], 3)
        self.assertIsNone(object_expression.object_expression_get_property_value("d"))
        self.assertIsNone(object_expression.object_expression_get_property_value("e"))

    def test_average_identifier_length(self):
        code = ""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_identifier_length(), -1)

        code = """a = bc + def"""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_identifier_length(), 2.0)

        code = """a = bc"""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_identifier_length(), 1.5)

    def test_average_declared_variable_name_length(self):
        code = ""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_declared_variable_name_length(), -1)

        code = """
        var a = foobar();
        let bc = foo_bar_baz();
        const def = foo_bar_baz_boo();
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_declared_variable_name_length(), 2.0)

        code = """
        var a = foobar();
        let bc = foo_bar_baz();
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_declared_variable_name_length(), 1.5)

    def test_average_function_declaration_name_length(self):
        code = ""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_function_declaration_name_length(), -1)

        code = """
        function a() {}
        function bc() { function def() {} }
        bawitdaba = diggy_diggy_diggy;
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_function_declaration_name_length(), 2.0)

        code = """
        function a() {}
        function bc() {}
        bawitdaba = diggy_diggy_diggy;
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_function_declaration_name_length(), 1.5)

    def test_average_class_name_length(self):
        code = ""
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_class_name_length(), -1)

        code = """
        class A {}
        class Bc {}
        class Def {}
        bawitdaba = diggy_diggy_diggy;
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_class_name_length(), 2.0)

        code = """
        class A {}
        class Bc {}
        bawitdaba = diggy_diggy_diggy;
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(pdg.average_class_name_length(), 1.5)

    def test_is_function_declaration_param(self):
        code = """
        function foo(x,y) {
            z();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        y = pdg.get_identifier_by_name("y")
        z = pdg.get_identifier_by_name("z")
        self.assertTrue(x.is_function_declaration_param())
        self.assertTrue(y.is_function_declaration_param())
        self.assertFalse(z.is_function_declaration_param())

    def test_is_inside_any_function_declaration_param(self):
        code = """
        function foo(x=1,{a:y}) {
            z();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        y = pdg.get_identifier_by_name("y")
        z = pdg.get_identifier_by_name("z")
        self.assertTrue(x.is_inside_any_function_declaration_param())
        self.assertTrue(y.is_inside_any_function_declaration_param())
        self.assertFalse(z.is_inside_any_function_declaration_param())

    def test_is_or_is_inside_any_function_declaration_param(self):
        code = """
        function foo(x,{a:y}) {
            z();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        y = pdg.get_identifier_by_name("y")
        z = pdg.get_identifier_by_name("z")
        self.assertTrue(x.is_or_is_inside_any_function_declaration_param())
        self.assertTrue(y.is_or_is_inside_any_function_declaration_param())
        self.assertFalse(z.is_or_is_inside_any_function_declaration_param())

    def test_arrow_function_expression_get_nth_param(self):
        for code in ["!function(x,y,z) {}", "!function foo(x,y,z) {}"]:
            pdg = generate_pdg(code)
            print(pdg)
            function_expression = (pdg
                                   .get_child("ExpressionStatement")
                                   .get_child("UnaryExpression")
                                   .get_child("FunctionExpression"))
            x = pdg.get_identifier_by_name("x")
            y = pdg.get_identifier_by_name("y")
            z = pdg.get_identifier_by_name("z")
            self.assertEqual(x, function_expression.arrow_function_expression_get_nth_param(0))
            self.assertEqual(y, function_expression.arrow_function_expression_get_nth_param(1))
            self.assertEqual(z, function_expression.arrow_function_expression_get_nth_param(2))

    def test_resolve_identifier(self):
        # Tests the examples given in the doc comment of resolve_identifier():

        # Returns this very Node again, when this is already where the Identifier is being defined, e.g., for this 'x':
        code = """
        let x = foo()
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        self.assertEqual(x.resolve_identifier(), x)

        # Returns None on failure, for example for the following piece of code:
        code = """
        foo(x)
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        self.assertEqual(x.resolve_identifier(), None)

        # Also works when there is overshadowing going on:
        code = """
        let x = foo1();
        {
            let x = foo2();
            bar(x);          // resolving this 'x' will return the 'x' from the declaration one line above!
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        xs = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "x"]
        xs.sort(key=lambda identifier: identifier.code_occurrence())
        self.assertEqual(len(xs), 3)
        self.assertEqual(xs[2].resolve_identifier(), xs[1])

        code = """
        const x = 42;
        foo(x);
        """
        pdg = generate_pdg(code)
        print(pdg)
        xs = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "x"]
        xs.sort(key=lambda identifier: identifier.code_occurrence())
        self.assertEqual(len(xs), 2)
        self.assertEqual(xs[1].resolve_identifier(), xs[0])

    def test_function_declaration_is_called_anywhere(self):
        # Negative examples:
        negative_examples: List[str] = [
            """
            function foo() {}
            """,
            """
            function bar() { function foo() {} }
            foo(); // must refer to some other 'foo'
            """
        ]
        for negative_example in negative_examples:
            pdg = generate_pdg(negative_example)
            func_decl =\
                [fd for fd in pdg.get_all("FunctionDeclaration") if fd.function_declaration_get_name() == "foo"][0]
            self.assertFalse(func_decl.function_declaration_is_called_anywhere())

        # Positive examples:
        positive_examples: List[str] = [
            """
            function foo() {}
            foo();
            """,
            # Hoisting #1:
            """
            foo();
            function foo() {}
            """,
            # Hoisting #2:
            """
            function bar() {
                foo();
                function foo() {}
            }
            """,
            # Recursion:
            """
            function foo() { foo(); }
            """
        ]
        for positive_example in positive_examples:
            pdg = generate_pdg(positive_example)
            func_decl = \
                [fd for fd in pdg.get_all("FunctionDeclaration") if fd.function_declaration_get_name() == "foo"][0]
            self.assertTrue(func_decl.function_declaration_is_called_anywhere())

    def test_function_expression_get_name(self):
        for code in ["!function foo() {}", "!function foo(x) {}", "!function foo(x,y) {}"]:
            pdg = generate_pdg(code)
            print(pdg)
            func_expr = pdg.get_all("FunctionExpression")[0]
            self.assertEqual(func_expr.function_expression_get_name(), "foo")

        for code in ["!function () {}", "!function (foo) {}", "!function (foo,x) {}", "!function (foo,x,y) {}"]:
            pdg = generate_pdg(code)
            print(pdg)
            func_expr = pdg.get_all("FunctionExpression")[0]
            self.assertIsNone(func_expr.function_expression_get_name())

    def test_function_expression_get_id_node(self):
        for code in ["!function foo() {}", "!function foo(x) {}", "!function foo(x,y) {}"]:
            pdg = generate_pdg(code)
            print(pdg)
            func_expr = pdg.get_all("FunctionExpression")[0]
            id_node = func_expr.function_expression_get_id_node()
            self.assertIsNotNone(id_node)
            self.assertEqual(id_node.name, "Identifier")

        for code in ["!function () {}", "!function (foo) {}", "!function (foo,x) {}", "!function (foo,x,y) {}"]:
            pdg = generate_pdg(code)
            print(pdg)
            func_expr = pdg.get_all("FunctionExpression")[0]
            self.assertIsNone(func_expr.function_expression_get_id_node())

    def test_function_expression_calls_itself_recursively(self):
        # Examples from https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Functions/arguments/callee:

        code = """
        [1, 2, 3, 4, 5].map(function factorial(n) {
            return n <= 1 ? 1 : factorial(n - 1) * n;
        });
        """
        pdg = generate_pdg(code)
        print(pdg)
        func_expr = pdg.get_all("FunctionExpression")[0]
        self.assertTrue(func_expr.function_expression_calls_itself_recursively())

        code = """
        [1, 2, 3, 4, 5].map(function (n) {
            return n <= 1 ? 1 : arguments.callee(n - 1) * n;
        });
        """
        pdg = generate_pdg(code)
        print(pdg)
        func_expr = pdg.get_all("FunctionExpression")[0]
        self.assertTrue(func_expr.function_expression_calls_itself_recursively())

        # Negative examples:

        code = """
        [1, 2, 3, 4, 5].map(function factorial(n) {
            
        });
        """
        pdg = generate_pdg(code)
        print(pdg)
        func_expr = pdg.get_all("FunctionExpression")[0]
        self.assertFalse(func_expr.function_expression_calls_itself_recursively())

        code = """
        [1, 2, 3, 4, 5].map(function (n) {
            
        });
        """
        pdg = generate_pdg(code)
        print(pdg)
        func_expr = pdg.get_all("FunctionExpression")[0]
        self.assertFalse(func_expr.function_expression_calls_itself_recursively())

    def test_identifier_is_assigned_to_before(self):
        # A simple negative example:
        code = """
        let x = 1;
        foo(x);
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [33] [Program] (2 children)
        # 	[34] [VariableDeclaration:"let"] (1 child)
        # 		[35] [VariableDeclarator] (2 children)
        # 			[36] [Identifier:"x"] (0 children) --data--> [41]
        # 			[37] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 	[38] [ExpressionStatement] (1 child)
        # 		[39] [CallExpression] (2 children)
        # 			[40] [Identifier:"foo"] (0 children)
        # 			[41] [Identifier:"x"] (0 children)
        x1 = pdg.get_child("VariableDeclaration").get_child("VariableDeclarator").get_child("Identifier")
        x2 = pdg.get_child("ExpressionStatement").get_child("CallExpression").children[1]
        self.assertFalse(x1.identifier_is_assigned_to_before(x2, scope=pdg))

        # A simple positive example:
        code = """
        let x = 1;
        x = 2;
        foo(x);
        """
        pdg = generate_pdg(code)
        print(pdg)
        # [77] [Program] (3 children)
        # 	[78] [VariableDeclaration:"let"] (1 child)
        # 		[79] [VariableDeclarator] (2 children)
        # 			[80] [Identifier:"x"] (0 children)
        # 			[81] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 	[82] [ExpressionStatement] (1 child)
        # 		[83] [AssignmentExpression:"="] (2 children)
        # 			[84] [Identifier:"x"] (0 children) --data--> [89]
        # 			[85] [Literal::{'raw': '2', 'value': 2}] (0 children)
        # 	[86] [ExpressionStatement] (1 child)
        # 		[87] [CallExpression] (2 children)
        # 			[88] [Identifier:"foo"] (0 children)
        # 			[89] [Identifier:"x"] (0 children)
        x1 = pdg.get_child("VariableDeclaration").get_child("VariableDeclarator").get_child("Identifier")
        x3 = pdg.children[2].get_child("CallExpression").children[1]
        self.assertTrue(x1.identifier_is_assigned_to_before(x3, scope=pdg))

        # A positive example with 2 scopes:
        code = """
        let x = 1;
        {
            x = 2;
            foo(x);
        }
        """
        # [114] [Program] (2 children)
        # 	[115] [VariableDeclaration:"let"] (1 child)
        # 		[116] [VariableDeclarator] (2 children)
        # 			[117] [Identifier:"x"] (0 children)
        # 			[118] [Literal::{'raw': '1', 'value': 1}] (0 children)
        # 	[119] [BlockStatement] (2 children) --e--> [120] --e--> [124]
        # 		[120] [ExpressionStatement] (1 child)
        # 			[121] [AssignmentExpression:"="] (2 children)
        # 				[122] [Identifier:"x"] (0 children) --data--> [127]
        # 				[123] [Literal::{'raw': '2', 'value': 2}] (0 children)
        # 		[124] [ExpressionStatement] (1 child)
        # 			[125] [CallExpression] (2 children)
        # 				[126] [Identifier:"foo"] (0 children)
        # 				[127] [Identifier:"x"] (0 children)
        pdg = generate_pdg(code)
        print(pdg)
        x1 = pdg.get_child("VariableDeclaration").get_child("VariableDeclarator").get_child("Identifier")
        x3 = pdg.get_child("BlockStatement").children[1].get_child("CallExpression").children[1]
        self.assertTrue(x1.identifier_is_assigned_to_before(x3, scope=pdg))

    def test_get_identifiers_declared_in_scope(self):
        code = """
        let a = 1;
        const b = 2;
        var c = 3;
        function d(e) { foo(); }
        class f {}
        here;
        """
        pdg = generate_pdg(code, ast_only=True)
        print(pdg)
        here = pdg.get_identifier_by_name("here")
        for return_overshadowed_identifiers, return_reassigned_identifiers\
                in [(False, False), (False, True), (True, False), (True, True)]:
            print(f"{return_overshadowed_identifiers}, {return_reassigned_identifiers}")

            # At `here;`, "a", "b", "c", "d" and "f" are all identifiers declared in scope:
            ids = here.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=return_overshadowed_identifiers,
                return_reassigned_identifiers=return_reassigned_identifiers,
            )
            self.assertEqual(5, len(ids))
            self.assertEqual({"a", "b", "c", "d", "f"}, set(id_.attributes['name'] for id_ in ids))

            # At `foo();`, "a", "b", "c", "d", "e" and "f" are all identifiers declared in scope:
            func_call = pdg.get_all("CallExpression")[0]
            self.assertEqual("foo", func_call.call_expression_get_full_function_name())
            self.assertEqual(
                {"a", "b", "c", "d", "e", "f"},
                set(
                    id_.attributes['name']
                    for id_ in
                    func_call.get_identifiers_declared_in_scope(
                        return_overshadowed_identifiers=return_overshadowed_identifiers,
                        return_reassigned_identifiers=return_reassigned_identifiers
                    )
                )
            )

        code = """
        function foo() { // Don't forget that 'foo' is in scope, too :)
            let x = 11;
            {
                let x = 22;
                var y = x;
                bar();
            }
            return x + y;  // returns 33 (not 44)
        }
        """
        pdg = generate_pdg(code, ast_only=True)
        print(pdg)
        # [78] [Program] (1 child)
        # 	[79] [FunctionDeclaration] (2 children) --e--> [81]
        # 		[80] [Identifier:"foo"] (0 children)
        # 		[81] [BlockStatement] (3 children) --e--> [82] --e--> [86] --e--> [95]
        # 			[82] [VariableDeclaration:"let"] (1 child)
        # 				[83] [VariableDeclarator] (2 children)
        # 					[84] [Identifier:"x"] (0 children) --data--> [97]
        # 					[85] [Literal::{'raw': '11', 'value': 11}] (0 children)
        # 			[86] [BlockStatement] (2 children) --e--> [87] --e--> [91]
        # 				[87] [VariableDeclaration:"let"] (1 child)
        # 					[88] [VariableDeclarator] (2 children)
        # 						[89] [Identifier:"x"] (0 children) --data--> [94]
        # 						[90] [Literal::{'raw': '22', 'value': 22}] (0 children)
        # 				[91] [VariableDeclaration:"var"] (1 child)
        # 					[92] [VariableDeclarator] (2 children)
        # 						[93] [Identifier:"y"] (0 children)
        # 						[94] [Identifier:"x"] (0 children)
        # 			[95] [ReturnStatement] (1 child)
        # 				[96] [BinaryExpression:"+"] (2 children)
        # 					[97] [Identifier:"x"] (0 children)
        # 					[98] [Identifier:"y"] (0 children)
        foo = pdg.get_identifier_by_name("foo")
        xs = sorted([x for x in pdg.get_all_identifiers() if x.attributes['name'] == "x"], key=lambda x: x.id)
        ys = sorted([y for y in pdg.get_all_identifiers() if y.attributes['name'] == "y"], key=lambda y: y.id)

        # "foo", "let x = 11;" and "var y" should be in scope @ "return x + y;":
        return_statement = pdg.get_all("ReturnStatement")[0]
        identifiers_declared_in_scope =\
            return_statement.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=False,
                return_reassigned_identifiers=False
            )
        self.assertEqual(3, len(identifiers_declared_in_scope))
        self.assertEqual({"foo", "x", "y"}, set(id_.attributes['name'] for id_ in identifiers_declared_in_scope))
        self.assertEqual({foo, xs[0], ys[0]}, set(identifiers_declared_in_scope))

        # "foo", "let x = 22;" and "var y" should be in scope @ "bar();":
        bar = pdg.get_identifier_by_name("bar")
        identifiers_declared_in_scope = \
            bar.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=False,
                return_reassigned_identifiers=False
            )
        self.assertEqual(3, len(identifiers_declared_in_scope))
        self.assertEqual({"foo", "x", "y"}, set(id_.attributes['name'] for id_ in identifiers_declared_in_scope))
        self.assertEqual({foo, xs[1], ys[0]}, set(identifiers_declared_in_scope))

        # All 4, "foo", "let x = 11;", "let x = 22;" and "var y" should be in scope @ "bar();"
        #   when setting return_overshadowed_identifiers=True:
        identifiers_declared_in_scope = \
            bar.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=True,
                return_reassigned_identifiers=False
            )
        self.assertEqual(4, len(identifiers_declared_in_scope))
        self.assertEqual({"foo", "x", "y"}, set(id_.attributes['name'] for id_ in identifiers_declared_in_scope))
        self.assertEqual({foo, xs[0], xs[1], ys[0]}, set(identifiers_declared_in_scope))

        code = """
        function a() {
            function b() {
                function c() {
                    function d() {
                        function e() {
                            function f() {
                                function g() {
                                    function h() {
                                        foo();
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
        bar();
        """
        pdg = generate_pdg(code, ast_only=True)
        print(pdg)
        foo = pdg.get_identifier_by_name("foo")
        bar = pdg.get_identifier_by_name("bar")

        # "a", "b", "c", "d", "e", "f", "g", "h" should be in scope @ "foo();":
        identifiers_declared_in_scope = \
            foo.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=False,
                return_reassigned_identifiers=False
            )
        self.assertEqual(8, len(identifiers_declared_in_scope))
        self.assertEqual(
            {"a", "b", "c", "d", "e", "f", "g", "h"},
            set(id_.attributes['name'] for id_ in identifiers_declared_in_scope)
        )

        # Only "a" should be in scope @ "bar();":
        identifiers_declared_in_scope = \
            bar.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=False,
                return_reassigned_identifiers=False
            )
        self.assertEqual(1, len(identifiers_declared_in_scope))
        self.assertEqual(
            {"a"},
            set(id_.attributes['name'] for id_ in identifiers_declared_in_scope)
        )

        code = """
        (function(t) {
            !function t() {}
            console.log(t);
        })(42);
        """
        # => this example is inspired by real-world code from the "ClassLink OneClick Extension", version 10.6,
        #    extension ID jgfbgkjjlonelmpenhpfeeljjlcgnkpe
        pdg = generate_pdg(code, ast_only=True)
        print(pdg)
        # [142] [Program] (1 child)
        # 	[143] [ExpressionStatement] (1 child)
        # 		[144] [CallExpression] (2 children)
        # 			[145] [FunctionExpression::{'generator': False, 'async': False, 'expression': False}] (2 children)
        # 				[146] [Identifier:"t"] (0 children)
        # 				[147] [BlockStatement] (2 children) --e--> [148] --e--> [153]
        # 					[148] [ExpressionStatement] (1 child)
        # 						[149] [UnaryExpression:"!"] (1 child)
        # 							[150] [FunctionExpression::{...}] (2 children)
        # 								[151] [Identifier:"t"] (0 children) --data--> [158]
        # 								[152] [BlockStatement] (0 children)
        # 					[153] [ExpressionStatement] (1 child)
        # 						[154] [CallExpression] (2 children)
        # 							[155] [MemberExpression:"False"] (2 children)
        # 								[156] [Identifier:"console"] (0 children)
        # 								[157] [Identifier:"log"] (0 children)
        # 							[158] [Identifier:"t"] (0 children)
        # 			[159] [Literal::{'raw': '42', 'value': 42}] (0 children)
        ts = sorted([t for t in pdg.get_all_identifiers() if t.attributes['name'] == "t"], key=lambda t: t.id)
        self.assertEqual(3, len(ts))
        [t1, t2, t3] = ts
        identifiers_declared_in_scope = \
            t3.get_identifiers_declared_in_scope(
                return_overshadowed_identifiers=False,
                return_reassigned_identifiers=False
            )
        self.assertEqual(1, len(identifiers_declared_in_scope))
        self.assertEqual("t", identifiers_declared_in_scope[0].attributes['name'])
        self.assertEqual([t1], identifiers_declared_in_scope)

    def test_find_member_expressions_ending_in(self):
        code = """
        let a = foo.bar.baz;
        let b = foo.bar;
        let c = bar.baz;
        let d = bar.baz();
        let e = foo.bar.baz();
        let f = hello.world.foo.bar.baz();
        let g = foo.bar.x.baz;
        """
        pdg = generate_pdg(code)
        print(pdg)
        member_expressions1 = pdg.find_member_expressions_ending_in("bar.baz")
        self.assertEqual(5, len(member_expressions1))
        member_expressions2 = pdg.find_member_expressions_ending_in(".bar.baz")
        self.assertEqual(3, len(member_expressions2))

    def test_member_expression_get_leftmost_identifier(self):
        self.assertEqual(
            "foo",
            expr("foo.bar")
                .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "foo",
            expr("foo.bar.baz")
                .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "foo",
            expr("foo.bar(42).baz")
            .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "foo",
            expr("foo.bar(42).baz(43).boo")
            .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "foo",
            expr("foo.bar(1,2,3).baz(4,5).boo")
            .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "foo",
            expr("foo.bar(1,2).baz(3,4,5).boo")
            .member_expression_get_leftmost_identifier().attributes['name']
        )
        self.assertEqual(
            "db",
            expr('db.transaction("accounts").objectStore("accounts").get("Alice").addEventListener')
            .member_expression_get_leftmost_identifier().attributes['name']
        )

    def test_static_eval(self):
        for allow_partial_eval in [True, False]:
            self.assertEqual(42, expr("42").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("+42").static_eval(allow_partial_eval))
            self.assertEqual(-42, expr("-42").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("0").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("3.14").static_eval(allow_partial_eval))
            self.assertEqual(-3.14, expr("-3.14").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false").static_eval(allow_partial_eval))
            self.assertEqual("foo", expr("'foo'").static_eval(allow_partial_eval))
            self.assertEqual("foo", expr("\"foo\"").static_eval(allow_partial_eval))
    
            # Test special values:
            self.assertEqual(None, expr("null").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("0/0").static_eval(allow_partial_eval)))
            self.assertTrue(math.isinf(expr("1/0").static_eval(allow_partial_eval)))
            self.assertTrue(math.isinf(expr("-1/0").static_eval(allow_partial_eval)))

            # Test the fact that null is treated as 0 for numeric additions using '+':
            self.assertEqual(0, expr("null+null").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("42+null").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("null+42").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("false+null").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("null+false").static_eval(allow_partial_eval))
            self.assertEqual(1, expr("true+null").static_eval(allow_partial_eval))
            self.assertEqual(1, expr("null+true").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("3.14+null").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("null+3.14").static_eval(allow_partial_eval))

            # Test other special cases for the '+' binary operator:
            self.assertEqual("1,23,4", expr("[1,2]+[3,4]").static_eval(allow_partial_eval))
            self.assertEqual("1,2null", expr("[1,2]+null").static_eval(allow_partial_eval))
            self.assertEqual("1.1,2.2null", expr("[1.1,2.2]+null").static_eval(allow_partial_eval))
            self.assertEqual("1,2null", expr("['1','2']+null").static_eval(allow_partial_eval))
            self.assertEqual("1,2false", expr("[1,2]+false").static_eval(allow_partial_eval))
            self.assertEqual("1,2true", expr("[1,2]+true").static_eval(allow_partial_eval))
            self.assertEqual("1,2[object Object]", expr("[1,2]+{'a':1}").static_eval(allow_partial_eval))
    
            # Test arithmetic:
            self.assertEqual(3, expr("1+2").static_eval(allow_partial_eval))  # int + int
            self.assertEqual(333, expr("111+222").static_eval(allow_partial_eval))  # int + int
            self.assertAlmostEqual(3.3, expr("1.1+2.2").static_eval(allow_partial_eval))  # float + float
            self.assertAlmostEqual(3.2, expr("1+2.2").static_eval(allow_partial_eval))  # int + float
            self.assertEqual(60, expr("70-10").static_eval(allow_partial_eval))  # int - int
            self.assertAlmostEqual(6.6, expr("7.7-1.1").static_eval(allow_partial_eval))  # float - float
            self.assertEqual(30, expr("5*6").static_eval(allow_partial_eval))  # int * int
            self.assertEqual(25, expr("100/4").static_eval(allow_partial_eval))  # int / int
            self.assertEqual(1024, expr("2**10").static_eval(allow_partial_eval))  # int ** int
    
            # Test string concatenation:
            self.assertEqual("foobar", expr("'foo' + 'bar'").static_eval(allow_partial_eval))
            self.assertEqual("foobar", expr("\"foo\" + \"bar\"").static_eval(allow_partial_eval))
            self.assertEqual("foobarbaz", expr("'foo' + 'bar' + 'baz'").static_eval(allow_partial_eval))
            self.assertEqual("foobarbaz", expr("\"foo\" + \"bar\" + \"baz\"").static_eval(allow_partial_eval))
            self.assertEqual("foobarbaz", expr("\"foo\" + 'bar' + \"baz\"").static_eval(allow_partial_eval))

            # Test string concatenation + casting:
            self.assertEqual("foo1", expr("'foo' + 1").static_eval(allow_partial_eval))
            self.assertEqual("foo1", expr("\"foo\" + 1").static_eval(allow_partial_eval))
    
            # Test lists/arrays:
            self.assertEqual([], expr("[]").static_eval(allow_partial_eval))
            self.assertEqual([42], expr("[42]").static_eval(allow_partial_eval))
            self.assertEqual([1, 2, 3], expr("[1, 2, 3]").static_eval(allow_partial_eval))
            self.assertEqual([30, 36], expr("[5*6, 6*6]").static_eval(allow_partial_eval))
            self.assertEqual(["foo", "bar"], expr("['foo', 'bar']").static_eval(allow_partial_eval))
    
            # Test AssignmentExpressions:
            self.assertEqual(42, expr("x = 42").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("x = 3.14").static_eval(allow_partial_eval))
            self.assertEqual("foo", expr("x = 'foo'").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("x = true").static_eval(allow_partial_eval))
    
            # Test logic:
            # NOT:
            self.assertEqual(False, expr("!true").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("!false").static_eval(allow_partial_eval))
            # OR:
            self.assertEqual(False, expr("false || false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("false || true").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true || false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true || true").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false | false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("false | true").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true | false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true | true").static_eval(allow_partial_eval))
            # AND:
            self.assertEqual(False, expr("false && false").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false && true").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("true && false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true && true").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false & false").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false & true").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("true & false").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("true & true").static_eval(allow_partial_eval))
            # Test laziness:
            self.assertEqual(True, expr("true || foo(x)").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("false && foo(x)").static_eval(allow_partial_eval))
            # Test more complex logic expressions:
            self.assertEqual(True, expr("!(false || (true && false))").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("!(true || (false && true))").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("(0 <= 10) && (10 <= 100)").static_eval(allow_partial_eval))
            
            # Test tilde operator:
            self.assertEqual(~42, expr("~42").static_eval(allow_partial_eval))
            
            # Test ConditionalExpressions:
            self.assertEqual(11, expr("(true || false) ? 11 : 22").static_eval(allow_partial_eval))
            self.assertEqual(22, expr("(true && false) ? 11 : 22").static_eval(allow_partial_eval))
            
            # Test lazy static evaluation of ConditionalExpressions:
            self.assertEqual(11, expr("(true || false) ? 11 : foo(x)").static_eval(allow_partial_eval))
            self.assertEqual(22, expr("(true && false) ? foo(x) : 22").static_eval(allow_partial_eval))

            # Test static evaluation of redundant ConditionalExpressions, even when the test expression cannot be
            #   evaluated statically:
            self.assertEqual(42, expr("foo(x) ? 42 : 42").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("foo(x) ? (40+2) : (84/2)").static_eval(allow_partial_eval))

            # Test MemberExpressions:
            self.assertEqual(111, expr("[111, 222, 333][0]").static_eval(allow_partial_eval))
            self.assertEqual(222, expr("[111, 222, 333][1]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][2]").static_eval(allow_partial_eval))
            self.assertEqual(111, expr("[111, 222, 333][0.0]").static_eval(allow_partial_eval))
            self.assertEqual(222, expr("[111, 222, 333][1.0]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][2.0]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][1+1]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][5-3]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][4/2]").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("[111, 222, 333][10/5]").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("[].length").static_eval(allow_partial_eval))
            self.assertEqual(1, expr("[1].length").static_eval(allow_partial_eval))
            self.assertEqual(2, expr("[1,2].length").static_eval(allow_partial_eval))
            self.assertEqual(3, expr("[1,2,3].length").static_eval(allow_partial_eval))
            self.assertEqual(4, expr("['a', 'b', 'c', 'd'].length").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("[]['length']").static_eval(allow_partial_eval))
            self.assertEqual(1, expr("[1]['length']").static_eval(allow_partial_eval))
            self.assertEqual(2, expr("[1,2]['length']").static_eval(allow_partial_eval))
            self.assertEqual(3, expr("[1,2,3]['length']").static_eval(allow_partial_eval))
            self.assertEqual(4, expr("['a', 'b', 'c', 'd']['length']").static_eval(allow_partial_eval))

            # Test SequenceExpressions (evaluate to the value of the last operand):
            self.assertEqual(222, expr("111, 222").static_eval(allow_partial_eval))
            self.assertEqual(333, expr("111, 222, 333").static_eval(allow_partial_eval))
            self.assertEqual(444, expr("111, 222, 333, 444").static_eval(allow_partial_eval))
            self.assertEqual(444, expr("foo(x), bar(y), baz(z), 444").static_eval(allow_partial_eval))
            self.assertEqual(555, expr("foo(x), bar(y), baz(z), 444+111").static_eval(allow_partial_eval))

            # Test static evaluation of calls to JavaScript built-in functions:
            # isFinite():
            self.assertEqual(True, expr("isFinite(42)").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite(3.14)").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite('42')").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite('3.14')").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite('')").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite('42x')").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite('x')").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite(true)").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite(false)").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite({})").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([{}])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite({'1':2})").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([{'1':2}])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([42])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([42,1])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([''])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite(['42'])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite(['42x'])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite(['42', '1'])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([true])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([false])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite(null)").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([null])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite(1/0)").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite(0/0)").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([[42]])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([[[42]]])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([[[[42]]]])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([[[['']]]])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([[[[42,1]]]])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([[[[42],1]]])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([[[[42]],1]])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isFinite([[[[42]]],1])").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isFinite([[[[[]]]]])").static_eval(allow_partial_eval))
            # isNaN() - should return exactly the opposite of isFinite(), except for the case of Infinity (1/0):
            self.assertEqual(not True, expr("isNaN(42)").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN(3.14)").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN('42')").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN('3.14')").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN('')").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN('42x')").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN('x')").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN(true)").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN(false)").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN({})").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([{}])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN({'1':2})").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([{'1':2}])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([42])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([42,1])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([''])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN(['42'])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN(['42x'])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN(['42', '1'])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([true])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([false])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN(null)").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([null])").static_eval(allow_partial_eval))
            self.assertEqual(False, expr("isNaN(1/0)").static_eval(allow_partial_eval))  # <----- Infinity
            self.assertEqual(not False, expr("isNaN(0/0)").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([[42]])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([[[42]]])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([[[[42]]]])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([[[['']]]])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([[[[42,1]]]])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([[[[42],1]]])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([[[[42]],1]])").static_eval(allow_partial_eval))
            self.assertEqual(not False, expr("isNaN([[[[42]]],1])").static_eval(allow_partial_eval))
            self.assertEqual(not True, expr("isNaN([[[[[]]]]])").static_eval(allow_partial_eval))
            # parseFloat():
            self.assertEqual(3.14, expr("parseFloat('3.14')").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("parseFloat('3.14xxx')").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseFloat('')").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat(false)").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat(true)").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat({})").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat({'1':2})").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat(null)").static_eval(allow_partial_eval)))
            self.assertEqual(3, expr("parseFloat(3)").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("parseFloat(3.14)").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseFloat([])").static_eval(allow_partial_eval)))
            self.assertEqual(3.14, expr("parseFloat([[[3.14, 1], 2], 3])").static_eval(allow_partial_eval))
            self.assertEqual(3.14, expr("parseFloat([[['3.14', '1'], '2'], '3'])").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseFloat([[['x', '1'], '2'], '3'])").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat([[['', '1'], '2'], '3'])").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseFloat([[], 42])").static_eval(allow_partial_eval)))
            self.assertTrue(42, expr("parseFloat([['  42xxx', 3]])").static_eval(allow_partial_eval))
            # parseInt():
            self.assertEqual(42, expr("parseInt('42')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('   42  ')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('042')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('0042')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('00042')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('42.1')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('42.9')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('42xxx')").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('42', 0)").static_eval(allow_partial_eval))
            self.assertEqual(22, expr("parseInt('42', 5)").static_eval(allow_partial_eval))
            self.assertEqual(26, expr("parseInt('42', 6)").static_eval(allow_partial_eval))
            self.assertEqual(30, expr("parseInt('42', 7)").static_eval(allow_partial_eval))
            self.assertEqual(34, expr("parseInt('42', 8)").static_eval(allow_partial_eval))
            self.assertEqual(38, expr("parseInt('42', 9)").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("parseInt('42', 10)").static_eval(allow_partial_eval))
            self.assertEqual(46, expr("parseInt('42', 11)").static_eval(allow_partial_eval))
            self.assertEqual(50, expr("parseInt('42', 12)").static_eval(allow_partial_eval))
            self.assertEqual(255, expr("parseInt('ff', 16)").static_eval(allow_partial_eval))
            self.assertEqual(255, expr("parseInt('FF', 16)").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseInt('ff')").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseInt('FF')").static_eval(allow_partial_eval)))
            self.assertEqual(255, expr("parseInt('0xff', 16)").static_eval(allow_partial_eval))
            self.assertEqual(255, expr("parseInt('0xFF', 16)").static_eval(allow_partial_eval))
            self.assertEqual(255, expr("parseInt('0xff')").static_eval(allow_partial_eval))
            self.assertEqual(255, expr("parseInt('0xFF')").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseInt('0', -1)").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseInt('0', 1)").static_eval(allow_partial_eval)))
            self.assertEqual(0, expr("parseInt('0', 2)").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("parseInt('0', 36)").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseInt('0', 37)").static_eval(allow_partial_eval)))
            self.assertEqual(42, expr("parseInt('42', 10, 1234)").static_eval(allow_partial_eval))
            # parseInt() examples from
            #     https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/parseInt:
            self.assertEqual(15, expr('parseInt("0xF", 16)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("0xF", 16)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("F", 16)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("17", 8)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("015", 10)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("15,123", 10)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("FXX123", 16)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("1111", 2)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("15 * 3", 10)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("15e2", 10)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("15px", 10)').static_eval(allow_partial_eval))
            self.assertEqual(15, expr('parseInt("12", 13)').static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr('parseInt("Hello", 8)').static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr('parseInt("546", 2)').static_eval(allow_partial_eval)))
            self.assertEqual(-15, expr('parseInt("-F", 16)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-0F", 16)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-0XF", 16)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-17", 8)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-15", 10)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-1111", 2)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-15e1", 10)').static_eval(allow_partial_eval))
            self.assertEqual(-15, expr('parseInt("-12", 13)').static_eval(allow_partial_eval))
            self.assertEqual(224, expr('parseInt("0e0", 16)').static_eval(allow_partial_eval))
            self.assertEqual(123, expr('parseInt("123_456")').static_eval(allow_partial_eval))
            self.assertEqual(146, expr('parseInt("123_456", 11)').static_eval(allow_partial_eval))
            # Using parseInt() on non-strings:
            # (https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/parseInt#using_parseint_on_non-strings)
            self.assertEqual(1112745, expr('parseInt(null, 36)').static_eval(allow_partial_eval))
            self.assertEqual(1023631, expr('parseInt(null, 35)').static_eval(allow_partial_eval))
            self.assertEqual(939407, expr('parseInt(null, 34)').static_eval(allow_partial_eval))
            self.assertEqual(859935, expr('parseInt(null, 33)').static_eval(allow_partial_eval))
            self.assertEqual(785077, expr('parseInt(null, 32)').static_eval(allow_partial_eval))
            self.assertEqual(714695, expr('parseInt(null, 31)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 30)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 29)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 28)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 27)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 26)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 25)').static_eval(allow_partial_eval))
            self.assertEqual(23, expr('parseInt(null, 24)').static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr('parseInt(null, 23)').static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr('parseInt(null, 22)').static_eval(allow_partial_eval)))
            # btoa() for Base64 encoding:
            self.assertEqual("SGVsbG8gV29ybGQh", expr('btoa("Hello World!")').static_eval(allow_partial_eval))
            self.assertEqual("SGVsbG8gV29ybGQh", expr('btoa("Hello " + "World!")').static_eval(allow_partial_eval))
            self.assertEqual("NDI=", expr('btoa("42")').static_eval(allow_partial_eval))
            self.assertEqual("NDI=", expr('btoa(42)').static_eval(allow_partial_eval))
            self.assertEqual("My4xNA==", expr('btoa("3.14")').static_eval(allow_partial_eval))
            self.assertEqual("My4xNA==", expr('btoa(3.14)').static_eval(allow_partial_eval))
            self.assertEqual("dHJ1ZQ==", expr('btoa("true")').static_eval(allow_partial_eval))
            self.assertEqual("dHJ1ZQ==", expr('btoa(true)').static_eval(allow_partial_eval))
            self.assertEqual("ZmFsc2U=", expr('btoa("false")').static_eval(allow_partial_eval))
            self.assertEqual("ZmFsc2U=", expr('btoa(false)').static_eval(allow_partial_eval))
            self.assertEqual("bnVsbA==", expr('btoa("null")').static_eval(allow_partial_eval))
            self.assertEqual("bnVsbA==", expr('btoa(null)').static_eval(allow_partial_eval))
            # Test additional redundant argument:
            self.assertEqual("SGVsbG8gV29ybGQh", expr('btoa("Hello World!", 42)').static_eval(allow_partial_eval))
            self.assertEqual("SGVsbG8gV29ybGQh", expr('btoa("Hello World!", foo)').static_eval(allow_partial_eval))
            # atob() for Base64 decoding:
            self.assertEqual("Hello World!", expr('atob("SGVsbG8gV29ybGQh")').static_eval(allow_partial_eval))
            self.assertEqual("Hello World!", expr('atob("SGVsb"+"G8gV2"+"9ybGQh")').static_eval(allow_partial_eval))
            # Test additional redundant argument:
            self.assertEqual("Hello World!", expr('atob("SGVsbG8gV29ybGQh", 42)').static_eval(allow_partial_eval))
            self.assertEqual("Hello World!", expr('atob("SGVsbG8gV29ybGQh", foo)').static_eval(allow_partial_eval))
            # Test behavior of these functions when no arguments are supplied:
            self.assertEqual(False, expr("isFinite()").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isNaN()").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isNaN(parseFloat())").static_eval(allow_partial_eval))
            self.assertEqual(True, expr("isNaN(parseInt())").static_eval(allow_partial_eval))
            self.assertTrue(math.isnan(expr("parseFloat()").static_eval(allow_partial_eval)))
            self.assertTrue(math.isnan(expr("parseInt()").static_eval(allow_partial_eval)))
            # btoa() and atob() require at least 1 argument, otherwise they raise a type error

            # Test JavaScript quirks:
            self.assertEqual(0, expr("+''").static_eval(allow_partial_eval))
            self.assertEqual(0, expr("+[]").static_eval(allow_partial_eval))
            self.assertEqual(42, expr("+[42]").static_eval(allow_partial_eval))
            self.assertEqual(-42, expr("-[42]").static_eval(allow_partial_eval))
    
            # Test resolving of constants:
            code = """
            const x = 42;
            foo(x);
            """
            pdg = generate_pdg(code)
            print(pdg)
            # [1] [Program] (2 children) <<< None
            # 	[2] [VariableDeclaration:"const"] (1 child) <<< body
            # 		[3] [VariableDeclarator] (2 children) <<< declarations
            # 			[4] [Identifier:"x"] (0 children) <<< id --data--> [9]
            # 			[5] [Literal::{'raw': '42', 'value': 42}] (0 children) <<< init
            # 	[6] [ExpressionStatement] (1 child) <<< body
            # 		[7] [CallExpression] (2 children) <<< expression
            # 			[8] [Identifier:"foo"] (0 children) <<< callee
            # 			[9] [Identifier:"x"] (0 children) <<< arguments
            self.assertEqual(
                42,
                pdg.get_child("ExpressionStatement")
                    .get_child("CallExpression")
                    .children[1]
                    .static_eval(allow_partial_eval)
            )

            # Test object:
            code = """
            const x = {"foo": "bar", a: "b", 11: 22};
            foo(x);
            """
            pdg = generate_pdg(code)
            print(pdg)
            self.assertEqual(
                {"foo": "bar", "a": "b", 11: 22},
                pdg.get_child("ExpressionStatement")
                .get_child("CallExpression")
                .children[1]
                .static_eval(allow_partial_eval)
            )

            # A built-in function is *not* overridden by a user-defined function:
            code = """
            foo(parseInt('42'));
            """
            pdg = generate_pdg(code)
            print(pdg)
            self.assertEqual(
                42,
                pdg.get_child("ExpressionStatement")
                .get_child("CallExpression")
                .children[1]
                .static_eval(allow_partial_eval)
            )

            # A built-in function *is* overridden by a user-defined function:
            for code in [
                """
                function parseInt(x) { return 43; }
                foo(parseInt('42'));
                """,
                """
                {parseInt = function (x) { return 43; }}
                foo(parseInt('42'));
                """,
                """
                var parseInt = function (x) { return 43; }
                foo(parseInt('42'));
                """,
                """
                let parseInt = function (x) { return 43; }
                foo(parseInt('42'));
                """,
                """
                const parseInt = function (x) { return 43; }
                foo(parseInt('42'));
                """,
                """
                {parseInt = (x) => { return 43; }}
                foo(parseInt('42'));
                """,
                """
                var parseInt = (x) => { return 43; }
                foo(parseInt('42'));
                """,
                """
                let parseInt = (x) => { return 43; }
                foo(parseInt('42'));
                """,
                """
                const parseInt = (x) => { return 43; }
                foo(parseInt('42'));
                """
            ]:
                pdg = generate_pdg(code)
                print(pdg)
                self.assertRaises(
                    StaticEvalException,
                    lambda: (pdg.get_child("ExpressionStatement")
                                .get_child("CallExpression")
                                .children[1]
                                .static_eval(allow_partial_eval))
                )
                # ToDo: replace with self.assertEqual(43, ...) once static_eval() is capable of evaluating user-defined
                #       pure functions statically (which will only work for 'const' though!)

        # Test partial evaluation of objects:
        code = """
        const x = {"foo": "bar", a: foo(x), 11: 22};
        foo(x);
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(
            {"foo": "bar", "a": None, 11: 22},
            pdg.get_child("ExpressionStatement")
            .get_child("CallExpression")
            .children[1]
            .static_eval(allow_partial_eval=True)
        )

        # Test partial evaluation of arrays/lists:
        code = """
        const x = [111, foo(bar), 333];
        foo(x);
        """
        pdg = generate_pdg(code)
        print(pdg)
        self.assertEqual(
            [111, None, 333],
            pdg.get_child("ExpressionStatement")
            .get_child("CallExpression")
            .children[1]
            .static_eval(allow_partial_eval=True)
        )

    def test_is_unreachable(self):
        # Basic example:
        code = """
        foo();
        if (1==1) {
            bar();
        } else {
            baz();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        bar = pdg.get_identifier_by_name("bar")
        self.assertFalse(bar.is_unreachable())
        baz = pdg.get_identifier_by_name("baz")
        self.assertTrue(baz.is_unreachable())

        # The same basic example but with the test expression evaluating to False instead of True now:
        code = """
        foo();
        if (1!=1) {
            bar();
        } else {
            baz();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        bar = pdg.get_identifier_by_name("bar")
        self.assertTrue(bar.is_unreachable())
        baz = pdg.get_identifier_by_name("baz")
        self.assertFalse(baz.is_unreachable())

        # The same basic example but w/o the else branch:
        code = """
        foo();
        if (1!=1) {
            bar();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        bar = pdg.get_identifier_by_name("bar")
        self.assertTrue(bar.is_unreachable())

        # Test more complex static evaluation of the test expression:
        code = """
        const x = false || (10 < 5); // evaluates to false
        if (x) {
            bar();
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        bar = pdg.get_identifier_by_name("bar")
        self.assertTrue(bar.is_unreachable())

        # Nested if statements #1:
        code = """
        if (1==1) {
            if (2==2) {
                a();
            } else {
                b();
            }
        } else {
            if (3==3) {
                c();
            } else {
                d();
            }
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        a = pdg.get_identifier_by_name("a")
        b = pdg.get_identifier_by_name("b")
        c = pdg.get_identifier_by_name("c")
        d = pdg.get_identifier_by_name("d")
        self.assertFalse(a.is_unreachable())
        self.assertTrue(b.is_unreachable())
        self.assertTrue(c.is_unreachable())
        self.assertTrue(d.is_unreachable())

        # Nested if statements #2:
        code = """
        if (1!=1) {
            if (2!=2) {
                a();
            } else {
                b();
            }
        } else {
            if (3!=3) {
                c();
            } else {
                d();
            }
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        a = pdg.get_identifier_by_name("a")
        b = pdg.get_identifier_by_name("b")
        c = pdg.get_identifier_by_name("c")
        d = pdg.get_identifier_by_name("d")
        self.assertTrue(a.is_unreachable())
        self.assertTrue(b.is_unreachable())
        self.assertTrue(c.is_unreachable())
        self.assertFalse(d.is_unreachable())

    def test_get_data_flow_parents_in_order_no_split(self):
        code = """
        a = 1;
        b = 2;
        c = a + b;
        d = c;
        e = d;
        f = e;
        g = f;
        """
        pdg = generate_pdg(code)
        print(pdg)
        g = pdg.get_identifier_by_name("g")
        data_flow_parents_in_order_no_split: List[Node] = g.get_data_flow_parents_in_order_no_split()
        data_flow_parents_in_order_no_split: List[str] = [p.attributes['name'] for p in data_flow_parents_in_order_no_split]
        print(data_flow_parents_in_order_no_split)
        self.assertEqual(
            data_flow_parents_in_order_no_split,
            ['g', 'f', 'f', 'e', 'e', 'd', 'd', 'c', 'c']
        )

    def test_is_in_same_loop_as(self):
        code = """
        while (1) {
            let x;
            let y;
        }
        let z; // not inside *any* loop
        """
        pdg = generate_pdg(code)
        print(pdg)
        x = pdg.get_identifier_by_name("x")
        y = pdg.get_identifier_by_name("y")
        z = pdg.get_identifier_by_name("z")
        self.assertTrue(x.is_in_same_loop_as(y))
        self.assertTrue(y.is_in_same_loop_as(x))
        self.assertFalse(z.is_in_same_loop_as(x))
        self.assertFalse(z.is_in_same_loop_as(y))
        self.assertFalse(x.is_in_same_loop_as(z))
        self.assertFalse(y.is_in_same_loop_as(z))

        # Edge case: self == other:
        self.assertTrue(x.is_in_same_loop_as(x))
        self.assertTrue(y.is_in_same_loop_as(y))
        self.assertFalse(z.is_in_same_loop_as(z))

    def test_get_all_identifiers_not_inside_a_as_iter(self):
        code = """
        let compute_and_print = (x) => {console.log(x**2);}; 
        """
        pdg = generate_pdg(code)
        print(pdg)
        variable_declarator = pdg.get_child("VariableDeclaration")\
                                 .get_child("VariableDeclarator")
        arrow_func_expr = variable_declarator.get("init")[0]
        self.assertEqual(0, len(list(arrow_func_expr.get_all_identifiers_not_inside_a_as_iter(
            forbidden_parent_names=["ArrowFunctionExpression"],
            include_self=True,
        ))))
        self.assertEqual(4, len(list(arrow_func_expr.get_all_identifiers_not_inside_a_as_iter(
            forbidden_parent_names=["ArrowFunctionExpression"],
            include_self=False,
        ))))  # the 4 identifiers being "x", "console", "log", and, again, "x"

    def test_call_expression_is_IIFE_and_is_IIFE_call_expression(self):
        self.assertFalse(Node.identifier("foo").is_IIFE_call_expression())

        # Negative example:
        code = "foo(bar, baz);"
        pdg = generate_pdg(code)
        print(pdg)
        call_expression: Node = pdg.find_pattern(Node("CallExpression"),
                                                 match_identifier_names=False,
                                                 match_literals=False,
                                                 match_operators=False,
                                                 allow_additional_children=True,
                                                 allow_different_child_order=False)[0]
        self.assertFalse(call_expression.call_expression_is_IIFE())
        self.assertFalse(call_expression.is_IIFE_call_expression())

        # Positive examples:
        for code in [
            # Examples taken from: https://en.wikipedia.org/wiki/Immediately_invoked_function_expression
            "(function () { /* ... */ })();",
            "(function () { /* ... */ }());",
            "(() => { /* ... */ })();",
            "!function () { /* ... */ }();",
            "~function () { /* ... */ }();",
            "-function () { /* ... */ }();",
            "+function () { /* ... */ }();",
            "void function () { /* ... */ }();",
            "delete function () { /* ... */ }();",
            "typeof function () { /* ... */ }();",
            "await function () { /* ... */ }();",
            "let f = function () { /* ... */ }();",
            "true && function () { /* ... */ }();",
            "0, function () { /* ... */ }();",
            "(function(a, b) { /* ... */ })('hello', 'world');",
        ]:
            pdg = generate_pdg(code)
            print(pdg)
            call_expression: Node = pdg.find_pattern(Node("CallExpression"),
                                                     match_identifier_names=False,
                                                     match_literals=False,
                                                     match_operators=False,
                                                     allow_additional_children=True,
                                                     allow_different_child_order=False)[0]
            self.assertTrue(call_expression.call_expression_is_IIFE())
            self.assertTrue(call_expression.is_IIFE_call_expression())

    def test_return_statement_get_function(self):
        code = """
        function double(x) {
            return 2*x;
        }
        """
        pdg = generate_pdg(code)
        print(pdg)
        return_statement: Node = pdg.find_pattern(Node("ReturnStatement"),
                                                  match_identifier_names=False,
                                                  match_literals=False,
                                                  match_operators=False,
                                                  allow_additional_children=True,
                                                  allow_different_child_order=False)[0]
        f = return_statement.return_statement_get_function()
        self.assertEqual(f.name, "FunctionDeclaration")


if __name__ == '__main__':
    unittest.main()
