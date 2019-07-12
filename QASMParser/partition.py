from .QASMTypes import *
from .QASMParser import ProgFile
import sys

def calculate_adjmat(code):
    regs = [ reg for reg in code if type(reg).__name__ == "QuantumRegister" ]
    nQubits = QuantumRegister.numQubits

def resolve_arg( self, var, args, spargs, loopVar = None ):
    var, ind = var
    maths = lambda x: self._resolve_maths( x, additional_vars = spargs)
    print(ind, loopVar)
    if isinstance(ind, (list, tuple)):
        *ind, = map(maths, ind)
    elif isinstance(ind, str) and loopVar is not None:
        ind = loopVar
    else:
        ind = maths(ind)

    if isinstance(var, Argument):
        if args is not None:
            var = args[var.name]
            if isinstance(var, tuple):
                out = list(range(*var))
                if isinstance(ind, int):
                    return out[ind]
                else:
                    return out[slice(*ind)]
            if isinstance(var, int):
                return var
        else:
            raise Exception("No arguments to function found")

    elif isinstance(ind, (list, tuple)):
        *out, = map(lambda x: var.start + x, ind)
        out[1] += 1
        return tuple(out)
    else:
        return var.start + ind

def quickDispl(self, topLevel = False, args = {}, spargs = {}):
    #print(self.name, *args, *spargs)
    code = self._code
    nQubits = QuantumRegister.numQubits
    printLn = [" "]*nQubits

    maths = lambda x: self._resolve_maths( x, additional_vars = spargs)
    def pp():
        print(*(f"{elem:<2.2}" for elem in printLn), end = "")
        print()
    def set_qubits(s = "|", range_ = (0, nQubits)):
        if isinstance(range_, int): range_ = (range_, range_+1)
        for i in range(*range_):
            printLn[i] = s

    # Print header
    if topLevel:
        regs = [ reg for reg in code if type(reg).__name__ == "QuantumRegister" ]
        *printLn, = map(str,range(nQubits))
        pp()
        P = 0
        for reg in regs:
            for i in range(reg.size):
                printLn[P] = reg.name
                P += 1
        pp()
        set_qubits("0")
        pp()

    for line in code:
        set_qubits()
        if isinstance(line, CallGate):
            if maxDepth < 0 or depth < maxDepth:

                if not isinstance(line.callee, Opaque):
                    spargsSend = dict( ((arg.name, maths(sparg.val) )
                                       for arg, sparg in zip(line.callee._spargs, line._spargs)))
                    if line._loops is not None:
                        for loopVar in range(line._loops.start[0], line._loops.end[0]+1):
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
                    set_qubits()
                    for qarg in qargs:
                        set_qubits(line.name[0:2], resolve_arg(self, qarg, args, spargs, loopVar))
                    pp()
            else:
                set_qubits()
                for qarg in qargs:
                    print("HONK", resolve_arg(self, qarg, args, spargs))
                    set_qubits(line.name[0:2], resolve_arg(self, qarg, args, spargs))
                pp()

        elif isinstance(line, Loop):
            for i in range(maths(line.start[0]), maths(line.end[0])+1):
                spargsSend = dict( **spargs )
                spargsSend[line.name] = i
                print(spargsSend)
                quickDispl(line, args = args, spargs = spargsSend)
            del spargsSend

        elif isinstance(line, CBlock):
            start = 3*nQubits//2 - 6
            end = 3*nQubits - 11 - start
            print("*"*start, " Classical ", "*"*end)

depth = 0
maxDepth = -1
