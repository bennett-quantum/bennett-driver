"""Query PassPluginLibraryInfo in an isolated process, with explicit R options.

Dialect §19.9 requires the selected profile's exact exported identity. LLVM's
public C support API parses registered options before that query for a producer
that selects its identity from command-line options. No pass callback runs.
Historical queries retain their pre-parse behavior.
"""
import ctypes
import sys

class Info(ctypes.Structure):
    _fields_ = [('api', ctypes.c_uint32), ('name', ctypes.c_char_p),
                ('version', ctypes.c_char_p), ('callback', ctypes.c_void_p)] + (
                    [('pre_codegen', ctypes.c_void_p)] if '/llvm-23/' in sys.argv[2] else [])

llvm = ctypes.CDLL(sys.argv[2], mode=ctypes.RTLD_GLOBAL)
plugin = ctypes.CDLL(sys.argv[1])
plugin.llvmGetPassPluginInfo.restype = Info
if sys.argv[3] == '0.3-r1':
    argv = [b'bennett-driver-identity', b'-bennett-dialect=0.3-r1', b'-bennett-isa=0.9']
    llvm.LLVMParseCommandLineOptions.argtypes = [ctypes.c_int,
                                                ctypes.POINTER(ctypes.c_char_p), ctypes.c_char_p]
    llvm.LLVMParseCommandLineOptions.restype = None
    llvm.LLVMParseCommandLineOptions(len(argv), (ctypes.c_char_p * len(argv))(*argv), b'')
info = plugin.llvmGetPassPluginInfo()
expected_api = 2 if '/llvm-23/' in sys.argv[2] else 1
if info.api != expected_api or info.name != b'bennett':
    raise SystemExit('BD-E-VERSION: incompatible pass-plugin API or name (expected bennett)')
print(info.version.decode('ascii'))
