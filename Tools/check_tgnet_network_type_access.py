#!/usr/bin/env python3
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
MANAGER_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionsManager.cpp"
SOCKET_CPP = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.cpp"
SOCKET_H = ROOT / "TMessagesProj/jni/tgnet/ConnectionSocket.h"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def require(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    manager_cpp = read(MANAGER_CPP)
    socket_cpp = read(SOCKET_CPP)
    socket_h = read(SOCKET_H)

    require(
        "int32_t getCurrentNetworkType() const;" in socket_h,
        "ConnectionSocket must expose the socket network type through an accessor",
        failures,
    )
    require(
        "int32_t ConnectionSocket::getCurrentNetworkType() const" in socket_cpp,
        "ConnectionSocket.cpp must implement getCurrentNetworkType()",
        failures,
    )
    require(
        "return currentNetworkType;" in socket_cpp,
        "getCurrentNetworkType() must return the network type captured by openConnection()",
        failures,
    )
    require(
        "connection->currentNetworkType" not in manager_cpp,
        "ConnectionsManager must not access the old Connection::currentNetworkType field",
        failures,
    )
    require(
        "connection->getCurrentNetworkType()" in manager_cpp,
        "request completion paths must pass the connection socket network type",
        failures,
    )

    if failures:
        print("tgnet network type access guard failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1
    print("tgnet network type access guard passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
