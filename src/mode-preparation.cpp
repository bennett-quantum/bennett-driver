#include "llvm/Bitcode/BitcodeWriter.h"
#include "llvm/IR/Constants.h"
#include "llvm/IR/Instructions.h"
#include "llvm/IR/Intrinsics.h"
#include "llvm/IR/Module.h"
#include "llvm/IR/Verifier.h"
#include "llvm/IRReader/IRReader.h"
#include "llvm/Support/FileSystem.h"
#include "llvm/Support/JSON.h"
#include "llvm/Support/MemoryBuffer.h"
#include "llvm/Support/SourceMgr.h"
#include "llvm/Support/raw_ostream.h"
#include <set>
#include <limits>
using namespace llvm;
static int fail(const Twine &s) { errs()<<"BD-E-PREPARATION: "<<s<<'\n'; return 1; }
static Expected<json::Value> load(StringRef path) {
  auto bytes=MemoryBuffer::getFile(path);
  if (!bytes) return createStringError(bytes.getError(), "cannot read %s", path.str().c_str());
  return json::parse((*bytes)->getBuffer());
}
static bool scalable(Type *type) {
  if(auto *v=dyn_cast<VectorType>(type))return v->getElementCount().isScalable();
  if(auto *a=dyn_cast<ArrayType>(type))return scalable(a->getElementType());
  if(auto *s=dyn_cast<StructType>(type))for(auto *element:s->elements())if(scalable(element))return true;
  return false;
}
int main(int argc,char **argv) {
  if(argc!=5)return fail("expected INPUT OUTPUT REQUEST REPORT");
  LLVMContext context; SMDiagnostic diagnostic;
  auto module=parseIRFile(argv[1],diagnostic,context);
  if(!module){diagnostic.print(argv[0],errs());return 1;}
  auto config=load(argv[3]);if(!config)return fail(toString(config.takeError()));
  auto *request=config->getAsObject();if(!request)return fail("request must be an object");
  Module &m=*module;json::Object report;json::Array images;
  if(auto path=request->getString("snapshot")) {
    auto dump=load(*path);if(!dump)return fail(toString(dump.takeError()));
    auto *object=dump->getAsObject();
    if(!object||object->size()!=2||object->getString("schema")!="bennett-driver-snapshot-1")
      return fail("expected snapshot schema bennett-driver-snapshot-1 and globals");
    auto *globals=object->getObject("globals");if(!globals)return fail("snapshot globals must be an object");
    for(auto &item:*globals) {
      auto *global=m.getNamedGlobal(item.first);auto hex=item.second.getAsString();
      if(!global||global->isDeclaration()||global->isConstant())return fail("snapshot requires a defined mutable global: "+item.first);
      if(!hex||hex->size()%2)return fail("snapshot image must be even-length hex: "+item.first);
      auto size=m.getDataLayout().getTypeAllocSize(global->getValueType());
      if(size.isScalable()||hex->size()/2!=size.getFixedValue())return fail("snapshot image extent differs from global: "+item.first);
      SmallVector<uint8_t,32> bytes;
      for(size_t i=0;i<hex->size();i+=2){unsigned value;if(hex->substr(i,2).getAsInteger(16,value))return fail("invalid snapshot hex");bytes.push_back(value);}
      auto *initializer=ConstantDataArray::get(context,bytes);
      auto linkage=global->hasCommonLinkage()?GlobalValue::ExternalLinkage:global->getLinkage();
      auto *replacement=new GlobalVariable(m,initializer->getType(),false,linkage,initializer,"",nullptr,global->getThreadLocalMode(),global->getAddressSpace());
      replacement->copyAttributesFrom(global);
      replacement->setAlignment(global->getAlign().valueOrOne()<m.getDataLayout().getABITypeAlign(global->getValueType())?
        m.getDataLayout().getABITypeAlign(global->getValueType()):global->getAlign().valueOrOne());
      replacement->takeName(global);global->replaceAllUsesWith(replacement);global->eraseFromParent();
      images.push_back(item.first.str());
    }
  }
  report["snapshot_globals"]=std::move(images);
  SmallVector<Metadata*,8> names;std::set<std::string> seen;json::Array classReport;
  auto addClass=[&](StringRef s){if(seen.insert(s.str()).second){names.push_back(MDString::get(context,s));classReport.push_back(s.str());}};
  if(auto *old=m.getModuleFlag("bennett.classes")) {
    auto *list=dyn_cast<MDNode>(old);if(!list)return fail("bennett.classes must contain a list");
    for(auto &operand:list->operands()){auto *name=dyn_cast_or_null<MDString>(operand.get());if(!name)return fail("class name must be a string");addClass(name->getString());}
  }
  if(auto *classes=request->getArray("classes"))for(auto &value:*classes){auto name=value.getAsString();if(!name||name->empty())return fail("empty class name");addClass(*name);}
  if(!names.empty())m.setModuleFlag(Module::AppendUnique,"bennett.classes",MDNode::get(context,names));
  report["classes"]=std::move(classReport);
  if(auto value=request->getString("vscale")) {
    uint64_t v;if(value->getAsInteger(10,v)||!v)return fail("vscale must be a positive 64-bit link value");
    SmallVector<CallInst*,8> calls;
    bool any=false,allFixed=true,vectors=false;std::optional<unsigned> fixed;
    for(auto &f:m)if(!f.isDeclaration()){
      bool uses=scalable(f.getReturnType());
      for(auto &arg:f.args())uses|=scalable(arg.getType());
      for(auto &block:f)for(auto &instruction:block){
        bool vector=scalable(instruction.getType());
        for(auto &operand:instruction.operands())vector|=scalable(operand->getType());
        vectors|=vector;uses|=vector;
        if(auto *call=dyn_cast<CallInst>(&instruction))if(call->getIntrinsicID()==Intrinsic::vscale){calls.push_back(call);uses=true;}
      }
      if(uses){any=true;auto range=f.getFnAttribute(Attribute::VScaleRange);
        if(!range.isValid()||!range.getVScaleRangeMax()||*range.getVScaleRangeMax()!=range.getVScaleRangeMin())allFixed=false;
        else {unsigned n=range.getVScaleRangeMin();if(fixed&&*fixed!=n)allFixed=false;fixed=n;}
      }
    }
    if(any&&allFixed&&fixed)v=*fixed;
    bool exact=(v<=std::numeric_limits<unsigned>::max())&&!(v&(v-1));
    if(vectors&&!exact)return fail("BD-B-MODE-BACKEND: this fixed scalable-vector value requires the backend vscale control beyond LLVM exact-range attributes; capability remains required");
    if(exact)for(auto &f:m)if(!f.isDeclaration())f.addFnAttr(Attribute::getWithVScaleRangeArgs(context,v,v));
    for(auto *call:calls){call->replaceAllUsesWith(ConstantInt::get(call->getType(),v));call->eraseFromParent();}
    report["vscale"]=v;
  }
  if(verifyModule(m,&errs()))return fail("prepared module failed verification");
  std::error_code error;raw_fd_ostream output(argv[2],error,sys::fs::OF_None);
  if(error)return fail(error.message());WriteBitcodeToFile(m,output);
  raw_fd_ostream record(argv[4],error,sys::fs::OF_Text);
  if(error)return fail(error.message());record<<json::Value(std::move(report));return 0;
}
