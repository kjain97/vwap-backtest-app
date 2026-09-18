from datetime import datetime, time
from typing import Dict, Any, Optional, Tuple, List

SCHEDULE_CONFIG = {
    0: {"symbol": "NIFTY",  "strike_step": 50,  "lot_size": 65, "otm_ce_offset":  100, "otm_pe_offset": -100},
    1: {"symbol": "NIFTY",  "strike_step": 50,  "lot_size": 65, "otm_ce_offset":  100, "otm_pe_offset": -100},
    2: {"symbol": "SENSEX", "strike_step": 100, "lot_size": 20, "otm_ce_offset":  200, "otm_pe_offset": -200},
    3: {"symbol": "SENSEX", "strike_step": 100, "lot_size": 20, "otm_ce_offset":  200, "otm_pe_offset": -200},
}
STOP_LOSS_PCT = 0.50


class VWAPStrangleStrategy:
    def __init__(self, sl_pct=STOP_LOSS_PCT, override_symbol=None):
        self.sl_pct = sl_pct
        self.override_symbol = override_symbol
        self.reset_day()

    def reset_day(self):
        self.current_date = None; self.config = None; self.symbol = None
        self.strike_step = 50; self.lot_size = 65
        self.ce_strike = None; self.pe_strike = None; self.strikes_locked = False
        self.cum_pv = 0.0; self.cum_vol = 0.0
        self.trade_type = None; self.bought_leg = None; self.bought_strike = None
        self.ce_ref_0930 = None; self.pe_ref_0930 = None; self.combined_ref_0930 = None
        self.below_vwap_streak = 0; self.above_reversal_streak = 0
        self.dip_below_vwap_occurred = False; self.price_before_drop = 0.0
        self.is_in_position = False; self.entered_today = False; self.entry_time = None
        self.entry_price = 0.0; self.sl_price = 0.0; self.trailing_sl_price = 0.0
        self.highest_price = 0.0; self.peak_gain_pct = 0.0
        self.price_at_130 = None; self.lowest_price = None; self.lowest_time = None
        self.max_drawdown = 0.0; self.eod_price = None
        self.realized_pnl = 0.0; self.points_booked = 0.0
        self.exit_reason = None; self.closed = False

    def get_schedule(self, dt):
        if self.override_symbol:
            s = self.override_symbol.upper()
            if s == "NIFTY": return SCHEDULE_CONFIG[0]
            if s == "SENSEX": return SCHEDULE_CONFIG[2]
        return SCHEDULE_CONFIG.get(dt.weekday())

    def select_strikes(self, spot, cfg):
        step = cfg["strike_step"]; atm = round(spot / step) * step
        return atm + cfg["otm_ce_offset"], atm + cfg["otm_pe_offset"]

    def process_bar(self, dt, spot, ce, pe, ce_vol=1.0, pe_vol=1.0):
        if self.current_date != dt.date():
            self.reset_day(); self.current_date = dt.date()
            self.config = self.get_schedule(dt)
            if not self.config: return {"action": "NO_TRADE_DAY"}
            self.symbol = self.config["symbol"]
            self.strike_step = self.config["strike_step"]
            self.lot_size = self.config["lot_size"]
        if not self.config: return {"action": "NO_TRADE_DAY"}
        ct = dt.time()
        if not self.strikes_locked:
            if ct >= time(9, 30):
                self.ce_strike, self.pe_strike = self.select_strikes(spot, self.config)
                self.strikes_locked = True
                self.ce_ref_0930 = ce; self.pe_ref_0930 = pe
                self.combined_ref_0930 = round(ce + pe, 2); self.price_before_drop = self.combined_ref_0930
                tv = max(ce_vol + pe_vol, 1.0)
                self.cum_pv += self.combined_ref_0930 * tv; self.cum_vol += tv
                vwap = round(self.cum_pv / self.cum_vol, 2)
                return {"action": "STRIKES_SELECTED", "time": dt.strftime("%H:%M"),
                        "symbol": self.symbol, "spot": spot,
                        "ce_strike": self.ce_strike, "pe_strike": self.pe_strike,
                        "combined_ref": self.combined_ref_0930, "vwap": vwap, "lot_size": self.lot_size}
            return {"action": "WAITING_0930", "time": dt.strftime("%H:%M")}

        cp = round(ce + pe, 2)
        tv = max(ce_vol + pe_vol, 1.0); self.cum_pv += cp * tv; self.cum_vol += tv
        vwap = round(self.cum_pv / self.cum_vol, 2)
        result = {"time": dt.strftime("%H:%M"), "combined_price": cp, "vwap": vwap, "action": "TRACKING"}

        if self.is_in_position and not self.closed:
            if self.trade_type == "SHORT_STRANGLE":
                if self.lowest_price is None or cp < self.lowest_price:
                    self.lowest_price = cp; self.lowest_time = dt.strftime("%H:%M")
                dd = max(0.0, round(cp - self.entry_price, 2))
                if dd > self.max_drawdown: self.max_drawdown = dd
                if cp >= self.sl_price:
                    self.is_in_position = False; self.closed = True; self.exit_reason = "SL_HIT_50_PCT"
                    self.points_booked = round(self.entry_price - cp, 2)
                    self.realized_pnl = round(self.points_booked * self.lot_size, 2)
                    result.update({"action": "EXIT_SL", "exit_price": cp,
                                   "points_booked": self.points_booked, "pnl": self.realized_pnl}); return result
                if ct >= time(13, 30):
                    self.is_in_position = False; self.closed = True; self.exit_reason = "TARGET_1330_SQUAREOFF"
                    self.price_at_130 = cp; self.points_booked = round(self.entry_price - cp, 2)
                    self.realized_pnl = round(self.points_booked * self.lot_size, 2)
                    result.update({"action": "EXIT_TARGET", "exit_price": cp,
                                   "points_booked": self.points_booked, "pnl": self.realized_pnl}); return result
            elif self.trade_type == "LONG_OPTION":
                cop = pe if self.bought_leg == "PE" else ce
                if cop > self.highest_price: self.highest_price = cop
                gp = ((cop - self.entry_price) / self.entry_price) * 100.0
                if gp > self.peak_gain_pct: self.peak_gain_pct = gp
                if self.peak_gain_pct >= 50.0:
                    s50 = int((self.peak_gain_pct - 50.0) / 10.0)
                    lp = 25.0 + s50 * 10.0; tsl = round(self.entry_price * (1.0 + lp / 100.0), 2)
                    if tsl > self.trailing_sl_price: self.trailing_sl_price = tsl
                if cop <= self.trailing_sl_price:
                    self.is_in_position = False; self.closed = True
                    iip = self.trailing_sl_price > self.entry_price
                    self.exit_reason = "TRAILING_SL_HIT" if iip else "SL_HIT_30_PCT"
                    self.points_booked = round(cop - self.entry_price, 2)
                    self.realized_pnl = round(self.points_booked * self.lot_size, 2)
                    result.update({"action": "EXIT_TRAILING_SL" if iip else "EXIT_SL",
                                   "exit_price": cop, "points_booked": self.points_booked,
                                   "pnl": self.realized_pnl}); return result
                if ct >= time(15, 25):
                    self.is_in_position = False; self.closed = True; self.exit_reason = "EOD_SESSION_CLOSE"
                    cop2 = pe if self.bought_leg == "PE" else ce
                    self.points_booked = round(cop2 - self.entry_price, 2)
                    self.realized_pnl = round(self.points_booked * self.lot_size, 2)
                    result.update({"action": "EXIT_TARGET", "exit_price": cop2,
                                   "points_booked": self.points_booked, "pnl": self.realized_pnl}); return result

        elif not self.entered_today and time(9, 30) <= ct < time(12, 0):
            if not self.dip_below_vwap_occurred: self.price_before_drop = max(self.price_before_drop, cp)
            if cp < vwap:
                self.below_vwap_streak += 1; self.above_reversal_streak = 0; self.dip_below_vwap_occurred = True
                if self.below_vwap_streak >= 2:
                    self.is_in_position = True; self.entered_today = True; self.trade_type = "SHORT_STRANGLE"
                    self.entry_time = dt.strftime("%H:%M"); self.entry_price = cp
                    self.sl_price = round(cp * (1.0 + self.sl_pct), 2)
                    self.lowest_price = cp; self.lowest_time = self.entry_time; self.max_drawdown = 0.0
                    result.update({"action": "ENTRY_SIGNAL", "entry_time": self.entry_time,
                                   "entry_price": self.entry_price, "sl_price": self.sl_price,
                                   "symbol": self.symbol, "ce_strike": self.ce_strike,
                                   "pe_strike": self.pe_strike, "lot_size": self.lot_size}); return result
            else:
                self.below_vwap_streak = 0
                if self.dip_below_vwap_occurred:
                    self.above_reversal_streak += 1
                    if self.above_reversal_streak >= 2 and cp > self.price_before_drop:
                        cec = (ce - self.ce_ref_0930) if self.ce_ref_0930 else 0.0
                        pec = (pe - self.pe_ref_0930) if self.pe_ref_0930 else 0.0
                        if pec >= cec: cl = "PE"; cs = self.pe_strike; bp = pe
                        else: cl = "CE"; cs = self.ce_strike; bp = ce
                        self.is_in_position = True; self.entered_today = True; self.trade_type = "LONG_OPTION"
                        self.bought_leg = cl; self.bought_strike = cs; self.entry_time = dt.strftime("%H:%M")
                        self.entry_price = bp; self.sl_price = round(bp * 0.70, 2)
                        self.trailing_sl_price = self.sl_price; self.highest_price = bp; self.peak_gain_pct = 0.0
                        result.update({"action": "ENTRY_BUY_OPTION", "bought_leg": cl, "bought_strike": cs,
                                       "entry_time": self.entry_time, "entry_price": bp, "sl_price": self.sl_price}); return result

        if ct >= time(15, 29): self.eod_price = cp
        return result

    def get_trade_record(self):
        if not self.entered_today: return None
        inst = ("BUY " + self.symbol + " " + str(self.bought_strike) + self.bought_leg
                if self.trade_type == "LONG_OPTION"
                else self.symbol + " " + str(self.ce_strike) + "CE/" + str(self.pe_strike) + "PE")
        return {"date": self.current_date.strftime("%d-%m-%Y") if self.current_date else "",
                "trade_type": self.trade_type, "instrument": inst,
                "entry_time": self.entry_time, "entry_price": self.entry_price,
                "sl_price": self.sl_price, "points_booked": self.points_booked,
                "max_drawdown": self.max_drawdown, "realized_pnl": self.realized_pnl,
                "status": self.exit_reason or ("OPEN" if self.is_in_position else "NO_EXIT")}


