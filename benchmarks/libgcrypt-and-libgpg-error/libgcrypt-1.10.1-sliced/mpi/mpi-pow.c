/* mpi-pow.c  -  MPI functions for exponentiation
 * Copyright (C) 1994, 1996, 1998, 2000, 2002
 *               2003  Free Software Foundation, Inc.
 *               2013  g10 Code GmbH
 *
 * This file is part of Libgcrypt.
 *
 * Libgcrypt is free software; you can redistribute it and/or modify
 * it under the terms of the GNU Lesser General Public License as
 * published by the Free Software Foundation; either version 2.1 of
 * the License, or (at your option) any later version.
 *
 * Libgcrypt is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Lesser General Public License for more details.
 *
 * You should have received a copy of the GNU Lesser General Public
 * License along with this program; if not, see <http://www.gnu.org/licenses/>.
 *
 * Note: This code is heavily based on the GNU MP Library.
 *	 Actually it's the same code with only minor changes in the
 *	 way the data is stored; this is to support the abstraction
 *	 of an optional secure memory allocation which may be used
 *	 to avoid revealing of sensitive data due to paging etc.
 */

#include <config.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "mpi-internal.h"
#include "longlong.h"

/**
 * Internal function to compute
 *
 *    X = R * S mod M
 *
 * and set the size of X at the pointer XSIZE_P.
 * Use karatsuba structure at KARACTX_P.
 *
 * Condition:
 *   RSIZE >= SSIZE
 *   Enough space for X is allocated beforehand.
 *
 * For generic cases, we can/should use gcry_mpi_mulm.
 * This function is use for specific internal case.
 */
static void
mul_mod (mpi_ptr_t xp, mpi_size_t *xsize_p,
         mpi_ptr_t rp, mpi_size_t rsize,
         mpi_ptr_t sp, mpi_size_t ssize,
         mpi_ptr_t mp, mpi_size_t msize,
         struct karatsuba_ctx *karactx_p)
{
  *xsize_p = rsize;
}

#define SIZE_PRECOMP ((1 << (5 - 1)))

/****************
 * RES = BASE ^ EXPO mod MOD
 *
 * To mitigate the Yarom/Falkner flush+reload cache side-channel
 * attack on the RSA secret exponent, we don't use the square
 * routine but multiplication.
 *
 * Reference:
 *   Handbook of Applied Cryptography
 *       Algorithm 14.83: Modified left-to-right k-ary exponentiation
 */
