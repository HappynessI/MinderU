from pathlib import Path
import unittest

from minderu.xlsx_reader import read_first_sheet


class XlsxReaderTest(unittest.TestCase):
    def test_sample_xlsx_can_be_read(self):
        path = Path(__file__).resolve().parents[1] / "医疗赛题" / "相关样例" / "医疗文档问答示例 - MinerU.xlsx"
        rows = read_first_sheet(path)
        self.assertGreaterEqual(len(rows), 5)
        self.assertIn("输入", rows[0])
        self.assertIn("来源", rows[0])


if __name__ == "__main__":
    unittest.main()
