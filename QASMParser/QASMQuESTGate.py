"""
Module to set up inbuilt QASM gates in QuEST format.
"""
import copy

from .QASMTypes import (Gate, Opaque, CBlock, MathsBlock, Constant, CallGate)
from .QASMTokens import (Binary)
from .FileHandle import QASMString
# Core gates

def setup_QASM_gates():
    """ Define core QASM gates """
    dummy = QASMString("Internal")

    unitary = Opaque(dummy, "U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitary._code = [CBlock(
        None,
        """
rotateZ(qreg,a_index,lambda);
rotateX(qreg,a_index,theta);
rotateZ(qreg,a_index,phi);
        """.splitlines())]

    unitary_inverse = Opaque(dummy, "inv_U", pargs=["theta", "phi", "lambda"], qargs=[{"var":"a"}], unitary=True)
    unitary_inverse._code = [CBlock(
        None,
        """
rotateZ(qreg,a_index,-lambda);
rotateX(qreg,a_index,-theta);
rotateZ(qreg,a_index,-phi);
        """.splitlines())]
    unitary._inverse = unitary_inverse
    unitary.invert = lambda parent, pargs, qargs, gargs, spargs: [CallGate(parent, "inv_U", pargs, qargs, gargs, spargs)]
    # def invert_unitary(parent, pargs, qargs, gargs, spargs):
    #     """ Inverse U gate (opposite rotation) """
    #     newArgs = []
    #     print(pargs)
    #     for parg in pargs:
    #         if isinstance(parg, MathsBlock):
    #             parg.topLevel = False
    #             arg = MathsBlock(parg.parent, Binary([["-", parg.maths]]))
    #         elif isinstance(parg, Constant):
    #             arg = MathsBlock(parg.parent, Binary([["-", parg]]))
    #         else:
    #             arg = parg
    #         newArgs.append(arg)
    #     qargs[0][1] = (0, 0)
    #     return [CallGate(parent, "U", newArgs, qargs, gargs, spargs)]

    # unitary.invert = invert_unitary

    controlledNot = Opaque(dummy, "CX", pargs=[], qargs=[{"var":"a"}, {"var":"b"}], unitary=True)
    controlledNot._code = [CBlock(
        None,
        """controlledNot(qreg, a_index, b_index);""".splitlines())]

    controlledNot.invert = controlledNot

    Gate.internalGates["U"] = unitary
    Gate.internalGates["CX"] = controlledNot
    Gate.internalGates["inv_U"] = unitary_inverse
