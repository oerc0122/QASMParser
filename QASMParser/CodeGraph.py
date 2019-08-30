"""
Contains routines to traverse the parsed code and build graphs
"""

import numpy as np
from .QASMTypes import (resolve_arg, CallGate, Opaque, SetAlias, Alias, Loop, CBlock, Measure)

class BaseGraphBuilder():
    """ Quantum circuit adjacency matrix """
    def __init__(self, size):
        self._nQubits = size
        self._involved = np.zeros(self.nQubits, dtype=np.int8)
        self.isIf = False
        self.currOp = None

    @property
    def nQubits(self):
        """ nQubits getter """
        return self._nQubits

    def set_qubits(self, value=0, ranges=None):
        """ Set labels to qubits """
        if ranges is None:
            self._involved[:] = value

        elif isinstance(ranges, int):
            self._involved[ranges] = value

        elif isinstance(ranges, tuple):
            for i in range(*ranges):
                self._involved[i] = value

        elif isinstance(ranges, list):
            for i in ranges:
                self._involved[i] = value

    def process(self, **kwargs):
        """ Perform necessary processing of set qubits """

    def handle_classical(self, **kwargs):
        """ Perform actions based on classical blocks """

    def handle_measure(self, **kwargs):
        """ Handle measurements """

def parse_code(codeObject, builder, args=None, spargs=None, depth=0, maxDepth=-1):
    """ Traverse code recursively updating the builder accordingly """
    if args is None:
        args = {}
    if spargs is None:
        spargs = {}

    recurse = lambda block: parse_code(block, builder,
                                       args=qargsSend, spargs=spargsSend,
                                       depth=depth+1, maxDepth=maxDepth)
    maths = lambda x: codeObject.resolve_maths(x, additionalVars=spargs)
    for line in codeObject.code:
        builder.currOp = line.name
        if isinstance(line, CallGate):
            if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                # Prepare args and enter function
                spargsSend = dict(((arg.name, maths(sparg.val))
                                   for arg, sparg in zip(line.callee.spargs, line.spargs)))
                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        qargsSend = dict((arg.name, resolve_arg(codeObject, qarg, args, spargs, loopVar))
                                         for arg, qarg in zip(line.callee.qargs, line.qargs))
                        recurse(line.callee)
                else:
                    qargsSend = dict((arg.name, resolve_arg(codeObject, qarg, args, spargs))
                                     for arg, qarg in zip(line.callee.qargs, line.qargs))
                    recurse(line.callee)

                del spargsSend
                continue

            qargs = line.qargs

            if line.loops is not None:
                for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                    for qarg in qargs:
                        builder.set_qubits(1, resolve_arg(codeObject, qarg, args, spargs, loopVar))
                    builder.process(lineObj=line)
            else:
                for qarg in qargs:
                    builder.set_qubits(1, resolve_arg(codeObject, qarg, args, spargs))
                builder.process(lineObj=line)

        elif isinstance(line, SetAlias):
            a = range_inclusive(*line.pargs[1])
            b = range_inclusive(*line.qargs[1])
            for i, elem in enumerate(a):
                args[line.alias.name][elem] = resolve_arg(codeObject, (line.qargs[0], b[i]), args, spargs)

        elif isinstance(line, Alias):
            args[line.name] = [None]*line.size

        elif isinstance(line, Loop):
            spargsSend = dict(**spargs)
            qargsSend = args
            for i in range(maths(line.start[0]), maths(line.end[0])):
                spargsSend[line.loopVar.name] = i
                recurse(line)
            del qargsSend
            del spargsSend

        elif isinstance(line, CBlock):
            builder.handle_classical(lineObj=line)

        elif isinstance(line, Measure):
            builder.handle_measure(lineObj=line)

def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)


def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)
