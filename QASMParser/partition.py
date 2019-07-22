from .QASMTypes import *
from .QASMParser import ProgFile
import sys


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

def calculate_adjmat(code):
    regs = [ reg for reg in code if type(reg).__name__ == "QuantumRegister" ]
    nQubits = QuantumRegister.numQubits

def resolve_arg( self, var, args, spargs, loopVar = None ):
    var, ind = var
    maths = lambda x: self._resolve_maths( x, additional_vars = spargs)

    if isinstance(ind, (list, tuple)):
        *ind, = map(maths, ind)
    elif isinstance(ind, str) and loopVar is not None:
        ind = loopVar
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
            for i in range(maths(line.start[0]), maths(line.end[0])):
                spargsSend = dict( **spargs )
                spargsSend[line.loopVar.name] = i
                quickDispl(line, args = args, spargs = spargsSend)
            del spargsSend

        elif isinstance(line, CBlock):
            printLn.write_classical()
depth = 0
maxDepth = -1
