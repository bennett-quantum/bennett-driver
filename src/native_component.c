#include "native-provider-api.h"
static struct driver_native_api *backend;
static struct driver_native_api *context(void) {
 if (!backend || backend->version != 1 || backend->size != sizeof(*backend) || !backend->program)
  __builtin_trap();
 return backend;
}
#define STATUS_FORWARD(n,p,a) int bennett_##n p { \
 struct driver_native_api *api=context(); \
 int status=api->n a; api->last_status=status; \
 if (!status && !__builtin_strcmp(#n,"qreg_new")) api->qreg_news++; \
 if (!status && !__builtin_strcmp(#n,"qreg_free")) api->qreg_frees++; \
 return status; }
DRIVER_STATUS_API(STATUS_FORWARD)
#undef STATUS_FORWARD
#define VALUE_FORWARD(t,n,p,a) t bennett_##n p { return context()->n a; }
DRIVER_VALUE_API(VALUE_FORWARD)
#undef VALUE_FORWARD
#define VOID_FORWARD(n,p,a) void bennett_##n p { context()->n a; }
DRIVER_VOID_API(VOID_FORWARD)
#undef VOID_FORWARD
/* DRIVER_ENTRY_DECL */
/* DRIVER_MAIN_STUB */
extern void driver_binding(void *) __asm__("DRIVER_BINDING_SYMBOL");
extern void __bennett_rt_native_inputs(int,char **,char **);
int __bennett_driver_component_run(struct driver_native_api *api,int argc,char **argv,char **envp) {
 if (backend || !api || api->version != 1 || api->size != sizeof(*api) || !api->program) __builtin_trap();
 backend=api;
 driver_binding(api->program);
 api->bound++;
 /* DRIVER_INPUTS */
 api->entered++;
 int result=/* DRIVER_ENTRY_CALL */;
 api->result=result;
 api->returned++;
 /* DRIVER_FINISH */
 backend=0;
 return result;
}

/* The real materialised EH state has already been written and cleanup run. */
__attribute__((noreturn)) void __bennett_driver_native_exit(int status) {
 context()->finish(status);
 __builtin_trap();
}
