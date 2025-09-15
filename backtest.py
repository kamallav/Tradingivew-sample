import pandas as pd

def run_backtest(data, strategy_type, timeframe):
    """
    Runs a backtest for a given strategy type (long or short) on the provided data.
    """
    if strategy_type not in ['long', 'short']:
        raise ValueError("strategy_type must be 'long' or 'short'")

    print(f"\n--- Running {strategy_type.capitalize()} Strategy on {timeframe} timeframe ---")

    # Calculate 5-period EMA
    data['ema_5'] = data['close'].ewm(span=5, adjust=False).mean()

    trades = []
    position = None
    daily_losses = 0
    current_day = None

    for i in range(1, len(data)):
        prev_candle = data.iloc[i-1]
        current_candle = data.iloc[i]

        # Reset daily loss counter at the start of a new day
        day = current_candle['timestamp'].date()
        if current_day != day:
            current_day = day
            daily_losses = 0

        # Check for SL/TP if a position is open
        if position:
            if position['type'] == 'long':
                if current_candle['low'] <= position['stop_loss']:
                    position['exit_price'] = position['stop_loss']
                    position['pnl'] = position['exit_price'] - position['entry_price']
                    trades.append(position)
                    if position['pnl'] < 0:
                        daily_losses += 1
                    position = None
                elif current_candle['high'] >= position['take_profit']:
                    position['exit_price'] = position['take_profit']
                    position['pnl'] = position['exit_price'] - position['entry_price']
                    trades.append(position)
                    position = None
            elif position['type'] == 'short':
                if current_candle['high'] >= position['stop_loss']:
                    position['exit_price'] = position['stop_loss']
                    position['pnl'] = position['entry_price'] - position['exit_price']
                    trades.append(position)
                    if position['pnl'] < 0:
                        daily_losses += 1
                    position = None
                elif current_candle['low'] <= position['take_profit']:
                    position['exit_price'] = position['take_profit']
                    position['pnl'] = position['entry_price'] - position['exit_price']
                    trades.append(position)
                    position = None
            if position is None: # If position was closed, continue to next candle
                continue

        # Check for entry signals if no position is open and daily loss limit not reached
        if not position and daily_losses < 3:
            # --- LONG STRATEGY RULES ---
            if strategy_type == 'long':
                # Alert candle: closes below 5 EMA, high does not touch EMA
                if prev_candle['close'] < prev_candle['ema_5'] and prev_candle['high'] < prev_candle['ema_5']:
                    alert_candle = prev_candle
                    # Entry trigger: price breaks above the high of the alert candle
                    if current_candle['high'] > alert_candle['high']:
                        entry_price = alert_candle['high']
                        stop_loss = alert_candle['low']
                        risk = entry_price - stop_loss
                        if risk == 0: continue
                        take_profit = entry_price + (risk * 3)

                        position = {
                            'type': 'long',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_time': current_candle['timestamp'],
                            'risk': risk
                        }

            # --- SHORT STRATEGY RULES ---
            elif strategy_type == 'short':
                # Alert candle: closes above 5 EMA, low does not touch EMA
                if prev_candle['close'] > prev_candle['ema_5'] and prev_candle['low'] > prev_candle['ema_5']:
                    alert_candle = prev_candle
                    # Entry trigger: price breaks below the low of the alert candle
                    if current_candle['low'] < alert_candle['low']:
                        entry_price = alert_candle['low']
                        stop_loss = alert_candle['high']
                        risk = stop_loss - entry_price
                        if risk == 0: continue
                        take_profit = entry_price - (risk * 3)

                        position = {
                            'type': 'short',
                            'entry_price': entry_price,
                            'stop_loss': stop_loss,
                            'take_profit': take_profit,
                            'entry_time': current_candle['timestamp'],
                            'risk': risk
                        }

    # Print results
    print("Trades:")
    total_pnl = 0
    wins = 0
    losses = 0
    if not trades:
        print("No trades were made.")
    else:
        for trade in trades:
            total_pnl += trade['pnl']
            if trade['pnl'] > 0:
                wins += 1
            else:
                losses += 1
            print(f"  - {trade['type'].capitalize()} at {trade['entry_price']:.2f} on {trade['entry_time']}, "
                  f"Exit at {trade['exit_price']:.2f}, PnL: {trade['pnl']:.2f}")

    print("\nSummary:")
    print(f"Total Trades: {len(trades)}")
    print(f"Wins: {wins}, Losses: {losses}")
    if len(trades) > 0:
        win_rate = (wins / len(trades)) * 100
        print(f"Win Rate: {win_rate:.2f}%")
    print(f"Total PnL: {total_pnl:.2f}")
    print("-" * 50)


def main():
    # Load data
    try:
        df = pd.read_csv('ohlc_data.csv')
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    except FileNotFoundError:
        print("Error: 'ohlc_data.csv' not found. Please make sure the data file is in the same directory.")
        return

    # --- Run Short Strategy on 5-minute data ---
    df_5min = df.copy()
    run_backtest(df_5min, 'short', '5-min')

    # --- Run Long Strategy on 15-minute data ---
    df_15min = df.set_index('timestamp').resample('15min').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last'
    }).dropna().reset_index()
    run_backtest(df_15min, 'long', '15-min')


if __name__ == "__main__":
    main()
