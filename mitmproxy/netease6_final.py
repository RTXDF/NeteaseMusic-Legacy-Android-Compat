from mitmproxy import http, ctx

from cryptography.hazmat.primitives.ciphers import (
    Cipher,
    algorithms,
    modes,
)

import hashlib
import json
import os
import re
import time
import urllib.parse
import urllib.request


# ============================================================
# Configuration
# ============================================================

PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

DEFAULT_CONFIG_FILE = os.path.join(
    PROJECT_ROOT,
    "config",
    "config.json"
)


def load_config() -> dict:
    config_file = os.path.expandvars(
        os.path.expanduser(
            os.getenv(
                "NCM_COMPAT_CONFIG",
                DEFAULT_CONFIG_FILE
            )
        )
    )

    if not os.path.exists(config_file):
        return {}

    with open(
        config_file,
        "r",
        encoding="utf-8"
    ) as f:
        return json.load(f)


CONFIG = load_config()

QR_FILE = os.path.expandvars(
    os.path.expanduser(
        os.getenv(
            "NCM_QR_FILE",
            CONFIG.get(
                "qr_file",
                "~/ncm_qr_result.json"
            )
        )
    )
)

LOCAL_API = os.getenv(
    "NCM_LOCAL_API",
    CONFIG.get(
        "local_api",
        "http://127.0.0.1:3000"
    )
).rstrip("/")

# 这组身份已经在 HTC / NCM 6.0 上验证能够越过旧版本检查。
NEW_APPVER = os.getenv(
    "NCM_APPVER",
    str(CONFIG.get(
        "appver",
        "8.20.20.231215173437"
    ))
)
NEW_VERSIONCODE = os.getenv(
    "NCM_VERSIONCODE",
    str(CONFIG.get(
        "versioncode",
        "140"
    ))
)

EAPI_KEY = b"e82ckenh8dichen8"
EAPI_SEP = b"-36cd479b6b5-"

AUTH_COOKIE_NAMES = {
    "MUSIC_U",
    "MUSIC_A",
    "__csrf",
    "NMTID",
    "MUSIC_R_T",
    "MUSIC_R_I",
}


# ============================================================
# PKCS7
# ============================================================

def pkcs7_pad(data: bytes) -> bytes:
    n = 16 - len(data) % 16
    return data + bytes([n]) * n


def pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty decrypted data")

    n = data[-1]

    if n < 1 or n > 16:
        raise ValueError(
            "invalid PKCS7 padding length"
        )

    if data[-n:] != bytes([n]) * n:
        raise ValueError(
            "invalid PKCS7 padding bytes"
        )

    return data[:-n]


# ============================================================
# EAPI AES
# ============================================================

def aes_ecb_encrypt(data: bytes) -> bytes:
    enc = Cipher(
        algorithms.AES(EAPI_KEY),
        modes.ECB()
    ).encryptor()

    data = pkcs7_pad(data)

    return (
        enc.update(data)
        + enc.finalize()
    )


def aes_ecb_decrypt(data: bytes) -> bytes:
    if len(data) % 16:
        raise ValueError(
            "EAPI ciphertext length "
            "is not multiple of 16"
        )

    dec = Cipher(
        algorithms.AES(EAPI_KEY),
        modes.ECB()
    ).decryptor()

    data = (
        dec.update(data)
        + dec.finalize()
    )

    return pkcs7_unpad(data)


# ============================================================
# Cookie helpers
# ============================================================

def parse_cookie(cookie: str) -> dict:
    result = {}

    for part in (cookie or "").split(";"):
        part = part.strip()

        if "=" not in part:
            continue

        key, value = part.split("=", 1)

        result[key.strip()] = value.strip()

    return result


def cookie_to_string(cookies: dict) -> str:
    return "; ".join(
        f"{k}={v}"
        for k, v in cookies.items()
    )


def load_qr_cookie() -> str:
    if not os.path.exists(QR_FILE):
        raise FileNotFoundError(
            f"QR credential missing: {QR_FILE}"
        )

    with open(
        QR_FILE,
        "r",
        encoding="utf-8"
    ) as f:
        data = json.load(f)

    cookie = data.get("cookie", "")

    if not cookie:
        raise ValueError(
            "QR file does not contain cookie"
        )

    return cookie


