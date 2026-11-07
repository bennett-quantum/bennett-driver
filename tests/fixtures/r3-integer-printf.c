#include <stdio.h>

/* Hand-derived stdout:
 *   [  musl] -00042 37 002a !\n
 *   tail:007
 * %6.4s pads "musl" with two spaces; %06d counts the minus sign in width 6;
 * %.4x pads 0x2a to four digits. The final eight bytes have no trailing LF
 * and must be flushed on normal main return.
 */
int main(void) {
    printf("[%6.4s] %06d %u %.4x %c\n", "musl", -42, 37u, 0x2au, '!');
    printf("tail:%03d", 7);
    return 0;
}
