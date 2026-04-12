(set-option :produce-models true)
(set-logic QF_BV)

; Ultra-minimal bit-structure-first UNSAT candidate
;
; Purpose
;   Keep the same arithmetic contradiction as ultra_minimal_a, but build D from
;   explicit bit-structure first:
;     - Often friendly to native BV reasoning
;     - Often slower with solve-bv-as-int=sum
;
; Explicit formula (bit-vector semantics)
;   Let C = 2^95.
;   Let b0, b1 be symbolic 8-bit values.
;   Define
;     W = concat(b1, 0x00, 0x00, b0, 0x00000000)   (64 bits)
;     D = (W << 31) mod 2^64
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
; Why this often hurts solve-bv-as-int=sum
;   The arithmetic core is the same as ultra_minimal_a, but D is produced by
;   concat + shift + modular truncation before division.
;   Native BV can exploit this bit-precise structure directly, while BV-as-Int
;   must first encode that structure into integer constraints.

; Two symbolic bytes are enough to keep the asymmetry.
(declare-fun b0 () (_ BitVec 8))
(declare-fun b1 () (_ BitVec 8))

; W = [b1, 0x00, 0x00, b0, 0x00000000].
(define-fun w64 () (_ BitVec 64)
  (concat b1 (concat (_ bv0 8) (concat (_ bv0 8) (concat b0 (_ bv0 32))))))

; D = (W << 31) mod 2^64.
(define-fun denom64 () (_ BitVec 64)
  (bvshl w64 (_ bv31 64)))

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

; P = D * (Q - 1), all in 128-bit BV arithmetic.
(define-fun p128 () (_ BitVec 128)
  (bvmul denom128 ((_ zero_extend 64) q_minus_one64)))

; H = high64(P).
(define-fun hi64 () (_ BitVec 64)
  ((_ extract 127 64) p128))

; Contradictory target H > 2^31.
(assert (bvult (_ bv2147483648 64) hi64))

(check-sat)
(exit)
