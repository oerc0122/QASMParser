"""
Contains the definition of an object for defining graph builders and code parsers
"""
from abc import ABC
import numpy as np
from ..parser.types import (resolve_arg, CallGate, Opaque, SetAlias, Alias, Loop, CBlock, Measure)

class GraphBuilder(ABC):
    """ Quantum circuit parser
    define _process for your subclass to perform these operations with respect to qubits
    define _finalise to call this function after all processing has been done
    define _handle_classical to perform special functions on classical operations
    define _handle_measure to perform special functions on measure operations"""
    def __init__(self, code: list, size: int, maxDepth: int):
        self._nQubits = size
        self._involved = np.zeros(self.nQubits, dtype=np.int8)
        self.isIf = False
        self.currOp = None
        self._code = code
        self._maxDepth = maxDepth

    involvedList = property(lambda self: self._involved)
    involved = property(lambda self: self._involved.nonzero())
    qubitsInvolved = property(lambda self: np.flatnonzero(self._involved == 1))
    nQubits = property(lambda self: self._nQubits)
    codeLines = property(lambda self: len(self.code._code))
    code = property(lambda self: self._code)
    maxDepth = property(lambda self: self._maxDepth)

    def _set_qubits(self, value=0, ranges=None):
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

    def _process(self, *args, **kwargs):
        """ Do the necessary processing of the set qubits """
        raise NotImplementedError("No process defined for subclass {}".format(type(self).__name__))

    def _finalise(self, *args, **kwargs):
        """ Finalise and fix code """

    def __process(self, **kwargs):
        """ Perform necessary processing of set qubits """
        self._process(**kwargs)
        self._set_qubits()

    def __finalise(self):
        """ Finalise and fix code """
        self._finalise()

    def _handle_classical(self, **kwargs):
        """ Perform actions based on classical blocks """

    def _handle_measure(self, **kwargs):
        """ Handle measurements """

    def __parse_code(self, codeObject=None, args=None, spargs=None, depth=0):
        """ Traverse code recursively updating the builder accordingly """
        if args is None:
            args = {}
        if spargs is None:
            spargs = {}
        if codeObject is None:
            codeObject = self.code

        recurse = lambda block: self.__parse_code(block,
                                                  args=qargsSend, spargs=spargsSend,
                                                  depth=depth+1)
        maths = lambda x: codeObject.resolve_maths(x, additionalVars=spargs)
        for line in codeObject.code:
            self.currOp = line.name
            if isinstance(line, CallGate):
                if not isinstance(line.callee, Opaque) and (self.maxDepth < 0 or depth < self.maxDepth):
                    # Prepare args and enter function
                    spargsSend = {arg.name: maths(sparg.val) for arg, sparg in zip(line.callee.spargs, line.spargs)}
                    if line.loops is not None:
                        for loopVar in range_inclusive(maths(line.loops.start[0]), maths(line.loops.end[0])):
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
                            self._set_qubits(1, resolve_arg(codeObject, qarg, args, spargs, loopVar))
                        self.__process(lineObj=line)
                else:
                    for qarg in qargs:
                        self._set_qubits(1, resolve_arg(codeObject, qarg, args, spargs))
                    self.__process(lineObj=line)

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
                for i in range_inclusive(maths(line.start[0]), maths(line.end[0])):
                    spargsSend[line.loopVar.name] = i
                    recurse(line)
                del qargsSend
                del spargsSend

            elif isinstance(line, CBlock):
                self._handle_classical(lineObj=line)

            elif isinstance(line, Measure):
                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        self._set_qubits(1, resolve_arg(codeObject, line.qargs, args, spargs, loopVar))
                        self._handle_measure(lineObj=line)
                else:
                    self._set_qubits(1, resolve_arg(codeObject, line.qargs, args, spargs))
                    self._handle_measure(lineObj=line)

        if depth == 0:
            self.__finalise()

def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)
