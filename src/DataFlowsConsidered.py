from enum import Enum


class DataFlowsConsidered(Enum):
    """
    An enum that is supplied to DataFlowGraph.get_data_flows().
    Defines which data flows to generate for a given start node
    (namely the `start_node` given when creating the DataFlowGraph object).

    WARNINGS:
        1. Some of these may have exponential runtime:
           - ALL
           - ALL_STOP_AT_CYCLE_INCLUSIVE
           - ALL_STOP_AT_CYCLE_EXCLUSIVE
        2. Some of these may not include all nodes into which data flows (i.e., may not have full node coverage):
           - ONE_PER_FINAL_NODE_SHORTEST
           - JUST_ONE

    The following variants both have non-exponential runtime *and* guarantee full node coverage:
        - ONE_PER_NODE_SHORTEST
        - DIJKSTRA_LEAVES

    INCLUSIONS:
        ONE_PER_FINAL_NODE_SHORTEST <= DIJKSTRA_LEAVES <= ONE_PER_NODE_SHORTEST <= ALL
        ^^^^^^^^^^^^^^^^^^^^^^^^^^^    ^^^^^^^^^^^^^^^                             ^^^
        does not always have           does not generate data                      worst-case exponential runtime
        full node coverage             flows ending in each node
        ...where "<=" means "subset of".

    BEWARE:
        Later on, we will iterate over all (from_flow, to_flow) combinations, meaning that the complexity of data
        flow generation is squared, so even for the methods that generate "only" O(|V|) data flows,
        the overall effort will be quadratic!
        Similarly, the data flow generation methods with (potential) exponential runtime will perform *even* worse!!!

    Notes on determinism:
        - ALL: always generates all data flows that have no duplicate nodes, order not guaranteed
        - ALL_STOP_AT_CYCLE_INCLUSIVE: data flows generated will always be the same, order not guaranteed
        - ALL_STOP_AT_CYCLE_EXCLUSIVE: data flows generated will always be the same, order not guaranteed
        - ONE_PER_NODE_SHORTEST: deterministic because Dijkstra implementation is implemented deterministically,
                                 preferring smaller Node IDs over larger ones
        - ONE_PER_FINAL_NODE_SHORTEST: (same here)
        - DIJKSTRA_LEAVES: (same here)
        - JUST_ONE: deterministic as the path that ensures the lowest node IDs will be taken

    Here is an example illustrating the differences between the different variants:
        let _1 = "data";       // node [1]
        let _2 = _1, _3 = _1;  // nodes [2], [1'], [3] and [1'']
        let _4 = _2 + _3;      // nodes [4], [2'] and [3']

        let _5 = _4, _6 = _4;  // nodes [5], [4'], [6] and [4'']
        let _7 = _5 + _6;      // nodes [7], [5'] and [6']

    Enum variant                         | Data flows considered for the example above (start_node=[1])
    -------------------------------------|-----------------------------------------------------------------------------
    ALL                                  | [1]
                                         | [1] -> [1']
                                         | [1] -> [1']   -> [2]
                                         | [1] -> [1']   -> [2] -> [2']
                                         | [1] -> [1']   -> [2] -> [2'] -> [4]
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4']
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4']  -> [5]
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5']
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4'']
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4''] -> [6]
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4''] -> [6] -> [6']
                                         | [1] -> [1']   -> [2] -> [2'] -> [4] -> [4''] -> [6] -> [6'] -> [7]
                                         | [1] -> [1'']
                                         | [1] -> [1'']  -> [3]
                                         | [1] -> [1'']  -> [3] -> [3']
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4]
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4']
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4']  -> [5]
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4']  -> [5] -> [5']
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4'']
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4''] -> [6]
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4''] -> [6] -> [6']
                                         | [1] -> [1'']  -> [3] -> [3'] -> [4] -> [4''] -> [6] -> [6'] -> [7]
                                         | => no. of flows: worst-case: exponential in |V|
    -------------------------------------|-----------------------------------------------------------------------------
    ALL_STOP_AT_CYCLE_INCLUSIVE          | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4''] -> [6] -> [6'] -> [7]
                                         | [1] -> [1''] -> [3] -> [3'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | [1] -> [1''] -> [3] -> [3'] -> [4] -> [4''] -> [6] -> [6'] -> [7]
                                         | => no. of flows: worst-case: exponential in |V|
    -------------------------------------|-----------------------------------------------------------------------------
    ALL_STOP_AT_CYCLE_EXCLUSIVE          | (same as above in this example as there *are* no cycles here)
                                         | => no. of flows: worst-case: exponential in |V|
    -------------------------------------|-----------------------------------------------------------------------------
    ONE_PER_NODE_SHORTEST                | [1]
                                         | [1] -> [1']
                                         | [1] -> [1'']
                                         | [1] -> [1']  -> [2]
                                         | [1] -> [1''] -> [3]
                                         | [1] -> [1']  -> [2] -> [2']
                                         | [1] -> [1''] -> [3] -> [3']
                                         | [1] -> [1']  -> [2] -> [2'] -> [4]
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4'']
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']  -> [5]
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4''] -> [6]
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5']
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4''] -> [6] -> [6']
                                         | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | => no. of flows: |V| = no. of vertices/nodes reachable via DF
    -------------------------------------|-----------------------------------------------------------------------------
    ONE_PER_FINAL_NODE_SHORTEST          | [1] -> [1']  -> [2] -> [2'] -> [4] -> [4']  -> [5] -> [5'] -> [7]
                                         | => no. of flows: no. of final nodes; max. |V|
    -------------------------------------|-----------------------------------------------------------------------------
    DIJKSTRA_LEAVES                      | => no. of flows: no. of leaves in the Dijkstra tree, max. |V|
    -------------------------------------|-----------------------------------------------------------------------------
    JUST_ONE                             | (same as for ONE_PER_FINAL_NODE_SHORTEST in this example)
                                         | => no. of flows: 1
    """

    ALL = 0
    """
    Generate all data flows
        start_node=x0 --data--> x1 --data--> x2 --data--> ... --data--> xn
    where xi != xj for 0<=i<=n, 0<=j<=n, i != j.
    
    WARNING: Potentially has exponential runtime!!!
    """

    ALL_STOP_AT_CYCLE_INCLUSIVE = 1
    """
    Generate all data flows
        start_node --data--> ... --data--> final_node    (where final_node has no outgoing DF edges anymore)
    and
        start_node --data--> ... --data--> X --data--> ... --data--> X    (where X is the only node appearing twice)
        
    WARNING: Potentially has exponential runtime!!!
    """

    ALL_STOP_AT_CYCLE_EXCLUSIVE = 2
    """
    Generate all data flows
        start_node --data--> ... --data--> final_node    (where final_node has no outgoing DF edges anymore)
    and
        start_node --data--> ... --data--> X --data--> ... --data--> Y   (where no node appears twice but Y --data--> X)
        
    WARNING: Potentially has exponential runtime!!!
    """

    ONE_PER_NODE_SHORTEST = 3
    """
    Generate one data flow
        start_node --data--> ... --data--> X
    for each node X that is reachable from `start_node` via data flow edges.
    For each node X, pick the shortest such path that exists.
    If multiple shortest paths exist, smaller Node IDs will be preferred over larger ones.
    Essentially just an enumeration of all possible paths one can take in the Dijkstra tree (starting
    at the `start_node` and without backtracking).
    Trivially ensures full node coverage.
    
    Note that many of these flows will not have "finished", meaning that X still has outgoing data flow edges!
    """

    ONE_PER_FINAL_NODE_SHORTEST = 4
    """
    Generate one data flow
        start_node --data--> ... --data--> final_node
    for each final node `final_node`, where a we define a final node as having no outgoing data flow edges.
    For each such `final_node`, pick the shortest path that exists.
    If multiple shortest paths exist, smaller Node IDs will be preferred over larger ones.
    ONE_PER_FINAL_NODE_SHORTEST generates a subset of flows as generated by ONE_PER_NODE_SHORTEST.
    ONE_PER_FINAL_NODE_SHORTEST also generates a subset of flows generated by DIJKSTRA_LEAVES,
      as all final nodes are necessarily Dijkstra leaves, too.
      
    The result should be equivalent to that of ALL_STOP_AT_CYCLE_INCLUSIVE/ALL_STOP_AT_CYCLE_EXCLUSIVE,
    when the DataFlowGraph has no cycles and no splits, i.e., when it is a tree.
    """

    DIJKSTRA_LEAVES = 5
    """
    Enumerates all data flows
        start_node --data--> ... --data--> dijkstra_leaf
    where `dijkstra_leaf` is a leaf in the generated Dijkstra tree of shortest data flow paths.
    Just like for ONE_PER_NODE_SHORTEST, the Dijkstra tree is enumerated, however only those paths
    that start at `start_node` and end in a leaf.
    Therefore, DIJKSTRA_LEAVES generates a subset of flows as generated by ONE_PER_NODE_SHORTEST.
    
    The result should be equivalent to that of ALL_STOP_AT_CYCLE_INCLUSIVE/ALL_STOP_AT_CYCLE_EXCLUSIVE,
    when the DataFlowGraph has no cycles and no splits, i.e., when it is a tree.
    """

    JUST_ONE = 6
    """
    Generate just one data flow
        start_node --data--> ... --data--> X
    where X is either a final node or already occurred before in the data flow (indicating a cycle).
    Data flow edges to create this flow are picked as to minimize node IDs (this is just to ensure
    deterministic behavior), until either a final node or a node that has already been visited is reached.
    
    Note that this is not a particular smart way of doing it but rather a particularly fast one and
    therefore potentially useful for testing purposes.
    """

    @classmethod
    def default(cls) -> str:
        return "ONE_PER_NODE_SHORTEST"