def get_qr_auth_cookies() -> dict:
    qr = parse_cookie(
        load_qr_cookie()
    )

    return {
        k: v
        for k, v in qr.items()
        if k in AUTH_COOKIE_NAMES
    }


# ============================================================
# Local API login/status
# ============================================================

def get_login_status() -> dict:
    cookie = load_qr_cookie()

    query = urllib.parse.urlencode({
        "cookie": cookie
    })

    url = (
        LOCAL_API
        + "/login/status?"
        + query
    )

    with urllib.request.urlopen(
        url,
        timeout=15
    ) as response:

        data = json.loads(
            response
            .read()
            .decode("utf-8")
        )

    status = data.get(
        "data",
        {}
    )

    if status.get("code") != 200:
        raise ValueError(
            "login/status returned "
            + repr(status.get("code"))
        )

    if not status.get("account"):
        raise ValueError(
            "login/status missing account"
        )

    if not status.get("profile"):
        raise ValueError(
            "login/status missing profile"
        )

    return status


# ============================================================
# EAPI decode
# ============================================================

def decode_eapi_params(params: str):
    raw = aes_ecb_decrypt(
        bytes.fromhex(params)
    )

    parts = raw.split(
        EAPI_SEP,
        2
    )

    if len(parts) != 3:
        raise ValueError(
            "unexpected EAPI structure"
        )

    url = parts[0].decode(
        "utf-8",
        errors="replace"
    )

    obj = json.loads(
        parts[1].decode("utf-8")
    )

    return url, obj


# ============================================================
# EAPI encode + MD5 signature
# ============================================================

def encode_eapi_params(
    url: str,
    obj: dict
) -> str:

    text = json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":")
    )

    source = (
        "nobody"
        + url
        + "use"
        + text
        + "md5forencrypt"
    )

    digest = hashlib.md5(
        source.encode("utf-8")
    ).hexdigest()

    plaintext = (
        url
        + "-36cd479b6b5-"
        + text
        + "-36cd479b6b5-"
        + digest
    )

    encrypted = aes_ecb_encrypt(
        plaintext.encode("utf-8")
    )

    return encrypted.hex().upper()


def encode_eapi_response(
    obj: dict
) -> bytes:

    text = json.dumps(
        obj,
        ensure_ascii=False,
        separators=(",", ":")
    )

    return aes_ecb_encrypt(
        text.encode("utf-8")
    )


# ============================================================
# Identify NetEase Music hosts
# ============================================================

def is_music_host(host: str) -> bool:
    host = (host or "").lower()

    return (
        host == "music.163.com"
        or
        host.endswith(".music.163.com")
    )


# ============================================================
# Global outer-layer identity spoof
# ============================================================

def patch_outer_identity(flow):
    buildver = str(
        int(time.time())
    )

    # --------------------------------------------------------
    # User-Agent
    # --------------------------------------------------------

    ua = flow.request.headers.get(
        "User-Agent",
        ""
    )

    if "NeteaseMusic/" in ua:
        ua = re.sub(
            r"NeteaseMusic/[^\s;]+"
            r"(?:\([^)]*\))?",
            (
                f"NeteaseMusic/"
                f"{NEW_APPVER}"
                f"({NEW_VERSIONCODE})"
            ),
            ua,
            count=1
        )

        flow.request.headers[
            "User-Agent"
        ] = ua

    # --------------------------------------------------------
    # Cookie
    # --------------------------------------------------------

    cookies = parse_cookie(
        flow.request.headers.get(
            "Cookie",
            ""
        )
    )

    # 强制高版本身份
    cookies["appver"] = (
        NEW_APPVER
    )

    cookies["versioncode"] = (
        NEW_VERSIONCODE
    )

    cookies["buildver"] = buildver

    # 如果客户端没有登录 Cookie，
    # 自动补入 QR 授权获得的登录态。
    try:
        auth = get_qr_auth_cookies()

        for key, value in auth.items():

            # MUSIC_U / MUSIC_A 等以二维码登录态为准，
            # 保证老客户端即使没有持久化 Cookie 也能认证。
            cookies[key] = value

    except Exception as e:
        ctx.log.warn(
            "[AUTH COOKIE] "
            + repr(e)
        )

    flow.request.headers[
        "Cookie"
    ] = cookie_to_string(
        cookies
    )


