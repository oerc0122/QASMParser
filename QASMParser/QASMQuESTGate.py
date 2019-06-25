from .QASMTypes import *# Gate, Opaque, CBlock
from .FileHandle import QASMString
import copy
# Core gates
dummy = QASMString("Internal")

_U = Opaque(dummy, "U", pargs = ["theta","phi","lambda"], qargs = [{"var":"a"}], unitary = True)
_U._code = [CBlock(
    None,
    """
    rotateZ(qreg,a_index,lambda);
    rotateX(qreg,a_index,theta);
    rotateZ(qreg,a_index,phi);
    """)]

def _invert_U(**kwargs):
    new_args = []
    for parg in kwargs["pargs"]:
        if isinstance(parg, MathsBlock):
            parg.topLevel = False
            arg = MathsBlock(parg.parent, Binary( [[ "-", parg.maths ]] ))
        elif isinstance(parg, Constant):
            arg = copy.copy(parg)
            if arg.name.startswith("-"): arg.name = arg.name.lstrip("-")
            else:                        arg.name = "-" + arg.name
        new_args.append(arg)

    qargs = kwargs["qargs"]
    qargs[0][1] = (None, None)
    return [CallGate(None, "U", new_args, qargs)]

_U.invert = _invert_U

_CX = Opaque(dummy, "CX", pargs = [], qargs = [{"var":"a"}, {"var":"b"}], unitary = True)
_CX._code = [CBlock(
    None,
    """
    controlledNot(qreg, a_index, b_index);
    """)]

def _invert_CX(**kwargs):
    pargs = kwargs["pargs"]
    qargs = kwargs["qargs"]
    for qarg in qargs:
        qarg[1] = (None, None)
    return [CallGate(None, "CX", **kwargs)]

_CX.invert = _invert_CX

Gate.internalGates["U"] = _U
Gate.internalGates["CX"] = _CX
