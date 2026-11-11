/* Negative control: change a real provider register's precondition, then invoke
   its real free. This neither constructs a program nor substitutes a qreg API. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
static int (*real_prepare)(void *,uint64_t,const uint8_t *,size_t);
static int (*real_free)(void *,uint64_t);
static int dirty_free(void *program,uint64_t qreg) {
 const uint8_t one=1;
 if(real_prepare(program,qreg,&one,1))abort();
 return real_free(program,qreg);
}
static void *resolve_with_dirty_precondition(void *handle,const char *name) {
 void *symbol=dlsym(handle,name);
 if(!strcmp(name,"bennett_qreg_free")) {
  real_free=symbol;
  real_prepare=dlsym(handle,"bennett_qreg_prepare");
  if(!real_free||!real_prepare)abort();
  return (void *)dirty_free;
 }
 return symbol;
}
#define dlsym resolve_with_dirty_precondition
#include "native-bootstrap.c"
