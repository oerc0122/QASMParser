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
        mem += 2**(nPhys + nVirt)
        time += nGateQubit * mem
    print("COST:", groups, mem, time)
    return mem, time

def optimal_cut(codeGraph):
    import networkx
    entangGraph = codeGraph.entang
    tensorGraph = codeGraph.tensorGraph
    baseCost = cost_func(codeGraph, (list(range(codeGraph.nQubits)),), 0)

    edgesCut, groups = networkx.algorithms.connectivity.stoerwagner.stoer_wagner(entangGraph)
    newCost = cost_func(codeGraph, groups, edgesCut)
    print(baseCost, newCost)
    
    adjMat = codeGraph.entanglements
    maxEdge = np.unravel_index(adjMat.argmax(), adjMat.shape)
    print(adjMat)

    return ()
