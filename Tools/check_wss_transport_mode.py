#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SHARED_CONFIG = ROOT / "TMessagesProj/src/main/java/org/telegram/messenger/SharedConfig.java"
CONNECTIONS_JAVA = ROOT / "TMessagesProj/src/main/java/org/telegram/tgnet/ConnectionsManager.java"
PROXY_LIST = ROOT / "TMessagesProj/src/main/java/org/telegram/ui/ProxyListActivity.java"
PROXY_SETTINGS = ROOT / "TMessagesProj/src/main/java/org/telegram/ui/ProxySettingsActivity.java"
BOT_WEBVIEW = ROOT / "TMessagesProj/src/main/java/org/telegram/ui/web/BotWebViewContainer.java"
WRAPPER_CPP = ROOT / "TMessagesProj/jni/TgNetWrapper.cpp"
MANAGER_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionsManager.cpp"
MANAGER_H = ROOT / "TMessagesProj/jni/tgnet/ConnectionsManager.h"
CONNECTION_CPP = ROOT / "TMessagesProj/jni/tgnet/Connection.cpp"
SOCKET_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.cpp"
SOCKET_H = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.h"
WSS_H = ROOT / "TMessagesProj/jni/tgnet/WssTransport.h"
WSS_CPP = ROOT / "TMessagesProj/jni/tgnet/WssTransport.cpp"
CMAKE = ROOT / "TMessagesProj/jni/CMakeLists.txt"
STRINGS = ROOT / "TMessagesProj/src/main/res/values/strings.xml"
STRINGS_RU = ROOT / "TMessagesProj/src/main/res/values-ru/strings.xml"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def require(condition: bool, message: str) -> None:
    if not condition:
        print(f"FAIL: {message}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    shared_config = text(SHARED_CONFIG)
    connections = text(CONNECTIONS_JAVA)
    proxy_list = text(PROXY_LIST)
    proxy_settings = text(PROXY_SETTINGS)
    bot_webview = text(BOT_WEBVIEW)
    wrapper = text(WRAPPER_CPP)
    manager_cpp = text(MANAGER_CPP)
    manager_h = text(MANAGER_H)
    connection_cpp = text(CONNECTION_CPP)
    socket_cpp = text(SOCKET_CPP)
    socket_h = text(SOCKET_H)
    cmake = text(CMAKE)
    wss_h = text(WSS_H) if WSS_H.exists() else ""
    wss_cpp = text(WSS_CPP) if WSS_CPP.exists() else ""

    require("PROXY_SCHEMA_V3" in shared_config, "proxy list schema must persist WSS transport fields separately from SOCKS5/MTProto")
    require("TRANSPORT_WSS_OFFICIAL" in shared_config and "TRANSPORT_WSS_CUSTOM" in shared_config and "TRANSPORT_WSS_SOCKS5" in shared_config, "SharedConfig must expose distinct WSS transport modes")
    require("wssHost" in shared_config and "wssPath" in shared_config and "wssUseForMiniApps" in shared_config, "ProxyInfo must persist custom WSS endpoint and miniapp routing intent")
    require("isWssTransport()" in shared_config and "isSocks5OverWss()" in shared_config, "ProxyInfo must distinguish WSS from legacy proxy modes")

    require("WSS_TRANSPORT_OFFICIAL" in connections and "setWssTransportSettings" in connections, "Java ConnectionsManager must expose WSS constants and setter")
    require("native_setWssTransportSettings" in connections, "Java must wire WSS settings into JNI separately from proxy settings")
    require("resolveWssTransportMode" in connections, "Java must normalize WSS mode before native calls")

    require("wssTransportModeRow" in proxy_list and "wssCustomGatewayRow" in proxy_list, "Proxy list UI must show a separate WSS transport section")
    require("R.string.WssTransportMode" in proxy_list and "R.string.WssTransportInfo" in proxy_list, "Proxy list UI must label WSS as a separate transport mode")
    require("R.string.ProxyConnections" in proxy_list and "R.string.WssTransportHeader" in proxy_list, "proxy UI must keep WSS rows apart from normal proxy connections")
    require("WSS_TRANSPORT_OPTIONS" in proxy_list and "ConnectionsManager.setWssTransportSettings" in proxy_list, "changing WSS mode in GUI must re-apply native transport settings")

    require("TYPE_WSS" in proxy_settings and "UseProxyWss" in proxy_settings, "proxy detail UI must offer WSS as a different proxy type")
    require("FIELD_WSS_PATH" in proxy_settings and "FIELD_WSS_HOST" in proxy_settings, "WSS detail UI must expose host/path separately from MTProxy secret")
    require("UseProxyWssInfo" in proxy_settings and "UseProxyTelegramInfoStealth" in proxy_settings, "WSS explanatory copy must be separate from MTProxy stealth copy")

    require('native_setWssTransportSettings", "(IIILjava/lang/String;ILjava/lang/String;ZZ)V"' in wrapper, "JNI signature must carry WSS mode, gateway type, host, port, path, miniapp flag, and enable flag")
    require("void setWssTransportSettings" in manager_h and "wssTransportMode" in manager_h, "native manager must store WSS transport settings")
    require("wssTransportChanged" in manager_cpp and "suspendConnections" in manager_cpp, "native manager must reconnect when WSS transport changes")

    require("WssTransport.cpp" in cmake and "tgnet/WssTransport.cpp" in cmake, "CMake must compile the native WSS transport module")
    require("class WssTransport" in wss_h and "WssRouteConfig" in wss_h, "WSS module must provide an isolated transport class and route config")
    require("kws2.web.telegram.org" in wss_cpp and "kws4.web.telegram.org" in wss_cpp and "/apiws" in wss_cpp, "WSS module must include official Telegram WSS route catalog")
    require("dcId != 2 && dcId != 4" in wss_cpp and "fallback to TCP" in socket_cpp, "official WSS must only auto-route proven DC2/DC4 relays and fall back for other DCs")
    require("Sec-WebSocket-Protocol: binary" in wss_cpp and "Sec-WebSocket-Key" in wss_cpp, "WSS module must perform a real WebSocket upgrade")
    require("SOCKS5-over-WSS" in wss_cpp and "buildSocks5Connect" in wss_cpp, "WSS module must include custom gateway SOCKS5-over-WSS support")
    require("SSL_connect" in wss_cpp and "SSL_read" in wss_cpp and "SSL_write" in wss_cpp, "WSS transport must use native TLS instead of FakeTLS or Python")

    require("openConnection(hostAddress, hostPort, secret, ipv6 != 0" in connection_cpp and "getDatacenterId()" in connection_cpp and "isMediaConnection" in connection_cpp, "Connection must pass DC/media metadata into the socket transport")
    require("isCurrentTransportWss()" in socket_h and "currentWssTransport" in socket_h, "ConnectionSocket must own WSS state separately from MTProxy state")
    require("wss_startup" in socket_cpp and "currentWssTransport->connect" in socket_cpp and "currentWssTransport->sendFrame" in socket_cpp, "ConnectionSocket must route connect/write/read through WSS when selected")
    require("forceProxyLikeInitForWss" in connection_cpp, "WSS mode must force the first MTProto init to carry dc_id without requiring an MTProxy secret")

    require("applyMiniAppWssProxyIfNeeded" in bot_webview and "wssUseForMiniApps" in bot_webview, "Bot miniapp WebView must have an explicit hook for WSS proxy routing")

    for path in (STRINGS, STRINGS_RU):
        source = text(path)
        for key in (
            "WssTransportHeader",
            "WssTransportMode",
            "WssTransportOff",
            "WssTransportOfficial",
            "WssTransportCustom",
            "WssTransportSocks5",
            "WssTransportInfo",
            "UseProxyWss",
            "UseProxyWssHost",
            "UseProxyWssPath",
            "UseProxyWssMiniApps",
            "UseProxyWssInfo",
        ):
            require(f'name="{key}"' in source, f"{path.name} must define {key}")

    print("WSS transport mode guard passed.")


if __name__ == "__main__":
    main()
