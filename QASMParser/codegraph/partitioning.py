"""
Module which performs the partitioning and set-up of quantum registers based on the partitioner request
"""
from enum import (IntEnum)
import numpy as np
from .drawing import COLOURS
from ..parser.parser import (ProgFile)
from ..parser.types import (TensorNetwork)
from .errors import (partitionWarning)

def partition(code: ProgFile, partitionLevel: int = 0, maxDepth=-1, dummy=False):
    """ Call correct partitioner based on partition level """
    partitionTypes = IntEnum("PartitionTypes", "NONE REGISTER SPACELIKE FULL", start=0)

    if partitionLevel > partitionTypes.REGISTER:
        from .codegraph import (CodeGraph)
        import networkx
    if partitionLevel > partitionTypes.SPACELIKE:
        from .graphpartition import (Tree)

    if partitionLevel == partitionTypes.NONE:
        if dummy:
            return

    if partitionLevel == partitionTypes.REGISTER:
        bestSlice = tuple([register.end for register in code.quantumRegisters])
        if not dummy:
            code.partition = create_tensor_network(code, bestSlice)

    if partitionLevel == partitionTypes.SPACELIKE:
        codeGraph = CodeGraph(code, code.nQubits, maxDepth=maxDepth)
        codeGraph.draw_entang("entang.pdf")
        slices = optimal_cut(codeGraph)

        if not slices or len(slices) == 1:
            print(partitionWarning)
        if not dummy:
            code.partition = create_tensor_network(code, bestSlice)

    if partitionLevel == partitionTypes.FULL:
        codeGraph = CodeGraph(code, code.nQubits, maxDepth=maxDepth)

        codeGraph.draw("graph.pdf", labelAttr="opName")

        tree = Tree(codeGraph.tensorGraph)
        tree.split_graph("metis")

        if dummy:
            graph = codeGraph.to_graphviz()
            codeGraph.circuit_layout()
            codeGraph.setup_draw_circuit(labelAttr="opName")
            nSplits = 0
            for tier in range(tree.nTier+1):
                nodes = tree.by_tier(tier)
                for node in nodes:
                    nSplits += 1
                    for vert in node.codeGraph:
                        currNode = graph.get_node(vert)
                        colourSel = COLOURS[nSplits%len(COLOURS)]
                        # Urgh, American spelling
                        currNode.attr["fillcolor"] = f":{colourSel}"

            graph.draw("graph"+str(tier)+".png")
        else:
            from contraction import contract
            contract(tree)


def create_tensor_network(code, slices):
    """ Build the tensor network command and calculate the number of virtual qubits needed for the operation """
    newOrder = [qubit for currSlice in slices for qubit in currSlice]
    print(newOrder)
    *physicalQubits, = map(len, tnNodes)
    code.useTN = True
    return TensorNetwork(code, "qreg", physicalQubits, virtualQubits)

def cost_func(codeGraph, groups, cut):
    mem = 0
    time = 0
    for group in groups:
        nPhys = len(group)
        nVirt = cut
        nGateQubit = sum(codeGraph.nGateQubit[qubit] for qubit in group)
        mem += (nPhys + nVirt)
        time += nGateQubit * 2**mem
    print("COST:", groups, mem, time)
    return mem, time

def optimal_cut(codeGraph):
    import networkx
    entangGraph = codeGraph.entang
    tensorGraph = codeGraph.tensorGraph
    baseCost = cost_func(codeGraph, (list(range(codeGraph.nQubits)),), 0)

    # edgesCut, groups = networkx.algorithms.connectivity.stoerwagner.stoer_wagner(entangGraph)
    # newCost = cost_func(codeGraph, groups, edgesCut)
    # print(baseCost, newCost)

    # adjMat = codeGraph.entanglements
    # maxEdge = np.unravel_index(adjMat.argmax(), adjMat.shape)
    # print(adjMat)
    testGraph = modified_stoer_wagner(entangGraph, opt="time", edgeSelectionFunc=highest_weight)
    print(testGraph)
    groups = []
    for nodeID in testGraph.nodes:
        node = testGraph.nodes[nodeID]
        if "contraction" in node:
            groups.append((nodeID, *(eaten for eaten in node["contraction"]), ))
        else:
            groups.append((nodeID, ))
    groups = tuple(groups)
    print(groups)

    return ()

def highest_weight(edges):
    return list(reversed(sorted(edges, key=lambda data: data[2]["weight"])))

def lowest_weight(edges):
    return list(sorted(edges, key=lambda data: data[2]["weight"]))

def random_selection(edges):
    import random
    out = list(edges)
    random.shuffle(out)
    return edges

def modified_stoer_wagner(graph, opt="mem", edgeSelectionFunc=highest_weight):
    """ Perform a qubit optimisation variant resembling Stoer-Wagner """
    import networkx

    # Optimisation measure
    if opt == "mem":
        check = 0
    elif opt == "time":
        check = 1
    elif opt == "memtime":
        check = slice(0, 2)
    else:
        raise ValueError("Unrecognised opt {}".format(opt))

    def cost(trialGraph):
        """ Estimate cost of current configuration """
        import math
        mem = 0
        time = 0
        for nodeID in trialGraph.nodes:
            node = trialGraph.nodes[nodeID]
            nPhys = 1
            nVirt = sum(trialGraph.get_edge_data(nodeID, node)["weight"] for node in trialGraph.neighbors(nodeID))
            nGateQubit = node["weight"]
            if "contraction" in node:
                nPhys += len(node["contraction"])
                nGateQubit += sum(eaten["weight"] for eaten in node["contraction"].values())
            print(nPhys, nVirt)
            mem += nPhys + nVirt
            time = exp_add(time, math.log2(nGateQubit) + nPhys + nVirt)
        print("COST:", mem, time)
        return mem, time

    testGraph = graph.copy()
    bestCost = cost(testGraph)

    while True:
        # Edge test order criterion
        sortEdges = edgeSelectionFunc(testGraph.edges(data=True))
        print(sortEdges)
        for *node, data in sortEdges:
            trialGraph = networkx.contracted_edge(testGraph, node, self_loops=False)
            
            # Prevent nesting contractions
            contNode = trialGraph.nodes[node[0]]
            for cont in list(contNode["contraction"].keys()):
                if "contraction" in contNode["contraction"][cont]:
                    contNode["contraction"].update(contNode["contraction"][cont]["contraction"])
                    del contNode["contraction"][cont]["contraction"]

            # Calculate new cost following reduction
            newCost = cost(trialGraph)
            if newCost[check] < bestCost[check]:
                testGraph = trialGraph
                bestCost = newCost
                break
        else:
            break

    return testGraph

def exp_add(a: float, b: float):
    """ Add the exponents of two numbers
    :param a: input exponent
    :param b: input exponent
    :returns: Sum of exponents"""
    import math
    if b == 0:
        return a
    if a == 0:
        return b

    # Assume that for very large numbers the 1 is irrelevant
    if a > 30 or b > 30:
        return a + b

    if a > b:
        out = math.log2(2**(a - b) + 1) + b
    else:
        out = math.log2(2**(b - a) + 1) + a
    return out
