# option_data_downloader.py

# option_data_downloader.py

import getpass
import sqlite3
import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, MetaData, Table, Index
from sqlalchemy.orm import sessionmaker
import logging

# --- Configuration ---
DB_FILE = "options_data.db"
UNDERLYING_CONFIG = {
    "NIFTY": {"tradingsymbol": "NIFTY 50", "strike_step": 50},
    "BANKNIFTY": {"tradingsymbol": "NIFTY BANK", "strike_step": 100}
}

# --- Database Setup ---
engine = create_engine(f'sqlite:///{DB_FILE}')
metadata = MetaData()

# Table for OHLC data
ohlc_data_table = Table('ohlc_data', metadata,
    Column('id', Integer, primary_key=True, autoincrement=True),
    Column('timestamp', DateTime, nullable=False),
    Column('instrument_token', Integer, nullable=False),
    Column('symbol', String, nullable=False),
    Column('open', Float, nullable=False),
    Column('high', Float, nullable=False),
    Column('low', Float, nullable=False),
    Column('close', Float, nullable=False)
)

# Table to index all stored contracts
contracts_index_table = Table('contracts_index', metadata,
    Column('instrument_token', Integer, primary_key=True),
    Column('symbol', String, nullable=False, unique=True),
    Column('expiry', DateTime, nullable=False),
    Column('strike', Float, nullable=False),
    Column('instrument_type', String(2), nullable=False) # 'CE' or 'PE'
)

def init_database():
    """Creates the database and tables if they don't exist."""
    logging.info("Initializing database...")
    metadata.create_all(engine)
    # Create indexes for faster queries
    with engine.connect() as conn:
        idx_ohlc = Index('ix_ohlc_data_timestamp_token', ohlc_data_table.c.timestamp, ohlc_data_table.c.instrument_token)
        try:
            idx_ohlc.create(conn)
            logging.info("Created index on ohlc_data (timestamp, instrument_token).")
        except Exception:
             logging.info("Index on ohlc_data already exists.")
    logging.info("Database initialized.")

import os
import json
from kiteconnect import KiteConnect
from datetime import datetime, date

# --- Main Application ---

API_KEY = None
API_SECRET = None
kite = None
instrument_df = None

def get_api_credentials():
    """Get API credentials from the user."""
    global API_KEY, API_SECRET
    API_KEY = getpass.getpass(prompt="Enter your Kite Connect API Key: ")
    API_SECRET = getpass.getpass(prompt="Enter your Kite Connect API Secret: ")

def authenticate_kite():
    """Handles the Kite Connect authentication."""
    global kite
    kite = KiteConnect(api_key=API_KEY)

    access_token_file = "access_token.txt"

    try:
        with open(access_token_file, 'r') as f:
            access_token = f.read()
        kite.set_access_token(access_token)
        logging.info("Using cached access token.")
    except FileNotFoundError:
        logging.info(f"Redirecting for login: {kite.login_url()}")
        request_token = input("Enter the request token: ")
        try:
            data = kite.generate_session(request_token, api_secret=API_SECRET)
            access_token = data["access_token"]
            kite.set_access_token(access_token)
            with open(access_token_file, 'w') as f:
                f.write(access_token)
            logging.info("Access token generated and saved.")
        except Exception as e:
            logging.error(f"Authentication failed: {e}")
            return False

    try:
        # Verify if the access token is still valid
        kite.profile()
        logging.info("Authentication successful.")
        return True
    except Exception as e:
        logging.error(f"Token expired or invalid, please re-authenticate: {e}")
        os.remove(access_token_file) # Remove expired token
        return False

import time
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

def load_instruments():
    """Fetch and cache all exchange instruments."""
    global instrument_df
    instrument_file = "all_instruments.csv"
    try:
        instrument_df = pd.read_csv(instrument_file)
        # Convert expiry to datetime objects for easier comparison
        instrument_df['expiry'] = pd.to_datetime(instrument_df['expiry']).dt.date
        logging.info("Loaded instruments from cache.")
    except (FileNotFoundError, KeyError):
        logging.info("Fetching all instruments from API...")
        try:
            # Fetch for all exchanges, or specify ones you need e.g., ["NSE", "NFO"]
            all_instruments = kite.instruments()
            instrument_df = pd.DataFrame(all_instruments)
            instrument_df.to_csv(instrument_file, index=False)
            # Convert expiry to datetime objects for easier comparison
            instrument_df['expiry'] = pd.to_datetime(instrument_df['expiry']).dt.date
            logging.info("All instruments fetched and cached.")
        except Exception as e:
            logging.error(f"Failed to fetch instruments: {e}")
            return False
    return True

