"""
Module for performing code analytics
"""

import numpy as np

from .QASMTypes import (QuantumRegister)
from .CodeGraph import (BaseGraphBuilder, parse_code)

import matplotlib.pyplot as plt

class Analyser(BaseGraphBuilder):
    """ Type to store graph of entanglement """
    def __init__(self, size):
        BaseGraphBuilder.__init__(self, size)
        self._nEntanglements = []
        self._nEntanglementsPQubit = [[]]*size
        self._entanglingOps = np.zeros(size, dtype=int)
        self._currentStretch = np.zeros(size, dtype=int)
        self._longestStretch = np.zeros(size, dtype=int)
        self._interCurrentStretch = np.zeros((size, size), dtype=int)
        self._interLongestStretch = np.zeros((size, size), dtype=int)
        self._interEntanglingOps = np.zeros((size, size), dtype=int)

    nEntanglements = property(lambda self: self._nEntanglements)
    nEntanglementsPQubit = property(lambda self: self._nEntanglementsPQubit)
    entanglingOps = property(lambda self: self._entanglingOps)
    longestStretch = property(lambda self: self._longestStretch)
    interLongestStretch = property(lambda self: self._interLongestStretch)
    interEntanglingOps = property(lambda self: self._interEntanglingOps)

    def process(self, **kwargs):
        involved = np.flatnonzero(self._involved == 1)
        self._nEntanglements.append(len(involved))

        for qubit in involved:
            self._nEntanglementsPQubit[qubit].append(len(involved))

            # Entangling?
            if len(involved) == 1:
                self._currentStretch[qubit] += 1
                break

            self._entanglingOps[qubit] += 1
            self._longestStretch[qubit] = max(self._currentStretch[qubit], self._longestStretch[qubit])
            self._currentStretch[qubit] = 0
            for qubit2 in range(self.nQubits):
                if qubit == qubit2:
                    continue
                if qubit2 in involved:
                    self._interEntanglingOps[qubit, qubit2] += 1
                    self._interLongestStretch[qubit, qubit2] = max(self._interCurrentStretch[qubit, qubit2],
                                                                   self._interLongestStretch[qubit, qubit2])
                    self._interCurrentStretch[qubit, qubit2] = 0
                else:
                    self._interCurrentStretch[qubit, qubit2] += 1

        self.set_qubits()

    def clean(self):
        del self._currentStretch
        del self._interCurrentStretch
        
    def handle_classical(self, **kwargs):
        """ Perform actions based on classical blocks """

    def handle_measure(self, **kwargs):
        """ Handle measurements """

def analyse(code, maxDepth=999):
    ""
    analyser = Analyser(QuantumRegister.numQubits)
    parse_code(code, analyser, maxDepth=maxDepth)
    print(analyser.entanglingOps)
    print(analyser.longestStretch)
    print(analyser.interEntanglingOps)
    print(analyser.interLongestStretch)
    plt.show()
    quit()
    return analyser
