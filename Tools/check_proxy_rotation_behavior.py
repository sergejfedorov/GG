#!/usr/bin/env python3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MESSENGER = ROOT / "TMessagesProj/src/main/java/org/telegram/messenger"
ROTATION = MESSENGER / "ProxyRotationController.java"
ENGINE = MESSENGER / "ProxyRotationEngine.java"
STORE = MESSENGER / "ProxyRuntimeStateStore.java"
HEALTH = MESSENGER / "ProxyHealthStore.java"
STATUS = MESSENGER / "ProxyStatusMirror.java"
CHECK_ALL = ROOT / "Tools/check_mtproxy_all.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def method_body(text: str, signature: str) -> str:
    start = text.find(signature)
    if start == -1:
        return ""
    brace = text.find("{", start)
    if brace == -1:
        return ""
    depth = 0
    for index in range(brace, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    return text[start:]


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def ordered(body: str, *needles: str) -> bool:
    cursor = -1
    for needle in needles:
        index = body.find(needle, cursor + 1)
        if index == -1:
            return False
        cursor = index
    return True


def main() -> int:
    failures: list[str] = []
    rotation = read(ROTATION)
    engine = read(ENGINE)
    store = read(STORE)
    health = read(HEALTH)
    status = read(STATUS)
    check_all = read(CHECK_ALL)

    switch_to_proxy = method_body(rotation, "private void switchToProxy")
    settings_branch = rotation[rotation.find("if (id == NotificationCenter.proxySettingsChanged)"):]
    settings_branch = settings_branch[:settings_branch.find("} else if", 1)]
    on_rotation_settings = method_body(engine, "void onRotationSettingsApplied")
    on_external_settings = method_body(engine, "void onSettingsChanged")
    complete_attempt = method_body(engine, "SwitchDecision completeScheduledAttempt")
    begin_attempt = method_body(engine, "Attempt beginScheduledAttempt")
    record_switch = method_body(engine, "void recordSwitch")
    is_candidate_allowed = method_body(engine, "private boolean isCandidateAllowed")

    require(
        ordered(
            switch_to_proxy,
            "engine.recordSwitch(info)",
            "postNotificationName(NotificationCenter.proxyChangedByRotation)",
            "postNotificationName(NotificationCenter.proxySettingsChanged, ROTATION_SETTINGS_CHANGE)",
            "ConnectionsManager.setProxySettings",
        ),
        "rotation switch must record rate-limit/cycle state before notifying UI and applying native settings",
        failures,
    )
    require(
        ordered(
            settings_branch,
            "cancelScheduledSwitchRunnable();",
            "if (isRotationOwnedSettingsChange(args))",
            "engine.onRotationSettingsApplied();",
            "return;",
            "engine.onSettingsChanged();",
        ),
        "rotation-owned proxySettingsChanged must bypass external settings reset path",
        failures,
    )
    require(
        "cycle.reset()" not in on_rotation_settings
        and "switchTimes.clear()" not in on_rotation_settings
        and "triedExactKeys.clear()" not in on_rotation_settings,
        "rotation-owned settings application must preserve switch history and tried endpoints",
        failures,
    )
    require(
        "cycle.reset()" in on_external_settings,
        "external settings changes must reset rotation cycle",
        failures,
    )
    require(
        ordered(
            complete_attempt,
            "ProxyCheckDiagnostics.CONNECTING_TIMEOUT.equals(attempt.reason)",
            "ProxyRuntimeStateStore.markEndpointFailure(currentProxy, ProxyCheckDiagnostics.CONNECTING_TIMEOUT)",
            "return selectSwitchCandidate(currentProxy, now)",
        ),
        "connecting timeout must be recorded as endpoint failure before selecting a fallback",
        failures,
    )
    require(
        "cycle.triedExactKeys.add(proxyExactKey)" in begin_attempt
        and "cycle.triedExactKeys.add(exactKey)" in record_switch
        and "!cycle.triedExactKeys.contains(exactKey)" in is_candidate_allowed,
        "rotation cycle must remember attempted endpoints and reject retries within the same cycle",
        failures,
    )
    require(
        "cycle.switchTimes.addLast(now)" in record_switch
        and "cycle.switchTimes.size() >= MAX_SWITCHES_PER_WINDOW" in engine
        and "decision = \"rate_limited\"" in engine,
        "rotation must enforce a real switch rate-limit window",
        failures,
    )
    require(
        "HashMap<String, EndpointState> endpointStates" in health
        and "endpointStates" not in store,
        "endpoint health state must live only in ProxyHealthStore, not the runtime facade",
        failures,
    )
    require(
        all(needle in status for needle in (
            ".lastCheckDiagnostic =",
            ".lastCheckDiagnosticTime =",
            ".available =",
            ".availableCheckTime =",
            ".checking =",
            ".proxyCheckPingId =",
            ".ping =",
        )),
        "ProxyStatusMirror must own all runtime ProxyInfo UI-state writes",
        failures,
    )
    require(
        all(needle not in store for needle in (
            ".lastCheckDiagnostic =",
            ".lastCheckDiagnosticTime =",
            ".available =",
            ".availableCheckTime =",
            ".checking =",
            ".proxyCheckPingId =",
            ".ping =",
        )),
        "ProxyRuntimeStateStore facade must not write runtime ProxyInfo UI-state directly",
        failures,
    )
    require(
        '"check_proxy_rotation_behavior.py"' in check_all,
        "full MTProxy guard suite must include rotation behavior scenarios",
        failures,
    )

    if failures:
        print("Proxy rotation behavior guard failed:")
        for failure in failures:
            print(f" - {failure}")
        return 1

    print("Proxy rotation behavior guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
