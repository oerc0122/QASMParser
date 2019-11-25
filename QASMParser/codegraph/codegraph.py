"""
Contains routines to traverse the parsed code and build graphs
"""

import copy
import networkx
from .drawing import COLOURS
from .graphbuilder import GraphBuilder

class Vertex():
    """ Class defining a single tensor node vertex """
    def __init__(self, ID, qubitID, age, localAge, graph, operation=None):
        self._ID = ID
        self._qubitID = qubitID
        self._age = age
        self._localAge = localAge
        self._indices = []
        self._op = operation
        self._contracted = []
        self._parent = graph
        self._fixedEdges = None
        self.lastNode = True

    def __deepcopy__(self, memo):
        newCopy = copy.copy(self)
        newCopy._parent = None
        newCopy._op = None
        return newCopy

    def fix_edges(self):
        """ Lock in edges for later use """
        self._fixedEdges = list(self.edges)

    ID = property(lambda self: self._ID)
    qubitID = property(lambda self: self._qubitID)
    age = property(lambda self: self._age)
    localAge = property(lambda self: self._localAge)
    contracted = property(lambda self: self._contracted)
    edges = property(lambda self: self.graph.edges(self.ID))
    fixedEdges = property(lambda self: self._fixedEdges)
    nEdges = property(lambda self: len(self.edges))
    op = property(lambda self: self._op)
    opName = property(lambda self: self.op.name)
    graph = property(lambda self: self._parent)

