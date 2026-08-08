import unittest

from ts2000 import MODE_CODES, RadioState, TS2000Emulator


class TS2000EmulatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.emu = TS2000Emulator(
            RadioState(
                frequency_a_hz=14_074_000,
                frequency_b_hz=7_074_000,
                mode_code=2,
                rx_vfo=0,
                tx_vfo=0,
                ptt=False,
            )
        )

    def test_fragmented_input(self) -> None:
        self.assertEqual(self.emu.feed("F"), [])
        self.assertEqual(self.emu.feed("A;"), ["FA00014074000;"])

    def test_multiple_commands_in_one_read(self) -> None:
        self.assertEqual(
            self.emu.feed("FA;FB;MD;FR;FT;ID;"),
            [
                "FA00014074000;",
                "FB00007074000;",
                "MD2;",
                "FR0;",
                "FT0;",
                "ID019;",
            ],
        )

    def test_set_frequency_a(self) -> None:
        self.assertEqual(self.emu.feed("FA00007000000;"), [])
        self.assertEqual(self.emu.state.frequency_a_hz, 7_000_000)
        self.assertEqual(self.emu.feed("FA;"), ["FA00007000000;"])

    def test_set_frequency_requires_11_digits(self) -> None:
        self.assertEqual(self.emu.feed("FA7000000;"), ["?;"])

    def test_mode(self) -> None:
        self.assertEqual(self.emu.feed("MD1;"), [])
        self.assertEqual(self.emu.state.mode_code, 1)
        self.assertEqual(MODE_CODES[self.emu.state.mode_code], "LSB")
        self.assertEqual(self.emu.feed("MD;"), ["MD1;"])

    def test_invalid_mode(self) -> None:
        self.assertEqual(self.emu.feed("MD8;"), ["?;"])

    def test_vfo_and_split(self) -> None:
        self.emu.feed("FR0;FT1;")
        self.assertFalse(self.emu.state.ptt)
        self.assertTrue(self.emu.state.split)
        self.assertEqual(self.emu.feed("FR;FT;"), ["FR0;", "FT1;"])

    def test_ptt(self) -> None:
        self.emu.feed("TX;")
        self.assertTrue(self.emu.state.ptt)
        self.emu.feed("RX;")
        self.assertFalse(self.emu.state.ptt)

    def test_unknown_command_is_captured(self) -> None:
        self.assertEqual(self.emu.feed("IF;"), [])
        self.assertEqual(self.emu.unsupported_commands, ["IF"])


if __name__ == "__main__":
    unittest.main()
