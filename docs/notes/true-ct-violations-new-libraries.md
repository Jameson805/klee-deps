# True Constant-Time Violations in Newly Added Libraries

## Scope and Method

This note covers only the newly added libraries under:

- `results/klee_cf_results_bearssl`
- `results/klee_cf_results_new`

It excludes the Mbed TLS, Libgcrypt, and OpenSSL families you asked to skip. One OpenSSL-derived benchmark is included as requested: `openssl_almeida_tls_rempad_luk13`.

I treated a location as a reproduced true positive when the top-level JSON row had `reproduced_status == "success"`. The tables below collapse duplicate rows to unique `(file, line, column, code)` locations, because the merged JSONs can repeat the same reproduced site. In this scope, every non-empty top-level JSON report already reproduced successfully, so the manual-review notes below are all extra suspected true violations that were not surfaced separately by the included reports.

The `File` column uses short repo-relative paths for readability. For JSON rows that used `./foo.c`, I normalized them to the actual benchmark path.

When I say an input is secret, I mean the runner-visible symbolic input name from the benchmark configuration or result JSON, such as `skey`, `key`, or `data`. Where the C benchmark stores the same bytes in concrete local buffers such as `skey_buf`, `data_buf`, `in_key`, or `in`, I name both so the data flow is easy to follow.

## BearSSL

