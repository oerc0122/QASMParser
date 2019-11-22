"""
Contains routines to traverse the parsed code and build graphs
"""

import copy
import numpy as np
import networkx
from ..parser.types import (resolve_arg, CallGate, Opaque, SetAlias, Alias, Loop, CBlock, Measure)

COLOURS = ["blue", "brown", "burlywood", "cadetblue", "chartreuse", "chocolate", "coral", "darkkhaki",
           "cornflowerblue", "cornsilk", "crimson", "cyan", "blueviolet", "darkgoldenrod", "darkgreen",
           "darkolivegreen", "darkorange", "darkorchid", "darksalmon", "darkseagreen", "darkslateblue",
           "darkslategray", "darkslategrey", "darkturquoise", "darkviolet", "deeppink", "deepskyblue",
           "dimgray", "dimgrey", "dodgerblue", "firebrick", "floralwhite", "forestgreen", "gainsboro",
           "ghostwhite", "gold", "goldenrod", "green", "greenyellow", "grey", "honeydew", "hotpink",
           "indianred", "indigo", "invis", "ivory", "khaki", "lavender", "lavenderblush", "lawngreen",
           "lemonchiffon", "lightblue", "lightcoral", "lightcyan", "lightgoldenrod", "lightgoldenrodyellow",
           "lightgray", "lightgrey", "lightpink", "lightsalmon", "lightseagreen", "lightskyblue",
           "lightslateblue", "lightslategray", "lightslategrey", "lightsteelblue", "lightyellow",
           "limegreen", "linen", "magenta", "maroon", "mediumaquamarine", "mediumblue", "mediumorchid",
           "mediumpurple", "mediumseagreen", "mediumslateblue", "mediumspringgreen", "mediumturquoise",
           "mediumvioletred", "midnightblue", "mintcream", "mistyrose", "moccasin", "navajowhite", "navy",
           "navyblue", "none", "oldlace", "olivedrab", "orange", "orangered", "orchid", "palegoldenrod",
           "palegreen", "paleturquoise", "palevioletred", "peachpuff", "peru", "pink", "plum",
           "powderblue", "purple", "red", "rosybrown", "royalblue", "saddlebrown", "salmon", "sandybrown",
           "seagreen", "seashell", "sienna", "skyblue", "slateblue", "slategray", "slategrey", "snow",
           "springgreen", "steelblue", "tan", "thistle", "tomato", "transparent", "turquoise", "violet",
           "violetred", "wheat", "white", "whitesmoke", "yellow", "yellowgreen"]

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

class CodeGraph():
    """ Build directed graph using NetworkX """
    def __init__(self, size):
        self._size = size
        self._codeGraph = networkx.Graph()
        self._entang = networkx.MultiGraph()
        for i in range(size):
            self._entang.add_node(i)
            self._codeGraph.add_node(i, node=Vertex(ID=i, qubitID=i, age=1, localAge=1, graph=self.codeGraph))
            end = Vertex(ID="end"+str(i), qubitID=i, age=None, localAge=None, graph=self.codeGraph, operation=None)
            end.lastNode = False
            self.codeGraph.add_node("end"+str(i), node=end)
        self._lastUpdated = [node.ID for node in self.verts]
        self._nGate = 1
        self._nGateQubit = [1]*size
        self.graph = None

    size = property(lambda self: self._size)
    nGate = property(lambda self: self._nGate)
    nGateQubit = property(lambda self: self._nGateQubit)
    entang = property(lambda self: self._entang)
    verts = property(lambda self: (self.codeGraph.nodes[vertex]["node"]
                                   for vertex in self.codeGraph.nodes if "end" not in str(vertex)))
    allVerts = property(lambda self: (self.codeGraph.nodes[vertex]["node"]
                                      for vertex in self.codeGraph.nodes))
    codeGraph = property(lambda self: self._codeGraph)
    nVerts = property(lambda self: len(list(self.verts)))
    edges = property(lambda self: (edge for edge in self.codeGraph.edges if not any("end" in str(node) for node in edge)))
    endVerts = property(lambda self: (self.codeGraph.nodes[node]["node"] for node in self.ends))
    ends = property(lambda self: ("end"+str(i) for i in range(self.size)))

    @property
    def entanglements(self):
        """ Number of entanglements between qubits """
        return networkx.adjacency_matrix(self.entang)

    def process(self, obj, **kwargs):
        """ Build graph from code """
        self._nGate += 1
        for qubit in obj.qubitsInvolved:
            prev = self._lastUpdated[qubit]
            self._nGateQubit[qubit] += 1
            self.codeGraph.nodes[prev]["node"].lastNode = False
            current = self.nVerts
            # Add new state as vertex
            node = Vertex(ID=self.nVerts, qubitID=qubit, age=self._nGate, localAge=self._nGateQubit[qubit],
                          graph=self.codeGraph, operation=kwargs["lineObj"])
            self._codeGraph.add_node(current, node=node)
            # Link last updated vertex to current
            self._codeGraph.add_edge(prev, current, weight=1)
            self._lastUpdated[qubit] = current
            if qubit != min(obj.qubitsInvolved): # Skip if initial qubit (nothing to link to)
                self._codeGraph.add_edge(current, lastVertex, weight=1)
                self._entang.add_edge(self.codeGraph.nodes[lastVertex]["node"].qubitID,
                                      self.codeGraph.nodes[current]["node"].qubitID, weight=1)
            # Link to previous qubit in operation
            lastVertex = current

    def finalise(self):
        """ Link final qubit with fictional outlet """
        for qubit, node in enumerate(self._lastUpdated):
            end = self.codeGraph.nodes["end"+str(qubit)]["node"]
            end._age = self.nGate+1
            end._localAge = self.nGateQubit[qubit]+1
            self.codeGraph.add_edge(node, "end"+str(qubit), key="end")

        for vertex in self.verts:
            vertex.fix_edges()

    def to_graphviz(self):
        """ Return the codeGraph as a graphviz object """
        self.graph = networkx.nx_agraph.to_agraph(self.codeGraph)
        for nodeID in self.codeGraph.nodes:
            node = self.graph.get_node(nodeID)
            del node.attr['node']

        return self.graph

    def setup_draw_circuit(self, graph=None, **kwargs):
        """ Draw this adjlist in a circuit layout """
        if graph is None:
            if self.graph is None:
                self.to_graphviz()
            graph = self.graph

        for nodeID in self.codeGraph.nodes:
            vert = self.codeGraph.nodes[nodeID]["node"]
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


