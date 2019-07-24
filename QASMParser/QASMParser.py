"""
Module containing main file for parsing
"""

from importlib import import_module
import sys
import os.path
from .QASMTypes import (CodeBlock, Constant, Comment, Gate, Include, CBlock, Verbatim,
                        InitEnv, Let, QuantumRegister)
from .FileHandle import (QASMFile, NullBlock)
from .QASMErrors import (langNotDefWarning, langMismatchWarning, includeWarning)

langConstants = ["e", "pi", "T", "F"]

class ProgFile(CodeBlock):
    """
    Main program file.

    Contians routines for converting code to outputlanguages and writing said output to an output file.
    """
    def __init__(self, filename):
        self.filename = filename
        self.name = filename
        CodeBlock.__init__(self, QASMFile(filename), None, False)
        self.parent = self
        for gate in Gate.internalGates.values():
            self._objs[gate.name] = gate
        for constant in ["e", "pi"]:
            self._objs[constant] = Constant(self, (constant, "float"), (None, None))
        for val, name in enumerate(["F", "T"]):
            self._objs[name] = Constant(self, (name, "bool"), (val, None))
        self.parse_instructions()
        self.depth = 0
        self.classLang = None

    def to_lang(self, filename=None, module=False, includes=(), langOut="C", verbose=False):
        """
        Translate file into provided language.
        If filename is provided write translation to file.
        Replace included files with their in language equivalents for module support.
        """
        try:
            lang = import_module(f"QASMParser.langs.{langOut}")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(lang))

        indent = lang.indent
        if hasattr(self, "classLang") and self.classLang is not langOut:
            raise NotImplementedError(langMismatchWarning.format(self.classLang, langOut))

        def print_code(self, code, outputFile):

            self.depth += 1
            for line in code:

                if verbose and hasattr(line, 'original') and not isinstance(line, Comment): # Verbose -- Print original
                    writeln(Comment(self, line.original).to_lang() + "\n")

                if hasattr(line, "inlineComment"): # Inline comments
                    writeln(line.inlineComment.to_lang())

                if hasattr(line, "loops") and line.loops: # Handle loops
                    writeln(line.loops.to_lang() + lang.blockOpen)
                    print_code(self, line.loops.code, outputFile)
                    writeln(lang.blockClose)

                elif isinstance(line, CBlock): # Handle verbatim language blocks
                    writeln(line.to_lang())

                elif hasattr(line, "code"): # Print children
                    writeln(line.to_lang() + lang.blockOpen)
                    print_code(self, line.code, outputFile)
                    writeln(lang.blockClose)

                elif issubclass(type(line), Verbatim):
                    if lang.blockClose and lang.blockClose in line.line:
                        self.depth -= 1
                    writeln(line.to_lang())
                    if lang.blockOpen and lang.blockOpen in line.line:
                        self.depth += 1

                else: # Print self
                    writeln(line.to_lang())

            self.depth -= 1

        if filename:
            outputFile = open(filename, 'w')
        else:
            outputFile = sys.stdout

        writeln = lambda writeIn: [outputFile.write(self.depth*indent + toWrite + "\n")
                                   for toWrite in writeIn.splitlines()]


        # Create copy to work with
        codeToWrite = self.code[:]
        self.depth = -1

        for line in self.currentFile.header:
            writeln(Comment(self, line).to_lang())

        # If our language needs to add things to the header
        if module:
            if filename:
                funcName = os.path.splitext(os.path.basename(filename))[0]
            else:
                funcName = "module"
        else:
            funcName = "main"
            if hasattr(lang, 'header'):
                if isinstance(lang.header, (list, tuple)):
                    for line in lang.header:
                        writeln(line)
                elif isinstance(lang.header, str):
                    writeln(lang.header)

        incs = (x for x in codeToWrite if isinstance(x, Include))
        for include in incs:
            target = codeToWrite.index(include)
            if include.filename in includes:
                codeToWrite[target].filename = includes[include.filename]
            else:
                codeToWrite[target:target+1] = include.code

        if lang.hoistIncludes:
            codeToWrite = sorted(codeToWrite, key=lambda x: isinstance(x, Include))
            while isinstance(codeToWrite[-1], Include):
                print_code(self, [codeToWrite.pop()], outputFile)

        if lang.hoistFuncs:
            codeToWrite = sorted(codeToWrite, key=lambda x: issubclass(type(x), Gate))
            gate = []
            while codeToWrite and issubclass(type(codeToWrite[-1]), Gate):
                gate.append(codeToWrite.pop())
            print_code(self, reversed(gate), outputFile)

        if any([not isinstance(line, Comment) for line in codeToWrite]):
            if not lang.bareCode:
                temp = Gate(self, funcName, NullBlock(self.currentFile), returnType="int")
                temp.code = [InitEnv()]
                # Hoist qregs
                regs = [x for x in codeToWrite if type(x).__name__ == "QuantumRegister"]
                for reg in regs:
                    temp.code += [Comment(self, f'{reg.name}[{reg.start}:{reg.end-1}]')]
                    temp.code += [Let(self, (reg.name, "const listint"),
                                      (list(range(reg.start, reg.end)), None))]
                # Remove qreg declarations
                codeToWrite = [x for x in codeToWrite if type(x).__name__ != "QuantumRegister"]
                temp.code += [QuantumRegister(self, "qreg", QuantumRegister.numQubits)]
                temp.code += codeToWrite
                codeToWrite = [temp]

        print_code(self, codeToWrite, outputFile)

        if filename:
            outputFile.close()

    def run(self):
        """ Run constructed code """
        try:
            lang = import_module(f"QASMParser.langs.Python")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(lang))

        for line in self.code:
            exec(line.to_lang())

    def include(self, filename):
        """ Parse second file and add gates and vars into local scope """
        other = ProgFile(filename)
        self.code += [Include(self, filename, other.code)]
        for objName, obj in other.get_objs():
            if objName in Gate.internalGates:
                continue
            if objName in langConstants:
                continue
            if objName in self._objs:
                self._error(includeWarning.format(name=objName,
                                                  type=self._objs[objName].type_,
                                                  other=other.filename,
                                                  me=self.filename))

            else:
                self._objs[objName] = obj
                self._objs[objName].included = True
