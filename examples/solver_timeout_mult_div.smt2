(set-option :produce-models true)
(set-logic QF_BV)

; Ultra-minimal arithmetic-first UNSAT candidate
;
; Purpose
;   Keep only the core arithmetic contradiction:
;     - Often friendly to BV-as-Int reasoning
;     - Can still be expensive for pure bit-blasting
;
; Explicit formula (bit-vector semantics)
;   Let C = 2^95.
;   Let D = d64.
;   Define
;     Q = low64( bvudiv(C, zext64(D)) )
;     P = zext64(D) * zext64((Q - 1) mod 2^64)
;     H = high64(P)
;   Constraint:
;     (1) H > 2^31
;
; Why UNSAT (human proof sketch)
;   - If D = 0, SMT-LIB defines bvudiv(C, 0) as all-ones, so Q-1 = 2^64-2.
;     Then P = 0 * (...) = 0, hence H = 0 and (1) fails.
;   - If D > 0, Q = floor(C / D), so D*Q <= C and D*(Q-1) < C = 2^95.
;     Therefore H < 2^(95-64) = 2^31, again contradicting (1).
;   Thus UNSAT.
;
; Why this often helps solve-bv-as-int=sum
;   The formula is arithmetic-first: one symbolic divisor feeds bvudiv/bvmul and
;   a high-half bound, with little extra bit-structure around D.

(declare-fun d64 () (_ BitVec 64))

; D = d64 in 64-bit space.
(define-fun denom64 () (_ BitVec 64)
  d64)

; Lift D into 128-bit arithmetic domain.
(define-fun denom128 () (_ BitVec 128)
  ((_ zero_extend 64) denom64))

; C = 2^95 in 128-bit space.
(define-fun c128 () (_ BitVec 128)
  (_ bv39614081257132168796771975168 128))

; Q = low64( C / D ).
(define-fun q64 () (_ BitVec 64)
  ((_ extract 63 0)
    (bvudiv c128 denom128)))

; q - 1 in modular 64-bit arithmetic.
(define-fun q_minus_one64 () (_ BitVec 64)
  (bvadd q64 (_ bv18446744073709551615 64)))

; P = D * (Q - 1), represented in 128 bits.
(define-fun p128 () (_ BitVec 128)
  (bvmul denom128 ((_ zero_extend 64) q_minus_one64)))

; H = high64(P).
(define-fun hi64 () (_ BitVec 64)
  ((_ extract 127 64) p128))

; Contradictory target H > 2^31.
(assert (bvult (_ bv2147483648 64) hi64))

(check-sat)
(exit)
