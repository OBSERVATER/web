from datetime import date
from unittest import TestCase
from unittest.mock import Mock

from valuation_monitor.models import Instrument, MetricSpec
from valuation_monitor.public_sources import PublicDataClient


class PublicHistoryTests(TestCase):
    def test_public_html_table_parses_only_dated_metric_values(self):
        client = PublicDataClient()
        html = """
          <table>
            <thead><tr><th>日期</th><th>收盘点位</th><th>股息率</th></tr></thead>
            <tbody>
              <tr><td>2026-09-18</td><td>5,461.76</td><td>4.27%</td></tr>
              <tr><td>2026-09-11</td><td>5,580.28</td><td>4.35%</td></tr>
              <tr><td>2026-09-04</td><td>5,648.28</td><td>4.29%</td></tr>
              <tr><td>not a date</td><td>1</td><td>9.99%</td></tr>
            </tbody>
          </table>"""
        client.session.get = Mock(return_value=Mock(text=html, raise_for_status=Mock()))
        instrument = Instrument(
            "csi_dividend", "中证红利", "cn", "000922",
            (MetricSpec("dyr"),),
            {"type": "public_html_table", "url": "https://example.org/history", "weighting": "mcw-external"},
        )
        rows = client.fetch_range(instrument, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[-1].day, date(2026, 9, 18))
        self.assertAlmostEqual(rows[-1].value, 4.27)
        self.assertEqual(rows[-1].weighting, "mcw-external")

    def test_chain_fills_missing_weeks_but_preserves_primary_week(self):
        client = PublicDataClient()
        primary_html = """<table><tr><th>日期</th><th>股息率</th></tr>
            <tr><td>2026-09-18</td><td>4.28%</td></tr></table>"""
        secondary_html = """<table><tr><th>日期</th><th>股息率</th></tr>
            <tr><td>2026-09-17</td><td>4.27%</td></tr>
            <tr><td>2026-09-11</td><td>4.35%</td></tr></table>"""
        def get(url, **kwargs):
            return Mock(text=primary_html if "official" in url else secondary_html, raise_for_status=Mock())
        client.session.get = Mock(side_effect=get)
        instrument = Instrument(
            "csi_dividend", "中证红利", "cn", "000922", (MetricSpec("dyr"),),
            {"type": "chain", "sources": [
                {"type": "public_html_table", "url": "https://example.org/official", "weighting": "aggregate"},
                {"type": "public_html_table", "url": "https://example.org/secondary", "weighting": "mcw-external"},
            ]},
        )
        rows = client.fetch_range(instrument, date(2026, 9, 1), date(2026, 9, 30))
        self.assertEqual(len(rows), 2)
        self.assertAlmostEqual(rows[-1].value, 4.28)
        self.assertAlmostEqual(rows[0].value, 4.35)
