#!/usr/bin/env python3
"""Query the public PassPluginLibraryInfo ABI in an isolated process, not Rust.
No pass callback is invoked. The driver executable has no LLVM linkage.
"""
import ctypes, sys
class Info(ctypes.Structure):
    _fields_ = [('api', ctypes.c_uint32), ('name', ctypes.c_char_p),
                ('version', ctypes.c_char_p), ('callback', ctypes.c_void_p)] + (
                    [('pre_codegen', ctypes.c_void_p)] if '/llvm-23/' in sys.argv[2] else [])
ctypes.CDLL(sys.argv[2], mode=ctypes.RTLD_GLOBAL)
lib = ctypes.CDLL(sys.argv[1])
lib.llvmGetPassPluginInfo.restype = Info
info = lib.llvmGetPassPluginInfo()
expected_api = 2 if '/llvm-23/' in sys.argv[2] else 1
if info.api != expected_api or info.name != b'bennett':
    raise SystemExit('BD-E-VERSION: incompatible pass-plugin API or name (expected bennett)')
print(info.version.decode('ascii'))
