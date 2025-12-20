import statistics
import logging
import math

class SignalBuffer:
    def __init__(self, median_window=7, ema_alpha=0.2):
        self.median_window = median_window
        self.ema_alpha = ema_alpha
        self.history = [] # List of recent raw RSSI values
        self.ema_value = None
        self.logger = logging.getLogger("SignalProc")

    def add_sample(self, rssi):
        """
        Adds a raw RSSI sample and returns the filtered (smoothed) value.
        Pipeline: Raw -> Median Filter -> EMA Filter -> Output
        """
        # 1. Update History Window
        self.history.append(rssi)
        if len(self.history) > self.median_window:
            self.history.pop(0)
            
        # 2. Median Filter (Removes outliers/spikes)
        # Statistics.median handles odd/even lengths correctly
        median_val = statistics.median(self.history)
        
        # 3. EMA Filter (Smoothing)
        # EMA_t = alpha * x_t + (1 - alpha) * EMA_{t-1}
        if self.ema_value is None:
            self.ema_value = median_val
        else:
            self.ema_value = (self.ema_alpha * median_val) + ((1 - self.ema_alpha) * self.ema_value)
            
        return self.ema_value
    
    def get_value(self):
        return self.ema_value

    def clear(self):
        self.history = []
        self.ema_value = None

def calculate_distance(rssi, tx_power=-59, n=2.5):
    """
    Estimates distance using Log-Distance Path Loss Model.
    d = 10 ^ ((TxPower - RSSI) / (10 * n))
    
    :param rssi: Received Signal Strength Indication (smoothed)
    :param tx_power: RSSI at 1 meter (default -59 dBm)
    :param n: Path loss exponent (2.0=free space, 2.5-3.0=typical indoor)
    :return: Estimated distance in meters
    """
    if rssi == 0:
        return -1.0
        
    try:
        ratio = (tx_power - rssi) / (10 * n)
        distance = math.pow(10, ratio)
        return round(distance, 2)
    except Exception:
        return -1.0
