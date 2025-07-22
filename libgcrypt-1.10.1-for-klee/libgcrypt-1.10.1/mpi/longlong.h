/* longlong.h -- definitions for mixed size 32/64 bit arithmetic.
   Pure C version: all inline asm replaced with portable C code.
   Note: This is the Libgcrypt version, modified for C portability.
*/

#define __BITS4 (W_TYPE_SIZE / 4)
#define __ll_B ((UWtype) 1 << (W_TYPE_SIZE / 2))
#define __ll_lowpart(t) ((UWtype) (t) & (__ll_B - 1))
#define __ll_highpart(t) ((UWtype) (t) >> (W_TYPE_SIZE / 2))

#ifndef __MPN
# define __MPN(x) __##x
#endif

/* Generic C versions of all macros. */

#define add_ssaaaa(sh, sl, ah, al, bh, bl) \
  do { \
    UWtype __x = (al) + (bl); \
    (sh) = (ah) + (bh) + (__x < (al)); \
    (sl) = __x; \
  } while (0)

#define sub_ddmmss(sh, sl, ah, al, bh, bl) \
  do { \
    UWtype __x = (al) - (bl); \
    (sh) = (ah) - (bh) - (__x > (al)); \
    (sl) = __x; \
  } while (0)

#define umul_ppmm(w1, w0, u, v) \
  do { \
    UWtype __x0, __x1, __x2, __x3; \
    UHWtype __ul, __vl, __uh, __vh; \
    UWtype __u = (u), __v = (v); \
    __ul = __ll_lowpart (__u); \
    __uh = __ll_highpart (__u); \
    __vl = __ll_lowpart (__v); \
    __vh = __ll_highpart (__v); \
    __x0 = (UWtype) __ul * __vl; \
    __x1 = (UWtype) __ul * __vh; \
    __x2 = (UWtype) __uh * __vl; \
    __x3 = (UWtype) __uh * __vh; \
    __x1 += __ll_highpart (__x0); \
    __x1 += __x2; \
    if (__x1 < __x2) \
      __x3 += __ll_B; \
    (w1) = __x3 + __ll_highpart (__x1); \
    (w0) = (__ll_lowpart (__x1) << (W_TYPE_SIZE/2)) + __ll_lowpart (__x0); \
  } while (0)

#define smul_ppmm(w1, w0, u, v) \
  do { \
    UWtype __w1; \
    UWtype __m0 = (u), __m1 = (v); \
    umul_ppmm (__w1, w0, __m0, __m1); \
    (w1) = __w1 - (-((SItype)__m0 >> (W_TYPE_SIZE - 1)) & __m1) \
                - (-((SItype)__m1 >> (W_TYPE_SIZE - 1)) & __m0); \
  } while (0)

#define __umulsidi3(u, v) \
  ({UWtype __hi, __lo; \
    umul_ppmm (__hi, __lo, u, v); \
    ((UDWtype) __hi << W_TYPE_SIZE) | __lo; })

#define __udiv_qrnnd_c(q, r, n1, n0, d) \
  do { \
    UWtype __d1, __d0, __q1, __q0, __r1, __r0, __m; \
    __d1 = __ll_highpart (d); \
    __d0 = __ll_lowpart (d); \
    __r1 = (n1) % __d1; \
    __q1 = (n1) / __d1; \
    __m = (UWtype) __q1 * __d0; \
    __r1 = __r1 * __ll_B | __ll_highpart (n0); \
    if (__r1 < __m) { \
      __q1--, __r1 += (d); \
      if (__r1 >= (d)) \
        if (__r1 < __m) \
          __q1--, __r1 += (d); \
    } \
    __r1 -= __m; \
    __r0 = __r1 % __d1; \
    __q0 = __r1 / __d1; \
    __m = (UWtype) __q0 * __d0; \
    __r0 = __r0 * __ll_B | __ll_lowpart (n0); \
    if (__r0 < __m) { \
      __q0--, __r0 += (d); \
      if (__r0 >= (d)) \
        if (__r0 < __m) \
          __q0--, __r0 += (d); \
    } \
    __r0 -= __m; \
    (q) = (UWtype) __q1 * __ll_B | __q0; \
    (r) = __r0; \
  } while (0)

#define udiv_qrnnd(q, r, n1, n0, d) __udiv_qrnnd_c(q, r, n1, n0, d)
#define UDIV_NEEDS_NORMALIZATION 1

/* Count leading zeros using a portable C loop. */
#define count_leading_zeros(count, x) \
  do { \
    UWtype __clz_x = (x); \
    int __clz_i; \
    (count) = 0; \
    for (__clz_i = W_TYPE_SIZE - 1; __clz_i >= 0; --__clz_i) { \
      if ((__clz_x >> __clz_i) & 1) break; \
      (count)++; \
    } \
  } while (0)
#define COUNT_LEADING_ZEROS_0 W_TYPE_SIZE

/* Count trailing zeros using a portable C loop. */
#define count_trailing_zeros(count, x) \
  do { \
    UWtype __ctz_x = (x); \
    int __ctz_i; \
    (count) = 0; \
    for (__ctz_i = 0; __ctz_i < W_TYPE_SIZE; ++__ctz_i) { \
      if ((__ctz_x >> __ctz_i) & 1) break; \
      (count)++; \
    } \
  } while (0)

/* End of portable C longlong.h */