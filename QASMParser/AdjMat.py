"""
Module handling the adjacency matrix method of partitioning
"""
import itertools as it
from math import log2, inf
import numpy as np
from .QASMTypes import (QuantumRegister)
from .CodeGraph import (BaseGraphBuilder, range_inclusive, parse_code)

def exp_add(a: float, b: float):
    """ Add the exponents of two numbers

    :param a: input exponent
    :param b: input exponent
    :returns: Sum of exponents"""
    if b == 0:
        return a
    if a == 0:
        return b

    # Assume that for very large numbers the 1 is irrelevant
    if a > 30 or b > 30:
        return a + b

    if a > b:
        out = log2(2**(a - b) + 1) + b
    else:
        out = log2(2**(b - a) + 1) + a
    return out

class AdjMat(np.ndarray, BaseGraphBuilder):
    """ Quantum circuit adjacency matrix """
    def __new__(cls, size):
        obj = np.ndarray.__new__(cls, (size, size), dtype=np.int32)
        return obj

    def __init__(self, size):
        self[:, :] = 0
        BaseGraphBuilder.__init__(self, size)

    @property
    def potentialSlices(self):
        """ Return a generator of all possible slices of current adjmat """
        return it.chain.from_iterable(it.combinations(range(self.nQubits), i)
                                      for i in range_inclusive(1, self.nQubits))

    def process(self):
        """ Set the appropriate elements of the adjacency matrix """
        for i, j in it.permutations(*self._involved.nonzero(), 2):
            self[i, j] += 1
        self._involved[:] = 0

    def slice_cost(self, currSlice: tuple, best: float = inf):
        """ Calculate the cost of a slice of given matrix mat """
        qubitCost = 0
        cutCost = 0
        cutPrev = 0
        work = self.copy()

        for cut in currSlice:
            cutCost = exp_add(cutCost, work[cut].sum())
            work[cut] = 0
            cut += 1
            qubitCost = exp_add(qubitCost, (cut - cutPrev))
            cutPrev = cut
            # Early exit for large values
            if exp_add(qubitCost, cutCost) > best:
                return exp_add(qubitCost, cutCost)
        # Catch remainder
        if cutPrev != len(self):
            qubitCost = exp_add(qubitCost, (len(self) - cutPrev))
        totalCost = exp_add(qubitCost, cutCost)

        return totalCost

    def divide_qubits(self, slices: tuple):
        """ Calculate the number of virtual qubits created by this slice """
        prev = 0
        nVirtualQubits = []
        qubitRanges = []
        self.print_data()
        for currSlice in slices:
            qubitRanges.append(range(prev, currSlice))
            nVirtualQubits.append(int(self[prev:currSlice, :prev].sum() + self[prev:currSlice, currSlice:].sum()))
            prev = currSlice

        # Catch remainder
        currSlice = self.nQubits
        if prev != currSlice:
            qubitRanges.append(range(prev, currSlice))
            nVirtualQubits.append(int(self[prev:currSlice, :prev].sum() + self[prev:currSlice, currSlice:].sum()))
        print(qubitRanges, nVirtualQubits)
        return qubitRanges, nVirtualQubits

    def print_data(self, regNames=None):
        """ Print the adjacency matrix in a pretty form """
        if regNames is None:
            regNames = [f"[{qubit}]" for qubit in range(self.nQubits)]
        rowFormat = "{:^8}" * (self.nQubits + 1)
        print(rowFormat.format("", *regNames))
        for reg, row in zip(regNames, self):
            print(rowFormat.format(reg, *row))
        print()

def best_slice_adjmat(mat):
    """ Calculate the optimal slice of adjacency matrix mat """
    base = mat.nQubits
    bestSlice = ()
    for potentialSlice in mat.potentialSlices:

        totalCost = mat.slice_cost(potentialSlice, base)

        if base > totalCost:
            base = totalCost
            bestSlice = potentialSlice

    return bestSlice

def calculate_adjmat(code, maxDepth=999):
    """ Calculate the entanglement adjacency from a code block """
    adjMat = AdjMat(QuantumRegister.numQubits)
    parse_code(code, adjMat, maxDepth=maxDepth)
    return adjMat