class BacktestRunner:
    def __init__(self): self.strategy = VWAPStrangleStrategy(); self.events = []
    def run(self, bars):
        self.strategy = VWAPStrangleStrategy(); self.events = []
        for bar in bars:
            dt, spot, ce, pe = bar
            self.events.append(self.strategy.process_bar(dt, spot, ce, pe))
        return {"events": self.events, "trade_record": self.strategy.get_trade_record()}


def sample_sept17_sensex_bars():
    d = datetime(2026, 9, 17)
    return [
        (d.replace(hour=9,  minute=30), 74300, 135.0, 135.0),
        (d.replace(hour=9,  minute=35), 74320, 136.0, 136.0),
        (d.replace(hour=9,  minute=40), 74330, 137.0, 137.0),
        (d.replace(hour=9,  minute=45), 74340, 137.0, 138.0),
        (d.replace(hour=9,  minute=50), 74350, 138.0, 138.0),
        (d.replace(hour=9,  minute=55), 74360, 139.0, 139.0),
        (d.replace(hour=10, minute=0),  74310, 141.0, 141.0),
        (d.replace(hour=10, minute=5),  74310, 143.0, 142.0),
        (d.replace(hour=10, minute=10), 74310, 141.0, 140.0),
        (d.replace(hour=10, minute=15), 74290, 133.0, 133.0),
        (d.replace(hour=10, minute=20), 74280, 132.0, 132.0),
        (d.replace(hour=13, minute=30), 74300,  87.0,  87.0),
        (d.replace(hour=15, minute=29), 74320,   0.05,  0.05),
    ]


