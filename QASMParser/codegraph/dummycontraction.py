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
        self.edges = edges
        self.indices = indices
        self.qubits = qubits
        self._memCost = 0
        self._timeCost = 0
        self.add_cost(self.malloc_cost())
        self._init_entangle()
        self.apply(ops)

    timeCost = property(lambda self: self._timeCost)
    memCost = property(lambda self: self._memCost)
    @property
    def cost(self):
        return (self._memCost, self._timeCost)

    def add_cost(self, val):
        self._timeCost += val[0]
        self._memCost += val[1]
        
    
    nPhys = property(lambda self: self._nPhys)
    nVirt = property(lambda self: self._nVirt)
    tensor = property(lambda self: self._tensor)
    # edges = property(lambda self: self._edges)
    # indices = property(lambda self: self._indices)
    # qubits = property(lambda self: self._qubits)
    nQubits = property(lambda self: len(self.qubits))

    qubitCost = property(lambda self: exp_add(self.nPhys, self.nVirt))

    def malloc_cost(self):
        return (self.qubitCost, self.qubitCost)

    def contract_cost(self, other):
        return (0, exp_add(self.qubitCost, other.qubitCost))

    def gate_cost(self):
        """ Cost of a gate, no memory overhead """
        return (0, self.qubitCost)

    def _init_entangle(self):
        """ Entangle first virtual with physical qubit """
        self.add_cost(self.gate_cost())

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
        print(self.qubits, other.qubits)
        print("HI", self.edges, other.edges, flush=True)
        return ([edge[::-1] in other.edges or
                 edge in other.edges for edge in self.edges],
                [edge[::-1] in self.edges or
                 edge in self.edges for edge in other.edges])

    def contract(self, other):
        """ Contract two tensor nodes and update the respective properties """
        contractionEdges = self._compute_contraction_edges(other)
        self.add_cost(self.contract_cost(other))
        self._inherit(other, contractionEdges)
        return self

    def apply(self, ops):
        """ Apply ops to tensor """
        for op in ops:
            self.add_cost(self.gate_cost())