class GraphBuilder():
    """ Quantum circuit preprocessing analysis """
    def __init__(self, size, code, partition=0):
        self._nQubits = size
        self._involved = np.zeros(self.nQubits, dtype=np.int8)
        self.isIf = False
        self.currOp = None
        self._code = code

        # Options

        self.adjmatPartition = partition in [1, 2]
        self.graphPartition = partition == 3
        self.codeGraph = CodeGraph(self.nQubits)

    involvedList = property(lambda self: self._involved)
    involved = property(lambda self: self._involved.nonzero())
    qubitsInvolved = property(lambda self: np.flatnonzero(self._involved == 1))
    nQubits = property(lambda self: self._nQubits)
    codeLines = property(lambda self: len(self.code._code))
    code = property(lambda self: self._code)

    def _set_qubits(self, value=0, ranges=None):
        """ Set labels to qubits """
        if ranges is None:
            self._involved[:] = value

        elif isinstance(ranges, int):
            self._involved[ranges] = value

        elif isinstance(ranges, tuple):
            for i in range(*ranges):
                self._involved[i] = value

        elif isinstance(ranges, list):
            for i in ranges:
                self._involved[i] = value

    def _process(self, **kwargs):
        """ Perform necessary processing of set qubits """
        self.codeGraph.process(self, **kwargs)
        self._set_qubits()

    def _finalise(self):
        """ Finalise and fix codeGraph """
        self.codeGraph.finalise()

    def _handle_classical(self, **kwargs):
        """ Perform actions based on classical blocks """

    def _handle_measure(self, **kwargs):
        """ Handle measurements """

    def parse_code(self, codeObject=None, args=None, spargs=None, depth=0, maxDepth=-1):
        """ Traverse code recursively updating the builder accordingly """
        if args is None:
            args = {}
        if spargs is None:
            spargs = {}
        if codeObject is None:
            codeObject = self.code

        recurse = lambda block: self.parse_code(block,
                                                args=qargsSend, spargs=spargsSend,
                                                depth=depth+1, maxDepth=maxDepth)
        maths = lambda x: codeObject.resolve_maths(x, additionalVars=spargs)
        for line in codeObject.code:
            self.currOp = line.name
            if isinstance(line, CallGate):
                if not isinstance(line.callee, Opaque) and (maxDepth < 0 or depth < maxDepth):
                    # Prepare args and enter function
                    spargsSend = {arg.name: maths(sparg.val) for arg, sparg in zip(line.callee.spargs, line.spargs)}
                    if line.loops is not None:
                        for loopVar in range_inclusive(maths(line.loops.start[0]), maths(line.loops.end[0])):
                            qargsSend = {arg.name: resolve_arg(codeObject, qarg, args, spargs, loopVar)
                                         for arg, qarg in zip(line.callee.qargs, line.qargs)}
                            recurse(line.callee)
                    else:
                        qargsSend = {arg.name: resolve_arg(codeObject, qarg, args, spargs)
                                     for arg, qarg in zip(line.callee.qargs, line.qargs)}
                        recurse(line.callee)

                    del spargsSend
                    continue

                qargs = line.qargs

                if line.loops is not None:
                    for loopVar in range(maths(line.loops.start[0]), maths(line.loops.end[0])):
                        for qarg in qargs:
                            self._set_qubits(1, resolve_arg(codeObject, qarg, args, spargs, loopVar))
                        self._process(lineObj=line)
                else:
                    for qarg in qargs:
                        self._set_qubits(1, resolve_arg(codeObject, qarg, args, spargs))
                    self._process(lineObj=line)

            elif isinstance(line, SetAlias):
                a = range_inclusive(*line.pargs[1])
                b = range_inclusive(*line.qargs[1])
                for i, elem in enumerate(a):
                    args[line.alias.name][elem] = resolve_arg(codeObject, (line.qargs[0], b[i]), args, spargs)

            elif isinstance(line, Alias):
                args[line.name] = [None]*line.size

            elif isinstance(line, Loop):
                spargsSend = dict(**spargs)
                qargsSend = args
                for i in range_inclusive(maths(line.start[0]), maths(line.end[0])):
                    spargsSend[line.loopVar.name] = i
                    recurse(line)
                del qargsSend
                del spargsSend

            elif isinstance(line, CBlock):
                self._handle_classical(lineObj=line)

            elif isinstance(line, Measure):
                self._handle_measure(lineObj=line)

        if depth == 0:
            self._finalise()

def range_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return range(start, stop+1, step)

def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop like anything sensible would """
    return slice(start, stop+1, step)