class CodeGraph(GraphBuilder):
    """ Build directed graph using NetworkX """
    def __init__(self, code: list, nQubits: int, maxDepth: int=-1):
        GraphBuilder.__init__(self, code, nQubits, maxDepth)
        self._tensorGraph = networkx.Graph()
        self._entang = networkx.Graph()
        for i in range(nQubits):
            self._entang.add_node(i)
            self._tensorGraph.add_node(i, node=Vertex(ID=i, qubitID=i, age=1, localAge=1, graph=self.tensorGraph))
            end = Vertex(ID="end"+str(i), qubitID=i, age=None, localAge=None, graph=self.tensorGraph, operation=None)
            end.lastNode = False
            self.tensorGraph.add_node("end"+str(i), node=end)
        self._lastUpdated = [node.ID for node in self.verts]
        self._nGate = 1
        self._nGateQubit = [1]*nQubits
        self.graph = None
        self._GraphBuilder__parse_code()

    nGate = property(lambda self: self._nGate)
    nGateQubit = property(lambda self: self._nGateQubit)
    entang = property(lambda self: self._entang)
    verts = property(lambda self: (self.tensorGraph.nodes[vertex]["node"]
                                   for vertex in self.tensorGraph.nodes if "end" not in str(vertex)))
    allVerts = property(lambda self: (self.tensorGraph.nodes[vertex]["node"]
                                      for vertex in self.tensorGraph.nodes))
    nodes = property(lambda self: (self.tensorGraph.nodes[vertex]
                                   for vertex in self.tensorGraph.nodes if "end" not in str(vertex)))
    allNodes = property(lambda self: (self.tensorGraph.nodes[vertex]
                                      for vertex in self.tensorGraph.nodes))
    tensorGraph = property(lambda self: self._tensorGraph)
    nVerts = property(lambda self: len(list(self.verts)))
    edges = property(lambda self: (edge for edge in self.tensorGraph.edges
                                   if not any("end" in str(node) for node in edge)))
    endVerts = property(lambda self: (self.tensorGraph.nodes[node]["node"] for node in self.ends))
    ends = property(lambda self: ("end"+str(i) for i in range(self.nQubits)))

    @property
    def entanglements(self):
        """ Number of entanglements between qubits """
        return networkx.adjacency_matrix(self.entang).todense()

    def _process(self, **kwargs):
        """ Build graph from code """
        self._nGate += 1
        for qubit in self.qubitsInvolved:
            prev = self._lastUpdated[qubit]
            self._nGateQubit[qubit] += 1
            self.tensorGraph.nodes[prev]["node"].lastNode = False
            current = self.nVerts
            # Add new state as vertex
            node = Vertex(ID=self.nVerts, qubitID=qubit, age=self._nGate, localAge=self._nGateQubit[qubit],
                          graph=self.tensorGraph, operation=kwargs["lineObj"])
            self._tensorGraph.add_node(current, node=node)
            # Link last updated vertex to current
            self._tensorGraph.add_edge(prev, current, weight=1)
            self._lastUpdated[qubit] = current
            if qubit != min(self.qubitsInvolved): # Skip if initial qubit (nothing to link to)
                self._tensorGraph.add_edge(current, lastVertex, weight=1)
                nodes = (self.tensorGraph.nodes[lastVertex]["node"].qubitID,
                         self.tensorGraph.nodes[current]["node"].qubitID)
                if self._entang.has_edge(*nodes):
                    self._entang[nodes[0]][nodes[1]]["weight"] += 1
                else:
                    self._entang.add_edge(*nodes, weight=1)
            # Link to previous qubit in operation
            lastVertex = current

    def _finalise(self):
        """ Link final qubit with fictional outlet """
        for qubit, node in enumerate(self._lastUpdated):
            end = self.tensorGraph.nodes["end"+str(qubit)]["node"]
            end._age = self.nGate+1
            end._localAge = self.nGateQubit[qubit]+1
            self.tensorGraph.add_edge(node, "end"+str(qubit), key="end")

        for vertex in self.verts:
            vertex.fix_edges()

    def to_graphviz(self):
        """ Return the circuit as a graphviz object """
        self.graph = networkx.nx_agraph.to_agraph(self.tensorGraph)
        for nodeID in self.tensorGraph.nodes:
            node = self.graph.get_node(nodeID)
            del node.attr['node']

        return self.graph

    def setup_draw_circuit(self, graph=None, **kwargs):
        """ Draw this adjlist in a circuit layout """
        if graph is None:
            if self.graph is None:
                self.to_graphviz()
            graph = self.graph

        for nodeID in self.tensorGraph.nodes:
            vert = self.tensorGraph.nodes[nodeID]["node"]
            node = graph.get_node(nodeID)
            node.attr["shape"] = kwargs.get("shape", "rect")
            node.attr["style"] = kwargs.get("style", "striped")
            if "colourFunc" in kwargs:
                node.attr["fillcolor"] = kwargs["colourFunc"](vert)
            else:
                node.attr["fillcolor"] = kwargs.get("colour", COLOURS[0])
            if "labelFunc" in kwargs:
                node.attr["label"] = kwargs.get("labelFunc")(vert)
            else:
                node.attr["label"] = getattr(vert, kwargs.get("labelAttr", "ID"), vert.ID)

        for nodeID in self.ends:
            endNode = graph.get_node(nodeID)
            endNode.attr["style"] = kwargs.get("endstyle", "dotted")
            endNode.attr["shape"] = kwargs.get("endshape", kwargs.get("shape", "rect"))

    def circuit_layout(self, graph=None, scale=60, **kwargs):
        """ Return a graph laid out as a quantum circuit """
        if graph is None:
            if self.graph is None:
                self.to_graphviz()
            graph = self.graph

        graph.layout()
        for vert in self.allVerts:
            node = graph.get_node(vert.ID)
            node.attr["pos"] = "{:f},{:f}".format(vert.age*scale, vert.qubitID*scale)

        for edge in graph.edges_iter():
            fromNode, toNode = graph.get_node(edge[0]), graph.get_node(edge[1])
            edge.attr["pos"] = "e,{1} s,{0}".format(fromNode.attr["pos"], toNode.attr["pos"])
        return graph

    def draw(self, outFile, **kwargs):
        """ Quick render to file """
        self.to_graphviz()
        self.circuit_layout(**kwargs)
        self.setup_draw_circuit(**kwargs)
        self.graph.draw(outFile)
