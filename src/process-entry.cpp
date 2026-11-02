// Driver-owned synthesis, invoked externally; the Rust driver never links LLVM.
#include "llvm/Bitcode/BitcodeWriter.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
using namespace llvm;

static int fail(const Twine &message) {
  errs() << "BD-E-PROCESS: " << message << '\n';
  return 1;
}

int main(int argc, char **argv) {
  if (argc != 5)
    return fail("expected INPUT.bc OUTPUT.bc ENTRY REPORT.json");
  LLVMContext context;
  SMDiagnostic diagnostic;
  auto module = parseIRFile(argv[1], diagnostic, context);
  if (!module) {
    diagnostic.print(argv[0], errs());
    return 1;
  }
  Module &m = *module;
  auto *user = m.getFunction(argv[3]);
  if (!user || user->isDeclaration())
    return fail("whole-program entry has no definition: " + Twine(argv[3]));
  auto *i32 = Type::getInt32Ty(context);
  auto *i64 = Type::getInt64Ty(context);
  auto *ptr = PointerType::getUnqual(context);
  auto *voidTy = Type::getVoidTy(context);
  auto *wrapperType = FunctionType::get(i32, {i32, ptr, ptr}, false);
  auto *prepareType = FunctionType::get(voidTy, {i32, ptr, ptr}, false);
  auto *exitType = FunctionType::get(voidTy, {i32}, false);
  auto *faultType = FunctionType::get(voidTy, {i64}, false);
  unsigned params = user->arg_size();
  if (user->isVarArg() || user->getReturnType() != i32 ||
      (params != 0 && params != 2 && params != 3) ||
      (params && (user->getArg(0)->getType() != i32 ||
                  user->getArg(1)->getType() != ptr)) ||
      (params == 3 && user->getArg(2)->getType() != ptr))
    return fail("C process entry requires i32 (), i32 (i32, ptr), or i32 (i32, ptr, ptr)");
  if (m.getDataLayout().getPointerSizeInBits() != 64)
    return fail("published process runtime requires the LP64 layout");
  for (auto item : {std::make_pair("__bennett_rt_prepare_process", prepareType),
                    std::make_pair("exit", exitType),
                    std::make_pair("__bennett_nz_fault", faultType)}) {
    if (auto *function = m.getFunction(item.first))
      if (function->getFunctionType() != item.second)
        return fail("incompatible runtime function type: " + Twine(item.first));
  }
  auto prepare = m.getOrInsertFunction("__bennett_rt_prepare_process", prepareType);
  auto exit = m.getOrInsertFunction("exit", exitType);
  auto fault = m.getOrInsertFunction("__bennett_nz_fault", faultType);

  auto *emptyType = ArrayType::get(ptr, 1);
  auto makeEmpty = [&](StringRef name) {
    auto *global = new GlobalVariable(m, emptyType, false,
        GlobalValue::PrivateLinkage, ConstantAggregateZero::get(emptyType), name);
    global->setAlignment(Align(8));
    return global;
  };
  auto *emptyArgv = makeEmpty(".bennett.driver.empty.argv");
  auto *emptyEnvp = makeEmpty(".bennett.driver.empty.envp");
  auto *null = ConstantPointerNull::get(ptr);

  // Bytewise volatile validation has no arbitrary vector/string length cap.
  // The normaliser/native adapter supplies live-allocation checks on these
  // reads; volatile keeps validation observable through the pre-link pipeline.
  auto *stringCheck = Function::Create(FunctionType::get(voidTy, {ptr}, false),
      GlobalValue::PrivateLinkage, ".bennett.driver.check.string", m);
  auto *stringEntry = BasicBlock::Create(context, "entry", stringCheck);
  auto *stringLoop = BasicBlock::Create(context, "loop", stringCheck);
  auto *stringDone = BasicBlock::Create(context, "done", stringCheck);
  IRBuilder<> b(stringEntry);
  b.CreateBr(stringLoop);
  b.SetInsertPoint(stringLoop);
  auto *bytePointer = b.CreatePHI(ptr, 2);
  bytePointer->addIncoming(stringCheck->getArg(0), stringEntry);
  auto *byte = b.CreateLoad(b.getInt8Ty(), bytePointer);
  byte->setVolatile(true);
  auto *nextByte = b.CreateGEP(b.getInt8Ty(), bytePointer, b.getInt64(1));
  bytePointer->addIncoming(nextByte, stringLoop);
  b.CreateCondBr(b.CreateICmpEQ(byte, b.getInt8(0)), stringDone, stringLoop);
  b.SetInsertPoint(stringDone);
  b.CreateRetVoid();

  std::string entry = user->getName().str();
  user->setName(".bennett.driver.user." + entry);
  user->setLinkage(GlobalValue::InternalLinkage);
  auto *wrapper = Function::Create(wrapperType, GlobalValue::ExternalLinkage,
                                   entry, m);
  wrapper->addFnAttr("bennett.driver.process.entry", "1");
  auto *begin = BasicBlock::Create(context, "entry", wrapper);
  auto *vectors = BasicBlock::Create(context, "vectors", wrapper);
  auto *argsHead = BasicBlock::Create(context, "argv.head", wrapper);
  auto *argsItem = BasicBlock::Create(context, "argv.item", wrapper);
  auto *argsString = BasicBlock::Create(context, "argv.string", wrapper);
  auto *argsEnd = BasicBlock::Create(context, "argv.end", wrapper);
  auto *envHead = BasicBlock::Create(context, "envp.head", wrapper);
  auto *envString = BasicBlock::Create(context, "envp.string", wrapper);
  auto *invoke = BasicBlock::Create(context, "invoke", wrapper);
  auto *bad = BasicBlock::Create(context, "bad.context", wrapper);
  b.SetInsertPoint(begin);
  auto *count = wrapper->getArg(0);
  auto *suppliedArgv = wrapper->getArg(1);
  auto *suppliedEnvp = wrapper->getArg(2);
  b.CreateStore(null, emptyArgv);
  b.CreateStore(null, emptyEnvp);
  b.CreateCondBr(b.CreateICmpSLT(count, b.getInt32(0)), bad, vectors);
  b.SetInsertPoint(vectors);
  auto *argvMissing = b.CreateICmpEQ(suppliedArgv, null);
  auto *actualArgv = b.CreateSelect(argvMissing, emptyArgv, suppliedArgv);
  auto *actualEnvp = b.CreateSelect(b.CreateICmpEQ(suppliedEnvp, null), emptyEnvp, suppliedEnvp);
  auto *wideCount = b.CreateZExt(count, i64);
  b.CreateCondBr(b.CreateAnd(argvMissing, b.CreateICmpNE(count, b.getInt32(0))), bad, argsHead);
  b.SetInsertPoint(argsHead);
  auto *argIndex = b.CreatePHI(i64, 2);
  argIndex->addIncoming(b.getInt64(0), vectors);
  b.CreateCondBr(b.CreateICmpULT(argIndex, wideCount), argsItem, argsEnd);
  b.SetInsertPoint(argsItem);
  auto *argValue = b.CreateLoad(ptr, b.CreateGEP(ptr, actualArgv, argIndex));
  argValue->setVolatile(true);
  b.CreateCondBr(b.CreateICmpEQ(argValue, null), bad, argsString);
  b.SetInsertPoint(argsString);
  b.CreateCall(stringCheck, {argValue});
  auto *nextArg = b.CreateAdd(argIndex, b.getInt64(1));
  argIndex->addIncoming(nextArg, argsString);
  b.CreateBr(argsHead);
  b.SetInsertPoint(argsEnd);
  auto *terminator = b.CreateLoad(ptr, b.CreateGEP(ptr, actualArgv, wideCount));
  terminator->setVolatile(true);
  b.CreateCondBr(b.CreateICmpEQ(terminator, null), envHead, bad);
  b.SetInsertPoint(envHead);
  auto *envIndex = b.CreatePHI(i64, 2);
  envIndex->addIncoming(b.getInt64(0), argsEnd);
  auto *envValue = b.CreateLoad(ptr, b.CreateGEP(ptr, actualEnvp, envIndex));
  envValue->setVolatile(true);
  b.CreateCondBr(b.CreateICmpEQ(envValue, null), invoke, envString);
  b.SetInsertPoint(envString);
  b.CreateCall(stringCheck, {envValue});
  auto *nextEnv = b.CreateAdd(envIndex, b.getInt64(1));
  envIndex->addIncoming(nextEnv, envString);
  b.CreateBr(envHead);
  b.SetInsertPoint(invoke);
  b.CreateCall(prepare, {count, actualArgv, actualEnvp});
  SmallVector<Value *, 3> forwarded;
  if (params) forwarded = {count, actualArgv};
  if (params == 3) forwarded.push_back(actualEnvp);
  auto *status = b.CreateCall(user, forwarded);
  status->setCallingConv(user->getCallingConv());
  b.CreateCall(exit, {status});
  b.CreateUnreachable();
  b.SetInsertPoint(bad);
  b.CreateCall(fault, {b.getInt64(7)});
  b.CreateUnreachable();

  if (verifyModule(m, &errs())) return fail("synthesised module failed verification");
  std::error_code error;
  raw_fd_ostream output(argv[2], error, sys::fs::OF_None);
  if (error) return fail(error.message());
  WriteBitcodeToFile(m, output);
  raw_fd_ostream report(argv[4], error, sys::fs::OF_Text);
  if (error) return fail(error.message());
  report << json::Value(json::Object{
      {"schema", "bennett-driver-process-entry-1"}, {"entry", entry},
      {"user_entry", user->getName().str()}, {"user_parameters", params},
      {"wrapper_type", "i32 (i32, ptr, ptr)"},
      {"prepare_type", "void (i32, ptr, ptr)"},
      {"fresh_static_images", "published runtimes bitcode"},
      {"null_vectors", "nonnull empty vectors; positive argc requires argv"}});
  return 0;
}
