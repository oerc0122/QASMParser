"""
Module to perform analysis for partitioning tensor network representation of state for memory optimisation.
"""
_rowBuild = lambda x: "{0:<2.2s} ".format(str(x))

def process(obj, **_):
    """ Print the qubit list """
    line = ""
    for qubitInvolved in obj.involvedList:
        if qubitInvolved:
            line += _rowBuild(obj.currOp)
        else:
            line += _rowBuild("|")
    if obj.isIf:
        line += "?"
    return line

def handle_classical(obj, **_):
    """ Print an appropriately scaled classical line """
    return "{:*^{width}}".format(' Classical ', width=3*obj.nQubits)

def handle_measure(obj, **_):
    """ Print an appropriately scaled measure line """
    return "{:*^{width}}".format(' Measure ', width=3*obj.nQubits)

def header(nQubits, codeObject):
    """ Return the header for the ASCII graph output """
    line = ""
    for i in range(nQubits):
        line += _rowBuild(i)
    line += "\n"

    for reg in codeObject.quantumRegisters:
        for i in range(reg.size):
            line += _rowBuild(reg.name)
    line += "\n"
    for i in range(nQubits):
        line += _rowBuild(0)
    line += "\n"
    return line
