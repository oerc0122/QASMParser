from .QASMErrors import *
from .QASMTokens import *
from .FileHandle import QASMFile, QASMBlock, NullBlock
import copy

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
            parg[1] = parg[1]
            if parg[1] is None:
                parg[1] = parg[0].name + "_index"
                self.add_loop(parg[1], parg[0].start, parg[0].end)
                
            elif isinstance(parg[1], str):
                pargSplit = parg[1].split(':')
                if len(pargSplit) == 1: # Just index
                    if pargSplit[0].isdecimal():
                        parg[1] = int(pargSplit[0])
                    else: # Do nothing, assume the variable is fine
                        pass
                    
                elif len(pargSplit) == 2: # Min Max
                    parg[1] = parg[0].name + "_index"
                    pargMin = 1
                    pargMax = parg[0].size
                    if pargSplit[0]: pargMin = int(pargSplit[0])
                    if pargSplit[1]: pargMax = int(pargSplit[1])
                    self.add_loop(parg[1], pargMin, pargMax)
                    
                else: raise IOError('Bad Index syntax')

    def resolve_arg(self, arg):
        if type(arg[0]) is Argument:
            return str(arg[1])
        elif issubclass(type(arg[0]),Register):
            if type(arg[1]) is str:
                if arg[1].isdecimal():
                    return str(arg[0].start + int(arg[1]))
                else:
                    return arg[1]
            elif type(arg[1]) is int:
                return str(arg[0].start + int(arg[1]))
            elif type(arg[1]) is Constant:
                return str(arg[1].val)
            else:
                raise TypeError(parseArgWarning.format("index", type(arg[1]).__name__))
        else:
            raise TypeError(parseArgWarning.format("arg", type(arg[0]).__name__))

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Referencable:
    def __init__(self):
        self.type_ = type(self).__name__

class Comment:
    def __init__(self, comment):
        self.name = comment
        self.comment = comment

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

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
        self.size = int(size)

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))
    
class QuantumRegister(Register):

    numQubits = 0
    
    def __init__(self, name, size):
        Register.__init__(self, name, size)
        self.start = QuantumRegister.numQubits
        self.end   = QuantumRegister.numQubits + self.size
        QuantumRegister.numQubits += self.size

class ClassicalRegister(Register):
    def __init__(self, name, size):
        Register.__init__(self, name, size)
        self.start = 0
        self.end = self.size
    
class Alias(Register):
    def __init__(self, name, referee, start, end):
        size = end - start + 1
        Register.__init__(self, name, size)
        self.start = referee.start + start
        self.end   = self.start + size
        self.type_ = "QuantumRegister"
        
class Argument(Referencable):
    def __init__(self, name, classical):
        Referencable.__init__(self)
        self.name = name
        self.classical = classical

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Let:
    def __init__(self, var, val = None):
        if type(var) is Constant:
            self.const = var
        elif type(var) in [tuple, list]:
            self.const = Constant(var, val)
        else:
            raise TypeError('Bad assignment of let')
            
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class CallGate(Operation):
    def __init__(self, gate, cargs, qargs):
        self.name = gate
        Operation.__init__(self, qargs, cargs)
        if cargs:
            if type(cargs) is str:
                self._cargs = cargs.split(',')
            elif type(cargs) is list:
                self._cargs = cargs
        else: self._cargs = []
        self.handle_loops(self._qargs)

    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class Measure(Operation):
    def __init__(self, qarg, carg):
        Operation.__init__(self, qarg, carg)
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

