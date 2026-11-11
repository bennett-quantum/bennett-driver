#define _GNU_SOURCE
#include <dlfcn.h>
#include <elf.h>
#include <errno.h>
#include <fcntl.h>
#include <link.h>
#include <limits.h>
#include <linux/audit.h>
#include <linux/filter.h>
#include <linux/seccomp.h>
#include <setjmp.h>
#include <signal.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <unistd.h>
#include <ucontext.h>
#ifndef SYS_SECCOMP
#define SYS_SECCOMP 1
#endif
#include "native-provider-api.h"
static sigjmp_buf escape;
static volatile sig_atomic_t component_exit, component_status, component_signal;
static uintptr_t text_begin, text_end;
static int fail(const char *what) {
 fprintf(stderr,"BD-E-NATIVE-PROVIDER: %s: %s\n",what,strerror(errno)); return 125;
}
static unsigned char *bytes(const char *path,size_t *size) {
 FILE *f=fopen(path,"rb"); if(!f) return NULL;
 if(fseek(f,0,SEEK_END) || ftell(f)<0) {fclose(f);return NULL;}
 *size=(size_t)ftell(f); rewind(f);
 unsigned char *b=malloc(*size?*size:1);
 if(!b || fread(b,1,*size,f)!=*size) {free(b);fclose(f);return NULL;}
 fclose(f);return b;
}
static uintptr_t component_symbol(const unsigned char *file,size_t size,const char *name) {
 const Elf64_Ehdr *e=(const void *)file;
 if(e->e_shoff>size || e->e_shnum>(size-e->e_shoff)/sizeof(Elf64_Shdr)) return 0;
 const Elf64_Shdr *sections=(const void *)(file+e->e_shoff);
 for(unsigned i=0;i<e->e_shnum;i++) {
  const Elf64_Shdr *s=&sections[i];
  if(s->sh_type!=SHT_SYMTAB)continue;
  if(s->sh_offset>size || s->sh_size>size-s->sh_offset || s->sh_link>=e->e_shnum)return 0;
  const Elf64_Shdr *strings=&sections[s->sh_link];
  if(strings->sh_offset>size || strings->sh_size>size-strings->sh_offset)return 0;
  const Elf64_Sym *symbols=(const void *)(file+s->sh_offset);
  for(size_t j=0;j<s->sh_size/sizeof(*symbols);j++) {
   const Elf64_Sym *v=&symbols[j];
   if(v->st_name>=strings->sh_size)continue;
   const char *text=(const void *)(file+strings->sh_offset+v->st_name);
   if(!memchr(text,0,strings->sh_size-v->st_name))return 0;
   if(v->st_shndx!=SHN_UNDEF && !strcmp(text,name))return (uintptr_t)v->st_value;
  }
 }
 return 0;
}
static int map_component(const unsigned char *file,size_t size,uintptr_t *text_low,uintptr_t *text_high) {
 if(size<sizeof(Elf64_Ehdr))return fail("short ELF");
 const Elf64_Ehdr *e=(const void *)file;
 if(memcmp(e->e_ident,ELFMAG,SELFMAG) || e->e_ident[EI_CLASS]!=ELFCLASS64 || e->e_machine!=EM_X86_64 || e->e_type!=ET_EXEC)
  return fail("component must be a fixed x86-64 ELF");
 if(e->e_phoff>size || e->e_phnum>(size-e->e_phoff)/sizeof(Elf64_Phdr))return fail("ELF program table");
 const Elf64_Phdr *ph=(const void *)(file+e->e_phoff);
 *text_low=UINTPTR_MAX;*text_high=0;
 for(unsigned i=0;i<e->e_phnum;i++) {
  const Elf64_Phdr *p=&ph[i];
  if(p->p_type==PT_DYNAMIC || p->p_type==PT_INTERP)return fail("component has dynamic imports");
  if(p->p_type!=PT_LOAD || !p->p_memsz)continue;
  if(p->p_offset>size || p->p_filesz>size-p->p_offset || p->p_filesz>p->p_memsz || p->p_memsz>UINTPTR_MAX-p->p_vaddr)
   return fail("component range");
  uintptr_t start=p->p_vaddr&~(uintptr_t)4095;
  size_t length=((p->p_vaddr+p->p_memsz+4095)&~(uintptr_t)4095)-start;
  void *mapping=mmap((void *)start,length,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED_NOREPLACE,-1,0);
  if(mapping==MAP_FAILED)return fail("fixed component mapping (no relocation allowed)");
  if(mapping!=(void *)start){munmap(mapping,length);errno=EADDRNOTAVAIL;return fail("kernel relocated component mapping");}
  memcpy((void *)p->p_vaddr,file+p->p_offset,p->p_filesz);
  int prot=((p->p_flags&PF_R)?PROT_READ:0)|((p->p_flags&PF_W)?PROT_WRITE:0)|((p->p_flags&PF_X)?PROT_EXEC:0);
  if(mprotect(mapping,length,prot))return fail("component protections");
  if(p->p_flags&PF_X) {if(p->p_vaddr<*text_low)*text_low=p->p_vaddr;if(p->p_vaddr+p->p_memsz>*text_high)*text_high=p->p_vaddr+p->p_memsz;}
 }
 return *text_high?0:fail("component has no text");
}
static void exited(int signal,siginfo_t *info,void *context) {
 uintptr_t ip=(uintptr_t)((ucontext_t *)context)->uc_mcontext.gregs[REG_RIP];
 if(signal==SIGILL && ip>=text_begin && ip<text_end) {
  component_signal=SIGILL;
  siglongjmp(escape,1);
 }
 if(signal!=SIGSYS || info->si_code!=SYS_SECCOMP)_Exit(125);
 component_status=(int)((ucontext_t *)context)->uc_mcontext.gregs[REG_RDI];
 component_exit=1;
 siglongjmp(escape,1);
}
/* Trap only the component's real Linux exit syscall; provider/bootstrap remain ordinary host code. */
static void materialised_exit(int status) {
 component_status=status;component_exit=1;
 siglongjmp(escape,1);
}
static int catch_exit(uintptr_t low,uintptr_t high) {
 text_begin=low;text_end=high;
 struct sigaction sa={0};sa.sa_sigaction=exited;sa.sa_flags=SA_SIGINFO;sigemptyset(&sa.sa_mask);
 if(sigaction(SIGSYS,&sa,NULL)||sigaction(SIGILL,&sa,NULL))return fail("component termination handlers");
 /* Lexicographic 64-bit instruction-address bounds; no smaller address cap. */
 struct sock_filter code[]={
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,arch)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,AUDIT_ARCH_X86_64,0,14),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,instruction_pointer)+4),
  BPF_JUMP(BPF_JMP|BPF_JGE|BPF_K,(uint32_t)(low>>32),0,12),
  BPF_JUMP(BPF_JMP|BPF_JGT|BPF_K,(uint32_t)(high>>32),11,0),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,(uint32_t)(low>>32),0,3),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,instruction_pointer)),
  BPF_JUMP(BPF_JMP|BPF_JGE|BPF_K,(uint32_t)low,0,8),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,instruction_pointer)+4),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,(uint32_t)(high>>32),0,2),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,instruction_pointer)),
  BPF_JUMP(BPF_JMP|BPF_JGE|BPF_K,(uint32_t)high,4,0),
  BPF_STMT(BPF_LD|BPF_W|BPF_ABS,offsetof(struct seccomp_data,nr)),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_exit,1,0),
  BPF_JUMP(BPF_JMP|BPF_JEQ|BPF_K,SYS_exit_group,0,1),
  BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_TRAP),
  BPF_STMT(BPF_RET|BPF_K,SECCOMP_RET_ALLOW)};
 struct sock_fprog program={(unsigned short)(sizeof(code)/sizeof(*code)),code};
 if(prctl(PR_SET_NO_NEW_PRIVS,1,0,0,0) || prctl(PR_SET_SECCOMP,SECCOMP_MODE_FILTER,&program))return fail("component exit interception");
 return 0;
}
static void json_string(FILE *out,const char *text) {
 fputc('"',out);
 for(const unsigned char *p=(const void *)text;*p;p++) {
  if(*p=='"'||*p=='\\'){fputc('\\',out);fputc(*p,out);}
  else if(*p<32)fprintf(out,"\\u%04x",*p);else fputc(*p,out);
 }
 fputc('"',out);
}
static int provider_report(const char *path,void *handle,Lmid_t namespace,struct driver_native_api *api,int unloaded) {
 FILE *out=fopen(path,"w");if(!out)return fail("lifetime report");
 fprintf(out,"{\"schema\":\"bennett-driver-native-lifetime-1\",\"namespace\":%ld,\"load\":true,\"binding_calls\":%lu,\"entry_calls\":%lu,\"entry_returned\":%lu,\"status\":%d,\"unload_status\":%d,\"qreg_new_successes\":%lu,\"qreg_free_successes\":%lu,\"last_provider_status\":%d,\"signal\":%d,\"component_exit\":%d,\"dependencies\":[",(long)namespace,api->bound,api->entered,api->returned,api->result,unloaded,api->qreg_news,api->qreg_frees,api->last_status,(int)component_signal,(int)component_exit);
 struct link_map *map=NULL;dlinfo(handle,RTLD_DI_LINKMAP,&map);
 while(map&&map->l_prev)map=map->l_prev;
 int first=1;
 for(;map;map=map->l_next)if(map->l_name&&map->l_name[0]) {
  if(!first)fputc(',',out);first=0;
  fprintf(out,"{\"path\":");json_string(out,map->l_name);fprintf(out,",\"base\":%lu}",(unsigned long)map->l_addr);
 }
 fprintf(out,"]}\n");fclose(out);return 0;
}
int main(int argc,char **argv,char **envp) {
 if(argc<8){errno=EINVAL;return fail("expected COMPONENT PROVIDER TARGET OBJECT REPORT PARENT ARGV0 [args]");}
 char *end=NULL;long parent=strtol(argv[6],&end,10);
 if(!end||*end||parent<1||parent>INT_MAX||getppid()!=(pid_t)parent||prctl(PR_SET_PDEATHSIG,SIGKILL)||getppid()!=(pid_t)parent)return fail("launcher lifetime");
 size_t component_size=0,object_size=0,target_size=0;
 unsigned char *file=bytes(argv[1],&component_size),*object=bytes(argv[4],&object_size),*target=bytes(argv[3],&target_size);
 if(!file||!object||!target)return fail("input read");
 uintptr_t low,high;if(map_component(file,component_size,&low,&high))return 125;
 uintptr_t address=component_symbol(file,component_size,"__bennett_driver_component_run");
 if(!address)return fail("component entry export");
 void *handle=dlmopen(LM_ID_NEWLM,argv[2],RTLD_NOW|RTLD_LOCAL);
 if(!handle){fprintf(stderr,"BD-E-NATIVE-PROVIDER: dlmopen: %s\n",dlerror());return 125;}
 Lmid_t namespace=LM_ID_BASE;if(dlinfo(handle,RTLD_DI_LMID,&namespace)||namespace==LM_ID_BASE)return fail("provider isolation");
 int (*load)(const uint8_t *,size_t,const uint8_t *,size_t,void **)=dlsym(handle,"bennett_load");
 int (*unload)(void *)=dlsym(handle,"bennett_unload");
 const char *(*last_error)(void)=dlsym(handle,"bennett_last_error");
 if(!load||!unload)return fail("provider load/unload exports");
 struct driver_native_api *api=calloc(1,sizeof(*api));if(!api)return fail("gateway context");
 api->version=1;api->size=sizeof(*api);api->finish=materialised_exit;
#define RESOLVE_STATUS(n,p,a) api->n=dlsym(handle,"bennett_" #n);if(!api->n)return fail("provider export " #n);
 DRIVER_STATUS_API(RESOLVE_STATUS)
#undef RESOLVE_STATUS
#define RESOLVE_VALUE(t,n,p,a) api->n=dlsym(handle,"bennett_" #n);if(!api->n)return fail("provider export " #n);
 DRIVER_VALUE_API(RESOLVE_VALUE)
#undef RESOLVE_VALUE
#define RESOLVE_VOID(n,p,a) api->n=dlsym(handle,"bennett_" #n);if(!api->n)return fail("provider export " #n);
 DRIVER_VOID_API(RESOLVE_VOID)
#undef RESOLVE_VOID
 int status=load(object,object_size,target,target_size,&api->program);
 if(status||!api->program){fprintf(stderr,"BD-E-NATIVE-PROVIDER: load status %d: %s\n",status,last_error?last_error():"unavailable");return 125;}
 free(file);free(object);free(target);
 if(catch_exit(low,high))return 125;
 if(!sigsetjmp(escape,1)) {
  int (*run)(struct driver_native_api *,int,char **,char **)=(void *)address;
  api->result=run(api,argc-7,argv+7,envp);
 } else {if(!component_exit&&!component_signal)return fail("unexpected component escape");if(component_exit)api->result=component_status;}
 int unloaded=unload(api->program);
 if(provider_report(argv[5],handle,namespace,api,unloaded))return 125;
 if(dlclose(handle))return fail("provider dlclose");
 if(!api->bound||!api->entered||unloaded){errno=EINVAL;return fail("incomplete live-program lifetime");}
 int result=api->result;free(api);
 if(component_signal){signal(component_signal,SIG_DFL);raise(component_signal);return 125;}
 return result;
}
