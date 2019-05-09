from .QASMErrors import *
from .QASMTokens import *
from .FileHandle import QASMFile, QASMBlock, NullBlock
import re
import copy

isInt  = re.compile("[+-]?(\d+)(?:[eE][+-]?\d+)?")
isReal = re.compile("[+-]?(\d*\.\d+|\d+\.\d*)(?:[eE][+-]?\d+)?")

# Core types
class Operation:
    def __init__(self, qargs = None, cargs = None):
        self._loops = None
        self._qargs = qargs
        self._cargs = cargs

    def add_loop(self, index, start, end):
        if self._loops:
            self._loops = NestLoop(self._loops, index, start, end)
        else:
            self.innermost = NestLoop(copy.copy(self), index, start, end)
            self._loops = self.innermost

    def finalise_loops(self):
        if self._loops:
            self.innermost._code = [copy.copy(self)]
            self.innermost._code[0]._loops = []
        else:
            pass

    def handle_loops(self, pargs, slice = None):
        for parg in pargs:
            if isinstance(parg[1], tuple):
                start, end = parg[1]
                if isinstance(start, int): start -= parg[0].start
                if isinstance(end, int): end -= parg[0].start
                if start == end :
                    parg[1] = start
                else:
                    parg[1] = parg[0].name + "_index"
                    start = self.resolve_arg( (parg[0], start) )
                    end = self.resolve_arg( (parg[0], end + 1) )
                    self.add_loop(parg[1], start, end)

    def resolve_arg(self, arg):

        if type(arg[0]) is Argument:
            return str(arg[1])
        elif issubclass(type(arg[0]),Register):
            start = arg[1]
            offset = arg[0].start
            if isinstance(start, int):
                return str(offset + start)
            elif isinstance(start, Constant):
                return str(offset + arg[1].val)
            elif isinstance(start, str):
                if (offset > 0): return f"{start} + {arg[0].start}"
                else: return f"{start}"
            else:
                return arg[1]
        else:
            raise TypeError(parseArgWarning.format("arg", type(arg[0]).__name__))

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Referencable:
    def __init__(self):
        self.type_ = type(self).__name__

