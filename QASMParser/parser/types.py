"""
Main module for tokenising parsed files
"""

import re
import copy
from pyparsing import (ParseResults)

from .errors import (argWarning, langWarning, badMappingWarning,
                     dupWarning, existWarning, wrongTypeWarning,
                     indexWarning, aliasIndexWarning, argSizeWarning,
                     gateWarning, instructionWarning, includeNotMainWarning,
                     loopSpecWarning, argParseWarning, noExitWarning,
                     mathsEvalWarning, failedOpWarning, redefClassLangWarning,
                     inlineOpaqueWarning, badDirectiveWarning, rangeSpecWarning,
                     rangeToIndexWarning, gateDeclareWarning)
from .tokens import (MathOp, Binary, Function)
from .filehandle import (QASMBlock, NullBlock)

isInt = re.compile(r"[+-]?(\d+)(?:[eE][+-]?\d+)?")
isReal = re.compile(r"[+-]?(\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?")

def slice_inclusive(start=None, stop=None, step=1):
    """ Actually include the stop, like anything sensible would """
    return slice(start, stop+1, step)

def resolve_arg(block, var, args, spargs, loopVar=None):
    """ Determine the actual register ID

    :param block: block to resolve argument
    :param var:   var to resolve
    :param args:  extra arguments
    :param spargs: extra special arguments
    :param loopVar: Whether there is an implicit loop
    :returns:
    :rtype:

    """


    var, ind = var
    maths = lambda x: block.resolve_maths(x, additionalVars=spargs)

    if isinstance(ind, (list, tuple)):
        *ind, = map(maths, ind)
    elif isinstance(ind, str) and loopVar is not None:
        shift = ind.split("_loop")[1]
        shift = shift if shift else 0
        ind = loopVar + int(shift)
    elif isinstance(ind, Constant):
        if ind.name in spargs: # If we can do a direct sub
            ind = maths(spargs[ind.name])
        else:
            raise KeyError(badConstantWarning.format(ind.name))
    else:
        ind = maths(ind)

    if var.name in args:
        out = copy.copy(args[var.name])
        if isinstance(out, (list, tuple)):
            if isinstance(out, tuple) and len(out) == 2:
                *out, = range(*out)
            if isinstance(ind, int):
                out = out[ind]
            elif isinstance(ind, (list, tuple)):
                out = list(out[slice_inclusive(*ind)])
            else:
                raise Exception("Cannot handle request")
        elif isinstance(out, int):
            out = out

    elif isinstance(ind, (list, tuple)):
        *out, = map(lambda x: var.start + x, ind)
        out[1] += 1
        out = tuple(out)
    elif isinstance(ind, int):
        out = var.start + ind
    else:
        raise Exception("Cannot handle request")

    return out

def to_lang_error(self):
    """ Standard error handle for undefined function """
    print("Not implemented:", langWarning.format(type(self).__name__))
    quit()

class CoreOp:
    """ Abstract base class for QASM operations """
    def __init__(self, parent):
        self._parent = parent
        self._name = type(self).__name__
        self._trueType = type(self).__name__

    trueType = property(lambda self: self._trueType)
    name = property(lambda self: self._name)
    parent = property(lambda self: self._parent)
    to_lang = to_lang_error

# Base types
class Operation(CoreOp):
    """ Base class for callable function-like objects

    :param parent: Parent block defining object
    :param qargs: Input quantum arguments Input quantum arguments
    :param pargs: Input parameter arguments
    :param gargs: Input gate arguments
    :param spargs: Input special arguments
    """

    def __init__(self, parent, qargs=None, pargs=None, gargs=None, spargs=None):
        """Initialise an operation """
        CoreOp.__init__(self, parent)
        self.loops = None
        self._qargs = qargs
        self._pargs = pargs
        self._spargs = spargs
        self._gargs = gargs
        self._error = self.parent.currentFile.error
        self.innermost = None

    @property
    def qargs(self):
        """ qargs getter """
        return self._qargs

    @property
    def pargs(self):
        """ pargs getter """
        return self._pargs

    @property
    def spargs(self):
        """ spargs getter """
        return self._spargs

    @property
    def gargs(self):
        """ gargs getter """
        return self._gargs

    def _add_loop(self, index, start, end):
        """ Wrap self in a loop

        :param index: Loop variable
        :param start: Loop start
        :param end:   Loop end

        """
        if self.loops:
            self.loops = NestLoop(self.loops, index, start, end)
        else:
            self.innermost = NestLoop(copy.copy(self), index, start, end)
            self.loops = self.innermost

    def _finalise_loops(self):
        """ Dealias references of self if self has changed to avoid infinite loops """
        if self.loops:
            self.innermost.finalise()

    def handle_loops(self, pargs):
        """ Handle loop rules according to modified REQASM rules

        :param pargs: Input parameter arguments

        """
        baseStart, baseEnd = pargs[0][1]
        loopable = baseStart != baseEnd

        if loopable:
            loopVar = pargs[0][0].name + "_loop"
            self._add_loop(loopVar, baseStart, baseEnd)
        else:
            loopVar = False

        if loopVar:
            for parg in pargs:
                pargStart, _ = parg[1]
                if pargStart - baseStart:
                    parg[1] = loopVar + f" + {pargStart - baseStart}"
                else:
                    parg[1] = loopVar
        else:
            for parg in pargs:
                parg[1] = parg[1][0]


class Referencable(CoreOp):
    """ Base class for any element which will exist within scope

    :param parent: Parent block defining object
    """
    def __init__(self, parent, name):
        """Initialise a referencable object """
        CoreOp.__init__(self, parent)
        self._name = name
        self._argType = type(self).__name__

    argType = property(lambda self: self._argType)

