# Some unit tests of the "Node" class can't be done inside "node_unittest.py" because of import difficulties.

import os
import tempfile
import unittest

from get_pdg import get_pdg
from pdg_js.build_pdg import get_data_flow
from add_missing_data_flow_edges import add_missing_data_flow_edges
from remove_incorrect_data_flow_edges import remove_incorrect_data_flow_edges

os.environ['PARSER'] = "espree"
os.environ['SOURCE_TYPE'] = "module"
os.environ['DEBUG'] = "yes"
os.environ['TIMEOUT'] = "600"


def generate_pdg(code):
    tmp_file = tempfile.NamedTemporaryFile()
    with open(tmp_file.name, 'w') as f:
        f.write(code)

    # WARNING: Do NOT put the below code into the "with" block, it won't work!!!
    res_dict = dict()
    benchmarks = res_dict['benchmarks'] = dict()
    pdg = get_pdg(file_path=tmp_file.name, res_dict=benchmarks)
    # Note that for a very obscure reason
    #     src.get_pdg.get_pdg(file_path=tmp_file.name, res_dict=benchmarks)
    # is *NOT* equivalent to
    #     src.pdg_js.build_pdg.get_data_flow(tmp_file.name, benchmarks=benchmarks, store_pdgs=None, save_path_pdg=False,
    #                                        beautiful_print=False, check_json=False)
    # ...even though get_pdg() does nothing more than to call get_data_flow().
    # The reason for that is the isinstance(lhs, Identifier) check in add_missing_data_flow_edges(); isinstance()
    #     apparently somehow depends on how modules are imported, cf. https://bugs.python.org/issue1249615
    no_removed_df_edges = remove_incorrect_data_flow_edges(pdg)
    print(f"{no_removed_df_edges} incorrect data flows edges removed from PDG")
    no_added_df_edges = add_missing_data_flow_edges(pdg)
    print(f"{no_added_df_edges} missing data flows edges added to PDG")
    return pdg


class TestNodeClass2(unittest.TestCase):
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

        pdg = generate_pdg("foo.bar.baz")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz")

        pdg = generate_pdg("foo.bar.baz.boo")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "foo.bar.baz.boo")

        # More complex examples:

        pdg = generate_pdg("foo.bar().baz.boo")
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

        pdg = generate_pdg("this().bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this().bar")

        pdg = generate_pdg("this(x,y,z).bar")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "this().bar")

        # Test handling of Literals:

        pdg = generate_pdg("'foo'.length")
        member_expression = pdg.get_all("MemberExpression")[0]
        self.assertEqual(member_expression.member_expression_to_string(), "<literal>.length")

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
                         "<function_expression>")

        # A real-world example from the "ClassLink OneClick Extension",
        #   version 10.6, extension ID jgfbgkjjlonelmpenhpfeeljjlcgnkpe:
        pdg = generate_pdg("!function(t, n, e) { f.apply(this, arguments) }(l, t.data, n.frameId)")
        call_expression = pdg.get_all("CallExpression")[0]
        self.assertEqual(call_expression.call_expression_get_full_function_name(),
                         "<function_expression>")

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
        # [81] [Program] (2 children)
        # 	[87] [FunctionDeclaration] (3 children) --e--> [90] --e--> [89]
        # 		[90] [FunctionDeclaration] (2 children) --e--> [92]
        # 			[91] [Identifier:"foo"] (0 children) --data--> [101]     <--------- ...should refer to this!
        # 			[92] [BlockStatement] (1 child) --e--> [93]
        # 				[93] [ReturnStatement] (1 child)
        # 					[94] [Literal::{'raw': '2', 'value': 2}] (0 children)
        # 		[88] [Identifier:"bar"] (0 children)
        # 		[89] [BlockStatement] (1 child) --e--> [95]
        # 			[95] [ExpressionStatement] (1 child)
        # 				[96] [CallExpression] (2 children)
        # 					[97] [MemberExpression:"False"] (2 children)
        # 						[98] [Identifier:"console"] (0 children)
        # 						[99] [Identifier:"log"] (0 children)
        # 					[100] [CallExpression] (1 child)
        # 						[101] [Identifier:"foo"] (0 children)        <--------- This...
        # 	[82] [FunctionDeclaration] (2 children) --e--> [84]
        # 		[83] [Identifier:"foo"] (0 children)
        # 		[84] [BlockStatement] (1 child) --e--> [85]
        # 			[85] [ReturnStatement] (1 child)
        # 				[86] [Literal::{'raw': '1', 'value': 1}] (0 children)
        foos = [identifier for identifier in pdg.get_all_identifiers() if identifier.attributes['name'] == "foo"]
        self.assertEqual(len(foos), 3)
        function_identifier = [foo for foo in foos if foo.parent.name == "CallExpression"][0]
        correct_function_declaration = [foo.parent for foo in foos if foo.parent.name == "FunctionDeclaration"
                                                            and foo.grandparent().name == "FunctionDeclaration"][0]
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


if __name__ == '__main__':
    unittest.main()
