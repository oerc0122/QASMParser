"""
Module for building adjacency list and firing that through METIS for partitioning
"""

import metis
import numpy as np
from .QASMTypes import (QuantumRegister)
from .CodeGraph import (BaseGraphBuilder, range_inclusive, parse_code)

class AdjListBuilder(BaseGraphBuilder):
    """ Class for building tensor network adjacency list """
    def __init__(self, size):
        BaseGraphBuilder.__init__(self, size)
        # Set initialise (entry) statements
        self.lastUpdated = [i for i in range(size)]
        self._adjList = [[] for i in range(size)]
        self.remap = {}
        self.unmap = {}

    nVerts = property(lambda self: len(self._adjList))
    adjList = property(lambda self: self._adjList)

    def finalise(self):
        """ Lock in vertices """
        self._adjList = np.asarray(list(map(tuple, self._adjList)))

    def process(self, **kwargs):
        start, end = min(np.flatnonzero(self._involved == 1)), max(np.flatnonzero(self._involved == 1))
        for qubit in range_inclusive(start, end):
            prev = self.lastUpdated[qubit]
            # Add new state as vertex
            self._adjList.append([])
            current = self.nVerts-1
            # Link last updated vertex to current
            self._link(prev, current)
            self.lastUpdated[qubit] = current
            # Set mappings
            self.remap[kwargs['lineNo']] = current
            self.unmap[current] = kwargs['lineNo']
            if qubit != start: # Skip if initial qubit (nothing to link to)
                self._link(lastVertex, current)
            # Link to previous qubit in operation
            lastVertex = current

        self.set_qubits()

    def _link(self, a, b):
        self._adjList[a].append(b)
        self._adjList[b].append(a)

    def handle_measure(self, **kwargs):
        self.set_qubits(1)
        self.process(**kwargs)

class Tree:
    """ Class defining tree head """
    def __init__(self, graph):
        self.parent = None
        self.tier = 0
        self.child = []
        self._adjList = graph
        self.remap = dict((i, i) for i, _ in enumerate(graph))
        self.unmap = self.remap
        self.vertices = self.remap.values()

    def __add__(self, other):
        if self.nChild < 2:
            self.child.append(other)
            return self
        raise IndexError('Binary tree cannot have more than 2 children')

    left = property(lambda self: self.child[0])
    right = property(lambda self: self.child[1])
    nChild = property(lambda self: len(self.child))
    nVerts = property(lambda self: len(self._adjList))

    adjList = property(lambda self: self._adjList)

    def to_local(self, edge):
        """ find local index of vertex """
        return self.remap[edge]

    def to_global(self, edge):
        """ Find global index of vertex """
        return self.unmap[edge]

    @property
    def adjListMap(self):
        """ Return the adjacency list mapped to local context, removing adjacencies outside local space """
        out = []
        for vertex in self._adjList:
            out.append(tuple(self.remap[edge] for edge in vertex if edge in self.remap))
        out = np.asarray(out)
        return out

    def __str__(self):
        return self.tree_form("adjList")

    def tree_form(self, prop):
        """ Return printout tree displaying property """
        lines, _, _, _ = self.display_aux(prop)
        strOut = "\n".join(lines)
        return strOut

    def display_aux(self, prop):
        """Returns list of strings, width, height, and horizontal coordinate of the root."""
        asStr = str(list(getattr(self, prop)))

        # No child.
        if self.nChild == 0:
            width = len(asStr)
            height = 1
            middle = width // 2
            return [asStr], width, height, middle

        # Only left child.
        if self.nChild == 1:
            lines, width, height, middle = self.left.display_aux(prop)
            strLen = len(asStr)
            offset = width - middle - 1
            firstLine = (middle + 1) * ' ' + (offset) * '_' + asStr
            secondLine = middle * ' ' + '/' + (offset + strLen) * ' '
            shiftedLines = [line + strLen * ' ' for line in lines]
            return [firstLine, secondLine] + shiftedLines, width + strLen, height + 2, width + strLen // 2

        # Two children.
        left, widthL, heightL, middleL = self.left.display_aux(prop)
        right, widthR, heightR, middleR = self.right.display_aux(prop)
        sepL, sepR = widthL - middleL, widthR - middleR
        strLen = len(asStr)
        firstLine = (middleL + 1) * ' ' + (sepL - 1) * '_' + asStr + middleR * '_' + (sepR) * ' '
        secondLine = middleL * ' ' + '/' + (sepL - 1 + strLen + middleR) * ' ' + '\\' + (sepR - 1) * ' '
        if heightL < heightR:
            left += [widthL * ' '] * (heightR - heightL)
        else:
            right += [widthR * ' '] * (heightL - heightR)
        lines = [firstLine, secondLine] + [a + strLen * ' ' + b for a, b in zip(left, right)]
        return lines, widthL + widthR + strLen, max(heightL, heightR) + 2, widthL + strLen // 2

    def split_graph(self):
        """ Recursively split the graph and build the resulting binary tree """
        if self.nVerts < 2:
            return
        graph = adjlist_to_metis(self.adjListMap)
        cut = np.asarray(metis.part_graph(graph, nparts=2)[1])
        if 0 < sum(cut) < len(cut): # Handle METIS not splitting small graphs by taking first value
            cutL, cutR = np.nonzero(cut == 0)[0], np.nonzero(cut == 1)[0]
        else:
            cutL = min(map(len, self.adjList))
            cutR = [*range(0, cutL), *range(cutL+1, len(cut))]
            cutL = [cutL]
        childL, childR = Node(self, cutL), Node(self, cutR)
        childL.split_graph()
        childR.split_graph()


class Node(Tree):
    """ Tree node class """
    def __init__(self, parent, cut):
        Tree.__init__(self, [])
        self.parent = parent
        parent += self
        self.tier = self.parent.tier + 1
        self.child = []
        self._adjList = parent.adjList[cut]
        self.remap = dict((old, new) for new, old in enumerate(cut))
        self.unmap = dict((new, parent.unmap[old]) for new, old in enumerate(cut))
        *self.vertices, = map(parent.to_global, cut)


def add_weights(weights):
    """ Add weights necessary for METIS partitioning """
    return [[(weight, 1) for weight in edge] for edge in weights]
    

def adjlist_to_metis(adjList):
    """ Actually add the 1 weights in """
    return metis.adjlist_to_metis(add_weights(adjList))


def calculate_adjlist(code, maxDepth=999):
    """ Calculate adjacency list for METIS partitioner """
    adjList = AdjListBuilder(QuantumRegister.numQubits)
    parse_code(code, adjList, maxDepth=maxDepth)
    adjList.finalise()
    return adjList
