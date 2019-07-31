"""
Module handling the adjacency matrix method of partitioning
"""
import itertools as it
from math import log2
import numpy as np
from .QASMTypes import (resolve_arg, CallGate, Opaque, SetAlias, Alias, Loop, QuantumRegister)

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

def slice_cost(mat: np.ndarray, currSlice: tuple, best: float):
    """ Calculate the cost of a slice of given matrix mat """
    qubitCost = 0
    cutCost = 0
    cutPrev = 0
    work = mat.copy()

    for cut in currSlice:
        cutCost = exp_add(cutCost, work[cut].sum())
        work[cut] = 0
        # work[:][:cut] = 0
        cut += 1
        qubitCost = exp_add(qubitCost, (cut - cutPrev))
        cutPrev = cut
        # Early exit for large values
        if exp_add(qubitCost, cutCost) > best:
            return exp_add(qubitCost, cutCost)
    # Catch remainder
    if cutPrev != len(mat):
        qubitCost = exp_add(qubitCost, (len(mat) - cutPrev))
    totalCost = exp_add(qubitCost, cutCost)

    return totalCost

def slice_adjmat(mat):
    """ Calculate the optimal slice of adjacency matrix mat """
    slices = it.chain.from_iterable(it.combinations(range(len(mat)), i) for i in range_inclusive(1, len(mat)))
    base = len(mat)
    bestSlice = ()
    for potentialSlice in slices:

        totalCost = slice_cost(mat, potentialSlice, base)

        if base > totalCost:
            base = totalCost
            bestSlice = potentialSlice

    print(bestSlice, len(mat), slice_cost(mat, bestSlice, base))

    return bestSlice

def print_adjmat(regNames, mat):
    """ Print the adjacency matrix in a pretty form """
    rowFormat = "{:^8}" * (len(mat) + 1)
    print(rowFormat.format("", *regNames))
    for reg, row in zip(regNames, mat):
        print(rowFormat.format(reg, *row))
    print()


class AdjMatBuilder:
    """ Class to store information about Qubits """
    def __init__(self, size):
        self.nQubits = size
        self.line = np.zeros(self.nQubits, dtype=np.int8)
        self.adjMat = np.zeros((self.nQubits, self.nQubits), dtype=np.int32)

    def set_qubits(self, value=0, ranges=None):
        """ Set labels to qubits """
        if ranges is None:
            self.line[:] = value

        elif isinstance(ranges, int):
            self.line[ranges] = value

        elif isinstance(ranges, tuple):
            for i in range(*ranges):
                self.line[i] = value

        elif isinstance(ranges, list):
            for i in ranges:
                self.line[i] = value

    def update_adjmat(self):
        """ Set the appropriate elements of the adjacency matrix """
        for i, j in it.permutations(*self.line.nonzero(), 2):
            self.adjMat[i, j] += 1

def calculate_adjmat(code, maxDepth=999):
    """ Calculate the entanglement adjacency from a code block """

    adjMat = AdjMatBuilder(QuantumRegister.numQubits)
    parse_code(code, adjMat, maxDepth=maxDepth)
    return adjMat.adjMat

def parse_code(self, adjMat, args=None, spargs=None, depth=0, maxDepth=-1):
    """ Traverse code recursively updating the adjacency matrix accordingly """

    if args is None:
        args = {}
    if spargs is None:
        spargs = {}

    recurse = lambda block: parse_code(block, adjMat,
                                       args=qargsSend, spargs=spargsSend,
                                       depth=depth+1, maxDepth=maxDepth)
    maths = lambda x: self.resolve_maths(x, additionalVars=spargs)

    code = self.code

    for line in code:

        if isinstance(line, CallGate):
            if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                # Prepare args and enter function
                spargsSend = dict(((arg.name, maths(sparg.val))
                                   for arg, sparg in zip(line.callee.spargs, line.spargs)))
                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        qargsSend = dict((arg.name, resolve_arg(self, qarg, args, spargs, loopVar))
                                         for arg, qarg in zip(line.callee.qargs, line.qargs))
                        recurse(line.callee)
                else:
                    qargsSend = dict((arg.name, resolve_arg(self, qarg, args, spargs))
                                     for arg, qarg in zip(line.callee.qargs, line.qargs))
                    recurse(line.callee)

                del qargsSend
                del spargsSend
                continue

            qargs = line.qargs

            if line.loops is not None:
                for loopVar in range(line.loops.start[0], line.loops.end[0]+1):
                    adjMat.set_qubits()
                    for qarg in qargs:
                        adjMat.set_qubits(1, resolve_arg(self, qarg, args, spargs, loopVar))
                    adjMat.update_adjmat()
            else:
                adjMat.set_qubits()
                for qarg in qargs:
                    adjMat.set_qubits(1, resolve_arg(self, qarg, args, spargs))
                adjMat.update_adjmat()

        elif isinstance(line, SetAlias):
            a = range_inclusive(*line.pargs[1])
            b = range_inclusive(*line.qargs[1])
            for i, elem in enumerate(a):
                args[line.alias.name][elem] = resolve_arg(self, (line.qargs[0], b[i]), args, spargs)

        elif isinstance(line, Alias):
            args[line.name] = [None]*line.size

        elif isinstance(line, Loop):
            spargsSend = dict(**spargs)
            for i in range(maths(line.start[0]), maths(line.end[0])):
                spargsSend[line.loopVar.name] = i
                recurse(line)
            del spargsSend
