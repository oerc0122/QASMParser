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
        """)]

    def invert_unitary(**kwargs):
        """ Inverse U gate (opposite rotation) """
        newArgs = []
        for parg in kwargs["pargs"]:
            if isinstance(parg, MathsBlock):
                parg.topLevel = False
                arg = MathsBlock(parg.parent, Binary([["-", parg.maths]]))
            elif isinstance(parg, Constant):
                arg = copy.copy(parg)
                if arg.name.startswith("-"):
                    arg.name = arg.name.lstrip("-")
                else:
                    arg.name = "-" + arg.name
            newArgs.append(arg)

        qargs = kwargs["qargs"]
        qargs[0][1] = (None, None)
        return [CallGate(None, "U", newArgs, qargs, **kwargs)]

    unitary.invert = invert_unitary

    controlledNot = Opaque(dummy, "CX", pargs=[], qargs=[{"var":"a"}, {"var":"b"}], unitary=True)
    controlledNot._code = [CBlock(
        None,
        """
        controlledNot(qreg, a_index, b_index);
        """)]

    def invert_controlled_not(**kwargs): # 
        """ inverse CX gate (CX gate) """
    #    pargs = kwargs["pargs"]
        qargs = kwargs["qargs"]
        for qarg in qargs:
            qarg[1] = (None, None)
        return [CallGate(None, "CX", **kwargs)]

    controlledNot.invert = invert_controlled_not

    Gate.internalGates["U"] = unitary
    Gate.internalGates["CX"] = controlledNot
