import tempfile
import unittest
from pathlib import Path

from flexeval import db_utils
from flexeval.classes import eval_set_run


class TestDbUtils(unittest.TestCase):
    def test_initialize_database(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            for filename in ["tmp1.db", "tmp2.db"]:
                db_utils.initialize_database(str(tmp_dir / filename))
                esr = eval_set_run.EvalSetRun.create(
                    dataset_files="",
                    metrics="",
                    metrics_graph_ordered_list="",
                    do_completion=False,
                )
                self.assertEqual(esr.id, 1)
                self.assertEqual(esr, eval_set_run.EvalSetRun.get())

    def test_bind_to_database(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir = Path(tmp_dir)
            db_utils.initialize_database(str(tmp_dir / "tmp1.db"))
            # TODO implement me
            # for filename in ["tmp2.db", "tmp3.db"]:
            #    db = db_utils.bind_to_database(str(tmp_dir / filename))
