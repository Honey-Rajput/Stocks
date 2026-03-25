import os
import time
import logging
from datetime import datetime
import pandas as pd
from dotenv import load_dotenv

# Telegram imports
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import schedule
import threading

# Local app imports
import os
os.environ['STREAMLIT_SERVER_HEADLESS'] = 'true'
import logging
logger = logging.getLogger('streamlit.runtime.scriptrunner_utils.script_run_context')
logger.setLevel(logging.ERROR)

from app import nse_stocks_dict

from analysis_engine import AnalysisEngine
from db_utils import get_db_manager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load Environment Variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAM_API_KEY")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

SCAN_DEPTH = 1500  # Number of stocks to scan
MAX_WORKERS = 25

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /start is issued."""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    msg = (f"Hi {user.first_name}! 📈\n\n"
           f"Your Chat ID is: `{chat_id}`\n"
           f"Add this ID as `TELEGRAM_CHAT_ID` in your `.env` file to receive scheduled updates.\n\n"
           f"Available Scanners:\n"
           f"/scansmc - Smart Money Concept (Accumulation)\n"
           f"/scanswing - Swing Trading Setups (15-20 days)\n"
           f"/scanlongterm - Fundamentals & Growth (Compounders)\n"
           f"/scancyclical - Historical Seasonal Patterns\n"
           f"/scanstage - Weinstein Stage Analysis\n\n"
           f"Type /help to see details for each command.")
           
    await update.message.reply_markdown(msg)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message when the command /help is issued."""
    msg = ("*Available Commands:*\n\n"
           "🚀 /scansmc - Detect institutional accumulation based on volume and price action.\n\n"
           "📈 /scanswing - Find stocks with bullish momentum for 2-3 week trades.\n\n"
           "💎 /scanlongterm - Identify companies with strong ROE, low debt, and revenue growth.\n\n"
           "🗓️ /scancyclical - High-probability seasonal performers based on 10-year backtests.\n\n"
           "📊 /scanstage - Identify Weinstein Stage 2 (Advancing) or Stage 1 (Basing) stocks.\n\n"
           "ℹ️ /start - Get your Chat ID for automated updates.")
    await update.message.reply_markdown(msg)

def format_results(title, results, max_results=5):
    """Format scanner results into a Telegram-friendly message."""
    if not results:
        return f"*{title}*\n\n❌ No high-confidence setups found right now."
    
    msg = f"🚀 *{title}* 🚀\n\n"
    for idx, res in enumerate(results[:max_results]):
        # Handle multiple possible keys for robustness
        ticker = res.get('Stock Symbol') or res.get('ticker') or 'Unknown'
        ticker_clean = str(ticker).replace('.NS', '')
        
        # Get price from multiple possible keys
        price_val = res.get('Current Price') or res.get('Price') or res.get('price')
        if price_val is not None and str(price_val) != 'nan':
            try:
                price_str = f"₹{float(price_val):.2f}"
            except:
                price_str = str(price_val)
        else:
            price_str = "Price N/A"
            
        # Get score/confidence from multiple possible keys
        conf = res.get('Smart Money Score (0–100)') or res.get('Confidence Score (0–100)') or res.get('Score') or res.get('confidence')
        if conf is not None and str(conf) != 'nan':
            conf_str = f"{float(conf):.1f}%"
        else:
            conf_str = "N/A"
            
        msg += f"{idx+1}. *{ticker_clean}* - {price_str} (Conf: {conf_str})\n"
        
        # Add a specific note if available
        note = res.get('Institutional Activity (Yes/No + short note)') or res.get('Technical Reason (short explanation)') or res.get('Long-Term Thesis (1–2 line summary)')
        if note:
            # Clean up the note if it's too long
            note = str(note).replace('Yes - ', '')
            msg += f"📝 _{note[:60]}..._\n"
            
        msg += f"🔗 [TradingView Chart](https://www.tradingview.com/chart/?symbol=NSE:{ticker_clean})\n\n"
        
    return msg

