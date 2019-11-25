"""
Module containing contraction methods
"""

import ctypes
import sys
import networkx
from graphpartition import Tree
sys.path += ["/home/jacob/QuEST-TN/utilities/"]


# Find QuEST and TN libraries
from QuESTPy.QuESTBase import init_QuESTLib
from TNPy.TNBase import init_TNLib
QuESTPath = "/home/jacob/QuEST-TN/build/TN/QuEST"
TNPath = "/home/jacob/QuEST-TN/build/TN/"
init_QuESTLib(QuESTPath)
init_TNLib(TNPath)

import QuESTPy
import TNPy
import TNPy.TNFunc as TNFunc
import TNPy.TNAdditionalGates as TNAdd
import QuESTPy.QuESTFunc as QuESTFunc

ENV = None

class TensorNode:
    """ Class containing details relating to tensor contractions """
    def __init__(self, tensor, node, edges, indices, qubits):
        self.tensor = tensor
        self._node = node
        self._edges = edges
        self._indices = indices
        self._qubits = qubits

    node = property(lambda self: self._node)
    edges = property(lambda self: self._edges)
    indices = property(lambda self: self._indices)
    qubits = property(lambda self: self._qubits)

    @staticmethod
    def inherit(left, right, prop, contractionEdges):
        """ Set self's indices and qubits to the combination of left and right """
        return ([propty for contracted, propty in zip(contractionEdges[0], getattr(left, prop)) if not contracted] +
                [propty for contracted, propty in zip(contractionEdges[1], getattr(right, prop)) if not contracted])

    @staticmethod
    def contract(left, right, contractionEdges):
        """ Contract two tensor nodes and update the respective properties """
        contPass = [[i for i, edges in enumerate(cont) if edges] for cont in contractionEdges]
        freePass = [[i for i, edges in enumerate(cont) if not edges] for cont in contractionEdges]
        # Transform into ctypes arrays
        *contPass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), contPass)
        *freePass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), freePass)
        out = TensorNode(TNFunc.contractIndices(left.tensor, right.tensor,
                                                contPass[0], contPass[1], ctypes.c_int(len(contPass[0])),
                                                freePass[0], ctypes.c_int(len(freePass[0])),
                                                freePass[1], ctypes.c_int(len(freePass[1])), ENV),
                         node=left.node, # Inherit left's ID
                         edges=TensorNode.inherit(left, right, "edges", contractionEdges),
                         indices=TensorNode.inherit(left, right, "indices", contractionEdges),
                         qubits=TensorNode.inherit(left, right, "qubits", contractionEdges))
        return out

    @staticmethod
    def compute_contraction_edges(left, right):
        """ Calculate the edges which are involved in a contraction """
        return ([edge[::-1] in right.tensorNode.edges or
                 edge in right.tensorNode.edges for edge in left.edges],
                [edge[::-1] in left.tensorNode.edges or
                 edge in left.tensorNode.edges for edge in right.edges])

def resolve_node(node: Tree):
    """
    Initialise tensor/qureg
    Call our operation on qubits
    Update node resolved

    Return TensorObject
    """

    vertex = node.vertex
    print(f"Hi, I'm {vertex.ID}")
    nVirtQubit = vertex.nEdges - 1

    print(f"I have {vertex.nEdges} edges and 1 physical qubit")
    print(f"My edges are {list(vertex.edges)}")
    node._tensor = TensorNode(TNFunc.createTensor(1, nVirtQubit, ENV),
                              edges=vertex.fixedEdges,
                              node=vertex.ID,
                              indices=[(vertex.ID, i) for i in range(vertex.nEdges)],
                              qubits=[vertex.qubitID for i in range(vertex.nEdges)])

    # If we're initialise -- createTensor => |0>
    if vertex.op is None:
        return

    # Entangle first virtual with physical qubit
    print("TARGET HALF")
    TNAdd.TN_controlledGateTargetHalf(QuESTFunc.controlledNot, node.tensor, 1, 0)

    if vertex.op.name == "CX":
        gate = QuESTFunc.controlledNot
        args = [0, 2]
    elif vertex.op.name == "U":
        gate = QuESTFunc.hadamard
        args = [0]

    for vertex in node.vertices:
        if gate.control:
            if vertex.qubitID == vertex.op.qargs[gate.control-1][1]:
                print("Control")
                # physical qubit is the control, virtual qubit is the target
                print(args)
                TNAdd.TN_controlledGateControlHalf(gate, node.tensor, *args)
            else:
                print("Target")
                # virtual qubit is the control, physical qubit is the target
                print(args[::-1])
                TNAdd.TN_controlledGateTargetHalf(gate, node.tensor, *args[::-1])
        else:
            TNAdd.TN_singleQubitGate(gate, node.tensor, *args)

def contract(graph):
    """ Contract entire tree recursively """
    if isinstance(graph, Tree):
        global ENV
        ENV = QuESTFunc.createQuESTEnv()

    if graph.isLeaf:
        graph.resolve()
        return

    for child in graph.child:
        child.contract()

    childL = graph.left
    childR = graph.right
    tensorL = childL.tensorNode
    tensorR = childR.tensorNode
    idL = childL.vertex.ID
    idR = childR.vertex.ID

    print("Left", idL, list(graph.left.edges))
    print("Right", idR, list(graph.right.edges))

    contractionEdges = TensorNode.compute_contraction_edges(childL, childR)
    # My vertex becomes child's merged vertex
    graph._tensor = TensorNode.contract(tensorL, tensorR, contractionEdges)

    if graph.tier == 0:
        return

    # Reduce graph image
    graph.root._adjList = networkx.contracted_nodes(graph.root._adjList, idL, idR)
    graph.vertex._contracted += [idL]
    graph.child = []

    print("Hi, I'm ", graph.vertex.ID, list(graph.edges), "I ate ", graph.vertex.contracted)
