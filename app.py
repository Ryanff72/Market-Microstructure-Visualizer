import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import numpy as np
from datetime import datetime
import plotly.graph_objs as go
from websocket_client import CoinbaseWebSocket
from order_book import OrderBook

##################
# Global Vars
##################

orderbook = OrderBook()
ws_client = None

#state for fast interpolation
previous_metrics = {'best_bid': 0, 'best_ask': 0, 'spread': 0, 'mid_price': 0, 'imbalance': 0.5}
target_metrics = {'best_bid': 0, 'best_ask': 0, 'spread': 0, 'mid_price': 0, 'imbalance': 0.5}

# track trades
portfolio = {
    'usd': 200000.0,
    'btc': 0.0,
    'transactions': []
}
#limit on how many trades we keep in memory
transaction_history_limit = 100

#how often graphs updated
graph_interval = 2

#method for interpolating vals (makes site look fast haha)
def interpolate_value(old, new, steps=10, current_step = 0):
    if old is None or new is None:
        return new or old or 0
    alpha = min(current_step / steps, 1.0)
    return old + (new-old) *alpha #lin interp formula


# Sleek Dark Mode: Professional trading terminal—clean blacks, subtle grays, precise accents
COLORS = {
    'background': '#0c0c0c',  # Deep black for focus
    'card_bg': '#1a1a1a',     # Subtle gray-black for cards
    'text': '#f0f0f0',        # Clean off-white for readability
    'bid_green': '#10b981',   # Modern emerald green for bids
    'ask_red': '#ef4444',     # Crisp red for asks
    'accent': '#3b82f6',      # Professional blue for highlights
    'grid': 'rgba(55, 65, 81, 0.3)',  # Muted slate grid
}

# Fonts: Inter for everything—modern, highly legible sans-serif
FONTS = {
    'header': '"Inter", sans-serif',
    'body': '"Inter", sans-serif',
}

##################
# Create application
##################

app = dash.Dash(__name__)
server = app.server
app.title = "BTC-USD Visualizer"

app.config.update_title = None
app.config.suppress_callback_exceptions = True

