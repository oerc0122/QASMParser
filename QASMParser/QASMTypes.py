"""
Main module for tokenising parsed files
"""

import re
import copy
from pyparsing import (ParseResults)

from .QASMErrors import (argWarning, langWarning,
                         noResolveMathsWarning, mathsParseWarning,
                         dupWarning, existWarning, wrongTypeWarning,
                         indexWarning, aliasIndexWarning, argSizeWarning,
                         gateWarning, instructionWarning, includeNotMainWarning,
                         loopSpecWarning, argParseWarning, noExitWarning, declareGateWarning,
                         unitaryWarning, nonInvertUnit, nonInvertObj)
from .QASMTokens import (MathOp, Binary, Function)
from .FileHandle import (QASMBlock, NullBlock)

isInt = re.compile(r"[+-]?(\d+)(?:[eE][+-]?\d+)?")
isReal = re.compile(r"[+-]?(\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?")

def to_lang_error(self):
    """ Standard error handle for undefined function """
    print("Not implemented:", langWarning.format(type(self).__name__))
    quit()

class CoreOp:
    """ Abstract base class for operations which do not necessarily translate into QASM ops """
    to_lang = to_lang_error

# Base types
class Operation:
    """ Base class for callable function-like objects """

    def __init__(self, parent, qargs=None, pargs=None, gargs=None, spargs=None):
        """Initialise an operaion

        :param parent: Parent block defining object
        :param qargs: Input quantum arguments Input quantum arguments
        :param pargs: Input parameter arguments
        :param gargs:
        :param spargs: Input special arguments
        :returns:
        :rtype:

        """
        self.parent = parent
        self.loops = None
        self.qargs = qargs
        self.pargs = pargs
        self.spargs = spargs
        self.gargs = gargs
        self.innermost = None

    def add_loop(self, index, start, end):
        """ Wrap self in a loop

        :param index:
        :param start:
        :param end:

        """
        if self.loops:
            self.loops = NestLoop(self.loops, index, start, end)
        else:
            self.innermost = NestLoop(copy.copy(self), index, start, end)
            self.loops = self.innermost

    def finalise_loops(self):
        """ Dealias references of self if self has changed to avoid infinite loops """

        if self.loops:
            self.innermost.code = [copy.copy(self)]
            self.innermost.code[0].loops = []
        else:
            pass

    def handle_loops(self, pargs):
        """ Handle loop rules according to modified REQASM rules

        :param pargs: Input parameter arguments

        """
        baseStart, baseEnd = pargs[0][1]
        loopable = baseStart != baseEnd

        if loopable:
            loopVar = pargs[0][0].name + "_loop"
            self.add_loop(loopVar, baseStart, baseEnd)
        else:
            loopVar = False

        if loopVar:
            for parg in pargs:
                pargStart, _ = parg[1]
                if pargStart - baseStart:
                    parg[1] = loopVar + str(pargStart - baseStart)
                else:
                    parg[1] = loopVar
        else:
            for parg in pargs:
                parg[1] = parg[1][0]

    to_lang = to_lang_error


class Referencable:
    """ Base class for any element which will exist within scope """

    def __init__(self, parent):
        """Initialise a referencable object

        :param parent: Parent block defining object
        :returns:
        :rtype:

        """
        self.argType = type(self).__name__
        self.parent = parent

    to_lang = to_lang_error

