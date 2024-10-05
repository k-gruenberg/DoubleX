import unittest

from src.pdg_js.node import Node


class TestNodeClass(unittest.TestCase):
    def test_equivalent(self):
        # Implicitly also tests the matches() function as equivalent() simply calls matches() with certain params:

        # For Identifiers, names are compared.
        identifier1 = Node("Identifier", attributes={"name": "foo"})
        identifier2 = Node("Identifier", attributes={"name": "foo"})
        identifier3 = Node("Identifier", attributes={"name": "bar"})
        self.assertTrue(identifier1.equivalent(identifier1))
        self.assertTrue(identifier1.equivalent(identifier2))
        self.assertTrue(identifier2.equivalent(identifier1))
        self.assertFalse(identifier1.equivalent(identifier3))
        self.assertFalse(identifier3.equivalent(identifier1))
        self.assertFalse(identifier2.equivalent(identifier3))
        self.assertFalse(identifier3.equivalent(identifier2))

        # For Literals, raw literal values are compared:
        literal1 = Node("Literal", attributes={"raw": "'Hello World'"})
        literal2 = Node("Literal", attributes={"raw": "'Hello World'"})
        literal3 = Node("Literal", attributes={"raw": "'Bye World'"})
        self.assertTrue(literal1.equivalent(literal1))
        self.assertTrue(literal1.equivalent(literal2))
        self.assertTrue(literal2.equivalent(literal1))
        self.assertFalse(literal1.equivalent(literal3))
        self.assertFalse(literal3.equivalent(literal1))
        self.assertFalse(literal2.equivalent(literal3))
        self.assertFalse(literal3.equivalent(literal2))

        # For BinaryExpressions, LogicalExpressions, UnaryExpressions, AssignmentExpressions and UpdateExpressions,
        #   operators are compared:

        # BinaryExpression, LogicalExpression, AssignmentExpression:
        for (expr_type, op_name1, op_name2) in [
            ("BinaryExpression", "==", "!="),
            ("LogicalExpression", "&&", "||"),
            ("AssignmentExpression", "+=", "-=")
        ]:
            expression1 = Node(expr_type, attributes={"operator": op_name1})\
                                  .child(Node("Identifier", attributes={"name": "x"}))\
                                  .child(Node("Identifier", attributes={"name": "y"}))

            expression2 = Node(expr_type, attributes={"operator": op_name2}) \
                .child(Node("Identifier", attributes={"name": "x"})) \
                .child(Node("Identifier", attributes={"name": "y"}))

            expression3 = Node(expr_type, attributes={"operator": op_name2}) \
                .child(Node("Identifier", attributes={"name": "x"})) \
                .child(Node("Identifier", attributes={"name": "z"}))

            self.assertTrue(expression1.equivalent(expression1))
            self.assertFalse(expression1.equivalent(expression2))
            self.assertFalse(expression2.equivalent(expression1))
            self.assertFalse(expression2.equivalent(expression3))
            self.assertFalse(expression3.equivalent(expression2))

        # UnaryExpression, UpdateExpression:
        for (expr_type, op_name1, op_name2) in [
            ("UnaryExpression", "+", "-"),
            ("UpdateExpression", "++", "--")
        ]:
            expression1 = Node(expr_type, attributes={"operator": op_name1}) \
                .child(Node("Identifier", attributes={"name": "x"}))

            expression2 = Node(expr_type, attributes={"operator": op_name2}) \
                .child(Node("Identifier", attributes={"name": "x"}))

            expression3 = Node(expr_type, attributes={"operator": op_name2}) \
                .child(Node("Identifier", attributes={"name": "z"}))

            self.assertTrue(expression1.equivalent(expression1))
            self.assertFalse(expression1.equivalent(expression2))
            self.assertFalse(expression2.equivalent(expression1))
            self.assertFalse(expression2.equivalent(expression3))
            self.assertFalse(expression3.equivalent(expression2))

        # Otherwise, number of children, order of children and child names are compared for equality:

        # Child names:
        self.assertTrue(Node("ReturnStatement").equivalent(Node("ReturnStatement")))
        self.assertFalse(Node("ReturnStatement").equivalent(identifier1))
        self.assertFalse(identifier1.equivalent(Node("ReturnStatement")))

        # Number of children:
        pdg_2_children = Node("IfStatement")\
                            .child(Node("Literal", attributes={"raw": "1"}))\
                            .child(Node("BlockStatement"))
        pdg_3_children = Node("IfStatement")\
                            .child(Node("Literal", attributes={"raw": "1"}))\
                            .child(Node("BlockStatement"))\
                            .child(Node("BlockStatement"))
        self.assertTrue(pdg_2_children.equivalent(pdg_2_children))
        self.assertTrue(pdg_3_children.equivalent(pdg_3_children))
        self.assertFalse(pdg_2_children.equivalent(pdg_3_children))
        self.assertFalse(pdg_3_children.equivalent(pdg_2_children))

        # Order of children:
        pdg_order1 = Node("BinaryExpression", attributes={"operator": "+"})\
                            .child(Node("Literal", attributes={"raw": "1"}))\
                            .child(Node("Literal", attributes={"raw": "2"}))
        pdg_order2 = Node("BinaryExpression", attributes={"operator": "+"})\
                            .child(Node("Literal", attributes={"raw": "2"}))\
                            .child(Node("Literal", attributes={"raw": "1"}))
        self.assertTrue(pdg_order1.equivalent(pdg_order1))
        self.assertTrue(pdg_order2.equivalent(pdg_order2))
        self.assertFalse(pdg_order1.equivalent(pdg_order2))
        self.assertFalse(pdg_order2.equivalent(pdg_order1))

    def test_matches(self):
        # Test match_identifier_names argument:
        args = {
            "match_literals": True,
            "match_operators": True,
            "allow_additional_children": False,
            "allow_different_child_order": True
        }
        expression1 = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Identifier", attributes={"name": "x"})) \
            .child(Node("Identifier", attributes={"name": "y"}))
        expression2 = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Identifier", attributes={"name": "x"})) \
            .child(Node("Identifier", attributes={"name": "z"}))
        # Test that each expression matches itself, no matter the value of match_identifier_names:
        self.assertTrue(expression1.matches(expression1, match_identifier_names=True, **args))
        self.assertTrue(expression1.matches(expression1, match_identifier_names=False, **args))
        self.assertTrue(expression2.matches(expression2, match_identifier_names=True, **args))
        self.assertTrue(expression2.matches(expression2, match_identifier_names=False, **args))
        # Test match_identifier_names=False:
        self.assertTrue(expression1.matches(expression2, match_identifier_names=False, **args))
        self.assertTrue(expression2.matches(expression1, match_identifier_names=False, **args))
        # Test match_identifier_names=True:
        self.assertFalse(expression1.matches(expression2, match_identifier_names=True, **args))
        self.assertFalse(expression2.matches(expression1, match_identifier_names=True, **args))

        # Test match_literals argument:
        args = {
            "match_identifier_names": True,
            "match_operators": True,
            "allow_additional_children": False,
            "allow_different_child_order": False
        }
        expression1 = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'"})) \
            .child(Node("Literal", attributes={"raw": "'y'"}))
        expression2 = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'"})) \
            .child(Node("Literal", attributes={"raw": "'z'"}))
        # Test that each expression matches itself, no matter the value of match_literals:
        self.assertTrue(expression1.matches(expression1, match_literals=True, **args))
        self.assertTrue(expression1.matches(expression1, match_literals=False, **args))
        self.assertTrue(expression2.matches(expression2, match_literals=True, **args))
        self.assertTrue(expression2.matches(expression2, match_literals=False, **args))
        # Test match_literals=False:
        self.assertTrue(expression1.matches(expression2, match_literals=False, **args))
        self.assertTrue(expression2.matches(expression1, match_literals=False, **args))
        # Test match_literals=True:
        self.assertFalse(expression1.matches(expression2, match_literals=True, **args))
        self.assertFalse(expression2.matches(expression1, match_literals=True, **args))

        # Test match_operators argument:
        args = {
            "match_identifier_names": True,
            "match_literals": True,
            "allow_additional_children": False,
            "allow_different_child_order": True
        }
        expression1 = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Identifier", attributes={"name": "x"})) \
            .child(Node("Identifier", attributes={"name": "y"}))
        expression2 = Node("BinaryExpression", attributes={"operator": "-"}) \
            .child(Node("Identifier", attributes={"name": "x"})) \
            .child(Node("Identifier", attributes={"name": "y"}))
        # Test that each expression matches itself, no matter the value of match_operators:
        self.assertTrue(expression1.matches(expression1, match_operators=True, **args))
        self.assertTrue(expression1.matches(expression1, match_operators=False, **args))
        self.assertTrue(expression2.matches(expression2, match_operators=True, **args))
        self.assertTrue(expression2.matches(expression2, match_operators=False, **args))
        # Test match_operators=False:
        self.assertTrue(expression1.matches(expression2, match_operators=False, **args))
        self.assertTrue(expression2.matches(expression1, match_operators=False, **args))
        # Test match_operators=True:
        self.assertFalse(expression1.matches(expression2, match_operators=True, **args))
        self.assertFalse(expression2.matches(expression1, match_operators=True, **args))

        # Test allow_additional_children argument:
        args = {
            "match_identifier_names": False,
            "match_literals": True,
            "match_operators": True,
            "allow_different_child_order": False
        }
        pdg_2_children = Node("IfStatement") \
            .child(Node("Literal", attributes={"raw": "1"})) \
            .child(Node("BlockStatement"))
        pdg_3_children = Node("IfStatement") \
            .child(Node("Literal", attributes={"raw": "1"})) \
            .child(Node("BlockStatement")) \
            .child(Node("BlockStatement"))
        # Both PDGs match themselves, no matter the allow_additional_children argument:
        self.assertTrue(pdg_2_children.matches(pdg_2_children, allow_additional_children=True, **args))
        self.assertTrue(pdg_2_children.matches(pdg_2_children, allow_additional_children=False, **args))
        self.assertTrue(pdg_3_children.matches(pdg_3_children, allow_additional_children=True, **args))
        self.assertTrue(pdg_3_children.matches(pdg_3_children, allow_additional_children=False, **args))
        # pdg_3_children matches the pdg_2_children pattern if and only if allow_additional_children=True:
        self.assertTrue(pdg_3_children.matches(pattern=pdg_2_children, allow_additional_children=True, **args))
        self.assertFalse(pdg_3_children.matches(pattern=pdg_2_children, allow_additional_children=False, **args))

        # Test allow_different_child_order argument:
        args = {
            "match_identifier_names": False,
            "match_literals": True,
            "match_operators": True,
            "allow_additional_children": False
        }
        pdg_order1 = Node("BinaryExpression", attributes={"operator": "+"})\
            .child(Node("Literal", attributes={"raw": "1"}))\
            .child(Node("Literal", attributes={"raw": "2"}))
        pdg_order2 = Node("BinaryExpression", attributes={"operator": "+"})\
            .child(Node("Literal", attributes={"raw": "2"}))\
            .child(Node("Literal", attributes={"raw": "1"}))
        # Both PDGs match themselves, no matter the allow_different_child_order argument:
        self.assertTrue(pdg_order1.matches(pdg_order1, allow_different_child_order=True, **args))
        self.assertTrue(pdg_order1.matches(pdg_order1, allow_different_child_order=False, **args))
        self.assertTrue(pdg_order2.matches(pdg_order2, allow_different_child_order=True, **args))
        self.assertTrue(pdg_order2.matches(pdg_order2, allow_different_child_order=False, **args))
        # The PDGs match each other when allow_different_child_order=True:
        self.assertTrue(pdg_order1.matches(pdg_order2, allow_different_child_order=True, **args))
        self.assertTrue(pdg_order2.matches(pdg_order1, allow_different_child_order=True, **args))
        # The PDGs do NOT match each other when allow_different_child_order=False:
        self.assertFalse(pdg_order1.matches(pdg_order2, allow_different_child_order=False, **args))
        self.assertFalse(pdg_order2.matches(pdg_order1, allow_different_child_order=False, **args))

    def test_string_literal_without_quotation_marks(self):
        literal1 = Node("Literal", attributes={"raw": "'Hello World'", "value": "Hello World"})
        literal2 = Node("Literal", attributes={"raw": "\"Hello World\"", "value": "Hello World"})
        self.assertEqual(literal1.string_literal_without_quotation_marks(), "Hello World")
        self.assertEqual(literal2.string_literal_without_quotation_marks(), "Hello World")
        # Note that while `strings` enclosed in backticks are possible in JavaScript, they generate a "TemplateLiteral"
        #     Node instead of a "Literal" Node as they are vastly more complex. We shall not consider those!

    def test_string_literal_matches_full_regex(self):
        string_literal = Node("Literal", attributes={"raw": "'https://www.admin.com'",
                                                           "value": "https://www.admin.com"})
        self.assertTrue(string_literal.string_literal_matches_full_regex(r"https:\/\/.+"))
        self.assertFalse(string_literal.string_literal_matches_full_regex(r"'https:\/\/.+"))

    def test_string_literal_contains_regex(self):
        string_literal = Node("Literal", attributes={"raw": "'Hello World'", "value": "Hello World"})
        self.assertTrue(string_literal.string_literal_contains_regex("Hello"))
        self.assertFalse(string_literal.string_literal_contains_regex("'Hello"))

    def test_any_literal_inside_matches_full_regex(self):
        pdg = Node("Literal", attributes={"raw": "3.14", "value": 3.14})
        self.assertTrue(pdg.any_literal_inside_matches_full_regex(r"\d\.\d\d"))
        self.assertFalse(pdg.any_literal_inside_matches_full_regex(r"\d\.\d"))

    def test_any_literal_inside_contains_regex(self):
        pdg = Node("Literal", attributes={"raw": "1", "value": 1})
        self.assertTrue(pdg.any_literal_inside_contains_regex(r"\d"))
        self.assertFalse(pdg.any_literal_inside_contains_regex(r"\D"))

        pdg = Node("Literal", attributes={"raw": "3.14", "value": 3.14})
        self.assertTrue(pdg.any_literal_inside_contains_regex(r"^\d\.\d\d$"))
        self.assertFalse(pdg.any_literal_inside_contains_regex(r"^\d\.\d$"))

        pdg = Node("Literal", attributes={"raw": "'https://www.admin.com'", "value": "https://www.admin.com"})
        self.assertTrue(pdg.any_literal_inside_contains_regex(r"https:\/\/"))
        self.assertFalse(pdg.any_literal_inside_contains_regex(r"^https:\/\/$"))

    def test_any_string_literal_inside_matches_full_regex(self):
        pdg = Node("Literal", attributes={"raw": "'https://www.admin.com'", "value": "https://www.admin.com"})
        self.assertTrue(pdg.any_string_literal_inside_matches_full_regex(r"https:\/\/.+"))
        self.assertFalse(pdg.any_string_literal_inside_matches_full_regex(r"'https:\/\/.+"))

    def test_any_string_literal_inside_contains_regex(self):
        pdg = Node("Literal", attributes={"raw": "'Hello World'", "value": "Hello World"})
        self.assertTrue(pdg.any_string_literal_inside_contains_regex("Hello"))
        self.assertFalse(pdg.any_string_literal_inside_contains_regex("'Hello"))

    def test_get_height(self):
        pdg = Node("Program")
        self.assertEqual(pdg.get_height(), 1)

        pdg = Node("Program")\
                .child(
                    Node("BlockStatement")
                )
        self.assertEqual(pdg.get_height(), 2)

        pdg = Node("Program")\
                .child(
                    Node("ExpressionStatement")
                        .child(
                            Node("Literal", attributes={"raw": 42})
                        )
                )
        self.assertEqual(pdg.get_height(), 3)

    def test_get_sibling_by_name(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        self.assertEqual(len(expression.children), 2)
        [sibling1, sibling2] = expression.children
        self.assertEqual(sibling1.get_sibling_by_name("Literal"), sibling2)
        self.assertEqual(sibling2.get_sibling_by_name("Literal"), sibling1)

    def test_get_only_sibling(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        self.assertEqual(len(expression.children), 2)
        [sibling1, sibling2] = expression.children
        self.assertEqual(sibling1.get_only_sibling(), sibling2)
        self.assertEqual(sibling2.get_only_sibling(), sibling1)

    def test_has_sibling(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        self.assertEqual(len(expression.children), 2)
        [sibling1, sibling2] = expression.children
        self.assertTrue(sibling1.has_sibling("Literal"))
        self.assertTrue(sibling2.has_sibling("Literal"))

    def test_count_siblings(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        self.assertEqual(len(expression.children), 2)
        [sibling1, sibling2] = expression.children
        self.assertEqual(sibling1.count_siblings(), 1)
        self.assertEqual(sibling2.count_siblings(), 1)

    def test_root(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        self.assertEqual(expression.root(), expression)
        [literal1, literal2] = expression.children
        self.assertEqual(literal1.root(), expression)
        self.assertEqual(literal1.root(), expression)

    def test_is_inside(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        [literal1, literal2] = expression.children
        self.assertTrue(literal1.is_inside(expression))
        self.assertTrue(literal2.is_inside(expression))
        self.assertFalse(expression.is_inside(literal1))
        self.assertFalse(expression.is_inside(literal2))

    def test_is_nth_child_of_a(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        [literal1, literal2] = expression.children

        self.assertTrue(literal1.is_nth_child_of_a(0, ["BinaryExpression"]))
        self.assertTrue(literal2.is_nth_child_of_a(1, ["BinaryExpression"]))
        self.assertTrue(literal1.is_nth_child_of_a(0, ["CallExpression", "BinaryExpression", "AssignmentExpression"]))
        self.assertTrue(literal2.is_nth_child_of_a(1, ["CallExpression", "BinaryExpression", "AssignmentExpression"]))

        self.assertFalse(literal1.is_nth_child_of_a(1, ["BinaryExpression"]))
        self.assertFalse(literal2.is_nth_child_of_a(0, ["BinaryExpression"]))
        self.assertFalse(expression.is_nth_child_of_a(0, ["Literal"]))
        self.assertFalse(expression.is_nth_child_of_a(1, ["Literal"]))

    def test1_is_within_the_nth_child_of_a(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        [literal1, literal2] = expression.children

        self.assertTrue(literal1.is_within_the_nth_child_of_a(0, ["BinaryExpression"]))
        self.assertTrue(literal2.is_within_the_nth_child_of_a(1, ["BinaryExpression"]))
        self.assertTrue(literal1.is_within_the_nth_child_of_a(0, ["CallExpression", "BinaryExpression", "AssignmentExpression"]))
        self.assertTrue(literal2.is_within_the_nth_child_of_a(1, ["CallExpression", "BinaryExpression", "AssignmentExpression"]))

        self.assertFalse(literal1.is_within_the_nth_child_of_a(1, ["BinaryExpression"]))
        self.assertFalse(literal2.is_within_the_nth_child_of_a(0, ["BinaryExpression"]))
        self.assertFalse(expression.is_within_the_nth_child_of_a(0, ["Literal"]))
        self.assertFalse(expression.is_within_the_nth_child_of_a(1, ["Literal"]))

    def test2_is_within_the_nth_child_of_a(self):
        # (a+b)||(x+y)
        expression: Node = Node("LogicalExpression", attributes={"operator": "||"})\
            .child(
                Node("BinaryExpression", attributes={"operator": "+"})
                    .child(Node("Identifier", attributes={"name": "a"}))
                    .child(Node("Identifier", attributes={"name": "b"}))
            )\
            .child(
                Node("BinaryExpression", attributes={"operator": "+"})
                    .child(Node("Identifier", attributes={"name": "x"}))
                    .child(Node("Identifier", attributes={"name": "y"}))
            )
        # print(expression) # will raise an AttributeError as __data_dep_children is None for the Identifiers!
        a = expression.get_identifier_by_name("a")
        b = expression.get_identifier_by_name("b")
        x = expression.get_identifier_by_name("x")
        y = expression.get_identifier_by_name("y")

        self.assertTrue(a.is_within_the_nth_child_of_a(0, ["LogicalExpression"]))
        self.assertTrue(b.is_within_the_nth_child_of_a(0, ["LogicalExpression"]))
        self.assertFalse(a.is_within_the_nth_child_of_a(1, ["LogicalExpression"]))
        self.assertFalse(b.is_within_the_nth_child_of_a(1, ["LogicalExpression"]))

        self.assertFalse(x.is_within_the_nth_child_of_a(0, ["LogicalExpression"]))
        self.assertFalse(y.is_within_the_nth_child_of_a(0, ["LogicalExpression"]))
        self.assertTrue(x.is_within_the_nth_child_of_a(1, ["LogicalExpression"]))
        self.assertTrue(y.is_within_the_nth_child_of_a(1, ["LogicalExpression"]))

    def test_lower(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        [literal1, literal2] = expression.children

        self.assertEqual(Node.lower(expression, literal1), literal1)
        self.assertEqual(Node.lower(literal1, expression), literal1)

        self.assertEqual(Node.lower(expression, literal2), literal2)
        self.assertEqual(Node.lower(literal2, expression), literal2)

        # Check if it returns `node1` when both nodes are equally low in the tree:
        self.assertEqual(Node.lower(literal1, literal2), literal1)
        self.assertEqual(Node.lower(literal2, literal1), literal2)

    def test_is_identifier_named(self):
        self.assertTrue(Node.identifier("foobar").is_identifier_named("foobar"))
        self.assertFalse(Node.identifier("foobar").is_identifier_named("foo"))
        self.assertFalse(Node("Program").is_identifier_named("foo"))

    def test_is_lhs_of_a_and_is_rhs_of_a(self):
        expression = Node("BinaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "'x'", "value": "x"})) \
            .child(Node("Literal", attributes={"raw": "'y'", "value": "y"}))
        print(expression)
        [literal1, literal2] = expression.children
        self.assertTrue(literal1.is_lhs_of_a("BinaryExpression"))
        self.assertTrue(literal1.is_lhs_of_a("BinaryExpression", allow_missing_rhs=False))
        self.assertTrue(literal1.is_lhs_of_a("BinaryExpression", allow_missing_rhs=True))
        self.assertTrue(literal2.is_rhs_of_a("BinaryExpression"))

        self.assertFalse(literal1.is_lhs_of_a("LogicalExpression"))
        self.assertFalse(literal1.is_lhs_of_a("LogicalExpression", allow_missing_rhs=False))
        self.assertFalse(literal1.is_lhs_of_a("LogicalExpression", allow_missing_rhs=True))
        self.assertFalse(literal2.is_rhs_of_a("LogicalExpression"))

        self.assertFalse(literal1.is_rhs_of_a("BinaryExpression"))
        self.assertFalse(literal2.is_lhs_of_a("BinaryExpression"))
        self.assertFalse(literal2.is_lhs_of_a("BinaryExpression", allow_missing_rhs=False))
        self.assertFalse(literal2.is_lhs_of_a("BinaryExpression", allow_missing_rhs=True))

        # Test allow_missing_rhs argument:
        expression = Node("UnaryExpression", attributes={"operator": "+"}) \
            .child(Node("Literal", attributes={"raw": "42", "value": 42}))
        print(expression)
        [literal1] = expression.children
        self.assertTrue(literal1.is_lhs_of_a("UnaryExpression", allow_missing_rhs=True))
        self.assertFalse(literal1.is_lhs_of_a("UnaryExpression", allow_missing_rhs=False))


if __name__ == '__main__':
    unittest.main()
