"""
Module containing main file for parsing
"""

from .types import (QuantumRegister, CodeBlock, Constant, Include, Gate, Circuit, Procedure, Opaque)
from .filehandle import (QASMFile)
from .errors import (includeWarning)

langConstants = ["e", "pi", "T", "F"]

class ProgFile(CodeBlock):
    """
    Main program file.

    Contians routines for converting code to outputlanguages and writing said output to an output file.
    """
    quantumRegisters = property(lambda self: self._quantumRegisters)

    def __init__(self, filename):
        self.filename = filename
        self._name = filename
        self.classLang = None
        CodeBlock.__init__(self, self, QASMFile(filename), False)
        for gate in Gate.internalGates.values():
            self._objs[gate.name] = gate
        for constant in ["e", "pi"]:
            self._objs[constant] = Constant(self, (constant, "float"), (None, None))
        for val, name in enumerate(["F", "T"]):
            self._objs[name] = Constant(self, (name, "bool"), (val, None))
        self.parse_instructions()
        self._quantumRegisters = [reg for reg in self.code if isinstance(reg, QuantumRegister)]
        self._gates = [gate for gate in self.code if isinstance(gate, (Gate, Circuit, Procedure, Opaque))]
        self.useTN = False
        self.partition = None

    def include(self, filename):
        """ Parse second file and add gates and vars into local scope

        :param filename: file to include

        """
        other = ProgFile(filename)
        self._code += [Include(self, filename, other.code)]
        for objName, obj in other.get_objs():
            if objName in Gate.internalGates:
                continue
            if objName in langConstants:
                continue
            if objName in self._objs:
                self._error(includeWarning.format(name=objName,
                                                  type=self._objs[objName].type_,
                                                  other=other.filename,
                                                  me=self.filename))

            else:
                self._objs[objName] = obj
                self._objs[objName].included = True
