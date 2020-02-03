"""
Module containing contraction methods
"""

import ctypes
import sys
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

ENV = QuESTFunc.createQuESTEnv()

def least_connect(adjList, i, j):
    return adjList[i, j]

def most_connect(adjList, i, j):
    return -adjList[i, j]

def connection(adjList, i, j):
    """ Calculate Ania's cost metric min(free - contraction) """
    return sum(sum(elem for k, elem in enumerate(adjList[i])
                   if k not in (i, j)),
               sum(elem for k, elem in enumerate(adjList[j])
                   if k not in (i, j)),
               -adjList[i, j])


def contract_order(adjList, order=0):
    """ Generator returning leaves in expected resolution order """
    contractOrder = (connection, least_connect, most_connect)
    possibleContractions = ((i, j) for i in adjList for j in adjList[i:]
                            if adjList[i, j] > 0)
    for elem in sorted(possibleContractions, key=lambda elem: contractOrder[order](adjList, *elem)):
        yield elem


class TensorNode:
    """ Class to represent tensors and perform contractions """
    def __init__(self, nPhys, nVirt, edges, indices, qubits, ops):
        global ENV
        self._tensor = TNFunc.createTensor(nPhys, nVirt, ENV)
        self._nPhys = nPhys
        self._nVirt = nVirt
        self._edges = edges
        self._indices = indices
        self._qubits = qubits

        self._init_entangle()
        self.apply(ops)

    nPhys = property(lambda self: self._nPhys)
    nVirt = property(lambda self: self._nVirt)
    tensor = property(lambda self: self._tensor)
    edges = property(lambda self: self._edges)
    indices = property(lambda self: self._indices)
    qubits = property(lambda self: self._qubits)
    nQubits = property(lambda self: len(self.qubits))

    def _init_entangle(self):
        """ Entangle first virtual with physical qubit """
        TNAdd.TN_controlledGateTargetHalf(QuESTFunc.controlledNot, self.tensor, 1, 0)

    def _inherit(self, other, contractionEdges):
        """ Set self's indices and qubits to the combination of self and other """
        self._nPhys += other.nPhys
        self._nVirt += other.nVirt - len(contractionEdges[0]) - len(contractionEdges[1])

        for prop in ("edges", "indices", "qubits"):
            setattr(self, prop,
                    ([propty for contracted, propty in zip(contractionEdges[0], getattr(self, prop))
                      if not contracted] +
                     [propty for contracted, propty in zip(contractionEdges[1], getattr(other, prop))
                      if not contracted])
                    )

    def _compute_contraction_edges(self, other):
        """ Calculate the edges which are involved in a contraction """
        return ([edge[::-1] in other.edges or
                 edge in other.edges for edge in self.edges],
                [edge[::-1] in self.edges or
                 edge in self.edges for edge in other.edges])

    def contract(self, other):
        """ Contract two tensor nodes and update the respective properties """
        contractionEdges = self._compute_contraction_edges(other)
        contPass = [[i for i, edges in enumerate(cont) if edges] for cont in contractionEdges]
        freePass = [[i for i, edges in enumerate(cont) if not edges] for cont in contractionEdges]
        # Transform into ctypes arrays
        *contPass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), contPass)
        *freePass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), freePass)
        self._tensor = TNFunc.contractIndices(self.tensor, other.tensor,
                                              contPass[0], contPass[1], ctypes.c_int(len(contPass[0])),
                                              freePass[0], ctypes.c_int(len(freePass[0])),
                                              freePass[1], ctypes.c_int(len(freePass[1])), ENV)
        self._inherit(other, contractionEdges)
        return self

    def apply(self, ops):
        """ Apply ops to tensor """

        for op in ops:
            # If we're initialise -- createTensor => |0>
            if op is None:
                continue

            if op.name == "CX":
                gate = QuESTFunc.controlledNot
                args = [0, 2]
            elif op.name == "U":
                gate = QuESTFunc.hadamard
                args = [0]

            if gate.control:
                for qubit, index in zip(self.qubits, self.indices):
                    if index[0] == op.qargs[gate.control-1][1]:
                        print("Control")
                        # physical qubit is the control, virtual qubit is the target
                        print(args)
                        TNAdd.TN_controlledGateControlHalf(gate, self.tensor, *args)
                    elif index[1] == op.qargs[gate.control-1][1]:
                        print("Target")
                        # virtual qubit is the control, physical qubit is the target
                        print(args[::-1])
                        TNAdd.TN_controlledGateTargetHalf(gate, self.tensor, *args[::-1])
            else:
                for qubit in self.qubits:
                    if op.qargs[0][1] == qubit:
                        TNAdd.TN_singleQubitGate(gate, self.tensor, qubit)