# ============================================================
# Global EAPI header patch
# ============================================================

def patch_eapi(flow):
    if "/eapi/" not in flow.request.path:
        return

    try:
        body = flow.request.get_text(
            strict=False
        )

        form = urllib.parse.parse_qsl(
            body,
            keep_blank_values=True
        )

        params = None

        for key, value in form:
            if key == "params":
                params = value
                break

        if not params:
            return

        url, obj = decode_eapi_params(
            params
        )

        header = obj.get(
            "header",
            {}
        )

        if not isinstance(
            header,
            dict
        ):
            return

        old_appver = header.get(
            "appver"
        )

        header["appver"] = (
            NEW_APPVER
        )

        header["versioncode"] = (
            NEW_VERSIONCODE
        )

        header["buildver"] = str(
            int(time.time())
        )

        obj["header"] = header

        new_params = encode_eapi_params(
            url,
            obj
        )

        new_form = []

        for key, value in form:

            if key == "params":
                value = new_params

            new_form.append(
                (key, value)
            )

        new_body = urllib.parse.urlencode(
            new_form
        )

        flow.request.text = new_body

        if old_appver != NEW_APPVER:
            ctx.log.info(
                "[EAPI] "
                + url
                + " appver "
                + str(old_appver)
                + " -> "
                + NEW_APPVER
            )

    except Exception as e:
        # 某些接口即使路径有 /eapi/
        # 也未必使用标准 Android EAPI 格式。
        # 不影响原请求继续发送。
        ctx.log.warn(
            "[EAPI PATCH] "
            + flow.request.path
            + ": "
            + repr(e)
        )


# ============================================================
# Login-state injection
# ============================================================

def inject_login(flow):
    status = get_login_status()

    account = status.get(
        "account"
    )

    profile = status.get(
        "profile"
    )

    result = {
        "code": 200,
        "loginType": 1,
        "account": account,
        "profile": profile,
        "bindings": status.get(
            "bindings",
            []
        ),
    }

    encrypted = encode_eapi_response(
        result
    )

    flow.response = http.Response.make(
        200,
        encrypted,
        {
            "Content-Type":
                "application/json;charset=UTF-8",

            "Cache-Control":
                "no-cache, no-store",

            "Connection":
                "keep-alive",
        }
    )

    auth = get_qr_auth_cookies()

    for key, value in auth.items():
        flow.response.headers.add(
            "Set-Cookie",
            (
                f"{key}={value}; "
                "Path=/; "
                "Domain=.music.163.com"
            )
        )

    ctx.log.warn("")
    ctx.log.warn(
        "========== NCM LOGIN =========="
    )
    ctx.log.warn(
        "[LOGIN] QR session valid"
    )
    ctx.log.warn(
        "[LOGIN] account=True"
    )
    ctx.log.warn(
        "[LOGIN] profile=True"
    )
    ctx.log.warn(
        "[LOGIN] auth cookies injected"
    )
    ctx.log.warn(
        "[LOGIN] *** SUCCESS ***"
    )
    ctx.log.warn(
        "==============================="
    )
    ctx.log.warn("")


# ============================================================
# mitmproxy request hook
# ============================================================

def request(flow: http.HTTPFlow):
    host = flow.request.pretty_host

    if not is_music_host(host):
        return

    # --------------------------------------------------------
    # 老 NCM 6.0 的手机号登录直接由 QR 登录态接管。
    # 用户输入的密码不会再发送给网易云。
    # --------------------------------------------------------

    if (
        host == "interface.music.163.com"
        and
        flow.request.path.startswith(
            "/eapi/login/cellphone"
        )
    ):
        try:
            inject_login(flow)

        except Exception as e:
            ctx.log.error(
                "[LOGIN INJECT] "
                + repr(e)
            )

        return

    # --------------------------------------------------------
    # 所有其他网易云请求：
    #
    # 1. 外层 UA / Cookie 伪装
    # 2. QR 登录 Cookie 注入
    # 3. EAPI 内层 header 伪装
    # --------------------------------------------------------

    patch_outer_identity(flow)
    patch_eapi(flow)
