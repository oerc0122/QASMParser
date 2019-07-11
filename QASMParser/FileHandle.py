import os.path
import copy
from .QASMTokens import *
from .QASMErrors import *

class QASMFile:

    _QASMFiles = []
    depth_limit = 10

    def __init__(self,filename, reqVersion=(1,2,0)):
        if filename in QASMFile._QASMFiles: raise IOError('Circular dependency in includes')
        if os.path.isfile(filename): self.File = open(filename,'r')
        else: raise FileNotFoundError(fnfWarning.format(filename))
        self.path = filename
        self.name = filename[filename.rfind('/')+1:] # Remove path
        if len(QASMFile._QASMFiles) > self.depth_limit: self._error(recursionError.format(self.depth_limit))
        QASMFile._QASMFiles.append(self.name)
        self.nLine = 0
        temp = ''
        self.header = []
        for line in self.read_instruction():
            if line.get('keyword',None) is None:
                if line.get("comment", None) is not None:
                    self.header += [line['comment']]
                else:
                    pass
            elif line.get('keyword') == "version":
                self.version = parseVersion(line["version"][0])
                self.QASMType = line["version"]["type"]
                self.versionNumber = line["version"]["versionNumber"]
                break
            else:
                self._error("Header does not contain version")

        if reqVersion[0] > self.version[0] :
            self._error('Unsupported QASM version: {}.{}'.format(*self.version))

    def _error(self, message=""):
        print(fileWarning.format(message=message,
                                         file=self.name, line=self.nLine))
        import traceback
        traceback.print_stack()
        quit()

    def __del__(self):
        try:
            openFiles = QASMFile._QASMFiles
            del openFiles[openFiles.index(self.name)]
            self.File.close()
        except AttributeError:
            return

    def _handler(self,err, line):
            if not err.line:
                print("No line found")
                self._error(unknownParseWarning)
            if len(line) < 80:
                print(" ".join(line.splitlines()))
                print(" "*(line.index(err.line) + err.column-1) + "^")
            else:
                print(err.line)
                print(" "*(err.column-1) + "^")
            problem = errorKeywordParser.parseString(err.line)
            key = problem["keyword"]
            try:
                if key in qops.keys():
                    temp = qops[key].parser.parseString(err.line)
                elif key in cops.keys():
                    temp = cops[key].parser.parseString(err.line)
                elif key in blocks.keys():
                    temp = blocks[key].parser.parseString(err.line)
                else:
                    raise ParseException(instructionWarning.format(key, self.QASMType, self.versionNumber))
                if key in ["gate", "circuit", "opaque"]:
                    if reserved.searchString(err.line.replace(key,"")):
                        raise ParseException("Reserved keyword '{}' used in {} declaration".format(
                            reserved.searchString(err.line.replace(key,"")).pop().pop(), key
                            ))
                raise ParseException(unknownParseWarning + f" with parsing {problem['keyword']}")
            except ParseException as subErr:
                print(fileWarning.format(message=subErr.msg, file=self.name, line=self.nLine))
                import traceback
                traceback.print_stack()
                quit()

    def read_instruction(self):
        line = self.readline()
        currentLine = line
        while line is not None:
            *test, = lineParser.scanString(currentLine.strip())
            if test and test[0][1] == 0: # If line looks like valid instruction
                try:
                    prev = 0
                    for inst, start, end in QASMcodeParser.scanString(currentLine.lstrip()):
                        if start != prev:
                            if prev != 0: break
                            else: QASMcodeParser.parseString(currentLine,parseAll=True)
                        if not currentLine[start:end].strip(): continue # Skip blank lines
                        instruction = inst[0]
                        instruction.original = currentLine[start:end]
                        prev = end
                        yield instruction
                        currentLine = currentLine[end:].lstrip()
                except ParseException as err:
                    self._handler(err, currentLine)

            if currentLine.strip().startswith(";"): # Handle null statement
                currentLine = currentLine.lstrip(" ;\n\t")
            line = self.readline()
            if line is not None: currentLine += line

        if currentLine.strip(): # Catch remainder
            try:
                if list(QASMcodeParser.scanString(currentLine))[0][0] != 0:
                    raise IOError
                for inst, start, end in QASMcodeParser.scanString(currentLine):
                    instruction = inst[0]
                    instruction.original = currentLine[start:end]
                    prev = end
                    print(inst)
                    yield instruction
                    currentLine = currentLine[end:].lstrip()

            except ParseException as err:
                self._handler(err, currentLine)

    def readline(self):
        """ Reads a line from a file """
        for line in self.File:
            self.nLine += 1
            if not line.strip(): continue
            return line
        else:
            return None

    def _parent_file(self, parent):
        self.name = parent.name
        self.version = parent.version
        self.QASMType = parent.QASMType
        self.nLine = parent.nLine

class QASMString(QASMFile):
    def __init__(self, block):
        import io
        self.parent = self
        self.version = (2,2,0)
        self.versionNumber = 2.0
        self.QASMType = "REQASM"
        self.name = "Internal"
        self.File = io.StringIO(block)
        self.currentFile = self
        self.nLine = 0
        self._objs = {}

    def __del__(self):
        pass

class QASMBlock(QASMFile):
    def __init__(self, parent, block, startline = None):
        self._parent_file(parent)
        if startline: self.nLine = startline
        self.File = block

    def __len__(self):
        return len(self.File)

    def read_instruction(self):
        for instruction in self.File[0]:
            self.nLine += 1
            yield instruction

    def readline(self):
        """ Reads a line from a file """
        raise NotImplementedError()

    def __del__(self):
        pass

class NullBlock(QASMFile):
    def __init__(self, parent):
        self._parent_file(parent)
        self.File = [';']
        self.read = False

    def __len__(self):
        return 0

    def readline(self):
        if not self.read:
            self.read = True
            return "// "
        return None

    def __del__(self):
        pass
