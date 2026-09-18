"""
main.py  -  VWAP Backtest Engine  (Kivy Android App)
Dark-mode trading dashboard. Runs backtests in background thread,
streams events to the UI live, saves trade logs to /sdcard/trading_logs/.
"""
import os, json, threading
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from strategy_engine import BacktestRunner, sample_sept17_sensex_bars, sample_sept15_nifty_bars

# ── colours ──────────────────────────────────────────────────────
BG     = (0.10, 0.10, 0.18, 1)
CARD   = (0.09, 0.13, 0.24, 1)
ACCENT = (0.06, 0.20, 0.38, 1)
POS    = (0.00, 1.00, 0.53, 1)
NEG    = (1.00, 0.27, 0.27, 1)
WARN   = (1.00, 0.76, 0.03, 1)
GRAY   = (0.75, 0.75, 0.75, 1)
WHITE  = (1.00, 1.00, 1.00, 1)

ACTION_COLOR = {
    "STRIKES_SELECTED": WARN,
    "ENTRY_SIGNAL":     POS,
    "ENTRY_BUY_OPTION": POS,
    "EXIT_TARGET":      (0.20, 0.60, 1.00, 1),
    "EXIT_TRAILING_SL": (0.20, 0.60, 1.00, 1),
    "EXIT_SL":          NEG,
    "TRACKING":         GRAY,
    "WAITING_0930":     GRAY,
    "NO_TRADE_DAY":     GRAY,
}

SAMPLES = {
    "17-Sep SENSEX (+90 pts)": sample_sept17_sensex_bars,
    "15-Sep NIFTY  (Long PE)": sample_sept15_nifty_bars,
}


def bg(widget, color):
    with widget.canvas.before:
        Color(*color)
        rect = Rectangle(size=widget.size, pos=widget.pos)
    widget.bind(size=lambda *a: setattr(rect, "size", widget.size),
                pos=lambda *a: setattr(rect, "pos", widget.pos))


class EventRow(BoxLayout):
    def __init__(self, evt, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, height=28, **kw)
        action = evt.get("action", "?")
        t      = evt.get("time", "--:--")
        cp     = evt.get("combined_price", "")
        vwap   = evt.get("vwap", "")
        ep     = evt.get("entry_price", "")
        pts    = evt.get("points_booked", "")
        pnl    = evt.get("pnl", "")

        if action == "STRIKES_SELECTED":
            detail = f"CE={evt.get('ce_strike')}  PE={evt.get('pe_strike')}  Ref={evt.get('combined_ref')}"
        elif action in ("ENTRY_SIGNAL", "ENTRY_BUY_OPTION"):
            detail = f"Entry={ep}  SL={evt.get('sl_price')}  Lot={evt.get('lot_size')}"
        elif action in ("EXIT_TARGET", "EXIT_SL", "EXIT_TRAILING_SL"):
            detail = f"Exit={evt.get('exit_price')}  Pts={pts}  PnL=Rs{pnl}"
        elif cp:
            detail = f"Combined={cp}  VWAP={vwap}"
        else:
            detail = evt.get("message", "")

        col = ACTION_COLOR.get(action, GRAY)
        self.add_widget(Label(text=t,      size_hint_x=0.12, color=GRAY,  font_size=11))
        self.add_widget(Label(text=action, size_hint_x=0.30, color=col,   font_size=11, bold=True))
        self.add_widget(Label(text=detail, size_hint_x=0.58, color=WHITE, font_size=11, halign="left",
                               text_size=(None, None)))


