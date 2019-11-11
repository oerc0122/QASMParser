"""
Module to set up inbuilt QASM gates in QuEST format.
"""

from .types import (Gate, Opaque, CallGate)
from .filehandle import QASMString

def setup_QASM_gates():
    """ Define core QASM gates """
    dummy = QASMString("Internal")

    unitary = Opaque(dummy, "U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitaryInverse = Opaque(dummy, "inv_U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitary.set_inverse(unitaryInverse)
    unitary.invert = lambda parent, pargs, qargs, gargs, spargs: \
        [CallGate(parent, "inv_U", pargs, qargs, gargs, spargs)]

    controlledNot = Opaque(dummy, "CX", pargs=[], qargs=[{"var":"a"}, {"var":"b"}], unitary=True)
    controlledNot.invert = controlledNot

    Gate.internalGates["U"] = unitary
    Gate.internalGates["CX"] = controlledNot
    Gate.internalGates["inv_U"] = unitaryInverse