def get_atm_strike(underlying_instrument, target_date):
    """Gets the ATM strike for a given underlying on a target date."""
    try:
        config = UNDERLYING_CONFIG.get(underlying_instrument)
        if not config:
            logging.error(f"No configuration found for underlying: {underlying_instrument}")
            return None

        underlying_symbol = config['tradingsymbol']
        strike_step = config['strike_step']

        # Get the token for the underlying index/stock
        underlying_token = instrument_df[instrument_df['tradingsymbol'] == underlying_symbol].instrument_token.iloc[0]

        # Fetch historical data for the underlying for that day
        from_date = target_date
        to_date = target_date
        records = kite.historical_data(underlying_token, from_date, to_date, "day")

        if not records:
            logging.warning(f"No historical data found for {underlying_symbol} on {target_date}.")
            return None

        # The close price of the day is our spot price
        spot_price = records[-1]['close']

        # Round to the nearest strike
        atm_strike = round(spot_price / strike_step) * strike_step
        logging.info(f"ATM strike for {target_date} is {atm_strike} (Spot: {spot_price})")
        return atm_strike
    except IndexError:
        logging.error(f"Could not find instrument token for '{underlying_symbol}'. Check if the symbol is correct and present in the instrument list.")
        return None
    except Exception as e:
        logging.error(f"Could not get ATM strike for {target_date}: {e}")
        return None

def get_relevant_contracts(underlying_symbol, expiry_date, atm_strike, strike_range=10):
    """
    Filters and returns relevant option contracts (ATM ± strike_range) for a given expiry.
    """
    config = UNDERLYING_CONFIG.get(underlying_symbol)
    if not config:
        logging.error(f"No configuration found for underlying: {underlying_symbol}")
        return pd.DataFrame()

    strike_width = config['strike_step']
    min_strike = atm_strike - (strike_range * strike_width)
    max_strike = atm_strike + (strike_range * strike_width)

    # Ensure expiry_date is a date object for comparison
    if isinstance(expiry_date, datetime):
        expiry_date = expiry_date.date()

    # Filter for NFO contracts, the specific underlying, and expiry date
    nfo_df = instrument_df[instrument_df['segment'] == 'NFO-OPT']

    relevant_contracts = nfo_df[
        (nfo_df['name'] == underlying_symbol) &
        (nfo_df['expiry'] == expiry_date) &
        (nfo_df['strike'] >= min_strike) &
        (nfo_df['strike'] <= max_strike)
        ]
    return relevant_contracts


def download_and_store_ohlc(contract_row, from_date, to_date):
    """Downloads 1-min OHLC data and stores it in the database."""
    instrument_token = contract_row['instrument_token']
    symbol = contract_row['tradingsymbol']
    logging.info(f"Downloading data for {symbol} from {from_date} to {to_date}")
    try:
        records = kite.historical_data(instrument_token, from_date, to_date, "minute")
        if not records:
            logging.warning(f"No data received for {symbol} in the given date range.")
            return

        df = pd.DataFrame(records)
        df.rename(columns={'date': 'timestamp'}, inplace=True)
        df['instrument_token'] = instrument_token
        df['symbol'] = symbol
        df = df[['timestamp', 'instrument_token', 'symbol', 'open', 'high', 'low', 'close']]

        # Insert OHLC data and update the contracts index in a single transaction
        with engine.begin() as conn:
            # 1. Insert OHLC data
            df.to_sql('ohlc_data', conn, if_exists='append', index=False)

            # 2. Prepare and insert contract info into the index table
            contract_info = {
                "instrument_token": contract_row['instrument_token'],
                "symbol": contract_row['tradingsymbol'],
                "expiry": contract_row['expiry'],
                "strike": contract_row['strike'],
                "instrument_type": contract_row['instrument_type']
            }
            # Use an "upsert" statement to avoid duplicates on primary key
            stmt = sqlite_insert(contracts_index_table).values(contract_info)
            stmt = stmt.on_conflict_do_nothing(index_elements=['instrument_token'])
            conn.execute(stmt)

        logging.info(f"Successfully stored {len(df)} records and indexed {symbol}.")

    except Exception as e:
        logging.error(f"Error downloading/storing data for {symbol}: {e}")

    # Respect API rate limits
    time.sleep(0.4)


from datetime import timedelta

def get_nearest_expiry(trade_date):
    """Finds the nearest upcoming expiry date from the instruments list."""
    # Ensure trade_date is a date object
    if isinstance(trade_date, datetime):
        trade_date = trade_date.date()

    future_expiries = instrument_df[
        (instrument_df['expiry'] >= trade_date) &
        (instrument_df['segment'] == 'NFO-OPT')
    ]['expiry'].unique()

    if len(future_expiries) > 0:
        return min(future_expiries)
    return None

