import dotenv


class DotenvMixin:
    def setUp(self):
        super().setUp()
        # TODO we could restore os.environ after running this
        dotenv.load_dotenv("tests/resources/unittest.env", override=True)

    def tearDown(self):
        super().tearDown()
