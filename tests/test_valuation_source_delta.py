import unittest

from scripts.build_issue_comment import instrument_section


class SourceDivergenceTests(unittest.TestCase):
    def test_dividend_source_spread_explicit_but_not_mixed(self):
        item={"name":"中证红利","metric":"dyr","current":4.51,"zone":"偏高",
              "rating_percentile":0.4334637964774951,
              "reference_current":4.31,
              "reference_source":"csindex-official-public",
              "reference_date":"2026-10-23","source":"guzhibiao-public-funddb-history",
              "source_date":"2026-10-23"}
        rendered="\n".join(instrument_section(item,{"status":"暂无新收盘"}))
        self.assertIn("当前估值：股息率 4.51%",rendered)
        self.assertIn("异源差异：+0.20个百分点",rendered)
        self.assertIn("历史分位：43.35%",rendered)
        self.assertIn("不混合计算",rendered)

    def test_pe_source_spread_with_unit(self):
        item={"name":"沪深300","metric":"pe_ttm","current":12.81,"zone":"偏高",
              "reference_current":15.44,"source_date":"2026-10-23"}
        rendered="\n".join(instrument_section(item,{}))
        self.assertIn("异源差异：-2.63（估值单位）",rendered)


if __name__=="__main__":
    unittest.main()
