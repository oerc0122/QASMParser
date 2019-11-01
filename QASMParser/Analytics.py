"""
Module for performing code analytics
"""

import numpy as np

def setup(obj):
    obj.analysis = Analyser(obj.nQubits)

def process(obj, **kwargs):
    obj.analysis.process(obj.nQubits, obj.qubitsInvolved)

class Analyser():
    """ Type to store graph of entanglement """
    def __init__(self, size):
        self._nGates = 0
        self._nEntanglements = []
        self._nEntanglementsPQubit = [None]*size
        for i in range(size):
            self._nEntanglementsPQubit[i] = []
        self._entanglingOps = [None]*size
        for i in range(size):
            self._entanglingOps[i] = []

        self._currStart, self._longStart, self._longEnd = 0, 0, 0
        self._currentStretch = np.zeros(size, dtype=int)
        self._longestStretch = np.zeros(size, dtype=int)

        self._nInterEntanglingOps = np.zeros((size, size), dtype=int)
        self._interEntanglingOps = [None]*size
        for i in range(size):
            self._interEntanglingOps[i] = [None]*size
            for j in range(size):
                self._interEntanglingOps[i][j] = []
        
        self._interLongStart, self._interLongEnd = 0, 0
        self._interCurrentStretch = np.zeros((size, size), dtype=int)
        self._interLongestStretch = np.zeros((size, size), dtype=int)

    nEntanglements = property(lambda self: self._nEntanglements)
    nEntanglementsPQubit = property(lambda self: self._nEntanglementsPQubit)
    entanglingOps = property(lambda self: self._entanglingOps)
    longestStretch = property(lambda self: self._longestStretch)
    stretchRange = property(lambda self: range(self._longStart, self._longEnd))
    interLongestStretch = property(lambda self: self._interLongestStretch)
    interEntanglingOps = property(lambda self: self._interEntanglingOps)
    nGates = property(lambda self: self._nGates)

    def process(self, nQubits, involved, **kwargs):
        """ Perform necessary processing of set qubits """
        self._nGates += 1
        self._nEntanglements.append(len(involved))

        for qubit in involved:
            self._nEntanglementsPQubit[qubit].append(len(involved))

            # Entangling?
            if len(involved) == 1:
                self._currentStretch[qubit] += 1
                break

            # Stretch broken
            if self._currentStretch[qubit] > self._longestStretch[qubit]:
                self._longestStretch[qubit] = self._currentStretch[qubit]
                self._longEnd = self.nGates
                self._longStart = self._currStart
                self._currStart = self.nGates
                self._currentStretch[qubit] = 0

            self._entanglingOps[qubit].append(1)

            for qubit2 in range(nQubits):
                if qubit == qubit2:
                    continue
                if qubit2 in involved:
                    self._nInterEntanglingOps[qubit][qubit2] += 1
                    self._interEntanglingOps[qubit][qubit2].append(1)
                    self._interLongestStretch[qubit][qubit2] = max(self._interCurrentStretch[qubit][qubit2],
                                                                   self._interLongestStretch[qubit][qubit2])
                    self._interCurrentStretch[qubit][qubit2] = 0
                else:
                    self._interCurrentStretch[qubit][qubit2] += 1

def analyse(analyser):
    """ Print results of analysis """
    print(analyser.longestStretch)
    print(analyser.stretchRange)
