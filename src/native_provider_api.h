#ifndef BENNETT_DRIVER_NATIVE_PROVIDER_API_H
#define BENNETT_DRIVER_NATIVE_PROVIDER_API_H
#include <stddef.h>
#include <stdint.h>
/* Driver-private bootstrap/component ABI; functions use published launch ABI. */
#define DRIVER_STATUS_API(X) \
 X(qreg_new,(void *p,const char *c,uint32_t n,uint64_t *o),(p,c,n,o)) \
 X(qreg_prepare,(void *p,uint64_t q,const uint8_t *b,size_t n),(p,q,b,n)) \
 X(qreg_free,(void *p,uint64_t q),(p,q)) \
 X(budget,(void *p,const char *r,uint64_t s,uint64_t h,uint64_t st,uint64_t d,uint64_t *o),(p,r,s,h,st,d,o)) \
 X(args_new,(size_t n,void **o),(n,o)) \
 X(args_set_int,(void *a,size_t i,uint32_t w,const uint8_t *b),(a,i,w,b)) \
 X(args_set_f64,(void *a,size_t i,double v),(a,i,v)) \
 X(args_set_qreg,(void *a,size_t i,uint64_t q),(a,i,q)) \
 X(args_set_token,(void *a,size_t i,uint64_t t),(a,i,t)) \
 X(run,(void *p,const char *e,const void *a,const uint8_t *b,size_t n,uint64_t *o),(p,e,a,b,n,o)) \
 X(wait,(void *p,uint64_t r,void **o,void **q),(p,r,o,q)) \
 X(reply,(void *p,uint64_t r,const uint8_t *b,size_t n),(p,r,b,n)) \
 X(run_close,(void *p,uint64_t r),(p,r)) \
 X(reverse,(void *p,uint64_t r),(p,r)) \
 X(result_get,(const void *r,size_t i,int *k,uint32_t *w,uint8_t *b,size_t c),(r,i,k,w,b,c)) \
 X(result_measurement,(const void *r,size_t i,uint64_t *q,uint8_t *b,size_t c,size_t *n),(r,i,q,b,c,n))
#define DRIVER_VALUE_API(X) \
 X(size_t,result_nvalues,(const void *r),(r)) \
 X(size_t,result_nfaults,(const void *r),(r)) \
 X(uint64_t,result_fault,(const void *r,size_t i),(r,i)) \
 X(size_t,result_nmeasurements,(const void *r),(r)) \
 X(const char *,request_service,(const void *r),(r)) \
 X(const uint8_t *,request_payload,(const void *r,size_t *n),(r,n))
#define DRIVER_VOID_API(X) \
 X(args_free,(void *a),(a)) \
 X(result_free,(void *r),(r)) \
 X(request_free,(void *r),(r))
struct driver_native_api {
 uint64_t version, size;
 void *program;
 void (*finish)(int);
 uint64_t bound, entered, returned, qreg_news, qreg_frees;
 int last_status, result;
#define STATUS_FIELD(n,p,a) int (*n) p;
 DRIVER_STATUS_API(STATUS_FIELD)
#undef STATUS_FIELD
#define VALUE_FIELD(t,n,p,a) t (*n) p;
 DRIVER_VALUE_API(VALUE_FIELD)
#undef VALUE_FIELD
#define VOID_FIELD(n,p,a) void (*n) p;
 DRIVER_VOID_API(VOID_FIELD)
#undef VOID_FIELD
};
#endif
