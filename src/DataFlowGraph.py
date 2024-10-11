from typing import Dict, List, Tuple, Set

from pdg_js.node import Node
from DataFlow import DataFlow
from DataFlowsConsidered import DataFlowsConsidered


class DataFlowGraph:
    """
    A graph representing all the data flows that go out of a certain given Identifier Node.
    All Nodes in this graph are reachable via data flow edges from this initial Identifier Node.
    Edges are stored using per-node adjacency sets.

    Example code:
        let _1 = "data";
        let _2 = _1, _3 = _1;
        let _4 = _2 + _3;
        let _5 = _4, _6 = _4;
        let _7 = _5 + _6;

    Example DataFlowGraph:
                                                   [1]
                                                    |
                                -----------------------------------------
                                |                                       |
                               [1']                                    [1'']
                                |                                       |
                               [2]                                     [3]
                                |                                       |
                               [2']                                    [3']
                                |________________> [4] <________________|
                                ____________________|___________________
                                |                                      |
                               [4']                                   [4'']
                                |                                      |
                               [5]                                    [6]
                                |                                      |
                               [5']                                   [6']
                                |________________> [7] <_______________|

    You can see that, if we were to continue this pattern, the number of data flows represented by this
    DataFlowGraph can potentially be **exponential** in its number of nodes!!!
    This fact is the whole reason for having this class; without it, my code would have exponential runtime!!!

    DO NOT CONFUSE THIS WITH THE `Node` CLASS!
    The `Node` class represents the AST tree, annotated with data flow edges (making it a so called "PDG").
    This `DataFlowGraph` class however represents a sub-view of this entire PDG, only focusing on the Identifier
    Nodes that are reachable from the given `start_node` via data flow edges.
    """

    def __init__(self, start_node: Node):
        """
        Parameters:
            start_node: the Identifier Node starting this DataFlowGraph;
                        this DataFlowGraph will contain all Nodes for which there is a data flow to them from this
                        start node; an AssertionError is thrown when `start_node` is not an Identifier Node.
        """
        assert start_node.name == "Identifier"
        self.start_node = start_node
        self.node_df_children: Dict[Node, List[Node]] = dict()  # maps each Node in this graph to its data flow children
        # => Note that we use a List[] instead of a Set[] here to make the behavior of the Dijkstra algorithm
        #    deterministic (assuming Node.data_dep_children() is deterministic, that is!).
        # self.node_df_parents: Dict[Node, List[Node]] = dict()  # maps each Node in this graph to its data flow parents
        # # At all times, node_df_children.keys() shall equal node_df_parents.keys() !!!

        # Generate graph:
        all_nodes: List[Node] = list(self.start_node.get_all_data_flow_descendents())  # turn set into list
        # => self.start_node.get_all_data_flow_descendents() will return self.start_node itself, too!
        all_nodes.sort()  # (to ensure determinism of DataFlowGraph.get_nodes() and get_all_final_nodes())
        for node in all_nodes:
            self.node_df_children[node] = [df_child.extremity for df_child in node.data_dep_children()]
            # self.node_df_parents[node] = [df_child.extremity for df_child in node.data_dep_parents()]

        # On the generated DataFlowGraph, perform the Dijkstra algorithm to determine shortest paths to
        # the start_node; this information will then be used by get_data_flows():
        self.dijkstra_distances: Dict[Node, float] =\
            {node: (0 if node == self.start_node else float('inf')) for node in self.get_nodes()}
        self.dijkstra_predecessors: Dict[Node, Node] = dict()
        self.dijkstra_successors: Dict[Node, Node] = dict()
        unvisited_nodes: Set[Node] = set(self.get_nodes())  # does not add any non-determinism here!!!
        while len(unvisited_nodes) > 0:
            u: Node = min(unvisited_nodes, key=lambda node: (self.dijkstra_distances[node], node.id))
            # => added `node.id` as 2nd tuple element ("tie-breaker") to ensure deterministic behavior!!!
            unvisited_nodes.remove(u)
            for df_child_v in self.node_df_children[u]:
                if df_child_v in unvisited_nodes:
                    # Distance update:
                    dist: float = self.dijkstra_distances[u] + 1  # 1 being the distance between u and v
                    if dist < self.dijkstra_distances[df_child_v]:
                        self.dijkstra_distances[df_child_v] = dist
                        self.dijkstra_predecessors[df_child_v] = u
                        self.dijkstra_successors[u] = df_child_v
        # => cf. https://de.wikipedia.org/wiki/Dijkstra-Algorithmus
        # Note: I also implemented a version of the Dijkstra algorithm using a heapq,
        #       that one actually turned out to be SLOWER, however!
        # Assuming DF edges have already been generated, one __init__() call takes about 0.0015 sec to execute.

    def __str__(self):
        """
        Returns a string representation of the Dijkstra-shortest-path tree of this DataFlowGraph.
        """
        dijkstra_successors: Dict[Node, List[Node]] = dict()
        for node in self.get_nodes():
            dijkstra_successors[node] =\
                [successor for successor, predecessor in self.dijkstra_predecessors.items() if predecessor == node]

        def to_str(node: Node, indent: int) -> str:
            s: str = f'{'\t' * indent}[{node.id}] [{node.name}:"{node.attributes.get('name')}"]\n'
            for dijkstra_successor in dijkstra_successors[node]:
                s += to_str(dijkstra_successor, indent=indent+1)
            return s

        return to_str(self.start_node, indent=0)

    def get_nodes(self):
        """
        A set-like object providing a view on all the Identifier Nodes `x` in this graph.
        For all these Nodes `x`, there exists a data flow from `start_node` (the Node originally passed
        to DataFlowGraph() constructor) to `x`:
            start_node --data--> ... --data--> ... --data--> x
        """
        return self.node_df_children.keys()

    def get_start_node(self) -> Node:
        """
        The Identifier Node that started this DataFlowGraph.
        Equals the Identifier Node originally supplied to the DataFlowGraph() constructor.
        """
        return self.start_node

    def get_data_flows(self,
                       data_flows_considered: DataFlowsConsidered) -> List[DataFlow]:
        """
        Enumerates data flows based on this DataFlowGraph.
        The DataFlowsConsidered enum passed as an argument dictates which data flows to enumerate.
        Cf. doc comments in DataFlowsConsidered, but note that this is a question of trade-off: runtime vs. recall.
        Also beware that some of the variants of DataFlowsConsidered will have worst-case exponential runtime!!!
        """
        result: List[DataFlow] = []

        match data_flows_considered:
            case DataFlowsConsidered.ALL:
                raise NotImplementedError("todo")

            case DataFlowsConsidered.ALL_STOP_AT_CYCLE_INCLUSIVE:
                raise NotImplementedError("todo")

            case DataFlowsConsidered.ALL_STOP_AT_CYCLE_EXCLUSIVE:
                raise NotImplementedError("todo")

            case DataFlowsConsidered.ONE_PER_NODE_SHORTEST:  # (cf. ONE_PER_FINAL_NODE_SHORTEST below)
                for node in self.get_nodes():
                    reverse_df: List[Node] = [node]
                    while reverse_df[-1] != self.start_node:
                        reverse_df.append(self.dijkstra_predecessors[reverse_df[-1]])
                    result.append(DataFlow(list(reversed(reverse_df))))

            case DataFlowsConsidered.ONE_PER_FINAL_NODE_SHORTEST:
                for final_node in self.get_all_final_nodes():
                    # Use the Dijkstra algorithm that has already been performed during __init__() to determine the
                    #   shortest path from self.start_node to final_node; turn the path into a DataFlow object and
                    #   append it to the result list:
                    reverse_df: List[Node] = [final_node]
                    while reverse_df[-1] != self.start_node:
                        reverse_df.append(self.dijkstra_predecessors[reverse_df[-1]])
                    # Reverse [final_node, ..., start_node] into [start_node, ..., final_node] and append to result list:
                    result.append(DataFlow(list(reversed(reverse_df))))

            case DataFlowsConsidered.DIJKSTRA_LEAVES:  # (cf. ONE_PER_FINAL_NODE_SHORTEST above)
                for dijkstra_leaf in self.get_all_dijkstra_leaves():
                    reverse_df: List[Node] = [dijkstra_leaf]
                    while reverse_df[-1] != self.start_node:
                        reverse_df.append(self.dijkstra_predecessors[reverse_df[-1]])
                    result.append(DataFlow(list(reversed(reverse_df))))

            case DataFlowsConsidered.JUST_ONE:
                flow: List[Node] = [self.start_node]
                while True:
                    df_children: List[Node] = self.node_df_children[flow[-1]]
                    if len(df_children) == 0:
                        break  # stop when there's nowhere to go anymore
                    next_df_child: Node = min(df_children, key=lambda node: node.id)
                    if next_df_child in flow:
                        flow.append(next_df_child)
                        break  # stop after having added the first duplicate Node
                    else:
                        flow.append(next_df_child)
                result.append(DataFlow.from_node_list(flow))

        return result

    def get_all_final_nodes(self) -> List[Node]:
        """
        Returns all Nodes `x` such that there is a data flow from `start_node` to `x`:
            start_node --data--> ... --data--> ... --data--> x
        ...but `x` has no further *outgoing* data flow edges.
        """
        return [node for node, df_children in self.node_df_children.items() if len(df_children) == 0]

    def get_all_dijkstra_leaves(self) -> List[Node]:
        """
        Returns all leave nodes of the Dijkstra tree internally stored by this DataFlowGraph.
        Will be a superset of the Nodes returned by get_all_final_nodes(), as every "final node" is necessarily also
        a leaf of the Dijkstra tree (as it has no outgoing data flow edges)!
        """
        # Return all Nodes that a not the Dijkstra predecessor of another Node (a.k.a. all leaves of the Dijkstra tree):
        return [node for node in self.get_nodes() if node not in self.dijkstra_predecessors.values()]

    def has_cycle(self) -> bool:
        """
        Returns true iff this DataFlowGraph has any cycle in it.
        Example:
            while (1) {
                x = y;
                y = x;
            }
        """
        raise NotImplementedError("todo")

    def has_split(self) -> bool:
        """
        Returns true iff this DataFlowGraph has any split in it, meaning that there are two nodes A and B
        such that there exist at least 2 different data flow paths from A to B.
        Example:
            let a = "data";
            let x = a, y = a;
            let b = x + y;
        """
        raise NotImplementedError("todo")