class CodeBlock:
    """  Base class for an object which creates its own scope and contains code """

    def __init__(self, block, parent, copyObjs=True):
        """Initialise a code block

        :param block:Code block of operations
        :param parent: Parent block defining object
        :param copyObjs: Inherit objects from parent

        """
        self.code = []
        self.qargs = []
        self.pargs = []
        self.spargs = []
        self.gargs = []
        if copyObjs:
            self._objs = copy.copy(parent.get_objs("Copy"))
        else:
            self._objs = {}
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile.error


    def get_objs(self, obj=None):
        """ Return objects dict or element

        :param ob:j

        """
        if obj is not None:
            out = self._objs[obj]
        elif obj == "Copy":
            out = self._objs
        else:
            out = self._objs.items()
        return out

    def _dump_line(self):
        """ Return current line """
        return self.currentFile.nLine

    def _resolve(self, var, argType, index=""):
        """Resolve an argument and return its corresponding value or location based on current scope.

        :param var:
        :param argType:
        :param index:

        """
         # If we've accidentally passed the object through (fix this more thoroughly)
        if isinstance(var, (Constant)):
            var = getattr(var, 'name', var)

        if argType in ["ClassicalRegister", "QuantumRegister"]:
            if self._check_def(var, create=False, argType=argType):
                var = self._objs[var]
            elif self._check_def(var, create=False, argType="Alias"):
                var = self._objs[var]

            else:
                self._is_def(var, create=False, argType=argType)

            if index or index is None: # If index or implicit loop

                index = self.parse_range(index, var)

                out = [var, index]

            elif isinstance(var, Argument):

                out = [var, var.name]


        elif argType == "Alias":

            self._is_def(var, create=False, argType=argType)
            var = self._objs[var]

            index = self.parse_range(index, var)
            out = [var, index]

        elif argType == "Constant":
            if isinstance(var, ParseResults):
                var = var.pop()

            if var is None:
                out = None
            elif isinstance(var, (list, tuple)):
                out = [self._resolve(elem, argType="Constant") for elem in var]
            elif isinstance(var, (int, float)):
                out = var
            elif isinstance(var, str) and re.fullmatch(isInt, var):
                var = float(var)
                out = int(var)
            elif isinstance(var, str) and re.fullmatch(isReal, var):
                var = float(var)
                out = var
            elif issubclass(type(var), MathOp):
                out = self.parse_maths(var)
            else:
                self._is_def(var, create=False, argType=argType)
                out = self._objs[var] #.name

        elif argType == "Maths":

            if isinstance(var, (tuple, list)):
                if len(var) == 1:
                    var = var.pop()
                elif not var:
                    out = None
                else:
                    raise NotImplementedError("cannot handle list args")

            if var is None:
                out = None
            elif isinstance(var, (float, int)):
                out = var
            elif isinstance(var, str) and re.fullmatch(isInt, var):
                out = int(var)
            elif isinstance(var, str) and re.fullmatch(isReal, var):
                out = float(var)
            elif issubclass(type(var), MathOp):
                out = self.parse_maths(var)
            elif isinstance(var, ParseResults):
                if var.get("var", None) is not None:
                    out = self._resolve(var.get("var"), argType="Maths", index=var.get("ref"))
                elif var.get("start") or var.get("end"):
                    out = self.parse_range(var)
            elif isinstance(var, MathsBlock):
                out = var.maths
            else:
                self._is_def(var, create=False, argType=None)
                var = self._objs[var]

                if isinstance(var, Argument):

                    out = [var, var.name]

                elif isinstance(var, Constant):

                    out = var.name

                elif isinstance(var, ClassicalRegister):

                    if index or index is None: # If index or implicit loop
                        index = self.parse_range(index, var)

                        out = [var, index]
                    else:
                        out = [var, None]
                elif isinstance(var, QuantumRegister):
                    self._error("Cannot use quantum register {} in maths expression".format(var.name))

                else:
                    self._error("Undetermined type {} in maths parsing".format(type(var).__name__))

        elif argType == "Gate":
            self._is_def(var, create=False, argType=argType)
            out = self._objs[var]

        else:
            self._error("Unrecognised type {} in _resolve".format(argType))

        return out

    def resolve_maths(self, elem, additionalVars=None, topLevel=True, tempDict=None):
        """Perform the set of maths operations to return the final value or an error if it cannot be evaluated

        :param elem:
        :param additionalVars:
        :param topLevel:
        :param tempDict:

        """
         # Ops which should be unchanged
        identOp = ["-", "+", "*", "/", "%",
                   "<", "<=", "==", "!=", ">=", ">", "!",
                   "sin", "cos", "tan", "sqrt", "abs", "and", "or"]
        # Ops which require simple substitution
        subOp = {"xor":"!=", "mod":"%", "^":"**", "div":"//",
                 "arccos":"acos", "arcsin":"asin", "arctan":"atan"}

        outStr = ""

        if tempDict is None:
            tempDict = copy.copy(self._objs)
            if additionalVars is not None:
                for key, val in additionalVars.items():
                    tempDict[key] = val

        recurse = lambda elem: self.resolve_maths(elem, additionalVars, False, tempDict)

        if isinstance(elem, MathsBlock):
            for point in elem.maths:
                outStr += recurse(point)
        elif isinstance(elem, (float, int)):
            outStr += str(elem)
        elif isinstance(elem, Constant):
            if not hasattr(elem, "sparg"):
                outStr += recurse(elem.val)
            else:
                outStr += elem.name
        elif isinstance(elem, str) and elem in tempDict:
            outStr += recurse(tempDict[elem])
        elif isinstance(elem, Binary):
            for operator, operand in elem.args:
                if operator == "nop":
                    operand = recurse(operand)
                    outStr += str(operand)
                elif operator == "in":
                    if len(operand) == 2:
                        outStr = "({0} > {1} && {0} < {2})".format(outStr, *operand)
                    else:
                        raise OSError
                elif operator in identOp:
                    operand = recurse(operand)
                    outStr += " {} {}".format(operator, operand)
                elif operator in subOp:
                    operand = recurse(operand)
                    outStr += " {} {}".format(subOp[operator], operand)
                else:
                    raise NotImplementedError(operator)
        elif isinstance(elem, Function):
            elem = elem.op
            args = (recurse(arg) for arg in elem.args)
            outStr += "{}({})".format(elem, ", ".join(args))

        elif isinstance(elem, ParseResults):
            var = self._resolve(elem, argType="Constant")
            outStr += self.resolve_maths(var, additionalVars, False)
        elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
            self._error(noResolveMathsWarning.format(elem[0].name))
        else:
            raise NotImplementedError(mathsParseWarning.format(type(elem).__name__, elem))

        if not outStr:
            return "0"

        if topLevel:
            try:
                return eval(str(outStr))
            except ValueError:
                self._error("Error parsing maths string:\n '{}'\n".format(outStr))
        else:
            return outStr

    def _check_def(self, name, create, argType=None):
        """
        Check if object exists in local scope
        Create == True: returns False if an object already exists
        Create == False: returns False if object does not exist or is not of matching type

        :param name: Reference name of the object
        :param create:
        :param argType:

        """
        if name not in self._objs:
            out = create
        elif argType is not None and self._objs[name].argType is not argType:
            out = False
        else:
            out = not create
        return out

    def _is_def(self, name, create, argType=None):
        """
        Check if object exists in local scope
        Create == True: returns an error if an object already exists
        Create == False: returns an error if object does not exist or is not of matching type

        :param name: Reference name of the object
        :param create:
        :param argType:
        :returns:
        :rtype:

        """

        if create: # Check for duplicate naming
            if name in self._objs:
                self._error(dupWarning.format(Name=name, Type=self._objs[name].argType))

        else: # Check exists and type is right
            if name not in self._objs:
                self._error(existWarning.format(Type=argType, Name=name))
            elif argType is None:
                pass
            elif self._objs[name].argType is not argType:
                self._error(wrongTypeWarning.format(argType, self._objs[name].argType))

    def _check_bounds(self, interval, arg=None):
        """ Check for register over-run and raise error if present

        :param interval:
        :param arg:

        """
        if arg is None:
            return
        if not isinstance(arg.start, int) or not isinstance(arg.size, int):
            return

        if isinstance(interval[0], int) and interval[0] < arg.min:
            self._error(indexWarning.format(Req=interval[0], Var=arg.name, Min=arg.min, Max=arg.max))
        elif isinstance(interval[1], int) and interval[1] > arg.max:
            self._error(indexWarning.format(Req=interval[1], Var=arg.name, Min=arg.min, Max=arg.max))

    def comment(self, comment):
        """ Create a comment in scope of self and append it to the code

        :param comment:

        """
        self.code += [Comment(self, comment)]

    def new_variable(self, argName, size, classical):
        """ Create a new register in scope of self and append it to the code

        :param argName:
        :param size:
        :param classical:

        """
        self._is_def(argName, create=True)

        if classical:
            variable = ClassicalRegister(self, argName, size)
            self._objs[argName] = variable
        else:
            variable = QuantumRegister(self, argName, size)
            self._objs[argName] = variable

        self.code += [variable]

    def new_alias(self, argName, size):
        """ Create a new alias in scope of self

        :param argName:
        :param size:

        """
        self._is_def(argName, create=True)
        alias = Alias(self, argName, size)
        self._objs[argName] = alias
        self.code += [alias]

    def alias(self, aliasName, argIndex, referee, refIndex):
        """
        If an alias called aliasName exists: assign values to this alias
        If it does not exist:  Create it and if values assign it

        :param aliasName:
        :param argIndex:
        :param referee:
        :param refIndex:
        :returns:
        :rtype:

        """

        referee, refInter = self._resolve(referee, argType="QuantumRegister", index=refIndex)
        refInter = refInter[0], refInter[1]
        refSize = self.resolve_maths(refInter[1] - refInter[0] + 1)

        if self._check_def(aliasName, create=True, argType="Alias"):
            self.new_alias(aliasName, refSize)

        alias, aliasInter = self._resolve(aliasName, argType="Alias", index=argIndex)
        aliasSize = 1 + aliasInter[1] - aliasInter[0]
        if aliasSize != refSize:
            self._error(aliasIndexWarning.format(aliasName, aliasSize, refSize))

        self.code += [SetAlias(self, (alias, aliasInter), (referee, refInter))]

    def gate(self, gateName, block,
             pargs=None, qargs=None, spargs=None, gargs=None, byprod=None,
             recursive=False, unitary=False, argType="gate"):
        """Declare a new gate-like object in current scope and append it to the code

        :param gateName:
        :param block:Code block of operations
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param spargs: Input special arguments
        :param gargs:
        :param byprod: Output classical bit
        :param recursive: Gate allowed to recurse
        :param unitary: Gate allowed to contain non-unitaries
        :param argType:

        """
        self._is_def(gateName, create=True)

        if argType == "gate":
            gate = Gate(self, gateName, block,
                        pargs, qargs,
                        recursive=recursive, unitary=unitary)
        elif argType == "opaque":
            gate = Opaque(self, gateName,
                          pargs, qargs, spargs,
                          byprod=byprod, recursive=recursive, unitary=unitary)
        elif argType == "circuit":
            gate = Circuit(self, gateName, block,
                           pargs, qargs, spargs,
                           byprod=byprod, recursive=recursive, unitary=unitary)
        elif argType == "procedure":
            gate = Procedure(self, gateName, block,
                             pargs, qargs, spargs, gargs,
                             byprod=byprod, recursive=recursive, unitary=unitary)
        else:
            self._error(gateWarning.format(argType))

        self._objs[gate.name] = gate
        self.code += [gate]

    def let(self, var, val):
        """ Define and set variable in scope

        :param var:
        :param val:

        """
        varName, _ = var # Don't need varType
        value, valType = val

        val = (self._resolve(value, argType="Constant"), valType)
        if self._check_def(varName, create=True, argType="Constant"):
            letobj = Constant(self, var, val)
            self._objs[letobj.name] = letobj
        else:
            var = (self._resolve(varName, argType="Constant").name, None)
            letobj = Constant(self, var, val)
            self._objs[letobj.name] = letobj

        self.code += [Let(self, letobj)]

    def call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, modifiers=()):
        """ Check gate exists, if it does, call it, else raise error

        :param gateName:
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs:
        :param spargs: Input special arguments
        :param modifiers:

        """
        self._is_def(gateName, create=False, argType="Gate")

        pargs = self.parse_args(pargs, argType="Constant")
        qargs = self.parse_args(qargs, argType="QuantumRegister")
        gargs = self.parse_args(gargs, argType="Gate")
        spargs = self.parse_args(spargs, argType="Constant")


        if "INV" in modifiers.asList():
            orig = self._resolve(gateName, argType="Gate")
            if self._check_def("inv_"+gateName, create=True, argType="Gate"):
                inv = copy.copy(orig)
                inv.code = orig.invert(pargs, qargs)
                inv.name = "inv_"+inv.name
                orig.inverse = inv
                self.code += [inv]
            gateName = "inv_"+gateName

        gate = CallGate(self, gateName, pargs, qargs, gargs, spargs)

        self.code += [gate]

    def measurement(self, qarg, qindex, parg, bindex):
        """ Add measurement to code

        :param qarg:
        :param qindex:
        :param parg:
        :param bindex:

        """
        parg = self._resolve(parg, argType="ClassicalRegister", index=bindex)
        qarg = self._resolve(qarg, argType="QuantumRegister", index=qindex)

        measure = Measure(self, qarg, parg)

        self.code += [measure]

    def leave(self):
        """ Leave loop """
        if hasattr(self, "entry"):
            self.entry.exited()
        else:
            self._error("Cannot exit from a non-recursive gate")

    def reset(self, qarg, qindex):
        """ Reset register value

        :param qarg:
        :param qindex:

        """
        qarg = self._resolve(qarg, argType="QuantumRegister", index=qindex)
        reset = Reset(self, qarg)

        self.code += [reset]

    def output(self, parg, bindex):
        """ Write out creg

        :param parg:
        :param bindex:

        """
        parg = self._resolve(parg, argType="ClassicalRegister", index=bindex)
        output = Output(self, parg)

        self.code += [output]

    def loop(self, var, block, start, end):
        """ Add loop to code

        :param var:
        :param block:Code block of operations
        :param start:
        :param end:

        """
        loop = Loop(self, block, var, start, end)
        self.code += [loop]

    def cycle(self, var):
        """ Cycle loop

        :param var:

        """
        var = self._resolve(var, argType="Constant")
        if not var.loopVar:
            self._error("Cannot cycle non-loop vars")
        self.code += [Cycle(self, var)]

    def escape(self, var):
        """ Break out of loop

        :param var:

        """
        var = self._resolve(var, argType="Constant")
        if not var.loopVar:
            self._error("Cannot escape non-loop vars")
        self.code += [Escape(self, var)]

    def end(self):
        """ End current process """
        self.code += [TheEnd(self, self)]

    def new_while(self, cond, block):
        """ Add while block

        :param cond:
        :param block:Code block of operations

        """
        self.code += [While(self, cond, block)]

    def new_if(self, cond, block):
        """ Add if block

        :param cond:
        :param block:Code block of operations

        """
        self.code += [IfBlock(self, cond, block)]

    def classical_block(self, block):
        """ Add classical block

        :param block:Code block of operations

        """
        self.code += [CBlock(self, block)]

    def directive(self, directive, args=None, block=None):
        """ Determine and apply directive

        :param directive:
        :param args:
        :param block:Code block of operations

        """
        if directive in ["classicallang", "classlang"]:
            if not isinstance(self, ProgFile):
                self._error("Cannot set classical language outside of main code")
            if hasattr(self, "classLang"):
                if self.classLang is not None:
                    self._error("Classical language already defined as {}".format(self.classLang))
                self.classLang = args.strip('"\'')
        elif directive == "classical":
            if block:
                self.classical_block(block)
            else:
                self.classical_block([args+";"])
        elif directive == "opaque":
            if not block:
                self._error("Cannot set opaque by inline directive")
            gate = args[0]
            if self._objs[gate]:
                target = self._objs[gate]
                target.classical_block(block)
            else:
                self._error("Cannot find opaque {}".format(gate))
        else:
            self._error("Unrecognised directive: {}".format(directive))

    def parse_line(self, token):
        """ Parse token extract relevant vars and add to code

        :param token: Pyparsed token to translate and apply

        """
        nonCode = ["alias", "exit", "comment", "barrier", "directive"]
        keyword = token.get("keyword", None)
        comment = token.get("comment", "")

        if self.currentFile.version < token["reqVersion"]:
            self._error(instructionWarning.format(keyword,
                                                  self.currentFile.QASMType,
                                                  self.currentFile.versionNumber))

        if keyword == "include":
            if hasattr(self, "include"):
                self.include(token["file"])
            else:
                self._error(includeNotMainWarning)

        # Functions and gates
        elif keyword == "call":
            gateName = token["gate"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            gargs = token.get("gargs", [])
            mods = token.get("mods", [])

            self.call_gate(gateName, pargs, qargs, gargs, spargs, modifiers=mods)
        elif keyword == "measure":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            parg = token["creg"]["var"]
            bindex = token["creg"].get("ref", None)
            self.measurement(qarg, qindex, parg, bindex)
        elif keyword == "reset":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            self.reset(qarg, qindex)
        elif keyword == "output":
            parg = token["value"]["var"]
            bindex = token["value"].get("ref", None)
            self.output(parg, bindex)
        elif keyword == "if":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token["block"])
            self.new_if(cond, block)

        # Directives
        elif keyword == "directive":
            directive = token["directive"]
            args = token.get("args", None)
            block = token.get("block", None)
            self.directive(directive, args, block)
        elif keyword == "barrier":
            pass

        # Variable-like routines
        elif keyword in ["cbit", "creg"]: # Registers default to size 1 if blank
            argName = token["arg"]["var"]
            size = token["arg"].get("ref")
            if size is None:
                size = {"index": 1}
            else:
                size = token["arg"]["ref"]
            size = self.parse_range(size)
            self.new_variable(argName, size, True)
        elif keyword in ["qbit", "qreg"]:

            argName = token["arg"]["var"]
            size = token["arg"].get("ref")
            if size is None:
                size = {"index": 1}
            else:
                size = token["arg"]["ref"]
            size = self.parse_range(size)
            self.new_variable(argName, size, False)
        elif keyword == "val":
            var = token["var"]
            val = token["val"]
            argType = token["type"]
            self.let((var, argType), (val, None))
        elif keyword == "defAlias":
            name = token["alias"]["var"]
            index = self.parse_range(token["alias"]["ref"])
            self.new_alias(name, index)
        elif keyword == "alias":
            name = token["alias"]["var"]
            index = token["alias"].get("ref", None)
            qarg = token["target"]["var"]
            qindex = token["target"].get("ref", None)
            self.alias(name, index, qarg, qindex)

        # Loop routines
        elif keyword == "for":
            var = token["var"]
            start, end = self.parse_range(token["range"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.loop(var, block, start, end) # Handle "<" ending one early
        elif keyword == "while":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.new_while(block, cond)
        elif keyword == "next":
            var = token["loopVar"]
            self.cycle(var)
        elif keyword == "escape":
            var = token["loopVar"]
            self.escape(var)
        elif keyword == "exit":
            self.leave()

        elif keyword == "end":
            var = token["process"]
            self.end()

        # Gate declaration routines
        elif keyword == "gate":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(gateName, block, pargs, qargs, unitary=unitary, recursive=recursive)

        elif keyword == "circuit":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            byprod = token.get("byprod", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(gateName, block,
                      pargs, qargs, spargs, byprod=byprod, unitary=unitary, recursive=recursive, argType="circuit")

        elif keyword == "opaque":

            gateInfo = {"block":None, "argType":"opaque"}
            gateInfo['gateName'] = token.get("name")
            gateInfo['pargs'] = token.get("pargs", [])
            gateInfo['qargs'] = token.get("qargs", [])
            gateInfo['spargs'] = token.get("spargs", [])
            gateInfo['byprod'] = token.get("byprod", [])
            gateInfo['unitary'] = token.get("unitary", False)
            gateInfo['recursive'] = token.get("recursive", False)
            self.gate(**gateInfo)


        # Whole line comment
        elif keyword is None:
            self.comment(comment)
        else:
            self._error(instructionWarning.format(keyword,
                                                  self.currentFile.QASMType,
                                                  self.currentFile.versionNumber))

        if not self.code:
            self.code.append(Comment(self, ""))
        lastLine = self.code[-1]
        if hasattr(token, "original") and token.original:
            original = token.original
            if not hasattr(lastLine, "original") or keyword not in nonCode:
                lastLine.original = original.strip()
            elif keyword in nonCode:
                lastLine.original += "\n"+original.strip()
        if keyword is not None and comment != "":
            lastLine.inlineComment = Comment(self, comment)

    def parse_args(self, argsIn, argType):
        """ Parse function arguments

        :param argsIn:
        :param argType:

        """
        if not argsIn:
            return []
        args = []
        if argType in ["ClassicalRegister", "QuantumRegister"]:
            for arg in argsIn:
                args.append(self._resolve(arg["var"], argType, arg.get("ref", None)))
        elif argType in ["Constant"]:
            for arg in argsIn:
                args.append(self._resolve(arg, argType))
        else:
            self._error(argParseWarning.format(argType))

        return args

    def parse_instructions(self):
        """ Run through instructions and apply to AST """
        for instruction in self.instructions:
            self.parse_line(instruction)

    def parse_range(self, rangeSpec, arg=None, indexOnly=False):
        """ Parse a range or index into tuple

        :param rangeSpec:
        :param arg:
        :param indexOnly:

        """
        if rangeSpec is None:
            if arg:
                if arg.size is None:
                    interval = (None, None)
                elif isinstance(arg.size, int):
                    if indexOnly:
                        interval = (arg.size, arg.size)
                    else:
                        interval = (0, arg.size-1)
                elif isinstance(arg.size, str):
                    if indexOnly:
                        interval = (arg.size, arg.size)
                    else:
                        interval = (0, arg.size)
                elif isinstance(arg.size, MathsBlock):
                    return (0, arg.size)
                else:
                    self._error("Unable to determine argument size")
            else:
                self._error(loopSpecWarning.format("start or end"))

        elif rangeSpec.get("index", None) is not None:
            point = rangeSpec.get("index", None)
            if isinstance(point, ParseResults):
                point = point.get("var", point)
            point = self._resolve(point, argType="Constant")
            interval = (point, point)
            self._check_bounds(interval, arg)

        elif rangeSpec.get("start", None) is not None or rangeSpec.get("end", None) is not None:
            if indexOnly:
                self._error("Passed range specifier to index")
            start, end = rangeSpec.get("start", None), rangeSpec.get("end", None)

            start = self._resolve(start, argType="Constant")
            end = self._resolve(end, argType="Constant")

            if arg:
                if not start:
                    start = 0
                if not end:
                    end = arg.size
            else:
                if start is None or end is None:
                    self._error(loopSpecWarning.format("end" if end is None else "start"))

            interval = (start, end)

            self._check_bounds(interval, arg)

        else:
            self._error("Unknown range specification: {}".format(rangeSpec))

        return interval

    def parse_maths(self, maths):
        """ Parse maths into maths block

        :param maths:

        """
        return MathsBlock(self, maths, topLevel=True)

    to_lang = to_lang_error

# Maths Parsing

class MathsBlock:
    """ Block for handling maths as returned from the parser """

    def __init__(self, parent, maths, topLevel=False):
        """Initialise a maths block

        :param parent: Parent block defining object
        :param maths:
        :param topLevel:
        :returns:
        :rtype:

        """
        self.parent = parent
        self.topLevel = topLevel
        elem = copy.deepcopy(maths)

        self.logical = False
        if isinstance(elem, Binary):
            newArgs = []
            for operator, operand in elem.args:
                # Skip identities
                if (operator in "+-") and str(operand) == "0":
                    continue
                if (operator in "*/%") and str(operand) == "1":
                    continue

                if issubclass(type(operand), MathOp):
                    operand = MathsBlock(parent, operand)
                    newArgs.append((operator, operand))
                else:
                    operand = parent._resolve(operand, argType="Maths")
                    newArgs.append((operator, operand))
            elem.args = newArgs
        elif isinstance(elem, Function):
            newArgs = []
            for arg in elem.args:
                if issubclass(type(arg), MathOp):
                    arg = MathsBlock(parent, arg)
                    newArgs.append(arg)
                else:
                    arg = parent._resolve(arg, argType="Maths")
                    newArgs.append(arg)
            elem.args = newArgs

        self.maths = [elem]

    def __add__(self, val):
        return MathsBlock(self.parent, Binary([[self.maths, "+", val]]))

    def __sub__(self, val):
        return MathsBlock(self.parent, Binary([[self.maths, "-", val]]))

    def __div__(self, val):
        return MathsBlock(self.parent, Binary([[self.maths, "/", val]]))

    def __mul__(self, val):
        return MathsBlock(self.parent, Binary([[self.maths, "*", val]]))

    to_lang = to_lang_error


# Variable types

class Constant(Referencable):
    """ Class pertaining to a constant value or variable object """

    def __init__(self, parent, var, val):
        """Initialise constant

        :param parent: Parent block defining object
        :param var:
        :param val:
        :returns:
        :rtype:

        """
        Referencable.__init__(self, parent)
        self.name = var[0]
        self.varType = var[1]
        self.val = val[0]
        self.cast = val[1]
        self.loopVar = False
        self.parent = parent

    def __add__(self, val):
        return MathsBlock(self.parent, Binary([[self, "+", val]]))

    def __sub__(self, val):
        return MathsBlock(self.parent, Binary([[self, "-", val]]))

    def __div__(self, val):
        return MathsBlock(self.parent, Binary([[self, "/", val]]))

    def __mul__(self, val):
        return MathsBlock(self.parent, Binary([[self, "*", val]]))

    def __deepcopy__(self, memo):
        return Constant(self.parent, (self.name, self.varType), (self.val, self.cast))

class Register(Referencable):
    """
    Base class pertaining to list-like objects:
    - Classical registers (creg)
    - Quantum registers   (qreg)
    - Aliases             (alias)
    """

    def __init__(self, parent, name, size):
        """Initialise a general register object

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param size:
        :returns:
        :rtype:

        """
        Referencable.__init__(self, parent)
        self.name = name

        self.size = self.render_size(size)

    def render_size(self, inter):
        """Parse a size interval to determine the actual size, start and end of the register

        :param inter: Size interval to be parsed and set up

        """
        if isinstance(inter, (list, tuple)):
            start, end = inter

            if isinstance(start, Constant):
                start = start.val
            if isinstance(end, Constant):
                end = end.val
            if start == end:
                size = end
                start, end = 0, end
            else:
                size = end - start + 1
            self.min = start
            self.max = end
            self.start = 0
            self.end = size

        else:
            size = inter
            self.min = 0
            self.max = size
            self.start, self.end = self.min, self.max

        return size

class QuantumRegister(Register):
    """
    Quantum register as created by "qreg"
    """
    numQubits = 0

    def __init__(self, parent, name, inter):
        """Initialise a quantum register

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param inter:
        :returns:
        :rtype:

        """
        Register.__init__(self, parent, name, inter)

        self.start += QuantumRegister.numQubits
        self.end += QuantumRegister.numQubits
        QuantumRegister.numQubits += self.size

class ClassicalRegister(Register):
    """
    Classical register as created by "creg"
    """
    def __init__(self, parent, name, inter):
        """Initialise a classical register

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param inter:
        :returns:
        :rtype:

        """
        Register.__init__(self, parent, name, inter)

        self.start = 0
        self.end = self.size

class DeferredClassicalRegister(ClassicalRegister):
    """
    Classical register whose size is unknown until execution of the code,
    e.g. size is a function variable
    """
    def __init__(self, parent, name, size):
        """Initialise a deferred classical register

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param size:
        :returns:
        :rtype:

        """
        ClassicalRegister.__init__(self, parent, name, size)
        self.argType = "ClassicalRegister"

class Alias(Register):
    """
    Alias as specified in REQASM
    """

    def __init__(self, parent, name, inter):
        """Initialise an alias

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param inter:
        :returns:
        :rtype:

        """
        Register.__init__(self, parent, name, inter)
        self.argType = "Alias"
        self.targets = [(None, None)]*self.size
        self.allSet = False

    def set_target(self, indices, target, interval):
        """ Aliases target to indices

        :param indices:
        :param target:
        :param interval:

        """
        for index in range(indices[0], indices[1]+1):
            self.targets[index - self.min] = (target, interval[0] + index)

        self.allSet = all(target != (None, None) for target in self.targets)

class Argument(Register):
    """
    Dummy register for arguments to gates permitted to have size under REQASM specifications
    """

    def __init__(self, parent, name, size=None):
        """Initialise an argument

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param size:
        :returns:
        :rtype:

        """
        Register.__init__(self, parent, name, size)
        self.name = name
        self.argType = "QuantumRegister"
        self.start = name
        self.end = self.size

# Operation types
class Return(Operation):
    """ Return from function """
    def __init__(self, parent, parg):
        """Initialise a return

        :param parent: Parent block defining object
        :param parg:
        :returns:
        :rtype:

        """
        Operation.__init__(self, parent, pargs=parg)

class Comment:
    """ Add comment to code """
    def __init__(self, parent, comment):
        """Initialise a comment

        :param parent: Parent block defining object
        :param comment:
        :returns:
        :rtype:

        """
        self.parent = parent
        self.name = comment
        self.comment = comment

    to_lang = to_lang_error

class Let(Operation):
    """ Set a variable """
    def __init__(self, parent, var, val=None):
        """Initialise a let

        :param parent: Parent block defining object
        :param var:
        :param val:
        :returns:
        :rtype:

        """
        self.parent = parent
        if isinstance(var, Constant):
            self.const = var
        elif isinstance(var, (tuple, list)):
            self.const = Constant(self.parent, var, val)
        else:
            raise TypeError("Bad assignment of let")

class CallGate(Operation):
    """ Call a gate """
    def __init__(self, parent, gate, pargs, qargs, gargs, spargs):
        """Initialise a call to a gate

        :param parent: Parent block defining object
        :param gate:
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs:
        :param spargs: Input special arguments
        :returns:
        :rtype:

        """
        self.name = gate
        Operation.__init__(self, parent, qargs, pargs, gargs, spargs)

        self.resolvedQargs = None

        self.callee = self.parent._resolve(self.name, argType="Gate")

        self._check_args(pargs, qargs, gargs, spargs)

        self.handle_loops(self.qargs)

    def _check_args(self, pargs, qargs, gargs, spargs):
        """ Check gate arguments are valid and of the right size. Raise error if not

        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs:
        :param spargs: Input special arguments

        """
          # Check number of args matches
        for name, args, expect in zip(["pargs", "gargs", "spargs"],
                                      [pargs, gargs, spargs],
                                      [self.callee.pargs, self.callee.gargs, self.callee.spargs]):
            if len(args) != len(expect):
                place = "call to {}".format(self.name)
                expect = "{} {}".format(len(expect), name)
                received = len(args)
                self.parent._error(argWarning.format(place, expect, received))

        parsedSparg = zip((sparg.name for sparg in self.callee.spargs), spargs)

        newSpargs = dict(parsedSparg)
        newQargs = []

        for sparg in spargs: # Disambiguate?
            if sparg in self.parent.spargs:
                newSpargs[sparg.name] = 0


        for qarg in self.callee.qargs:
            newQargs.append([qarg, int(self.parent.resolve_maths(qarg.size, additionalVars=newSpargs))])

        self.resolvedQargs = newQargs

        self.nLoops = 0
        # Implicit loops mean we handle qargs separately
        for index, qarg in enumerate(qargs):
            # Hack to bypass stupidity of Python's object fiddling
            if isinstance(qarg[1][1], (Constant, MathsBlock)) or isinstance(qarg[1][0], (Constant, MathsBlock)) or \
               newQargs[index][1] == 0:
                continue
            nArg = qarg[1][1] - qarg[1][0] + 1
            expect = newQargs[index][1]
            if not isinstance(nArg, int): # Skip constants which cannot be resolved
                continue
            if not self.nLoops:  # Assume all vars must have the same number of loops
                self.nLoops = nArg // expect
            if nArg % expect != 0:
                place = "call to {} in qarg {}".format(self.name, index+1)
                expect = "multiple of {}".format(expect)
                received = nArg
                self.parent._error(argWarning.format(place, expect, received))
            elif nArg // expect != self.nLoops:
                place = "call to {} in qarg {} for implicit {} loops".format(self.name, index+1, self.nLoops)
                expect = "{} qubits".format(self.nLoops*expect)
                received = nArg
                self.parent._error(argWarning.format(place, expect, received))

    def handle_loops(self, pargs):
        """
        Handle loops for calling of gates:
        If gate args all just qubits not registers:
            Use regular handling
        If gate takes qregs, but can be looped (based on args):
            Loop in blocks
        If gate takes qregs and is not looped:
            Use prevars

        :param pargs: Input parameter arguments
        :returns: None
        :rtype: None

        """

        """
        """

        # Gates need special loop handling for multi-args
        if all(qarg[1] == 1 for qarg in self.resolvedQargs): # Can use regular loop if everyone only takes 1 arg
            Operation.handle_loops(self, pargs)
        elif self.nLoops < 2:
            for parg in pargs:
                pargStart, pargEnd = parg[1]

                if pargStart == pargEnd:
                    parg[1] = pargStart
                else:
                    pass
        else:
            raise NotImplementedError("Cannot currently loop non-linear gates")

class SetAlias(Operation):
    """ Set an alias to refer to a quantum register """
    def __init__(self, parent, alias, target):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :param alias:
        :param target:
        :returns:
        :rtype:

        """
        Operation.__init__(self, parent, pargs=alias, qargs=target)
        self.alias = alias[0]
        self.alias.set_target(alias[1], target[0], target[1])

class Measure(Operation):
    """ Measure a qubit and assign to a classical register """
    def __init__(self, parent, qarg, parg):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :param qarg:
        :param parg:
        :returns:
        :rtype:

        """
        Operation.__init__(self, parent, qarg, parg)
        self.handle_loops([self.pargs, self.qargs])
        parg, bindex = self.pargs
        qarg, _ = self.qargs

        # Check bindices
        if bindex is None:
            if parg.size < qarg.size:
                raise IOError(argSizeWarning.format(Req=qarg.size, Var=parg.name, Var2=qarg.name, Max=parg.size))
            if parg.size > qarg.size:
                raise IOError(argSizeWarning.format(Req=parg.size, Var=qarg.name, Var2=parg.name, Max=qarg.size))
            self.pargs[1] = self.qargs[1]
        self.finalise_loops()

class Reset(Operation):
    """ Reset a quantum register """
    def __init__(self, parent, qarg):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :param qarg:
        :returns:
        :rtype:

        """
        Operation.__init__(self, parent, qarg)
        self.handle_loops([self.qargs])

class Output(Operation):
    """ Write a classical register to screen """
    def __init__(self, parent, parg):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :param parg:
        :returns:
        :rtype:

        """
        Operation.__init__(self, parent, pargs=parg)
        self.handle_loops([self.pargs])

class EntryExit(CoreOp):
    """ Exit block? """
    def __init__(self, parent):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :returns:
        :rtype:

        """
        self.parent = parent
        self.depth = 1

    def exited(self):
        """ Depth is defined """
        self.depth = 0

class While(CodeBlock):
    """ Define a while loop """
    def __init__(self, parent, block, cond):
        """FIXME! briefly describe function

        :param parent: Parent block defining object
        :param block:Code block of operations
        :param cond:
        :returns:
        :rtype:

        """
        self.cond = cond
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_instructions()

class IfBlock(CodeBlock):
    """ Define an if statement """
    def __init__(self, parent, cond, block):
        """Initialise the if statement

        :param parent: Parent block defining object
        :param cond:
        :param block:Code block of operations
        :returns:
        :rtype:

        """
        self.cond = cond
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_instructions()

class Gate(Referencable, CodeBlock):
    """
    Type to handle general general gates and their extensions (circuit, procedure, etc.)

    Attributes:

    """
    internalGates = {}

    def __init__(self, parent, name, block,
                 pargs=(), qargs=(), spargs=(), gargs=(), byprod=(),
                 recursive=False, unitary=False, returnType=None):
        """Initialises the gate object

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param block: Code block of operations
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments
        :param spargs: Input special arguments
        :param gargs: Input gate arguments
        :param byprod: Output classical bit
        :param recursive: Gate allowed to recurse
        :param unitary: Gate allowed to contain non-unitaries
        :param returnType: Type of return of function
        :returns: New gate object
        :rtype: Gate

        """

        Referencable.__init__(self, parent)
        self.name = name
        self.spargs = []
        self.gargs = []

        CodeBlock.__init__(self, block, parent=parent)
        self.unitary = unitary

        self._inverse = None

        if recursive:
            self.gate(name, NullBlock(block), pargs, qargs, unitary=unitary)
            self.code = []
            self.entry = EntryExit(self.name)

        self.parse_gate_args(pargs, "ClassicalArgument")
        self.parse_gate_args(spargs, "SpecialArgument")
        self.parse_gate_args(qargs, "QuantumArgument")
        self.parse_gate_args(gargs, "Gates")

        self.parse_instructions()

        if not byprod:
            self.returnType = None
        else:
            self.code.append(Return(self, byprod))
            self.returnType = "listint"

        if returnType is not None:
            self.returnType = returnType

        if recursive and self.entry.depth > 0:
            self._error(noExitWarning.format(self.name))

    def invert(self, pargs, qargs):
        """Calculates the inverse of the gate and called gates and assigns it to self._inverse

        :param pargs: Input parameter arguments Call's parameter arguments for inversion
        :param qargs: Input quantum arguments Input quantum arguments Call's quantum arguments for inversion

        """
        if not self.unitary:
            self._error(nonInvertUnit)
        if self._inverse:
            return self._inverse
        self._inverse = []

        for line in reversed(self.code):
            if isinstance(line, CallGate):
                self._inverse += self._objs[line.name].invert(pargs=line.pargs, qargs=line.qargs)
            else:
                self._error(nonInvertObj.format(self.name))

        return self._inverse

    def parse_gate_args(self, args, argType):
        """
        Parse classes of arguments and assign them in scope
        """

        if not args:
            return

        if argType in ["ClassicalArgument"]:
            for arg in args:
                self._objs[arg] = Constant(self, (arg, "float"), (MathsBlock(self, arg), None))
                self.pargs.append(self._objs[arg])
        elif argType in ["SpecialArgument"]:
            for arg in args:
                self._objs[arg] = Constant(self, (arg, "int"), (MathsBlock(self, arg), None))
                self.spargs.append(self._objs[arg])
        elif argType in ["QuantumArgument"]:
            for argTok in args:
                arg = argTok["var"]
                size = argTok.get("ref", {"index":1})
                if size is not None:
                    size = self.parse_range(size)
                self._objs[arg] = Argument(self, arg, size)
                self.qargs.append(self._objs[arg])
        elif argType in ["Gates"]:
            for arg in args:
                self.gate(arg, NullBlock(self), unitary=self.unitary)

    def new_variable(self, argName, size, classical):
        if not classical:
            self._error(declareGateWarning.format("carg", type(self).__name__))
        else:
            self._error(declareGateWarning.format("qarg", type(self).__name__))

    def call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, modifiers=()):
        self._is_def(gateName, create=False, argType="Gate")
        # Perform unitary checks
        if self.unitary and not self._objs[gateName].unitary:
            self._error(unitaryWarning.format(gateName, self.name))

        CodeBlock.call_gate(self, gateName, pargs, qargs, gargs, spargs, modifiers)

    def measurement(self, qarg, qindex, parg, bindex):
        self._error("Cannot perform measure in gate")

class Circuit(Gate):
    """
    Type reflecting REQASM extension to gate
    """

    def __init__(self, *args, **kwargs):
        Gate.__init__(self, *args, **kwargs)
        self.argType = "Gate"
        self.measurement = CodeBlock.measurement

    def new_variable(self, argName, size, classical):
        """ Override new variable of gate to allow classical variables """
        self._is_def(argName, create=True)

        if classical:
            variable = DeferredClassicalRegister(self, argName, size)
            self._objs[argName] = variable
        else:
            self._error(declareGateWarning.format("qarg", type(self).__name__))

        self.code += [variable]

    measurement = CodeBlock.measurement

class Opaque(Gate):
    """
    Type reflecting OpenQASM opaque gate
    Allows the definition of a block through directive extensions
    """
    def __init__(self, parent, name,
                 pargs=(), qargs=(), spargs=(), gargs=(), byprod=(),
                 recursive=False, unitary=False, returnType=None):
        self.argType = "Gate"
        self.name = name
        self.inverse = None
        self.parent = parent
        self.parentFile = parent.currentFile
        self.returnType = returnType
        self.set_block(NullBlock(self.parentFile))
        self.unitary = unitary

        self.pargs = []
        self.qargs = []
        self.spargs = []
        self.gargs = []
        self.parse_gate_args(pargs, "ClassicalArgument")
        self.parse_gate_args(spargs, "SpecialArgument")
        self.parse_gate_args(qargs, "QuantumArgument")
        self.parse_gate_args(gargs, "Gates")

    def set_block(self, block):
        """ Set the block of the opaque gate """
        CodeBlock.__init__(self, block, parent=self.parent)
        self.parse_instructions()

    def set_inverse(self, block):
        """ Set the inverse of the opaque gate """
        CodeBlock.__init__(self, block, parent=self.parent)
        self.inverse = block

class CBlock:
    """ Classical block """
    def __init__(self, parent, block):
        self.parent = parent
        self.block = block

class Loop(CodeBlock):
    """ Loop structure """
    def __init__(self, parent, block, var, start, end, step=None):
        CodeBlock.__init__(self, block, parent=parent)
        self._objs[var] = Constant(self, (var, "int"), (0, None)) # Value is 0 for disambiguating resolution
        self._objs[var].loopVar = True
        self.loopVar = self._objs[var]
        self.name = var+"_loop"
        self.depth = 1

        if not isinstance(var, (list, tuple)):
            var = [var]
        if not isinstance(start, (list, tuple)):
            start = [start]
        if not isinstance(end, (list, tuple)):
            end = [end]

        self.var = var
        self.start = start
        self.end = end
        self.step = step or (1,)*len(start)
        if not isinstance(self.step, (list, tuple)):
            self.step = [step]
        self.parse_instructions()

class NestLoop(Loop):
    """ Nested loop structure """
    def __init__(self, block, var, start, end, step=1):
        self.code = [block]
        self.depth = 1
        if not isinstance(var, (list, tuple)):
            var = [var]
        if not isinstance(start, (list, tuple)):
            start = [start]
        if not isinstance(end, (list, tuple)):
            end = [end]

        self.var = var
        self.start = start
        self.end = end
        self.step = step
        if not isinstance(self.step, (list, tuple)):
            self.step = [step]

class InitEnv(CoreOp):
    """ Initialise QuESTEnv """
    def __init__(self):
        pass

class Verbatim:
    """ Literal text """
    def __init__(self, line):
        self.line = str(line)

    def to_lang(self):
        """ Return line literally """
        return self.line

class Include(CoreOp):
    """ Import other QASM files """
    def __init__(self, parent, filename, code):
        self.parent = parent
        self.filename = filename
        self.code = code

class Cycle(CoreOp):
    """ Jump to end of loop """
    def __init__(self, parent, var):
        self.parent = parent
        self.var = var

class Escape(CoreOp):
    """ Break out of loop """
    def __init__(self, parent, var):
        self.parent = parent
        self.var = var

class TheEnd(CoreOp):
    """ Kill running process """
    def __init__(self, parent, process):
        self.parent = parent
        self.process = process
