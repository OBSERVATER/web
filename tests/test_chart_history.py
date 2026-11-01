import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch
from PIL import ImageFont
from scripts import render_report_image as charts
from valuation_monitor.config import load_config
from valuation_monitor.app import source_specs
from valuation_monitor.public_sources import PublicDataClient, PublicSourceError
from valuation_monitor.price_sources import PRICES


class ChartHistoryTests(unittest.TestCase):
    def test_csv_provenance_survives_renderer_filter_and_ten_year_cutoff(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'history.csv'
            with path.open('w', newline='') as handle:
                writer = csv.DictWriter(handle, fieldnames=['day', 'instrument_id', 'metric', 'value', 'source', 'weighting'])
                writer.writeheader()
                for day, source, weight in [('2026-10-23', 'danjuan-public-history', 'aggregate'),
                                             ('2026-10-30', 'danjuan-public', 'aggregate'),
                                             ('2015-10-30', 'danjuan-public', 'aggregate'),
                                             ('2026-10-30', 'other', 'aggregate'),
                                             ('2026-10-30', 'danjuan-public', 'other')]:
                    writer.writerow(dict(day=day, instrument_id='x', metric='pe_ttm', value=20,
                                         source=source, weighting=weight))
            rows = charts.load_history(path)
            item = dict(current=20, series_family='danjuan', weighting='aggregate')
            font = ImageFont.load_default()
            fonts = {key: font for key in ['head', 'head_code', 'metric_title', 'label', 'value', 'axis', 'legend', 'small', 'empty']}
            with patch.object(charts, 'draw_chart') as draw:
                charts.render_one(Path(folder) / 'chart.png', '2026-10-31',
                                  dict(id='x', name='X', code='X', metrics={'pe_ttm': {}}), item, rows, fonts)
            plotted = draw.call_args.args[3]
            self.assertEqual([r['day'] for r in plotted], [date(2026, 10, 23), date(2026, 10, 30)])

    def test_short_real_history_draws_curve(self):
        from PIL import Image, ImageDraw
        image = Image.new('RGB', (600, 400))
        draw = ImageDraw.Draw(image)
        fonts = {key: ImageFont.load_default() for key in ['axis', 'empty', 'label']}
        rows = [dict(day=date(2026, 10, 1) + timedelta(days=7*i), value=10+i) for i in range(5)]
        with patch.object(charts, 'txt') as text:
            charts.draw_chart(draw, (80, 20, 500, 300), 'pe_ttm', rows, None, fonts)
        self.assertFalse(any('暂不绘制' in str(c) for c in text.call_args_list))
        self.assertTrue(any(pixel == (127, 199, 210) for pixel in image.getdata()))

    def test_lowvol_identity_and_lowercase_provider_code(self):
        _, instruments = load_config('watchlist.yaml')
        ins = next(i for i in instruments if i.id == 'csi_dividend_lowvol')
        self.assertEqual(ins.code, 'H30269')
        self.assertTrue(ins.metrics[0].higher_is_cheaper)
        self.assertEqual(PRICES[ins.id][2], ins.code)
        src = next(s for s in source_specs(ins) if s.source['type'] == 'guzhibiao')
        payload = dict(code='h30269', indicator='dividend', dates=['2026-10-30'], values=[4.3])
        client = PublicDataClient()
        with patch.object(client, '_get_json', return_value=payload):
            rows = client.fetch_latest(src, end=date(2026, 10, 31))
        self.assertEqual(rows[0].value, 4.3)
        payload['code'] = '930955'
        with patch.object(client, '_get_json', return_value=payload):
            with self.assertRaises(PublicSourceError):
                client.fetch_latest(src, end=date(2026, 10, 31))