##################
# Layout
##################
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        
        <!-- Google Fonts: Clean modern sans -->
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        
        <style>
            ._dash-loading,
            .dash-loading-callback,
            .dash-spinner {
                display: none !important; 
            }
            ::-webkit-scrollbar {
                width: 6px;
            }
            ::-webkit-scrollbar-track {
                background: #1a1a1a;
            }
            ::-webkit-scrollbar-thumb {
                background: #374151;
                border-radius: 3px;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: #4b5563;
            }
            
            body {
                font-family: ''' + FONTS['body'] + ''';
                margin: 0;
                padding: 0;
                background-color: ''' + COLORS['background'] + ''';
                color: ''' + COLORS['text'] + ''';
                line-height: 1.5;
            }
            
            h1, h2, h3 {
                font-family: ''' + FONTS['header'] + ''';
                font-weight: 600;
                letter-spacing: -0.025em;
                margin: 0 0 0.5em 0;
            }

            .sleek-card {
                background-color: ''' + COLORS['card_bg'] + ''';
                border: 1px solid ''' + COLORS['grid'] + ''';
                border-radius: 8px;
                padding: 24px;
                transition: border-color 0.2s ease, box-shadow 0.2s ease;
                position: relative;
            }
            .sleek-card:hover {
                border-color: ''' + COLORS['accent'] + ''';
                box-shadow: 0 1px 3px rgba(0,0,0,0.1), 0 4px 12px rgba(0,0,0,0.05);
            }
            
            .sleek-divider {
                border: none;
                height: 1px;
                background-color: ''' + COLORS['grid'] + ''';
                margin: 24px 0;
            }
            
            .metric-label {
                font-size: 12px;
                font-weight: 500;
                color: ''' + COLORS['accent'] + ''';
                text-transform: uppercase;
                letter-spacing: 0.05em;
                margin-bottom: 8px;
            }
            
            .metric-value {
                font-size: 32px;
                font-weight: 700;
                line-height: 1.2;
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''

app.layout = html.Div(style={
    'minHeight': '100vh',
    'padding': '32px',
    'maxWidth': '1600px',
    'margin': '0 auto',
}, children=[

    # Header: Clean title bar
    html.Div([
        html.H1("BTC-USD Microstructure Visualizer",
                style={'color': COLORS['text'], 'textAlign': 'center', 'fontSize': '28px', 'marginBottom': '4px'}),
    ], className='sleek-card', style={'marginBottom': '32px', 'textAlign': 'center'}),

    html.Div(className='sleek-divider'),

    ####################
    # Metrics Grid
    ####################
    html.Div([
        # Best Bid
        html.Div([
            html.Div("Best Bid", className='metric-label'),
            html.Div(id='best-bid-value', children="$0.00", style={
                'color': COLORS['bid_green'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Best Ask
        html.Div([
            html.Div("Best Ask", className='metric-label'),
            html.Div(id='best-ask-value', children="$0.00", style={
                'color': COLORS['ask_red'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Spread
        html.Div([
            html.Div("Spread", className='metric-label'),
            html.Div(id='spread-value', children="$0.00", style={
                'color': COLORS['accent'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Mid Price
        html.Div([
            html.Div("Mid Price", className='metric-label'),
            html.Div(id='mid-price-value', children="$0.00", style={
                'color': COLORS['text'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

        # Imbalance
        html.Div([
            html.Div("Imbalance", className='metric-label'),
            html.Div(id='imbalance-value', children="0.00%", style={
                'color': COLORS['accent'],
                'className': 'metric-value',
            })
        ], className='sleek-card', style={'flex': '1', 'minWidth': '180px'}),

    ], style={
        'display': 'grid',
        'gridTemplateColumns': 'repeat(auto-fit, minmax(180px, 1fr))',
        'gap': '16px',
        'marginBottom': '32px',
    }),

    ########################
    # Charts: Side-by-side, compressed
    ########################

    html.Div([
        
        # Order Book Depth Chart
        html.Div([
            html.H3("Order Book Depth", style={
                'color': COLORS['text'], 
                'textAlign': 'center',
                'fontSize': '16px',
                'marginBottom': '16px'
            }),
            dcc.Graph(
                id='orderbook-chart',
                config={'displayModeBar': False},
                style={'height': '200px'}
            )
        ], className='sleek-card', style={'flex': '1', 'marginRight': '16px'}),

        html.Div([
            html.H3("Spread over Time", style={
                'color': COLORS['text'],
                'textAlign': 'center',
                'fontSize' : '16px',
                'marginBottom': '16px'
            }),
            dcc.Graph(
                id='spread-chart',
                config={'displayModeBar': False},
                style={'height': '200px'}
            )
        ], className='sleek-card', style={'flex': '1', 'marginLeft': '16px'}) 
        
    ], style={'display': 'flex', 'gap': '16px', 'marginBottom': '32px'}),

    # Imbalance Gauge
    html.Div([
        html.H3("Order Imbalance", style={
            'color': COLORS['text'], 
            'textAlign': 'center',
            'fontSize': '16px',
            'marginBottom': '8px'
        }),
        html.Div([
            html.Div("Sell Pressure", style={
                'color': COLORS['ask_red'],
                'fontSize': '12px',
                'fontWeight': '500',
                'textAlign': 'left'
            }),
            html.Div(id='imbalance-gauge-value', children="50.0%", style={
                'color': COLORS['text'],
                'fontSize': '18px',
                'fontWeight': '500',
                'textAlign': 'center'
            }),
            html.Div("Buy Pressure", style={
                'color': COLORS['bid_green'],
                'fontSize': '12px',
                'fontWeight': '500',
                'textAlign': 'right'
            }),
        ], style={
            'display': 'flex',
            'justifyContent': 'space-between',
            'marginBottom': '6px'
        }),
        html.Div([
            html.Div(id='imbalance-bar-sell', style={
                'backgroundColor': COLORS['ask_red'],
                'height': '6px',
                'transition': 'width 0.3s ease',
                'borderRadius': '3px',
                'width': '50%',
            }),
            html.Div(id='imbalance-bar-buy', style={
                'backgroundColor': COLORS['bid_green'],
                'height': '6px',
                'transition': 'width 0.3s ease',
                'borderRadius': '3px',
                'width': '50%',
            }),
        ], style={
            'width': '100%',
            'backgroundColor': COLORS['grid'],
            'borderRadius': '3px',
            'overflow': 'hidden',
        })
        
    ], className='sleek-card', style={'marginBottom': '10px'}),
    # trading sim
    html.Div([
        html.H3("Trade", style={
            'color': COLORS['text'], 
            'textAlign': 'center',
            'fontSize': '24px',
            'letterSpacing': '2px',
            'marginBottom': '8px',
            'fontWeight': '700'
        }),
        
        # Portfolio Display - Sleek Cards
        html.Div([
            html.Div([
                html.Div("Balance", style={'fontSize': '11px', 'color': COLORS['accent'], 'textTransform': 'uppercase', 'letterSpacing': '1px', 'marginBottom': '8px'}),
                html.Div(id='portfolio-usd', children="$10,000.00", 
                    style={'fontSize': '24px', 'color': COLORS['text'], 'fontWeight': '700'})
            ], style={
                'flex': '1', 
                'textAlign': 'center',
                'padding': '20px',
                'backgroundColor': f"{COLORS['background']}40",
                'borderRadius': '12px',
                'border': f"1px solid {COLORS['grid']}30"
            }),
            html.Div([
                html.Div("Holdings", style={'fontSize': '11px', 'color': COLORS['accent'], 'textTransform': 'uppercase', 'letterSpacing': '1px', 'marginBottom': '8px'}),
                html.Div(id='portfolio-btc', children="0.0000 BTC", 
                    style={'fontSize': '24px', 'color': COLORS['text'], 'fontWeight': '700'})
            ], style={
                'flex': '1', 
                'textAlign': 'center',
                'padding': '20px',
                'backgroundColor': f"{COLORS['background']}40",
                'borderRadius': '12px',
                'border': f"1px solid {COLORS['grid']}30",
                'margin': '0 12px'
            }),
            html.Div([
                html.Div("Total Value", style={'fontSize': '11px', 'color': COLORS['accent'], 'textTransform': 'uppercase', 'letterSpacing': '1px', 'marginBottom': '8px'}),
                html.Div(id='portfolio-total', children="$10,000.00", 
                    style={'fontSize': '24px', 'color': COLORS['bid_green'], 'fontWeight': '700'})
            ], style={
                'flex': '1', 
                'textAlign': 'center',
                'padding': '20px',
                'backgroundColor': f"{COLORS['background']}40",
                'borderRadius': '12px',
                'border': f"1px solid {COLORS['grid']}30"
            }),
        ], style={'display': 'flex', 'marginBottom': '25px'}),
        
        # Main Trading Area - Two Columns
        html.Div([
            # Left Column - Trading Controls
            html.Div([
                html.Label("Amount (BTC)", style={
                    'color': COLORS['text'], 
                    'marginBottom': '12px', 
                    'display': 'block',
                    'fontSize': '13px',
                    'fontWeight': '600',
                    'textTransform': 'uppercase',
                    'letterSpacing': '1px'
                }),
                dcc.Input(
                    id='trade-amount',
                    type='number',
                    value=0.01,
                    min=0.0001,
                    step=0.0001,
                    style={
                        'width': '90%',
                        'padding': '16px',
                        'backgroundColor': f"{COLORS['background']}60",
                        'color': COLORS['text'],
                        'border': f'1px solid {COLORS["text"]}50',
                        'borderRadius': '6px',
                        'fontFamily': FONTS['body'],
                        'fontSize': '16px',
                        'fontWeight': '600',
                        'marginBottom': '16px',
                        'transition': 'all 0.3s ease'
                    }
                ),
                
                # Buy button with animation
                html.Button('Buy', id='buy-button', n_clicks=0, 
                    className='trade-button trade-buy-button',
                    style={
                        'width': '100%',
                        'padding': '18px',
                        'backgroundColor': COLORS['bid_green'],
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '6px',
                        'fontSize': '16px',
                        'fontWeight': '700',
                        'cursor': 'pointer',
                        'marginBottom': '12px',
                        'textTransform': 'uppercase',
                        'letterSpacing': '1.5px',
                        'transition': 'all 0.2s ease',
                        'boxShadow': f"0 4px 12px {COLORS['bid_green']}40"
                    }
                ),
                
                # Sell button with animation
                html.Button('Sell', id='sell-button', n_clicks=0,
                    className='trade-button trade-sell-button',
                    style={
                        'width': '100%',
                        'padding': '18px',
                        'backgroundColor': COLORS['ask_red'],
                        'color': 'white',
                        'border': 'none',
                        'borderRadius': '6px',
                        'fontSize': '16px',
                        'fontWeight': '700',
                        'cursor': 'pointer',
                        'textTransform': 'uppercase',
                        'letterSpacing': '1.5px',
                        'transition': 'all 0.2s ease',
                        'boxShadow': f"0 4px 12px {COLORS['ask_red']}40"
                    }
                ),
                
                # Transaction feedback
                html.Div(id='trade-feedback', style={
                    'textAlign': 'center',
                    'color': COLORS['accent'],
                    'fontSize': '13px',
                    'minHeight': '20px',
                    'marginTop': '16px',
                    'fontWeight': '500'
                })
            ], style={
                'flex': '0 0 300px',
                'marginRight': '25px'
            }),
            
            # Right Column - Transaction History
            html.Div([
                html.Div("Recent Trades", style={
                    'fontSize': '14px',
                    'fontWeight': '700',
                    'color': COLORS['text'],
                    'marginBottom': '16px',
                    'textTransform': 'uppercase',
                    'letterSpacing': '1.5px'
                }),
                html.Div(id='transaction-history', children=[
                    html.Div("No trades yet", style={
                        'color': COLORS['accent'],
                        'textAlign': 'center',
                        'padding': '40px 20px',
                        'fontSize': '13px',
                        'opacity': '0.6'
                    })
                ], style={
                    'maxHeight': '280px',
                    'overflowY': 'auto',
                    'overflowX': 'hidden'
                })
            ], style={
                'flex': '1',
                'backgroundColor': f"{COLORS['background']}40",
                'padding': '20px',
                'borderRadius': '12px',
                'border': f"1px solid {COLORS['grid']}30"
            })
        ], style={'display': 'flex', 'alignItems': 'stretch'})
    ], style={
        'backgroundColor': COLORS['card_bg'],
        'padding': '30px',
        'borderRadius': '16px',
        'marginBottom': '20px',
        'boxShadow': '0 8px 32px rgba(0,0,0,0.2)'
    }),
    # Interval component (keep as-is)
    dcc.Interval(
        id='interval-component',
        interval=500,
        n_intervals=0
    ),
])

##################
# Websocket
##################

def handle_websocket_message(msg_type, data):
	if msg_type == "snapshot":
		orderbook.initialize_snapshot(data['bids'], data['asks'])
		print("Orderbook Initialized.")

	elif msg_type == "l2update":
		orderbook.process_update(data['changes'])

def start_websocket():
	global ws_client
	ws_client = CoinbaseWebSocket(on_message_callback=handle_websocket_message)
	ws_client.start()
	print("Websocket Started.")

##################
# Callback
##################

@app.callback(
	[
		Output('best-bid-value', 'children'),
		Output('best-ask-value', 'children'),
		Output('spread-value', 'children'),
		Output('mid-price-value', 'children'),
		Output('imbalance-value', 'children'),
	],
	Input('interval-component', 'n_intervals')
)

def update_metrics(n):
    metrics = orderbook.get_metrics()
    return [
        f"${metrics['best_bid']:,.2f}",
        f"${metrics['best_ask']:,.2f}",
        f"${metrics['spread']:,.2f}",
        f"${metrics['mid_price']:,.2f}",
        f"{metrics['imbalance']:,.1%}",
    ]

@app.callback(
    Output('orderbook-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)

def update_orderbook_chart(n):
    if n % graph_interval != 0:
        raise dash.exceptions.PreventUpdate
    depth = orderbook.get_depth_snapshot(levels=15)
    bid_prices = [price for price, size in depth['bids']]
    bid_sizes = [size for price, size in depth['bids']]
    ask_prices = [price for price, size in depth['asks']]
    ask_sizes = [size for price, size in depth['asks']]
    bid_sizes = [-size for size in bid_sizes]
    max_volume = max(max(abs(x) for x in bid_sizes), max(abs(x) for x in ask_sizes))
    # make chart
    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=bid_prices,
        x=bid_sizes,
        orientation='h',
        name='Bids',
        marker_color=COLORS['bid_green'],
        hovertemplate='Price: $%{y:,.2f}<br>Size: %{x:.4f} BTC'
    ))
    fig.add_trace(go.Bar(
        y=ask_prices,
        x=ask_sizes,
        orientation='h',
        name='Asks',
        marker_color=COLORS['ask_red'],
        hovertemplate='Price: $%{y:,.2f}<br>Size: %{x:.4f} BTC'
    ))
    fig.update_layout(
        plot_bgcolor=COLORS['card_bg'],
        paper_bgcolor=COLORS['card_bg'],
        font={'color': COLORS['text'], 'family': FONTS['body'], 'size': 12},
        showlegend=False,
        margin=dict(l=60, r=40, t=20, b=40),
        xaxis=dict(
            title="Volume (BTC)",
            gridcolor=COLORS['grid'],
            zerolinecolor=COLORS['grid'],
            zerolinewidth=1,
            range=[-max_volume * 1.1, max_volume * 1.1]
        ),
        yaxis=dict(
            title="Price (USD)",
            gridcolor=COLORS['grid'],
            tickformat='$,.0f',
        ),
        hovermode='closest',
        bargap=0.4,
        bargroupgap=0,
    )
    fig.update_traces(
        width=0.6,
        selector=dict(type='bar')
    )
    
    return fig

@app.callback(
    Output('spread-chart', 'figure'),
    Input('interval-component', 'n_intervals')
)

def update_spread_chart(n):
    if n % graph_interval != 0:
        raise dash.exceptions.PreventUpdate
    fig = go.Figure()
    orderbook.update_history()
    spread_data = list(orderbook.spread_history)
    spread_data=[s for s in spread_data if s is not None]
    x_values = list(range(len(spread_data)- 1, -1, -1))

    fig.add_trace(go.Scatter(
        x=x_values,
        y=spread_data,
        mode='lines',
        name='Spread',
        line=dict(
            color=COLORS['accent'],
            width=2
        ),
        fill='tozeroy',
        fillcolor=f'rgba(59, 130, 246, 0.1)',
        hovertemplate='$%{y:.2f}'
    ))

    #styling
    fig.update_layout(
        plot_bgcolor=COLORS['card_bg'],
        paper_bgcolor=COLORS['card_bg'],
        font={'color': COLORS['text'], 'family': FONTS['body'], 'size': 12},
        showlegend=False,
        margin=dict(l=40, r=20, t=20, b=40),
        xaxis=dict(
            title="Time Ago (Seconds)",
            gridcolor=COLORS['grid'],
            tickformat='d'
        ),
        yaxis=dict(
            title="Spread (USD)",
            gridcolor=COLORS['grid'],
            tickformat='$,.2f',
            range=[0, max(spread_data) * 1.2]
        ),
        hovermode='x unified'
    )
    return fig

@app.callback(
    [
        Output('imbalance-gauge-value', 'children'),
        Output('imbalance-bar-sell', 'style'),
        Output('imbalance-bar-buy', 'style'),
    ],
    Input('interval-component', 'n_intervals')
)

def update_imbalance_gauge(n):
    imbalance = orderbook.get_imbalance()
    if imbalance is None: imbalance = 0.5
    buy_percentage = imbalance * 100
    sell_percentage = (1-imbalance) * 100
    gauge_text = f"{imbalance:.1%}"

    sell_style = {
        'backgroundColor': COLORS['ask_red'],
        'height': '6px',
        'transition': 'width 0.3s ease',
        'borderRadius': '3px',
        'width': f'{sell_percentage}%'
    }

    buy_style = {
        'backgroundColor': COLORS['bid_green'],
        'height': '6px',
        'transition': 'width 0.3s ease',
        'borderRadius': '3px',
        'width': f'{buy_percentage}%'
    }

    return gauge_text, sell_style, buy_style

# paper trading
@app.callback(
    [
        Output('portfolio-usd', 'children'),
        Output('portfolio-btc', 'children'),
        Output('portfolio-total', 'children'),
        Output('trade-feedback', 'children'),
        Output('transaction-history', 'children'),
    ],
    [
        Input('buy-button', 'n_clicks'),
        Input('sell-button', 'n_clicks'),
        Input('interval-component', 'n_intervals'),
    ],
    [
        dash.dependencies.State('trade-amount', 'value')
    ]
)
def handle_trading(buy_clicks, sell_clicks, n, amount):
    global portfolio
    
    if amount is None or amount <= 0:
        amount = 0.01

    best_ask = orderbook.get_best_ask()
    if best_ask is None:
        best_ask = 0
    
    ctx = dash.callback_context
    feedback = ""

    
    if ctx.triggered:
        button_id = ctx.triggered[0]['prop_id'].split('.')[0]
        
        if button_id == 'buy-button' and buy_clicks > 0:
            cost = amount * best_ask
            
            # Check if we have enough USD
            if portfolio['usd'] >= cost - 0.00001:
                portfolio['usd'] -= cost
                portfolio['btc'] += amount
                feedback = f"Bought {amount} BTC at ${best_ask:,.2f}"
                portfolio['transactions'].insert(0, {
                    'type': 'buy',
                    'amount': amount,
                    'price': best_ask,
                    'total': cost,
                    'timestamp': datetime.now().strftime('%H:%M:%S')
                })
                portfolio['transactions'] = portfolio['transactions'][:transaction_history_limit]
            else:
                feedback = f"Insufficient USD (need ${cost:,.2f})"
        
        elif button_id == 'sell-button' and sell_clicks > 0:
            # Check if we have enough BTC
            if portfolio['btc'] >= amount - 0.00001:
                revenue = amount * best_ask
                portfolio['btc'] -= amount
                portfolio['usd'] += (amount * best_ask)
                feedback = f"Sold {amount} BTC at ${best_ask:,.2f}"
                portfolio['transactions'].insert(0, {
                    'type': 'sell',
                    'amount': amount,
                    'price': best_ask,
                    'total': revenue,
                    'timestamp': datetime.now().strftime('%H:%M:%S')
                })
                portfolio['transactions'] = portfolio['transactions'][:transaction_history_limit]
            else:
                feedback = f"Insufficient BTC (have {portfolio['btc']:.4f})"
    portfolio['usd'] = abs(portfolio['usd'])
    portfolio['btc'] = abs(portfolio['btc'])
    total_value = portfolio['usd'] + (portfolio['btc'] * best_ask)
    
    usd_display = f"${portfolio['usd']:,.2f}"
    btc_display = f"{portfolio['btc']:.4f} BTC"
    total_display = f"${total_value:,.2f}"
    if portfolio['transactions']:
        transaction_items = []
        for tx in portfolio['transactions']:
            trade_class = 'trade-item trade-buy' if tx['type'] == 'buy' else 'trade-item trade-sell'
            transaction_items.append(
                html.Div([
                    html.Div([
                        html.Span(tx['type'].upper(), style={
                            'fontWeight': '700',
                            'color': COLORS['bid_green'] if tx['type'] == 'buy' else COLORS['ask_red'],
                            'marginRight': '8px'
                        }),
                        html.Span(f"{tx['amount']:.4f} BTC", style={'color': COLORS['text']}),
                    ]),
                    html.Div([
                        html.Div(f"${tx['price']:,.2f}", style={'color': COLORS['text'], 'fontWeight': '600'}),
                        html.Div(tx['timestamp'], style={'fontSize': '11px', 'color': COLORS['accent'], 'marginTop': '2px'}),
                    ], style={'textAlign': 'right'})
                ], className=trade_class)
            )
        transaction_history = transaction_items
    else:
        transaction_history = [
            html.Div("No trades yet", style={
                'color': COLORS['accent'],
                'textAlign': 'center',
                'padding': '40px 20px',
                'fontSize': '13px',
                'opacity': '0.6'
            })
        ]
    
    return usd_display, btc_display, total_display, feedback, transaction_history
##################
# Main
##################

if __name__ == '__main__':
	start_websocket()
	app.run(debug=False, 
            dev_tools_hot_reload=False,
            dev_tools_ui=False,
            dev_tools_props_check=False,
            dev_tools_serve_dev_bundles=False,
            host='0.0.0.0', 
            port=8050)