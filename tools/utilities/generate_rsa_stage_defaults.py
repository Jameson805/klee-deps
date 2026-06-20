#!/usr/bin/env python3
"""Generate deterministic RSA-stage benchmark defaults."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sys
from dataclasses import dataclass


KEY_BITS = 1024
PUBLIC_EXPONENT = 65537
DEFAULT_SEED = 0x5253415F5354414745
MILLER_RABIN_ROUNDS = 32


@dataclass(frozen=True)
class RsaPrivateKey:
    n: int
    e: int
    d: int
    p: int
    q: int
    dp: int
    dq: int
    q_inv: int
    p_inv: int


@dataclass(frozen=True)
class EncodedDefault:
    scheme: str
    digest: str | None
    message: bytes
    encoded: bytes
    ciphertext: bytes


def deterministic_bytes(rng: random.Random, length: int) -> bytes:
    return bytes(rng.randrange(0, 256) for _ in range(length))


def deterministic_nonzero_bytes(rng: random.Random, length: int) -> bytes:
    output = bytearray()
    while len(output) < length:
        value = rng.randrange(1, 256)
        output.append(value)
    return bytes(output)


def is_probable_prime(value: int, rng: random.Random) -> bool:
    if value < 2:
        return False
    small_primes = (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37)
    for prime in small_primes:
        if value == prime:
            return True
        if value % prime == 0:
            return False

    d = value - 1
    shifts = 0
    while d % 2 == 0:
        d //= 2
        shifts += 1

    for _ in range(MILLER_RABIN_ROUNDS):
        base = rng.randrange(2, value - 2)
        x = pow(base, d, value)
        if x == 1 or x == value - 1:
            continue
        for _ in range(shifts - 1):
            x = pow(x, 2, value)
            if x == value - 1:
                break
        else:
            return False
    return True


def generate_prime(rng: random.Random, bits: int, exponent: int) -> int:
    while True:
        candidate = rng.getrandbits(bits)
        candidate |= (1 << (bits - 1)) | 1
        if math.gcd(candidate - 1, exponent) != 1:
            continue
        if is_probable_prime(candidate, rng):
            return candidate


def generate_key(seed: int, bits: int = KEY_BITS) -> RsaPrivateKey:
    rng = random.Random(seed)
    prime_bits = bits // 2
    while True:
        p = generate_prime(rng, prime_bits, PUBLIC_EXPONENT)
        q = generate_prime(rng, prime_bits, PUBLIC_EXPONENT)
        if p == q:
            continue
        n = p * q
        if n.bit_length() != bits:
            continue
        phi = (p - 1) * (q - 1)
        d = pow(PUBLIC_EXPONENT, -1, phi)
        return RsaPrivateKey(
            n=n,
            e=PUBLIC_EXPONENT,
            d=d,
            p=p,
            q=q,
            dp=d % (p - 1),
            dq=d % (q - 1),
            q_inv=pow(q, -1, p),
            p_inv=pow(p, -1, q),
        )


def i2osp(value: int, length: int) -> bytes:
    if value < 0 or value >= 1 << (8 * length):
        raise ValueError(f"integer does not fit in {length} bytes")
    return value.to_bytes(length, "big")


def mgf1(seed: bytes, length: int, digest_name: str) -> bytes:
    output = bytearray()
    counter = 0
    while len(output) < length:
        digest = hashlib.new(digest_name)
        digest.update(seed)
        digest.update(counter.to_bytes(4, "big"))
        output.extend(digest.digest())
        counter += 1
    return bytes(output[:length])


def xor_bytes(left: bytes, right: bytes) -> bytes:
    return bytes(a ^ b for a, b in zip(left, right, strict=True))


def encode_pkcs1_v15(message: bytes, key_bytes: int, rng: random.Random) -> bytes:
    ps_len = key_bytes - len(message) - 3
    if ps_len < 8:
        raise ValueError("PKCS#1 v1.5 message is too long")
    return b"\x00\x02" + deterministic_nonzero_bytes(rng, ps_len) + b"\x00" + message


def encode_sslv23(message: bytes, key_bytes: int, rng: random.Random) -> bytes:
    ps_len = key_bytes - len(message) - 3
    if ps_len < 8:
        raise ValueError("SSLv23 message is too long")
    random_prefix_len = ps_len - 8
    return (
        b"\x00\x02"
        + deterministic_nonzero_bytes(rng, random_prefix_len)
        + (b"\x03" * 8)
        + b"\x00"
        + message
    )


def encode_oaep(message: bytes, key_bytes: int, rng: random.Random, digest_name: str) -> bytes:
    digest_len = hashlib.new(digest_name).digest_size
    if len(message) > key_bytes - 2 * digest_len - 2:
        raise ValueError(f"OAEP-{digest_name} message is too long")

    label_hash = hashlib.new(digest_name, b"").digest()
    ps = b"\x00" * (key_bytes - len(message) - 2 * digest_len - 2)
    db = label_hash + ps + b"\x01" + message
    seed = deterministic_bytes(rng, digest_len)
    db_mask = mgf1(seed, key_bytes - digest_len - 1, digest_name)
    masked_db = xor_bytes(db, db_mask)
    seed_mask = mgf1(masked_db, digest_len, digest_name)
    masked_seed = xor_bytes(seed, seed_mask)
    return b"\x00" + masked_seed + masked_db


def encode_raw(message: bytes, key: RsaPrivateKey, key_bytes: int) -> bytes:
    value = int.from_bytes(message, "big") % key.n
    if value == 0:
        value = 1
    return i2osp(value, key_bytes)


def encrypt_encoded(encoded: bytes, key: RsaPrivateKey, key_bytes: int) -> bytes:
    encoded_value = int.from_bytes(encoded, "big")
    if encoded_value >= key.n:
        raise ValueError("encoded representative is outside the RSA modulus")
    return i2osp(pow(encoded_value, key.e, key.n), key_bytes)


def build_defaults(key: RsaPrivateKey, seed: int, message_len: int) -> list[EncodedDefault]:
    key_bytes = (key.n.bit_length() + 7) // 8
    rng = random.Random(seed ^ 0xD3FA0175)
    messages = {
        "pkcs1_v15": deterministic_bytes(rng, message_len),
        "oaep_sha1": deterministic_bytes(rng, message_len),
        "oaep_sha256": deterministic_bytes(rng, message_len),
        "sslv23": deterministic_bytes(rng, message_len),
        "raw": deterministic_bytes(rng, key_bytes),
    }
    encoded_values = [
        ("pkcs1_v15", None, encode_pkcs1_v15(messages["pkcs1_v15"], key_bytes, rng)),
        ("oaep_sha1", "sha1", encode_oaep(messages["oaep_sha1"], key_bytes, rng, "sha1")),
        ("oaep_sha256", "sha256", encode_oaep(messages["oaep_sha256"], key_bytes, rng, "sha256")),
        ("sslv23", None, encode_sslv23(messages["sslv23"], key_bytes, rng)),
        ("raw", None, encode_raw(messages["raw"], key, key_bytes)),
    ]
    return [
        EncodedDefault(
            scheme=scheme,
            digest=digest,
            message=messages[scheme],
            encoded=encoded,
            ciphertext=encrypt_encoded(encoded, key, key_bytes),
        )
        for scheme, digest, encoded in encoded_values
    ]


def format_byte_array(name: str, data: bytes, indent: str = "\t") -> str:
    lines = [f"{name} = ["]
    for index in range(0, len(data), 8):
        chunk = data[index:index + 8]
        lines.append(indent + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    lines.append("]")
    return "\n".join(lines)


def format_c_array(name: str, data: bytes) -> str:
    lines = [f"static const unsigned char {name}[{len(data)}] = {{"]
    for index in range(0, len(data), 16):
        chunk = data[index:index + 16]
        lines.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    lines.append("};")
    return "\n".join(lines)


def key_bytes(key: RsaPrivateKey) -> dict[str, bytes]:
    return {
        "RSA_N_BYTES": i2osp(key.n, 128),
        "RSA_P_BYTES": i2osp(key.p, 64),
        "RSA_Q_BYTES": i2osp(key.q, 64),
        "RSA_D_BYTES": i2osp(key.d, 128),
        "RSA_DP_BYTES": i2osp(key.dp, 64),
        "RSA_DQ_BYTES": i2osp(key.dq, 64),
        "RSA_QP_BYTES": i2osp(key.q_inv, 64),
        "RSA_IQ_BYTES": i2osp(key.q_inv, 64),
        "RSA_U_BYTES": i2osp(key.p_inv, 64),
        "RSA_E_BYTES": i2osp(key.e, 3),
    }


def print_toml(defaults: list[EncodedDefault]) -> None:
    target_map = {
        "core_private": "pkcs1_v15",
        "pkcs1_decrypt": "pkcs1_v15",
        "oaep_decrypt_sha1": "oaep_sha1",
        "oaep_decrypt_sha256": "oaep_sha256",
        "sslv23_decrypt": "sslv23",
        "raw_decrypt": "raw",
    }
    defaults_by_scheme = {default.scheme: default for default in defaults}
    print("# Full/private decrypt ciphertext defaults")
    for target, scheme in target_map.items():
        print(f"\n# {target}: {scheme}")
        print(format_byte_array("ciphertext_buf", defaults_by_scheme[scheme].ciphertext))

    print("\n# Padding-only ABACUS encoded-block defaults")
    for default in defaults:
        if default.scheme == "raw":
            continue
        print(f"\n# {default.scheme}")
        print(format_byte_array("encoded_buf", default.encoded))


def print_c_key(key: RsaPrivateKey) -> None:
    for name, data in key_bytes(key).items():
        print(format_c_array(name, data))
        print()


def print_json(key: RsaPrivateKey, defaults: list[EncodedDefault], seed: int) -> None:
    payload = {
        "seed": seed,
        "key_bits": KEY_BITS,
        "public_exponent": key.e,
        "key": {name: data.hex() for name, data in key_bytes(key).items()},
        "defaults": {
            default.scheme: {
                "digest": default.digest,
                "message": default.message.hex(),
                "encoded": default.encoded.hex(),
                "ciphertext": default.ciphertext.hex(),
            }
            for default in defaults
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a deterministic 1024-bit RSA private key and fixed "
            "RSA-stage ciphertext / encoded-block defaults. The TOML output "
            "is organized by target because the current shared runner profiles "
            "cannot represent different defaults for targets that share one profile."
        )
    )
    parser.add_argument(
        "--seed",
        type=lambda value: int(value, 0),
        default=DEFAULT_SEED,
        help=f"deterministic RNG seed, decimal or hex (default: 0x{DEFAULT_SEED:x})",
    )
    parser.add_argument(
        "--message-bytes",
        type=int,
        default=32,
        help="fixed random plaintext length for padded schemes (default: 32)",
    )
    parser.add_argument(
        "--format",
        choices=("toml", "json", "c-key"),
        default="toml",
        help="output format (default: toml)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.message_bytes <= 0:
        parser.error("--message-bytes must be positive")

    key = generate_key(args.seed)
    defaults = build_defaults(key, args.seed, args.message_bytes)

    if args.format == "toml":
        print_toml(defaults)
    elif args.format == "json":
        print_json(key, defaults, args.seed)
    else:
        print_c_key(key)
    return 0


if __name__ == "__main__":
    sys.exit(main())
