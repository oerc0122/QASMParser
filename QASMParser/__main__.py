#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""

from QASMParser.QASMParser import ProgFile
from QASMParser.QASMQuESTGate import setup_QASM_gates
from QASMParser.Cli import get_command_args
from QASMParser.CircuitDiag import (print_circuit_diag)
from QASMParser.AdjMat import (calculate_adjmat, print_adjmat, slice_adjmat)
from QASMParser.QASMErrors import (noSpecWarning)


def main():
    """ Run main program """
    argList = get_command_args()

    # Set up the core internal gates
    setup_QASM_gates()
    if argList.print:
        for source in argList.sources:
            myProg = ProgFile(source)
            print(source)
            print(argList.max_depth)
            print_circuit_diag(myProg, topLevel=True, maxDepth=argList.max_depth)
        return

    if argList.analyse:
        for source in argList.sources:
            myProg = ProgFile(source)
            print(source)
            mat = calculate_adjmat(myProg, maxDepth=argList.max_depth)
            regNames = [f"{reg.name:.5}[{i}]"
                        for reg in myProg.code
                        if type(reg).__name__ == "QuantumRegister"
                        for i in range(reg.size)]
            print_adjmat(regNames, mat)
            slice_adjmat(mat)
        return

    lang = None
    if argList.language:
        lang = argList.language
    elif argList.output.endswith('.py'):
        lang = "Python"
    elif argList.output.endswith('.c'):
        lang = "C"
    elif not argList.output:
        raise IOError(noSpecWarning)

    if not lang:
        raise IOError(noSpecWarning)

    if argList.output:
        outputFile = argList.output
    else:
        outputFile = None

    for source in argList.sources:
        myProg = ProgFile(source)
        myProg.to_lang(outputFile, argList.to_module, argList.include, lang, argList.debug)

if __name__ == "__main__":
    main()
