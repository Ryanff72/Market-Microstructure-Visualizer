# Market-Microstructure-Visualizer
A visualization of how buyers and sellers find each other in the market. Also includes a paper trading simulator.
## Setup
Very typical and easy. Once in venv:
```pip install requirements.txt```
Then run:
```python app.py```
## Features
### Paper Trading
<img width="1840" height="634" alt="paper trading image" src="https://github.com/user-attachments/assets/bae69ff6-b58c-4783-937d-51cdf1229995" />
This section allows users to test their own trading strategies based on the current market microstructure, giving them a surface level understanding
of what the various indicators might mean for the price of BTC.

### Quick Facts
<img width="1849" height="164" alt="quick facts image" src="https://github.com/user-attachments/assets/c96e40c9-ebf1-476f-a215-9cd1b6fc7b21" />
This section shows the best bid and ask, spread, mid price, and market imbalance. These are calculated from the coinbase API. 

### Order Book Depth and Spread Over Time Graphs
<img width="1849" height="352" alt="graphs image" src="https://github.com/user-attachments/assets/6a43c577-8e35-41d0-9fde-eded0089f8b7" />
These graphs show live data on the current order book depth and spread over the last 5 minutes. The order book depth provides deeper insight into the buy and sell orders near the 
midpoint price. The spread over time graph gives an idea of liquidity patterns. A smaller spread typically indicates higher liquidity, as the best ask and bid are very close to overlapping.

### Order Imbalance Gauge
<img width="1850" height="172" alt="imbalance" src="https://github.com/user-attachments/assets/092c1aec-ddf4-47c9-85d5-179f162b6624" />
This simple gauge visualizes the current buy / sell pressure.

