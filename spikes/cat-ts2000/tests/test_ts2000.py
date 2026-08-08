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
                auto_information=0,
                af_gain_main=128,
            )
        )

    def test_fragmented_input(self) -> None:
        self.assertEqual(self.emu.feed("F"), [])
        self.assertEqual(self.emu.feed("A;"), ["FA00014074000;"])

    def test_multiple_commands_in_one_read(self) -> None:
        self.assertEqual(
            self.emu.feed("FA;FB;MD;FR;FT;ID;"),
            ["FA00014074000;", "FB00007074000;", "MD2;", "FR0;", "FT0;", "ID019;"],
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

    def test_ai_off_observed_from_n1mm(self) -> None:
        self.emu.state.auto_information = 2
        self.assertEqual(self.emu.feed("AI0;"), [])
        self.assertEqual(self.emu.state.auto_information, 0)
        self.assertEqual(self.emu.feed("AI;"), ["AI0;"])

    def test_ag0_poll_observed_from_n1mm(self) -> None:
        self.assertEqual(self.emu.feed("AG0;"), ["AG0128;"])
        self.assertEqual(self.emu.feed("AG0255;"), [])
        self.assertEqual(self.emu.feed("AG0;"), ["AG0255;"])

    def test_if_contains_frequency_mode_and_rx_state(self) -> None:
        response = self.emu.feed("IF;")[0]
        self.assertTrue(response.startswith("IF00014074000"))
        self.assertTrue(response.endswith(";"))
        self.assertEqual(len(response), 38)
        # Fixed-position fields from the TS-2000 IF answer.
        self.assertEqual(response[29], "0")  # RX
        self.assertEqual(response[30], "2")  # USB
        self.assertEqual(response[31], "0")  # VFO A
        self.assertEqual(response[33], "0")  # split OFF

    def test_if_reflects_tx_and_split(self) -> None:
        self.emu.feed("FT1;TX;")
        response = self.emu.feed("IF;")[0]
        self.assertEqual(response[29], "1")
        self.assertEqual(response[33], "1")

    def test_n1mm_observed_poll_batch_has_no_unsupported_commands(self) -> None:
        responses = self.emu.feed("IF;FA;FB;AG0;")
        self.assertEqual(len(responses), 4)
        self.assertEqual(self.emu.unsupported_commands, [])

    def test_unknown_command_is_captured(self) -> None:
        self.assertEqual(self.emu.feed("ZZ;"), [])
        self.assertEqual(self.emu.unsupported_commands, ["ZZ"])


if __name__ == "__main__":
    unittest.main()
