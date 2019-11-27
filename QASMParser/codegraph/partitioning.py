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
        print(slices)
        if not slices or len(slices) == 1:
            print(partitionWarning)
        if not dummy:
            create_tensor_network(code, codeGraph.entang, slices)

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


def create_tensor_network(code, entangGraph, slices):
    """ Build the tensor network command and calculate the number of virtual qubits needed for the operation """
    remap = {new: old for old, new in enumerate(point for group in slices for point in group)}
    print(remap)
    for reg in code.quantumRegisters:
        reg.mapping = tuple(map(lambda x: remap[x], reg.mapping))
    *physicalQubits, = map(len, slices)
    *virtualQubits, = (sum(entangGraph.get_edge_data(*edge)["weight"] for edge in external_edges(entangGraph, group))
                       for group in slices)
    print(physicalQubits, virtualQubits)
    code.useTN = True
    code.partition = TensorNetwork(code, "qreg", physicalQubits, virtualQubits)

def cost_func_groups(entangGraph, groups):
    """ Estimate cost of current configuration """
    import math
    mem = 0
    time = 0
    for group in groups:
        nPhys = len(group)
        nVirt = sum(entangGraph.get_edge_data(*edge)["weight"] for edge in external_edges(entangGraph, group))
        nGateQubit = sum(entangGraph.nodes[qubit]["weight"] for qubit in group)
        mem += nPhys + nVirt
        time = exp_add(time, math.log2(nGateQubit) + nPhys + nVirt)
    return mem, time

def cost_func_graph(trialGraph):
    """ Estimate cost of current configuration """
    import math
    mem = 0
    time = 0
    for nodeID in trialGraph.nodes:
        node = trialGraph.nodes[nodeID]
        nPhys = 1
        nVirt = list(trialGraph.get_edge_data(*edge)["weight"] for edge in trialGraph.edges(nodeID))
        nVirt = sum(nVirt)
        nGateQubit = node["weight"]
        if "contraction" in node:
            nPhys += len(node["contraction"])
            nGateQubit += sum(eaten["weight"] for eaten in node["contraction"].values())
        mem += nPhys + nVirt
        time = exp_add(time, math.log2(nGateQubit) + nPhys + nVirt)
    return mem, time

def external_edges(graph, nbunch):
    """ Get the edges external to a set of nodes """
    return (edge for edge in graph.edges(nbunch) if any(node not in nbunch for node in edge))

def optimal_cut(codeGraph):
    """ Calculate the best cut """
    import networkx
    entangGraph = codeGraph.entang
    testGraph = modified_stoer_wagner(entangGraph, opt="time", edgeSelectionFunc=highest_weight)

    graph = networkx.nx_agraph.to_agraph(testGraph)
    graph.draw("postsquish.pdf", prog="neato")
    # Map testGraph's nodes to slices
    groups = []
    for nodeID in testGraph.nodes:
        node = testGraph.nodes[nodeID]
        if "contraction" in node:
            groups.append((nodeID, *(eaten for eaten in node["contraction"]), ))
        else:
            groups.append((nodeID, ))
    groups = tuple(groups)
    return groups

def highest_weight(edges):
    """ Get edges based on highest weight first """
    return list(reversed(sorted(edges, key=lambda data: data[2]["weight"])))

def lowest_weight(edges):
    """ Get edges based on lowest weight first """
    return list(sorted(edges, key=lambda data: data[2]["weight"]))

def random_selection(edges):
    """ Choose edges 'completely' randomly """
    import random
    out = list(edges)
    random.shuffle(out)
    return edges

def modified_contract_nodes(G, u, v):
    """ A node contraction to accumulate the costs
    based on the contract nodes function in networkx """
    import copy

    outGraph = copy.deepcopy(G)

    # x is v; w is other
    for x, w, d in outGraph.edges(v, data=True):
        if w != u:
            if outGraph.has_edge(u, w):
                outGraph.get_edge_data(u, w)["weight"] += d["weight"]
            else:
                outGraph.add_edge(u, w, **d)
    uData, vData = outGraph.nodes[u], outGraph.nodes[v]
    outGraph.remove_node(v)

    if "label" in uData:
        uData["label"] += ":"+str(v)
    else:
        uData["label"] = str(u) + ":" + str(v)
    if "contraction" in uData:
        uData["contraction"][v] = vData
    else:
        uData["contraction"] = {v: vData}
    # Prevent nesting contractions
    if "contraction" in vData:
        uData["contraction"].update(vData["contraction"])
        del vData["contraction"]
    return outGraph


def modified_stoer_wagner(graph, opt="mem", edgeSelectionFunc=highest_weight):
    """ Perform a qubit optimisation variant resembling Stoer-Wagner """
    # Optimisation measure
    if opt == "mem":
        check = 0
    elif opt == "time":
        check = 1
    elif opt == "memtime":
        check = slice(0, 2)
    else:
        raise ValueError("Unrecognised opt {}".format(opt))


    testGraph = graph.copy()
    bestCost = cost_func_graph(testGraph)

    while True:
        # Edge test order criterion
        sortEdges = edgeSelectionFunc(testGraph.edges(data=True))
        for *node, data in sortEdges:
            trialGraph = modified_contract_nodes(testGraph, *node)

            # Calculate new cost following reduction
            newCost = cost_func_graph(trialGraph)
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
