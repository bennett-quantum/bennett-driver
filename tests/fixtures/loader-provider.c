/* A public-ABI fixture, not a VM implementation or an estimation oracle. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { char root[128]; uint64_t next; uint64_t revoked; } program;
typedef struct { char bytes[512]; } estimate;
#ifndef EXPORT_NO_QUERY
static const uint8_t manifest[] = {MANIFEST_BYTES};
#endif
#if !defined(EXPORT_NO_QUERY) && !defined(EXPORT_SCHED)
int bennett_launch_features(const uint8_t **out, size_t *len) {
    if (!out || !len) return 11;
    *out = QUERY_STATUS ? NULL : manifest;
    *len = QUERY_STATUS ? 0 : sizeof(manifest)-1;
    return QUERY_STATUS;
}
#endif
#ifdef EXPORT_SCHED
int bennett_sched_features(const uint8_t **out, size_t *len) {
    if (!out || !len) return 11;
    *out = QUERY_STATUS ? NULL : manifest; *len = QUERY_STATUS ? 0 : sizeof(manifest)-1;
    return QUERY_STATUS;
}

#ifndef EXPORT_NO_ALIAS
int bennett_sched_request_set_token_aliases(void *r, const uint8_t *a, size_t n) { (void)r; (void)a; (void)n; return 0; }

#endif
#ifndef EXPORT_NO_SCHEDULE
int bennett_sched_schedule(const void *r, void **out) { (void)r; (void)out; return 0; }
#endif
#endif
int bennett_load(const uint8_t *object, size_t n, const uint8_t *target, size_t tn, program **out) {
    (void)target; (void)tn;
#if defined(EXPORT_NO_EFFECTS) || defined(EXPORT_NO_QUERY) || defined(EXPORT_NO_ALIAS)
    abort();
#endif
    assert(n > 7 && n < 128 && !memcmp(object,"object:",7));
    *out = calloc(1,sizeof(program)); assert(*out);
    memcpy((*out)->root,object+7,n-7); return 0;
}
int bennett_unload(program *p) { free(p); return 0; }
int bennett_budget(program *p, const char *r, uint64_t s, uint64_t h, uint64_t st, uint64_t d, uint64_t *out) {
    assert(!strcmp(p->root,r)); assert(s==7 && h==8 && st==9 && d==10);
    *out = ++p->next; return 0;
}
#ifndef EXPORT_NO_ALIAS
int bennett_estimate_run_with_token_aliases(program *p, const char *r, uint64_t token, const char *v, uint32_t c,
    const uint8_t *params, size_t pn, const uint8_t *aliases, size_t an, estimate **out) {
#if defined(EXPORT_NO_EFFECTS) || defined(EXPORT_NO_QUERY) || defined(EXPORT_NO_ALIAS)
    abort();
#endif
    assert(!strcmp(p->root,r)); assert(!strcmp(v,"forward")); assert(token>0 && token<=p->next);
    if (token==p->revoked) return 11;
    if ((an>1 && aliases[1]!='0') || (an==5 && aliases[3]=='2') || an>7) return 11;
    *out = malloc(sizeof(estimate)); assert(*out);
    int n = snprintf((*out)->bytes,sizeof((*out)->bytes),"%s|%llu|%u|%.*s|%.*s",r,(unsigned long long)token,c,(int)pn,params,(int)an,aliases);
    assert(n>0 && (size_t)n<sizeof((*out)->bytes)); return 0;
}
#endif
/* Any erasing retry or mistaken 0.8/0.9 legacy dispatch is an immediate failure. */
int bennett_estimate_run(void) { abort(); }
const uint8_t *bennett_estimate_certificate(const estimate *e, size_t *n) { *n=strlen(e->bytes); return (const uint8_t *)e->bytes; }
void bennett_estimate_free(estimate *e) { free(e); }

uint64_t fixture_mint(program *p) { return ++p->next; }
void fixture_reverse(program *p, uint64_t token) { p->revoked=token; }
