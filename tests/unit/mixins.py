import pathlib
import tempfile
import unittest.mock

import dotenv


class TempPathMixin:
    def setUp(self):
        super().setUp()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = pathlib.Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()
        super().tearDown()


class DotenvMixin:
    def setUp(self):
        super().setUp()
        # TODO we could restore os.environ after running this
        dotenv.load_dotenv("tests/resources/unittest.env", override=True)

    def tearDown(self):
        super().tearDown()


class PatchOpenAIMixin:
    def setUp(self):
        super().setUp()
        patcher = unittest.mock.patch("")
        self.mock_create = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        super().tearDown()