class CodeBlock:
    def __init__(self, block, parent, copyObjs = True, copyFuncs = True):
        self._code = []
        self._qargs= {}
        self._cargs= {}
        if copyObjs:
            self._objs = copy.copy(parent._objs)
        else:
            self._objs = {}
        self.currentFile = block
        self.instructions = self.currentFile.read_instruction()
        self._error = self.currentFile._error
        QASMType = self.currentFile.QASMType
        if QASMType == "OPENQASM":
            self.tokens = openQASM
        elif QASMType == "OAQEQASM":
            self.tokens = OAQEQASM
        else:
            self._error(QASMWarning.format(QASMType))
            
    def to_lang(self, filename):
        for line in self._code:
            return line.to_lang()

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

    def alias(self, argName, referee, index):
        self._is_def(argName, create=True)
        referee = self._resolve(referee, type_="QuantumRegister")
        start, end = self.parse_range(index)
        alias = Alias(argName, referee, start, end)
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
        self._objs[var] = Constant( var, val )
        self._code += [Let( self._objs[var] )]
        
    def call_gate(self, funcName, cargs, qargs):
        self._is_def(funcName, create=False, type_ = 'Gate')
        
        qargs = self.parse_qarg_string(qargs)
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
        carg = self._resolve(carg, type_ = 'ClassicalRegister', index=bindex)
        qarg = self._resolve(qarg, type_ = 'QuantumRegister', index=qindex)

        measure = Measure( qarg, carg )
        
        self._code += [measure]

    def leave(self):
        if hasattr(self, "entry"):
            self.entry.exited()
        else:
            self._error('Cannot exit from a non-recursive gate')

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
        
    def new_if(self, cond, block):
        self._code += [IfBlock(self, cond, block)]

    def cBlock(self, block):
        self._code += [CBlock(self, block)]

    def _resolve(self, var, type_, index = ""):
        if type_ == "Index":

            if var is None:
                return None

            elif type(var) is str:

                if var.isdecimal():
                    return int(var)
                else:
                    self._is_def(var, create=False, type_ = "Index")
                    return self._objs[var]
            else:
                self._error(indexTypeWarning.format(type(var).__name__))
                
        elif type_ in ["ClassicalRegister","QuantumRegister","Alias"]:

            self._is_def(var, create=False, type_ = type_)
            var = self._objs[var]

            if index or index is None: # If index or implicit loop
                index = self._resolve(index, "Index")
                if type(index) is int and (index > var.size - 1 or index < 0) :
                    self._error(indexWarning.format(Var=var.name,Req=index,Max=var.size))

                return [var, index]
            
            else: # Usually arguments through here
                return var
        
        elif type_ == "Constant":
            self._is_def(var, create=False, type_ = type_)
            return self._objs[var].val
        
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
            elif type_ == "Index": # Special case for index vars
                if self._objs[name].type_ not in ['Constant', 'ClassicalRegister']:
                    self._error(wrongTypeWarning.format(self._objs[name].type_, type_))
            elif self._objs[name].type_ is not type_:
                self._error(wrongTypeWarning.format(type_,self._objs[name].type_))
            else: pass
                                                                
    def parse_line(self, line, token):
        match = token(line)
        if token.name == "include":
            if hasattr(self,"include"):
                self.include(match.group('filename'))
            else:
                self._error(includeNotMain)
        elif token.name == "wholeLineComment":
            self.comment(match.group('comment'))
        elif token.name == "createReg":
            argName = match.group('qargName')
            size = match.group('qubitIndex')
            classical = match.group('regType') == "c"
            self.new_variable(argName, size, classical)
        elif token.name == "callGate":
            funcName = match.group('funcName')
            cargs = match.group('cargs')
            qargs = match.group('qargs')
            self.call_gate(funcName, cargs, qargs)
        elif token.name == "createGate":
            funcName = match.group('funcName')
            cargs = match.group('cargs')
            qargs = match.group('qargs')
            block = self.parse_block(funcName)
            self.gate(funcName, cargs, qargs, block)
        elif token.name == "createRGate":
            funcName = match.group('funcName')
            cargs = match.group('cargs')
            qargs = match.group('qargs')
            block = self.parse_block(funcName)
            self.gate(funcName, cargs, qargs, block, recursive = True)
        elif token.name == "opaque":
            funcName = match.group('funcName')
            cargs = match.group('cargs')
            qargs = match.group('qargs')
            block = self.parse_block(funcName)
            self.gate(funcName, cargs, qargs, block, opaque = True)
        elif token.name == "measure":
            carg = match.group('cargName')
            bindex = match.group('bitIndex')
            qarg = match.group('qargName')
            qindex = match.group('qubitIndex')
            self.measurement(qarg, qindex, carg, bindex)
        elif token.name == "ifLine":
            cond = match.group('cond')
            if match.group('op'):
                block = QASMBlock(self.currentFile, match.group('op'))
            else:
                block = self.parse_block("if")
            self.new_if(cond, block)
        elif token.name == "CBlock":
            block = self.parse_block("CBlock")
            self.cBlock(block)
        elif token.name == "PyBlock":
            block = self.parse_block("PyBlock")
            self.PyBlock(block)
        elif token.name == "barrier":
            pass
        elif token.name == "reset":
            qarg = match.group('qargName')
            qindex = match.group('qubitIndex')
            self.reset(qarg, qindex)
        elif token.name == "forLoop":
            var = match.group('var')
            start, end = self.parse_range(match.group('range'))
            block = self.parse_block("for loop")
            self.loop(var, block, start, end)
        elif token.name == "let":
            var = match.group('var')
            val = match.group('val')
            self.let( (var, "const int"), (val, None) )
        elif token.name == "exit":
            self.leave()
        elif token.name == "alias":
            name = match.group('alias')
            qarg = match.group('qargName')
            qindex = match.group('qubitIndex')
            self.alias(name, qarg, qindex)
        elif token.name == "output":
            carg = match.group('cargName')
            bindex = match.group('bitIndex')
            self.output(carg, bindex)
        else:
            self._error(instructionWarning.format(line.lstrip().split()[0], self.currentFile.QASMType))
        self._code[-1].original = line
            
    def parse_qarg_string(self, qargString):
        qargs = [ list(coreTokens.namedQubit(qarg).groups()) for qarg in qargString.split(',')]
        for qarg in qargs:
            qarg[0],qarg[1] = self._resolve(qarg[0], type_="QuantumRegister", index=qarg[1])
        return qargs

    def parse_instructions(self):
        for line in self.instructions:
            for token in self.tokens.tokens():
                if token(line) is not None:
                    self.parse_line(line, token)
                    break
            else: self._error('Invalid instruction: "'+line+'"')

    def parse_block(self, blockName):
        blockOpen = next(self.instructions)
        if not coreTokens.openBlock(blockOpen):
            self._error(f'{blockname} specification not followed by open block')
        depth = 1
        startline = self.currentFile.nLine
        block = ""
        for line in self.instructions:
            if coreTokens.openBlock(line):
                depth += 1
            elif coreTokens.closeBlock(line):
                depth -= 1
            if depth == 0: break
            block += line + ";\n"
        else:
            self._error(eofWarning.format(f'parsing block {blockName}'))
        return QASMBlock(self.currentFile, block, startline)

    def parse_verbatim(self, block):
        indent = "  "
        depth = 0
        instruction = block.readline()
        while instruction:
            if instruction.startswith('for'):
                instruction += block.readline()
                instruction += block.readline()
                instruction = instruction.strip(';')
            if coreTokens.closeBlock(instruction): depth-=1
            self._code += [Verbatim(indent*depth + instruction)]
            if coreTokens.openBlock(instruction): depth+=1
            instruction = block.readline()
    
    def parse_range(self, rangeSpec, arg = None):
        if ":" not in rangeSpec:
            return rangeSpec, rangeSpec
        else:
            if self.currentFile.QASMType != "OAQEQASM":
                self._error(instructionWarning.format('Range specifier', self.currentFile.QASMType))

            start,_,end = rangeSpec.partition(':')
            start = self._resolve(start, type_ = "Index")
            end   = self._resolve(end, type_ = "Index")
            if arg:
                if not start: start = 0
                if not end: end = arg.size
                if start < 0: self._error(indexWarning.format(Req=start, Var = arg.name, Max = arg.size))
                elif end > arg.size: self._error(indexWarning.format(Req=end, Var = arg.name, Max = arg.size))
            else:
                if not start or not end:
                    self._error(loopSpecWarning.format("end" if not end else "start"))
            return start, end
            
    def to_lang(self):
        raise NotImplementedError(langWarning.format(type(self).__name__))