async def scan_smc_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run SMC Scan."""
    await update.message.reply_text("🛰️ Running Smart Money Scanner... This may take a moment.")
    try:
        all_tickers = list(nse_stocks_dict.values())[:SCAN_DEPTH]
        results = AnalysisEngine.get_smart_money_stocks(all_tickers, max_results=10, max_workers=MAX_WORKERS)
        msg = format_results("Smart Money Concept Scan", results)
        await update.message.reply_markdown(msg, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"SMC error: {e}")
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

async def scan_swing_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Swing Scan."""
    await update.message.reply_text("🔍 Running Swing Scanner...")
    try:
        all_tickers = list(nse_stocks_dict.values())[:SCAN_DEPTH]
        results = AnalysisEngine.get_swing_stocks(all_tickers, max_results=10, max_workers=MAX_WORKERS)
        msg = format_results("Swing Trading Scan", results)
        await update.message.reply_markdown(msg, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Swing error: {e}")
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

async def scan_longterm_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Long Term Scan."""
    await update.message.reply_text("💎 Running Long-Term Fundamental Scanner...")
    try:
        all_tickers = list(nse_stocks_dict.values())[:SCAN_DEPTH]
        results = AnalysisEngine.get_long_term_stocks(all_tickers, max_results=10, max_workers=8) # Lower workers for yfinance info
        msg = format_results("Long-Term Investing Scan", results)
        await update.message.reply_markdown(msg, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Longterm error: {e}")
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

async def scan_cyclical_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Cyclical Scan."""
    await update.message.reply_text("🗓️ Running Cyclical/Seasonal Scanner...")
    try:
        all_tickers = list(nse_stocks_dict.values())[:SCAN_DEPTH]
        grouped_results = AnalysisEngine.get_cyclical_stocks_by_quarter(all_tickers, max_results_per_quarter=5, max_workers=MAX_WORKERS)
        
        # Get current quarter
        q_key = f"Q{(datetime.now().month-1)//3 + 1}"
        current_q_results = grouped_results.get(q_key, [])
        
        msg = format_results(f"Cyclical Patterns ({q_key})", current_q_results)
        await update.message.reply_markdown(msg, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Cyclical error: {e}")
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

async def scan_stage_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Run Stage Analysis Scan."""
    await update.message.reply_text("📊 Running Weinstein Stage Analysis...")
    try:
        all_tickers = list(nse_stocks_dict.values())[:SCAN_DEPTH]
        grouped = AnalysisEngine.get_weinstein_scanner_stocks(all_tickers, max_workers=MAX_WORKERS)
        
        # Focus on Stage 2 (Advancing)
        stage2 = grouped.get("Stage 2 - Advancing", [])
        msg = format_results("Stage 2: Advancing Stocks", stage2)
        await update.message.reply_markdown(msg, disable_web_page_preview=True)
    except Exception as e:
        logger.error(f"Stage error: {e}")
        await update.message.reply_text(f"❌ Error during scan: {str(e)}")

import requests

def send_scheduled_updates():
    """Function to run scans and send to TELEGRAM_CHAT_ID synchronously."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("No TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID configured.")
        return
        
def send_scheduled_updates():
    """Function to run all scans and send to TELEGRAM_CHAT_ID synchronously."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("No TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID configured.")
        return
        
    logger.info("Starting comprehensive 9:15 AM morning update...")
    try:
        all_tickers = list(nse_stocks_dict.values())[:800] # moderate depth for morning
        
        # 1. SMC Scan
        results = AnalysisEngine.get_smart_money_stocks(all_tickers, max_results=5, max_workers=MAX_WORKERS)
        msg = format_results("Morning SMC Update", results)
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})
        
        # 2. Swing Scan
        results = AnalysisEngine.get_swing_stocks(all_tickers, max_results=5, max_workers=MAX_WORKERS)
        msg = format_results("Morning Swing Update", results)
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})

        # 3. Stage Analysis (Stage 2)
        grouped = AnalysisEngine.get_weinstein_scanner_stocks(all_tickers, max_workers=MAX_WORKERS)
        stage2 = grouped.get("Stage 2 - Advancing", [])
        msg = format_results("Morning Stage 2 Update", stage2[:5])
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})

        # 4. Long Term Focus
        results = AnalysisEngine.get_long_term_stocks(all_tickers, max_results=5, max_workers=8)
        msg = format_results("Morning Long-Term Focus", results)
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
                      json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": True})
        
    except Exception as e:
        logger.error(f"Error sending scheduled updates: {e}")

def run_scheduler():
    """Background thread to run schedule tasks."""
    logger.info("Scheduler started for 9:15 AM IST.")
    
    def job_wrapper():
        logger.info("Triggering 9:15 AM job.")
        send_scheduled_updates()
        
    # Schedule for 09:15 AM daily
    schedule.every().day.at("09:15").do(job_wrapper) # Simplest daily schedule
    
    while True:
        schedule.run_pending()
        time.sleep(60)

async def post_init(application: Application) -> None:
    """Set bot commands menu on startup."""
    from telegram import BotCommand
    commands = [
        BotCommand("scansmc", "Smart Money Concepts"),
        BotCommand("scanswing", "Swing Trading"),
        BotCommand("scanlongterm", "Long Term Investing"),
        BotCommand("scancyclical", "Cyclical Stocks"),
        BotCommand("scanstage", "Stage Analysis"),
        BotCommand("help", "All commands"),
        BotCommand("start", "Get Chat ID")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands menu registered.")

def main() -> None:
    """Start the bot."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("No TELEGRAM_BOT_TOKEN provided.")
        return

    # Create the Application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("scansmc", scan_smc_command))
    application.add_handler(CommandHandler("scan_smc", scan_smc_command))
    application.add_handler(CommandHandler("scanswing", scan_swing_command))
    application.add_handler(CommandHandler("scan_swing", scan_swing_command))
    application.add_handler(CommandHandler("scanlongterm", scan_longterm_command))
    application.add_handler(CommandHandler("scancyclical", scan_cyclical_command))
    application.add_handler(CommandHandler("scanstage", scan_stage_command))

    # Start the scheduler thread
    threading.Thread(target=run_scheduler, daemon=True).start()

    # Run the bot
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
