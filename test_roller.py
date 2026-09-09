import asyncio
import unittest
from unittest.mock import patch

import app


class TestPokemonRoller(unittest.TestCase):

    def test_roll_gender(self):
        # Genderless
        self.assertIsNone(app.roll_gender(-1))

        # 100% Male
        self.assertEqual(app.roll_gender(0), "M")

        # 100% Female
        self.assertEqual(app.roll_gender(8), "F")

        # 75% Female / 25% Male (gender_rate=6 -> d4, 1 is M, 2,3,4 are F)
        with patch("app.roll_dice", side_effect=[1]):
            self.assertEqual(app.roll_gender(6), "M")
        with patch("app.roll_dice", side_effect=[2]):
            self.assertEqual(app.roll_gender(6), "F")
        with patch("app.roll_dice", side_effect=[3]):
            self.assertEqual(app.roll_gender(6), "F")
        with patch("app.roll_dice", side_effect=[4]):
            self.assertEqual(app.roll_gender(6), "F")

        # 50% Female / 50% Male (gender_rate=4 -> d2, 1 is M, 2 is F)
        with patch("app.roll_dice", side_effect=[1]):
            self.assertEqual(app.roll_gender(4), "M")
        with patch("app.roll_dice", side_effect=[2]):
            self.assertEqual(app.roll_gender(4), "F")

        # 25% Female / 75% Male (gender_rate=2 -> d4, 1,2,3 are M, 4 is F)
        with patch("app.roll_dice", side_effect=[1]):
            self.assertEqual(app.roll_gender(2), "M")
        with patch("app.roll_dice", side_effect=[3]):
            self.assertEqual(app.roll_gender(2), "M")
        with patch("app.roll_dice", side_effect=[4]):
            self.assertEqual(app.roll_gender(2), "F")

        # 12.5% Female / 87.5% Male (gender_rate=1 -> d8, 1..7 are M, 8 is F)
        with patch("app.roll_dice", side_effect=[7]):
            self.assertEqual(app.roll_gender(1), "M")
        with patch("app.roll_dice", side_effect=[8]):
            self.assertEqual(app.roll_gender(1), "F")

    def test_roll_ivs(self):
        with patch("app.roll_dice", side_effect=[10, 20, 30, 5, 15, 25]):
            ivs = app.roll_ivs()
            self.assertEqual(ivs["HP"], 10)
            self.assertEqual(ivs["Atk"], 20)
            self.assertEqual(ivs["Def"], 30)
            self.assertEqual(ivs["SpA"], 5)
            self.assertEqual(ivs["SpD"], 15)
            self.assertEqual(ivs["Spe"], 25)

        # Ensure random rolls are within [1, 31]
        for _ in range(100):
            ivs = app.roll_ivs()
            for stat, val in ivs.items():
                self.assertTrue(1 <= val <= 31, f"{stat} value {val} out of bounds")

    def test_roll_nature(self):
        # First roll = lowered, Second roll = raised
        # Lowered 1 (Atk), Raised 5 (Spe) -> Timid
        with patch("app.roll_dice", side_effect=[1, 5]):
            self.assertEqual(app.roll_nature(), "Timid")

        # Lowered 3 (SpA), Raised 1 (Atk) -> Adamant
        with patch("app.roll_dice", side_effect=[3, 1]):
            self.assertEqual(app.roll_nature(), "Adamant")

        # Lowered 3 (SpA), Raised 5 (Spe) -> Jolly
        with patch("app.roll_dice", side_effect=[3, 5]):
            self.assertEqual(app.roll_nature(), "Jolly")

        # Lowered 1 (Atk), Raised 3 (SpA) -> Modest
        with patch("app.roll_dice", side_effect=[1, 3]):
            self.assertEqual(app.roll_nature(), "Modest")

        # Lowered 1, Raised 1 -> Hardy
        with patch("app.roll_dice", side_effect=[1, 1]):
            self.assertEqual(app.roll_nature(), "Hardy")

        # Lowered 5, Raised 5 -> Serious
        with patch("app.roll_dice", side_effect=[5, 5]):
            self.assertEqual(app.roll_nature(), "Serious")

        # Verify all 25 combinations exist
        self.assertEqual(len(app.NATURE_MATRIX), 25)

    def test_roll_ability(self):
        abilities_3 = [
            {"ability": {"name": "keen-eye"}, "is_hidden": False, "slot": 1},
            {"ability": {"name": "tangled-feet"}, "is_hidden": False, "slot": 2},
            {"ability": {"name": "big-pecks"}, "is_hidden": True, "slot": 3},
        ]
        # Rolls 1-5: first option (keen-eye)
        for r in range(1, 6):
            with patch("app.roll_dice", return_value=r):
                chosen = app.roll_ability(abilities_3)
                self.assertEqual(chosen["ability"]["name"], "keen-eye")

        # Rolls 6-9: second option (tangled-feet)
        for r in range(6, 10):
            with patch("app.roll_dice", return_value=r):
                chosen = app.roll_ability(abilities_3)
                self.assertEqual(chosen["ability"]["name"], "tangled-feet")

        # Roll 10: hidden ability replaces 10 (big-pecks)
        with patch("app.roll_dice", return_value=10):
            chosen = app.roll_ability(abilities_3)
            self.assertEqual(chosen["ability"]["name"], "big-pecks")

        # 2 regular abilities, no hidden:
        abilities_2_no_hidden = [
            {"ability": {"name": "levitate"}, "is_hidden": False, "slot": 1},
            {"ability": {"name": "neutralizing-gas"}, "is_hidden": False, "slot": 2},
        ]
        with patch("app.roll_dice", return_value=10):
            chosen = app.roll_ability(abilities_2_no_hidden)
            self.assertEqual(chosen["ability"]["name"], "neutralizing-gas")

        # 1 regular ability, 1 hidden:
        abilities_1_hidden = [
            {"ability": {"name": "static"}, "is_hidden": False, "slot": 1},
            {"ability": {"name": "lightning-rod"}, "is_hidden": True, "slot": 3},
        ]
        with patch("app.roll_dice", return_value=7):
            chosen = app.roll_ability(abilities_1_hidden)
            self.assertEqual(chosen["ability"]["name"], "static")
        with patch("app.roll_dice", return_value=10):
            chosen = app.roll_ability(abilities_1_hidden)
            self.assertEqual(chosen["ability"]["name"], "lightning-rod")

        # 1 regular ability only
        abilities_1 = [
            {"ability": {"name": "forecast"}, "is_hidden": False, "slot": 1},
        ]
        chosen = app.roll_ability(abilities_1)
        self.assertEqual(chosen["ability"]["name"], "forecast")

    def test_roll_shiny(self):
        with patch("app.roll_dice", return_value=1):
            self.assertTrue(app.roll_shiny())
        with patch("app.roll_dice", return_value=2):
            self.assertFalse(app.roll_shiny())
        with patch("app.roll_dice", return_value=8192):
            self.assertFalse(app.roll_shiny())

    def test_format_showdown(self):
        ivs = {"HP": 31, "Atk": 15, "Def": 28, "SpA": 31, "SpD": 10, "Spe": 25}
        # Non-shiny with gender
        result = app.format_showdown("Pikachu", "M", "Static", False, ivs, "Jolly")
        expected = (
            "Pikachu (M)\n"
            "Ability: Static\n"
            "IVs: 31 HP / 15 Atk / 28 Def / 31 SpA / 10 SpD / 25 Spe\n"
            "Jolly Nature"
        )
        self.assertEqual(result, expected)

        # Shiny genderless
        result_shiny = app.format_showdown("Magnemite", None, "Sturdy", True, ivs, "Modest")
        expected_shiny = (
            "Magnemite\n"
            "Ability: Sturdy\n"
            "Shiny: Yes\n"
            "IVs: 31 HP / 15 Atk / 28 Def / 31 SpA / 10 SpD / 25 Spe\n"
            "Modest Nature"
        )
        self.assertEqual(result_shiny, expected_shiny)

    def test_normalize_pokemon_name(self):
        self.assertEqual(app.normalize_pokemon_name("Pikachu"), "pikachu")
        self.assertEqual(app.normalize_pokemon_name("  Tapu Koko  "), "tapu-koko")
        self.assertEqual(app.normalize_pokemon_name("Mr. Mime"), "mr-mime")
        self.assertEqual(app.normalize_pokemon_name("Farfetch'd"), "farfetchd")
        self.assertEqual(app.normalize_pokemon_name("Type: Null"), "type-null")
        self.assertEqual(app.normalize_pokemon_name("Nidoran Male"), "nidoran-m")
        self.assertEqual(app.normalize_pokemon_name("Nidoran (F)"), "nidoran-f")
        self.assertEqual(app.normalize_pokemon_name("Flabébé"), "flabebe")
        self.assertEqual(app.normalize_pokemon_name("Rotom-Wash"), "rotom-wash")

    def test_live_roll_pokemon(self):
        async def run_async_tests():
            # Test valid Pokémon roll
            res = await app.roll_pokemon("pikachu")
            self.assertIn("Pikachu", res)
            self.assertIn("Ability:", res)
            self.assertIn("IVs:", res)
            self.assertIn("Nature", res)

            # Test genderless
            res_mag = await app.roll_pokemon("magnemite")
            self.assertIn("Magnemite\n", res_mag)

            # Test 100% female
            res_chansey = await app.roll_pokemon("chansey")
            self.assertIn("Chansey (F)", res_chansey)

            # Test 100% male
            res_tauros = await app.roll_pokemon("tauros")
            self.assertIn("Tauros (M)", res_tauros)

            # Test form
            res_rotom = await app.roll_pokemon("rotom-wash")
            self.assertIn("Rotom-Wash", res_rotom)

            # Test invalid pokemon raises PokemonNotFoundError
            with self.assertRaises(app.PokemonNotFoundError):
                await app.roll_pokemon("invalid-nonexistent-pokemon-xyz")

        asyncio.run(run_async_tests())


if __name__ == "__main__":
    unittest.main()
