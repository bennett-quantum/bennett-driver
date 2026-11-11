// Comparison-only storage placement and native transport of the published exit EH record.
#include "llvm/Bitcode/BitcodeWriter.h"
#include "llvm/IR/GlobalAlias.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Instructions.h"
#include "llvm/Support/ModRef.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include <set>
using namespace llvm;
static int fail(const Twine &text) {errs()<<"BD-E-NATIVE-LAYOUT: "<<text<<'\n';return 1;}
static bool honourExit(Module &module) {
 auto *state=module.getGlobalVariable("__bennett_rt_eh",true);
 if(!state)return true;
 auto *type=dyn_cast<StructType>(state->getValueType());
 if(!type||type->getNumElements()!=3||!type->getElementType(0)->isIntegerTy(32)||!type->getElementType(1)->isIntegerTy(32)||!type->getElementType(2)->isPointerTy())return false;
 LLVMContext &context=module.getContext();
 auto *poll=Function::Create(FunctionType::get(Type::getVoidTy(context),false),GlobalValue::InternalLinkage,"__bennett_driver_exit_poll",module);
 auto *entry=BasicBlock::Create(context,"entry",poll),*exit=BasicBlock::Create(context,"exit",poll),*resume=BasicBlock::Create(context,"resume",poll);
 IRBuilder<> builder(entry);
 auto *active=builder.CreateLoad(builder.getInt32Ty(),builder.CreateStructGEP(type,state,0));
 builder.CreateCondBr(builder.CreateICmpEQ(active,builder.getInt32(4)),exit,resume);
 builder.SetInsertPoint(exit);
 auto *status=builder.CreateLoad(builder.getInt32Ty(),builder.CreateStructGEP(type,state,1));
 auto finish=module.getOrInsertFunction("__bennett_driver_native_exit",FunctionType::get(builder.getVoidTy(),{builder.getInt32Ty()},false));
 builder.CreateCall(finish,{status});builder.CreateUnreachable();
 builder.SetInsertPoint(resume);builder.CreateRetVoid();
 for(auto &function:module) {
  if(function.isDeclaration()||!function.hasFnAttribute("bennett.native.materialised.sha256"))continue;
  function.setMemoryEffects(MemoryEffects::unknown());
  for(auto attribute:{Attribute::WillReturn,Attribute::NoSync,Attribute::NoFree,Attribute::Speculatable,Attribute::NoCallback})function.removeFnAttr(attribute);
  for(auto &block:function) {
   Instruction *point=block.getTerminator();
   Instruction *previous=point->getPrevNode();
   while(previous) {
    auto *call=dyn_cast<CallBase>(previous);auto *callee=call?call->getCalledFunction():nullptr;
    if(!callee||callee->getName().take_front(9)!="llvm.dbg.")break;
    previous=previous->getPrevNode();
   }
   if(isa<ReturnInst>(point))if(auto *call=dyn_cast_or_null<CallInst>(previous))if(call->isMustTailCall())point=call;
   IRBuilder<> before(point);before.CreateCall(poll);
  }
 }
 for(auto &function:module)for(auto &block:function)for(auto &instruction:block)if(auto *call=dyn_cast<CallBase>(&instruction)) {
  auto *callee=call->getCalledFunction();
  if(!call->isIndirectCall() && (!callee||!callee->hasFnAttribute("bennett.native.materialised.sha256")))continue;
  call->setMemoryEffects(MemoryEffects::unknown());
  for(auto attribute:{Attribute::WillReturn,Attribute::NoSync,Attribute::NoFree,Attribute::Speculatable,Attribute::NoCallback})call->removeFnAttr(attribute);
 }
 return true;
}
int main(int argc,char **argv) {
 if(argc!=4)return fail("expected INPUT.bc LAYOUT.json OUTPUT.bc");
 LLVMContext context;SMDiagnostic diagnostic;
 auto module=parseIRFile(argv[1],diagnostic,context);
 if(!module){diagnostic.print(argv[0],errs());return 1;}
 auto text=MemoryBuffer::getFile(argv[2]);if(!text)return fail("cannot read layout");
 auto value=json::parse((*text)->getBuffer());if(!value)return fail("invalid layout JSON");
 auto *layout=value->getAsObject();if(!layout)return fail("layout is not an object");
 auto *bindings=layout->getArray("native_bindings");if(!bindings)return fail("missing binding inventory");
 std::set<GlobalVariable *> seen;
 for(auto &item:*bindings) {
  auto *binding=item.getAsObject();if(!binding)return fail("invalid binding");
  auto symbol=binding->getString("native_symbol");auto *sections=binding->getArray("sections");
  if(!symbol||!sections||sections->size()!=1||!(*sections)[0].getAsString())return fail("missing exact native section");
  auto *value=module->getNamedValue(*symbol);if(!value)return fail("mapped symbol absent: "+*symbol);
  GlobalObject *object=dyn_cast<GlobalObject>(value);
  if(auto *alias=dyn_cast<GlobalAlias>(value))object=alias->getAliaseeObject();
  auto *global=dyn_cast_or_null<GlobalVariable>(object);
  if(!global||global->isDeclaration()||!seen.insert(global).second)return fail("mapped symbol lacks unique storage: "+*symbol);
  global->setUnnamedAddr(GlobalValue::UnnamedAddr::None);
  global->setSection(*(*sections)[0].getAsString());
 }
 if(!honourExit(*module))return fail("unexpected published EH record ABI");
 if(verifyModule(*module,&errs()))return fail("sectioned module failed verification");
 std::error_code error;raw_fd_ostream output(argv[3],error,sys::fs::OF_None);
 if(error)return fail(error.message());WriteBitcodeToFile(*module,output);
 return 0;
}
