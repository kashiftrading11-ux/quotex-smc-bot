# ============================================
# 🤖 QUOTEX SMC SMART BRAIN BOT (24/7 CLOUD READY)
# Strategy: SMC (Order Block + FVG + BOS)
# Timeframe: 5 Min | Timing: Exact T-15 Seconds
# ============================================

import os
import logging
import asyncio
import threading
from flask import Flask
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler,
    CallbackQueryHandler, ContextTypes
)

# ================= CLOUD SERVER (RENDER) =================
app_web = Flask('')

@app_web.route('/')
def home():
    return "🤖 Quotex SMC Bot Status: 24/7 ONLINE & ACTIVE!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host='0.0.0.0', port=port)

# ================= CONFIGURATION =================
# ⚠️ APNA TELEGRAM BOT TOKEN YAHAN DAL EIN (Quotes ke andar)
BOT_TOKEN = "9256890403:AAGXm_3iv6rJWBncE4enQye9AZ8-MyIa1UI"

PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "EUR/JPY": "EURJPY=X",
    "EUR/GBP": "EURGBP=X",
    "USD/CAD": "USDCAD=X",
}

MARTINGALE_AMOUNTS = [1, 2.5, 6]  # 3 Levels
MAX_LOSSES = 3

# ================= USER STATE =================
user_states = {}

def get_user_state(user_id):
    if user_id not in user_states:
        user_states[user_id] = {
            "selected_pair": None,
            "loss_count": {p: 0 for p in PAIRS},
            "last_signal": None,
        }
    return user_states[user_id]

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ================= DATA FETCH =================
def fetch_data_5m(ticker):
    """Yahoo Finance se 5 min market data layein"""
    try:
        df = yf.download(
            ticker, period="5d", interval="5m",
            progress=False, auto_adjust=True
        )
        if df is None or df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        logger.error(f"Data fetch error: {e}")
        return None

# ================= SMC BRAIN ENGINE =================
def analyze_smc(df):
    """
    SMC Core Engine:
    1. Structure Break (BOS / CHoCH)
    2. Fair Value Gap (FVG)
    3. Order Block (OB)
    4. Liquidity Sweeps
    """
    if len(df) < 30:
        return None

    df = df.tail(30).copy()
    close = df["Close"].values
    high = df["High"].values
    low = df["Low"].values
    open_p = df["Open"].values

    buy_score = 0
    sell_score = 0
    smc_reasons = []

    recent_high = np.max(high[-15:-3])
    recent_low = np.min(low[-15:-3])

    # 1. Market Structure Break (BOS)
    if close[-1] > recent_high:
        buy_score += 2
        smc_reasons.append("⚡ Bullish BOS (Structure Break UP)")
    elif close[-1] < recent_low:
        sell_score += 2
        smc_reasons.append("⚡ Bearish BOS (Structure Break DOWN)")

    # 2. Fair Value Gap (FVG)
    if low[-1] > high[-3]:
        buy_score += 1.5
        smc_reasons.append("⚖️ Bullish FVG (Imbalance Zone)")
    elif high[-1] < low[-3]:
        sell_score += 1.5
        smc_reasons.append("⚖️ Bearish FVG (Imbalance Zone)")

    # 3. Order Block (OB) Detection
    is_last_red = close[-2] < open_p[-2]
    is_last_green = close[-2] > open_p[-2]
    strong_up = close[-1] > high[-2]
    strong_down = close[-1] < low[-2]

    if is_last_red and strong_up:
        buy_score += 2
        smc_reasons.append("📦 Bullish Order Block Tapped")
    elif is_last_green and strong_down:
        sell_score += 2
        smc_reasons.append("📦 Bearish Order Block Tapped")

    # 4. Liquidity Sweep
    if low[-1] < recent_low and close[-1] > recent_low:
        buy_score += 2
        smc_reasons.append("💧 Liquidity Swept Below (Bull Trap)")
    elif high[-1] > recent_high and close[-1] < recent_high:
        sell_score += 2
        smc_reasons.append("💧 Liquidity Swept Above (Bear Trap)")

    # Final Decision Calculation
    if buy_score >= 3 and buy_score > sell_score:
        direction = "🟢 BUY (UP ⬆️)"
        confidence = min(96, int(60 + (buy_score * 7)))
    elif sell_score >= 3 and sell_score > buy_score:
        direction = "🔴 SELL (DOWN ⬇️)"
        confidence = min(96, int(60 + (sell_score * 7)))
    else:
        trend_up = close[-1] > close[-5]
        direction = "🟢 BUY (UP ⬆️)" if trend_up else "🔴 SELL (DOWN ⬇️)"
        confidence = 68
        smc_reasons.append("📊 Trend Momentum Alignment")

    return {
        "direction": direction,
        "confidence": confidence,
        "price": float(close[-1]),
        "reasons": smc_reasons
    }

