#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
CONNECTIONS_JAVA = ROOT / "TMessagesProj/src/main/java/org/telegram/tgnet/ConnectionsManager.java"
PROXY_LIST = ROOT / "TMessagesProj/src/main/java/org/telegram/ui/ProxyListActivity.java"
SHARED_CONFIG = ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/SharedConfig.java"
SOCKET_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.cpp"
SOCKET_H = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.h"
MANAGER_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionsManager.cpp"
MANAGER_H = ROOT / "TMessagesProj/jni/tgnet/ConnectionsManager.h"
PROXY_CHECK = ROOT / "TMessagesProj/jni/tgnet/ProxyCheckInfo.h"
STRINGS = ROOT / "TMessagesProj/src/main/res/values/strings.xml"
STRINGS_RU = ROOT / "TMessagesProj/src/main/res/values-ru/strings.xml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    connections = text(CONNECTIONS_JAVA)
    proxy_list = text(PROXY_LIST)
    shared_config = text(SHARED_CONFIG)
    socket_cpp = text(SOCKET_CPP)
    socket_h = text(SOCKET_H)
    manager_cpp = text(MANAGER_CPP)
    manager_h = text(MANAGER_H)
    proxy_check = text(PROXY_CHECK)

    for name in ("OFF", "SOFT", "QUIET", "STRICT"):
        require(
            f"MT_PROXY_CONNECTION_PATTERN_{name}" in connections
            and f"MT_PROXY_CONNECTION_PATTERN_{name}" in socket_cpp,
            f"Java and native must define MTProxy connection pattern {name}",
        )

    require(
        "public static int mtProxyConnectionPatternMode" in shared_config
        and 'getInt("mtProxyConnectionPatternMode"' in shared_config
        and 'getBoolean("mtProxyHandshakeAdmission", false)' in shared_config
        and 'putInt("mtProxyConnectionPatternMode", mtProxyConnectionPatternMode)' in shared_config,
        "SharedConfig must persist integer connection-pattern mode and migrate the old admission boolean",
    )
    require(
        "private static int resolveMtProxyConnectionPatternMode()" in connections
        and "SharedConfig.mtProxyConnectionPatternMode" in connections
        and "mtProxyConnectionPatternMode" in connections
        and "native_setProxySettings(currentAccount, proxyAddress, proxyPort, proxyUsername, proxyPassword, proxySecret, mtProxyTlsProfile, mtProxyClientHelloFragmentation, mtProxyConnectionPatternMode, mtProxyRecordSizingMode, mtProxyTimingMode, mtProxyStartupCoverMode)" in connections,
        "Java must pass the selected connection-pattern mode into native proxy settings",
    )
    require(
        "mtProxyConnectionPatternRow" in proxy_list
        and "MT_PROXY_CONNECTION_PATTERN_OPTIONS" in proxy_list
        and "getMtProxyConnectionPatternLabels()" in proxy_list
        and "SharedConfig.mtProxyConnectionPatternMode" in proxy_list
        and "VIEW_TYPE_SLIDE_CHOOSER" in proxy_list,
        "proxy settings UI must expose connection pattern as a SlideChooseView, not a checkbox",
    )
    require(
        "SharedConfig.mtProxyHandshakeAdmission = !" not in proxy_list
        and "mtProxyHandshakeAdmissionRow" not in proxy_list,
        "old admission checkbox row must be replaced by the connection-pattern chooser",
    )
    require(
        "int32_t proxyConnectionPatternMode = 0" in manager_h
        and "normalizeMtProxyConnectionPatternMode" in manager_cpp
        and "connectionPatternChanged" in manager_cpp
        and "proxyConnectionPatternMode = normalizeMtProxyConnectionPatternMode" in manager_cpp,
        "native ConnectionsManager must store connection-pattern mode and reconnect when it changes",
    )
    require(
        "int32_t mtProxyConnectionPatternMode" in proxy_check
        and "overrideProxyConnectionPatternMode" in socket_h
        and "currentConnectionPatternMode" in socket_h
        and "setOverrideProxy(std::string address, uint16_t port, std::string username, std::string password, std::string secret, int32_t mtProxyTlsProfile, int32_t mtProxyClientHelloFragmentation, int32_t mtProxyConnectionPatternMode, int32_t mtProxyRecordSizingMode, int32_t mtProxyTimingMode, int32_t mtProxyStartupCoverMode)" in socket_h,
        "proxy-check override sockets must carry the same connection-pattern mode as real sockets",
    )
    require(
        "mtProxyConnectionPatternModeName" in socket_cpp
        and "mtProxyConnectionPatternUsesAdmission" in socket_cpp
        and "mtProxyConnectionPatternUsesCooldown" in socket_cpp
        and "mtProxyHandshakeGrantDelay(int32_t mode)" in socket_cpp
        and "mtProxyHandshakeSpacingDelay" in socket_cpp
        and "lastGrantTime" in socket_cpp
        and "mtProxyHandshakeRetryDelay(int64_t now, int64_t cooldownUntil, int32_t priority, int32_t mode)" in socket_cpp
        and "mtProxyHandshakeActiveLimit(const MtProxyHandshakeEndpointState &state, int64_t now, int32_t mode)" in socket_cpp,
        "ConnectionSocket scheduler must be mode-aware for admission, delay, retry, limit, and cooldown policy",
    )
    require(
        "admission_mode=%s" in socket_cpp
        and "connection_pattern=%s" in socket_cpp
        and 'return "strict";' in socket_cpp
        and 'return "quiet";' in socket_cpp
        and "admission_failure_cooldown" in socket_cpp,
        "startup diagnostics must log readable connection-pattern/admission mode and cooldown decisions",
    )
    require(
        "MT_PROXY_CONNECTION_PATTERN_STRICT" in socket_cpp
        and "3000 + secureRandomBounded(3001)" in socket_cpp
        and "MT_PROXY_CONNECTION_PATTERN_QUIET" in socket_cpp
        and "1200 + secureRandomBounded(1301)" in socket_cpp,
        "quiet and strict modes must slow sequential grants instead of only limiting concurrency",
    )
    for path in (STRINGS, STRINGS_RU):
        source = text(path)
        require(
            'name="MtProxyConnectionPattern"' in source
            and 'name="MtProxyConnectionPatternInfo"' in source
            and 'name="MtProxyConnectionPatternOff"' in source
            and 'name="MtProxyConnectionPatternSoft"' in source
            and 'name="MtProxyConnectionPatternQuiet"' in source
            and 'name="MtProxyConnectionPatternStrict"' in source,
            f"{path.name} must define connection-pattern UI strings",
        )

    print("MTProxy connection pattern modes guard passed.")


if __name__ == "__main__":
    main()
