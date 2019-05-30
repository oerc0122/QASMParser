from importlib import import_module
import sys
import os.path
from .QASMTokens import *
from .QASMTypes import *
from .FileHandle import *
from .QASMErrors import *

lang_constants = ["e", "pi", "T", "F"]

class ProgFile(CodeBlock):
    def __init__(self, filename):
        self.filename = filename
        CodeBlock.__init__(self, QASMFile(filename), parent = None, copyFuncs = False, copyObjs = False)
        for gate in Gate.internalGates.values():
            self._objs[gate.name] = gate
        for constant in ["e","pi"]:
            self._objs[constant] = Constant( ( constant, "float"), ( None, None ))
        for val, name in enumerate(["F", "T"]):
            self._objs[name] = Constant( ( name, "bool") , ( val, None ) )
        self.parse_instructions()
        
    def to_lang(self, filename = None, module = False, function = False, includes = {}, langOut = "C", verbose = False):
        try:
            lang = import_module(f"QASMParser.langs.{langOut}")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(lang))

        indent = lang.indent
        writeln = lambda writeIn: [outputFile.write(self.depth*indent + toWrite + "\n" ) for toWrite in writeIn.splitlines()]

        if hasattr(self, "classLang") and self.classLang is not langOut:
            raise NotImplementedError("Classical language {} does not match output language {}".format(self.classLang, langOut))
        
        def print_code(self, code, outputFile):
            self.depth += 1
            for line in code:
                
                if verbose and hasattr(line,'original') and type(line) is not Comment: # Verbose -- Print original
                    writeln(Comment(self, line.original).to_lang() + "\n")

                if hasattr(line,"inlineComment"): # Inline comments
                    writeln(line.inlineComment.to_lang())
                    
                if hasattr(line,"_loops") and line._loops: # Handle loops
                    writeln(line._loops.to_lang() + lang.blockOpen)
                    print_code(self,line._loops._code,outputFile)
                    writeln(lang.blockClose)
                    
                elif issubclass(type(line), ExternalLang): # Handle verbatim language blocks
                    writeln(line.to_lang())
                    
                elif hasattr(line,"_code"): # Print children
                    writeln(line.to_lang() + lang.blockOpen)
                    print_code(self,line._code,outputFile)
                    writeln(lang.blockClose)

                elif issubclass(type(line), Verbatim):
                    if lang.blockClose and lang.blockClose in line.line: self.depth -= 1
                    writeln(line.to_lang())
                    if lang.blockOpen and lang.blockOpen in line.line: self.depth += 1
                
                else: # Print self
                    writeln(line.to_lang())
                
            self.depth -= 1
            
        if filename: outputFile = open(filename, 'w')
        else:        outputFile = sys.stdout

        codeToWrite = self._code[:]
        self.depth = -1
       
        for line in self.currentFile.header:
            writeln(Comment(self, line).to_lang())

        # If our language needs to add things to the header
        if module:
            if filename: funcName = os.path.splitext(os.path.basename(filename))[0]
            else:        funcName = "module"
        else:
            funcName = "main"
            if hasattr(lang,'header'):
                if type(lang.header) is list:
                    for line in lang.header:
                        writeln(line)
                elif type(lang.header) is str:
                    writeln(lang.header)
                    
        incs = [ x for x in codeToWrite if isinstance(x, Include) ]
        for include in incs:
            target = codeToWrite.index(include)
            if include.filename in includes:
                codeToWrite[target].filename = includes[include.filename]
            else:
                codeToWrite[target:target+1] = include.code

        if lang.hoistIncludes:
            codeToWrite = sorted(codeToWrite, key = lambda x: isinstance(x, Include) )
            while isinstance(codeToWrite[-1], Include):
                print_code(self,[codeToWrite.pop()], outputFile)

        if lang.hoistFuncs:
            codeToWrite = sorted(codeToWrite, key = lambda x: issubclass(type(x), Gate) )
            gate = []
            while issubclass(type(codeToWrite[-1]), Gate):
                gate.append(codeToWrite.pop())
            print_code(self, reversed(gate), outputFile)
            
        if any( [ not isinstance(line, Comment) for line in codeToWrite ] ):
            if not lang.bareCode:
                temp = Gate(self, funcName, NullBlock(self.currentFile), returnType = "int")
                temp._code = [InitEnv()]
                # Hoist qregs
                regs = [ x for x in codeToWrite if type(x).__name__ == "QuantumRegister" ]
                for reg in regs:
                    temp._code += [Comment(self, f'{reg.name}[{reg.start}:{reg.end-1}]')]
                codeToWrite = [ x for x in codeToWrite if type(x).__name__ != "QuantumRegister" ]
                temp._code += [QuantumRegister("qreg", QuantumRegister.numQubits)]
                temp._code += codeToWrite
                codeToWrite = [temp]

        print_code(self, codeToWrite, outputFile)
            
        if filename: outputFile.close()
        
    def run(self):
        try:
            lang = import_module(f"QASMParser.langs.Python")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(lang))

        for line in self._code:
            exec(line.to_lang())

    def include(self, filename):
        other = ProgFile(filename)
        self._code += [Include(self, filename, other._code)]
        for obj in other._objs:
            if obj in Gate.internalGates: continue
            if obj in lang_constants: continue
            if obj in self._objs:
                self._error(includeWarning.format(
                    name = obj, type = self._objs[obj].type_, other = other.filename, me = self.filename)
                )
            else:
                self._objs[obj] = other._objs[obj]
                self._objs[obj].included = True
