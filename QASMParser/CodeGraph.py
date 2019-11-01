"""
Contains routines to traverse the parsed code and build graphs
"""

import numpy as np
from .QASMTypes import (resolve_arg, CallGate, Opaque, SetAlias, Alias, Loop, CBlock, Measure)
import QASMParser.Analytics as Analytics
import QASMParser.CircuitDiag as CircuitDiag
import QASMParser.AdjMat as AdjMat
import QASMParser.GraphPartition as GraphPartition


class GraphBuilder():
    """ Quantum circuit preprocessing analysis """
    def __init__(self, size, code, analyse=False, printASCII=False, partition=0, **kwargs):
        self._nQubits = size
        self._involved = np.zeros(self.nQubits, dtype=np.int8)
        self.isIf = False
        self.currOp = None
        self._code = code

        # Options
        
        self.codeAnalysis = analyse
        self.printASCII = printASCII
        self.adjmatPartition = partition in [1, 2]
        self.graphPartition = partition == 2
        self.setup()
        
    involvedList = property(lambda self: self._involved)
    involved = property(lambda self: self._involved.nonzero())
    qubitsInvolved = property(lambda self: np.flatnonzero(self._involved == 1))
    nQubits = property(lambda self: self._nQubits)
    codeLines = property(lambda self: len(self.code._code))
    code = property(lambda self: self._code)


    
    def setup(self):
        if self.codeAnalysis:
            Analytics.setup(self)
        if self.printASCII:
            print(CircuitDiag.header(self.nQubits, self.code))
        if self.adjmatPartition:
            AdjMat.setup(self)
        if self.graphPartition:
            GraphPartition.setup(self)

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
        if self.codeAnalysis:
            Analytics.process(self)
        if self.printASCII:
            print(CircuitDiag.process(self))
        if self.adjmatPartition:
            AdjMat.process(self)
        if self.graphPartition:
            GraphPartition.process(self)
        self.set_qubits()

    def finalise(self):
        if self.codeAnalysis:
            Analytics.analyse(self.analysis)
        if self.graphPartition:
            GraphPartition.finalise()
            
    def handle_classical(self, **kwargs):
        """ Perform actions based on classical blocks """
        if self.printASCII:
            print(CircuitDiag.handle_classical(self))

    def handle_measure(self, **kwargs):
        """ Handle measurements """
        if self.printASCII:
            print(CircuitDiag.handle_measure(self))

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
                spargsSend = {arg.name: maths(sparg.val) for arg, sparg in zip(line.callee.spargs, line.spargs)}
                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        qargsSend = {arg.name: resolve_arg(codeObject, qarg, args, spargs, loopVar)
                                     for arg, qarg in zip(line.callee.qargs, line.qargs)}
                        recurse(line.callee)
                else:
                    qargsSend = {arg.name: resolve_arg(codeObject, qarg, args, spargs)
                                 for arg, qarg in zip(line.callee.qargs, line.qargs)}
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
