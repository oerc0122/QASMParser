import os.path
import copy
from .QASMTokens import *
from .QASMErrors import *

class QASMFile:

    _QASMFiles = []
    depth_limit = 10
    
    def __init__(self,filename, reqVersion=("2","0")):
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
                self.header += [line['comment']]
            elif line.get('keyword') == "version":
                self.QASMType, self.majorVer, self.minorVer = (line["type"], *line["versionNumber"].split("."))
                self.version = (self.majorVer, self.minorVer)
                break
            else:
                self._error("Header does not contain version")

        if reqVersion[0] > self.version[0] :
            self._error('Unsupported QASM version: {}.{}'.format(*self.version))

    def _error(self, message=""):
        raise IOError(fileWarning.format(message=message,
                                         file=self.name, line=self.nLine))

    def __del__(self):
        try:
            openFiles = QASMFile._QASMFiles
            del openFiles[openFiles.index(self.name)]
            self.File.close()
        except AttributeError:
            return

    def _handler(err):
            if not err.line:
                self._error(unknownParseWarning)
            print(err.line)
            print(" "*(err.column-1) + "^")
            problem = testKeyword.parseString(err.line)
            try:
                if problem["keyword"] in qops.keys():
                    temp = qops[problem["keyword"]].parser.parseString(err.line)
                elif problem["keyword"] in cops.keys():
                    temp = cops[problem["keyword"]].parser.parseString(err.line)
                else:
                    self._error(instructionWarning.format(problem["keyword"], self.QASMType))
                self._error(unknownParseWarning + f" with parsing {problem['keyword']}")
            except ParseException as subErr:
                self._error(subErr)

    def read_instruction(self):
        line = self.readline()
        currentLine = line
        while line is not None:
            *test, = lineParser.scanString(currentLine)
            if test and test[0][1] == 0: # If line looks like valid instruction
                try:
                    yield QASMcodeParser.parseString(currentLine)[0]
                    currentLine = ""
                except ParseException as err:
                    self._handler(err)
                    
            line = self.readline()
            if line is not None: currentLine += line
            
        if currentLine: # Catch remainder
            try:
                yield QASMcodeParser.parseString(currentLine)[0]
            except ParseException as err:
                self._handler(err)

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
        
class QASMBlock(QASMFile):
    def __init__(self, parent, block, startline = None):
        self._parent_file(parent)
        if startline: self.nLine = startline
        else : self.nLine = 0
        self.File = block
        
    def __len__(self):
        return len(self.File)

    def read_instruction(self):
        for instruction in self.File[0]:
            print("QASMBLOCK", instruction.dump())
            self.nLine += 1
            yield instruction
    
    def readline(self):
        """ Reads a line from a file """
        raise NotImplementedError()
        # while len(self.File) > 0:
        #     line = self.File.pop(0)
        #     self.nLine += 1
        #     if not line: continue
        #     print(self.nLine, line)
        #     return line
        # else:
        #     # Recallable
        #     self.File = self.orig.splitlines()
        #     return None

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