class CodeBlock:
    def __init__(self, block, parent, copyObjs = True, copyFuncs = True):
        self._code = []
        self._qargs= []
        self._cargs= []
        if copyObjs:
            self._objs = copy.copy(parent._objs)
        else:
            self._objs = {}
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile._error
        QASMType = self.currentFile.QASMType
        if QASMType not in ["OPENQASM", "REQASM"]:
            self._error(QASMWarning.format(QASMType))

    def _resolve(self, var, type_, index = ""):
        if type_ in ["ClassicalRegister","QuantumRegister"]:

            self._is_def(var, create=False, type_ = type_)
            var = self._objs[var]

            if isinstance(var,Argument):

                return [var, var.name + "_index"]

            elif index or index is None: # If index or implicit loop

                index = self.parse_range(index, var)

                return [var, index]

        elif type_ == "Constant":
            if var is None:
                return None
            elif isinstance(var, int) or isinstance(var, float):
                return var
            elif isinstance(var,str) and re.fullmatch(isInt, var):
                var = float(var)
                return int(var)
            elif isinstance(var,str) and re.fullmatch(isReal, var):
                return float(var)
            elif isinstance(var, ParseResults):
                return self.parse_maths(var)
            else:
                self._is_def(var, create=False, type_ = type_)
                return self._objs[var].name

        elif type_ == "Maths":
            
            if var is None:
                return None
            elif isinstance(var, int) or isinstance(var, float):
                return var
            elif isinstance(var,str) and re.fullmatch(isInt, var):
                return int(var)
            elif isinstance(var,str) and re.fullmatch(isReal, var):
                return float(var)
            elif isinstance(var, ParseResults):
                return self.parse_maths(var)
            else:
                self._is_def(var, create=False, type_ = None)
                var = self._objs[var]

                if isinstance(var,Argument):
                    
                    return [var, var.name + "_index"]

                elif isinstance(var,Constant):

                    if var.val:
                        return var.val
                    else: # Is argument or not set yet
                        return var.name

                elif isinstance(var, ClassicalRegister):
                    
                    if index or index is None: # If index or implicit loop

                        index = self.parse_range(index, var)
                        
                        return [var, index]
                    else:
                        return [var, None]
                else:
                    self._error("Undetermined type in maths parsing")

        elif type_ == "Gate":
            self._is_def(var, create=False, type_ = type_)
            # Add argument checking?
            return self._objs[var]

    def _is_def(self, name, create, type_ = None):

        if create: # Check for duplicate naming
            if name in self._objs: self._error(dupWarning.format(Name=name, Type=self._objs[name].type_))

        else: # Check exists and type is right
            if name not in self._objs:
                self._error(existWarning.format(Type=type_, Name=name))
            elif type_ is None: pass
            elif self._objs[name].type_ is not type_:
                self._error(wrongTypeWarning.format(type_,self._objs[name].type_))

    def _check_bounds(self,interval, arg = None):
        if arg is None: return
        if isinstance(interval[0],int) and interval[0] < 0:
            self._error(indexWarning.format(Req=interval[0], Var = arg.name, Max = arg.size))
        elif isinstance(interval[1],int) and interval[1] > arg.size:
            self._error(indexWarning.format(Req=interval[1], Var = arg.name, Max = arg.size))

    def comment(self, comment):
        self._code += [Comment(comment)]

    def new_variable(self, argName, size, classical):
        self._is_def(argName, create=True)

        if classical:
            variable = ClassicalRegister(argName, size)
            self._objs[argName] = variable
        else:
            variable = QuantumRegister(argName, size)
            self._objs[argName] = variable

        self._code += [variable]

    def alias(self, argName, argIndex, referee, refIndex):
        self._is_def(argName, create=True)
        referee, interval = self._resolve(referee, type_="QuantumRegister", index = refIndex)
        alias = Alias(argName, referee, interval)

        self._objs[argName] = alias

    def gate(self, funcName, cargs, qargs, block, recursive = False, opaque = False):
        self._is_def(funcName, create=True)

        if not opaque:
            gate = Gate(self, funcName, cargs, qargs, block, recursive)
        else:
            gate = Opaque(self, funcName, cargs, qargs, block)

        self._objs[gate.name] = gate
        self._code += [gate]

    def let(self, var, val):
        self._is_def(var, create=True)
        val = (self._resolve(val[0], type_="Constant"), val[1])
        letobj = Constant( var, val )
        self._objs[letobj.name] = letobj
        self._code += [Let( letobj )]
    def call_gate(self, funcName, cargs, qargs, gargs=None, spargs=None):
        self._is_def(funcName, create=False, type_ = "Gate")
        cargs = self.parse_args(cargs, type_ = "Constant")
        qargs = self.parse_args(qargs, type_ = "QuantumRegister")
        gargs = self.parse_args(gargs, type_ = "Gate")
        spargs = self.parse_args(spargs, type_ = "Constant")

        if funcName in Gate.internalGates:
            gateRef = Gate.internalGates[funcName]
            gate = CallGate(gateRef.internalName, cargs, qargs)
            preCode, outCargs = gateRef.reorder_args(gate._qargs,gate._cargs)
            gate._qargs = []
            gate._cargs = outCargs
            if preCode:
                self._code += preCode
            gate.finalise_loops()
        else:
            gate = CallGate(funcName, cargs, qargs)

        self._code += [gate]

    def measurement(self, qarg, qindex, carg, bindex):
        carg = self._resolve(carg, type_ = "ClassicalRegister", index=bindex)
        qarg = self._resolve(qarg, type_ = "QuantumRegister", index=qindex)

        measure = Measure( qarg, carg )

        self._code += [measure]

    def leave(self):
        if hasattr(self, "entry"):
            self.entry.exited()
        else:
            self._error("Cannot exit from a non-recursive gate")

    def reset(self, qarg, qindex):
        qarg = self._resolve(qarg, type_="QuantumRegister", index=qindex)
        reset = Reset( qarg )

        self._code += [reset]

    def output(self, carg, bindex):
        carg = self._resolve(carg, type_="ClassicalRegister", index=bindex)
        output = Output ( carg )

        self._code += [output]

    def loop(self, var, block, start, end):
        loop = Loop(self,block, var, start, end)
        self._code += [loop]

    def new_while(self, cond, block):
        self._code += [While(self, cond, block)]
        
    def new_if(self, cond, block):
        self._code += [IfBlock(self, cond, block)]

    def cBlock(self, block):
        self._code += [CBlock(self,block)]

    def directive(self, directive, args = None, block = None):
        if directive == "ClassLang":
            if type(self).__name__ is not "ProgFile" : self._error("Cannot set classical language outside of main code")
            if hasattr(self, "classLang") : self._error("Classical language already defined as {}".format(self.classLang))
            self.classLang = args.strip('"\'')
        elif directive == "classical":
            if block:
                self.cBlock(block)
            else:
                self.cBlock([args+";"])
        elif directive == "opaque":
            if not block: self._error("Cannot set opaque by inline directive")
            gate = args[0]
            if self._objs[gate]:
                target = self._objs[gate]
                target.cBlock(block)
            else:
                self._error("Cannot find opaque {}".format(gate))
        else:
            self._error("Unrecognised directive: {}".format(directive))

    def parse_line(self, token, line):
        non_code = ["alias","exit","comment","barrier","directive"]
        
        keyword = token.get("keyword", None)
        comment = token.get("comment", "")
        if keyword == "include":
            if hasattr(self,"include"):
                self.include(token["file"])
            else:
                self._error(includeNotMain)
        elif keyword == "creg": # Registers NEED index, not range, must dereference ref.
            argName = token["arg"]["var"]
            size = int(token["arg"]["ref"].get("index",1))
            self.new_variable(argName, size, True)
        elif keyword == "qreg":
            argName = token["arg"]["var"]
            size = int(token["arg"]["ref"].get("index",1))
            self.new_variable(argName, size, False)
        elif keyword == "call":
            funcName = token["gate"]
            cargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            self.call_gate(funcName, cargs, qargs)
        elif keyword == "gate":
            funcName = token["gateName"]
            cargs = token.get("pargs", [])
            qargs = token.get("qargs", [])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(funcName, cargs, qargs, block)
        elif keyword == "createRGate":
            funcName = match.group("funcName")
            cargs = match.group("cargs")
            qargs = match.group("qargs")
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.gate(funcName, cargs, qargs, block, recursive = True)
        elif keyword == "opaque":
            funcName = token.get("name")
            cargs = token.get("cargs", [])
            qargs = token.get("qargs", [])
            self.gate(funcName, cargs, qargs, None, opaque = True)
        elif keyword == "measure":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            carg = token["creg"]["var"]
            bindex = token["creg"].get("ref", None)
            self.measurement(qarg, qindex, carg, bindex)
        elif keyword == "if":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token["block"])
            self.new_if(cond, block)
        elif keyword == "barrier":
            pass
        elif keyword == "reset":
            qarg = token["qreg"]["var"]
            qindex = token["qreg"].get("ref", None)
            self.reset(qarg, qindex)
        elif keyword == "for":
            var = token["var"]
            start, end = self.parse_range(token["range"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.loop(var, block, start, end)
        elif keyword == "while":
            cond = self.parse_maths(token["cond"])
            block = QASMBlock(self.currentFile, token.get("block", None))
            self.new_while(block, cond)
        elif keyword == "let":
            var = token["var"]
            val = token["val"]
            type_ = token["type"]
            self.let( (var, type_), (val, None) )
        elif keyword == "exit":
            self.leave()
        elif keyword == "alias":
            name = token["alias"]["var"]
            index = token["alias"].get("ref", None)
            qarg = token["target"]["var"]
            qindex = token["target"].get("ref", None)
            self.alias(name, index, qarg, qindex)
        elif keyword == "output":
            carg = token["value"]["var"]
            bindex = token["value"].get("ref", None)
            self.output(carg, bindex)
        elif keyword == "directive":
            directive = token["directive"]
            args = token.get("args", None)
            block = token.get("block", None)
            self.directive(directive, args, block)
        elif keyword is None:
            self.comment(comment)
        else:
            self._error(instructionWarning.format(keyword, self.currentFile.QASMType))

        lastLine = self._code[-1]
        if line:
            if not hasattr(lastLine,"original") or keyword not in non_code: lastLine.original = line.strip()
            elif keyword in non_code: lastLine.original += "\n"+line.strip()
        if keyword is not None and comment is not "": lastLine.inlineComment = Comment(comment)

    def parse_args(self, args_in, type_):
        if not args_in: return []

        args = []

        if type_ in ["ClassicalRegister", "QuantumRegister"]:
            for arg in args_in:
                args.append(self._resolve(arg["var"], type_, arg.get("ref",None)))
        elif type_ in ["Constant"]:
            args_in = args_in[0]
            for arg in args_in:
                args.append(self._resolve(arg, type_))
        else:
            self._error("Cannot parse args of type {}".format(type_))

        return args
    def parse_instructions(self):
        for instruction in self.instructions:
            self.parse_line(instruction, instruction.original)

    def parse_range(self, rangeSpec, arg = None):

        if rangeSpec is None:
            if arg:
                if arg.size is None: interval = ( None, None )
                else: interval = ( 0, arg.size-1 )
            else:
                self._error(loopSpecWarning.format("start or end"))

        elif rangeSpec.get("index", None) is not None:
            point = rangeSpec.get("index", None)
            if isinstance(point, ParseResults): point = point.get("var", point)
            point = self._resolve(point, type_ = "Constant")
            interval = (point, point)
            self._check_bounds(interval, arg)

        elif rangeSpec.get("start", None) is not None or rangeSpec.get("end", None) is not None:
            if self.currentFile.QASMType != "REQASM":
                self._error(instructionWarning.format("Range specifier", self.currentFile.QASMType))

            start, end = rangeSpec.get("start", None), rangeSpec.get("end", None)
            start = self._resolve(start, type_ = "Constant")
            end   = self._resolve(end, type_ = "Constant")
            if arg:
                if not start: start = 0
                if not end: end = arg.size
            else:
                if not start or not end:
                    self._error(loopSpecWarning.format("end" if not end else "start"))
            interval = (start, end)
            self._check_bounds(interval, arg)

        else:
            self._error("Unknown range specification: {}".format(rangeSpec))
        return interval

    def parse_maths(self, maths):
        return MathsBlock(self,maths)
    
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class MathsBlock:

    arithOp = ["-","+","^","*","/","div"]
    boolOp = ["!","not","and","or","xor","orof","xorof","andof","<","<=","==","!=",">=",">"]
    intFunc = ["abs","rempow"]
    realFunc = ["arcsin", "arccos", "arctan", "sin", "cos", "tan", "exp", "ln", "sqrt"]
    special = arithOp + boolOp + intFunc + realFunc
    
    def __init__(self, parent, maths, topLevel=True):
        self.parent = parent
        self.maths = []
        self.logical = False
        self.topLevel = topLevel
        while(maths):
            elem = maths.pop(0)
            if isinstance(elem, ParseResults):
                if len(elem) < 3 and hasattr(elem,"var"):
                    self.maths.append(parent._resolve(elem["var"], "Maths", elem.get("ref",None)))
                else:
                    self.maths.append(MathsBlock(self.parent, elem, False))
            elif isinstance(elem, str):
                if elem in MathsBlock.arithOp:
                    self.maths.append(elem)
                elif elem in MathsBlock.boolOp: 
                    self.logical = True
                    self.maths.append(elem)
                elif elem in MathsBlock.intFunc: 
                    self.maths.append(elem)
                    self.maths.append(MathsBlock(self.parent, [maths.pop(0)], False))
                elif elem in MathsBlock.realFunc: 
                    self.maths.append(elem)
                    self.maths.append(MathsBlock(self.parent, [maths.pop(0)], False))
                else:
                    self.maths.append(parent._resolve(elem, "Maths"))
                    
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class ExternalLang:
    pass


# Variable types
class Constant(Referencable):
    def __init__(self, var, val):
        Referencable.__init__(self)
        self.name = var[0]
        self.var_type = var[1]
        self.val  = val[0]
        self.cast = val[1]
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Register(Referencable):
    def __init__(self, name, size):
        Referencable.__init__(self)
        self.name = name
        self.size = size

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class QuantumRegister(Register):

    numQubits = 0

    def __init__(self, name, size):
        Register.__init__(self, name, size)
        if size is None: return# Size is None implies argument

        self.start = QuantumRegister.numQubits
        self.end   = QuantumRegister.numQubits + self.size
        QuantumRegister.numQubits += self.size

class ClassicalRegister(Register):
    def __init__(self, name, size):
        Register.__init__(self, name, size)
        if size is None: return # Size is None implies argument

        self.start = 0
        self.end = self.size

class Alias(Register):
    def __init__(self, name, referee, interval):
        start, end = interval
        size = end - start + 1
        Register.__init__(self, name, size)
        self.start = referee.start + start
        self.end   = self.start + size
        self.type_ = "QuantumRegister"

class Argument(Referencable):
    def __init__(self, name):
        Referencable.__init__(self)
        self.name = name
        self.type_ = "QuantumRegister"

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))