class CodeBlock(CoreOp):
    """  Base class for an object which creates its own scope and contains code """
    def __init__(self, parent, block, copyObjs=True):
        """Initialise a code block

        :param block: Code block of operations
        :param parent: Parent block defining object
        :param copyObjs: Inherit objects from parent

        """
        CoreOp.__init__(self, parent)

        if parent is not None:
            self.classLang = parent.classLang
        else:
            self.classLang = None

        self._code = []
        self._qargs = []
        self._pargs = []
        self._spargs = []
        self._gargs = []
        self._objs = copy.copy(parent.get_objs("Copy")) if copyObjs else {}
        self._to_free = []
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile.error

    code = property(lambda self: self._code)
    pargs = property(lambda self: self._pargs)
    qargs = property(lambda self: self._qargs)
    spargs = property(lambda self: self._spargs)
    gargs = property(lambda self: self._gargs)

    def get_objs(self, obj=None):
        """ Return objects dict or element

        :param obj: Object to be searched for

        """
        if obj == "Copy":
            out = self._objs
        elif obj is not None:
            out = self._objs[obj]
        else:
            out = self._objs.items()

        return out

    def dump_line(self):
        """ Return current line """
        return self.currentFile.nLine

    def resolve(self, var, argType, index=""):
        """Resolve an argument and return its corresponding value or location based on current scope.

        :param var: Variable to resolve
        :param argType: Type of variable to resolve
        :param index: Possible index of register objects
        :returns: Resolved argument
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
            else:
                out = var
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
                out = [self.resolve(elem, argType="Constant") for elem in var]
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
                    raise NotImplementedError(argParseWarning.format(type(var).__name__))

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
                    out = self.resolve(var.get("var"), argType="Maths", index=var.get("ref"))
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
                    self._error(failedOpWarning.format("use quantum register "+var.name, "resolve_maths"))
                else:
                    self._error(failedOpWarning.format("resolve type "+var.trueType, "resolve_maths"))

        elif argType == "Gate":
            self._is_def(var, create=False, argType=argType)
            out = self._objs[var]
        else:
            self._error(argParseWarning.format(argType))

        return out

    def resolve_maths(self, elem, additionalVars=None, topLevel=True, tempDict=None):
        """Perform the set of maths operations to return the final value or an error if it cannot be evaluated

        :param elem: Element to be resolved
        :param additionalVars: A dictionary of variables already resolved with values
        :param topLevel: Whether this is the function to eval
        :param tempDict: Higher level resolved values
        :returns: Resolved numerical value of mathsblock
        :rtype: int/float/bool
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
            var = self.resolve(elem, argType="Constant")
            outStr += self.resolve_maths(var, additionalVars, False)
        elif isinstance(elem, list) and isinstance(elem[0], ClassicalRegister):
            self._error(failedOpWarning.format("resolve " + elem[0].name + " to constant value", "resolve_maths"))
        else:
            if hasattr(elem, "trueType"):
                raise NotImplementedError(failedOpWarning.format(f"parse {elem.trueType} {elem}", "resolve_maths"))
            else:
                raise NotImplementedError(failedOpWarning.format(f"parse {type(elem).__name__} {elem}", "resolve_maths"))
        if not outStr:
            return "0"

        if topLevel:
            try:
                return eval(str(outStr))
            except ValueError:
                self._error(mathsEvalWarning.format(outStr))
        else:
            return outStr

    def _check_def(self, name, create, argType=None):
        """
        Check if object exists in local scope
        Create == True: returns False if an object already exists
        Create == False: returns False if object does not exist or is not of matching type

        :param name: Reference name of the object
        :param create: Whether variable is to be created
        :param argType: Type of argument to find
        :returns: Whether object exists or can be created
        :rtype: Bool
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
        :param create: Whether variable is to be created
        :param argType: Type of argument to find
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

        :param interval: Range to establish in range
        :param arg:      Argument to check range of

        """
        if arg is None:
            return
        if not isinstance(arg.start, int) or not isinstance(arg.size, int):
            return

        if isinstance(interval[0], int) and interval[0] < arg.minIndex:
            self._error(indexWarning.format(Req=interval[0], Var=arg.name, Min=arg.minIndex, Max=arg.maxIndex))
        elif isinstance(interval[1], int) and interval[1] > arg.maxIndex:
            self._error(indexWarning.format(Req=interval[1], Var=arg.name, Min=arg.minIndex, Max=arg.maxIndex))

    def _comment(self, comment):
        """ Create a comment in scope of self and append it to the code

        :param comment: Comment to transpile

        """
        self._code += [Comment(self, comment)]

    def _new_variable(self, argName, size, classical):
        """ Create a new register in scope of self and append it to the code

        :param argName: Name of register to create
        :param size:    Size of register to create
        :param classical: Whether register is Classical or Quantum

        """
        self._is_def(argName, create=True)

        if classical:
            variable = ClassicalRegister(self, argName, size)
            self._objs[argName] = variable
        else:
            variable = QuantumRegister(self, argName, size)
            self._objs[argName] = variable

        self._code += [variable]

    def _new_alias(self, argName, size):
        """ Create a new alias in scope of self

        :param argName: Name of alias to create
        :param size:    Size of alias to create

        """
        self._is_def(argName, create=True)
        alias = Alias(self, argName, size)
        self._objs[argName] = alias
        self._code += [alias]

    def _alias(self, aliasName, argIndex, referee, refIndex):
        """
        If an alias called aliasName exists: assign values to this alias
        If it does not exist:  Create it and if values assign it

        :param aliasName: Name of alias to create
        :param argIndex:  Index of alias to assign to
        :param referee:   Register to be aliased
        :param refIndex:  Index of register to be aliased
        """

        referee, refInter = self.resolve(referee, argType="QuantumRegister", index=refIndex)
        refInter = refInter[0], refInter[1]
        refSize = self.resolve_maths(refInter[1] - refInter[0] + 1)

        if self._check_def(aliasName, create=True, argType="Alias"):
            self._new_alias(aliasName, refSize)

        alias, aliasInter = self.resolve(aliasName, argType="Alias", index=argIndex)
        aliasSize = 1 + aliasInter[1] - aliasInter[0]
        if aliasSize != refSize:
            self._error(aliasIndexWarning.format(aliasName, aliasSize, refSize))

        self._code += [SetAlias(self, (alias, aliasInter), (referee, refInter))]

    def _gate(self, gateName, block,
              pargs=None, qargs=None, spargs=None, gargs=None, byprod=None,
              recursive=False, unitary=False, argType="gate"):
        """Declare a new gate-like object in current scope and append it to the code

        :param gateName: Name of gate to output
        :param block: Code block of operations
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param spargs: Input special arguments
        :param gargs: Input gate arguments
        :param byprod: Output classical bit
        :param recursive: Gate allowed to recurse
        :param unitary: Gate allowed to contain non-unitaries
        :param argType: Type of gate to return

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
        self._code += [gate]

    def _leave(self):
        """ Leave loop """
        self._error(failedOpWarning.format("exit", "non-recursive " + self.trueType))

    def _let(self, var, val):
        """ Define and set variable in scope

        :param var: Tuple of variable name, variable type
        :param val: Tuple of value, value type

        """
        varName, _ = var # Don't need varType
        value, valType = val

        val = (self.resolve(value, argType="Constant"), valType)
        if self._check_def(varName, create=True, argType="Constant"):
            letobj = Constant(self, var, val)
            self._objs[letobj.name] = letobj
        else:
            var = (self.resolve(varName, argType="Constant").name, None)
            letobj = Constant(self, var, val)
            self._objs[letobj.name] = letobj

        self._code += [Let(self, letobj)]

    def _call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, byprod=None, modifiers=()):
        """ Check gate exists, if it does, call it, else raise error

        :param gateName: Name of gate to call
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs: Input gate args
        :param spargs: Input special arguments
        :param modifiers: Modifiers on call such as invert and control

        """
        self._is_def(gateName, create=False, argType="Gate")

        pargs = self.parse_args(pargs, argType="Constant")
        qargs = self.parse_args(qargs, argType="QuantumRegister")
        gargs = self.parse_args(gargs, argType="Gate")
        spargs = self.parse_args(spargs, argType="Constant")

        if "INV" in modifiers.asList():
            # If inverse doesn't exist, make it
            if self._check_def("inv_"+gateName, create=True, argType="Gate"):
                orig = self.resolve(gateName, argType="Gate")
                orig.invert(self)
            gateName = "inv_"+gateName
        gate = CallGate(self, gateName, pargs, qargs, gargs, spargs, byprod)

        self._code += [gate]

    def _measurement(self, qarg, qindex, parg, bindex):
        """ Add measurement to code

        :param qarg: Quantum register to measure
        :param qindex: Index of quantum register to measure
        :param parg: Output classical register
        :param bindex: Index of output classical register

        """
        parg = self.resolve(parg, argType="ClassicalRegister", index=bindex)
        qarg = self.resolve(qarg, argType="QuantumRegister", index=qindex)

        measure = Measure(self, qarg, parg)

        self._code += [measure]

    def _reset(self, qarg, qindex):
        """ Reset register value

        :param qarg:
        :param qindex:

        """
        qarg = self.resolve(qarg, argType="QuantumRegister", index=qindex)
        reset = Reset(self, qarg)

        self._code += [reset]

    def _output(self, parg, bindex):
        """ Write out creg

        :param parg:
        :param bindex:

        """
        parg = self.resolve(parg, argType="ClassicalRegister", index=bindex)
        output = Output(self, parg)

        self._code += [output]

    def _loop(self, var, block, start, end, step):
        """ Add loop to code

        :param var:
        :param block: Code block of operations
        :param start:
        :param end:

        """
        loop = Loop(self, block, var, start, end, step)
        self._code += [loop]

    def _cycle(self, var):
        """ Cycle loop

        :param var:

        """
        var = self.resolve(var, argType="Constant")
        if not var.loopVar:
            self._error(failedOpWarning.format("cycle", "non-loop"))
        self._code += [Cycle(self, var)]

    def _escape(self, var):
        """ Break out of loop

        :param var:

        """
        var = self.resolve(var, argType="Constant")
        if not var.loopVar:
            self._error(failedOpWarning.format("escape", "non-loop"))
        self._code += [Escape(self, var)]

    def _end(self):
        """ End current process """
        self._code += [TheEnd(self, self)]

    def _dealloc(self, target):
        """ Free deferred objects """
        targetObj = self.resolve(target, argType="ClassicalRegister")
        if targetObj not in self._to_free:
            self._error(freeWarning.format(targetObj.name))

        self._code += [Dealloc(self, targetObj)]
        
    def _new_while(self, cond, block):
        """ Add while block

        :param cond:
        :param block: Code block of operations

        """
        self._code += [While(self, cond, block)]

    def _new_if(self, cond, block):
        """ Add if block

        :param cond:
        :param block: Code block of operations

        """
        self._code += [IfBlock(self, block, cond)]

    def _init_env(self):
        """ Add a call to initialise QuEST environment """
        self._code += [InitEnv(self)]

    def include(self, _):
        """ Raise an error if attempting to include outside of a main file """
        self._error(includeNotMainWarning)

    def classical_block(self, block):
        """ Add classical block

        :param block: Code block of operations

        """
        self._code += [CBlock(self, block)]

    def _directive(self, directive, args=None, block=None):
        """ Determine and apply directive

        :param directive: Type of directive to apply
        :param args: Arguments to the directive
        :param block: Code block of operations

        """
        if directive in ["classicallang", "classlang"]:
            if type(self).__name__ != "ProgFile":
                self._error(failedOpWarning.format("set classLang", self.trueType))
            elif self.classLang is not None:
                self._error(redefClassLangWarning.format(self.classLang))

            self.classLang = args.strip('"\'')
        elif directive == "classical":
            if block:
                self.classical_block(block)
            else:
                self.classical_block([args+";"])
        elif directive == "opaque":
            if not block:
                self._error(inlineOpaqueWarning)
            gate = args[0]
            target = self.resolve(gate, argType="Gate")
            target.set_code([CBlock(target, block)])
        elif directive == "inverse":
            if not block:
                self._error(inlineOpaqueWarning)
            gate = args[0]
            target = self.resolve(gate, argType="Gate")
            target.set_inverse(block)
        else:
            self._error(badDirectiveWarning.format(directive))

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
            self.include(token["file"])

        # Functions and gates
        elif keyword == "call":
            gateName = token["gate"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            gargs = token.get("gargs", [])
            byprod = token.get("byprod", None)
            mods = token.get("mods", [])

            self._call_gate(gateName, pargs, qargs, gargs, spargs, byprod, modifiers=mods)
        elif keyword == "measure":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            parg = token["creg"]["var"]
            bindex = token["creg"].get("ref", None)
            self._measurement(qarg, qindex, parg, bindex)
        elif keyword == "reset":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            self._reset(qarg, qindex)
        elif keyword == "output":
            parg = token["value"]["var"]
            bindex = token["value"].get("ref", None)
            self._output(parg, bindex)
        elif keyword == "if":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token["block"])
            self._new_if(cond, block)

        # Directives
        elif keyword == "directive":
            directive = token["directive"]
            args = token.get("args", None)
            block = token.get("block", None)
            self._directive(directive, args, block)
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
            self._new_variable(argName, size, True)
        elif keyword in ["qbit", "qreg"]:

            argName = token["arg"]["var"]
            size = token["arg"].get("ref")
            if size is None:
                size = {"index": 1}
            else:
                size = token["arg"]["ref"]
            size = self.parse_range(size)
            self._new_variable(argName, size, False)
        elif keyword == "val":
            var = token["var"]
            val = token["val"]
            argType = token["type"]
            self._let((var, argType), (val, None))
        elif keyword == "defAlias":
            name = token["alias"]["var"]
            index = self.parse_range(token["alias"]["ref"])
            self._new_alias(name, index)
        elif keyword == "alias":
            name = token["alias"]["var"]
            index = token["alias"].get("ref", None)
            qarg = token["target"]["var"]
            qindex = token["target"].get("ref", None)
            self._alias(name, index, qarg, qindex)

        # Loop routines
        elif keyword == "for":
            var = token["var"]
            start, end, interval = self.parse_range(token["range"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self._loop(var, block, start, end, step=interval) # Handle "<" ending one early
        elif keyword == "while":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self._new_while(block, cond)
        elif keyword == "next":
            var = token["loopVar"]
            self._cycle(var)
        elif keyword == "escape":
            var = token["loopVar"]
            self._escape(var)
        elif keyword == "exit":
            self._leave()

        elif keyword == "end":
            var = token["process"]
            self._end()

        # Gate declaration routines
        elif keyword == "gate":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self._gate(gateName, block, pargs, qargs, unitary=unitary, recursive=recursive)

        elif keyword == "circuit":
            gateName = token["gateName"]
            pargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            spargs = token.get("spargs", [])
            byprod = token.get("byprod", [])
            unitary = token.get("unitary", False)
            recursive = token.get("recursive", False)
            block = QASMBlock(self.currentFile, token.get("block", None))
            self._gate(gateName, block,
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
            self._gate(**gateInfo)


        # Whole line comment
        elif keyword is None:
            self._comment(comment)
        else:
            self._error(instructionWarning.format(keyword,
                                                  self.currentFile.QASMType,
                                                  self.currentFile.versionNumber))

        if not self._code:
            self._code.append(Comment(self, ""))
        lastLine = self._code[-1]
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
                args.append(self.resolve(arg["var"], argType, arg.get("ref", None)))
        elif argType in ["Constant"]:
            for arg in argsIn:
                args.append(self.resolve(arg, argType))
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
                        interval = (0, arg.size+"-1")
                elif isinstance(arg.size, MathsBlock):
                    return (0, arg.size-1)
                else:
                    self._error(failedOpWarning.format("determine arg size", "parse_range"))
            else:
                self._error(loopSpecWarning.format("start or end"))

        elif "index" in rangeSpec:
            point = rangeSpec.get("index", None)
            if isinstance(point, ParseResults):
                point = point.get("var", point)
            point = self.resolve(point, argType="Constant")
            interval = (point, point)
            self._check_bounds(interval, arg)

        elif "start" in rangeSpec or "end" in rangeSpec:
            if indexOnly:
                self._error(rangeToIndexWarning)
            start, end = rangeSpec.get("start", None), rangeSpec.get("end", None)

            start = self.resolve(start, argType="Constant")
            end = self.resolve(end, argType="Constant")

            if arg:
                if not start:
                    start = 0
                if not end:
                    end = arg.size
            else:
                if start is None or end is None:
                    self._error(loopSpecWarning.format("end" if end is None else "start"))

            if "step" in rangeSpec:
                step = rangeSpec["step"]
                step = self.resolve(step, argType="Constant")
                interval = (start, end, step)
            else:
                interval = (start, end)

            self._check_bounds(interval, arg)

        else:
            self._error(rangeSpecWarning.format(rangeSpec))

        return interval

    def parse_maths(self, maths):
        """ Parse maths into maths block

        :param maths:

        """
        return MathsBlock(self, maths, topLevel=True)

class SubBlock(CodeBlock):
    """ Extending type to inherit overwritten core functions with those of the parent """
    def __init__(self, parent, block, copyObjs=True):
        CodeBlock.__init__(self, parent, block, copyObjs)


# Maths Parsing

class MathsBlock(CoreOp):
    """ Block for handling maths as returned from the parser """

    def __init__(self, parent, maths, topLevel=False):
        """Initialise a maths block

        :param parent: Parent block defining object
        :param maths:
        :param topLevel:
        :returns:
        :rtype:

        """
        CoreOp.__init__(self, parent)
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
                    operand = parent.resolve(operand, argType="Maths")
                    newArgs.append((operator, operand))
            elem.args = newArgs
        elif isinstance(elem, Function):
            newArgs = []
            for arg in elem.args:
                if issubclass(type(arg), MathOp):
                    arg = MathsBlock(parent, arg)
                    newArgs.append(arg)
                else:
                    arg = parent.resolve(arg, argType="Maths")
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


# Variable types

class Constant(Referencable):
    """ Class pertaining to a constant value or variable object """

    def __init__(self, parent, var, val):
        """Initialise constant

        :param parent: Parent block defining object
        :param var: Variable to assign to
        :param val: Value to assign
        """
        Referencable.__init__(self, parent, var[0])
        self.varType = var[1]
        self.val = val[0]
        self.cast = val[1]
        self.loopVar = False

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
        Referencable.__init__(self, parent, name)

        self._size = self.render_size(size)

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
            self._minIndex = start
            self._maxIndex = end
            self._start = 0
            self._end = size

        else:
            size = inter
            self._minIndex = 0
            self._maxIndex = size
            self._start, self._end = self.minIndex, self.maxIndex

        return size

    minIndex = property(lambda self: self._minIndex)
    maxIndex = property(lambda self: self._maxIndex)
    start = property(lambda self: self._start)
    end = property(lambda self: self._end)
    size = property(lambda self: self._size)

class TensorNetwork(Register):
    """ Tensor network of register nodes """
    nQubits = property(lambda self: self._nQubits)
    physicalQubits = property(lambda self: self._physicalQubits)
    virtualQubits = property(lambda self: self._virtualQubits)

    def __init__(self, parent, name, physicalQubits, virtualQubits):
        self._nQubits = sum(physicalQubits) + sum(virtualQubits)
        self._physicalQubits = physicalQubits
        self._virtualQubits = virtualQubits

        Register.__init__(self, parent, name, self.nQubits)
        self._argType = "QuantumRegister"

class QuantumRegister(Register):
    """
    Quantum register as created by "qreg"

    :param parent: Parent block defining object
    :param name: Reference name of the object
    :param inter: Range of bits
    """
    numQubits = 0

    def __init__(self, parent, name, inter):
        """Initialise a quantum register
        """
        Register.__init__(self, parent, name, inter)

        self._start += QuantumRegister.numQubits
        self._end += QuantumRegister.numQubits
        self._mapping = tuple(range(self._start, self._end))
        QuantumRegister.numQubits += self.size

    @property
    def mapping(self):
        return self._mapping

    @mapping.setter
    def mapping(self, val):
        if len(val) != self.size:
            raise ValueError(badMappingWarning.format(self.name, len(val), val, self.size))
        self._mapping = val
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

        self._start = 0
        self._end = self.size

class DeferredClassicalRegister(ClassicalRegister):
    """
    Classical register whose size is unknown until execution of the code,
    e.g. size is a function variable

    :param parent: Parent block defining object
    :param name: Reference name of the object
    :param size: Size of register to initialise
    """
    def __init__(self, parent, name, size):
        """Initialise a deferred classical register
        """
        ClassicalRegister.__init__(self, parent, name, size)
        self._end -= 1
        self._argType = "ClassicalRegister"

class Alias(Register):
    """
    Alias as specified in REQASM
    """

    def __init__(self, parent, name, inter):
        """Initialise an alias

        :param parent: Parent block defining object
        :param name: Reference name of the object
        :param inter: Range of bits
        """
        Register.__init__(self, parent, name, inter)
        self.allSet = False
        self.targets = [(None, None)]*self.size

    def set_target(self, indices, target, interval):
        """ Aliases target to indices

        :param indices:
        :param target:
        :param interval:

        """
        for index in range(indices[0], indices[1]+1):
            self.targets[index - self.minIndex] = (target, interval[0] + index)

        self.allSet = all(target != (None, None) for target in self.targets)

class DeferredAlias(Alias):
    """
    Alias whose size is unknown until execution of the code,
    e.g. size is a function variable

    :param parent: Parent block defining object
    :param name: Reference name of the object
    :param size: Size of register to initialise
    """
    def __init__(self, parent, name, inter):
        """ Initialise a deferred alias """
        Register.__init__(self, parent, name, inter)
        self.allSet = False
        self.targets = []
        self._argType = "Alias"

    def set_target(self, indices, target, interval):
        """ Aliases target to indices

        :param indices:
        :param target:
        :param interval:

        """
        for index in range(indices[0], indices[1]+1):
            if index - self.minIndex > len(self.targets) - 1:
                self.targets += [(None, None)] * (len(self.targets) + 1 - index + self.minIndex)
            self.targets[index - self.minIndex] = (target, interval[0] + index)

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
        self._argType = "QuantumRegister"
        self._start = name
        self._end = self.size


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

class Comment(CoreOp):
    """ Add comment to code """
    def __init__(self, parent, comment):
        """Initialise a comment

        :param parent: Parent block defining object
        :param comment:
        :returns:
        :rtype:

        """
        self._parent = parent
        self._name = comment
        self.comment = comment

    to_lang = to_lang_error

class Let(CoreOp):
    """ Set a variable """
    def __init__(self, parent, var, val=None):
        """Initialise a let

        :param parent: Parent block defining object
        :param var: Variable to assign to
        :param val: Value to assign
        """
        CoreOp.__init__(self, parent)

        if isinstance(var, Constant):
            self.const = var
        elif isinstance(var, (tuple, list)):
            self.const = Constant(self.parent, var, val)
        else:
            raise TypeError(failedOpWarning.format("assign " + var.trueType, "let"))

class CallGate(Operation):
    """ Call a gate """
    name = property(lambda self: self._name)

    def __init__(self, parent, gate, pargs, qargs, gargs, spargs, byprod):
        """Initialise a call to a gate

        :param parent: Parent block defining object
        :param gate:  Name of gate to be called
        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs: Input gate arguments
        :param spargs: Input special arguments
        """
        Operation.__init__(self, parent, qargs, pargs, gargs, spargs)
        self._byprod = byprod
        self._name = gate

        self.resolvedQargs = None

        self.callee = self.parent.resolve(self.name, argType="Gate")

        self._check_args(pargs, qargs, gargs, spargs, byprod)

        self.handle_loops(self.qargs)

    byprod = property(lambda self: self._byprod)

    def _check_args(self, pargs, qargs, gargs, spargs, byprod):
        """ Check gate arguments are valid and of the right size. Raise error if not

        :param pargs: Input parameter arguments
        :param qargs: Input quantum arguments Input quantum arguments
        :param gargs:
        :param spargs: Input special arguments

        """
          # Check number of args matches
        for name, args, expect in [("pargs", pargs, self.callee.pargs),
                                   ("gargs", gargs, self.callee.gargs),
                                   ("spargs", spargs, self.callee.spargs)]:
            if len(args) != len(expect):
                place = "call to {}".format(self.name)
                expect = "{} {}".format(len(expect), name)
                received = len(args)
                self._error(argWarning.format(place, expect, received))

        newSpargs = {sparg.name: spargs[i] for i, sparg in enumerate(self.callee.spargs)}
        newQargs = []

        for sparg in spargs: # Disambiguate?
            if sparg in self.parent.spargs:
                newSpargs[sparg.name] = 0


        for qarg in self.callee.qargs:
            newQargs.append([qarg, int(self.parent.resolve_maths(qarg.size, additionalVars=newSpargs))])

        self.resolvedQargs = newQargs

        if self.callee.byprod:
            resolvedByprod = self.parent.resolve(byprod, "ClassicalRegister")
            received = int(self.parent.resolve_maths(resolvedByprod.size, additionalVars=newSpargs))
            expect = int(self.parent.resolve_maths(self.callee.byprod.size, additionalVars=newSpargs))
            if received != expect:
                place = "call to {}".format(self.name)
                expect = "{} {}".format(expect, "return")
                self._error(argWarning.format(place, expect, received))

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
                self._error(argWarning.format(place, expect, received))
            elif nArg // expect != self.nLoops:
                place = "call to {} in qarg {} for implicit {} loops".format(self.name, index+1, self.nLoops)
                expect = "{} qubits".format(self.nLoops*expect)
                received = nArg
                self._error(argWarning.format(place, expect, received))

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
            raise NotImplementedError(failedOpWarning.format("use loop step > 1", "implicit loop"))

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
    """ Measure a qubit and assign to a classical register

    :param parent: Parent block defining object
    :param qarg: Quantum register to measure
    :param parg: Classical register to measure
    """
    def __init__(self, parent, qarg, parg):
        """ Initialise a measure operation  """
        Operation.__init__(self, parent, qarg, parg)
        self.handle_loops([self.pargs, self.qargs])
        parg, bindex = self.pargs
        qarg, _ = self.qargs

        # Check bindices
        if bindex is None:
            if parg.size < qarg.size:
                raise IOError(
                    (argSizeWarning + indexWarning).format(Req=qarg.size, Var=parg.name,
                                                           Var2=qarg.name, Max=parg.size))
            if parg.size > qarg.size:
                raise IOError(
                    (argSizeWarning + indexWarning).format(Req=parg.size, Var=qarg.name,
                                                           Var2=parg.name, Max=qarg.size))
            self.pargs[1] = self.qargs[1]
        self._finalise_loops()

class Reset(Operation):
    """ Reset a quantum register to the zero state

    :param parent: Parent block defining object
    :param qarg: Argument to reset
    """
    def __init__(self, parent, qarg):
        """Initialise a reset """
        Operation.__init__(self, parent, qarg)
        self.handle_loops([self.qargs])

class Output(Operation):
    """ Write a classical register to screen """
    def __init__(self, parent, parg):
        """Initialise an output statement

        :param parent: Parent block defining object
        :param parg: Register to be written

        """
        Operation.__init__(self, parent, pargs=parg)
        self.handle_loops([self.pargs])

class EntryExit(CoreOp):
    """ Exit recursive routine

    :param parent: Parent block defining object

    """
    def __init__(self, parent):
        """ Initialise entry-exit construct """
        CoreOp.__init__(self, parent)
        self.depth = 1

    def exited(self):
        """ Depth is defined """
        self.depth = 0

class Gate(Referencable, CodeBlock):
    """
    Type to handle general general gates and their extensions (circuit, procedure, etc.)

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
    """
    internalGates = {}

    def __init__(self, parent, name, block,
                 pargs=(), qargs=(), spargs=(), gargs=(), byprod=(),
                 recursive=False, unitary=False, returnType=None):
        """Initialises the gate object """
        CodeBlock.__init__(self, parent, block)
        Referencable.__init__(self, parent, name)

        # Gates are, by definition, unitary
        if isinstance(self, Gate):
            self.unitary = True
        else:
            self.unitary = unitary

        self._inverse = None
        self._control = None

        if recursive:
            self._gate(name, NullBlock(block), pargs, qargs, unitary=unitary)
            self._code = []
            self.entry = EntryExit(self.name)
        else:
            self.entry = None

        self.spargs = spargs
        self.qargs = qargs
        self.pargs = pargs
        self.gargs = gargs
        # List of vars declared only in scope

        self.parse_instructions()

        # Free those vars
        self._code += [Dealloc(self, freeable) for freeable in self._to_free if freeable != byprod]

        if not byprod:
            self.byprod = None
            self.returnType = None
        else:
            # Catches undefined returns
            self.byprod = self.resolve(byprod, "ClassicalRegister")

            self._code.append(Return(self, self.byprod))

            if self.byprod.size == 1:
                self.returnType = "int"
            else:
                self.returnType = "listint"

        if returnType is not None:
            self.returnType = returnType

        if recursive and self.entry.depth > 0:
            self._error(noExitWarning.format(self.name))

    def invert(self, parent):
        """Calculates the inverse of the gate and called gates and assigns it to self._inverse """
        if not self.unitary:
            self._error(failedOpWarning.format("invert", "non unitary "+self.trueType))

        if self._inverse:
            return self._inverse

        inverse = copy.copy(self)
        inverse._name = "inv_"+self.name
        inverse._code = []

        for line in reversed(self.code):
            if isinstance(line, CallGate):
                gateName = line.name
                if parent._check_def("inv_"+gateName, create=True, argType="Gate"):
                    gate = parent.resolve(gateName, argType="Gate")
                    gate.invert(parent)
                line.qargs[0][1] = (0, 0)
                inverse._code.append(CallGate(self, "inv_"+gateName, line.pargs, line.qargs, line.gargs, line.spargs))

            else:
                self._error(failedOpWarning.format("invert "+line.name, self.name + " invert"))

        self._inverse = inverse
        parent._code += [inverse]
        parent._objs[inverse.name] = inverse
        return self._inverse

    def qargs_setter(self, args):
        """ Parse qargs and assign as arguments """
        for argTok in args:
            arg = argTok["var"]
            size = argTok.get("ref", {"index":1})
            if size is not None:
                size = self.parse_range(size)
            self._objs[arg] = Argument(self, arg, size)
            self.qargs.append(self._objs[arg])

    def pargs_setter(self, args):
        """ Parse pargs and set as floats """
        for arg in args:
            self._objs[arg] = Constant(self, (arg, "float"), (MathsBlock(self, arg), None))
            self.pargs.append(self._objs[arg])

    def spargs_setter(self, args):
        """ Parse spargs and set as ints """
        for arg in args:
            self._objs[arg] = Constant(self, (arg, "int"), (MathsBlock(self, arg), None))
            self.spargs.append(self._objs[arg])

    def gargs_setter(self, args):
        """ Parse gargs and add to space """
        for arg in args:
            self._gate(arg, NullBlock(self), unitary=self.unitary)

    def _new_variable(self, argName, size, classical):
        if not classical:
            self._error(failedOpWarning.format("declare carg", self.trueType))
        else:
            self._error(failedOpWarning.format("declare qarg", self.trueType))

    def _call_gate(self, gateName, pargs, qargs, gargs=None, spargs=None, byprod=None, modifiers=()):
        self._is_def(gateName, create=False, argType="Gate")
        # Perform unitary checks
        if self.unitary and not self._objs[gateName].unitary:
            self._error(failedOpWarning.format("call non-unitary gate " + gateName, "unitary gate " + self.name))

        CodeBlock._call_gate(self, gateName, pargs, qargs, gargs, spargs, byprod, modifiers)

    def _measurement(self, qarg, qindex, parg, bindex):
        self._error(failedOpWarning.format("measure", self.trueType))

    def _new_alias(self, argName, size):
        """ Create a new alias in scope of self

        :param argName: Name of alias to create
        :param size:    Size of alias to create

        """
        self._is_def(argName, create=True)
        alias = DeferredAlias(self, argName, size)
        self._objs[argName] = alias
        self._code += [alias]
        self._to_free += [self]

    def _alias(self, aliasName, argIndex, referee, refIndex):
        """
        If an alias called aliasName exists: assign values to this alias
        If it does not exist:  Create it and if values assign it

        :param aliasName: Name of alias to create
        :param argIndex:  Index of alias to assign to
        :param referee:   Register to be aliased
        :param refIndex:  Index of register to be aliased
        """
        referee, refInter = self.resolve(referee, argType="QuantumRegister", index=refIndex)
        refInter = refInter[0], refInter[1]
        refSize = self.resolve_maths(refInter[1] - refInter[0] + 1)
        if self._check_def(aliasName, create=True, argType="Alias"):
            self._new_alias(aliasName, refSize)

        alias, aliasInter = self.resolve(aliasName, argType="Alias", index=argIndex)

        self._code += [SetAlias(self, (alias, aliasInter), (referee, refInter))]

    def _leave(self):
        """ Leave loop """
        if self.entry is not None:
            self.entry.exited()
        else:
            self._error(failedOpWarning.format("exit", "non-recursive "+self.trueType))

    qargs = property(lambda self: self._qargs, qargs_setter)
    pargs = property(lambda self: self._pargs, pargs_setter)
    spargs = property(lambda self: self._spargs, spargs_setter)
    gargs = property(lambda self: self._gargs, gargs_setter)
    inverse = property(lambda self: self._inverse)
    control = property(lambda self: self._control)

class Circuit(Gate):
    """
    Type reflecting REQASM extension to gate
    """

    def __init__(self, *args, **kwargs):
        Gate.__init__(self, *args, **kwargs)
        self._argType = "Gate"

    def _new_variable(self, argName, size, classical):
        """ Override new variable of gate to allow classical variables """
        self._is_def(argName, create=True)

        if classical:
            variable = DeferredClassicalRegister(self, argName, size)
            self._to_free += [self]
            self._objs[argName] = variable
        else:
            self._error(gateDeclareWarning.format("qarg", type(self).__name__))

        self._code += [variable]

    _measurement = CodeBlock._measurement

class Procedure(Circuit):
    """ Defines a circuit as according to REQASM """
    def __init__(self, *args, **kwargs):
        Circuit.__init__(self, *args, **kwargs)
        self._argType = "Procedure"

class Opaque(Gate):
    """
    Type reflecting OpenQASM opaque gate
    Allows the definition of a block through directive extensions
    """
    def __init__(self, parent, name,
                 pargs=(), qargs=(), spargs=(), gargs=(), byprod=None,
                 recursive=False, unitary=False, returnType=None):
        self.parentFile = parent.currentFile
        Gate.__init__(self, parent, name, NullBlock(self.parentFile),
                      pargs, qargs, spargs, gargs, byprod,
                      recursive, unitary, returnType)
        self._argType = "Gate"

        self._inverse = None

    def set_block(self, block):
        """ Set the block of the opaque gate """
        CodeBlock.__init__(self, self.parent, block)
        self.parse_instructions()

    def set_code(self, code):
        """ Set the code of the opaque block directly """
        self._code = code

    def set_inverse(self, block):
        """ Set the inverse of the opaque gate """
        self._inverse = block

    def set_control(self, block):
        """ Set the control of the opaque gate """
        self._control = block

class Dealloc(Operation):
    """ Deallocate assigned memory """
    def __init__(self, parent, targ):
        Operation.__init__(self, parent, pargs=targ)

class CBlock(CoreOp):
    """ Classical block """
    def __init__(self, parent, block):
        CoreOp.__init__(self, parent)
        self.block = block

class While(SubBlock):
    """ Define a while loop

    :param parent: Parent block defining object
    :param block: Code block of operations
    :param cond: Condition of if statement
    """
    def __init__(self, parent, block, cond):
        """Initalise a while construct """
        self.cond = cond
        SubBlock.__init__(self, parent, block)
        self.parse_instructions()

class IfBlock(SubBlock):
    """ Define an if statement
    :param parent: Parent block defining object
    :param block: Code block of operations
    :param cond: Condition of if statement

    """
    def __init__(self, parent, block, cond):
        """Initialise an if construct """
        self.cond = cond
        SubBlock.__init__(self, parent, block)
        self.parse_instructions()

class Loop(SubBlock):
    """ Loop structure """
    def __init__(self, parent, block, var, start, end, step=None):
        SubBlock.__init__(self, parent, block)

        self._objs[var] = Constant(self, (var, "int"), (0, None)) # Value is 0 for disambiguating resolution
        self._objs[var].loopVar = True
        self.loopVar = self._objs[var]
        self._name = var+"_loop"
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
        self._code = [block]
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

    def finalise(self):
        """ Dereference nested references to self to avoid infinite nesting """
#        self._code = [# copy.copy(self)
#        ]
        self._code[0].loops = []


class InitEnv(CoreOp):
    """ Initialise QuESTEnv """
    def __init__(self, parent):
        CoreOp.__init__(self, parent)

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
        CoreOp.__init__(self, parent)
        self._filename = filename
        self._code = [line for line in code if not isinstance(line, Comment)] # Filter mainprog comments
    raw_code = property(lambda self: self._code)
    filename = property(lambda self: self._filename)

    def set_import(self, filename):
        self._filename = filename

class Cycle(CoreOp):
    """ Jump to end of loop """
    def __init__(self, parent, var):
        CoreOp.__init__(self, parent)
        self.var = var

class Escape(CoreOp):
    """ Break out of loop """
    def __init__(self, parent, var):
        CoreOp.__init__(self, parent)
        self.var = var

class TheEnd(CoreOp):
    """ Kill running process """
    def __init__(self, parent, process):
        CoreOp.__init__(self, parent)
        self.process = process
