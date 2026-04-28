import unittest

from thunderobot_thermal.fan_strategy import FanCommand
from thunderobot_thermal.leishen_smi import LeishenSmiClient, SmiPacket


class FakeTransport:
    def __init__(self) -> None:
        self.packets: list[SmiPacket] = []

    def transact(self, packet: SmiPacket) -> SmiPacket:
        self.packets.append(packet)
        if packet.a0 == 0xFA00 and packet.a1 == 0x0200:
            return SmiPacket(a2=66, a3=71, a4=3600, a5=3700)
        if packet.a0 == 0xFA00 and packet.a1 == 0x0207:
            return SmiPacket(a2=54, a3=4100)
        return packet


class SmiPacketTests(unittest.TestCase):
    def test_round_trips_packet_bytes(self) -> None:
        packet = SmiPacket(a0=0xFB00, a1=0x0205, a2=70, a3=80, a4=90)

        self.assertEqual(SmiPacket.from_bytes(packet.to_bytes()), packet)


class LeishenSmiClientTests(unittest.TestCase):
    def test_read_sensors_uses_primary_and_system_smi_commands(self) -> None:
        transport = FakeTransport()
        client = LeishenSmiClient(transport)

        snapshot = client.read_sensors()

        self.assertEqual(snapshot.cpu_temp, 66)
        self.assertEqual(snapshot.gpu_temp, 71)
        self.assertEqual(snapshot.sys_temp, 54)
        self.assertEqual(snapshot.cpu_fan_rpm, 3600)
        self.assertEqual(snapshot.gpu_fan_rpm, 3700)
        self.assertEqual(snapshot.sys_fan_rpm, 4100)
        self.assertEqual((transport.packets[0].a0, transport.packets[0].a1), (0xFA00, 0x0200))
        self.assertEqual((transport.packets[1].a0, transport.packets[1].a1), (0xFA00, 0x0207))

    def test_set_fans_uses_vendor_command_and_percent_fields(self) -> None:
        transport = FakeTransport()
        client = LeishenSmiClient(transport)

        client.set_fans(FanCommand(cpu=65, gpu=75, sys=85))

        packet = transport.packets[-1]
        self.assertEqual((packet.a0, packet.a1), (0xFB00, 0x0205))
        self.assertEqual((packet.a2, packet.a3, packet.a4), (65, 75, 85))

    def test_set_fan_control_enabled_uses_vendor_command(self) -> None:
        transport = FakeTransport()
        client = LeishenSmiClient(transport)

        client.set_fan_control_enabled(True)

        packet = transport.packets[-1]
        self.assertEqual((packet.a0, packet.a1, packet.a2), (0xFB00, 0x0206, 1))

    def test_release_fan_control_returns_auto_sentinel(self) -> None:
        transport = FakeTransport()
        client = LeishenSmiClient(transport)

        client.release_fan_control()

        self.assertEqual((transport.packets[-2].a0, transport.packets[-2].a1, transport.packets[-2].a2), (0xFB00, 0x0206, 0))
        self.assertEqual((transport.packets[-1].a0, transport.packets[-1].a1), (0xFB00, 0x0205))
        self.assertEqual((transport.packets[-1].a2, transport.packets[-1].a3, transport.packets[-1].a4), (255, 255, 255))

    def test_set_power_mode_uses_vendor_command(self) -> None:
        transport = FakeTransport()
        client = LeishenSmiClient(transport)

        client.set_power_mode("high")

        packet = transport.packets[-1]
        self.assertEqual((packet.a0, packet.a1, packet.a2), (0xFB00, 0x0300, 0))


if __name__ == "__main__":
    unittest.main()
