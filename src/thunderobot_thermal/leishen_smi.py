from __future__ import annotations

import struct
import subprocess
import threading
from dataclasses import dataclass
from typing import Protocol

import pythoncom
import wmi

from .fan_strategy import FanCommand, SensorSnapshot


READ_PRIMARY_STATUS = (0xFA00, 0x0200)
READ_SYSTEM_STATUS = (0xFA00, 0x0207)
SET_FAN_SPEED = (0xFB00, 0x0205)
SET_FAN_CONTROL_STATUS = (0xFB00, 0x0206)
SET_POWER_MODE = (0xFB00, 0x0300)


@dataclass
class SmiPacket:
    a0: int = 0
    a1: int = 0
    a2: int = 0
    a3: int = 0
    a4: int = 0
    a5: int = 0
    a6: int = 0
    rev0: int = 0
    rev1: int = 0

    def to_bytes(self) -> bytes:
        return struct.pack(
            "<HHIIIIIII",
            self.a0,
            self.a1,
            self.a2,
            self.a3,
            self.a4,
            self.a5,
            self.a6,
            self.rev0,
            self.rev1,
        )

    @classmethod
    def from_bytes(cls, payload: bytes) -> "SmiPacket":
        if len(payload) != 32:
            raise ValueError(f"SMI payload must be 32 bytes, got {len(payload)}")
        return cls(*struct.unpack("<HHIIIIIII", payload))


class SmiTransport(Protocol):
    def transact(self, packet: SmiPacket) -> SmiPacket:
        ...


class WmiSmiTransport:
    def __init__(self, namespace: str = r"root\wmi", persistent: bool = True) -> None:
        self._namespace = namespace
        self._persistent = persistent
        self._local = threading.local()

    def transact(self, packet: SmiPacket) -> SmiPacket:
        if self._persistent:
            connection = self._connection()
            return self._transact_with_connection(connection, packet)

        pythoncom.CoInitialize()
        try:
            connection = wmi.WMI(namespace=self._namespace)
            return self._transact_with_connection(connection, packet)
        finally:
            pythoncom.CoUninitialize()

    def _transact_with_connection(self, connection, packet: SmiPacket) -> SmiPacket:
        objects = connection.RW_GMWMI()
        if not objects:
            raise RuntimeError("WMI class RW_GMWMI was not found")
        item = objects[0]
        item.BufferBytes = list(packet.to_bytes())
        item.Put_()
        refreshed = connection.RW_GMWMI()[0]
        return SmiPacket.from_bytes(bytes(refreshed.BufferBytes))

    def _connection(self):
        connection = getattr(self._local, "connection", None)
        if connection is None:
            pythoncom.CoInitialize()
            connection = wmi.WMI(namespace=self._namespace)
            self._local.connection = connection
        return connection


class LeishenSmiClient:
    def __init__(self, transport: SmiTransport | None = None, persistent: bool = True) -> None:
        self._transport = transport or WmiSmiTransport(persistent=persistent)

    def read_sensors(self) -> SensorSnapshot:
        primary = self._transport.transact(SmiPacket(a0=READ_PRIMARY_STATUS[0], a1=READ_PRIMARY_STATUS[1]))
        system = self._transport.transact(SmiPacket(a0=READ_SYSTEM_STATUS[0], a1=READ_SYSTEM_STATUS[1]))
        return SensorSnapshot(
            cpu_temp=primary.a2 & 0xFF,
            gpu_temp=primary.a3 & 0xFF,
            sys_temp=system.a2 & 0xFF,
            cpu_fan_rpm=primary.a4 & 0xFFFF,
            gpu_fan_rpm=primary.a5 & 0xFFFF,
            sys_fan_rpm=system.a3 & 0xFFFF,
        )

    def set_fans(self, command: FanCommand) -> SmiPacket:
        command = command.clamped()
        return self._transport.transact(
            SmiPacket(
                a0=SET_FAN_SPEED[0],
                a1=SET_FAN_SPEED[1],
                a2=command.cpu,
                a3=command.gpu,
                a4=command.sys,
            )
        )

    def set_fan_control_enabled(self, enabled: bool) -> SmiPacket:
        return self._transport.transact(
            SmiPacket(
                a0=SET_FAN_CONTROL_STATUS[0],
                a1=SET_FAN_CONTROL_STATUS[1],
                a2=1 if enabled else 0,
            )
        )

    def release_fan_control(self) -> SmiPacket:
        self.set_fan_control_enabled(False)
        return self._transport.transact(
            SmiPacket(
                a0=SET_FAN_SPEED[0],
                a1=SET_FAN_SPEED[1],
                a2=255,
                a3=255,
                a4=255,
            )
        )

    def set_power_mode(self, mode: str) -> SmiPacket:
        mode_map = {
            "high": 0,
            "game": 1,
            "office": 2,
        }
        if mode not in mode_map:
            raise ValueError(f"unsupported power mode: {mode}")
        return self._transport.transact(
            SmiPacket(
                a0=SET_POWER_MODE[0],
                a1=SET_POWER_MODE[1],
                a2=mode_map[mode],
            )
        )


def activate_windows_power_plan(name: str) -> None:
    known_guids = {
        "high": "a9932169-f1fb-4dff-9034-fe1c4ca1886e",
        "game": "653fbb7f-248b-41d0-aa49-03fabbfd5e8e",
        "office": "5da85d85-eb0c-4710-a805-6da8bbcf1f02",
    }
    guid = known_guids.get(name)
    if guid is None:
        raise ValueError(f"unsupported Windows power plan: {name}")
    subprocess.run(["powercfg", "/S", guid], check=True)