class VWAPApp(App):
    def build(self):
        Window.clearcolor = BG
        self.runner       = BacktestRunner()
        self.running      = False
        self.sample_index = 0
        self.sample_keys  = list(SAMPLES.keys())

        root = BoxLayout(orientation="vertical", spacing=4, padding=8)
        bg(root, BG)

        # ── Header ─────────────────────────────────────────
        hdr = BoxLayout(size_hint_y=None, height=42, padding=[6, 0])
        bg(hdr, ACCENT)
        hdr.add_widget(Label(text="VWAP Backtest Engine", font_size=17, bold=True, color=WHITE,
                             halign="left", size_hint_x=0.6))
        self.lbl_clock = Label(text="", font_size=12, color=GRAY, halign="right", size_hint_x=0.4)
        hdr.add_widget(self.lbl_clock)
        root.add_widget(hdr)

        # ── Status card ────────────────────────────────────
        status = GridLayout(cols=3, size_hint_y=None, height=64, spacing=4, padding=4)
        bg(status, CARD)
        self.lbl_symbol = self._stat_label("--")
        self.lbl_mode   = self._stat_label("IDLE")
        self.lbl_pnl    = self._stat_label("PnL: --")
        for w in (self.lbl_symbol, self.lbl_mode, self.lbl_pnl): status.add_widget(w)
        root.add_widget(status)

        # ── Dataset selector ───────────────────────────────
        self.lbl_dataset = Label(text="Dataset: " + self.sample_keys[0],
                                 size_hint_y=None, height=28, color=WARN, font_size=12)
        root.add_widget(self.lbl_dataset)

        # ── Event log scroll ───────────────────────────────
        scroll = ScrollView(do_scroll_x=False)
        self.log_grid = GridLayout(cols=1, spacing=2, size_hint_y=None)
        self.log_grid.bind(minimum_height=self.log_grid.setter("height"))
        scroll.add_widget(self.log_grid)
        root.add_widget(scroll)

        # ── Trade result card ──────────────────────────────
        self.result_card = Label(text="", size_hint_y=None, height=54,
                                 font_size=12, color=WHITE, halign="center",
                                 text_size=(Window.width - 16, None))
        bg_box = BoxLayout(size_hint_y=None, height=58)
        bg(bg_box, CARD)
        bg_box.add_widget(self.result_card)
        root.add_widget(bg_box)

        # ── Buttons ────────────────────────────────────────
        btn_row = BoxLayout(size_hint_y=None, height=50, spacing=6)
        b_run   = self._btn("▶  RUN",      (0.05, 0.55, 0.20, 1), self.on_run)
        b_stop  = self._btn("⏹  STOP",     (0.55, 0.12, 0.12, 1), self.on_stop)
        b_next  = self._btn("⇄  DATASET",  ACCENT,                 self.on_next_dataset)
        b_logs  = self._btn("📋  LOGS",    (0.20, 0.20, 0.35, 1), self.on_show_logs)
        for b in (b_run, b_stop, b_next, b_logs): btn_row.add_widget(b)
        root.add_widget(btn_row)

        Clock.schedule_interval(self.tick_clock, 1)
        return root

    # ── helpers ────────────────────────────────────────────
    def _stat_label(self, txt):
        l = Label(text=txt, font_size=13, color=WHITE, bold=True,
                  halign="center", valign="middle")
        return l

    def _btn(self, txt, col, cb):
        b = Button(text=txt, background_color=col, color=WHITE, font_size=12, bold=True)
        b.bind(on_press=cb)
        return b

    def tick_clock(self, dt):
        self.lbl_clock.text = datetime.now().strftime("%d-%b %H:%M:%S")

    # ── Button handlers ────────────────────────────────────
    def on_run(self, *_):
        if self.running: return
        self.running = True
        self.log_grid.clear_widgets()
        self.result_card.text = ""
        self.lbl_mode.text = "RUNNING"
        self.lbl_mode.color = WARN
        key = self.sample_keys[self.sample_index]
        bars_fn = SAMPLES[key]
        threading.Thread(target=self._run_backtest, args=(bars_fn,), daemon=True).start()

    def on_stop(self, *_):
        self.running = False
        self.update_mode("STOPPED", NEG)

    def on_next_dataset(self, *_):
        if self.running: return
        self.sample_index = (self.sample_index + 1) % len(self.sample_keys)
        key = self.sample_keys[self.sample_index]
        self.lbl_dataset.text = "Dataset: " + key
        self.log_grid.clear_widgets()
        self.result_card.text = ""
        self.lbl_pnl.text = "PnL: --"
        self.lbl_symbol.text = "--"

    def on_show_logs(self, *_):
        log_dir = self._log_dir()
        files   = sorted(os.listdir(log_dir)) if os.path.isdir(log_dir) else []
        self.log_grid.clear_widgets()
        self.log_grid.add_widget(
            Label(text="Trade Logs in " + log_dir, size_hint_y=None, height=28,
                  color=WARN, font_size=12))
        if not files:
            self.log_grid.add_widget(
                Label(text="No logs yet. Run a backtest first.", size_hint_y=None, height=28,
                      color=GRAY, font_size=12))
        else:
            for f in files[-20:]:
                self.log_grid.add_widget(
                    Label(text="  " + f, size_hint_y=None, height=24, color=WHITE, font_size=11,
                          halign="left"))

    # ── background runner ──────────────────────────────────
    def _run_backtest(self, bars_fn):
        bars   = bars_fn()
        result = self.runner.run(bars)
        for evt in result["events"]:
            if not self.running: break
            self.append_event(evt)
        self.running = False
        rec = result.get("trade_record")
        if rec:
            self.finish_run(rec)
            self._save_log(rec, result["events"])

    @mainthread
    def append_event(self, evt):
        self.log_grid.add_widget(EventRow(evt))
        action = evt.get("action", "")
        sym    = evt.get("symbol", self.lbl_symbol.text)
        if sym and sym != "--": self.lbl_symbol.text = sym
        if action == "TRACKING":
            self.lbl_mode.text  = "TRACKING"
            self.lbl_mode.color = GRAY
        elif action in ("ENTRY_SIGNAL", "ENTRY_BUY_OPTION"):
            self.lbl_mode.text  = action.replace("_", " ")
            self.lbl_mode.color = POS
        elif action in ("EXIT_TARGET", "EXIT_TRAILING_SL"):
            self.lbl_mode.text  = "EXITED ✅"
            self.lbl_mode.color = (0.2, 0.6, 1, 1)
        elif action == "EXIT_SL":
            self.lbl_mode.text  = "SL HIT ❌"
            self.lbl_mode.color = NEG

    @mainthread
    def finish_run(self, rec):
        pts = rec.get("points_booked", 0)
        pnl = rec.get("realized_pnl", 0)
        col = POS if pnl >= 0 else NEG
        self.lbl_pnl.text  = ("PnL: +" if pnl >= 0 else "PnL: ") + "Rs" + str(pnl)
        self.lbl_pnl.color = col
        status_str = ("PROFIT ✅" if pnl >= 0 else "LOSS ❌")
        self.result_card.text = (
            rec.get("trade_type", "") + "  |  " +
            "Entry " + str(rec.get("entry_time")) + "  @  " + str(rec.get("entry_price")) +
            "\nPoints: " + str(pts) + "  |  PnL: Rs" + str(pnl) + "  |  " + status_str)
        self.result_card.color = col
        self.lbl_mode.text  = status_str
        self.lbl_mode.color = col

    @mainthread
    def update_mode(self, txt, col):
        self.lbl_mode.text  = txt
        self.lbl_mode.color = col

    # ── log saving ─────────────────────────────────────────
    def _log_dir(self):
        if os.path.isdir("/sdcard"):
            d = "/sdcard/trading_logs"
        else:
            d = os.path.join(os.path.expanduser("~"), "trading_logs")
        os.makedirs(d, exist_ok=True)
        return d

    def _save_log(self, rec, events):
        log_dir  = self._log_dir()
        fname    = datetime.now().strftime("%Y-%m-%d") + ".json"
        fpath    = os.path.join(log_dir, fname)
        payload  = {"trade_record": rec, "events": events, "saved_at": datetime.now().isoformat()}
        with open(fpath, "w") as f:
            json.dump(payload, f, indent=2, default=str)
        print("Log saved: " + fpath)


if __name__ == "__main__":
    VWAPApp().run()