# Operation types
class Comment:
    def __init__(self, comment):
        self.name = comment
        self.comment = comment

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Let(Operation):
    def __init__(self, var, val = None):
        if type(var) is Constant:
            self.const = var
        elif type(var) in [tuple, list]:
            self.const = Constant(var, val)
        else:
            raise TypeError("Bad assignment of let")

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class CallGate(Operation):
    def __init__(self, gate, cargs, qargs):
        self.name = gate

        Operation.__init__(self, qargs, cargs)
        self.handle_loops(self._qargs)

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Measure(Operation):
    def __init__(self, qarg, carg):
        Operation.__init__(self, qarg, carg)
        self.handle_loops([self._cargs])
        if self._loops: self._qargs[1] = self._cargs[1]
        self.handle_loops([self._qargs])
        carg = self._cargs[0]
        bindex = self._cargs[1]
        qarg = self._qargs[0]
        qindex = self._qargs[1]
        # Check bindices
        if bindex is None:
            if carg.size < qarg.size:
                raise IOError(argSizeWarning.format(Req=qarg.size, Var=carg.name, Var2 = qarg.name, Max=carg.size))
            if carg.size > qarg.size:
                raise IOError(argSizeWarning.format(Req=carg.size, Var=qarg.name, Var2 = carg.name, Max=qarg.size))
            self._cargs[1] = self._qargs[1]
        self.finalise_loops()