### bearssl_aes_big

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| memory | src/symcipher/aes_big_enc.c | 108 | 8 | `v0 = SboxExt0(s0 >> 24)` |
| memory | src/symcipher/aes_big_enc.c | 109 | 6 | `^ SboxExt1((s1 >> 16) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 110 | 6 | `^ SboxExt2((s2 >> 8) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 111 | 6 | `^ SboxExt3(s3 & 0xFF);` |
| memory | src/symcipher/aes_big_enc.c | 112 | 8 | `v1 = SboxExt0(s1 >> 24)` |
| memory | src/symcipher/aes_big_enc.c | 113 | 6 | `^ SboxExt1((s2 >> 16) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 114 | 6 | `^ SboxExt2((s3 >> 8) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 115 | 6 | `^ SboxExt3(s0 & 0xFF);` |
| memory | src/symcipher/aes_big_enc.c | 116 | 8 | `v2 = SboxExt0(s2 >> 24)` |
| memory | src/symcipher/aes_big_enc.c | 117 | 6 | `^ SboxExt1((s3 >> 16) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 118 | 6 | `^ SboxExt2((s0 >> 8) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 119 | 6 | `^ SboxExt3(s1 & 0xFF);` |
| memory | src/symcipher/aes_big_enc.c | 120 | 8 | `v3 = SboxExt0(s3 >> 24)` |
| memory | src/symcipher/aes_big_enc.c | 121 | 6 | `^ SboxExt1((s0 >> 16) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 122 | 6 | `^ SboxExt2((s1 >> 8) & 0xFF)` |
| memory | src/symcipher/aes_big_enc.c | 123 | 6 | `^ SboxExt3(s2 & 0xFF);` |
| memory | src/symcipher/aes_big_enc.c | 133 | 18 | `t0 = ((uint32_t)S[s0 >> 24] << 24)` |
| memory | src/symcipher/aes_big_enc.c | 134 | 16 | `\| ((uint32_t)S[(s1 >> 16) & 0xFF] << 16)` |
| memory | src/symcipher/aes_big_enc.c | 135 | 16 | `\| ((uint32_t)S[(s2 >> 8) & 0xFF] << 8)` |
| memory | src/symcipher/aes_big_enc.c | 136 | 15 | `\| (uint32_t)S[s3 & 0xFF];` |
| memory | src/symcipher/aes_big_enc.c | 137 | 18 | `t1 = ((uint32_t)S[s1 >> 24] << 24)` |
| memory | src/symcipher/aes_big_enc.c | 138 | 16 | `\| ((uint32_t)S[(s2 >> 16) & 0xFF] << 16)` |
| memory | src/symcipher/aes_big_enc.c | 139 | 16 | `\| ((uint32_t)S[(s3 >> 8) & 0xFF] << 8)` |
| memory | src/symcipher/aes_big_enc.c | 140 | 15 | `\| (uint32_t)S[s0 & 0xFF];` |
| memory | src/symcipher/aes_big_enc.c | 141 | 18 | `t2 = ((uint32_t)S[s2 >> 24] << 24)` |
| memory | src/symcipher/aes_big_enc.c | 142 | 16 | `\| ((uint32_t)S[(s3 >> 16) & 0xFF] << 16)` |
| memory | src/symcipher/aes_big_enc.c | 143 | 16 | `\| ((uint32_t)S[(s0 >> 8) & 0xFF] << 8)` |
| memory | src/symcipher/aes_big_enc.c | 144 | 15 | `\| (uint32_t)S[s1 & 0xFF];` |
| memory | src/symcipher/aes_big_enc.c | 145 | 18 | `t3 = ((uint32_t)S[s3 >> 24] << 24)` |
| memory | src/symcipher/aes_big_enc.c | 146 | 16 | `\| ((uint32_t)S[(s0 >> 16) & 0xFF] << 16)` |
| memory | src/symcipher/aes_big_enc.c | 147 | 16 | `\| ((uint32_t)S[(s1 >> 8) & 0xFF] << 8)` |
| memory | src/symcipher/aes_big_enc.c | 148 | 15 | `\| (uint32_t)S[s2 & 0xFF];` |

This benchmark implements AES block encryption using BearSSL's `aes_big` backend, which is a classic table-driven software implementation built around precomputed lookup tables (`Ssm0[]` for round transforms and `S[]` for the final round) instead of a constant-time bitsliced or arithmetic S-box. The secret benchmark inputs are `skey_buf` (named `skey` in the result JSON) and `data_buf` (named `data`). The BearSSL wrapper copies `skey_buf` into `ctx.skey` and passes `data_buf` into `br_aes_big_encrypt()`. Inside `br_aes_big_encrypt()`, `data_buf` is decoded into `s0`, `s1`, `s2`, and `s3`; then lines like `s0 ^= skey[0]` through `s3 ^= skey[3]` mix in words from the secret expanded schedule stored in `ctx.skey`. After that, the reported expressions at lines 108-123 take byte slices such as `s0 >> 24`, `(s1 >> 16) & 0xFF`, and `s3 & 0xFF` and use them as indices into `Ssm0[]` via `SboxExt0..3()`. The reported expressions at lines 133-148 do the same thing with the final-round `S[]` table. The memory address therefore depends on bytes of `s0..s3`, and `s0..s3` themselves come from the secret block `data_buf` after xor with the secret schedule `skey_buf`, so these are genuine secret-dependent memory accesses.

Manual review found more likely true violations in the same BearSSL AES family that were not surfaced separately by the included reports:

- `benchmarks/bearssl/bearssl-0.6/src/symcipher/aes_big_dec.c:205-220` has the same flow as the reproduced encrypt-side hits: secret `data_buf` bytes are decoded into `s0..s3`, xored with the secret schedule copied from `skey_buf`, and the resulting state bytes index `iSsm0[]` and `iS[]`.
- `benchmarks/bearssl/bearssl-0.6/src/symcipher/aes_common.c:63-66` implements `SubWord()` for `br_aes_keysched()`. There the secret input is the raw AES key pointer `key`; bytes extracted from the key-derived word `x` become indices into `S[]`, so the key schedule itself leaks through table addresses.
- `benchmarks/bearssl/bearssl-0.6/src/symcipher/aes_small_enc.c:51` updates `state[i] = S[state[i]];`. In that backend, `state[i]` is a byte of the AES state derived from the secret plaintext/ciphertext block and the secret round key, so the S-box access is also secret-indexed.

### bearssl_des_tab

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| memory | src/symcipher/des_tab.c | 211 | 5 | `S1[((r1 >> 11) ^ (skl >> 18)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 212 | 5 | `\| S2[((r0 >> 23) ^ (skl >> 12)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 213 | 5 | `\| S3[((r0 >> 19) ^ (skl >> 6)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 214 | 5 | `\| S4[((r0 >> 15) ^ (skl )) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 215 | 5 | `\| S5[((r0 >> 11) ^ (skr >> 18)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 216 | 5 | `\| S6[((r0 >> 7) ^ (skr >> 12)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 217 | 5 | `\| S7[((r0 >> 3) ^ (skr >> 6)) & 0x3F]` |
| memory | src/symcipher/des_tab.c | 218 | 5 | `\| S8[((r1 >> 15) ^ (skr )) & 0x3F];` |

This benchmark implements DES block encryption with BearSSL's `des_tab` backend, a table-based Feistel implementation whose round function is written as explicit S-box table lookups rather than as a constant-time boolean network. The secret benchmark inputs are `skey_buf` (reported as `skey`) and `data_buf` (reported as `data`). The wrapper copies `skey_buf` into `ctx.skey`, decodes `data_buf` into the left and right block halves, and calls `process_block_unit(&l, &r, skey)`. Inside `Fconf()`, the reported index expressions such as `((r0 >> 23) ^ (skl >> 12)) & 0x3F` and `((r1 >> 15) ^ skr) & 0x3F` mix bits from the secret block half (`r0` or `r1`) with bits from the secret round subkeys (`skl` and `skr`). Those mixed six-bit values are then used as indices into `S1..S8`. The memory address therefore depends on `data_buf`, `skey_buf`, or both, which makes these true secret-dependent table accesses.

I did not find another distinct unreported source location in `des_tab.c` itself beyond these eight S-box lookups. The same vulnerable `Fconf()` is simply reused round after round. BearSSL also ships a separate `des_ct.c` backend, so this issue is specific to the table-based `des_tab` implementation.

## appliedCryp

### appliedcryp_3way

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| branch | appliedCryp/3way.c | 36 | 6 | `if(a[0]&1) b[2] \|= 1 ;` |
| branch | appliedCryp/3way.c | 37 | 6 | `if(a[1]&1) b[1] \|= 1 ;` |
| branch | appliedCryp/3way.c | 38 | 6 | `if(a[2]&1) b[0] \|= 1 ;` |

This benchmark implements the 3-Way block cipher. The code is a word-oriented software implementation of the cipher's linear and nonlinear permutation layers (`theta`, `pi_1`, `gamma`, `pi_2`), and the reported site is in `mu()`, the bit-reversal permutation used during key setup. The secret benchmark inputs are `in_key` (reported as `key`) and `in` (reported as `data`), but only `in_key` reaches these three sites. `main()` passes `in_key` into `twy_key()`, which copies those three secret 32-bit words into `c->ki` and then calls `mu(c->ki)`. Inside `mu()`, the parameter `a` points at that key-derived array, so `a[0]`, `a[1]`, and `a[2]` are still just transformed views of `in_key`. Each reported `if(a[i] & 1)` tests the current low bit of one secret-derived word and conditionally copies it into `b[2]`, `b[1]`, or `b[0]`. Since the branch predicate is literally a bit of `in_key`, these are direct secret-dependent control-flow leaks.

I did not find another distinct branch or memory-access leak near this benchmarked code. The three reproduced `mu()` branches are the core issue.

### appliedcryp_des

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| branch | appliedCryp/des.c | 130 | 17 | `if( pcr[pc2[j]] ) kn[m] \|= bigbyte[j];` |
| branch | appliedCryp/des.c | 131 | 17 | `if( pcr[pc2[j+24]] ) kn[n] \|= bigbyte[j];` |

This benchmark implements DES. The code uses the traditional software approach from older DES implementations: explicit permutation tables (`pc1`, `pc2`, `totrot`) and bit-assembly helpers (`bigbyte`) rather than constant-time bit-sliced logic. The secret benchmark inputs are `in_key` (reported as `key`) and `in` (reported as `data`), but only `in_key` reaches the reported branches. `main()` calls `deskey(in_key, EN0)`. Inside `deskey()`, bytes of `in_key` are first unpacked into one-bit entries in `pc1m[]`; then the DES key rotations copy those bits into `pcr[]`; then lines 130-131 read `pcr[pc2[j]]` and `pcr[pc2[j+24]]`. Each of those values is a single secret bit derived from `in_key` after the PC-1 and PC-2 permutations. The two `if (...)` statements branch on those secret bits to decide whether `bigbyte[j]` should be OR'ed into `kn[m]` or `kn[n]`, so this is a true key-schedule control-flow leak.

I did not find another nearby source-level branch or secret-indexed memory access in this benchmark that looked as clearly real as these two key-schedule branches.

### appliedcryp_loki91

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| branch | appliedCryp/loki91.c | 165 | 7 | `if (b & 01)` |
| branch | appliedCryp/loki91.c | 181 | 6 | `if (base == 0) /* if zero base specified then */` |
| memory | appliedCryp/loki91.c | 201 | 21 | `v = exp8(t, sfn[r].exp, sfn[r].gen); /* Sfn[r] = t ^ exp mod gen */` |

This benchmark implements the LOKI91 block cipher. The implementation is a Feistel network whose S-box layer is not a flat lookup table; instead it computes S-box outputs through finite-field multiplication and exponentiation, parameterized by an `sfn[]` table that selects the exponent and generator polynomial. The secret benchmark inputs are `in_key` (reported as `key`) and `in` (reported as `data`). `main()` first calls `setlokikey(in_key, &lc)`, so the round-key array inside `lc` is derived from the secret key input. It then calls `enloki(&lc, in)`, so the Feistel state also starts from secret plaintext bytes. In the round function `f()`, the expression `E(R(i-1)) XOR K(i)` produces a secret 32-bit value `a` because it combines the current secret right half with a secret round key. The helper `s()` receives 12-bit pieces of `a`, computes `r = ((i >> 8) & 0xc) | (i & 0x3)` and `t = (c + ((r * 17) ^ 0xff)) & 0xff`, and then evaluates `exp8(t, sfn[r].exp, sfn[r].gen)`. That is why line 201 is a true secret-dependent memory access: the index `r` depends on `in` and `in_key`, so the selected table row `sfn[r]` does too. The branch at line 181 is true secret-dependent control flow because it tests whether the secret-derived `base` argument `t` is zero. The branch at line 165 is also secret-dependent because `mult8()` branches on the low bit of its parameter `b`, and in this call chain `b` is derived from the secret `t` value produced by `s()`.

Manual review found two more likely true branches in the same computation chain that the included reports did not surface separately:

- `benchmarks/appliedCryp/loki91.c:168` has `if (a >= SIZE)`. Here `a` is the multiplicand inside `mult8()`, and in this benchmark it is reached from the secret-derived `base` value `t` and then updated under the secret-selected generator polynomial `sfn[r].gen`, so that branch should also be controlled by `in` and `in_key`.
- `benchmarks/appliedCryp/loki91.c:187` has `if (( exponent & 0x0001) == 0x0001)`. `exp8()` receives `exponent = sfn[r].exp`, and `r` is computed from `E(R(i-1)) XOR K(i)`, so the chosen exponent bits depend on the secret plaintext path and the secret key schedule.

## Ghostrider

### ghostrider_findmax

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| branch | ghostrider/findmax.c | 11 | 13 | `if (h[i] > m) m = h[i];` |

This benchmark is not cryptographic; it implements a simple maximum-finding reduction over an integer array using the standard linear-scan approach with a running accumulator. The only secret benchmark input is the array `in` (reported as `data` in the result JSON). `main()` fills `in[]` from stdin and then calls `max(INPUT_SIZE, in)`, where the parameter name becomes `h`. On each iteration, line 11 compares the current secret element `h[i]` against the running maximum `m`. The variable `m` is itself built from earlier secret elements of `h`, so the predicate `h[i] > m` depends entirely on secret data. That branch therefore leaks ordering information about the secret array and about when the running maximum changes.

### ghostrider_matmul

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| - | ghostrider/matmul.c | - | - | No reproduced positives in the included JSON summaries. |

This benchmark implements dense matrix multiplication in the textbook triple-nested-loop style. I did not find a likely branch or memory-address constant-time violation in `matmul.c`. Its loop bounds are fixed, and its array indices are affine functions of public loop counters only. If someone wanted to worry about operand-dependent integer multiply latency on a particular microarchitecture, that would be outside the branch/memory scope of this report and is not evidenced by these results.

## libg

### libg_des

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| memory | libg/des.c | 546 | 12 | `left = ((leftkey_swap[(left >> 0) & 0xf] << 3)` |
| memory | libg/des.c | 547 | 14 | `\| (leftkey_swap[(left >> 8) & 0xf] << 2)` |
| memory | libg/des.c | 548 | 14 | `\| (leftkey_swap[(left >> 16) & 0xf] << 1)` |
| memory | libg/des.c | 549 | 14 | `\| (leftkey_swap[(left >> 24) & 0xf])` |
| memory | libg/des.c | 550 | 14 | `\| (leftkey_swap[(left >> 5) & 0xf] << 7)` |
| memory | libg/des.c | 551 | 14 | `\| (leftkey_swap[(left >> 13) & 0xf] << 6)` |
| memory | libg/des.c | 552 | 14 | `\| (leftkey_swap[(left >> 21) & 0xf] << 5)` |
| memory | libg/des.c | 553 | 14 | `\| (leftkey_swap[(left >> 29) & 0xf] << 4));` |
| memory | libg/des.c | 557 | 13 | `right = ((rightkey_swap[(right >> 1) & 0xf] << 3)` |
| memory | libg/des.c | 558 | 15 | `\| (rightkey_swap[(right >> 9) & 0xf] << 2)` |
| memory | libg/des.c | 559 | 15 | `\| (rightkey_swap[(right >> 17) & 0xf] << 1)` |
| memory | libg/des.c | 560 | 15 | `\| (rightkey_swap[(right >> 25) & 0xf])` |
| memory | libg/des.c | 561 | 15 | `\| (rightkey_swap[(right >> 4) & 0xf] << 7)` |
| memory | libg/des.c | 562 | 15 | `\| (rightkey_swap[(right >> 12) & 0xf] << 6)` |
| memory | libg/des.c | 563 | 15 | `\| (rightkey_swap[(right >> 20) & 0xf] << 5)` |
| memory | libg/des.c | 564 | 15 | `\| (rightkey_swap[(right >> 28) & 0xf] << 4));` |
| memory | libg/des.c | 674 | 3 | `DES_ROUND (right, left, work, keys) DES_ROUND (left, right, work, keys)` |
| memory | libg/des.c | 674 | 39 | `DES_ROUND (right, left, work, keys) DES_ROUND (left, right, work, keys)` |

This benchmark also implements DES, but here the code comes from libg and uses a highly table-driven software strategy for both phases: nibble permutation tables for key scheduling and eight precomputed S-box tables inside the round macro. The secret benchmark inputs are `in_key` (reported as `key`) and `in` (reported as `data`). The first leak family is in `des_key_schedule()`: `des_setkey(in_key, ctx)` passes the secret key bytes into `READ_64BIT_DATA(rawkey, left, right)`, so `left` and `right` are key-derived words. The reported expressions `(left >> k) & 0xf` and `(right >> k) & 0xf` then use secret key nibbles as indices into `leftkey_swap[]` and `rightkey_swap[]`, which makes those table accesses key-dependent. The second leak family is in `des_ecb_crypt()`: it loads the secret data buffer `in` into `left` and `right`, then each `DES_ROUND` computes `work = from ^ *subkey++`. Here `from` comes from the evolving secret block state and `*subkey` comes from the schedule derived from `in_key`. The expressions `work & 0x3f`, `(work >> 8) & 0x3f`, and so on then index `sbox1..sbox8`. Those round-function table addresses therefore depend on `in`, `in_key`, or both.

The raw JSON for this benchmark contained repeated successful rows, especially for line 674. I collapsed those to unique locations here. Manual review also found one important reporting gap: `benchmarks/libg/des.c:675-681` repeat the same `DES_ROUND` macro invocation across the remaining DES rounds, so the same data flow still applies there: secret block state flows into `from`, secret key material flows into `*subkey++`, and the resulting secret-derived `work` indexes the DES S-box tables.

## PyCrypto

### pycrypto_arc4

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| memory | pycrypto/src/ARC4.c | 82 | 20 | `self->state[i] = self->state[index2];` |

This benchmark implements the RC4 stream cipher in the standard array-permutation style, with a key-scheduling algorithm (KSA) that scrambles a 256-byte state table and a PRGA that keeps swapping and re-indexing that table. The only secret benchmark input is the local array `key`, which is also reported as `key` in the results. The harness in `stream_template.c` reads that array from stdin, leaves `in` as a fixed all-zero buffer, calls `stream_init(&st, key, KEY_LEN)`, and then runs `stream_encrypt(&st, in, STREAM_SIZE)`. The reproduced hit is in `stream_init()`: each loop iteration updates `index2 = (key[index1] + self->state[i] + index2) % 256`, so `index2` becomes a function of the secret key bytes and the already-permuted RC4 state. Line 82 then reads `self->state[index2]`, which means the address of that load is controlled by the secret input `key`. That is a true secret-dependent memory access in the RC4 key-scheduling algorithm.

Manual review found several more likely true violations in the same benchmark that were not surfaced separately by the included report:

- `benchmarks/pycrypto/src/ARC4.c:56` reads `self->state[y]`, where `y` is computed from the RC4 state permutation that was already made key-dependent by `stream_init(key, ...)`.
- `benchmarks/pycrypto/src/ARC4.c:57` writes `self->state[y] = t`, so the write address follows the same key-derived `y` value.
- `benchmarks/pycrypto/src/ARC4.c:61` reads `self->state[y]` again while building `xorIndex`, so the same key-dependent state position is observed twice.
- `benchmarks/pycrypto/src/ARC4.c:62` reads `self->state[xorIndex]`, and `xorIndex` is computed from `self->state[x] + self->state[y]`, both of which come from the key-initialized secret permutation.
- `benchmarks/pycrypto/src/ARC4.c:83` writes `self->state[index2] = t`, which is the paired secret-dependent write to the same key-derived KSA address family as the reproduced line 82.

## OpenSSL Almeida

### openssl_almeida_tls_rempad_luk13_fix_pub

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| - | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | - | - | No reproduced positives in the included `fix_pub` JSON summaries. |

This benchmark implements TLS CBC record padding removal, specifically the Lucky13-vulnerable `tls1_cbc_remove_padding()` routine. The implementation approach is a branchy padding-validation routine: it reads the last plaintext byte as the claimed padding length, adjusts that length for compatibility corner cases, then uses ordinary control flow and a byte-by-byte loop to validate the padding region. In `fix_pub`, the only secret input is `data_buf` (reported as `data`), while `options`, `s3_flags`, `flags`, `slicing_cheat`, `block_size`, and `mac_size` are fixed to their preset defaults.

Even though the included `fix_pub` top-level summaries are empty, manual inspection strongly suggests that several true constant-time violations remain in this mode. The relevant flow is `data_buf -> data[] -> rec->data -> ii/i/j`:

- `rec_obj.data` is initialized from `data_buf`, and `ii = i = rec->data[l - 1]` reads the last secret record byte as the padding length.
- With the default preset, `options = 0`, so the TLS padding-bug compatibility branch at line 79 is disabled. However, line 87 still tests `if (i + bs > rec->length)`, where `i` comes from the secret last byte and `bs` is the fixed public block size `16`.
- Line 96 sets the loop start to `l - i`, so the number of loop iterations depends on the secret padding length.
- Line 98 reads `rec->data[j]` and branches on `rec->data[j] != ii`, so both the accessed padding positions and the equality test are controlled by secret `data_buf` bytes.

Because of that, lines 87, 96, and 98 still look like true constant-time violations in `fix_pub`, even though they were not surfaced by the included summaries.

### openssl_almeida_tls_rempad_luk13_var_pub

| Kind | File | Line | Column | Code |
| --- | --- | ---: | ---: | --- |
| branch | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | 79 | 11 | `if ((memcmp(s->s3->read_sequence,` |
| branch | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | 87 | 7 | `if (i + bs > (int)rec->length)` |
| branch | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | 96 | 3 | `for (j=(int)(l-i); j<(int)l; j++)` |
| branch | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | 98 | 11 | `if (rec->data[j] != ii)` |
| memory | openssl_almeida/tls1_cbc_remove_padding_lucky13.c | 98 | 11 | `if (rec->data[j] != ii)` |

This benchmark is the same TLS CBC padding-removal routine, but in `var_pub` the secret input `data_buf` is accompanied by symbolic public control fields `options`, `s3_flags`, `flags`, `slicing_cheat`, `block_size`, and `mac_size`. The implementation style remains a branchy byte-by-byte padding check rather than a constant-time masked validation pass. The data flow is `data_buf -> data[] -> rec->data -> ii/i/j`, with the public controls determining which compatibility and length checks are active.

The reproduced sites are all consistent with that flow:

- Line 79 is guarded by the public flag `options & SSL_OP_TLS_BLOCK_PADDING_BUG`, but once that public gate is enabled, the condition also tests `!(ii & 1)`. Here `ii` is `rec->data[l - 1]`, so the branch depends on the parity of the last secret byte in `data_buf`. In this benchmark, `read_sequence` is zero-initialized, so the `memcmp(...) == 0` part is effectively public and the secret influence comes from `ii`.
- Line 87 branches on `i + bs > rec->length`. The variable `i` starts as the secret last byte `ii`, is incremented, and may be decremented by the line-79 compatibility path. The public input `bs` can change the threshold, but the branch outcome still depends on the secret-derived `i`.
- Line 96 sets the loop start to `l - i`, so the loop count depends on the secret padding length held in `i`.
- Line 98 compares each candidate padding byte `rec->data[j]` against the secret byte `ii`. The branch is secret-dependent because both operands come from `data_buf`, and the memory access is secret-dependent because the range of `j` values is determined by the secret-derived `i`.

Compared with `fix_pub`, `var_pub` mainly broadens which public configurations expose the leak. It does not change the core cause: the function treats the decrypted record bytes as secret padding metadata and then uses ordinary branches and data-dependent iteration to validate them.