void
_gcry_mpi_powm (gcry_mpi_t res, gcry_mpi_t base, gcry_mpi_t expo, gcry_mpi_t mod)
{
  mpi_ptr_t  rp, ep, mp, bp;
  mpi_size_t esize, msize, bsize, rsize;
  int msign, bsign, rsign, esec, msec, bsec;
  mpi_size_t size;
  int mod_shift_cnt, negative_result;
  mpi_ptr_t mp_marker = NULL;
  mpi_ptr_t bp_marker = NULL;
  mpi_ptr_t ep_marker = NULL;
  mpi_ptr_t xp_marker = NULL;
  unsigned int mp_nlimbs = 0;
  unsigned int bp_nlimbs = 0;
  unsigned int ep_nlimbs = 0;
  unsigned int xp_nlimbs = 0;
  mpi_ptr_t precomp[SIZE_PRECOMP]; 
  mpi_size_t precomp_size[SIZE_PRECOMP];
  mpi_size_t W;
  mpi_ptr_t base_u;
  mpi_size_t base_u_size;
  mpi_size_t max_u_size;
  esize = expo->nlimbs;
  msize = mod->nlimbs;
  size = 2 * msize;
  msign = mod->sign;
  ep = expo->d;
  // @slice_preserve_ctrl;
  // @slice_preserve_stmt;
  MPN_NORMALIZE(ep, esize);
  if (esize * BITS_PER_MPI_LIMB > 512) W = 5;
  else if (esize * BITS_PER_MPI_LIMB > 256) W = 4;
  else if (esize * BITS_PER_MPI_LIMB > 128) W = 3;
  else if (esize * BITS_PER_MPI_LIMB > 64) W = 2;
  else W = 1;
  esec = mpi_is_secure(expo);
  msec = mpi_is_secure(mod);
  bsec = mpi_is_secure(base);
  rp = res->d;
  if (!msize)
    _gcry_divide_by_zero();
  if (!esize)
    {
      res->nlimbs = (msize == 1 && mod->d[0] == 1) ? 0 : 1;
      if (res->nlimbs)
        {
          RESIZE_IF_NEEDED (res, 1);
          rp = res->d;
          rp[0] = 1;
        }
      res->sign = 0;
      goto leave;
    }
  mp_nlimbs = msec? msize:0;
  mp = mp_marker = mpi_alloc_limb_space(msize, msec);
  count_leading_zeros (mod_shift_cnt, mod->d[msize-1]);
  if (mod_shift_cnt)
    _gcry_mpih_lshift (mp, mod->d, msize, mod_shift_cnt);
  else
    MPN_COPY( mp, mod->d, msize );
  bsize = base->nlimbs;
  bsign = base->sign;
  if (bsize > msize)
    {
      bp_nlimbs = bsec ? (bsize + 1):0;
      bp = bp_marker = mpi_alloc_limb_space( bsize + 1, bsec );
      MPN_COPY ( bp, base->d, bsize );
      _gcry_mpih_divrem( bp + msize, 0, bp, bsize, mp, msize );
      bsize = msize;
      MPN_NORMALIZE( bp, bsize );
    }
  else
    bp = base->d;
  if (!bsize)
    {
      res->nlimbs = 0;
      res->sign = 0;
      goto leave;
    }
  if ( rp == bp )
    {
      gcry_assert (!bp_marker);
      bp_nlimbs = bsec? bsize:0;
      bp = bp_marker = mpi_alloc_limb_space( bsize, bsec );
      MPN_COPY(bp, rp, bsize);
    }
  if ( rp == ep )
    {
      ep_nlimbs = esec? esize:0;
      ep = ep_marker = mpi_alloc_limb_space( esize, esec );
      MPN_COPY(ep, rp, esize);
    }
  if (res->alloced < size)
    {
      mpi_resize (res, size);
      rp = res->d;
    }
  {
    mpi_size_t i, j, k;
    mpi_ptr_t xp;
    mpi_size_t xsize;
    int c;
    mpi_limb_t e;
    mpi_limb_t carry_limb;
    struct karatsuba_ctx karactx;
    mpi_ptr_t tp;
    xp_nlimbs = msec? size:0;
    xp = xp_marker = mpi_alloc_limb_space( size, msec );
    memset( &karactx, 0, sizeof karactx );
    // @slice_preserve_ctrl;
    // @slice_preserve_stmt;
    negative_result = (ep[0] & 1) && bsign;
    base_u_size = bsize;
    i = esize - 1;
    rsign = 0;
    if (W == 1)
      {
        rsize = bsize;
      }
    else
      {
        rsize = msize;
        MPN_ZERO (rp, rsize);
      }
    MPN_COPY ( rp, bp, bsize );
    e = ep[i];
    count_leading_zeros (c, e);
    e = (e << c) << 1;
    c = BITS_PER_MPI_LIMB - 1 - c;
    j = 0;
    for (;;) 
      {
        // @slice_preserve_ctrl;
        // @slice_preserve_stmt;
        if (e == 0)
          {
            j += c;
            if ( --i < 0 )
              break;

            e = ep[i];
            c = BITS_PER_MPI_LIMB;
          }
        else
          {
            int c0;
            mpi_limb_t e0;
            struct gcry_mpi w, u;
            w.sign = u.sign = 0;
            w.flags = u.flags = 0;
            w.d = base_u;

            count_leading_zeros (c0, e);
            e = (e << c0);
            c -= c0;
            j += c0;

            e0 = (e >> (BITS_PER_MPI_LIMB - W));
            // @slice_preserve_ctrl;
            // @slice_preserve_stmt;
            if (c >= W)
              c0 = 0;
            else
              {
                if ( --i < 0 )
                  {
                    e0 = (e >> (BITS_PER_MPI_LIMB - c));
                    j += c - W;
                    goto last_step;
                  }
                else
                  {
                    c0 = c;
                    e = ep[i];
                    c = BITS_PER_MPI_LIMB;
                    e0 |= (e >> (BITS_PER_MPI_LIMB - (W - c0)));
                  }
              }
            e = e << (W - c0);
            c -= (W - c0);
          last_step:
            count_trailing_zeros (c0, e0);
            e0 = (e0 >> c0) >> 1;
            // @slice_preserve_ctrl;
            // @slice_preserve_stmt;
            for (j += W - c0; j >= 0; j--)
              {
                base_u_size = rsize;
                mul_mod (xp, &xsize, rp, rsize, base_u, base_u_size, mp, msize, &karactx);
                tp = rp; rp = xp; xp = tp;
                rsize = xsize;
              }
            j = c0;
            if ( i < 0 )
              break;
          }
    }
    // @slice_preserve_ctrl;
    // @slice_preserve_stmt;
    while (j--)
      {
        mul_mod (xp, &xsize, rp, rsize, rp, rsize, mp, msize, &karactx);
        tp = rp; rp = xp; xp = tp;
        rsize = xsize;
      }
  }
  leave: ;
}
