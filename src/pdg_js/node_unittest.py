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

    def test_any_literal_inside_matches_full_regex(self):
        pdg = Node("Literal", attributes={"raw": "3.14"})
        self.assertTrue(pdg.any_literal_inside_matches_full_regex("\d\\.\d\d"))
        self.assertFalse(pdg.any_literal_inside_matches_full_regex("\d\\.\d"))

    def test_any_literal_inside_contains_regex(self):
        pdg = Node("Literal", attributes={"raw": "1"})
        self.assertTrue(pdg.any_literal_inside_contains_regex("\d"))
        self.assertFalse(pdg.any_literal_inside_contains_regex("\D"))

        pdg = Node("Literal", attributes={"raw": "3.14"})
        self.assertTrue(pdg.any_literal_inside_contains_regex("^\d\\.\d\d$"))
        self.assertFalse(pdg.any_literal_inside_contains_regex("^\d\\.\d$"))

        pdg = Node("Literal", attributes={"raw": "'https://www.admin.com'"})
        self.assertTrue(pdg.any_literal_inside_contains_regex("https:\\/\\/"))
        self.assertFalse(pdg.any_literal_inside_contains_regex("^https:\\/\\/$"))

    def test_any_string_literal_inside_matches_full_regex(self):
        pdg = Node("Literal", attributes={"raw": "'https://www.admin.com'"})
        self.assertTrue(pdg.any_string_literal_inside_matches_full_regex("https:\/\/.+"))
        self.assertFalse(pdg.any_string_literal_inside_matches_full_regex("'https:\/\/.+"))

    def test_any_string_literal_inside_contains_regex(self):
        pdg = Node("Literal", attributes={"raw": "'Hello World'"})
        self.assertTrue(pdg.any_string_literal_inside_contains_regex("Hello"))
        self.assertFalse(pdg.any_string_literal_inside_contains_regex("'Hello"))


if __name__ == '__main__':
    unittest.main()
