"""
Module containing dummy contraction methods to calculate cost of contraction without any maths
"""
from .utility import exp_add

class TensorNode:
    """ Class to represent tensors and perform contractions """
    def __init__(self, nPhys, nVirt, edges, indices, qubits, ops):
        global ENV
        self._tensor = None
        self._nPhys = nPhys
        self._nVirt = nVirt
        self._edges = edges
        self._indices = indices
        self._qubits = qubits
        self._timeCost = self.malloc_time(self)
        self._memCost = self.qubitCost
        self._init_entangle()
        self.apply(ops)

    timeCost = property(lambda self: self._timeCost)
    memCost = property(lambda self: self._memCost)
    cost = property(lambda self: (self._memCost, self._timeCost))

    nPhys = property(lambda self: self._nPhys)
    nVirt = property(lambda self: self._nVirt)
    tensor = property(lambda self: self._tensor)
    edges = property(lambda self: self._edges)
    indices = property(lambda self: self._indices)
    qubits = property(lambda self: self._qubits)
    nQubits = property(lambda self: len(self.qubits))

    qubitCost = property(lambda self: exp_add(self.nPhys, self.nVirt))

    def malloc_time(self):
        return 1

    def contract_cost(self, other):
        return 1

    def gate_cost(self):
        return 1

    def _init_entangle(self):
        """ Entangle first virtual with physical qubit """
        self._timeCost += self.gate_cost(self)

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
        self._timeCost += self.contract_cost(self, other)
        self._inherit(other, contractionEdges)
        return self

    def apply(self, ops):
        """ Apply ops to tensor """

        for op in ops:
            self._timeCost, self._memCost += self.gate_cost(self)
