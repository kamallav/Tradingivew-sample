# database/models.py

import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import settings

# --- Database Setup ---
Base = declarative_base()
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Database Models ---

class Trade(Base):
    """
    Represents a single trade transaction in the database.
    """
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, index=True)
    strategy = Column(String, index=True)  # e.g., "SHORT_STRANGLE_HEDGE"
    order_id = Column(String, unique=True)
    instrument = Column(String)
    transaction_type = Column(String)  # "BUY" or "SELL"
    quantity = Column(Integer)
    price = Column(Float)
    status = Column(String)  # e.g., "OPEN", "CLOSED", "CANCELLED"
    entry_time = Column(DateTime, default=datetime.datetime.utcnow)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, default=0.0)

    def __repr__(self):
        return f"<Trade(id={self.id}, strategy='{self.strategy}', instrument='{self.instrument}')>"


class PnlLog(Base):
    """
    Stores the Profit and Loss log on a periodic basis (e.g., daily).
    """
    __tablename__ = "pnl_log"

    id = Column(Integer, primary_key=True, index=True)
    strategy = Column(String, index=True)
    date = Column(DateTime, default=datetime.date.today)
    pnl = Column(Float)

    def __repr__(self):
        return f"<PnlLog(id={self.id}, date='{self.date}', strategy='{self.strategy}', pnl={self.pnl})>"


class StrategySetting(Base):
    """
    Stores user-configurable settings for each strategy.
    This allows for dynamic adjustments via the web dashboard.
    """
    __tablename__ = "strategy_settings"

    id = Column(Integer, primary_key=True, index=True)
    strategy_name = Column(String, unique=True, index=True)
    # Stores all parameters for a strategy as a JSON object
    # e.g., {"capital_allocation": 0.35, "otm_points": 200, "sl_per_lot": 7000}
    parameters = Column(JSON)
    is_active = Column(Integer, default=1)  # 1 for active, 0 for inactive

    def __repr__(self):
        return f"<StrategySetting(id={self.id}, strategy_name='{self.strategy_name}')>"


# --- Function to Create Database ---
def create_db():
    """
    Creates all the tables in the database.
    This function should be called once at the start of the application.
    """
    print("Creating database and tables...")
    Base.metadata.create_all(bind=engine)
    print("Database and tables created successfully.")

if __name__ == "__main__":
    # This allows us to create the database by running this script directly
    create_db()
