from .QASMTypes import *
from .QASMParser import ProgFile
import numpy as np
import itertools as it
import sys
import copy
from math import log2, exp

def exp_add(a, b):
    if b == 0: return a
    if a == 0: return b

    # Assume that for very large numbers the 1 is irrelevant
    if a > 30 or b > 30:
        return a + b
    
    if a > b:
        out = log2( 2**(a - b) + 1 ) + b
    else:
        out = log2( 2**(b - a) + 1 ) + a
    return out

def slice_cost(mat, slice_, max):
    qubit_cost = 0
    cut_cost = 0
    cut_prev = 0
    work = mat.copy()

    for cut in slice_:
        cut_cost = exp_add(cut_cost, work[cut].sum())
        work[cut] = 0
        # work[:][:cut] = 0
        cut += 1
        qubit_cost = exp_add(qubit_cost,  (cut - cut_prev))
        cut_prev = cut
        # Early exit for large values
        if exp_add(qubit_cost, cut_cost) > max: return exp_add(qubit_cost, cut_cost)
    # Catch remainder
    if cut_prev != len(mat):
        qubit_cost = exp_add(qubit_cost,  (len(mat) - cut_prev))
    total_cost = exp_add(qubit_cost, cut_cost)
    print("HI", slice_, qubit_cost, cut_cost, total_cost, max)
    return total_cost
    
def slice_adjmat(mat):
    slices = it.chain.from_iterable( it.combinations(range(len(mat)), i) for i in rangeP1(1,len(mat)) )
    base = len(mat)
    best_slice = ()
    for potential_slice in slices:

        total_cost = slice_cost(mat, potential_slice, base)

        if base > total_cost:
            base = total_cost
            best_slice = potential_slice

    print(2**base, best_slice, 2**slice_cost(mat, best_slice, base))
    return best_slice
    
def print_adjmat(regNames, mat):
    row_format ="{:^8}" * (len(mat) + 1)
    print(row_format.format("", *regNames))
    for reg, row in zip(regNames, mat):
        print(row_format.format(reg, *row))
    print()

def calculate_adjmat(code):
    def update_adjmat(block):
        for i,j in it.permutations(*block.line.nonzero(), 2):
            adjMat[i,j] += 1

    class QubitBlock:
        def __init__(self,size):
            self.line = np.zeros(size, dtype=np.int8)
            self.nQubits = size

        def set_qubits(self, s = 0, range_ = None):
            if range_ is None:
                for i in range(self.nQubits):
                    self.line[i] = s

            elif isinstance(range_, int):
                self.line[range_] = s

            elif isinstance(range_, tuple):
                for i in range(*range_):
                    self.line[i] = s

            elif isinstance(range_, list):
                for i in range_:
                    self.line[i] = s

    def parse_code(self, args = {}, spargs = {}):
        maths = lambda x: self._resolve_maths( x, additional_vars = spargs)

        code = self._code

        block = QubitBlock(nQubits)

        for line in code:

            if isinstance(line, CallGate):
                if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                    # Prepare args and enter function
                    spargsSend = dict( ((arg.name, maths(sparg.val) )
                                       for arg, sparg in zip(line.callee._spargs, line._spargs)))
                    if line._loops is not None:
                        for loopVar in range(maths(line._loops.start[0]), maths(line._loops.end[0])):
                            qargsSend = dict( (arg.name, resolve_arg(self, qarg, args, spargs, loopVar) )
                                         for arg, qarg in zip(line.callee._qargs, line._qargs))
                            parse_code(line.callee, args = qargsSend, spargs = spargsSend)
                    else:
                        qargsSend = dict( (arg.name, resolve_arg(self, qarg, args, spargs))
                                     for arg, qarg in zip(line.callee._qargs, line._qargs))
                        parse_code(line.callee, args = qargsSend, spargs = spargsSend)

                    del qargsSend
                    del spargsSend
                    continue

                qargs = line._qargs

                if line._loops is not None:
                    for loopVar in range(line._loops.start[0], line._loops.end[0]+1):
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
                a = rangeP1(*line._pargs[1])
                b = rangeP1(*line._qargs[1])
                for i in range(len(a)):
                    args[line.alias.name][a[i]] = resolve_arg(self, (line._qargs[0], b[i]), args, spargs)

            elif isinstance(line, Alias):
                args[line.name] = [None]*line.size

            elif isinstance(line, Loop):
                spargsSend = dict( **spargs )
                for i in range(maths(line.start[0]), maths(line.end[0])):
                    spargsSend[line.loopVar.name] = i
                    parse_code(line, args = args, spargs = spargsSend)
                del spargsSend

    regs = [ reg for reg in code._code if type(reg).__name__ == "QuantumRegister" ]
    nQubits = QuantumRegister.numQubits
    adjMat = np.zeros( (nQubits, nQubits), dtype=np.int32 )

    parse_code(code)
    return adjMat

