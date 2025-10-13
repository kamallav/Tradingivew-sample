# broker/zerodha.py

import logging
from kiteconnect import KiteConnect, KiteTicker
from config import settings

# --- Setup Logging ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class ZerodhaBroker:
    """
    Handles all interactions with the Zerodha Kite Connect API.
    """

    def __init__(self):
        """
        Initializes the KiteConnect client.
        """
        log.info("Initializing Zerodha Broker...")
        self.kite = KiteConnect(api_key=settings.API_KEY)
        self.access_token = settings.ACCESS_TOKEN
        self.kws = None  # Websocket client instance
        self.ticks = [] # To store ticks

        if self.access_token and self.access_token != "YOUR_ACCESS_TOKEN":
            try:
                self.kite.set_access_token(self.access_token)
                log.info("Session already active. Access token set.")
            except Exception as e:
                log.error(f"Could not set access token, you might need to login again: {e}")
                self.access_token = None
        else:
            log.warning("Access token not found. Please login to generate one.")

    def get_login_url(self):
        """
        Generates the login URL for the user to authenticate.
        """
        login_url = self.kite.login_url()
        log.info(f"Kite Login URL: {login_url}")
        return login_url

    def generate_session(self, request_token):
        """
        Generates a session (access token) using the request token.
        This access token is long-lived and should be stored securely.
        """
        try:
            data = self.kite.generate_session(request_token, api_secret=settings.API_SECRET)
            self.access_token = data["access_token"]
            self.kite.set_access_token(self.access_token)

            log.info("Session generated successfully!")
            log.info(f"Access Token: {self.access_token}")

            # IMPORTANT: Persist this access token for future use.
            # In a real application, you would save this to a secure file or database.
            # For this project, we can update the settings file, but this is not ideal for production.
            log.warning("Please update the ACCESS_TOKEN in config/settings.py with the new token.")

            return self.access_token
        except Exception as e:
            log.error(f"Error generating session: {e}")
            return None

    def get_profile(self):
        """
        Fetches the user's profile.
        """
        if not self.access_token:
            log.error("Authentication required. Please login first.")
            return None
        try:
            return self.kite.profile()
        except Exception as e:
            log.error(f"Error fetching profile: {e}")
            return None

    # --- Placeholder methods for trading logic ---

    def place_order(self, variety, exchange, tradingsymbol, transaction_type, quantity, product, order_type, price=None, trigger_price=None):
        """
        Places an order. This is a placeholder and will be expanded.
        """
        if not self.access_token:
            log.error("Authentication required. Please login first.")
            return None
        try:
            order_id = self.kite.place_order(
                variety=variety,
                exchange=exchange,
                tradingsymbol=tradingsymbol,
                transaction_type=transaction_type,
                quantity=quantity,
                product=product,
                order_type=order_type,
                price=price,
                trigger_price=trigger_price
            )
            log.info(f"Order placed. Order ID: {order_id}")
            return order_id
        except Exception as e:
            log.error(f"Error placing order: {e}")
            return None

    # --- Websocket Methods ---

    def connect_websocket(self, instrument_tokens):
        """
        Connects to the Kite Ticker websocket and subscribes to instruments.
        """
        if not self.access_token:
            log.error("Authentication required to connect to websocket.")
            return

        self.kws = KiteTicker(settings.API_KEY, self.access_token)

        def on_ticks(ws, ticks):
            log.info(f"Ticks received: {ticks}")
            self.ticks.append(ticks)

        def on_connect(ws, response):
            log.info("Websocket connected.")
            ws.subscribe(instrument_tokens)
            ws.set_mode(ws.MODE_FULL, instrument_tokens)

        def on_close(ws, code, reason):
            log.warning(f"Websocket closed: {code} - {reason}")

        self.kws.on_ticks = on_ticks
        self.kws.on_connect = on_connect
        self.kws.on_close = on_close

        log.info("Connecting to websocket in the background...")
        self.kws.connect(threaded=True)

# --- Example Usage (for manual login) ---
if __name__ == "__main__":
    broker = ZerodhaBroker()

    if not broker.access_token:
        print("Please generate a request token to proceed.")
        print("1. Get the login URL by running this script.")
        login_url = broker.get_login_url()
        print(f"Login URL: {login_url}")

        print("\n2. Open the URL, log in, and you will be redirected to a URL with a 'request_token'.")
        request_token = input("3. Please paste the request_token here: ")

        if request_token:
            broker.generate_session(request_token)

    if broker.access_token:
        profile = broker.get_profile()
        if profile:
            print(f"\nSuccessfully connected! Welcome, {profile.get('user_name')}.")