def sample_sept15_nifty_bars():
    d = datetime(2026, 9, 15)
    return [
        (d.replace(hour=9,  minute=30), 23455, 52.45, 64.35),
        (d.replace(hour=9,  minute=35), 23440, 48.0,  60.0),
        (d.replace(hour=9,  minute=40), 23420, 45.0,  75.0),
        (d.replace(hour=9,  minute=45), 23400, 40.0,  85.0),
        (d.replace(hour=11, minute=45), 23300, 25.0, 130.0),
        (d.replace(hour=13, minute=30), 23250, 15.0, 155.0),
        (d.replace(hour=14, minute=20), 23180,  5.0, 220.0),
        (d.replace(hour=14, minute=45), 23200,  5.0, 185.0),
    ]


if __name__ == "__main__":
    r = BacktestRunner()
    res = r.run(sample_sept17_sensex_bars())
    rec = res["trade_record"]
    print("TEST1: 17-Sep SENSEX | Entry=" + str(rec["entry_time"]) + " Points=" + str(rec["points_booked"]) + " PnL=Rs" + str(rec["realized_pnl"]))
    assert rec["points_booked"] == 90.0 and rec["realized_pnl"] == 1800.0
    print("PASS")
    res2 = r.run(sample_sept15_nifty_bars())
    rec2 = res2["trade_record"]
    print("TEST2: 15-Sep NIFTY  | Entry=" + str(rec2["entry_time"]) + " Type=" + str(rec2["trade_type"]) + " Points=" + str(rec2["points_booked"]) + " PnL=Rs" + str(rec2["realized_pnl"]))
    assert rec2["trade_type"] == "LONG_OPTION" and rec2["points_booked"] > 0
    print("PASS")
    print("All engine tests passed.")