from flask import Flask, request, jsonify, render_template
import random
from collections import Counter
import time
import numpy as np
import json

app = Flask(__name__)

def getdeck(deltapudding=0):
    deck = [
        14*['Tempura'],
        14*['Sashimi'],
        14*['Dumpling'],
        12*['2Maki'],
        8*['3Maki'],
        6*['1Maki'],
        10*['2Nigiri'],
        5*['3Nigiri'],
        5*['1Nigiri'],
        (10-deltapudding)*['Pudding'],
        6*['Wasabi'],
        4*['Chopsticks']
    ]
    deck = [card for typecard in deck for card in typecard]
    random.shuffle(deck)
    return deck

def scorenigiri(player):
    pts = 0
    wasabis = 0
    for card in player.table:
        if card == 'Wasabi':
            wasabis += 1
        elif 'Nigiri' not in card:
            continue
        else:
            pts += int(card[0]) * (3 if wasabis else 1)
            wasabis = max(0, wasabis - 1)
    return pts

def noval(p1, p2):
    return 0

def r1puddingval(p1, p2):
    return max(-6, min(6, (p1 - p2) * 2.25))

def r2puddingval(p1, p2):
    return max(-6, min(6, (p1 - p2) * 2.75))

def r3puddingval(p1, p2):
    return 6 if p1 > p2 else (-6 if p1 < p2 else 0)
    