class Reset(Operation):
    def __init__(self, qarg):
        Operation.__init__(self, qarg)
        self.handle_loops([self._qargs])

class Output(Operation):
    def __init__(self, carg):
        Operation.__init__(self, cargs = carg)
        self.handle_loops([self._cargs])

class EntryExit:
    def __init__(self, parent):
        self.parent = parent
        self.depth = 1

    def exited(self):
        self.depth = 0

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class While(CodeBlock):
    def __init__(self, parent, block, cond):
        self._cond = cond
        CodeBlock.__init__(self,block, parent=parent)
        self.parse_instructions()

class IfBlock(CodeBlock, Operation):
    def __init__(self, parent, cond, block):
        self._cond = cond
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_instructions()

class Gate(Referencable, CodeBlock):

    internalGates = {}

    def __init__(self, parent, name, cargs, qargs, block, recursive = False, returnType = None, unitary = False):
        Referencable.__init__(self)
        self.name = name
        CodeBlock.__init__(self, block, parent=parent)
        self.returnType = returnType
        self.unitary = unitary
        
        if recursive:
            self.gate(name, cargs, qargs, NullBlock(block))
            self._code = []
            self.entry = EntryExit(self.name)

        self.parse_gate_args(qargs, "QuantumArgument")
        self.parse_gate_args(cargs, "ClassicalArgument")

        self.parse_instructions()

        if recursive and self.entry.depth > 0: self._error(noExitWarning.format(self.name))

    def argument(self, arg, classical):
        if classical:
            self._objs[arg] = Constant( (arg, "float") , (None, None) )
            self._cargs.append(self._objs[arg])
        else:
            self._objs[arg] = Argument(arg)
            self._qargs.append(self._objs[arg])

    def parse_gate_args(self, args_in, type_):
        if not args_in: return []
        if type_ in ["ClassicalArgument"]:
            args = args_in[0]
            for arg in args:
                self.argument(arg, True)
        elif type_ in ["QuantumArgument"]:
            for arg in args_in:
                self.argument(arg, False)


    def new_variable(self, argument):
        if not argument.classical: raise IOError("Cannot declare new qarg in gate")
        else : raise IOError("Cannot declare new carg in gate")

