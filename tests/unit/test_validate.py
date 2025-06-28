import io
import unittest

from flexeval import validate
from tests.unit import mixins


class TestValidate(mixins.DotenvMixin, unittest.TestCase):
    def test_load(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(validate)
        self.assertTrue(suite.countTestCases() > 0)

        test_stream = io.StringIO()
        result = unittest.TextTestRunner(stream=test_stream, verbosity=1).run(suite)
        # self.assertFalse(result.wasSuccessful())

        validation_output = test_stream.getvalue()
        self.assertTrue(len(validation_output) > 0)
