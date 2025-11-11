[kernel:annot:missing-spec] slicing_driver.c:13: Warning: 
  Neither code nor specification for function Frama_C_interval,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function Frama_C_interval
[eva:malloc:new] libgcrypt-1.10.1/src/global.c:1177: 
  allocating variable __malloc__gcry_xmalloc_l1177
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148
[kernel:annot:missing-spec] libgcrypt-1.10.1/mpi/mpiutil.c:149: Warning: 
  Neither code nor specification for function Frama_C_make_unknown,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function Frama_C_make_unknown
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:112: Warning: 
  out of bounds write. assert \valid(&a->d);
[eva:malloc:new] libgcrypt-1.10.1/src/global.c:1177: 
  allocating variable __malloc__gcry_xmalloc_l1177_0
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_0
[eva:malloc:new] libgcrypt-1.10.1/src/global.c:1177: 
  allocating variable __malloc__gcry_xmalloc_l1177_1
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_1
[eva:malloc:new] libgcrypt-1.10.1/src/global.c:1177: 
  allocating variable __malloc__gcry_xmalloc_l1177_2
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_2
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:569: Warning: 
  out of bounds write. assert \valid(w->d + 0);
[kernel:annot:missing-spec] libgcrypt-1.10.1/mpi/mpi-pow.c:467: Warning: 
  Neither code nor specification for function _gcry_divide_by_zero,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function _gcry_divide_by_zero
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:478: Warning: 
  assertion got status unknown.
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_3
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-lshift.c:55: Warning: 
  invalid RHS operand for shift. assert 0 ≤ sh_2 < 64;
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-lshift.c:63: Warning: 
  out of bounds write. assert \valid(wp + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-lshift.c:63: Warning: 
  invalid RHS operand for shift. assert 0 ≤ sh_1 < 64;
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:495: Warning: 
  out of bounds write. assert \valid(mp + _i);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:495: 
  starting to merge loop iterations
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_4
[eva] FRAMAC_SHARE/libc/string.h:161: 
  cannot evaluate ACSL term, unsupported ACSL construct: logic function memset
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_5
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:576: Warning: 
  out of bounds write. assert \valid(precomp[0] + _i_3);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:576: 
  starting to merge loop iterations
[eva:malloc:new] libgcrypt-1.10.1/mpi/mpiutil.c:148: 
  allocating variable __malloc__gcry_mpi_alloc_limb_space_l148_6
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:595: Warning: 
  out of bounds write. assert \valid(base_u + _i_5);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:595: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:617: Warning: 
  out of bounds write. assert \valid(rp + _i_7);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:617: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:621: Warning: 
  assertion got status unknown.
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:649: Warning: 
  assertion got status unknown.
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:664: Warning: 
  invalid RHS operand for shift. assert 0 ≤ (int)((int)(8 * 8) - c) < 64;
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:682: Warning: 
  assertion got status unknown.
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:540: Warning: 
  accessing uninitialized left-value. assert \initialized(uu + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:540: Warning: 
  out of bounds read. assert \valid_read(uu + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:541: Warning: 
  accessing uninitialized left-value. assert \initialized(uw + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpiutil.c:541: Warning: 
  out of bounds read. assert \valid_read(uw + i);
[eva:partition] libgcrypt-1.10.1/mpi/mpiutil.c:538: 
  starting to merge loop iterations
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:696: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:492: Warning: 
  accessing uninitialized left-value. assert \initialized(vp + 0);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:492: Warning: 
  out of bounds read. assert \valid_read(vp + 0);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:495: Warning: 
  out of bounds write. assert \valid(prodp + _i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:495: Warning: 
  accessing uninitialized left-value. assert \initialized(up + _i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:495: Warning: 
  out of bounds read. assert \valid_read(up + _i);
[eva:partition] libgcrypt-1.10.1/mpi/mpih-mul.c:495: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:497: Warning: 
  out of bounds write. assert \valid(prodp + _i_0);
[eva:partition] libgcrypt-1.10.1/mpi/mpih-mul.c:497: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul1.c:54: Warning: 
  accessing uninitialized left-value. assert \initialized(&prod_low);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul1.c:55: Warning: 
  accessing uninitialized left-value. assert \initialized(&prod_high);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul1.c:56: Warning: 
  out of bounds write. assert \valid(res_ptr + j);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-mul.c:503: Warning: 
  out of bounds write. assert \valid(prodp + usize);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-div.c:224: Warning: 
  accessing uninitialized left-value. assert \initialized(dp + 0);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-div.c:224: Warning: 
  out of bounds read. assert \valid_read(dp + 0);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-div.c:225: Warning: 
  accessing uninitialized left-value.
  assert \initialized(np + (mpi_size_t)(nsize - 1));
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-div.c:225: Warning: 
  out of bounds read. assert \valid_read(np + (mpi_size_t)(nsize - 1));
[eva:partition] libgcrypt-1.10.1/mpi/mpih-div.c:233: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-div.c:240: Warning: 
  out of bounds write. assert \valid(np + 0);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:688: 
  starting to merge loop iterations
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:627: 
  starting to merge loop iterations
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:726: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:726: Warning: 
  signed overflow. assert -2147483648 ≤ j - 1;
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-lshift.c:54: Warning: 
  accessing uninitialized left-value. assert \initialized(up + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-lshift.c:54: Warning: 
  out of bounds read. assert \valid_read(up + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:745: Warning: 
  out of bounds write. assert \valid(rp + rsize);
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:749: Warning: 
  pointer comparison. assert \pointer_comparable((void *)res->d, (void *)rp);
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:751: Warning: 
  out of bounds write. assert \valid(res->d + _i_8);
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:751: Warning: 
  accessing uninitialized left-value. assert \initialized(rp + _i_8);
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:751: Warning: 
  out of bounds read. assert \valid_read(rp + _i_8);
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:751: 
  starting to merge loop iterations
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-rshift.c:54: Warning: 
  out of bounds read. assert \valid_read(up + 0);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-rshift.c:55: Warning: 
  invalid RHS operand for shift. assert 0 ≤ sh_2 < 64;
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-rshift.c:63: Warning: 
  out of bounds write. assert \valid(wp + i);
[eva:alarm] libgcrypt-1.10.1/mpi/mpih-rshift.c:63: Warning: 
  invalid RHS operand for shift. assert 0 ≤ sh_1 < 64;
[eva:alarm] libgcrypt-1.10.1/mpi/mpi-pow.c:764: Warning: 
  out of bounds read. assert \valid_read(rp + (mpi_size_t)(rsize - 1));
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:764: 
  starting to merge loop iterations
[kernel:annot:missing-spec] libgcrypt-1.10.1/src/global.c:1098: Warning: 
  Neither code nor specification for function _gcry_private_free,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function _gcry_private_free
[kernel:annot:missing-spec] libgcrypt-1.10.1/src/global.c:1101: Warning: 
  Neither code nor specification for function gpg_err_set_errno,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function gpg_err_set_errno
[eva:partition] libgcrypt-1.10.1/mpi/mpi-pow.c:767: 
  starting to merge loop iterations
[kernel:annot:missing-spec] libgcrypt-1.10.1/mpi/mpi-pow.c:782: Warning: 
  Neither code nor specification for function _gcry_assert_failed,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function _gcry_assert_failed
[kernel:annot:missing-spec] libgcrypt-1.10.1/mpi/mpiutil.c:165: Warning: 
  Neither code nor specification for function _gcry_fast_wipememory,
   generating default assigns. See -generated-spec-* options for more info
[eva] using specification for function _gcry_fast_wipememory
[eva:garbled-mix:assigns] libgcrypt-1.10.1/src/global.c:1098: 
  The specification of function _gcry_private_free
  has generated a garbled mix of addresses
  for assigns clause *((char *)a + (0 ..)).
[eva] libgcrypt-1.10.1/mpi/mpi-pow.c:664: 
  assertion 'Eva,shift' got final status invalid.
[scope:rm_asserts] removing 1 assertion(s)
[eva:summary] ====== ANALYSIS SUMMARY ======
  ----------------------------------------------------------------------------
  23 functions analyzed (out of 467): 4% coverage.
  In these functions, 528 statements reached (out of 841): 62% coverage.
  ----------------------------------------------------------------------------
  Some errors and warnings have been raised during the analysis:
    by the Eva analyzer:      0 errors    0 warnings
    by the Frama-C kernel:    0 errors  141 warnings
  ----------------------------------------------------------------------------
  42 alarms generated by the analysis:
      25 invalid memory accesses
      10 accesses to uninitialized left-values
       5 invalid shifts
       1 integer overflow
       1 other
  1 of them is a sure alarm (invalid status).
  ----------------------------------------------------------------------------
  Evaluation of the logical properties reached by the analysis:
    Assertions        1 valid     4 unknown     0 invalid      5 total
    Preconditions     1 valid     0 unknown     0 invalid      1 total
  33% of the logical properties reached have been proven.
  ----------------------------------------------------------------------------
[slicing] initializing slicing ...
[slicing] interpreting slicing requests from the command line...
[pdg] computing for function gcry_mpi_powm
[from] Computing for function _gcry_mpi_powm
[from] Computing for function _gcry_divide_by_zero <-_gcry_mpi_powm
[from] Done for function _gcry_divide_by_zero
[from] Computing for function _gcry_mpi_alloc_limb_space <-_gcry_mpi_powm
[from] Computing for function malloc <-_gcry_mpi_alloc_limb_space <-_gcry_mpi_powm
[from] Done for function malloc
[from] Computing for function Frama_C_make_unknown <-_gcry_mpi_alloc_limb_space <-_gcry_mpi_powm
[from] Done for function Frama_C_make_unknown
[from] Done for function _gcry_mpi_alloc_limb_space
[from] Computing for function _gcry_mpih_lshift <-_gcry_mpi_powm
[from] Done for function _gcry_mpih_lshift
[from] Computing for function memset <-_gcry_mpi_powm
[from] Done for function memset
[from] Computing for function _gcry_mpi_set_cond <-_gcry_mpi_powm
[from] Done for function _gcry_mpi_set_cond
[from] Computing for function mul_mod <-_gcry_mpi_powm
[from] Computing for function _gcry_mpih_mul <-mul_mod <-_gcry_mpi_powm
[from] Computing for function _gcry_mpih_mul_1 <-_gcry_mpih_mul <-mul_mod <-_gcry_mpi_powm
[from] Done for function _gcry_mpih_mul_1
[from] Done for function _gcry_mpih_mul
[from] Computing for function _gcry_mpih_divrem <-mul_mod <-_gcry_mpi_powm
[from] Done for function _gcry_mpih_divrem
[from] Done for function mul_mod
[from] Computing for function _gcry_mpih_rshift <-_gcry_mpi_powm
[from] Done for function _gcry_mpih_rshift
[from] Computing for function _gcry_mpih_release_karatsuba_ctx <-_gcry_mpi_powm
[from] Done for function _gcry_mpih_release_karatsuba_ctx
[from] Computing for function _gcry_mpi_free_limb_space <-_gcry_mpi_powm
[from] Computing for function _gcry_fast_wipememory <-_gcry_mpi_free_limb_space <-_gcry_mpi_powm
[from] Done for function _gcry_fast_wipememory
[from] Computing for function _gcry_free <-_gcry_mpi_free_limb_space <-_gcry_mpi_powm
[from] Computing for function _gcry_private_free <-_gcry_free <-_gcry_mpi_free_limb_space <-_gcry_mpi_powm
[from] Done for function _gcry_private_free
[from] Computing for function gpg_err_set_errno <-_gcry_free <-_gcry_mpi_free_limb_space <-_gcry_mpi_powm
[from] Done for function gpg_err_set_errno
[from] Done for function _gcry_free
[from] Done for function _gcry_mpi_free_limb_space
[from] Computing for function _gcry_assert_failed <-_gcry_mpi_powm
[from] Done for function _gcry_assert_failed
[from] Done for function _gcry_mpi_powm
[pdg] done for function gcry_mpi_powm
[pdg] computing for function main
[from] Computing for function Frama_C_interval
[from] Done for function Frama_C_interval
[from] Computing for function gcry_mpi_new
[from] Computing for function _gcry_mpi_new <-gcry_mpi_new
[from] Computing for function _gcry_mpi_alloc <-_gcry_mpi_new <-gcry_mpi_new
[from] Computing for function _gcry_xmalloc <-_gcry_mpi_alloc <-_gcry_mpi_new <-gcry_mpi_new
[from] Done for function _gcry_xmalloc
[from] Done for function _gcry_mpi_alloc
[from] Done for function _gcry_mpi_new
[from] Done for function gcry_mpi_new
[from] Computing for function gcry_mpi_set_ui
[from] Computing for function _gcry_mpi_set_ui <-gcry_mpi_set_ui
[from] Done for function _gcry_mpi_set_ui
[from] Done for function gcry_mpi_set_ui
[from] Computing for function gcry_mpi_powm
[from] Done for function gcry_mpi_powm
[from] Computing for function gcry_mpi_release
[from] Computing for function _gcry_mpi_release <-gcry_mpi_release
[from] Computing for function _gcry_mpi_free <-_gcry_mpi_release <-gcry_mpi_release
[from] Done for function _gcry_mpi_free
[from] Done for function _gcry_mpi_release
[from] Done for function gcry_mpi_release
[pdg] done for function main
[slicing] applying all slicing requests...
[slicing] applying 0 actions...
[slicing] applying all slicing requests...
[slicing] applying 2 actions...
[slicing] applying actions: 1/2...
[pdg] computing for function _gcry_mpi_powm
[pdg] libgcrypt-1.10.1/mpi/mpi-pow.c:491: Warning: Ignoring inline assembly code
[pdg] libgcrypt-1.10.1/mpi/mpi-pow.c:620: Warning: Ignoring inline assembly code
[pdg] libgcrypt-1.10.1/mpi/mpi-pow.c:648: Warning: Ignoring inline assembly code
[pdg] libgcrypt-1.10.1/mpi/mpi-pow.c:681: Warning: Ignoring inline assembly code
[pdg] done for function _gcry_mpi_powm
[pdg] computing for function _gcry_mpi_free_limb_space
[pdg] done for function _gcry_mpi_free_limb_space
[pdg] computing for function _gcry_free
[pdg] done for function _gcry_free
[pdg] computing for function _gcry_mpih_rshift
[pdg] done for function _gcry_mpih_rshift
[pdg] computing for function _gcry_mpih_divrem
[pdg] libgcrypt-1.10.1/mpi/mpih-div.c:234: Warning: 
  Ignoring inline assembly code
[pdg] done for function _gcry_mpih_divrem
[pdg] computing for function _gcry_mpih_lshift
[pdg] done for function _gcry_mpih_lshift
[pdg] computing for function mul_mod
[pdg] done for function mul_mod
[pdg] computing for function _gcry_mpih_mul
[pdg] done for function _gcry_mpih_mul
[pdg] computing for function _gcry_mpih_mul_1
[pdg] libgcrypt-1.10.1/mpi/mpih-mul1.c:53: Warning: 
  Ignoring inline assembly code
[pdg] done for function _gcry_mpih_mul_1
[pdg] computing for function _gcry_mpi_set_cond
[pdg] done for function _gcry_mpi_set_cond
[pdg] computing for function _gcry_mpi_alloc_limb_space
[pdg] done for function _gcry_mpi_alloc_limb_space
[pdg] computing for function gcry_mpi_set_ui
[pdg] done for function gcry_mpi_set_ui
[pdg] computing for function _gcry_mpi_set_ui
[pdg] done for function _gcry_mpi_set_ui
[pdg] computing for function gcry_mpi_new
[pdg] done for function gcry_mpi_new
[pdg] computing for function _gcry_mpi_new
[pdg] done for function _gcry_mpi_new
[pdg] computing for function _gcry_mpi_alloc
[pdg] done for function _gcry_mpi_alloc
[pdg] computing for function _gcry_xmalloc
[pdg] done for function _gcry_xmalloc
[slicing] applying actions: 2/2...
[slicing] exporting project to 'Slicing export'...
[slicing] applying all slicing requests...
[slicing] applying 0 actions...
[slicing] libgcrypt-1.10.1/mpi/mpi-pow.c:491: Warning: 
  Dropping unsupported ACSL annotation
[slicing] libgcrypt-1.10.1/mpi/mpi-pow.c:620: Warning: 
  Dropping unsupported ACSL annotation
[slicing] libgcrypt-1.10.1/mpi/mpi-pow.c:648: Warning: 
  Dropping unsupported ACSL annotation
[slicing] libgcrypt-1.10.1/mpi/mpi-pow.c:681: Warning: 
  Dropping unsupported ACSL annotation
[slicing] libgcrypt-1.10.1/mpi/mpih-div.c:234: Warning: 
  Dropping unsupported ACSL annotation
[slicing] libgcrypt-1.10.1/mpi/mpih-mul1.c:53: Warning: 
  Dropping unsupported ACSL annotation
[sparecode] remove unused global declarations from project 'Slicing export tmp'
[sparecode] removed unused global declarations in new project 'Slicing export'
/* Generated by Frama-C */
#include "errno.h"
#include "stdio.h"
#include "stdlib.h"
#include "string.h"
enum __anonenum_gpg_err_source_t_1 {
    GPG_ERR_SOURCE_UNKNOWN = 0,
    GPG_ERR_SOURCE_GCRYPT = 1,
    GPG_ERR_SOURCE_GPG = 2,
    GPG_ERR_SOURCE_GPGSM = 3,
    GPG_ERR_SOURCE_GPGAGENT = 4,
    GPG_ERR_SOURCE_PINENTRY = 5,
    GPG_ERR_SOURCE_SCD = 6,
    GPG_ERR_SOURCE_GPGME = 7,
    GPG_ERR_SOURCE_KEYBOX = 8,
    GPG_ERR_SOURCE_KSBA = 9,
    GPG_ERR_SOURCE_DIRMNGR = 10,
    GPG_ERR_SOURCE_GSTI = 11,
    GPG_ERR_SOURCE_GPA = 12,
    GPG_ERR_SOURCE_KLEO = 13,
    GPG_ERR_SOURCE_G13 = 14,
    GPG_ERR_SOURCE_ASSUAN = 15,
    GPG_ERR_SOURCE_TPM2D = 16,
    GPG_ERR_SOURCE_TLS = 17,
    GPG_ERR_SOURCE_ANY = 31,
    GPG_ERR_SOURCE_USER_1 = 32,
    GPG_ERR_SOURCE_USER_2 = 33,
    GPG_ERR_SOURCE_USER_3 = 34,
    GPG_ERR_SOURCE_USER_4 = 35,
    GPG_ERR_SOURCE_DIM = 128
};
enum __anonenum_gpg_err_code_t_2 {
    GPG_ERR_NO_ERROR = 0,
    GPG_ERR_GENERAL = 1,
    GPG_ERR_UNKNOWN_PACKET = 2,
    GPG_ERR_UNKNOWN_VERSION = 3,
    GPG_ERR_PUBKEY_ALGO = 4,
    GPG_ERR_DIGEST_ALGO = 5,
    GPG_ERR_BAD_PUBKEY = 6,
    GPG_ERR_BAD_SECKEY = 7,
    GPG_ERR_BAD_SIGNATURE = 8,
    GPG_ERR_NO_PUBKEY = 9,
    GPG_ERR_CHECKSUM = 10,
    GPG_ERR_BAD_PASSPHRASE = 11,
    GPG_ERR_CIPHER_ALGO = 12,
    GPG_ERR_KEYRING_OPEN = 13,
    GPG_ERR_INV_PACKET = 14,
    GPG_ERR_INV_ARMOR = 15,
    GPG_ERR_NO_USER_ID = 16,
    GPG_ERR_NO_SECKEY = 17,
    GPG_ERR_WRONG_SECKEY = 18,
    GPG_ERR_BAD_KEY = 19,
    GPG_ERR_COMPR_ALGO = 20,
    GPG_ERR_NO_PRIME = 21,
    GPG_ERR_NO_ENCODING_METHOD = 22,
    GPG_ERR_NO_ENCRYPTION_SCHEME = 23,
    GPG_ERR_NO_SIGNATURE_SCHEME = 24,
    GPG_ERR_INV_ATTR = 25,
    GPG_ERR_NO_VALUE = 26,
    GPG_ERR_NOT_FOUND = 27,
    GPG_ERR_VALUE_NOT_FOUND = 28,
    GPG_ERR_SYNTAX = 29,
    GPG_ERR_BAD_MPI = 30,
    GPG_ERR_INV_PASSPHRASE = 31,
    GPG_ERR_SIG_CLASS = 32,
    GPG_ERR_RESOURCE_LIMIT = 33,
    GPG_ERR_INV_KEYRING = 34,
    GPG_ERR_TRUSTDB = 35,
    GPG_ERR_BAD_CERT = 36,
    GPG_ERR_INV_USER_ID = 37,
    GPG_ERR_UNEXPECTED = 38,
    GPG_ERR_TIME_CONFLICT = 39,
    GPG_ERR_KEYSERVER = 40,
    GPG_ERR_WRONG_PUBKEY_ALGO = 41,
    GPG_ERR_TRIBUTE_TO_D_A = 42,
    GPG_ERR_WEAK_KEY = 43,
    GPG_ERR_INV_KEYLEN = 44,
    GPG_ERR_INV_ARG = 45,
    GPG_ERR_BAD_URI = 46,
    GPG_ERR_INV_URI = 47,
    GPG_ERR_NETWORK = 48,
    GPG_ERR_UNKNOWN_HOST = 49,
    GPG_ERR_SELFTEST_FAILED = 50,
    GPG_ERR_NOT_ENCRYPTED = 51,
    GPG_ERR_NOT_PROCESSED = 52,
    GPG_ERR_UNUSABLE_PUBKEY = 53,
    GPG_ERR_UNUSABLE_SECKEY = 54,
    GPG_ERR_INV_VALUE = 55,
    GPG_ERR_BAD_CERT_CHAIN = 56,
    GPG_ERR_MISSING_CERT = 57,
    GPG_ERR_NO_DATA = 58,
    GPG_ERR_BUG = 59,
    GPG_ERR_NOT_SUPPORTED = 60,
    GPG_ERR_INV_OP = 61,
    GPG_ERR_TIMEOUT = 62,
    GPG_ERR_INTERNAL = 63,
    GPG_ERR_EOF_GCRYPT = 64,
    GPG_ERR_INV_OBJ = 65,
    GPG_ERR_TOO_SHORT = 66,
    GPG_ERR_TOO_LARGE = 67,
    GPG_ERR_NO_OBJ = 68,
    GPG_ERR_NOT_IMPLEMENTED = 69,
    GPG_ERR_CONFLICT = 70,
    GPG_ERR_INV_CIPHER_MODE = 71,
    GPG_ERR_INV_FLAG = 72,
    GPG_ERR_INV_HANDLE = 73,
    GPG_ERR_TRUNCATED = 74,
    GPG_ERR_INCOMPLETE_LINE = 75,
    GPG_ERR_INV_RESPONSE = 76,
    GPG_ERR_NO_AGENT = 77,
    GPG_ERR_AGENT = 78,
    GPG_ERR_INV_DATA = 79,
    GPG_ERR_ASSUAN_SERVER_FAULT = 80,
    GPG_ERR_ASSUAN = 81,
    GPG_ERR_INV_SESSION_KEY = 82,
    GPG_ERR_INV_SEXP = 83,
    GPG_ERR_UNSUPPORTED_ALGORITHM = 84,
    GPG_ERR_NO_PIN_ENTRY = 85,
    GPG_ERR_PIN_ENTRY = 86,
    GPG_ERR_BAD_PIN = 87,
    GPG_ERR_INV_NAME = 88,
    GPG_ERR_BAD_DATA = 89,
    GPG_ERR_INV_PARAMETER = 90,
    GPG_ERR_WRONG_CARD = 91,
    GPG_ERR_NO_DIRMNGR = 92,
    GPG_ERR_DIRMNGR = 93,
    GPG_ERR_CERT_REVOKED = 94,
    GPG_ERR_NO_CRL_KNOWN = 95,
    GPG_ERR_CRL_TOO_OLD = 96,
    GPG_ERR_LINE_TOO_LONG = 97,
    GPG_ERR_NOT_TRUSTED = 98,
    GPG_ERR_CANCELED = 99,
    GPG_ERR_BAD_CA_CERT = 100,
    GPG_ERR_CERT_EXPIRED = 101,
    GPG_ERR_CERT_TOO_YOUNG = 102,
    GPG_ERR_UNSUPPORTED_CERT = 103,
    GPG_ERR_UNKNOWN_SEXP = 104,
    GPG_ERR_UNSUPPORTED_PROTECTION = 105,
    GPG_ERR_CORRUPTED_PROTECTION = 106,
    GPG_ERR_AMBIGUOUS_NAME = 107,
    GPG_ERR_CARD = 108,
    GPG_ERR_CARD_RESET = 109,
    GPG_ERR_CARD_REMOVED = 110,
    GPG_ERR_INV_CARD = 111,
    GPG_ERR_CARD_NOT_PRESENT = 112,
    GPG_ERR_NO_PKCS15_APP = 113,
    GPG_ERR_NOT_CONFIRMED = 114,
    GPG_ERR_CONFIGURATION = 115,
    GPG_ERR_NO_POLICY_MATCH = 116,
    GPG_ERR_INV_INDEX = 117,
    GPG_ERR_INV_ID = 118,
    GPG_ERR_NO_SCDAEMON = 119,
    GPG_ERR_SCDAEMON = 120,
    GPG_ERR_UNSUPPORTED_PROTOCOL = 121,
    GPG_ERR_BAD_PIN_METHOD = 122,
    GPG_ERR_CARD_NOT_INITIALIZED = 123,
    GPG_ERR_UNSUPPORTED_OPERATION = 124,
    GPG_ERR_WRONG_KEY_USAGE = 125,
    GPG_ERR_NOTHING_FOUND = 126,
    GPG_ERR_WRONG_BLOB_TYPE = 127,
    GPG_ERR_MISSING_VALUE = 128,
    GPG_ERR_HARDWARE = 129,
    GPG_ERR_PIN_BLOCKED = 130,
    GPG_ERR_USE_CONDITIONS = 131,
    GPG_ERR_PIN_NOT_SYNCED = 132,
    GPG_ERR_INV_CRL = 133,
    GPG_ERR_BAD_BER = 134,
    GPG_ERR_INV_BER = 135,
    GPG_ERR_ELEMENT_NOT_FOUND = 136,
    GPG_ERR_IDENTIFIER_NOT_FOUND = 137,
    GPG_ERR_INV_TAG = 138,
    GPG_ERR_INV_LENGTH = 139,
    GPG_ERR_INV_KEYINFO = 140,
    GPG_ERR_UNEXPECTED_TAG = 141,
    GPG_ERR_NOT_DER_ENCODED = 142,
    GPG_ERR_NO_CMS_OBJ = 143,
    GPG_ERR_INV_CMS_OBJ = 144,
    GPG_ERR_UNKNOWN_CMS_OBJ = 145,
    GPG_ERR_UNSUPPORTED_CMS_OBJ = 146,
    GPG_ERR_UNSUPPORTED_ENCODING = 147,
    GPG_ERR_UNSUPPORTED_CMS_VERSION = 148,
    GPG_ERR_UNKNOWN_ALGORITHM = 149,
    GPG_ERR_INV_ENGINE = 150,
    GPG_ERR_PUBKEY_NOT_TRUSTED = 151,
    GPG_ERR_DECRYPT_FAILED = 152,
    GPG_ERR_KEY_EXPIRED = 153,
    GPG_ERR_SIG_EXPIRED = 154,
    GPG_ERR_ENCODING_PROBLEM = 155,
    GPG_ERR_INV_STATE = 156,
    GPG_ERR_DUP_VALUE = 157,
    GPG_ERR_MISSING_ACTION = 158,
    GPG_ERR_MODULE_NOT_FOUND = 159,
    GPG_ERR_INV_OID_STRING = 160,
    GPG_ERR_INV_TIME = 161,
    GPG_ERR_INV_CRL_OBJ = 162,
    GPG_ERR_UNSUPPORTED_CRL_VERSION = 163,
    GPG_ERR_INV_CERT_OBJ = 164,
    GPG_ERR_UNKNOWN_NAME = 165,
    GPG_ERR_LOCALE_PROBLEM = 166,
    GPG_ERR_NOT_LOCKED = 167,
    GPG_ERR_PROTOCOL_VIOLATION = 168,
    GPG_ERR_INV_MAC = 169,
    GPG_ERR_INV_REQUEST = 170,
    GPG_ERR_UNKNOWN_EXTN = 171,
    GPG_ERR_UNKNOWN_CRIT_EXTN = 172,
    GPG_ERR_LOCKED = 173,
    GPG_ERR_UNKNOWN_OPTION = 174,
    GPG_ERR_UNKNOWN_COMMAND = 175,
    GPG_ERR_NOT_OPERATIONAL = 176,
    GPG_ERR_NO_PASSPHRASE = 177,
    GPG_ERR_NO_PIN = 178,
    GPG_ERR_NOT_ENABLED = 179,
    GPG_ERR_NO_ENGINE = 180,
    GPG_ERR_MISSING_KEY = 181,
    GPG_ERR_TOO_MANY = 182,
    GPG_ERR_LIMIT_REACHED = 183,
    GPG_ERR_NOT_INITIALIZED = 184,
    GPG_ERR_MISSING_ISSUER_CERT = 185,
    GPG_ERR_NO_KEYSERVER = 186,
    GPG_ERR_INV_CURVE = 187,
    GPG_ERR_UNKNOWN_CURVE = 188,
    GPG_ERR_DUP_KEY = 189,
    GPG_ERR_AMBIGUOUS = 190,
    GPG_ERR_NO_CRYPT_CTX = 191,
    GPG_ERR_WRONG_CRYPT_CTX = 192,
    GPG_ERR_BAD_CRYPT_CTX = 193,
    GPG_ERR_CRYPT_CTX_CONFLICT = 194,
    GPG_ERR_BROKEN_PUBKEY = 195,
    GPG_ERR_BROKEN_SECKEY = 196,
    GPG_ERR_MAC_ALGO = 197,
    GPG_ERR_FULLY_CANCELED = 198,
    GPG_ERR_UNFINISHED = 199,
    GPG_ERR_BUFFER_TOO_SHORT = 200,
    GPG_ERR_SEXP_INV_LEN_SPEC = 201,
    GPG_ERR_SEXP_STRING_TOO_LONG = 202,
    GPG_ERR_SEXP_UNMATCHED_PAREN = 203,
    GPG_ERR_SEXP_NOT_CANONICAL = 204,
    GPG_ERR_SEXP_BAD_CHARACTER = 205,
    GPG_ERR_SEXP_BAD_QUOTATION = 206,
    GPG_ERR_SEXP_ZERO_PREFIX = 207,
    GPG_ERR_SEXP_NESTED_DH = 208,
    GPG_ERR_SEXP_UNMATCHED_DH = 209,
    GPG_ERR_SEXP_UNEXPECTED_PUNC = 210,
    GPG_ERR_SEXP_BAD_HEX_CHAR = 211,
    GPG_ERR_SEXP_ODD_HEX_NUMBERS = 212,
    GPG_ERR_SEXP_BAD_OCT_CHAR = 213,
    GPG_ERR_SUBKEYS_EXP_OR_REV = 217,
    GPG_ERR_DB_CORRUPTED = 218,
    GPG_ERR_SERVER_FAILED = 219,
    GPG_ERR_NO_NAME = 220,
    GPG_ERR_NO_KEY = 221,
    GPG_ERR_LEGACY_KEY = 222,
    GPG_ERR_REQUEST_TOO_SHORT = 223,
    GPG_ERR_REQUEST_TOO_LONG = 224,
    GPG_ERR_OBJ_TERM_STATE = 225,
    GPG_ERR_NO_CERT_CHAIN = 226,
    GPG_ERR_CERT_TOO_LARGE = 227,
    GPG_ERR_INV_RECORD = 228,
    GPG_ERR_BAD_MAC = 229,
    GPG_ERR_UNEXPECTED_MSG = 230,
    GPG_ERR_COMPR_FAILED = 231,
    GPG_ERR_WOULD_WRAP = 232,
    GPG_ERR_FATAL_ALERT = 233,
    GPG_ERR_NO_CIPHER = 234,
    GPG_ERR_MISSING_CLIENT_CERT = 235,
    GPG_ERR_CLOSE_NOTIFY = 236,
    GPG_ERR_TICKET_EXPIRED = 237,
    GPG_ERR_BAD_TICKET = 238,
    GPG_ERR_UNKNOWN_IDENTITY = 239,
    GPG_ERR_BAD_HS_CERT = 240,
    GPG_ERR_BAD_HS_CERT_REQ = 241,
    GPG_ERR_BAD_HS_CERT_VER = 242,
    GPG_ERR_BAD_HS_CHANGE_CIPHER = 243,
    GPG_ERR_BAD_HS_CLIENT_HELLO = 244,
    GPG_ERR_BAD_HS_SERVER_HELLO = 245,
    GPG_ERR_BAD_HS_SERVER_HELLO_DONE = 246,
    GPG_ERR_BAD_HS_FINISHED = 247,
    GPG_ERR_BAD_HS_SERVER_KEX = 248,
    GPG_ERR_BAD_HS_CLIENT_KEX = 249,
    GPG_ERR_BOGUS_STRING = 250,
    GPG_ERR_FORBIDDEN = 251,
    GPG_ERR_KEY_DISABLED = 252,
    GPG_ERR_KEY_ON_CARD = 253,
    GPG_ERR_INV_LOCK_OBJ = 254,
    GPG_ERR_TRUE = 255,
    GPG_ERR_FALSE = 256,
    GPG_ERR_ASS_GENERAL = 257,
    GPG_ERR_ASS_ACCEPT_FAILED = 258,
    GPG_ERR_ASS_CONNECT_FAILED = 259,
    GPG_ERR_ASS_INV_RESPONSE = 260,
    GPG_ERR_ASS_INV_VALUE = 261,
    GPG_ERR_ASS_INCOMPLETE_LINE = 262,
    GPG_ERR_ASS_LINE_TOO_LONG = 263,
    GPG_ERR_ASS_NESTED_COMMANDS = 264,
    GPG_ERR_ASS_NO_DATA_CB = 265,
    GPG_ERR_ASS_NO_INQUIRE_CB = 266,
    GPG_ERR_ASS_NOT_A_SERVER = 267,
    GPG_ERR_ASS_NOT_A_CLIENT = 268,
    GPG_ERR_ASS_SERVER_START = 269,
    GPG_ERR_ASS_READ_ERROR = 270,
    GPG_ERR_ASS_WRITE_ERROR = 271,
    GPG_ERR_ASS_TOO_MUCH_DATA = 273,
    GPG_ERR_ASS_UNEXPECTED_CMD = 274,
    GPG_ERR_ASS_UNKNOWN_CMD = 275,
    GPG_ERR_ASS_SYNTAX = 276,
    GPG_ERR_ASS_CANCELED = 277,
    GPG_ERR_ASS_NO_INPUT = 278,
    GPG_ERR_ASS_NO_OUTPUT = 279,
    GPG_ERR_ASS_PARAMETER = 280,
    GPG_ERR_ASS_UNKNOWN_INQUIRE = 281,
    GPG_ERR_ENGINE_TOO_OLD = 300,
    GPG_ERR_WINDOW_TOO_SMALL = 301,
    GPG_ERR_WINDOW_TOO_LARGE = 302,
    GPG_ERR_MISSING_ENVVAR = 303,
    GPG_ERR_USER_ID_EXISTS = 304,
    GPG_ERR_NAME_EXISTS = 305,
    GPG_ERR_DUP_NAME = 306,
    GPG_ERR_TOO_YOUNG = 307,
    GPG_ERR_TOO_OLD = 308,
    GPG_ERR_UNKNOWN_FLAG = 309,
    GPG_ERR_INV_ORDER = 310,
    GPG_ERR_ALREADY_FETCHED = 311,
    GPG_ERR_TRY_LATER = 312,
    GPG_ERR_WRONG_NAME = 313,
    GPG_ERR_NO_AUTH = 314,
    GPG_ERR_BAD_AUTH = 315,
    GPG_ERR_NO_KEYBOXD = 316,
    GPG_ERR_KEYBOXD = 317,
    GPG_ERR_NO_SERVICE = 318,
    GPG_ERR_SERVICE = 319,
    GPG_ERR_SYSTEM_BUG = 666,
    GPG_ERR_DNS_UNKNOWN = 711,
    GPG_ERR_DNS_SECTION = 712,
    GPG_ERR_DNS_ADDRESS = 713,
    GPG_ERR_DNS_NO_QUERY = 714,
    GPG_ERR_DNS_NO_ANSWER = 715,
    GPG_ERR_DNS_CLOSED = 716,
    GPG_ERR_DNS_VERIFY = 717,
    GPG_ERR_DNS_TIMEOUT = 718,
    GPG_ERR_LDAP_GENERAL = 721,
    GPG_ERR_LDAP_ATTR_GENERAL = 722,
    GPG_ERR_LDAP_NAME_GENERAL = 723,
    GPG_ERR_LDAP_SECURITY_GENERAL = 724,
    GPG_ERR_LDAP_SERVICE_GENERAL = 725,
    GPG_ERR_LDAP_UPDATE_GENERAL = 726,
    GPG_ERR_LDAP_E_GENERAL = 727,
    GPG_ERR_LDAP_X_GENERAL = 728,
    GPG_ERR_LDAP_OTHER_GENERAL = 729,
    GPG_ERR_LDAP_X_CONNECTING = 750,
    GPG_ERR_LDAP_REFERRAL_LIMIT = 751,
    GPG_ERR_LDAP_CLIENT_LOOP = 752,
    GPG_ERR_LDAP_NO_RESULTS = 754,
    GPG_ERR_LDAP_CONTROL_NOT_FOUND = 755,
    GPG_ERR_LDAP_NOT_SUPPORTED = 756,
    GPG_ERR_LDAP_CONNECT = 757,
    GPG_ERR_LDAP_NO_MEMORY = 758,
    GPG_ERR_LDAP_PARAM = 759,
    GPG_ERR_LDAP_USER_CANCELLED = 760,
    GPG_ERR_LDAP_FILTER = 761,
    GPG_ERR_LDAP_AUTH_UNKNOWN = 762,
    GPG_ERR_LDAP_TIMEOUT = 763,
    GPG_ERR_LDAP_DECODING = 764,
    GPG_ERR_LDAP_ENCODING = 765,
    GPG_ERR_LDAP_LOCAL = 766,
    GPG_ERR_LDAP_SERVER_DOWN = 767,
    GPG_ERR_LDAP_SUCCESS = 768,
    GPG_ERR_LDAP_OPERATIONS = 769,
    GPG_ERR_LDAP_PROTOCOL = 770,
    GPG_ERR_LDAP_TIMELIMIT = 771,
    GPG_ERR_LDAP_SIZELIMIT = 772,
    GPG_ERR_LDAP_COMPARE_FALSE = 773,
    GPG_ERR_LDAP_COMPARE_TRUE = 774,
    GPG_ERR_LDAP_UNSUPPORTED_AUTH = 775,
    GPG_ERR_LDAP_STRONG_AUTH_RQRD = 776,
    GPG_ERR_LDAP_PARTIAL_RESULTS = 777,
    GPG_ERR_LDAP_REFERRAL = 778,
    GPG_ERR_LDAP_ADMINLIMIT = 779,
    GPG_ERR_LDAP_UNAVAIL_CRIT_EXTN = 780,
    GPG_ERR_LDAP_CONFIDENT_RQRD = 781,
    GPG_ERR_LDAP_SASL_BIND_INPROG = 782,
    GPG_ERR_LDAP_NO_SUCH_ATTRIBUTE = 784,
    GPG_ERR_LDAP_UNDEFINED_TYPE = 785,
    GPG_ERR_LDAP_BAD_MATCHING = 786,
    GPG_ERR_LDAP_CONST_VIOLATION = 787,
    GPG_ERR_LDAP_TYPE_VALUE_EXISTS = 788,
    GPG_ERR_LDAP_INV_SYNTAX = 789,
    GPG_ERR_LDAP_NO_SUCH_OBJ = 800,
    GPG_ERR_LDAP_ALIAS_PROBLEM = 801,
    GPG_ERR_LDAP_INV_DN_SYNTAX = 802,
    GPG_ERR_LDAP_IS_LEAF = 803,
    GPG_ERR_LDAP_ALIAS_DEREF = 804,
    GPG_ERR_LDAP_X_PROXY_AUTH_FAIL = 815,
    GPG_ERR_LDAP_BAD_AUTH = 816,
    GPG_ERR_LDAP_INV_CREDENTIALS = 817,
    GPG_ERR_LDAP_INSUFFICIENT_ACC = 818,
    GPG_ERR_LDAP_BUSY = 819,
    GPG_ERR_LDAP_UNAVAILABLE = 820,
    GPG_ERR_LDAP_UNWILL_TO_PERFORM = 821,
    GPG_ERR_LDAP_LOOP_DETECT = 822,
    GPG_ERR_LDAP_NAMING_VIOLATION = 832,
    GPG_ERR_LDAP_OBJ_CLS_VIOLATION = 833,
    GPG_ERR_LDAP_NOT_ALLOW_NONLEAF = 834,
    GPG_ERR_LDAP_NOT_ALLOW_ON_RDN = 835,
    GPG_ERR_LDAP_ALREADY_EXISTS = 836,
    GPG_ERR_LDAP_NO_OBJ_CLASS_MODS = 837,
    GPG_ERR_LDAP_RESULTS_TOO_LARGE = 838,
    GPG_ERR_LDAP_AFFECTS_MULT_DSAS = 839,
    GPG_ERR_LDAP_VLV = 844,
    GPG_ERR_LDAP_OTHER = 848,
    GPG_ERR_LDAP_CUP_RESOURCE_LIMIT = 881,
    GPG_ERR_LDAP_CUP_SEC_VIOLATION = 882,
    GPG_ERR_LDAP_CUP_INV_DATA = 883,
    GPG_ERR_LDAP_CUP_UNSUP_SCHEME = 884,
    GPG_ERR_LDAP_CUP_RELOAD = 885,
    GPG_ERR_LDAP_CANCELLED = 886,
    GPG_ERR_LDAP_NO_SUCH_OPERATION = 887,
    GPG_ERR_LDAP_TOO_LATE = 888,
    GPG_ERR_LDAP_CANNOT_CANCEL = 889,
    GPG_ERR_LDAP_ASSERTION_FAILED = 890,
    GPG_ERR_LDAP_PROX_AUTH_DENIED = 891,
    GPG_ERR_USER_1 = 1024,
    GPG_ERR_USER_2 = 1025,
    GPG_ERR_USER_3 = 1026,
    GPG_ERR_USER_4 = 1027,
    GPG_ERR_USER_5 = 1028,
    GPG_ERR_USER_6 = 1029,
    GPG_ERR_USER_7 = 1030,
    GPG_ERR_USER_8 = 1031,
    GPG_ERR_USER_9 = 1032,
    GPG_ERR_USER_10 = 1033,
    GPG_ERR_USER_11 = 1034,
    GPG_ERR_USER_12 = 1035,
    GPG_ERR_USER_13 = 1036,
    GPG_ERR_USER_14 = 1037,
    GPG_ERR_USER_15 = 1038,
    GPG_ERR_USER_16 = 1039,
    GPG_ERR_SQL_OK = 1500,
    GPG_ERR_SQL_ERROR = 1501,
    GPG_ERR_SQL_INTERNAL = 1502,
    GPG_ERR_SQL_PERM = 1503,
    GPG_ERR_SQL_ABORT = 1504,
    GPG_ERR_SQL_BUSY = 1505,
    GPG_ERR_SQL_LOCKED = 1506,
    GPG_ERR_SQL_NOMEM = 1507,
    GPG_ERR_SQL_READONLY = 1508,
    GPG_ERR_SQL_INTERRUPT = 1509,
    GPG_ERR_SQL_IOERR = 1510,
    GPG_ERR_SQL_CORRUPT = 1511,
    GPG_ERR_SQL_NOTFOUND = 1512,
    GPG_ERR_SQL_FULL = 1513,
    GPG_ERR_SQL_CANTOPEN = 1514,
    GPG_ERR_SQL_PROTOCOL = 1515,
    GPG_ERR_SQL_EMPTY = 1516,
    GPG_ERR_SQL_SCHEMA = 1517,
    GPG_ERR_SQL_TOOBIG = 1518,
    GPG_ERR_SQL_CONSTRAINT = 1519,
    GPG_ERR_SQL_MISMATCH = 1520,
    GPG_ERR_SQL_MISUSE = 1521,
    GPG_ERR_SQL_NOLFS = 1522,
    GPG_ERR_SQL_AUTH = 1523,
    GPG_ERR_SQL_FORMAT = 1524,
    GPG_ERR_SQL_RANGE = 1525,
    GPG_ERR_SQL_NOTADB = 1526,
    GPG_ERR_SQL_NOTICE = 1527,
    GPG_ERR_SQL_WARNING = 1528,
    GPG_ERR_SQL_ROW = 1600,
    GPG_ERR_SQL_DONE = 1601,
    GPG_ERR_MISSING_ERRNO = 16381,
    GPG_ERR_UNKNOWN_ERRNO = 16382,
    GPG_ERR_EOF = 16383,
    GPG_ERR_E2BIG = (1 << 15) | 0,
    GPG_ERR_EACCES = (1 << 15) | 1,
    GPG_ERR_EADDRINUSE = (1 << 15) | 2,
    GPG_ERR_EADDRNOTAVAIL = (1 << 15) | 3,
    GPG_ERR_EADV = (1 << 15) | 4,
    GPG_ERR_EAFNOSUPPORT = (1 << 15) | 5,
    GPG_ERR_EAGAIN = (1 << 15) | 6,
    GPG_ERR_EALREADY = (1 << 15) | 7,
    GPG_ERR_EAUTH = (1 << 15) | 8,
    GPG_ERR_EBACKGROUND = (1 << 15) | 9,
    GPG_ERR_EBADE = (1 << 15) | 10,
    GPG_ERR_EBADF = (1 << 15) | 11,
    GPG_ERR_EBADFD = (1 << 15) | 12,
    GPG_ERR_EBADMSG = (1 << 15) | 13,
    GPG_ERR_EBADR = (1 << 15) | 14,
    GPG_ERR_EBADRPC = (1 << 15) | 15,
    GPG_ERR_EBADRQC = (1 << 15) | 16,
    GPG_ERR_EBADSLT = (1 << 15) | 17,
    GPG_ERR_EBFONT = (1 << 15) | 18,
    GPG_ERR_EBUSY = (1 << 15) | 19,
    GPG_ERR_ECANCELED = (1 << 15) | 20,
    GPG_ERR_ECHILD = (1 << 15) | 21,
    GPG_ERR_ECHRNG = (1 << 15) | 22,
    GPG_ERR_ECOMM = (1 << 15) | 23,
    GPG_ERR_ECONNABORTED = (1 << 15) | 24,
    GPG_ERR_ECONNREFUSED = (1 << 15) | 25,
    GPG_ERR_ECONNRESET = (1 << 15) | 26,
    GPG_ERR_ED = (1 << 15) | 27,
    GPG_ERR_EDEADLK = (1 << 15) | 28,
    GPG_ERR_EDEADLOCK = (1 << 15) | 29,
    GPG_ERR_EDESTADDRREQ = (1 << 15) | 30,
    GPG_ERR_EDIED = (1 << 15) | 31,
    GPG_ERR_EDOM = (1 << 15) | 32,
    GPG_ERR_EDOTDOT = (1 << 15) | 33,
    GPG_ERR_EDQUOT = (1 << 15) | 34,
    GPG_ERR_EEXIST = (1 << 15) | 35,
    GPG_ERR_EFAULT = (1 << 15) | 36,
    GPG_ERR_EFBIG = (1 << 15) | 37,
    GPG_ERR_EFTYPE = (1 << 15) | 38,
    GPG_ERR_EGRATUITOUS = (1 << 15) | 39,
    GPG_ERR_EGREGIOUS = (1 << 15) | 40,
    GPG_ERR_EHOSTDOWN = (1 << 15) | 41,
    GPG_ERR_EHOSTUNREACH = (1 << 15) | 42,
    GPG_ERR_EIDRM = (1 << 15) | 43,
    GPG_ERR_EIEIO = (1 << 15) | 44,
    GPG_ERR_EILSEQ = (1 << 15) | 45,
    GPG_ERR_EINPROGRESS = (1 << 15) | 46,
    GPG_ERR_EINTR = (1 << 15) | 47,
    GPG_ERR_EINVAL = (1 << 15) | 48,
    GPG_ERR_EIO = (1 << 15) | 49,
    GPG_ERR_EISCONN = (1 << 15) | 50,
    GPG_ERR_EISDIR = (1 << 15) | 51,
    GPG_ERR_EISNAM = (1 << 15) | 52,
    GPG_ERR_EL2HLT = (1 << 15) | 53,
    GPG_ERR_EL2NSYNC = (1 << 15) | 54,
    GPG_ERR_EL3HLT = (1 << 15) | 55,
    GPG_ERR_EL3RST = (1 << 15) | 56,
    GPG_ERR_ELIBACC = (1 << 15) | 57,
    GPG_ERR_ELIBBAD = (1 << 15) | 58,
    GPG_ERR_ELIBEXEC = (1 << 15) | 59,
    GPG_ERR_ELIBMAX = (1 << 15) | 60,
    GPG_ERR_ELIBSCN = (1 << 15) | 61,
    GPG_ERR_ELNRNG = (1 << 15) | 62,
    GPG_ERR_ELOOP = (1 << 15) | 63,
    GPG_ERR_EMEDIUMTYPE = (1 << 15) | 64,
    GPG_ERR_EMFILE = (1 << 15) | 65,
    GPG_ERR_EMLINK = (1 << 15) | 66,
    GPG_ERR_EMSGSIZE = (1 << 15) | 67,
    GPG_ERR_EMULTIHOP = (1 << 15) | 68,
    GPG_ERR_ENAMETOOLONG = (1 << 15) | 69,
    GPG_ERR_ENAVAIL = (1 << 15) | 70,
    GPG_ERR_ENEEDAUTH = (1 << 15) | 71,
    GPG_ERR_ENETDOWN = (1 << 15) | 72,
    GPG_ERR_ENETRESET = (1 << 15) | 73,
    GPG_ERR_ENETUNREACH = (1 << 15) | 74,
    GPG_ERR_ENFILE = (1 << 15) | 75,
    GPG_ERR_ENOANO = (1 << 15) | 76,
    GPG_ERR_ENOBUFS = (1 << 15) | 77,
    GPG_ERR_ENOCSI = (1 << 15) | 78,
    GPG_ERR_ENODATA = (1 << 15) | 79,
    GPG_ERR_ENODEV = (1 << 15) | 80,
    GPG_ERR_ENOENT = (1 << 15) | 81,
    GPG_ERR_ENOEXEC = (1 << 15) | 82,
    GPG_ERR_ENOLCK = (1 << 15) | 83,
    GPG_ERR_ENOLINK = (1 << 15) | 84,
    GPG_ERR_ENOMEDIUM = (1 << 15) | 85,
    GPG_ERR_ENOMEM = (1 << 15) | 86,
    GPG_ERR_ENOMSG = (1 << 15) | 87,
    GPG_ERR_ENONET = (1 << 15) | 88,
    GPG_ERR_ENOPKG = (1 << 15) | 89,
    GPG_ERR_ENOPROTOOPT = (1 << 15) | 90,
    GPG_ERR_ENOSPC = (1 << 15) | 91,
    GPG_ERR_ENOSR = (1 << 15) | 92,
    GPG_ERR_ENOSTR = (1 << 15) | 93,
    GPG_ERR_ENOSYS = (1 << 15) | 94,
    GPG_ERR_ENOTBLK = (1 << 15) | 95,
    GPG_ERR_ENOTCONN = (1 << 15) | 96,
    GPG_ERR_ENOTDIR = (1 << 15) | 97,
    GPG_ERR_ENOTEMPTY = (1 << 15) | 98,
    GPG_ERR_ENOTNAM = (1 << 15) | 99,
    GPG_ERR_ENOTSOCK = (1 << 15) | 100,
    GPG_ERR_ENOTSUP = (1 << 15) | 101,
    GPG_ERR_ENOTTY = (1 << 15) | 102,
    GPG_ERR_ENOTUNIQ = (1 << 15) | 103,
    GPG_ERR_ENXIO = (1 << 15) | 104,
    GPG_ERR_EOPNOTSUPP = (1 << 15) | 105,
    GPG_ERR_EOVERFLOW = (1 << 15) | 106,
    GPG_ERR_EPERM = (1 << 15) | 107,
    GPG_ERR_EPFNOSUPPORT = (1 << 15) | 108,
    GPG_ERR_EPIPE = (1 << 15) | 109,
    GPG_ERR_EPROCLIM = (1 << 15) | 110,
    GPG_ERR_EPROCUNAVAIL = (1 << 15) | 111,
    GPG_ERR_EPROGMISMATCH = (1 << 15) | 112,
    GPG_ERR_EPROGUNAVAIL = (1 << 15) | 113,
    GPG_ERR_EPROTO = (1 << 15) | 114,
    GPG_ERR_EPROTONOSUPPORT = (1 << 15) | 115,
    GPG_ERR_EPROTOTYPE = (1 << 15) | 116,
    GPG_ERR_ERANGE = (1 << 15) | 117,
    GPG_ERR_EREMCHG = (1 << 15) | 118,
    GPG_ERR_EREMOTE = (1 << 15) | 119,
    GPG_ERR_EREMOTEIO = (1 << 15) | 120,
    GPG_ERR_ERESTART = (1 << 15) | 121,
    GPG_ERR_EROFS = (1 << 15) | 122,
    GPG_ERR_ERPCMISMATCH = (1 << 15) | 123,
    GPG_ERR_ESHUTDOWN = (1 << 15) | 124,
    GPG_ERR_ESOCKTNOSUPPORT = (1 << 15) | 125,
    GPG_ERR_ESPIPE = (1 << 15) | 126,
    GPG_ERR_ESRCH = (1 << 15) | 127,
    GPG_ERR_ESRMNT = (1 << 15) | 128,
    GPG_ERR_ESTALE = (1 << 15) | 129,
    GPG_ERR_ESTRPIPE = (1 << 15) | 130,
    GPG_ERR_ETIME = (1 << 15) | 131,
    GPG_ERR_ETIMEDOUT = (1 << 15) | 132,
    GPG_ERR_ETOOMANYREFS = (1 << 15) | 133,
    GPG_ERR_ETXTBSY = (1 << 15) | 134,
    GPG_ERR_EUCLEAN = (1 << 15) | 135,
    GPG_ERR_EUNATCH = (1 << 15) | 136,
    GPG_ERR_EUSERS = (1 << 15) | 137,
    GPG_ERR_EWOULDBLOCK = (1 << 15) | 138,
    GPG_ERR_EXDEV = (1 << 15) | 139,
    GPG_ERR_EXFULL = (1 << 15) | 140,
    GPG_ERR_CODE_DIM = 65536
};
typedef struct gcry_mpi *gcry_mpi_t;
typedef struct gcry_mpi_point *gcry_mpi_point_t;
enum gcry_ctl_cmds {
    GCRYCTL_CFB_SYNC = 3,
    GCRYCTL_RESET = 4,
    GCRYCTL_FINALIZE = 5,
    GCRYCTL_GET_KEYLEN = 6,
    GCRYCTL_GET_BLKLEN = 7,
    GCRYCTL_TEST_ALGO = 8,
    GCRYCTL_IS_SECURE = 9,
    GCRYCTL_GET_ASNOID = 10,
    GCRYCTL_ENABLE_ALGO = 11,
    GCRYCTL_DISABLE_ALGO = 12,
    GCRYCTL_DUMP_RANDOM_STATS = 13,
    GCRYCTL_DUMP_SECMEM_STATS = 14,
    GCRYCTL_GET_ALGO_NPKEY = 15,
    GCRYCTL_GET_ALGO_NSKEY = 16,
    GCRYCTL_GET_ALGO_NSIGN = 17,
    GCRYCTL_GET_ALGO_NENCR = 18,
    GCRYCTL_SET_VERBOSITY = 19,
    GCRYCTL_SET_DEBUG_FLAGS = 20,
    GCRYCTL_CLEAR_DEBUG_FLAGS = 21,
    GCRYCTL_USE_SECURE_RNDPOOL = 22,
    GCRYCTL_DUMP_MEMORY_STATS = 23,
    GCRYCTL_INIT_SECMEM = 24,
    GCRYCTL_TERM_SECMEM = 25,
    GCRYCTL_DISABLE_SECMEM_WARN = 27,
    GCRYCTL_SUSPEND_SECMEM_WARN = 28,
    GCRYCTL_RESUME_SECMEM_WARN = 29,
    GCRYCTL_DROP_PRIVS = 30,
    GCRYCTL_ENABLE_M_GUARD = 31,
    GCRYCTL_START_DUMP = 32,
    GCRYCTL_STOP_DUMP = 33,
    GCRYCTL_GET_ALGO_USAGE = 34,
    GCRYCTL_IS_ALGO_ENABLED = 35,
    GCRYCTL_DISABLE_INTERNAL_LOCKING = 36,
    GCRYCTL_DISABLE_SECMEM = 37,
    GCRYCTL_INITIALIZATION_FINISHED = 38,
    GCRYCTL_INITIALIZATION_FINISHED_P = 39,
    GCRYCTL_ANY_INITIALIZATION_P = 40,
    GCRYCTL_SET_CBC_CTS = 41,
    GCRYCTL_SET_CBC_MAC = 42,
    GCRYCTL_ENABLE_QUICK_RANDOM = 44,
    GCRYCTL_SET_RANDOM_SEED_FILE = 45,
    GCRYCTL_UPDATE_RANDOM_SEED_FILE = 46,
    GCRYCTL_SET_THREAD_CBS = 47,
    GCRYCTL_FAST_POLL = 48,
    GCRYCTL_SET_RANDOM_DAEMON_SOCKET = 49,
    GCRYCTL_USE_RANDOM_DAEMON = 50,
    GCRYCTL_FAKED_RANDOM_P = 51,
    GCRYCTL_SET_RNDEGD_SOCKET = 52,
    GCRYCTL_PRINT_CONFIG = 53,
    GCRYCTL_OPERATIONAL_P = 54,
    GCRYCTL_FIPS_MODE_P = 55,
    GCRYCTL_FORCE_FIPS_MODE = 56,
    GCRYCTL_SELFTEST = 57,
    GCRYCTL_DISABLE_HWF = 63,
    GCRYCTL_SET_ENFORCED_FIPS_FLAG = 64,
    GCRYCTL_SET_PREFERRED_RNG_TYPE = 65,
    GCRYCTL_GET_CURRENT_RNG_TYPE = 66,
    GCRYCTL_DISABLE_LOCKED_SECMEM = 67,
    GCRYCTL_DISABLE_PRIV_DROP = 68,
    GCRYCTL_SET_CCM_LENGTHS = 69,
    GCRYCTL_CLOSE_RANDOM_DEVICE = 70,
    GCRYCTL_INACTIVATE_FIPS_FLAG = 71,
    GCRYCTL_REACTIVATE_FIPS_FLAG = 72,
    GCRYCTL_SET_SBOX = 73,
    GCRYCTL_DRBG_REINIT = 74,
    GCRYCTL_SET_TAGLEN = 75,
    GCRYCTL_GET_TAGLEN = 76,
    GCRYCTL_REINIT_SYSCALL_CLAMP = 77,
    GCRYCTL_AUTO_EXPAND_SECMEM = 78,
    GCRYCTL_SET_ALLOW_WEAK_KEY = 79,
    GCRYCTL_SET_DECRYPTION_TAG = 80,
    GCRYCTL_FIPS_SERVICE_INDICATOR_CIPHER = 81,
    GCRYCTL_FIPS_SERVICE_INDICATOR_KDF = 82,
    GCRYCTL_NO_FIPS_MODE = 83
};
enum gcry_mpi_format {
    GCRYMPI_FMT_NONE = 0,
    GCRYMPI_FMT_STD = 1,
    GCRYMPI_FMT_PGP = 2,
    GCRYMPI_FMT_SSH = 3,
    GCRYMPI_FMT_HEX = 4,
    GCRYMPI_FMT_USG = 5,
    GCRYMPI_FMT_OPAQUE = 8
};
enum gcry_mpi_flag {
    GCRYMPI_FLAG_SECURE = 1,
    GCRYMPI_FLAG_OPAQUE = 2,
    GCRYMPI_FLAG_IMMUTABLE = 4,
    GCRYMPI_FLAG_CONST = 8,
    GCRYMPI_FLAG_USER1 = 0x0100,
    GCRYMPI_FLAG_USER2 = 0x0200,
    GCRYMPI_FLAG_USER3 = 0x0400,
    GCRYMPI_FLAG_USER4 = 0x0800
};
enum gcry_rng_types {
    GCRY_RNG_TYPE_STANDARD = 1,
    GCRY_RNG_TYPE_FIPS = 2,
    GCRY_RNG_TYPE_SYSTEM = 3
};
enum gcry_random_level {
    GCRY_WEAK_RANDOM = 0,
    GCRY_STRONG_RANDOM = 1,
    GCRY_VERY_STRONG_RANDOM = 2
};
enum gcry_log_levels {
    GCRY_LOG_CONT = 0,
    GCRY_LOG_INFO = 10,
    GCRY_LOG_WARN = 20,
    GCRY_LOG_ERROR = 30,
    GCRY_LOG_FATAL = 40,
    GCRY_LOG_BUG = 50,
    GCRY_LOG_DEBUG = 100
};
struct mpi_ec_ctx_s;
typedef struct mpi_ec_ctx_s *mpi_ec_t;
typedef unsigned long mpi_limb_t;
struct gcry_mpi {
   int alloced ;
   int nlimbs ;
   int sign ;
   unsigned int flags ;
   mpi_limb_t *d ;
};
enum gcry_mpi_constants {
    MPI_C_ZERO = 0,
    MPI_C_ONE = 1,
    MPI_C_TWO = 2,
    MPI_C_THREE = 3,
    MPI_C_FOUR = 4,
    MPI_C_EIGHT = 5
};
typedef struct barrett_ctx_s *mpi_barrett_t;
struct gcry_mpi_point {
   gcry_mpi_t x ;
   gcry_mpi_t y ;
   gcry_mpi_t z ;
};
enum gcry_mpi_ec_models {
    MPI_EC_WEIERSTRASS = 0,
    MPI_EC_MONTGOMERY = 1,
    MPI_EC_EDWARDS = 2
};
enum ecc_dialects {
    ECC_DIALECT_STANDARD = 0,
    ECC_DIALECT_ED25519 = 1,
    ECC_DIALECT_SAFECURVE = 2
};
struct __anonstruct_valid_16 {
   unsigned int a_is_pminus3 : 1 ;
   unsigned int two_inv_p : 1 ;
};
struct __anonstruct_t_15 {
   struct __anonstruct_valid_16 valid ;
   int a_is_pminus3 ;
   gcry_mpi_t two_inv_p ;
   mpi_barrett_t p_barrett ;
   gcry_mpi_t scratch[11] ;
};
struct mpi_ec_ctx_s {
   enum gcry_mpi_ec_models model ;
   enum ecc_dialects dialect ;
   int flags ;
   unsigned int nbits ;
   gcry_mpi_t p ;
   gcry_mpi_t a ;
   gcry_mpi_t b ;
   gcry_mpi_point_t G ;
   gcry_mpi_t n ;
   unsigned int h ;
   gcry_mpi_point_t Q ;
   gcry_mpi_t d ;
   char const *name ;
   struct __anonstruct_t_15 t ;
   void (*addm)(gcry_mpi_t w, gcry_mpi_t u, gcry_mpi_t v, mpi_ec_t ctx) ;
   void (*subm)(gcry_mpi_t w, gcry_mpi_t u, gcry_mpi_t v, mpi_ec_t ec) ;
   void (*mulm)(gcry_mpi_t w, gcry_mpi_t u, gcry_mpi_t v, mpi_ec_t ctx) ;
   void (*pow2)(gcry_mpi_t w, gcry_mpi_t const b, mpi_ec_t ctx) ;
   void (*mul2)(gcry_mpi_t w, gcry_mpi_t u, mpi_ec_t ctx) ;
   void (*mod)(gcry_mpi_t w, mpi_ec_t ctx) ;
};
typedef mpi_limb_t *mpi_ptr_t;
typedef int mpi_size_t;
typedef unsigned int __attribute__((__mode__(DI))) UDItype;
struct barrett_ctx_s {
   gcry_mpi_t m ;
   int m_copied ;
   int k ;
   gcry_mpi_t y ;
   gcry_mpi_t r1 ;
   gcry_mpi_t r2 ;
   gcry_mpi_t r3 ;
};
gcry_mpi_t ( __attribute__((__visibility__("default"))) gcry_mpi_new_slice_1)
(unsigned int nbits);

void ( __attribute__((__visibility__("default"))) gcry_mpi_set_ui_slice_1)
(gcry_mpi_t w, unsigned long u);

void ( __attribute__((__visibility__("default"))) gcry_mpi_powm_slice_1)
(gcry_mpi_t w, gcry_mpi_t const b, gcry_mpi_t const e, gcry_mpi_t const m);

extern int Frama_C_interval(int a, int b);

void main(void)
{
  int tmp;
  int tmp_0;
  int tmp_1;
  tmp = Frama_C_interval(-100,100);
  unsigned long A = (unsigned long)tmp;
  tmp_0 = Frama_C_interval(0,10);
  unsigned long E = (unsigned long)tmp_0;
  tmp_1 = Frama_C_interval(2,100);
  unsigned long N = (unsigned long)tmp_1;
  gcry_mpi_t base = gcry_mpi_new_slice_1((unsigned int)256);
  gcry_mpi_t exp = gcry_mpi_new_slice_1((unsigned int)256);
  gcry_mpi_t mod = gcry_mpi_new_slice_1((unsigned int)256);
  gcry_mpi_t result = gcry_mpi_new_slice_1((unsigned int)256);
  gcry_mpi_set_ui_slice_1(base,A);
  gcry_mpi_set_ui_slice_1(exp,E);
  gcry_mpi_set_ui_slice_1(mod,N);
  gcry_mpi_powm_slice_1(result,base,exp,mod);
  return;
}

gcry_mpi_t _gcry_mpi_new_slice_1(unsigned int nbits);

void _gcry_mpi_set_ui_slice_1(gcry_mpi_t w, unsigned long u);

void _gcry_mpi_powm_slice_1(gcry_mpi_t res, gcry_mpi_t base, gcry_mpi_t expo,
                            gcry_mpi_t mod);

void *_gcry_xmalloc_slice_1(size_t n);

void _gcry_free_slice_1(void *p);

void _gcry_fast_wipememory(void *ptr, size_t len);

gcry_mpi_t _gcry_mpi_alloc_slice_1(unsigned int nlimbs);

void _gcry_mpi_set_cond_slice_1(gcry_mpi_t w, gcry_mpi_t const u,
                                unsigned long set);

gcry_mpi_t ( __attribute__((__visibility__("default"))) gcry_mpi_new_slice_1)
(unsigned int nbits)
{
  gcry_mpi_t tmp;
  tmp = _gcry_mpi_new_slice_1(nbits);
  return tmp;
}

void ( __attribute__((__visibility__("default"))) gcry_mpi_set_ui_slice_1)
(gcry_mpi_t w, unsigned long u)
{
  _gcry_mpi_set_ui_slice_1(w,u);
  return;
}

void ( __attribute__((__visibility__("default"))) gcry_mpi_powm_slice_1)
(gcry_mpi_t w, gcry_mpi_t const b, gcry_mpi_t const e, gcry_mpi_t const m)
{
  _gcry_mpi_powm_slice_1(w,b,e,m);
  return;
}

void _gcry_private_free(void *a);

#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wswitch"
#pragma GCC diagnostic pop
void _gcry_free_slice_1(void *p)
{
  _gcry_private_free(p);
  return;
}

void *_gcry_xmalloc_slice_1(size_t n)
{
  void *p = malloc(n);
  return p;
}

mpi_ptr_t _gcry_mpi_alloc_limb_space_slice_1(unsigned int nlimbs);

void _gcry_mpi_free_limb_space_slice_1(mpi_ptr_t a, unsigned int nlimbs);

void _gcry_mpih_mul_slice_1(mpi_ptr_t prodp, mpi_ptr_t up, mpi_size_t usize,
                            mpi_ptr_t vp, mpi_size_t vsize);

mpi_limb_t _gcry_mpih_mul_1_slice_1(mpi_ptr_t res_ptr, mpi_size_t s1_size);

void _gcry_mpih_divrem_slice_1(mpi_ptr_t np, mpi_size_t nsize, mpi_ptr_t dp,
                               mpi_size_t dsize);

mpi_limb_t _gcry_mpih_lshift_slice_1(mpi_ptr_t wp, mpi_ptr_t up,
                                     mpi_size_t usize, unsigned int cnt);

void _gcry_mpih_rshift_slice_1(mpi_ptr_t wp, mpi_ptr_t up, unsigned int cnt);

static void mul_mod_slice_1(mpi_ptr_t xp, mpi_size_t *xsize_p, mpi_ptr_t rp,
                            mpi_size_t rsize, mpi_ptr_t sp, mpi_size_t ssize,
                            mpi_ptr_t mp, mpi_size_t msize)
{
  _gcry_mpih_mul_slice_1(xp,rp,rsize,sp,ssize);
  if (rsize + ssize > msize) {
    _gcry_mpih_divrem_slice_1(xp,rsize + ssize,mp,msize);
    *xsize_p = msize;
  }
  else *xsize_p = rsize + ssize;
  return;
}

void _gcry_mpi_powm_slice_1(gcry_mpi_t res, gcry_mpi_t base, gcry_mpi_t expo,
                            gcry_mpi_t mod)
{
  mpi_ptr_t rp;
  mpi_ptr_t ep;
  mpi_ptr_t mp;
  mpi_ptr_t bp;
  mpi_size_t esize;
  mpi_size_t msize;
  mpi_size_t bsize;
  mpi_size_t rsize;
  int rsign;
  mpi_size_t size;
  int mod_shift_cnt;
  mpi_ptr_t precomp[1 << (5 - 1)];
  mpi_size_t precomp_size[1 << (5 - 1)];
  mpi_size_t W;
  mpi_ptr_t base_u;
  mpi_size_t base_u_size;
  mpi_size_t max_u_size;
  mpi_ptr_t mp_marker = (mpi_ptr_t)0;
  mpi_ptr_t xp_marker = (mpi_ptr_t)0;
  unsigned int mp_nlimbs = (unsigned int)0;
  unsigned int xp_nlimbs = (unsigned int)0;
  esize = expo->nlimbs;
  msize = mod->nlimbs;
  size = 2 * msize;
  ep = expo->d;
  while (esize > 0) {
    /*@ \slicing::slice_preserve_ctrl ; */ ;
    /*@ \slicing::slice_preserve_stmt ; */
    if (*(ep + (esize - 1))) break;
    esize --;
  }
  W = 1;
  rp = res->d;
  if (! esize) {
    if (*(mod->d + 0) == (mpi_limb_t)1) res->nlimbs = 0;
    else res->nlimbs = 1;
    if (res->nlimbs) {
      rp = res->d;
      /*@ assert \valid(rp + 0); */ ;
      *(rp + 0) = (mpi_limb_t)1;
    }
    res->sign = 0;
    goto leave;
  }
  mp_nlimbs = (unsigned int)0;
  mp_marker = _gcry_mpi_alloc_limb_space_slice_1((unsigned int)msize);
  mp = mp_marker;
  {
    UDItype __cbtmp = (UDItype)0;
    mod_shift_cnt = (int)(__cbtmp ^ (unsigned int __attribute__((__mode__(DI))))63);
  }
  if (mod_shift_cnt) _gcry_mpih_lshift_slice_1(mp,mod->d,msize,
                                               (unsigned int)mod_shift_cnt);
  else {
    mpi_size_t _i;
    _i = 0;
    while (_i < msize) {
      *(mp + _i) = *(mod->d + _i);
      _i ++;
    }
  }
  bsize = base->nlimbs;
  bp = base->d;
  if (! bsize) {
    res->nlimbs = 0;
    res->sign = 0;
    goto leave;
  }
  {
    mpi_size_t i;
    mpi_size_t j;
    mpi_size_t k;
    mpi_ptr_t xp;
    mpi_size_t xsize;
    int c;
    mpi_limb_t e;
    mpi_limb_t carry_limb;
    mpi_ptr_t tp;
    mpi_size_t tmp_7;
    xp_nlimbs = (unsigned int)0;
    xp_marker = _gcry_mpi_alloc_limb_space_slice_1((unsigned int)size);
    xp = xp_marker;
    /*@ \slicing::slice_preserve_ctrl ; */ ;
    precomp[0] = _gcry_mpi_alloc_limb_space_slice_1((unsigned int)bsize);
    precomp_size[0] = bsize;
    max_u_size = precomp_size[0];
    {
      mpi_size_t _i_3;
      _i_3 = 0;
      while (_i_3 < bsize) {
        *(precomp[0] + _i_3) = *(bp + _i_3);
        _i_3 ++;
      }
    }
    base_u = _gcry_mpi_alloc_limb_space_slice_1((unsigned int)max_u_size);
    {
      int _i_5;
      _i_5 = 0;
      while (_i_5 < max_u_size) {
        *(base_u + _i_5) = (mpi_limb_t)0;
        _i_5 ++;
      }
    }
    i = esize - 1;
    rsign = 0;
    rsize = bsize;
    {
      mpi_size_t _i_7;
      _i_7 = 0;
      while (_i_7 < bsize) {
        *(rp + _i_7) = *(bp + _i_7);
        _i_7 ++;
      }
    }
    e = *(ep + i);
    {
      UDItype __cbtmp_0 = (UDItype)0;
      c = (int)(__cbtmp_0 ^ (unsigned int __attribute__((__mode__(DI))))63);
    }
    /*@ assert 0 ≤ c ≤ 8 * 8 - 1; */ ;
    e = (e << c) << 1;
    c = (8 * 8 - 1) - c;
    j = 0;
    while (1) 
      if (e == (mpi_limb_t)0) {
        j += c;
        /*@ \slicing::slice_preserve_ctrl ; */ ;
        break;
      }
      else {
        int c0;
        mpi_limb_t e0;
        struct gcry_mpi w;
        struct gcry_mpi u;
        w.d = base_u;
        {
          UDItype __cbtmp_1 = (UDItype)0;
          c0 = (int)(__cbtmp_1 ^ (unsigned int __attribute__((__mode__(DI))))63);
        }
        /*@ assert 0 ≤ c0 ≤ 8 * 8 - 1; */ ;
        e <<= c0;
        c -= c0;
        j += c0;
        e0 = e >> (8 * 8 - W);
        /*@ \slicing::slice_preserve_ctrl ; */ ;
        if (c >= W) c0 = 0;
        else 
          /*@ assert 0 ≤ c0 ≤ 8 * 8 - 1; */ ;
        e <<= W - c0;
        c -= W - c0;
        {
          UDItype __cbtmp_2 = (UDItype)0;
          c0 = (int)__cbtmp_2;
        }
        /*@ assert 0 ≤ c0 ≤ 8 * 8 - 1; */ ;
        e <<= c0;
        e0 = (e0 >> c0) >> 1;
        /*@ \slicing::slice_preserve_ctrl ; */ ;
        j += W - c0;
        while (j >= 0) {
          base_u_size = 0;
          k = 0;
          while (k < 1 << (W - 1)) {
            u.nlimbs = precomp_size[k];
            u.alloced = u.nlimbs;
            u.d = precomp[k];
            _gcry_mpi_set_cond_slice_1(& w,& u,
                                       (unsigned long)((mpi_limb_t)k == e0));
            base_u_size = (mpi_size_t)((unsigned long)base_u_size | (
                                       (unsigned long)precomp_size[k] & (
                                       0UL - (unsigned long)((mpi_limb_t)k == e0))));
            k ++;
          }
          u.nlimbs = rsize;
          u.alloced = u.nlimbs;
          u.d = rp;
          _gcry_mpi_set_cond_slice_1(& w,& u,(unsigned long)(j != 0));
          base_u_size = (mpi_size_t)((unsigned long)base_u_size ^ ((unsigned long)(
                                                                   base_u_size ^ rsize) & (
                                                                   0UL - (unsigned long)(
                                                                   j != 0))));
          mul_mod_slice_1(xp,& xsize,rp,rsize,base_u,base_u_size,mp,msize);
          tp = rp;
          rp = xp;
          xp = tp;
          rsize = xsize;
          j --;
        }
        j = c0;
      }
    /*@ \slicing::slice_preserve_ctrl ; */ ;
    while (1) {
      mpi_size_t tmp_5;
      tmp_5 = j;
      j --;
      if (! tmp_5) break;
      mul_mod_slice_1(xp,& xsize,rp,rsize,rp,rsize,mp,msize);
      tp = rp;
      rp = xp;
      xp = tp;
      rsize = xsize;
    }
    if (mod_shift_cnt) {
      carry_limb = _gcry_mpih_lshift_slice_1(res->d,rp,rsize,
                                             (unsigned int)mod_shift_cnt);
      rp = res->d;
      if (carry_limb) {
        *(rp + rsize) = carry_limb;
        rsize ++;
      }
    }
    else 
      if (res->d != rp) {
        {
          mpi_size_t _i_8;
          _i_8 = 0;
          while (_i_8 < rsize) {
            *(res->d + _i_8) = *(rp + _i_8);
            _i_8 ++;
          }
        }
        rp = res->d;
      }
    _gcry_mpih_divrem_slice_1(rp,rsize,mp,msize);
    rsize = msize;
    if (mod_shift_cnt) _gcry_mpih_rshift_slice_1(rp,rp,
                                                 (unsigned int)mod_shift_cnt);
    while (rsize > 0) {
      if (*(rp + (rsize - 1))) break;
      rsize --;
    }
    i = 0;
    while (i < 1 << (W - 1)) {
      mpi_size_t tmp_6;
      tmp_6 = 0;
      _gcry_mpi_free_limb_space_slice_1(precomp[i],(unsigned int)tmp_6);
      i ++;
    }
    tmp_7 = 0;
    _gcry_mpi_free_limb_space_slice_1(base_u,(unsigned int)tmp_7);
  }
  res->nlimbs = rsize;
  res->sign = rsign;
  leave: ;
  if (mp_marker) _gcry_mpi_free_limb_space_slice_1(mp_marker,mp_nlimbs);
  if (xp_marker) _gcry_mpi_free_limb_space_slice_1(xp_marker,xp_nlimbs);
  return;
}

void _gcry_mpih_divrem_slice_1(mpi_ptr_t np, mpi_size_t nsize, mpi_ptr_t dp,
                               mpi_size_t dsize)
{
  switch (dsize) {
    case 0: ;
    case 1:
    {
      mpi_limb_t n1;
      mpi_limb_t d;
      d = *(dp + 0);
      n1 = *(np + (nsize - 1));
      if (n1 >= d) n1 -= d;
      *(np + 0) = n1;
    }
    break;
    case 2: ;
    default: ;
  }
  return;
}

mpi_limb_t _gcry_mpih_lshift_slice_1(mpi_ptr_t wp, mpi_ptr_t up,
                                     mpi_size_t usize, unsigned int cnt)
{
  mpi_limb_t high_limb;
  mpi_limb_t low_limb;
  unsigned int sh_1;
  unsigned int sh_2;
  mpi_size_t i;
  mpi_limb_t retval;
  sh_1 = cnt;
  wp ++;
  sh_2 = (unsigned int)(8 * 8) - sh_1;
  i = usize - 1;
  low_limb = *(up + i);
  retval = low_limb >> sh_2;
  high_limb = low_limb;
  i --;
  goto break_cont_1;
  break_cont_1: *(wp + i) = high_limb << sh_1;
  return retval;
}

void _gcry_mpih_mul_slice_1(mpi_ptr_t prodp, mpi_ptr_t up, mpi_size_t usize,
                            mpi_ptr_t vp, mpi_size_t vsize)
{
  mpi_limb_t cy;
  {
    mpi_limb_t v_limb;
    if (! vsize) goto return_label;
    v_limb = *(vp + 0);
    if (v_limb <= (mpi_limb_t)1) {
      if (v_limb == (mpi_limb_t)1) {
        mpi_size_t _i;
        _i = 0;
        while (_i < usize) {
          *(prodp + _i) = *(up + _i);
          _i ++;
        }
      }
      else {
        int _i_0;
        _i_0 = 0;
        while (_i_0 < usize) {
          *(prodp + _i_0) = (mpi_limb_t)0;
          _i_0 ++;
        }
      }
      cy = (mpi_limb_t)0;
    }
    else cy = _gcry_mpih_mul_1_slice_1(prodp,usize);
    *(prodp + usize) = cy;
  }
  return_label: return;
}

mpi_limb_t _gcry_mpih_mul_1_slice_1(mpi_ptr_t res_ptr, mpi_size_t s1_size)
{
  mpi_limb_t cy_limb;
  mpi_size_t j;
  mpi_limb_t prod_high;
  mpi_limb_t prod_low;
  j = - s1_size;
  res_ptr -= j;
  cy_limb = (mpi_limb_t)0;
  while (1) {
    {
      int tmp;
      prod_low += cy_limb;
      tmp = 0;
      cy_limb = (mpi_limb_t)tmp + prod_high;
      *(res_ptr + j) = prod_low;
    }
    j ++;
    break;
  }
  return cy_limb;
}

void _gcry_mpih_rshift_slice_1(mpi_ptr_t wp, mpi_ptr_t up, unsigned int cnt)
{
  mpi_limb_t high_limb;
  mpi_limb_t low_limb;
  unsigned int sh_1;
  mpi_size_t i;
  sh_1 = cnt;
  wp --;
  high_limb = *(up + 0);
  low_limb = high_limb;
  i = 1;
  *(wp + i) = low_limb >> sh_1;
  return;
}

static mpi_limb_t volatile vzero_0 = (mpi_limb_t)0;
static mpi_limb_t volatile vone_0 = (mpi_limb_t)1;
extern void Frama_C_make_unknown(void *ptr, unsigned long size);

gcry_mpi_t _gcry_mpi_alloc_slice_1(unsigned int nlimbs)
{
  gcry_mpi_t a;
  a = (gcry_mpi_t)_gcry_xmalloc_slice_1(sizeof(*a));
  a->d = _gcry_mpi_alloc_limb_space_slice_1(nlimbs + (unsigned int)3);
  Frama_C_make_unknown((void *)a->d,
                       (unsigned long)nlimbs * sizeof(mpi_limb_t));
  a->alloced = (int)(nlimbs + (unsigned int)3);
  a->nlimbs = 0;
  a->sign = 0;
  a->flags = (unsigned int)0;
  return a;
}

mpi_ptr_t _gcry_mpi_alloc_limb_space_slice_1(unsigned int nlimbs)
{
  mpi_ptr_t p = malloc((unsigned long)nlimbs * sizeof(mpi_limb_t));
  Frama_C_make_unknown((void *)p,(unsigned long)nlimbs * sizeof(mpi_limb_t));
  return p;
}

void _gcry_mpi_free_limb_space_slice_1(mpi_ptr_t a, unsigned int nlimbs)
{
  if (a) {
    size_t len = (unsigned long)nlimbs * sizeof(mpi_limb_t);
    if (len) 
      if (1) goto _LOR; else _LOR: _gcry_fast_wipememory((void *)a,len);
    _gcry_free_slice_1((void *)a);
  }
  return;
}

void _gcry_mpi_set_cond_slice_1(gcry_mpi_t w, gcry_mpi_t const u,
                                unsigned long set)
{
  mpi_size_t i;
  mpi_limb_t xu;
  mpi_limb_t xw;
  mpi_size_t nlimbs = u->alloced;
  mpi_limb_t mask1 = vzero_0 - set;
  mpi_limb_t mask2 = set - vone_0;
  mpi_limb_t *uu = u->d;
  mpi_limb_t *uw = w->d;
  i = 0;
  while (i < nlimbs) {
    xu = *(uu + i);
    xw = *(uw + i);
    *(uw + i) = (xw & mask2) | (xu & mask1);
    i ++;
  }
  return;
}

void _gcry_mpi_set_ui_slice_1(gcry_mpi_t w, unsigned long u)
{
  *(w->d + 0) = u;
  if (u) w->nlimbs = 1; else w->nlimbs = 0;
  w->sign = 0;
  w->flags = (unsigned int)0;
  return;
}

gcry_mpi_t _gcry_mpi_new_slice_1(unsigned int nbits)
{
  gcry_mpi_t tmp;
  tmp = _gcry_mpi_alloc_slice_1(((nbits + (unsigned int)(8 * 8)) - (unsigned int)1) / (unsigned int)(
                                8 * 8));
  return tmp;
}


