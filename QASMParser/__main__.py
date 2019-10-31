#!/usr/bin/env python3
"""
Main program for transpiling QASM scripts into QuEST input format
"""

from QASMParser.QASMParser import ProgFile
from QASMParser.QASMQuESTGate import setup_QASM_gates
from QASMParser.Cli import get_command_args
from QASMParser.CircuitDiag import (print_circuit_diag)
from QASMParser.AdjMat import (calculate_adjmat, best_slice_adjmat)
from QASMParser.QASMErrors import (noSpecWarning)
from QASMParser.Partitioning import (partition)
from QASMParser.GraphPartition import (calculate_adjlist, Tree)
from QASMParser.Analytics import (analyse)




def main():
    """ Run main program """
    argList = get_command_args()
    setup_QASM_gates()

    for source in argList.sources:
        myProg = ProgFile(source)
        print(source)
        # Set up the core internal gates

        if argList.print:
            print_circuit_diag(myProg, maxDepth=argList.max_depth)

        if argList.analyse:
            analysis = analyse(myProg, maxDepth=argList.max_depth)

        if argList.dummy_partition:
            if argList.partition == 0:
                pass
            elif argList.partition == 1:
                mat = calculate_adjmat(myProg, maxDepth=argList.max_depth)
                bestSlice = [reg.end-1 for reg in myProg.quantumRegisters]

                print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))

            elif argList.partition == 2:
                mat = calculate_adjmat(myProg, maxDepth=argList.max_depth)
                bestSlice = best_slice_adjmat(mat)

                print(bestSlice, mat.nQubits, mat.slice_cost(bestSlice))

            elif argList.partition == 3:
                adj = calculate_adjlist(myProg, maxDepth=argList.max_depth)

                ### Drawing
                #import pygraphviz as pg
                #edgeList = [tuple([edge, i]) for i, vertex in enumerate(adj.adjList) for edge in vertex.edges]
                #graph = pg.AGraph()
                #for edge in edgeList:
                #    graph.add_edge(*edge)
                #graph.draw('graph.png', prog='neato')
                ### EndDraw

                tree = Tree(adj.adjList)
                tree.split_graph()
                print(tree.tree_form("vertIDs"))
                tree.contract()
                print(tree.tensor.qureg)
            else:
                raise IndexError("Unrecognised partition type")
            return

        if not any(argList.analyse, argList.dummy_partition, argList.print):
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
    
            partition(myProg, argList.partition)
            myProg.to_lang(outputFile, lang,
                           include_internals=argList.include_internals,
                           includes=argList.include,
                           module=argList.to_module,
                           verbose=argList.debug)

if __name__ == "__main__":
    main()