class IfBlock(CodeBlock):
    def __init__(self, parent, cond, block):
        self._cond = cond
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_instructions()
        
class Gate(Referencable, CodeBlock):

    internalGates = {}

    def __init__(self, parent, name, cargs, qargs, block, recursive = False, returnType = None):
        Referencable.__init__(self)
        self.name = name
        CodeBlock.__init__(self, block, parent=parent)
        self.returnType = returnType
        if recursive:
            self.gate(name, cargs, qargs, NullBlock(block))
            self._code = []
            self.entry = EntryExit(self.name)
        
        if qargs:
            for qarg in qargs.split(','):
                self._qargs[qarg] = Argument(qarg, False)

        if cargs:
            for carg in cargs.split(','):
                self._cargs[carg] = Argument(carg, True)

        self.parse_instructions()
        if recursive and self.entry.depth > 0: self._error(noExitWarning.format(self.name))
        
    def new_variable(self, argument):
        if not argument.classical: raise IOError('Cannot declare new qarg in gate')
        else : raise IOError('Cannot declare new carg in gate')

    def parse_qarg_string(self, qargString):
        qargs = [ coreTokens.namedQubit(qarg).groups() for qarg in qargString.split(',')]
        qargs = [[self._qargs[arg[0]], arg[0]+"_index"] for arg in qargs]
        return qargs

class Opaque(Gate):
    def __init__(self, parent, name, cargs, qargs, block, returnType = None):

        self.type_ = "Gate"
        self.name = name
        self.returnType = returnType
        if len(block) == 0: block.File = [';']
        if block.QASMType != "OAQEQASM" and block.File != ";":
            self._error(opaqueWarning.format(block.QASMType.title()))
            
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_verbatim(block)

        if qargs:
            for qarg in qargs.split(','):
                self._qargs[qarg] = Argument(qarg, False)

        if cargs:
            for carg in cargs.split(','):
                self._cargs[carg] = Argument(carg, True)
 
    
class Loop(CodeBlock):
    def __init__(self, parent, block, var, start, end, step = 1):
        CodeBlock.__init__(self,block, parent=parent)
        self._objs[var] = Constant( (var, "int") , (var, None) )
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError('Non contiguous loops not currently permitted')
        self.step = step
        self.parse_instructions()

class NestLoop(Loop):
    def __init__(self, block, var, start, end, step = 1):
        self._code = [block]
        self.depth = 1
        self.var = var
        self.start = start
        self.end = end
        if step != 1: raise NotImplementedError('Non contiguous loops not currently permitted')
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

class ExternalLang:
    pass
    
class CBlock(ExternalLang, CodeBlock):
    def __init__(self, parent, block):
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_verbatim(block)

        
class PyBlock(ExternalLang, CodeBlock):
    def __init__(self, parent, block):
        CodeBlock.__init__(self, block, parent=parent)
        self.parse_verbatim(block)
