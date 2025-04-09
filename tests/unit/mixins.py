import dotenv
import unittest.mock


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
