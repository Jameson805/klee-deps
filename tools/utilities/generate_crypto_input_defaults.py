#!/usr/bin/env python3
"""Generate shared deterministic crypto input defaults for runner configs."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REPO_ROOT = Path(__file__).resolve().parents[2]
BEARSSL_ROOT = REPO_ROOT / "benchmarks" / "bearssl" / "bearssl-0.6"
DEFAULT_CC = "cc"

def deterministic_bytes(label: str, length: int) -> bytes:
    """Return deterministic pseudorandom bytes for a named benchmark role."""
    return hashlib.shake_256(label.encode("ascii")).digest(length)


def with_odd_des_parity(data: bytes) -> bytes:
    """Return DES key bytes with the low bit adjusted for odd parity."""
    result = bytearray()
    for byte in data:
        without_parity = byte & 0xfe
        if without_parity.bit_count() % 2 == 0:
            result.append(without_parity | 1)
        else:
            result.append(without_parity)
    return bytes(result)


AES_128_KEY = bytes.fromhex("00112233445566778899aabbccddeeff")
DES_KEY = with_odd_des_parity(deterministic_bytes("klee-deps:crypto-default:des-key:v1", 8))
TDES_KEY = DES_KEY + with_odd_des_parity(deterministic_bytes("klee-deps:crypto-default:3des-key:v1", 16))
ECDSA_P192_ORDER = int("ffffffffffffffffffffffff99def836146bc9b1b4d22831", 16)
ECDSA_PRIVATE_KEY = (1).to_bytes(24, "big")
ECDSA_PRIVATE_KEY_32 = (1).to_bytes(32, "big")
ECDSA_NONCE = (
    int.from_bytes(deterministic_bytes("klee-deps:crypto-default:ecdsa-nonce:v1", 32), "big")
    % (ECDSA_P192_ORDER - 1)
    + 1
).to_bytes(24, "big")


def format_byte_array(name: str, data: bytes, indent: str = "\t") -> str:
    lines = [f"{name} = ["]
    for index in range(0, len(data), 8):
        chunk = data[index:index + 8]
        lines.append(indent + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    lines.append("]")
    return "\n".join(lines)


def _c_array(name: str, data: bytes) -> str:
    values = ", ".join(f"0x{byte:02x}" for byte in data)
    return f"static const unsigned char {name}[{len(data)}] = {{ {values} }};"


def _helper_source() -> str:
    return f"""
#include <stdint.h>
#include <stdio.h>
#include "bearssl.h"

{_c_array("AES_KEY", AES_128_KEY)}
{_c_array("TDES_KEY", TDES_KEY)}

static void print_bytes(const char *name, const void *data, size_t len) {{
    const unsigned char *buf = data;
    printf("%s = [\\n", name);
    for (size_t i = 0; i < len; i ++) {{
        if ((i & 7) == 0) {{
            printf("\\t");
        }}
        printf("0x%02x", buf[i]);
        if (i + 1 != len) {{
            printf(",");
        }}
        if ((i & 7) == 7 || i + 1 == len) {{
            printf("\\n");
        }} else {{
            printf(" ");
        }}
    }}
    printf("]\\n");
}}

