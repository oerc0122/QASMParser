"""
Module handling the adjacency matrix method of partitioning
"""
import itertools as it
from math import log2, inf
import numpy as np

def finalise(codeGraph, code, partition):
    if partition == 1:
        mat = codeGraph.adjMat
        bestSlice = [reg.end-1 for reg in code.quantumRegisters]

        print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))

    elif partition == 2:
        mat = codeGraph.adjMat
        bestSlice = mat.best_slice_adjmat()

        print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))


def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

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

def setup(obj):
    """ Add an adjacency matrix to the main object """
    obj.adjMat = AdjMat(obj.nQubits)

def process(obj, **_):
    """ Build the adjacency matrix """
    for i, j in it.permutations(obj.involved, 2):
        obj.adjMat[i, j] += 1

class AdjMat(np.ndarray):
    """ Quantum circuit adjacency matrix """
    def __new__(cls, size):
        obj = np.ndarray.__new__(cls, (size, size), dtype=np.int32)
        return obj

    def __init__(self, size):
        self[:, :] = 0
        self._nQubits = size

    nQubits = property(lambda self: self._nQubits)

    @property
    def potentialSlices(self):
        """ Return a generator of all possible slices of current adjmat """
        return it.chain.from_iterable(it.combinations(range(self.nQubits), i)
                                      for i in range_inclusive(1, self.nQubits))

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

    def __repr__(self):
        return self.to_str()

    def to_str(self, regNames=None):
        """ Print the adjacency matrix in a pretty form """
        if regNames is None:
            regNames = [f"[{qubit}]" for qubit in range(self.nQubits)]
        rowFormat = "{:^8}" * (self.nQubits + 1)
        out = rowFormat.format("", *regNames)
        for reg, row in zip(regNames, self):
            out += rowFormat.format(reg, *row)
        return out

    def best_slice_adjmat(self):
        """ Calculate the optimal slice of adjacency matrix """
        base = self.nQubits
        bestSlice = ()
        for potentialSlice in self.potentialSlices:

            totalCost = self.slice_cost(potentialSlice, base)

            if base > totalCost:
                base = totalCost
                bestSlice = potentialSlice

        return bestSlice