def score(player1, player2, puddingval):
    c1 = Counter(player1.table)
    c2 = Counter(player2.table)
    pts1 = pts2 = 0
    pts1 += 5 * (c1['Tempura'] // 2)
    pts2 += 5 * (c2['Tempura'] // 2)
    pts1 += 10 * (c1['Sashimi'] // 3)
    pts2 += 10 * (c2['Sashimi'] // 3)
    pts1 += min(15, c1['Dumpling'] * (c1['Dumpling'] + 1) // 2)
    pts2 += min(15, c2['Dumpling'] * (c2['Dumpling'] + 1) // 2)
    pts1 += scorenigiri(player1)
    pts2 += scorenigiri(player2)
    p1maki = c1['1Maki'] + c1['2Maki'] * 2 + c1['3Maki'] * 3
    p2maki = c2['1Maki'] + c2['2Maki'] * 2 + c2['3Maki'] * 3
    if p1maki > p2maki:
        pts1 += 6
        pts2 += 3 * (p2maki > 0)
    elif p2maki > p1maki:
        pts1 += 3 * (p1maki > 0)
        pts2 += 6
    pts1 += puddingval(c1['Pudding'] + player1.puddings, c2['Pudding'] + player2.puddings)
    return pts1 - pts2

class Player:

    def __init__(self, cards, table, puddings):
        self.cards = cards
        self.table = table
        self.puddings = puddings

    def play(self, ix, chopstix=-1):
        oldc, oldt = self.cards.copy(), self.table.copy()
        self.table.append(self.cards.pop(ix))
        if chopstix >= 0 and 'Chopsticks' in self.table:
            self.table.append(self.cards.pop(chopstix if chopstix < ix else (chopstix - 1)))
            self.table.remove('Chopsticks')
            self.cards.append('Chopsticks')
        child = Player(self.cards, self.table, self.puddings)
        self.cards = oldc
        self.table = oldt
        return child
    
def getchildren(player, other=None):
    maxki = 0
    maxri = 0
    legalcards = set()
    for c in player.cards:
        if 'Maki' in c:
            maxki = max(maxki, int(c[0]))
        elif 'Nigiri' in c:
            maxri = max(maxri, int(c[0]))
        else:
            legalcards.add(c)
    moves = []
    if maxki:
        moves.append(player.cards.index(f'{maxki}Maki'))
    if maxri:
        moves.append(player.cards.index(f'{maxri}Nigiri'))
    for c in legalcards:
        moves.append(player.cards.index(c))
    children = [player.play(m) for m in sorted(moves)]
    chopschildren = []
    if 'Chopsticks' in player.table:
        chops = set([tuple(sorted((m, i))) for m in moves for i in range(len(player.cards)) if i != m])
        named_moves = {}
        for m, i in chops:
            ts = tuple(sorted((player.cards[m], player.cards[i])))
            if ts in named_moves:
                named_moves[ts].append((m, i))
            else:
                named_moves[ts] = [(m, i)]
        to_delete = set()
        for k in named_moves:
            k0, k1 = k
            if 'Nigiri' in k0 and int(k0[0]) < 3:
                for xn in range(int(k0[0]) + 1, 4):
                    if (f'{xn}Nigiri', k1) in named_moves or (k1, f'{xn}Nigiri') in named_moves:
                        to_delete.add((k0, k1))
            if 'Nigiri' in k1 and int(k1[0]) < 3:
                for xn in range(int(k1[0]) + 1, 4):
                    if (k0, f'{xn}Nigiri') in named_moves or (f'{xn}Nigiri', k0) in named_moves:
                        to_delete.add((k0, k1))
            if 'Maki' in k0 and int(k0[0]) < 3:
                for xn in range(int(k0[0]) + 1, 4):
                    if (f'{xn}Maki', k1) in named_moves or (k1, f'{xn}Maki') in named_moves:
                        to_delete.add((k0, k1))
            if 'Maki' in k1 and int(k1[0]) < 3:
                for xn in range(int(k1[0]) + 1, 4):
                    if (k0, f'{xn}Maki') in named_moves or (f'{xn}Maki', k0) in named_moves:
                        to_delete.add((k0, k1))
            if 'Chopsticks' == k1 or 'Chopsticks' == k0:
                to_delete.add((k0, k1))
            if other is None:
                continue
            if (k1 == 'Sashimi' or k0 == 'Sashimi') and (player.cards.count('Sashimi') + other.cards.count('Sashimi') < 3):
                to_delete.add((k0, k1))
            if (k1 == 'Tempura' or k0 == 'Tempura') and (player.cards.count('Tempura') + other.cards.count('Tempura') < 2):
                to_delete.add((k0, k1))
        for tup in to_delete:
            del named_moves[tup]
        chopschildren = [player.play(*named_moves[k][0]) for k in named_moves]
    return children + chopschildren

def alphabeta(player1, player2, a, b, maximizingPlayer, pudding_val=r1puddingval, flip=False):
    if not player1.cards and not player2.cards:
        return score(player1, player2, pudding_val), (player1 if maximizingPlayer else player2)
    player1, player2 = Player(player1.cards.copy(), player1.table.copy(), player1.puddings), Player(player2.cards.copy(), player2.table.copy(), player2.puddings)
    if maximizingPlayer:
        value = -float('inf')
        bestkid = None
        if flip:
            player1.cards, player2.cards = player2.cards, player1.cards
        for child in getchildren(player1, player2):
            recurs, _ = alphabeta(child, player2, a, b, False, pudding_val)
            if recurs > value:
                value = recurs
                bestkid = child
            if value > b:
                break
            a = max(a, value)
        if flip:
            player1.cards, player2.cards = player2.cards, player1.cards
        return value, bestkid
    else:
        value = float('inf')
        worstkid = None
        for child in getchildren(player2, player1):
            recurs, _ = alphabeta(player1, child, a, b, True, pudding_val, flip=True)
            if recurs < value:
                value = recurs
                worstkid = child
            if value < a:
                break            
            b = min(b, value)
        return value, worstkid

@app.route('/newround', methods=['POST'])
def new_round():
    data = request.json
    p1 = json.loads(data['compstate'])
    p2 = json.loads(data['playerstate'])
    p1 = Player(p1['cards'], p1['table'], p1['puddings'])
    p2 = Player(p2['cards'], p2['table'], p2['puddings'])
    deck = getdeck(deltapudding=p1.puddings + p2.puddings)
    if data['currround'] > 3:
        prevpoints = score(p1, p2, r3puddingval)
    else:
        prevpoints = score(p1, p2, noval)
    p1 = Player(sorted([deck.pop() for _ in range(8)], key=lambda x: x[::-1]), [], p1.puddings if data['currround'] <= 3 else 0)
    p2 = Player(sorted([deck.pop() for _ in range(8)], key=lambda x: x[::-1]), [], p2.puddings if data['currround'] <= 3 else 0)
    return jsonify({'p1': p1.__dict__, 'p2': p2.__dict__ , 'prevpoints': prevpoints + data['prevpoints']})


@app.route('/initgame', methods=['POST'])
def init_game():
    deck = getdeck()
    p1 = Player(sorted([deck.pop() for _ in range(8)], key=lambda x: x[::-1]), [], 0)
    p2 = Player(sorted([deck.pop() for _ in range(8)], key=lambda x: x[::-1]), [], 0)
    prevpoints = 0
    return jsonify({'p1': p1.__dict__, 'p2': p2.__dict__ , 'prevpoints': prevpoints})

def process_next(a1, a2, p1, p2):
    _, kid = alphabeta(p1, p2, -float('inf'), float('inf'), True)
    kid2 = p2.play(int(a1), int(a2))
    assert len(kid.cards) == len(kid2.cards)
    p1, p2 = kid, kid2
    p1.cards, p2.cards = p2.cards, p1.cards
    return p1, p2

@app.route('/go', methods=['POST'])
def make_move():
    data = request.json
    select_list = data['selection']
    prevpoints = data['prevpoints']
    p1 = json.loads(data['compstate'])
    p2 = json.loads(data['playerstate'])
    p1 = Player(p1['cards'], p1['table'], p1['puddings'])
    p2 = Player(p2['cards'], p2['table'], p2['puddings'])
    if len(select_list) < 2:
        select_list.append(-1)
    p1, p2 = process_next(*select_list, p1, p2)
    if not p1.cards:
        p1.puddings += Counter(p1.table)['Pudding']
        p2.puddings += Counter(p2.table)['Pudding']
    return jsonify({'p1': p1.__dict__, 'p2': p2.__dict__ , 'prevpoints': prevpoints})


@app.route('/home', methods=['GET'])
def home():
    return render_template('index.html')

@app.route('/log', methods=['POST'])
def log_message():
    data = request.json  # Assuming the incoming data is JSON
    print(data['message'])  # Log the message to console
    return jsonify({"result": 123})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080)