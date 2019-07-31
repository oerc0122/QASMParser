"""
Module to perform analysis for partitioning tensor network representation of state for memory optimisation.
"""
from .QASMTypes import (resolve_arg, CallGate, QuantumRegister, Opaque, SetAlias, Alias, Loop, CBlock)

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
        print("{:*^{width}}".format(' Classical ', width=3*self.nQubits))


def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)

def print_circuit_diag(self, topLevel=False, args=None, spargs=None, depth=0, maxDepth=-1):
    """ Recursively traverse the code to print a quick entanglement graph/circuit diagram """
    #print(self.name, *args, *spargs)
    code = self.code
    nQubits = QuantumRegister.numQubits
    printLn = QubitLine(nQubits)

    if args is None:
        args = {}
    if spargs is None:
        spargs = {}

    recurse = lambda block: print_circuit_diag(block,
                                               args=qargsSend, spargs=spargsSend,
                                               depth=depth+1, maxDepth=maxDepth)
    maths = lambda x: self.resolve_maths(x, additionalVars=spargs)

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
                for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])+1):
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
            qargsSend = args
            for i in range(maths(line.start[0]), maths(line.end[0])):
                spargsSend[line.loopVar.name] = i
                recurse(line)
            del spargsSend

        elif isinstance(line, CBlock):
            printLn.write_classical()
