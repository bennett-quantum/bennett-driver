// Driver-owned ELF init/fini link inventory after link selection, before S2/S7.
#include "llvm/Bitcode/BitcodeWriter.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/GlobalAlias.h"
#include "llvm/IR/IRBuilder.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Operator.h"
#include "llvm/IR/ValueHandle.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/FormatVariadic.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include <algorithm>
#include <vector>
using namespace llvm;

static bool fail(const Twine &message) {errs()<<"BD-E-PROCESS-LINK: "<<message<<'\n';return false;}
// Associations can refer to section objects replaced by aliases below; track RAUW.
struct Registration {TrackingVH<Constant> function,associated;uint32_t priority;uint64_t order;GlobalVariable *owner=nullptr;};
struct Piece {GlobalVariable *global;size_t count;};
struct Table {
 StringRef kind,startName,endName,metadataName;
 std::vector<Registration> entries;
 std::vector<Piece> pieces;
 Constant *start=nullptr,*end=nullptr;
 GlobalVariable *storage=nullptr;
 uint64_t startOffset=0,endOffset=0;
 bool provided=false;
};
static Constant *unaliased(Constant *value) {
 value=cast<Constant>(value->stripPointerCasts());
 while(auto *alias=dyn_cast<GlobalAlias>(value))value=cast<Constant>(alias->getAliasee()->stripPointerCasts());
 return value;
}
static Function *callback(Constant *value) {return dyn_cast<Function>(unaliased(value));}
static bool add(Table &table,Constant *function,Constant *associated,uint32_t priority,uint64_t order) {
 auto *target=callback(function);
 if(!target||target->isDeclarationForLinker()||!target->getReturnType()->isVoidTy()||target->arg_size()!=0||target->isVarArg())
  return fail("init/fini callback needs its resolved void() definition");
 if(!associated->isNullValue()) {
  auto *object=dyn_cast<GlobalObject>(unaliased(associated));
  if(!object||object->isDeclarationForLinker())return fail("associated init/fini COMDAT was not resolved by the IR link");
 }
 table.entries.push_back({function,associated,priority,order});return true;
}
static bool metadata(Table &table,GlobalVariable &global,uint64_t &order) {
 if(!global.hasInitializer())return fail("undefined LLVM init/fini registration list");
 auto *array=dyn_cast<ArrayType>(global.getValueType());
 if(!array)return fail("LLVM init/fini list is not an array");
 for(uint64_t i=0;i<array->getNumElements();i++) {
  auto *item=global.getInitializer()->getAggregateElement(i);
  auto *priority=item?dyn_cast_or_null<ConstantInt>(item->getAggregateElement(0U)):nullptr;
  auto *function=item?item->getAggregateElement(1U):nullptr;
  auto *associated=item?item->getAggregateElement(2U):nullptr;
  if(!priority||priority->getBitWidth()!=32||!function||!associated)return fail("invalid LLVM init/fini entry");
  // LLVM's null-function metadata slots are not emitted callbacks.
  if(function->isNullValue())continue;
  if(!add(table,function,associated,(uint32_t)priority->getZExtValue(),order++))return false;
 }
 return true;
}
static bool section(Table &table,GlobalVariable &global,uint32_t priority,uint64_t &order) {
 if(!global.hasInitializer())return fail("undefined init/fini section contribution");
 auto *pointer=PointerType::getUnqual(global.getContext());
 size_t count=1;
 if(auto *array=dyn_cast<ArrayType>(global.getValueType())) {
  if(array->getElementType()!=pointer)return fail("init/fini section must contain target function pointers");
  count=array->getNumElements();
 } else if(global.getValueType()!=pointer)return fail("init/fini section is not pointer storage");
 table.pieces.push_back({&global,count});
 for(size_t i=0;i<count;i++) {
  auto *function=count==1&&global.getValueType()==pointer?global.getInitializer():global.getInitializer()->getAggregateElement((unsigned)i);
  if(!function||!add(table,function,ConstantPointerNull::get(pointer),priority,order++))return false;
  table.entries.back().owner=&global;
 }
 return true;
}
static bool collect(Module &module,std::vector<Table> &tables,std::vector<GlobalVariable *> &lists) {
 uint64_t order=0;
 for(auto &global:module.globals()) {
  for(auto &table:tables) {
   if(!table.metadataName.empty()&&global.getName()==table.metadataName) {
    if(!metadata(table,global,order))return false;
    lists.push_back(&global);
   }
   if(!global.hasSection())continue;
   std::string prefix="."+table.kind.str()+"_array";
   StringRef name=global.getSection();
   if(name!=prefix&&!name.starts_with(prefix+"."))continue;
   uint32_t priority=65535;
   if(name!=prefix&&name.drop_front(prefix.size()+1).getAsInteger(10,priority))return fail("invalid init/fini section priority");
   if(!section(table,global,priority,order))return false;
  }
 }
 // Equal priorities retain input order, including intentional duplicate callbacks.
 for(auto &table:tables)std::stable_sort(table.entries.begin(),table.entries.end(),[](const auto &a,const auto &b){return a.priority<b.priority;});
 return true;
}
static bool location(Constant *value,const DataLayout &layout,GlobalVariable *&base,uint64_t &offset) {
 offset=0;
 for(;;) {
  value=cast<Constant>(value->stripPointerCasts());
  if(auto *alias=dyn_cast<GlobalAlias>(value)){value=alias->getAliasee();continue;}
  if(auto *gep=dyn_cast<GEPOperator>(value)) {
   APInt delta(layout.getIndexSizeInBits(0),0);
   if(!gep->accumulateConstantOffset(layout,delta)||delta.isNegative())return fail("nonconstant init/fini boundary offset");
   offset+=delta.getZExtValue();value=cast<Constant>(gep->getPointerOperand());continue;
  }
  base=dyn_cast<GlobalVariable>(value);
  return base&&base->hasInitializer();
 }
}
static bool defined(GlobalValue *value) {return value&&!value->isDeclarationForLinker();}
static bool supplied(Module &module,Table &table) {
 auto *start=module.getNamedValue(table.startName),*end=module.getNamedValue(table.endName);
 if(!defined(start)&&!defined(end))return true;
 if(!defined(start)||!defined(end))return fail("only one init/fini boundary has a definition");
 GlobalVariable *first=nullptr,*last=nullptr;
 if(!location(start,module.getDataLayout(),first,table.startOffset)||!location(end,module.getDataLayout(),last,table.endOffset)||first!=last)
  return fail("provided init/fini bounds need one actual backing array");
 uint64_t width=module.getDataLayout().getPointerSize(0),bytes=module.getDataLayout().getTypeAllocSize(first->getValueType()).getFixedValue();
 if(table.endOffset<table.startOffset||table.endOffset>bytes||table.startOffset%width||table.endOffset%width)return fail("invalid provided init/fini extent");
 size_t count=(table.endOffset-table.startOffset)/width;
 std::vector<Registration> actual;
 for(size_t i=0;i<count;i++) {
  size_t index=table.startOffset/width+i;
  Constant *value=first->getValueType()->isPointerTy()&&index==0?first->getInitializer():first->getInitializer()->getAggregateElement((unsigned)index);
  if(!value||!callback(value))return fail("provided init/fini extent is not a resolved callback array");
  actual.push_back({value,ConstantPointerNull::get(PointerType::getUnqual(module.getContext())),65535,i});
 }
 if(!table.entries.empty()) {
  if(table.entries.size()!=actual.size())return fail("provided init/fini bounds exclude linked registrations");
  for(size_t i=0;i<actual.size();i++)if(callback(actual[i].function)!=callback(table.entries[i].function))return fail("provided init/fini order conflicts with linked registrations");
 } else table.entries=std::move(actual);
 table.storage=first;table.start=start;table.end=end;table.provided=true;return true;
}
static Constant *element(Module &module,GlobalVariable *storage,uint64_t index) {
 auto *integer=Type::getInt64Ty(module.getContext());
 Constant *indices[]={ConstantInt::get(integer,0),ConstantInt::get(integer,index)};
 return ConstantExpr::getGetElementPtr(storage->getValueType(),storage,indices);
}
static GlobalAlias *bind(Module &module,StringRef name,Type *type,Constant *address) {
 auto *old=module.getNamedValue(name);
 auto *alias=GlobalAlias::create(type,0,GlobalValue::ExternalLinkage,name+".resolved",address,&module);
 alias->setVisibility(GlobalValue::HiddenVisibility);alias->setDSOLocal(true);
 if(old){old->replaceAllUsesWith(alias);alias->takeName(old);old->eraseFromParent();}else alias->setName(name);
 return alias;
}
static bool materialise(Module &module,Table &table) {
 // Existing definitions are authoritative when they cover the complete inventory.
 if(table.provided)return true;
 auto &context=module.getContext();auto *pointer=PointerType::getUnqual(context);
 if(table.entries.empty()) {
  // Zero entries come from the complete link inventory. A linker location is
  // an alias one past the real process empty-argv object: no padding/table byte.
  auto *vectors=module.getNamedMetadata("bennett.driver.process_vectors");
  auto *reference=vectors&&vectors->getNumOperands()==1?dyn_cast<ValueAsMetadata>(vectors->getOperand(0)->getOperand(0)):nullptr;
  auto *anchor=reference?dyn_cast<GlobalVariable>(reference->getValue()):nullptr;
  if(!anchor||!anchor->hasInitializer())return fail("missing real process vector for empty link location");
  table.storage=anchor;table.startOffset=table.endOffset=module.getDataLayout().getPointerSize(0);
  table.start=table.end=element(module,anchor,1);
 } else {
  std::vector<Constant *> values;for(auto &entry:table.entries)values.push_back(entry.function);
  auto *type=ArrayType::get(pointer,values.size());
  table.storage=new GlobalVariable(module,type,false,GlobalValue::PrivateLinkage,ConstantArray::get(type,values),".bennett.driver."+table.kind+"_array");
  table.storage->setAlignment(module.getDataLayout().getABITypeAlign(pointer));
  table.start=element(module,table.storage,0);table.end=element(module,table.storage,values.size());
  table.endOffset=values.size()*module.getDataLayout().getPointerSize(0);
 }
 for(auto &piece:table.pieces) {
  size_t first=0;
  if(piece.count) {
   auto found=std::find_if(table.entries.begin(),table.entries.end(),[&](const auto &row){return row.owner==piece.global;});
   if(found==table.entries.end())return fail("lost init/fini section contribution");
   first=found-table.entries.begin();
  }
  Constant *address=table.entries.empty()?table.start:element(module,table.storage,first);
  auto *view=GlobalAlias::create(piece.global->getValueType(),0,piece.global->getLinkage(),piece.global->getName()+".view",address,&module);
  view->setVisibility(piece.global->getVisibility());view->setDSOLocal(piece.global->isDSOLocal());
  piece.global->replaceAllUsesWith(view);view->takeName(piece.global);piece.global->eraseFromParent();
 }
 auto *start=bind(module,table.startName,ArrayType::get(pointer,table.entries.size()),table.start);
 auto *end=bind(module,table.endName,ArrayType::get(pointer,0),table.end);
 table.start=start;table.end=end;
 return true;
}
static void walk(IRBuilder<> &builder,Function *runner,Constant *start,Constant *end,StringRef name) {
 auto &context=runner->getContext();auto *pointer=PointerType::getUnqual(context);
 auto *before=builder.GetInsertBlock(),*head=BasicBlock::Create(context,name+".head",runner),*body=BasicBlock::Create(context,name+".body",runner),*done=BasicBlock::Create(context,name+".done",runner);
 builder.CreateBr(head);builder.SetInsertPoint(head);
 auto *cursor=builder.CreatePHI(pointer,2);cursor->addIncoming(start,before);
 builder.CreateCondBr(builder.CreateICmpNE(cursor,end),body,done);builder.SetInsertPoint(body);
 auto *function=builder.CreateLoad(pointer,cursor);
 builder.CreateCall(FunctionType::get(builder.getVoidTy(),false),function,{});
 auto *next=builder.CreateGEP(pointer,cursor,builder.getInt64(1));cursor->addIncoming(next,body);builder.CreateBr(head);builder.SetInsertPoint(done);
}
static bool runner(Module &module,std::vector<Table> &tables) {
 auto *function=module.getFunction(".bennett.driver.run.init");
 if(!function||!function->isDeclaration())return fail("expected one driver init-dispatch declaration");
 auto *block=BasicBlock::Create(module.getContext(),"entry",function);IRBuilder<> builder(block);
 walk(builder,function,tables[0].start,tables[0].end,"preinit");
 auto *runtime=module.getNamedValue("__libc_start_init");
 if(defined(runtime)) {
  auto *target=callback(runtime);if(!target||target->arg_size()!=0||!target->getReturnType()->isVoidTy())return fail("incompatible real libc init dispatcher");
  builder.CreateCall(target->getFunctionType(),runtime,{});
 } else {
  auto *hook=module.getNamedValue("_init");
  if(defined(hook)) {
   auto *target=callback(hook);if(!target||target->arg_size()!=0||!target->getReturnType()->isVoidTy())return fail("incompatible _init definition");
   builder.CreateCall(target->getFunctionType(),hook,{});
  } else if(hook&&!hook->hasExternalWeakLinkage())return fail("unresolved strong _init hook");
  walk(builder,function,tables[1].start,tables[1].end,"init");
 }
 builder.CreateRetVoid();return true;
}
int main(int argc,char **argv) {
 if(argc!=4)return fail("expected INPUT.bc OUTPUT.bc REPORT.json")?0:1;
 LLVMContext context;SMDiagnostic diagnostic;auto module=parseIRFile(argv[1],diagnostic,context);
 if(!module){diagnostic.print(argv[0],errs());return 1;}
 std::vector<Table> tables={{"preinit","__preinit_array_start","__preinit_array_end",""},{"init","__init_array_start","__init_array_end","llvm.global_ctors"},{"fini","__fini_array_start","__fini_array_end","llvm.global_dtors"}};
 std::vector<GlobalVariable *> lists;
 if(!collect(*module,tables,lists))return 1;
 for(auto &table:tables)if(!supplied(*module,table)||!materialise(*module,table))return 1;
 for(auto *list:lists)list->eraseFromParent();
 if(!runner(*module,tables))return 1;
 json::Array descriptions;auto *named=module->getOrInsertNamedMetadata("bennett.driver.init_fini");
 for(auto &table:tables) {
  json::Array entries;
  for(auto &row:table.entries) {
   auto *function=callback(row.function);
   entries.push_back(json::Object{{"function",function->getName()},{"priority",(int64_t)row.priority},{"input_order",(int64_t)row.order},{"associated",row.associated->isNullValue()?"":unaliased(row.associated)->getName()}});
   Metadata *fields[]={MDString::get(context,table.kind),ConstantAsMetadata::get(row.function),ConstantAsMetadata::get(row.associated),ConstantAsMetadata::get(ConstantInt::get(Type::getInt32Ty(context),row.priority))};
   named->addOperand(MDNode::get(context,fields));
  }
  descriptions.push_back(json::Object{{"kind",table.kind},{"storage",table.storage->getName()},{"provided",table.provided},{"start_offset",(int64_t)table.startOffset},{"end_offset",(int64_t)table.endOffset},{"entries",std::move(entries)}});
 }
 if(verifyModule(*module,&errs()))return 1;
 std::error_code error;raw_fd_ostream output(argv[2],error,sys::fs::OF_None);if(error)return fail(error.message())?0:1;WriteBitcodeToFile(*module,output);
 raw_fd_ostream report(argv[3],error,sys::fs::OF_Text);if(error)return fail(error.message())?0:1;
 report<<formatv("{0:2}\n",json::Value(json::Object{{"schema","bennett-driver-init-fini-1"},{"tables",std::move(descriptions)}}));
 return 0;
}
