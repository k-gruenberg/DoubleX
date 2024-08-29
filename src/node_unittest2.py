# Some unit tests of the "Node" class can't be done inside "node_unittest.py" because of import difficulties.

import os
import tempfile
import unittest

from src.get_pdg import get_pdg
from src.pdg_js.build_pdg import get_data_flow
from src.kim_and_lee_vulnerability_detection import add_missing_data_flow_edges

os.environ['PARSER'] = "espree"
os.environ['SOURCE_TYPE'] = "module"


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
    no_added_df_edges_cs = add_missing_data_flow_edges(pdg)
    print(f"{no_added_df_edges_cs} missing data flows edges added to PDG")
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


if __name__ == '__main__':
    unittest.main()
