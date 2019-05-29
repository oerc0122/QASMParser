from .QASMTypes import Gate, Opaque, CBlock
from .FileHandle import QASMString
# Core gates
dummy = QASMString("Internal")

_U = Opaque(dummy, "U", ["theta","phi","lambda"], [{"var":"a"}])
_U._code = [CBlock(
    None,
    """
    rotateX(qreg,a_index,lambda);
    rotateX(qreg,a_index,theta);
    rotateX(qreg,a_index,phi);
    """)]

_CX = Opaque(dummy, "CX", [], [{"var":"a"}, {"var":"b"}])
_CX._code = [CBlock(
    None,
    """
    controlledNot(qreg, a_index, b_index)
    """)]
Gate.internalGates["U"] = _U
Gate.internalGates["CX"] = _CX
