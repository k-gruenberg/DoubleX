import unittest
from typing import List

from DataFlow import is_uxss_sanitizing_regex_pattern, DataFlow
from DataFlowsConsidered import DataFlowsConsidered
from pdg_js.node import Node
from unit.test_node2 import generate_pdg


class TestDataFlow(unittest.TestCase):
    def test_is_uxss_sanitizing_regex_pattern(self):
        # Positive examples (cf. doc comment):
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"\W"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^\w]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"\D"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^\d]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^a-zA-Z0-9_]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^a-z]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^a-zA-Z]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^a-z0-9]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^A-Z0-9]"))
        self.assertTrue(is_uxss_sanitizing_regex_pattern(r"[^0-9]"))

        # Negative examples:
        self.assertFalse(is_uxss_sanitizing_regex_pattern(r"$"))
        self.assertFalse(is_uxss_sanitizing_regex_pattern(r"foobar"))
        self.assertFalse(is_uxss_sanitizing_regex_pattern(r"<script>"))
        self.assertFalse(is_uxss_sanitizing_regex_pattern(r"<SCRIPT>"))
        self.assertFalse(is_uxss_sanitizing_regex_pattern(r"<script>|<SCRIPT>"))

    def test_from_flow_is_correctly_uxss_sanitized(self):
        # Positive examples:
        for code in [
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(source.replaceAll(/\W/g, ""));
            """,
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(source.replace(/\W/g, ""));
            """,
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(parseInt(source));
            """,
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(parseFloat(source));
            """
        ]:
            print(code)
            pdg: Node = generate_pdg(code)
            source: Node = pdg.get_all_identifiers_by_name("source")[0]
            data_flows: List[DataFlow] = DataFlow.beginning_at(initial_node=source)[0].get_continued_flows(
                data_flows_considered=DataFlowsConsidered.DIJKSTRA_LEAVES
            )
            self.assertEqual(len(data_flows), 1)
            data_flow: DataFlow = data_flows[0]
            self.assertTrue(data_flow.from_flow_is_correctly_uxss_sanitized())

        # Negative examples:
        for code in [
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(source.replaceAll(/<script>/g, ""));
            """,
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(source.replace(/\W/, ""));
            """,
            r"""
            let source = "<script>alert('UXSS');</script>"
            sink(foobar(source));
            """
        ]:
            print(code)
            pdg: Node = generate_pdg(code)
            source: Node = pdg.get_all_identifiers_by_name("source")[0]
            data_flows: List[DataFlow] = DataFlow.beginning_at(initial_node=source)[0].get_continued_flows(
                data_flows_considered=DataFlowsConsidered.DIJKSTRA_LEAVES
            )
            self.assertEqual(len(data_flows), 1)
            data_flow: DataFlow = data_flows[0]
            self.assertFalse(data_flow.from_flow_is_correctly_uxss_sanitized())
