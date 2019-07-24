"""
Module to perform analysis for partitioning tensor network representation of state for memory optimisation.
"""
import copy
import itertools as it
from math import log2
import numpy as np
from .QASMTypes import (CallGate, QuantumRegister, Opaque, SetAlias, Alias, Loop, CBlock)

def exp_add(a: float, b: float):
    """ The the exponents of two numbers """
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
    print("HI", currSlice, qubitCost, cutCost, totalCost, best)
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

    print(2**base, bestSlice, 2**slice_cost(mat, bestSlice, base))
    return bestSlice

def print_adjmat(regNames, mat):
    """ Print the adjacency matrix in a pretty form """
    rowFormat = "{:^8}" * (len(mat) + 1)
    print(rowFormat.format("", *regNames))
    for reg, row in zip(regNames, mat):
        print(rowFormat.format(reg, *row))
    print()

def calculate_adjmat(code):
    """ Calculate the entanglement adjacency from a code block """
    def update_adjmat(block):
        """ Set the appropriate elements of the adjacency matrix """
        for i, j in it.permutations(*block.line.nonzero(), 2):
            adjMat[i, j] += 1

    class QubitBlock:
        """ Class to store information about Qubits """
        def __init__(self, size):
            self.line = np.zeros(size, dtype=np.int8)
            self.nQubits = size

        def set_qubits(self, value=0, ranges=None):
            """ Set labels to qubits """
            if ranges is None:
                for i in range(self.nQubits):
                    self.line[i] = value

            elif isinstance(ranges, int):
                self.line[ranges] = value

            elif isinstance(ranges, tuple):
                for i in range(*ranges):
                    self.line[i] = value

            elif isinstance(ranges, list):
                for i in ranges:
                    self.line[i] = value

    def parse_code(self, args=(), spargs=()):
        """ Traverse code recursively updating the adjacency matrix accordingly """
        maths = lambda x: self.resolve_maths(x, additional_vars=spargs)

        code = self.code

        block = QubitBlock(nQubits)

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
                            parse_code(line.callee, args=qargsSend, spargs=spargsSend)
                    else:
                        qargsSend = dict((arg.name, resolve_arg(self, qarg, args, spargs))
                                         for arg, qarg in zip(line.callee.qargs, line.qargs))
                        parse_code(line.callee, args=qargsSend, spargs=spargsSend)

                    del qargsSend
                    del spargsSend
                    continue

                qargs = line.qargs

                if line.loops is not None:
                    for loopVar in range(line.loops.start[0], line.loops.end[0]+1):
                        block.set_qubits()
                        for qarg in qargs:
                            block.set_qubits(1, resolve_arg(self, qarg, args, spargs, loopVar))
                        update_adjmat(block)
                else:
                    block.set_qubits()
                    for qarg in qargs:
                        block.set_qubits(1, resolve_arg(self, qarg, args, spargs))
                    update_adjmat(block)

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
                    parse_code(line, args=args, spargs=spargsSend)
                del spargsSend

    nQubits = QuantumRegister.numQubits
    adjMat = np.zeros((nQubits, nQubits), dtype=np.int32)

    parse_code(code)
    return adjMat

class QubitLine:
    """ Type to store graph of entanglement """
    def __init__(self, size):
        self.line = [" "]*size
        self.nQubits = size
        self.isIf = False

    def set_qubits(self, value="|", ranges=None):
        """ Set labels to qubits """
        if ranges is None:
            for i in range(self.nQubits):
                self.line[i] = value

        elif isinstance(ranges, int):
            self.line[ranges] = value

        elif isinstance(ranges, tuple):
            for i in range(*ranges):
                self.line[i] = value

        elif isinstance(ranges, list):
            for i in ranges:
                self.line[i] = value

    def write(self):
        """ Print the qubit list """
        print(*(f"{elem:<2.2}" for elem in self.line), end="")
        if self.isIf:
            print("?")
        else:
            print()

    def write_classical(self):
        """ Print an appropriately scaled classical line """
        # start = 3*self.nQubits//2 - 6
        # end = 3*self.nQubits - 11 - start
        print("{:*^{width}}".format(' Classical ', width=3*self.nQubits))