class Opaque(Gate):
    def __init__(self, parent, name, cargs, qargs, returnType = None):

        self.type_ = "Gate"
        self.name = name
        self.parent = parent
        self.parentFile = parent.currentFile
        self.returnType = returnType
        self.set_block(NullBlock(self.parentFile))

        self.parse_gate_args(qargs, "QuantumArgument")
        self.parse_gate_args(cargs, "ClassicalArgument")

    def set_block(self, block):
        if block.QASMType != "REQASM" and block.File != ";":
            self._error(opaqueWarning.format(block.QASMType.title()))

        CodeBlock.__init__(self, block, parent=self.parent)
        self.parse_instructions()

class ExternalLang:
    pass

class CBlock(ExternalLang):
    def __init__(self, parent, block):
        self.parent = parent
        self.block = block

class Loop(CodeBlock):
    def __init__(self, parent, block, var, start, end, step = 1):
        CodeBlock.__init__(self,block, parent=parent)
        self._objs[var] = Constant( (var, "int") , (var, None) )
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError("Non contiguous loops not currently permitted")
        self.step = step
        self.parse_instructions()

class NestLoop(Loop):
    def __init__(self, block, var, start, end, step = 1):
        self._code = [block]
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError("Non contiguous loops not currently permitted")
        self.step = step

class InitEnv:
    # Initialise QuESTEnv
    def __init__(self):
        pass

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Verbatim:
    def __init__(self, line):
        self.line = str(line)

    def to_lang(self):
        return self.line

