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
    require("resolveWssSocksProxy" in connections and "SharedConfig.currentProxy.secret" in connections, "SOCKS5 WSS must reuse the selected legacy SOCKS5 proxy and ignore MTProxy secrets")
    require("wssSocksHost" in connections and "wssSocksUsername" in connections and "wssSocksPassword" in connections, "Java WSS settings must pass selected SOCKS5 upstream credentials separately from WSS gateway settings")

    require("wssTransportModeRow" in proxy_list and "wssCustomGatewayRow" in proxy_list, "Proxy list UI must show a separate WSS transport section")
    require("R.string.WssTransportMode" in proxy_list and "R.string.WssTransportInfo" in proxy_list, "Proxy list UI must label WSS as a separate transport mode")
    require("R.string.ProxyConnections" in proxy_list and "R.string.WssTransportHeader" in proxy_list, "proxy UI must keep WSS rows apart from normal proxy connections")
    require("WSS_TRANSPORT_OPTIONS" in proxy_list and "ConnectionsManager.setWssTransportSettings" in proxy_list, "changing WSS mode in GUI must re-apply native transport settings")
    require("openWssGatewaySettingsIfNeeded" in proxy_list and "ProxySettingsActivity.createWssGateway(mode)" in proxy_list, "selecting custom WSS without a gateway must open the gateway editor instead of leaving an empty WSS mode")
    require("getEffectiveWssTransportMode" in proxy_list and "TextUtils.isEmpty(SharedConfig.wssHost)" in proxy_list and "return ConnectionsManager.WSS_TRANSPORT_OFF" in proxy_list, "saved custom WSS with an empty gateway must behave as off in the UI")
    require("isWssTransportSelected()" in proxy_list and "useProxyRow = -1" in proxy_list and "mtProxySoftMuxRow = -1" in proxy_list, "proxy UI must hide legacy proxy toggles and MTProxy tuning while WSS transport is selected")
    require("isWssSocks5TransportSelected()" in proxy_list and "if (wssSocks5TransportSelected)" in proxy_list and "isPlainSocksProxy" in proxy_list, "SOCKS5 WSS UI must keep the SOCKS5 proxy list visible while filtering out MTProxy entries")
    require("actionBar.setSubtitle(getString(R.string.WssTransportHeader)" in proxy_list and "ProxyCheckDiagnostics.headerStatusText" in proxy_list, "proxy UI header must show WSS status instead of legacy proxy status while WSS is selected")
    require("isWssSocks5TransportSelected()" in proxy_list and "isPlainSocksProxy" in proxy_list, "proxy UI must expose selected SOCKS5 proxies for SOCKS5 WSS without showing MTProxy entries")
    require("WssSocksUpstreamHeader" in proxy_list and "WssSocksUpstreamInfo" in proxy_list, "proxy UI must label the SOCKS5 list as WSS upstream, not as the legacy proxy mode")
    require("ProxySettingsActivity.createWssSocksUpstream()" in proxy_list and "ProxySettingsActivity.createWssSocksUpstream(currentInfo)" in proxy_list, "adding or editing a WSS SOCKS5 upstream must open a SOCKS-only proxy editor")

    require("TYPE_WSS" in proxy_settings and "UseProxyWss" in proxy_settings, "proxy detail UI must offer WSS as a different proxy type")
    require("FIELD_WSS_PATH" in proxy_settings and "FIELD_WSS_HOST" in proxy_settings, "WSS detail UI must expose host/path separately from MTProxy secret")
    require("createWssGateway(int mode)" in proxy_settings and "wssEditorTransportMode" in proxy_settings, "WSS gateway editor must remember the pending custom/socks5 mode before it is saved globally")
    require("UseProxyWssInfo" in proxy_settings and "UseProxyTelegramInfoStealth" in proxy_settings, "WSS explanatory copy must be separate from MTProxy stealth copy")
    require("createWssSocksUpstream()" in proxy_settings and "createWssSocksUpstream(SharedConfig.ProxyInfo proxyInfo)" in proxy_settings and "proxyTypeLocked" in proxy_settings and "saveAsWssSocksUpstream" in proxy_settings, "WSS SOCKS5 upstream editor must hide MTProxy choices and avoid enabling legacy proxy mode")
    require("ConnectionsManager.setWssTransportSettings()" in proxy_settings and "ConnectionsManager.setProxySettings(enabled" in proxy_settings, "saving a WSS SOCKS5 upstream must reapply WSS without starting legacy proxy mode")

    require('native_setWssTransportSettings", "(IIILjava/lang/String;ILjava/lang/String;ZLjava/lang/String;ILjava/lang/String;Ljava/lang/String;ZZ)V"' in wrapper, "JNI signature must carry WSS gateway plus selected SOCKS5 upstream settings")
    require("void setWssTransportSettings" in manager_h and "wssTransportMode" in manager_h and "wssSocksHost" in manager_h, "native manager must store WSS transport and selected SOCKS5 upstream settings")
    require("wssTransportChanged" in manager_cpp and "suspendConnections" in manager_cpp, "native manager must reconnect when WSS transport changes")

    require("WssTransport.cpp" in cmake and "tgnet/WssTransport.cpp" in cmake, "CMake must compile the native WSS transport module")
    require("class WssTransport" in wss_h and "WssRouteConfig" in wss_h, "WSS module must provide an isolated transport class and route config")
    require("kws2.web.telegram.org" in wss_cpp and "kws4.web.telegram.org" in wss_cpp and "/apiws" in wss_cpp, "WSS module must include official Telegram WSS route catalog")
    require("dcId != 2 && dcId != 4" in wss_cpp and "fallback to TCP" in socket_cpp, "official WSS must only auto-route proven DC2/DC4 relays and fall back for other DCs")
    require("Sec-WebSocket-Protocol: binary" in wss_cpp and "Sec-WebSocket-Key" in wss_cpp, "WSS module must perform a real WebSocket upgrade")
    require("SOCKS5-over-WSS" in wss_cpp and "buildSocks5Connect" in wss_cpp, "WSS module must include custom gateway SOCKS5-over-WSS support")
    require("upstreamSocksEnabled" in wss_h and "buildSocks5Greeting" in wss_cpp and "buildSocks5PasswordAuth" in wss_cpp, "WSS module must tunnel through selected SOCKS5 after the WSS gateway connect")
    require("SSL_connect" in wss_cpp and "SSL_read" in wss_cpp and "SSL_write" in wss_cpp, "WSS transport must use native TLS instead of FakeTLS or Python")

    require("openConnection(hostAddress, hostPort, secret, ipv6 != 0" in connection_cpp and "getDatacenterId()" in connection_cpp and "isMediaConnection" in connection_cpp, "Connection must pass DC/media metadata into the socket transport")
    require("isCurrentTransportWss()" in socket_h and "currentWssTransport" in socket_h, "ConnectionSocket must own WSS state separately from MTProxy state")
    require("wss_startup" in socket_cpp and "currentWssTransport->connect" in socket_cpp and "currentWssTransport->sendFrame" in socket_cpp, "ConnectionSocket must route connect/write/read through WSS when selected")
    require("manager.wssSocksHost" in socket_cpp and "manager.wssSocksUsername" in socket_cpp and "manager.wssSocksPassword" in socket_cpp and "manager.wssSocksEnabled" in socket_cpp, "ConnectionSocket custom WSS route must pass selected SOCKS5 upstream settings")
    require("wss_startup connect_start" in socket_cpp and "mtproxy_startup connect_start" in socket_cpp, "ConnectionSocket logs must not label WSS connects as MTProxy connects")
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
            "WssSocksUpstreamHeader",
            "WssSocksUpstreamInfo",
        ):
            require(f'name="{key}"' in source, f"{path.name} must define {key}")

    print("WSS transport mode guard passed.")


if __name__ == "__main__":
    main()
