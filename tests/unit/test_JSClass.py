import unittest
import os

from src.pdg_js.JSClass import JSClass
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


class TestJSClass(unittest.TestCase):
    def test_JSClass(self):
        code = """
        class C {
            constructor(x, y) {
                this.x = x;
                this.y = y;
            }
            static foo(a) {
                return a;
            }
            static foo(b,c) {
                return b+c;
            }
            foo(d) {
                return 2*d;
            }
            foo(e,f) {
                return 2*(e+f);
            }
        }
        console.log(C.foo(1,2)); // prints 3
        let c = new C(100,200);
        console.log(c.foo(3,4)); // prints 14
        """
        pdg = generate_pdg(code)
        print(pdg)
        class_decl: Node = pdg.get_all("ClassDeclaration")[0]
        js_class: JSClass = JSClass(class_decl)
        self.assertEqual("C", js_class.get_name())
        self.assertIsNotNone(js_class.get_class_body())
        self.assertEqual(
            "MethodDefinition",
            js_class.get_static_method("foo", return_as_func=False).name
        )
        self.assertEqual(
            "MethodDefinition",
            js_class.get_non_static_method("foo", return_as_func=False).name
        )
        # Test get_static_method():
        static_foo: Func = js_class.get_static_method("foo", return_as_func=True)
        self.assertEqual(["b", "c"], [p.attributes['name'] for p in static_foo.get_params()])
        # Test get_non_static_method():
        non_static_foo: Func = js_class.get_non_static_method("foo", return_as_func=True)
        self.assertEqual(["e", "f"], [p.attributes['name'] for p in non_static_foo.get_params()])
