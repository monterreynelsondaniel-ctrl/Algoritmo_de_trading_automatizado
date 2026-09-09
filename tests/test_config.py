import unittest

from config import ConfigurationError, Settings


class SettingsTests(unittest.TestCase):
    def test_defaults_fail_closed(self):
        settings = Settings.from_env(env={}, env_file=None)
        self.assertEqual(settings.binance_env, "testnet")
        self.assertTrue(settings.dry_run)
        self.assertFalse(settings.trading_enabled)
        self.assertFalse(settings.can_send_orders())

    def test_live_ready_requires_live_environment_and_all_safety_conditions(self):
        settings = Settings.from_env(env={
            "BINANCE_ENV": "live",
            "BINANCE_LIVE_API_KEY": "key",
            "BINANCE_LIVE_API_SECRET": "secret",
            "TRADING_ENABLED": "true",
            "DRY_RUN": "false",
        }, env_file=None)
        self.assertTrue(settings.can_send_orders())
        self.assertTrue(settings.is_live_ready())

    def test_invalid_boolean_is_rejected(self):
        with self.assertRaises(ConfigurationError):
            Settings.from_env(env={"DRY_RUN": "maybe"}, env_file=None)

    def test_openai_key_is_excluded_from_settings_repr(self):
        secret = "sensitive-test-value"
        settings = Settings.from_env(env={"OPENAI_API_KEY": secret}, env_file=None)
        self.assertNotIn(secret, repr(settings))


if __name__ == "__main__":
    unittest.main()
