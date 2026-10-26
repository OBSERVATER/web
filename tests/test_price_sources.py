import unittest
from datetime import date
import pandas as pd
from valuation_monitor.price_sources import normalized_dates, PRICES


class PriceSourceTests(unittest.TestCase):
    def test_no_nyse_weekend_as_close(self):
        frame = pd.DataFrame({"日期":["2026-10-22","2026-10-23","2026-10-24"],
                              "close":[7000,6900,6850]})
        results=normalized_dates(frame,"日期","close","us",date(2026,10,22),date(2026,10,24))
        self.assertEqual(set(results),{date(2026,10,22),date(2026,10,23)})

    def test_china_holiday_excluded(self):
        frame=pd.DataFrame({"日期":["2026-09-30","2026-10-01","2026-10-09"],
                            "close":[1000,990,970]})
        results=normalized_dates(frame,"日期","close","cn",date(2026,9,30),date(2026,10,9))
        self.assertNotIn(date(2026,10,1),results)
        self.assertEqual(results[date(2026,10,9)],970)

    def test_duplicate_date_conflict(self):
        frame=pd.DataFrame({"日期":["2026-10-23","2026-10-23"],
                            "close":[4300,4200]})
        with self.assertRaises(ValueError):
            normalized_dates(frame,"日期","close","cn",date(2026,10,23),date(2026,10,23))

    def test_identity_and_base(self):
        self.assertEqual(PRICES["value100"][2],"980081")
        self.assertEqual(PRICES["csi_dividend"][2],"000922")
        self.assertEqual(PRICES["csi300"][2],"000300")
        self.assertEqual(PRICES["sp500"][2],"^GSPC")


if __name__=="__main__":
    unittest.main()
