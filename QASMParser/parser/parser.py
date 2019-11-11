"""
Module containing main file for parsing
"""

from importlib import import_module
import sys
import os.path
from .types import (QuantumRegister, CodeBlock, Let, Constant, Comment, Include, CBlock, Verbatim, InitEnv,
                        Gate, Circuit, Procedure, Opaque)
from .filehandle import (QASMFile)
from .errors import (langNotDefWarning, langMismatchWarning, includeWarning)

langConstants = ["e", "pi", "T", "F"]

class ProgFile(CodeBlock):
    """
    Main program file.

    Contians routines for converting code to outputlanguages and writing said output to an output file.
    """
    quantumRegisters = property(lambda self: self._quantumRegisters)

    def __init__(self, filename):
        self.filename = filename
        self._name = filename
        self.classLang = None
        CodeBlock.__init__(self, self, QASMFile(filename), False)
        for gate in Gate.internalGates.values():
            self._objs[gate.name] = gate
        for constant in ["e", "pi"]:
            self._objs[constant] = Constant(self, (constant, "float"), (None, None))
        for val, name in enumerate(["F", "T"]):
            self._objs[name] = Constant(self, (name, "bool"), (val, None))
        self.parse_instructions()
        self._quantumRegisters = [reg for reg in self.code if isinstance(reg, QuantumRegister)]
        self._gates = [gate for gate in self.code if isinstance(gate, (Gate, Circuit, Procedure, Opaque))]
        self.useTN = False
        self.partition = None

    def to_lang(self, filename=None, langOut="C", **options):
        """
        Translate file into provided language.
        If filename is provided write translation to file.
        Replace included files with their in language equivalents for module support.

        :param filename: output file to write
        :param module: whether to compile
        :param includes: dictionary of substitutions for included files
        :param langOut: output language
        :param verbose: whether to provide original QASM alongside
        :returns: None
        :rtype: None
        """
        includes = options.get("includes", {})

        try:
            lang = import_module(f"QASMParser.langs.{langOut}")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(langOut))

        indent = lang.indent
        if self.classLang is not None and self.classLang != langOut:
            raise NotImplementedError(langMismatchWarning.format(self.classLang, langOut))

        def print_code(self, code, outputFile):
            nonlocal depth
            depth += 1
            for line in code:
                # Verbose -- Print original
                if options["verbose"] and hasattr(line, 'original') and not isinstance(line, Comment):
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
                        depth -= 1
                    writeln(line.to_lang())
                    if lang.blockOpen and lang.blockOpen in line.line:
                        depth += 1

                else: # Print self
                    writeln(line.to_lang())

            depth -= 1

        if filename:
            outputFile = open(filename, 'w')
        else:
            outputFile = sys.stdout

        # Create copy to work with
        codeToWrite = self.code[:]
        depth = -1

        writeln = lambda writeIn: [outputFile.write(depth*indent + toWrite + "\n")
                                   for toWrite in writeIn.splitlines()]

        for line in self.currentFile.header:
            writeln(Comment(self, line).to_lang())

        # If our language needs to add things to the header
        if options["module"]:
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
                codeToWrite[target].set_import(includes[include.filename])
            else:
                codeToWrite[target:target+1] = include.raw_code

        if self.useTN:
            writeln(lang.includeTN)

        if lang.hoistIncludes:
            codeToWrite = sorted(codeToWrite, key=lambda x: isinstance(x, Include))
            while isinstance(codeToWrite[-1], Include):
                print_code(self, [codeToWrite.pop()], outputFile)

        if options["include_internals"]:
            codeToWrite = list(Gate.internalGates.values()) + codeToWrite

        if lang.hoistFuncs:
            codeToWrite = sorted(codeToWrite, key=lambda x: issubclass(type(x), Gate))
            gate = []
            while codeToWrite and issubclass(type(codeToWrite[-1]), Gate):
                gate.append(codeToWrite.pop())
            print_code(self, reversed(gate), outputFile)

        # Hoist qregs
        codeToWrite = [line for line in codeToWrite if line not in self.quantumRegisters]
        codeToWrite = self.fix_qureg() + codeToWrite

        if any([not isinstance(line, Comment) for line in codeToWrite]):
            mainProg = Opaque(self, funcName, returnType="int")
            mainProg.set_code(codeToWrite)

        print_code(self, [mainProg], outputFile)

        if filename:
            outputFile.close()

    def fix_qureg(self):
        """ Fix quantum registers to align with QuEST style """
        code = [InitEnv(self)]
        for reg in self.quantumRegisters:
            code += [Comment(self, f'{reg.name}[{reg.start}:{reg.end-1}]')]
            code += [Let(self, (reg.name, "const listint"),
                         (list(range(reg.start, reg.end)), None))]

        if not self.useTN:
            code += [QuantumRegister(self, "qreg", QuantumRegister.numQubits)]
        else:
            code += [self.partition]
        return code

    def run(self):
        """ Run constructed code in Python """
        try:
            lang = import_module(f"QASMParser.langs.Python")
            lang.set_lang()
        except ImportError:
            raise NotImplementedError(langNotDefWarning.format(lang))

        for line in self.code:
            exec(line.to_lang())

    def include(self, filename):
        """ Parse second file and add gates and vars into local scope

        :param filename: file to include

        """
        other = ProgFile(filename)
        self._code += [Include(self, filename, other.code)]
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
