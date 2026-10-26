import unittest
from unittest.mock import patch
from datetime import date
from valuation_monitor.config import load_config
from valuation_monitor.price_sources import PRICES, _yahoo_daily, fetch_daily


class Nasdaq100Tests(unittest.TestCase):
    def test_watchlist_source_and_index_identity(self):
        _, instruments = load_config("watchlist.yaml")
        entry=next(i for i in instruments if i.id=="nasdaq100")
        self.assertEqual(entry.market,"us")
        self.assertEqual(entry.code,"NDX")
        self.assertEqual(entry.source["type"],"danjuan")
        self.assertEqual(entry.source["index_code"],"NDX")
        self.assertEqual(PRICES["nasdaq100"][2],"^NDX")

    @patch("valuation_monitor.price_sources.requests.get")
    def test_yahoo_query_not_hardcoded_to_sp500(self, mock_get):
        payload={"chart":{"result":[{"timestamp":[1792800000],
                 "indicators":{"quote":[{"close":[28957.53]}]}}]}}
        mock_get.return_value.json.return_value=payload
        mock_get.return_value.raise_for_status.return_value=None
        frame=_yahoo_daily("^NDX",date(2026,10,1),date(2026,10,26))
        self.assertAlmostEqual(frame.iloc[0]["close"],28957.53)
        self.assertIn("%5ENDX",mock_get.call_args.args[0])
        self.assertNotIn("%5EGSPC",mock_get.call_args.args[0])

    def test_reject_wrong_ticker(self):
        with self.assertRaises(ValueError):
            _yahoo_daily("^IXIC",date(2026,10,1),date(2026,10,26))


if __name__=="__main__":
    unittest.main()