# ================= TIMING MATH (T-15 SECONDS) =================
def get_wait_seconds_for_15s_mark():
    """Calculates wait time until 15s before 5-min candle close"""
    now = datetime.now()
    minute = now.minute
    second = now.second
    microsecond = now.microsecond

    seconds_in_cycle = (minute % 5) * 60 + second + (microsecond / 1_000_000)
    target = 285.0  # 300 seconds - 15 seconds = 285 seconds

    if seconds_in_cycle < target:
        return target - seconds_in_cycle
    else:
        return (300.0 - seconds_in_cycle) + target

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_state(user.id)

    keyboard = []
    pair_list = list(PAIRS.keys())
    for i in range(0, len(pair_list), 2):
        row = []
        for j in range(2):
            if i + j < len(pair_list):
                p = pair_list[i + j]
                row.append(InlineKeyboardButton(p, callback_data=f"pair_{p}"))
        keyboard.append(row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🤖 *Quotex SMC Smart Brain Bot*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome {user.first_name}!\n\n"
        f"🧠 Strategy: *SMC (OB + FVG + BOS)*\n"
        f"⏱ Timeframe: *5 Minutes*\n"
        f"⏰ Signal Timing: *15 sec Before Candle Close*\n"
        f"💰 Martingale: 3 Levels ($1 → $2.5 → $6)\n\n"
        f"👇 *Pair Select Karein:*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id
    state = get_user_state(user_id)

    # 1. Pair Select Action
    if data.startswith("pair_"):
        pair = data.replace("pair_", "")
        state["selected_pair"] = pair

        keyboard = [[InlineKeyboardButton("▶️ RUN - SMC Signal", callback_data="run")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"✅ Pair Selected: *{pair}*\n"
            f"⏱ Timeframe: 5 Min\n\n"
            f"▶️ Press **RUN** to start SMC analysis.",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

    # 2. RUN Button Action
    elif data == "run":
        pair = state["selected_pair"]
        if not pair:
            await query.edit_message_text("⚠️ Pehle pair select karein! /start")
            return

        loss_count = state["loss_count"][pair]
        if loss_count >= MAX_LOSSES:
            keyboard = [[InlineKeyboardButton("🔄 Reset & Try Again", callback_data=f"reset_{pair}")]]
            await query.edit_message_text(
                f"🛑 *3 Losses ho gaye {pair} pe!*\n"
                f"Cool down karein aur reset karein.",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        wait_seconds = get_wait_seconds_for_15s_mark()

        await query.edit_message_text(
            f"⏳ *SMC Brain Market Analyze Kar Raha Hai...*\n"
            f"📌 Pair: {pair} (5 Min)\n"
            f"⏰ Signal exact *15 sec pehle* aayega.\n"
            f"⏱ Approx Wait: ~{int(wait_seconds)} sec...",
            parse_mode="Markdown"
        )

        # Wait asynchronously until 15s before candle close
        await asyncio.sleep(wait_seconds)

        ticker = PAIRS[pair]
        df = fetch_data_5m(ticker)

        if df is None:
            keyboard = [[InlineKeyboardButton("🔄 Try Again", callback_data="run")]]
            await query.edit_message_text(
                "⚠️ Data fetch error (Weekend/Market closed?). Retry karein.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return

        smc_res = analyze_smc(df)
        if smc_res is None:
            await query.edit_message_text("⚠️ Data kam hai SMC analyze karne ke liye.")
            return

        level = loss_count
        amount = MARTINGALE_AMOUNTS[level]
        mode = "🔥 RECOVERY" if level > 0 else "✅ NORMAL"

        reasons_text = "\n".join([f"  • {r}" for r in smc_res["reasons"]])

        full_msg = (
            f"⚡ *SMC SIGNAL GENERATED* ⚡\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{smc_res['direction']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 Pair: {pair}\n"
            f"⏱ Timeframe: *5 Min*\n"
            f"⏰ Expiry: *Next 5-Min Candle*\n"
            f"💹 Price: {smc_res['price']:.5f}\n"
            f"🧠 AI Confidence: {smc_res['confidence']}%\n\n"
            f"🔍 *SMC Confluence:*\n{reasons_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Trade Amount: ${amount} ({mode})\n"
            f"📈 Level: {level + 1}/3\n"
            f"🚨 *TRADE NOW — 15 sec remaining!*\n"
            f"━━━━━━━━━━━━━━━━━━"
        )

        state["last_signal"] = pair

        keyboard = [
            [
                InlineKeyboardButton("✅ WIN", callback_data="win"),
                InlineKeyboardButton("❌ LOSS", callback_data="loss"),
            ],
            [
                InlineKeyboardButton("▶️ Next Signal", callback_data="run"),
                InlineKeyboardButton("📋 Change Pair", callback_data="back_pairs"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            full_msg, parse_mode="Markdown", reply_markup=reply_markup
        )

    # 3. WIN Button Action
    elif data == "win":
        pair = state["selected_pair"]
        if pair:
            state["loss_count"][pair] = 0

        keyboard = [[InlineKeyboardButton("▶️ Next Signal", callback_data="run")]]
        await query.edit_message_text(
            f"🎉 *WIN! Profit booked!*\n"
            f"📊 Martingale Reset → $1\n\n"
            f"Next signal ke liye RUN press karein.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 4. LOSS Button Action
    elif data == "loss":
        pair = state["selected_pair"]
        if pair:
            state["loss_count"][pair] = min(state["loss_count"][pair] + 1, MAX_LOSSES)
            level = state["loss_count"][pair]

            if level >= MAX_LOSSES:
                keyboard = [[InlineKeyboardButton("🔄 Reset", callback_data=f"reset_{pair}")]]
                await query.edit_message_text(
                    f"😔 *3rd Loss! Max Recovery Reached.*\n"
                    f"🛑 Cool down karein. Reset karein?",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                next_amount = MARTINGALE_AMOUNTS[level]
                keyboard = [[InlineKeyboardButton("▶️ Recovery Signal", callback_data="run")]]
                await query.edit_message_text(
                    f"😔 *Loss Noted.*\n"
                    f"📊 Recovery Mode ON\n"
                    f"💰 Next Amount: ${next_amount} (Level {level + 1})\n\n"
                    f"Next signal ke liye RUN press karein.",
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

    # 5. RESET Button Action
    elif data.startswith("reset_"):
        pair = data.replace("reset_", "")
        state["loss_count"][pair] = 0

        keyboard = [[InlineKeyboardButton("▶️ RUN Signal", callback_data="run")]]
        await query.edit_message_text(
            f"🔄 *Reset Ho Gaya!*\n"
            f"💰 Amount back to $1 (Normal Mode).",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # 6. Back to Pairs Action
    elif data == "back_pairs":
        keyboard = []
        pair_list = list(PAIRS.keys())
        for i in range(0, len(pair_list), 2):
            row = []
            for j in range(2):
                if i + j < len(pair_list):
                    p = pair_list[i + j]
                    row.append(InlineKeyboardButton(p, callback_data=f"pair_{p}"))
            keyboard.append(row)
        await query.edit_message_text(
            "👇 *Pair Select Karein:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# ================= MAIN FUNCTION =================
def main():
    # 1. Start Cloud Keep-Alive Dummy Web Server
    threading.Thread(target=run_web, daemon=True).start()

    print("🤖 SMC Smart Brain Bot Starting...")
    print("🌐 Cloud Server Binding to Port...")
    print("📊 Strategy: SMC (OB + FVG + BOS)")
    print("⏱ Timeframe: 5 Minutes")
    print("⏰ Signal Timing: 15 sec Before Candle Expiry")
    print("=" * 50)

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))

    print("✅ Bot is RUNNING 24/7!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()