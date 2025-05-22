import unittest
from pathlib import Path

from flexeval.io.parsers import yaml_parser


class TestYamlParser(unittest.TestCase):
    def test_load_config_from_yaml(self):
        config_path = "tests/resources/test_config.yaml"
        config = yaml_parser.load_config_from_yaml(config_path)
        self.assertEqual(config.database_path, Path(".unittest/unittest.db"))

    def test_load_evals_from_yaml(self):
        evals_path = "tests/resources/test_evals.yaml"
        evals = yaml_parser.load_evals_from_yaml(evals_path)
        self.assertTrue("length_test" in evals)
