"""
Module for building adjacency list and firing that through METIS for partitioning
"""
import sys
import ctypes
import metis
import numpy as np
sys.path += ['/home/jacob/QuEST-TN/utilities/']

# Find QuEST and TN libraries
# from QuESTPy.QuESTBase import init_QuESTLib
# from TNPy.TNBase import init_TNLib
# QuESTPath = "/home/ania/Documents/no_sync/git_QuEST-TN/build/TN/QuEST"
# TNPath = "/home/ania/Documents/no_sync/git_QuEST-TN/build/TN/"
# init_QuESTLib(QuESTPath)
# init_TNLib(TNPath)

# import QuESTPy
# import TNPy
# import TNPy.TNFunc as TNFunc
# import TNPy.TNAdditionalGates as TNAdd
# import QuESTPy.QuESTFunc as QuESTFunc

from .QASMTypes import (QuantumRegister)
from .CodeGraph import (BaseGraphBuilder, parse_code)


class Vertex():
    """ Class defining a single tensor node vertex """
    def __init__(self, ID, qubitID, operation=None):
        self._ID = ID
        self._qubitID = qubitID
        self._edges = []
        self._indices = []
        self._op = operation
        self._contracted = []
        self.lastQubit = True

    ID = property(lambda self: self._ID)
    qubitID = property(lambda self: self._qubitID)
    contracted = property(lambda self: self._contracted)
    edgeIn = property(lambda self: self._edges[1])
    edgeOut = property(lambda self: self._edges[0])
    edges = property(lambda self: tuple(edge for edge in self._edges))
    nEdges = property(lambda self: len(self._edges))
    indices = property(lambda self: self._indices)
    op = property(lambda self: self._op)

    def link(self, other, prepend=False):
        """ Link two vertices together """
        if prepend:
            self._edges.insert(0, other.ID)
            other._edges.insert(0, self.ID)
            self._indices.insert(0, (other.ID, other.nEdges-1))
            other._indices.insert(0, (self.ID, self.nEdges-1))
        else:
            self._edges.append(other.ID)
            other._edges.append(self.ID)
            self._indices.append((other.ID, other.nEdges-1))
            other._indices.append((self.ID, self.nEdges-1))

    def update(self, remap):
        """ Update indices to new values post contraction """
        for i, index in enumerate(self.indices):
            self._indices[i] = remap.get(index, index)

        for i, index in enumerate(self.edges):
            self._edges[i] = remap.get(index, index)

    def contract(self, right):
        """ Combine two vertices """

        left = self
        print("Contracting", left.ID, right.ID)
        contractionEdges = [[], []]
        freeIndices = [[], []]

        for localQubit, (targetVertex, targetQubit) in enumerate(left.indices):
            if targetVertex == right.ID:
                contractionEdges[0].append(localQubit)
                contractionEdges[1].append(targetQubit)

        freeIndices[0] = [qubit for qubit in range(left.nEdges) if qubit not in contractionEdges[0]]
        freeIndices[1] = [qubit for qubit in range(right.nEdges) if qubit not in contractionEdges[1]]

        remap = {right.ID: left.ID}
        notDropped = 0
        for ind, _ in enumerate(left.indices):
            edge = (left.ID, ind)
            if ind in contractionEdges[0]:
                remap[edge] = None
            else:
                if notDropped != ind:
                    remap[edge] = left.ID, notDropped
                notDropped += 1

        for ind, _ in enumerate(right.indices):
            edge = (right.ID, ind)
            if ind in contractionEdges[1]:
                remap[edge] = None
            else:
                if notDropped != ind:
                    remap[edge] = left.ID, notDropped
                notDropped += 1

        left._edges = ([edge for edge in left.edges if edge != right.ID] +
                       [edge for edge in right.edges if edge != left.ID])
        left._indices = ([index for i, index in enumerate(left.indices) if i not in contractionEdges[0]] +
                         [index for i, index in enumerate(right.indices) if i not in contractionEdges[1]])
        left._contracted += [right.ID] + right.contracted

        return contractionEdges, freeIndices, remap

class AdjListBuilder(BaseGraphBuilder):
    """ Class for building tensor network adjacency list """
    def __init__(self, size):
        BaseGraphBuilder.__init__(self, size)
        # Set initialise (entry) statements
        self._adjList = [Vertex(ID=i, qubitID=i) for i in range(size)]
        self._lastUpdated = self.adjList[:]

    verts = property(lambda self: [vertex.ID for vertex in self.adjList])
    nVerts = property(lambda self: len(self._adjList))
    adjList = property(lambda self: np.asarray(self._adjList))
    edges = property(lambda self: [vertex.edges for vertex in self.adjList])

    def process(self, **kwargs):
        start = min(np.flatnonzero(self._involved == 1))
        # end = max(np.flatnonzero(self._involved == 1))
        # for qubit in range_inclusive(start, end):
        for qubit in np.flatnonzero(self._involved == 1):
            prev = self._lastUpdated[qubit]
            # Add new state as vertex
            prev.lastQubit = False
            current = Vertex(ID=self.nVerts, qubitID=qubit, operation=kwargs['lineObj'])
            self._adjList.append(current)
            # Link last updated vertex to current
            current.link(prev)
            self._lastUpdated[qubit] = current
            if qubit != start: # Skip if initial qubit (nothing to link to)
                current.link(lastVertex)
            # Link to previous qubit in operation
            lastVertex = current

        self.set_qubits()

    def handle_measure(self, **kwargs):
        self.set_qubits(1)
        self.process(**kwargs)

