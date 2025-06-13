from flask import Flask, render_template, request, redirect, url_for
from datetime import datetime
import uuid
import os
import json


app = Flask(__name__)

# In-memory data structures
games = {}  # game_id -> game data
player_stats = {}  # player_name -> {'profit': 0, 'games_played': 0}

DEFAULT_HAND = 20  # default starting amount in NIS
SAVE_FILE = 'games_data.json'

# -------- Persistence --------
def save_games_to_file():
    with open(SAVE_FILE, 'w') as f:
        json.dump({gid: {
            'id': game['id'],
            'timestamp': game['timestamp'],
            'players': game['players'],
            'history': game['history']
        } for gid, game in games.items()}, f, indent=4)

def load_games_from_file():
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, 'r') as f:
            data = json.load(f)
            for gid, g in data.items():
                games[gid] = {
                    'id': g['id'],
                    'timestamp': g['timestamp'],
                    'players': g['players'],
                    'history': g['history']
                }

@app.route('/')
def index():
    return render_template('index.html', games=games)

@app.route('/new_game', methods=['GET', 'POST'])
def new_game():
    if request.method == 'POST':
        game_id = str(uuid.uuid4())
        player_names = request.form.get('players').split(',')
        players = {name.strip(): {'balance': 0, 'hands': 1} for name in player_names}
        games[game_id] = {
            'id': game_id,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'players': players,
            'history': []
        
        }
        save_games_to_file()
        return redirect(url_for('manage_game', game_id=game_id))

    save_games_to_file()
    return render_template('new_game.html')

@app.route('/delete_game/<game_id>', methods=['POST'])
def delete_game(game_id):
    if game_id in games:
        del games[game_id]
        save_games_to_file()
    return redirect(url_for('index'))

@app.route('/game/<game_id>', methods=['GET', 'POST'])
def manage_game(game_id):
    game = games[game_id]
    
    if request.method == 'POST':
        action = request.form.get('action')
        player = request.form.get('player')

        if action == 'add_hand' and player in game['players']:
            game['players'][player]['hands'] += 1
            game['players'][player]['balance'] -= DEFAULT_HAND
            game['history'].append(f"{player} added a hand (-{DEFAULT_HAND} NIS) -"+datetime.now().strftime('%H:%M:%S'))
        elif action == 'remove_hand' and player in game['players']:
            
            game['players'][player]['hands'] -= 1
            game['players'][player]['balance'] += DEFAULT_HAND
            game['history'].append(f"{player} removed a hand (+{DEFAULT_HAND} NIS) -"+datetime.now().strftime('%H:%M:%S'))
        elif action == 'add_money' and player in game['players']:
            try:
                amount = float(request.form.get('amount', '0'))
                game['players'][player]['balance'] += amount
                game['history'].append(f"{player} added {amount:.2f} NIS to balance -"+datetime.now().strftime('%H:%M:%S'))
            except ValueError:
                pass  # invalid input, ignore
        elif action == 'add_player':
            new_player = request.form.get('new_player')
            if new_player and new_player.strip() not in game['players']:
                game['players'][new_player.strip()] = {'balance': 0, 'hands': 1}
                game['history'].append(f"{new_player.strip()} joined the game with 1 hand -"+datetime.now().strftime('%H:%M:%S'))

    # Calculate total balance (balance only; not including hand values)
    total_balance = sum(player['balance'] for player in game['players'].values())
    save_games_to_file()

    return render_template('manage_game.html', game=game, default_hand=DEFAULT_HAND, total_balance=total_balance)


@app.route('/game/<game_id>/summary')
def game_summary(game_id):
    game = games[game_id]
    balances = {p: d['balance'] for p, d in game['players'].items()}
    print(balances)
    # Calculate total money and average
    total = sum(balances.values())
    avg = total / len(balances)
    net = {p: balances[p] - avg for p in balances}

    debtors = {p: -net[p] for p in net if net[p] < 0}
    creditors = {p: net[p] for p in net if net[p] > 0}

    transactions = []
    transfers = {p: [] for p in game['players']}

    debtors = sorted(debtors.items(), key=lambda x: x[1], reverse=True)
    creditors = sorted(creditors.items(), key=lambda x: x[1], reverse=True)

    i, j = 0, 0
    while i < len(debtors) and j < len(creditors):
        debtor, debt_amt = debtors[i]
        creditor, credit_amt = creditors[j]
        amount = min(debt_amt, credit_amt)
        transactions.append(f"{debtor} pays {creditor} {amount:.2f} NIS")
        transfers[debtor].append((creditor, amount))

        debtors[i] = (debtor, debt_amt - amount)
        creditors[j] = (creditor, credit_amt - amount)

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    # Update stats
    for player, balance in net.items():
        player_stats.setdefault(player, {'profit': 0, 'games_played': 0})
        player_stats[player]['profit'] += balance
        player_stats[player]['games_played'] += 1

    save_games_to_file()

    return render_template(
        'summary.html',
        game=game,
        net=net,
        transactions=transactions,
        balances=balances,
        transfers=transfers
    )

@app.route('/stats')
def stats():
    return render_template('stats.html', stats=player_stats)

if __name__ == '__main__':
    load_games_from_file()
    app.run(debug=True)