#        print("*"*start, " Classical ", "*"*end)

def slice_inclusive(start=None, stop=None, step=None):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)

def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

def resolve_arg(self, var, args, spargs, loopVar=None):
    """ Determine the actual register point """
    var, ind = var
    maths = lambda x: self.resolve_maths(x, additional_vars=spargs)

    if isinstance(ind, (list, tuple)):
        *ind, = map(maths, ind)
    elif isinstance(ind, str) and loopVar is not None:
        shift = ind.split("_loop")[1]
        shift = shift if shift else 0
        ind = loopVar + int(shift)
    else:
        ind = maths(ind)

    if var.name in args:
        out = copy.copy(args[var.name])
        if isinstance(out, (list, tuple)):
            if isinstance(out, tuple) and len(out) == 2:
                *out, = range(*out)
            if isinstance(ind, int):
                return out[ind]
            elif isinstance(ind, (list, tuple)):
                return list(out[slice_inclusive(*ind)])
            else:
                raise Exception("Cannot handle request")
        elif isinstance(out, int):
            return out

    elif isinstance(ind, (list, tuple)):
        *out, = map(lambda x: var.start + x, ind)
        out[1] += 1
        return tuple(out)
    elif isinstance(ind, int):
        return var.start + ind
    else:
        raise Exception("Cannot handle request")

def print_circuit_diag(self, topLevel=False, args=(), spargs=()):
    """ Recursively traverse the code to print a quick entanglement graph/circuit diagram """
    #print(self.name, *args, *spargs)
    code = self.code
    nQubits = QuantumRegister.numQubits
    printLn = QubitLine(nQubits)

    maths = lambda x: self.resolve_maths(x, additional_vars=spargs)

    # Print header
    if topLevel:
        regs = [reg for reg in code if type(reg).__name__ == "QuantumRegister"]
        printLn.line = list(map(str, range(nQubits)))
        printLn.write()
        j = 0
        for reg in regs:
            for i in range(reg.size):
                printLn.line[j] = reg.name
                j += 1
        printLn.write()
        printLn.set_qubits("0")
        printLn.write()

    for line in code:
        printLn.set_qubits()
        if isinstance(line, CallGate):
            if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                # Prepare args and enter function
                spargsSend = dict(((arg.name, maths(sparg.val))
                                   for arg, sparg in zip(line.callee.spargs, line.spargs)))
                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        qargsSend = dict((arg.name, resolve_arg(self, qarg, args, spargs, loopVar))
                                         for arg, qarg in zip(line.callee.qargs, line.qargs))
                        print_circuit_diag(line.callee, args=qargsSend, spargs=spargsSend)
                else:
                    qargsSend = dict((arg.name, resolve_arg(self, qarg, args, spargs))
                                     for arg, qarg in zip(line.callee.qargs, line.qargs))
                    print_circuit_diag(line.callee, args=qargsSend, spargs=spargsSend)

                del qargsSend
                del spargsSend
                continue

            qargs = line.qargs

            if line.loops is not None:
                for loopVar in range(line.loops.start[0], line.loops.end[0]+1):
                    printLn.set_qubits()
                    for qarg in qargs:
                        printLn.set_qubits(line.name[0:2], resolve_arg(self, qarg, args, spargs, loopVar))
                    printLn.write()
            else:
                printLn.set_qubits()
                for qarg in qargs:
                    printLn.set_qubits(line.name[0:2], resolve_arg(self, qarg, args, spargs))
                printLn.write()

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
                print_circuit_diag(line, args=args, spargs=spargsSend)
            del spargsSend

        elif isinstance(line, CBlock):
            printLn.write_classical()
depth = 0
maxDepth = -1