int main(void) {{
    br_aes_big_cbcenc_keys aes_big = {{0}};
    br_aes_ct_cbcenc_keys aes_ct = {{0}};
    br_des_tab_cbcenc_keys des_tab = {{0}};
    br_des_ct_cbcenc_keys des_ct = {{0}};

    br_aes_big_cbcenc_init(&aes_big, AES_KEY, sizeof AES_KEY);
    br_aes_ct_cbcenc_init(&aes_ct, AES_KEY, sizeof AES_KEY);
    br_des_tab_cbcenc_init(&des_tab, TDES_KEY, sizeof TDES_KEY);
    br_des_ct_cbcenc_init(&des_ct, TDES_KEY, sizeof TDES_KEY);

    print_bytes("bearssl_aes_big_skey_buf", aes_big.skey, sizeof aes_big.skey);
    print_bytes("bearssl_aes_ct_skey_buf", aes_ct.skey, sizeof aes_ct.skey);
    print_bytes("bearssl_des_tab_skey_buf", des_tab.skey, sizeof des_tab.skey);
    print_bytes("bearssl_des_ct_skey_buf", des_ct.skey, sizeof des_ct.skey);
    return 0;
}}
"""


def generate_bearssl_schedules(cc: str) -> str:
    """Compile a tiny BearSSL helper and return TOML-ready schedule arrays."""
    with tempfile.TemporaryDirectory(prefix="crypto-defaults-") as tmp:
        tmp_path = Path(tmp)
        source = tmp_path / "generate.c"
        binary = tmp_path / "generate"
        source.write_text(_helper_source(), encoding="ascii")
        command = [
            cc,
            "-O0",
            "-I",
            str(BEARSSL_ROOT / "inc"),
            "-I",
            str(BEARSSL_ROOT / "src"),
            str(source),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_big_cbcenc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_big_enc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_ct_cbcenc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_ct_enc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_ct.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "aes_common.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "des_tab_cbcenc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "des_tab.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "des_ct_cbcenc.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "des_ct.c"),
            str(BEARSSL_ROOT / "src" / "symcipher" / "des_support.c"),
            "-o",
            str(binary),
        ]
        subprocess.run(command, check=True, cwd=REPO_ROOT)
        completed = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        return completed.stdout


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate deterministic crypto runner defaults.")
    parser.add_argument("--cc", default=os.environ.get("CC", DEFAULT_CC), help="C compiler for BearSSL schedules")
    parser.add_argument("--skip-bearssl", action="store_true", help="Do not compile BearSSL schedule defaults")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    plaintext = deterministic_bytes("klee-deps:crypto-default:plaintext:v1", 256)
    stream_key = deterministic_bytes("klee-deps:crypto-default:stream-key:v1", 32)
    stream_message = deterministic_bytes("klee-deps:crypto-default:stream-message:v1", 256)
    digest_message = deterministic_bytes("klee-deps:crypto-default:digest-message:v1", 256)
    ecdsa_digest_20 = deterministic_bytes("klee-deps:crypto-default:ecdsa-digest:v1", 20)
    ecdsa_digest_32 = deterministic_bytes("klee-deps:crypto-default:ecdsa-digest:v1", 32)

    print(format_byte_array("aes_key_buf", AES_128_KEY))
    print(format_byte_array("des_key_buf", DES_KEY))
    print(format_byte_array("tdes_key_buf", TDES_KEY))
    print(format_byte_array("stream_key_buf", stream_key))
    print(format_byte_array("plaintext_8", plaintext[:8]))
    print(format_byte_array("plaintext_16", plaintext[:16]))
    print(format_byte_array("plaintext_32", plaintext[:32]))
    print(format_byte_array("stream_message_64", stream_message[:64]))
    print(format_byte_array("stream_message_128", stream_message[:128]))
    print(format_byte_array("stream_message_256", stream_message))
    print(format_byte_array("digest_message_256", digest_message))
    print(format_byte_array("ecdsa_private_key_buf", ECDSA_PRIVATE_KEY))
    print(format_byte_array("ecdsa_private_key_32_buf", ECDSA_PRIVATE_KEY_32))
    print(format_byte_array("ecdsa_nonce_buf", ECDSA_NONCE))
    print(format_byte_array("ecdsa_digest_20", ecdsa_digest_20))
    print(format_byte_array("ecdsa_digest_32", ecdsa_digest_32))

    if not args.skip_bearssl:
        try:
            print(generate_bearssl_schedules(args.cc), end="")
        except subprocess.CalledProcessError as error:
            print(f"error: helper command failed with exit code {error.returncode}", file=sys.stderr)
            return error.returncode or 1
        except OSError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())