class Tree:
    """ Class defining tree head """

    def __init__(self, graph=None):
        self._tier = 0
        self.child = []
        self._adjList = graph
        self.remap = {i:i for i, _ in enumerate(graph)}
        self.unmap = self.remap
        self.tensor = None
        self.tree = self

    def __add__(self, other):
        if self.nChild < 2:
            self.child.append(other)
            return self
        raise IndexError('Binary tree cannot have more than 2 children')

    tier = property(lambda self: self._tier)
    isLeaf = property(lambda self: not self.child)
    left = property(lambda self: self.child[0])
    right = property(lambda self: self.child[1])
    nChild = property(lambda self: len(self.child))
    nVerts = property(lambda self: len(self._adjList))
    vertIDs = property(lambda self: [vertex.ID for vertex in self.adjList])
    vertices = property(lambda self: (vertex for vertex in self.adjList))
    vertex = property(lambda self: self.adjList[0])
    nEdge = property(lambda self: len(self._adjList))
    adjList = property(lambda self: self._adjList)
    neighbours = property(lambda self: set(edge for vertex in self.vertices for edge in vertex.edges))

    def to_local(self, edge):
        """ find local index of vertex """
        return self.remap[edge]

    def to_global(self, edge):
        """ Find global index of vertex """
        return self.unmap[edge]

    def leaves(self):
        """ Return leaves """
        if not self.child:
            yield self
        else:
            for child in self.child:
                yield from child.leaves()

    @property
    def adjListMap(self):
        """ Return the adjacency list mapped to local context, removing adjacencies outside local space """
        out = [tuple(self.remap[edge] for edge in vertex.edges if edge in self.remap) for vertex in self._adjList]
        return np.asarray(out)

    def __str__(self):
        return self.tree_form("vertIDs")


    def resolve(self):
        """
        Initialise tensor/qureg
        Call our operation on qubits
        Update self resolved

        Return TensorObject
        """
        return
        vertex = self.vertex
        nVirtQubit = vertex.nEdges if vertex.lastQubit else vertex.nEdges - 1
        print(f"Hi,I'm {vertex.ID}, I have {vertex.nEdges} edges and 1 physical qubit")
        self.tensor = TNFunc.createTensor(1, nVirtQubit, env)
        # Entangle first virtual with physical qubit

        # If we're initialise -- createTensor => |0>
        if vertex.op is None:
            return

        TNAdd.TN_controlledGateTargetHalf(QuESTFunc.controlledNot, self.tensor, 1, 0)

        if vertex.op.name == "CX":
            gate = QuESTFunc.controlledNot
            args = [2, 0]
        elif vertex.op.name == "U":
            gate = QuESTFunc.hadamard
            args = [0]

        for vertex in self.vertices:
            if gate.control:
                if vertex.qubitID == gate.control:
                    TNAdd.TN_controlledGateControlHalf(gate, self.tensor, *args)
                else:
                    TNAdd.TN_controlledGateTargetHalf(gate, self.tensor, *args)
            else:
                TNAdd.TN_singleQubitGate(gate, self.tensor, *args)


    def contract(self):
        """ Contract entire tree  """
        # if isinstance(self, Tree):
            # global env
            # env = QuESTFunc.createQuESTEnv()


        if self.isLeaf:
            self.resolve()
            return

        for child in self.child:
            child.contract()

        contractionEdges, freeIndices, remap = self.left.vertex.contract(self.right.vertex)
        *contPass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), contractionEdges)
        *freePass, = map(lambda pyarr: (ctypes.c_int * len(pyarr))(*pyarr), freeIndices)

        # self.tensor = TNFunc.contractIndices(self.left.tensor, self.right.tensor,
        #                                      contPass[0], contPass[1], ctypes.c_int(len(contractionEdges[0])),
        #                                      freePass[0], ctypes.c_int(len(freeIndices[0])),
        #                                      freePass[1], ctypes.c_int(len(freeIndices[1])), env)
        print("contractionEdges", contractionEdges, "\n free", freeIndices, "\nremap", remap)

        # My vertex becomes child's merged vertex
        self._adjList = self.left.adjList
        verts = list(self.tree.vertices)
        neighbours = [verts[neighbour] for neighbour in self.neighbours]
        print("Neigh", self.neighbours)
        print("Hi, I'm ", self.vertex.ID, self.vertex.indices, "I ate ", self.vertex.contracted)
        for neighbour in neighbours:
            print("Howdy", neighbour.ID, neighbour.indices)
            neighbour.update(remap)
            print("Doody", neighbour.ID, neighbour.indices)

        if self.tier == 0:
            return
        # Remove global reference to child
        self.tree._adjList[self.right.vertex.ID] = None
        self.child = []

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
        if 0 < sum(cut) < len(cut):
            cutL, cutR = np.nonzero(cut == 0)[0], np.nonzero(cut == 1)[0]
        else: # Handle METIS not splitting small graphs by taking least-connected value
            cutL = np.argmin(map(len, self.adjList))
            cutR = [*range(0, cutL), *range(cutL+1, len(cut))]
            cutL = [cutL]
            print("MY", *map(lambda x: x.ID, self.adjList[cutL]), *map(lambda x: x.ID, self.adjList[cutR]))
        childL, childR = Node(self, cutL), Node(self, cutR)
        childL.split_graph()
        childR.split_graph()


class Node(Tree):
    """ Tree node class """
    def __init__(self, parent, cut):
        Tree.__init__(self, graph=[])
        self.parent = parent
        parent += self
        self.tree = parent.tree
        self._tier = self.parent.tier + 1
        self.child = []
        self._adjList = parent.adjList[cut]
        self.remap = {old:new for new, old in enumerate(cut)}
        self.unmap = {new:parent.unmap[old] for new, old in enumerate(cut)}


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
    return adjList

env = None
