"""
Module to set up inbuilt QASM gates in QuEST format.
"""

from .types import (Gate, Opaque, CallGate)
from .filehandle import QASMString

def setup_QASM_gates():
    """ Define core QASM gates """
    dummy = QASMString("Internal")

    unitary = Opaque(dummy, "U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitaryInverse = Opaque(dummy, "_inv_U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitary.set_inverse(unitaryInverse)
    unitary.invert = lambda parent, pargs, qargs, gargs, spargs: \
        [CallGate(parent, "_inv_U", pargs, qargs, gargs, spargs)]
    unitaryControl = Opaque(dummy, "_ctrl_U",
                            pargs=["theta", "phi", "lambda"],
                            qargs=[{"var":"_ctrls", "ref":{"index":"_nCtrls"}, "index":"_nCtrls"}, {"var":"a"}],
                            spargs=["_nCtrls"], unitary=True)

    controlledNot = Opaque(dummy, "CX", pargs=[], qargs=[{"var":"a"}, {"var":"b"}], unitary=True)
    controlledNot.invert = controlledNot

    Gate.internalGates["U"] = unitary
    Gate.internalGates["CX"] = controlledNot
    Gate.internalGates["_inv_U"] = unitaryInverse
    Gate.internalGates["_ctrl_U"] = unitaryControl