class QubitLine:
    def __init__(self, size):
        self.line = [" "]*size
        self.nQubits = size
        self.isIf = False

    def set_qubits(self, s = "|", range_ = None):
        if range_ is None:
            for i in range(self.nQubits):
                self.line[i] = s

        elif isinstance(range_, int):
            self.line[range_] = s

        elif isinstance(range_, tuple):
            for i in range(*range_):
                self.line[i] = s

        elif isinstance(range_, list):
            for i in range_:
                self.line[i] = s

    def write(self):
        print(*(f"{elem:<2.2}" for elem in self.line), end = "")
        print("?") if self.isIf else print()

    def write_classical(self):
        start = 3*self.nQubits//2 - 6
        end = 3*self.nQubits - 11 - start
        print("*"*start, " Classical ", "*"*end)

def sliceP1(start = None, stop = None, step = None):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)

def rangeP1(start = None, stop = None, step = 1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

def resolve_arg( self, var, args, spargs, loopVar = None ):
    var, ind = var
    maths = lambda x: self._resolve_maths( x, additional_vars = spargs)

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
        if isinstance(out, (list,tuple)):
            if isinstance(out, tuple) and len(out) == 2:
                *out, = range(*out)
            if isinstance(ind, int):
                return out[ind]
            elif isinstance(ind, (list, tuple)):
                return list(out[sliceP1(*ind)])
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

def quickDispl(self, topLevel = False, args = {}, spargs = {}):
    #print(self.name, *args, *spargs)
    code = self._code
    nQubits = QuantumRegister.numQubits
    printLn = QubitLine(nQubits)

    maths = lambda x: self._resolve_maths( x, additional_vars = spargs)

    # Print header
    if topLevel:
        regs = [ reg for reg in code if type(reg).__name__ == "QuantumRegister" ]
        printLn.line = list(map(str,range(nQubits)))
        printLn.write()
        P = 0
        for reg in regs:
            for i in range(reg.size):
                printLn.line[P] = reg.name
                P += 1
        printLn.write()
        printLn.set_qubits("0")
        printLn.write()

    for line in code:
        printLn.set_qubits()
        if isinstance(line, CallGate):
            if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                # Prepare args and enter function
                spargsSend = dict( ((arg.name, maths(sparg.val) )
                                   for arg, sparg in zip(line.callee._spargs, line._spargs)))
                if line._loops is not None:
                    for loopVar in range(maths(line._loops.start[0]), maths(line._loops.end[0])):
                        qargsSend = dict( (arg.name, resolve_arg(self, qarg, args, spargs, loopVar) )
                                     for arg, qarg in zip(line.callee._qargs, line._qargs))
                        quickDispl(line.callee, args = qargsSend, spargs = spargsSend)
                else:
                    qargsSend = dict( (arg.name, resolve_arg(self, qarg, args, spargs))
                                 for arg, qarg in zip(line.callee._qargs, line._qargs))
                    quickDispl(line.callee, args = qargsSend, spargs = spargsSend)

                del qargsSend
                del spargsSend
                continue

            qargs = line._qargs

            if line._loops is not None:
                for loopVar in range(line._loops.start[0], line._loops.end[0]+1):
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
            a = rangeP1(*line._pargs[1])
            b = rangeP1(*line._qargs[1])
            for i in range(len(a)):
                args[line.alias.name][a[i]] = resolve_arg(self, (line._qargs[0], b[i]), args, spargs)

        elif isinstance(line, Alias):
            args[line.name] = [None]*line.size

        elif isinstance(line, Loop):
            spargsSend = dict( **spargs )
            for i in range(maths(line.start[0]), maths(line.end[0])):
                spargsSend[line.loopVar.name] = i
                quickDispl(line, args = args, spargs = spargsSend)
            del spargsSend

        elif isinstance(line, CBlock):
            printLn.write_classical()
depth = 0
maxDepth = -1
