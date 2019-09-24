"""
Module to perform analysis for partitioning tensor network representation of state for memory optimisation.
"""
from .QASMTypes import (QuantumRegister)
from .CodeGraph import (BaseGraphBuilder, parse_code)

_rowFormat = lambda x: print("{0:<2.2s}".format(str(x)), end=" ")

class QubitLine(BaseGraphBuilder):
    """ Type to store graph of entanglement """
    def __init__(self, size):
        BaseGraphBuilder.__init__(self, size)
        self._default = "|"

    lineFormat = lambda self, str: "{:*^{width}}".format(str, width=3*self.nQubits)

    def process(self, **kwargs):
        """ Print the qubit list """
        for qubitInvolved in self._involved:
            if qubitInvolved:
                _rowFormat(self.currOp)
            else:
                _rowFormat(self._default)
        if self.isIf:
            print("?")
        else:
            print()
        self.set_qubits()

    def handle_classical(self, **kwargs):
        """ Print an appropriately scaled classical line """
        print(self.lineFormat(' Classical '))

    def handle_measure(self, **kwargs):
        print(self.lineFormat(' Measure '))

def print_circuit_diag(codeObject, maxDepth=-1):
    """ Recursively traverse the code to print a quick entanglement graph/circuit diagram """
    nQubits = QuantumRegister.numQubits
    builder = QubitLine(nQubits)

    # Print header

    for i in range(nQubits):
        _rowFormat(i)
    print()
    for reg in codeObject.quantumRegisters:
        for i in range(reg.size):
            _rowFormat(reg.name)
    print()
    for i in range(nQubits):
        _rowFormat(0)
    print()

    parse_code(codeObject, builder, maxDepth=maxDepth)
