#include "bennett_markers.h"

static unsigned char region(void) {
  uint64_t first, second;
  __bennett_effect_clock_read(&first);
  __bennett_effect_clock_read(&second);
  return (unsigned char)((first & 15) | ((second & 15) << 4));
}

unsigned top(void) {
  bennett_q tgt = __bennett_qalloc(0, 8);
  bennett_q fault = __bennett_qalloc(0, 4);
  bennett_budget budget = {1000000, 1048576, 65536, 256, 0};
  BENNETT_ORACLE_DESC_D(1) desc;
  bennett_oracle_desc_init(&desc.h, 0, 1, tgt, fault);
  desc.dev[0] = (bennett_devbind){BENNETT_DEV_CLOCK, 0, 0, 3};
  __bennett_oracle((const void *)region, &budget, &desc.h);
  unsigned result = 0;
  for (unsigned i = 0; i < 8; ++i)
    result |= (unsigned)__bennett_measure(tgt, i) << i;
  for (unsigned i = 0; i < 4; ++i)
    result |= (unsigned)__bennett_measure(fault, i) << (i + 8);
  /* Each oracle invocation must start from its descriptor's private clock.
     Applying the same XOR payload again must leave both registers clean. */
  __bennett_oracle((const void *)region, &budget, &desc.h);
  __bennett_qfree(fault);
  __bennett_qfree(tgt);
  return result;
}
