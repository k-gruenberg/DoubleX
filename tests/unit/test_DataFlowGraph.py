import unittest
import os

from DataFlowGraph import DataFlowGraph
from DataFlowsConsidered import DataFlowsConsidered
from src.pdg_js.node import Node


os.environ['PARSER'] = "espree"
os.environ['SOURCE_TYPE'] = "module"
os.environ['DEBUG'] = "no"
os.environ['TIMEOUT'] = "600"


def generate_pdg(code: str, ast_only=False) -> Node:
    res_dict = dict()
    benchmarks = res_dict['benchmarks'] = dict()

    return Node.pdg_from_string(
        js_code=code,
        benchmarks=benchmarks,
        add_my_data_flows=not ast_only,
    )


class TestDataFlowGraph(unittest.TestCase):
    def test_DataFlowGraph(self):
        # An example with (many!) splits:
        code = """
        let _1 = "data";
        let _2 = _1, _3 = _1;
        let _4 = _2 + _3;
        
        let _5 = _4, _6 = _4;
        let _7 = _5 + _6;
        
        let _8 = _7, _9 = _7;
        let _10 = _8 + _9;
        
        let _11 = _10, _12 = _10;
        let _13 = _11 + _12;
        
        let _14 = _13, _15 = _13;
        let _16 = _14 + _15;
        
        let _17 = _16, _18 = _16;
        let _19 = _17 + _18;
        
        let _20 = _19, _21 = _19;
        let _22 = _20 + _21;
        
        let _23 = _22, _24 = _22;
        let _25 = _23 + _24;
        
        let _26 = _25, _27 = _25;
        let _28 = _26 + _27;
        
        let _29 = _28, _30 = _28;
        let _31 = _29 + _30;
        
        let _32 = _31, _33 = _31;
        let _34 = _32 + _33;
        
        let _35 = _34, _36 = _34;
        let _37 = _35 + _36;
        
        let _38 = _37, _39 = _37;
        let _40 = _38 + _39;
        """
        pdg = generate_pdg(code)
        print(f"pdg =\n{pdg}")
        _1 = pdg.get_first_identifier_by_name("_1")
        print(f"_1 = {_1}")

        df_graph = DataFlowGraph(start_node=_1)
        print(f"df_graph =\n{df_graph}")
        self.assertEqual(df_graph.get_start_node(), _1)
        print(f"len(df_graph.get_nodes()) = {len(df_graph.get_nodes())}")
        self.assertEqual(len(df_graph.get_nodes()), len(pdg.get_all_identifiers()))
        # get_all_final_nodes() should only return one "final node": _40
        _40 = pdg.get_identifier_by_name("_40")
        self.assertEqual(df_graph.get_all_final_nodes(), [_40])
        # get_data_flows(ONE_PER_FINAL_NODE_SHORTEST) should only return 1 data flow, as there's only one "final node": _40
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_FINAL_NODE_SHORTEST)
        self.assertEqual(len(data_flows), 1)
        print(f"data_flows[0] = {data_flows[0]}")
        self.assertEqual(data_flows[0].last_node(), _40)
        # get_data_flows(ONE_PER_NODE_SHORTEST) should only return as many data flows as there are nodes:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_NODE_SHORTEST)
        self.assertEqual(len(data_flows), len(pdg.get_all_identifiers()))
        # get_data_flows(JUST_ONE) should, as the name suggests, return just 1 data flow:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.JUST_ONE)
        self.assertEqual(len(data_flows), 1)

        # An example with a loop and 0 "final nodes":
        code = """
        while (1) {
            x = y
            y = x
        }
        """
        pdg = generate_pdg(code)
        print(f"pdg =\n{pdg}")
        x = pdg.get_first_identifier_by_name("x")
        print(f"x = {x}")
        df_graph = DataFlowGraph(start_node=x)
        print(f"df_graph =\n{df_graph}")
        self.assertEqual(df_graph.get_start_node(), x)
        print(f"len(df_graph.get_nodes()) = {len(df_graph.get_nodes())}")
        self.assertEqual(len(df_graph.get_nodes()), len(pdg.get_all_identifiers()))
        # get_all_final_nodes() should return no "final nodes":
        self.assertEqual(len(df_graph.get_all_final_nodes()), 0)
        # get_data_flows(ONE_PER_FINAL_NODE_SHORTEST) should return 0 data flows, as there are no "final nodes":
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_FINAL_NODE_SHORTEST)
        self.assertEqual(len(data_flows), 0)
        # get_data_flows(ONE_PER_NODE_SHORTEST) should only return as many data flows as there are nodes:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_NODE_SHORTEST)
        self.assertEqual(len(data_flows), len(pdg.get_all_identifiers()))
        # get_data_flows(JUST_ONE) should, as the name suggests, return just 1 data flow:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.JUST_ONE)
        self.assertEqual(len(data_flows), 1)
        # Even when there are 0 final nodes, get_data_flows(DIJKSTRA_LEAVES) should return more than 0 data flows:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.DIJKSTRA_LEAVES)
        print(f"No. of Dijkstra leaves: {len(data_flows)}")
        # => 1 is correct (Dijkstra tree will actually be a "degenerate" graph/a line)
        self.assertGreater(len(data_flows), 0)

        # An example with a loop and 1 "final node":
        code = """
        while (1) {
            x = y
            y = x
        }
        z = x
        """
        pdg = generate_pdg(code)
        print(f"pdg =\n{pdg}")
        x = pdg.get_first_identifier_by_name("x")
        z = pdg.get_identifier_by_name("z")
        print(f"x = {x}")
        df_graph = DataFlowGraph(start_node=x)
        print(f"df_graph =\n{df_graph}")
        self.assertEqual(df_graph.get_start_node(), x)
        print(f"len(df_graph.get_nodes()) = {len(df_graph.get_nodes())}")
        self.assertEqual(len(df_graph.get_nodes()), len(pdg.get_all_identifiers()))
        # get_all_final_nodes() should return 1 "final node":
        self.assertEqual(len(df_graph.get_all_final_nodes()), 1)
        # get_data_flows(ONE_PER_FINAL_NODE_SHORTEST) should return 1 data flow:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_FINAL_NODE_SHORTEST)
        self.assertEqual(len(data_flows), 1)
        print(f"data_flows[0] = {data_flows[0]}")
        self.assertEqual(data_flows[0].last_node(), z)
        # get_data_flows(ONE_PER_NODE_SHORTEST) should only return as many data flows as there are nodes:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.ONE_PER_NODE_SHORTEST)
        self.assertEqual(len(data_flows), len(pdg.get_all_identifiers()))
        # get_data_flows(JUST_ONE) should, as the name suggests, return just 1 data flow:
        data_flows = df_graph.get_data_flows(DataFlowsConsidered.JUST_ONE)
        self.assertEqual(len(data_flows), 1)