def run_full_historical_download(underlying_symbol="NIFTY", years=1):
    """
    Downloads historical data for the past X years, iterating day by day.
    """
    logging.info(f"Starting full historical download for {underlying_symbol} for the past {years} year(s).")

    end_date = date.today()
    start_date = end_date - timedelta(days=years * 365)

    current_date = start_date
    while current_date <= end_date:
        # We only care about weekdays
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue

        logging.info(f"--- Processing Date: {current_date} ---")

        # 1. Get ATM strike for the day
        atm_strike = get_atm_strike(underlying_symbol, current_date)
        if atm_strike is None:
            logging.warning(f"Skipping {current_date} as no ATM strike could be determined (likely a holiday).")
            current_date += timedelta(days=1)
            continue

        # 2. Find the nearest expiry for that trading day
        nearest_expiry = get_nearest_expiry(current_date)
        if nearest_expiry is None:
            logging.warning(f"No future expiry found for {current_date}. Skipping.")
            current_date += timedelta(days=1)
            continue
        logging.info(f"Nearest expiry for {current_date} is {nearest_expiry}")

        # 3. Get relevant contracts around the ATM strike
        contracts_to_download = get_relevant_contracts(underlying_symbol, nearest_expiry, atm_strike)

        if contracts_to_download.empty:
            logging.warning(f"No relevant contracts found for expiry {nearest_expiry} and ATM {atm_strike}.")
        else:
            logging.info(f"Found {len(contracts_to_download)} contracts to process for {current_date}.")

        # 4. Download data for each contract for that single day
        for _, contract_row in contracts_to_download.iterrows():
            # Check if data for this contract on this day already exists to make the script resumable
            with engine.connect() as conn:
                result = conn.execute(
                    ohlc_data_table.select().where(
                        (ohlc_data_table.c.instrument_token == contract_row['instrument_token']) &
                        (ohlc_data_table.c.timestamp >= datetime.combine(current_date, datetime.min.time())) &
                        (ohlc_data_table.c.timestamp <= datetime.combine(current_date, datetime.max.time()))
                    ).limit(1)
                ).first()

            if result:
                logging.info(f"Data for {contract_row['tradingsymbol']} on {current_date} already exists. Skipping.")
                continue

            download_and_store_ohlc(contract_row, current_date, current_date)

        current_date += timedelta(days=1)

    logging.info("Full historical download completed.")

def refresh_last_x_days(days=5):
    """
    Refreshes the OHLC data for the last X days for all contracts
    already present in the contracts_index.
    """
    logging.info(f"--- Starting refresh for last {days} days ---")

    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # 1. Get all unique, stored contracts from our index
    with engine.connect() as conn:
        stored_contracts_df = pd.read_sql_table('contracts_index', conn)

    if stored_contracts_df.empty:
        logging.warning("No contracts found in the index. Run a full download first.")
        return

    logging.info(f"Found {len(stored_contracts_df)} contracts in the index to refresh.")

    # 2. For each contract, delete old data and fetch new data for the date range
    for _, contract_row in stored_contracts_df.iterrows():
        instrument_token = contract_row['instrument_token']
        symbol = contract_row['symbol']

        logging.info(f"Refreshing {symbol} from {start_date} to {end_date}")

        # Delete existing data in the specified date range to prevent duplicates
        with engine.begin() as conn:
            delete_stmt = ohlc_data_table.delete().where(
                (ohlc_data_table.c.instrument_token == instrument_token) &
                (ohlc_data_table.c.timestamp >= datetime.combine(start_date, datetime.min.time())) &
                (ohlc_data_table.c.timestamp <= datetime.combine(end_date, datetime.max.time()))
            )
            conn.execute(delete_stmt)

        # Download fresh data for the range
        # The existing download function works perfectly for this
        download_and_store_ohlc(contract_row, start_date, end_date)

    logging.info("--- Incremental refresh completed ---")


from apscheduler.schedulers.blocking import BlockingScheduler
import pytz

def scheduled_job():
    """The job that the scheduler will run."""
    logging.info("--- Running scheduled daily refresh job ---")

    # Authenticate and load instruments before running the refresh
    get_api_credentials()
    if not API_KEY or not API_SECRET or not authenticate_kite() or not load_instruments():
        logging.error("Scheduled job failed: Could not authenticate or load instruments.")
        return

    # Refresh data for the last 2 days to be safe
    refresh_last_x_days(days=2)
    logging.info("--- Scheduled daily refresh job finished ---")

def start_scheduler():
    """Initializes and starts the APScheduler."""
    scheduler = BlockingScheduler(timezone=pytz.timezone('Asia/Kolkata'))

    # Schedule the job to run every weekday at 7:00 PM IST
    scheduler.add_job(scheduled_job, 'cron', day_of_week='mon-fri', hour=19, minute=0)

    logging.info("Scheduler started. Waiting for the next scheduled run.")
    print("Scheduler is running. Press Ctrl+C to exit.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Scheduler stopped.")


def main():
    """Main function to run the data downloader."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    init_database()

    # --- CLI ---
    print("Choose an action:")
    print("1: Run a full one-year historical download.")
    print("2: Manually refresh data for the last 5 days.")
    print("3: Start the daily scheduler (runs every weekday at 7 PM IST).")

    choice = input("Enter your choice (1, 2, or 3): ")

    if choice not in ['1', '2', '3']:
        print("Invalid choice. Exiting.")
        return

    # For choices 1 and 2, we need to authenticate immediately
    if choice in ['1', '2']:
        get_api_credentials()
        if not API_KEY or not API_SECRET:
            logging.error("API Key and Secret are required.")
            return
        if not authenticate_kite():
            return
        if not load_instruments():
            return

    if choice == '1':
        run_full_historical_download(underlying_symbol="NIFTY", years=1)
    elif choice == '2':
        refresh_last_x_days(days=5)
    elif choice == '3':
        start_scheduler()

if __name__ == "__main__":
    main()