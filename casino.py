import random
from collections import deque

class House():
	def __init__(self):
		self.rounds_per_table = 100_000
		self.game = Game(self)

class Game():
	def __init__(self, house: House, decks: int = 2, guests:int = 6, warning_card:int = 30):
		self.house = house
		self.rounds_played = 0
		self.deck: deque[Card] = deque(Card(rank,suit) for rank in Card.RANKS for suit in Card.SUITS for _ in range(decks))
		random.shuffle(self.deck)
		self.shuffles = 1
		self.deck_len = len(self.deck)
		self.warning_card= warning_card
		self.discard_pile: deque[Card] = deque()
		self.dealer = Dealer(cash = 100_000.00)
		self.players = [Guest() for _ in range(guests-1)] + [Clairvoyant()]

		self.run_table()

#TODO return
	def deal_card(self):
		if len(self.deck) > self.warning_card:
			return self.deck.popleft()
		else:
			self.shuffles += 1
			self.deck.extend(self.discard_pile.copy())
			self.discard_pile.clear()
			random.shuffle(self.deck)
			self.discard_pile.appendleft(self.deal_card()) #burn
			return self.deck.popleft()

#TODO return
#TODO negative money allowed
	def solicit(self):
		for player in self.players:
			if playable_spots := player.cash // player.normal_bet:
				player.spots = [Spot() for _ in range(min(player.spot_count,playable_spots))]
			elif player.cash:
				player.spots = [Spot()]
			for spot in player.spots:
				player_bet = player.bet(spot)
				player.cash -= player_bet
				spot.chips += player_bet
		self.dealer.spots = [Spot()]

#TODO return
	def deal(self):
		self.dealer.spots[0].draw(self.deal_card())
		for player in self.players:
			for spot in player.spots:
				if spot.chips:
					spot.draw(self.deal_card(), self.deal_card())
		self.dealer.spots[0].draw(self.deal_card())

#TODO return
#TODO: Illegal intents allowed
	def engage(self):
		up_card = self.dealer.spots[0].hand[1]
		hole_card = self.dealer.spots[0].hand[0]
		dealer_blackjack = False
		if up_card.rank == "A":
			dealer_blackjack = self.insurance()
		if not dealer_blackjack:
			for person in self.players + [self.dealer]:
				for i, spot in enumerate(person.spots):
					if spot.split_count:
						spot.draw(self.deal_card())
					playing = True
					while playing:
						action = person.intention(spot, up_card, hole_card)
						spot.plays.append(action)
						match action:
							case "Hit":
								spot.draw(self.deal_card())
							case "Split":
								additional_bet = person.supplemental_bet(spot, False)
								person.cash -= additional_bet
								new_spot = Spot(additional_bet, spot.split_count + 1)
								new_spot.draw(spot.hand.pop())
								person.spots.insert(i+1, new_spot)
								spot.draw(self.deal_card())
								spot.split = True
							case "Double":
								additional_bet = person.supplemental_bet(spot, True)
								person.cash -= additional_bet
								spot.chips += additional_bet
								spot.draw(self.deal_card())
								spot.doubled = True
							case "Stand":
								pass
							case "Bust":
								pass
						if action in ("Double", "Stand", "Bust"):
							playing = False

	def insurance(self):
		for person in self.players:
			for spot in person.spots:
				if insurance := person.insure(spot):
					person.cash -= insurance
					spot.insurance_pool += insurance
		if self.dealer.spots[0].is_blackjack():
			for person in self.players:
				for spot in person.spots:
					self.dealer.cash -= 2 * spot.insurance_pool
					spot.insurance_pool += 2 * spot.insurance_pool
					person.cash += spot.insurance_pool
					spot.insurance_pool = 0
			return True
		else:
			for person in self.players:
				for spot in person.spots:
					self.dealer.cash += spot.insurance_pool
					spot.insurance_pool = 0
			return False

#TODO return
#TODO: dealer bankrupt
	def sweep(self):
		dealer = self.dealer
		dealer_spot = dealer.spots[0]
		dealer_score = dealer_spot.best_score()
		dealer.last_results = ""
		for player in self.players:
			player.last_results = ""
			for player_spot in player.spots:
				player_score = player_spot.best_score()
				if dealer_spot == player_spot:
					player.pushes += 1
					player.last_results += "P"
					dealer.pushes += 1
					dealer.last_results += "P"
				elif player_spot.is_blackjack():
					player.wins += 1
					player.winning_blackjacks += 1
					player.last_results += "B"
					dealer.losses += 1
					dealer.last_results += "L"
					dealer.cash -= 1.5 * player_spot.chips
					player_spot.chips += 1.5 * player_spot.chips					
				elif player_score > 21 or player_spot < dealer_spot:
					player.losses += 1
					player.last_results += "L"
					dealer.wins += 1
					if dealer_spot.is_blackjack():
						dealer.last_results += "B"
						dealer.winning_blackjacks += 1
					else:
						dealer.last_results += "W"
					dealer.cash += player_spot.chips
					player_spot.chips = 0
				elif dealer_score > 21 or player_spot > dealer_spot:
					player.wins += 1
					player.last_results += "W"
					dealer.losses += 1
					dealer.last_results += "L"
					dealer.cash -= player_spot.chips
					player_spot.chips += player_spot.chips
				else:
					raise RuntimeError
				player.cash += player_spot.chips
				player_spot.chips = 0
				player.hands += 1
		dealer.hands += 1

#TODO return
	def discard(self):
		for person in self.players + [self.dealer]:
			for spot in person.spots:
				for _ in range(len(spot.hand)):
					self.discard_pile.appendleft(spot.hand.pop())
			person.spots.clear()

#TODO gather returns
	def play_round(self):
		self.solicit()
		self.deal()
		self.engage()
		self.sweep()
		self.discard()
		self.rounds_played += 1
			
	def run_table(self):
		while self.rounds_played < self.house.rounds_per_table and [player.cash for player in self.players if player.cash > 0]:
			self.play_round()
			if not self.rounds_played % 1000:
				print(f"{self.rounds_played}: {', '.join([f'{player.cash} {player.percentage()}' for player in self.players])}")

class Player():
	count = 0
	def __init__(self, cash = 1000.0, spot_count = 1, normal_bet = 5):
		self.starting_cash = cash
		self.spot_count = spot_count
		self.spots: list[Spot] = [Spot() for _ in range(spot_count)]
		self.cash: float = cash
		self.wins = 0
		self.winning_blackjacks = 0
		self.pushes = 0
		self.losses = 0
		self.hands = 0
		self.last_results = ""
		self.normal_bet = normal_bet
		self.is_dealer = False
		Player.count += 1
		self.number = Player.count

	def __repr__(self):
		return f'{"Dealer" if self.is_dealer else "Player"} {self.number}: %: {self.percentage()} Cash: {self.cash}, Best Scores: {[spot.best_score() for spot in self.spots]}, Bets: {[spot.chips for spot in self.spots]}, Spots: {self.spots}, Results: {self.last_results}, Plays: {[spot.plays for spot in self.spots]}'
	
	def bet(self, spot: "Spot"):
		if self.cash >= self.normal_bet:
			return self.normal_bet
		else:
			return self.cash
		
	def supplemental_bet(self, spot: "Spot", is_double = True):
		if self.cash >= self.normal_bet:
			if spot.chips >= self.normal_bet:
				return self.normal_bet
			else:
				return spot.chips
		else:
			return self.cash

	def intention(self, this_spot, up_card: "Card", hole_card: "Card"):
		if this_spot.best_score() < 18:
			return "Hit"
		else:
			return "Stand"
		
	def percentage(self):
		if self.wins + self.losses:
			return f'{100*self.wins/(self.wins + self.losses):.4f}%'
		else:
			return "--%"
		
	def insure(self, spot):
		return 0
		
class Dealer(Player):
	count = 0
	def __init__(self, cash=100_000.0):
		super().__init__(cash)
		self.spot_count = 1
		self.is_dealer = True
		Dealer.count += 1
		self.number = Dealer.count

	def intention(self, this_spot: "Spot", up_card: "Card", hole_card: "Card"):
		if this_spot.best_score() > 21:
			return "Bust"
		if this_spot.best_score() == 17 and 7 in this_spot.all_scores() or this_spot.best_score() < 17:
			return "Hit"
		else:
			return "Stand"
		
class Guest(Player):
	count = 0
	def __init__(self, cash=1_000.0):
		super().__init__(cash)
		self.is_dealer = False
		Guest.count += 1
		self.number = Guest.count
	
#TODO: The Book
#TODO: check bet
	def intention(self, this_spot: "Spot", up_card: "Card", hole_card: "Card"):
		if this_spot.best_score() > 21:
			return "Bust"
		if len(this_spot.hand) == 2 and self.cash:
			if this_spot.best_score() in (9,10,11):
				return "Double"
			if this_spot.split_count < 3 and this_spot.hand[0].rank == this_spot.hand[1].rank:
				return "Split"
		if this_spot.best_score() <= 11:
			return "Hit"
		if up_card <= Card('6'):
			return "Stand"
		if (this_spot.best_score() == 17 and 7 in this_spot.all_scores() or this_spot.best_score() < 17):
			return "Hit"
		else:
			return "Stand"
		
class Clairvoyant(Guest):
	def intention(self, this_spot: "Spot", up_card: "Card", hole_card: "Card"):
		dealer_spot = Spot(cards=[up_card, hole_card])
		if this_spot.best_score() > 21:
			return "Bust"
		if len(this_spot.hand) == 2 and self.cash:
			if this_spot.best_score() in (9,10,11):
				return "Double"
			if this_spot.split_count < 3 and this_spot.hand[0].rank == this_spot.hand[1].rank:
				return "Split"
		if this_spot.best_score() <= 11:
			return "Hit"
		if 14 > dealer_spot.best_score() > 17 and len(dealer_spot.all_scores()) == 1:
			return "Stand"
		if dealer_spot > this_spot:
			return "Hit"
		if (this_spot.best_score() == 17 and 7 in this_spot.all_scores() or this_spot.best_score() < 17):
			return "Hit"
		else:
			return "Stand"
			
class Spot():
	def __init__(self, chips = 0, split_count = 0, cards = None):
		self.split = False
		self.split_count = split_count
		self.doubled = False
		self.insurance_pool = 0
		self.hand: list[Card] = []
		if cards:
			self.hand = cards
		self.chips = chips
		self.plays: list[str] = []

	def __repr__(self) -> str:
		return ' '.join([str(card) for card in self.hand])
	
	def __eq__(self, other: "Spot"):
		left = 21 - self.best_score()
		right = 21 - other.best_score()
		left_blackjack = self.is_blackjack()
		right_blackjack = other.is_blackjack()
		return right_blackjack and left_blackjack or left < 0 > right or left == right
	
	def __lt__(self, other: "Spot"):
		left = 21 - self.best_score()
		right = 21 - other.best_score()
		left_blackjack = self.is_blackjack()
		right_blackjack = other.is_blackjack()
		return right_blackjack and not left_blackjack or left < 0 <= right or left > right >= 0
	
	def __le__(self, other: "Spot"):
		left = 21 - self.best_score()
		right = 21 - other.best_score()
		right_blackjack = other.is_blackjack()
		return right_blackjack or left < 0 or left >= right

	def draw(self, *cards: "Card"):
		for card in cards:
			self.hand.append(card)
	
	def best_score(self) -> int:
		if not self.hand:
			return 0
		if playable_hands := [score for score in self.all_scores() if score <= 21]:
			return max(playable_hands)
		else:
			return min(self.all_scores())
	
	def all_scores(self) -> tuple[int,...]:
		return sum(self.hand)
	
	def is_blackjack(self):
		return len(self.hand) == 2 and self.best_score() == 21 and not (self.split_count or self.split)

class Card():
	RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A')
	SUITS = ('♣︎', '♦︎', '♥︎', '♠︎')
	LONG_RANKS = ('Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Jack', 'Queen', 'King', 'Ace')
	LONG_SUITS = ('Clubs', 'Diamonds', 'Hearts', 'Spades')

	def __init__(self, rank: RANKS = 'A', suit: SUITS = '♠︎'):
		self.rank: str = str(rank)
		self.suit: str = str(suit)
	def __repr__(self) -> str:
		return f'{self.rank}{self.suit}'
	def __lt__(self, other):
		return Card.RANKS.index(self.rank) < Card.RANKS.index(other.rank) or Card.RANKS.index(self.rank) == Card.RANKS.index(other.rank) and Card.SUITS.index(self.suit) < Card.SUITS.index(other.suit)
	def __le__(self, other):
		return Card.RANKS.index(self.rank) <= Card.RANKS.index(other.rank)
	def __add__(self,other):
		if other == 0:
			return set(self.values())
		if isinstance(other, Card):
			return set(x+y for x in self.values() for y in other.values())
		else:
			return set(x+y for x in self.values() for y in other)
	def __radd__(self,other):
		return self + other
	def long_name(self) -> str:
		return f'{Card.LONG_RANKS[Card.RANKS.index(self.rank)]} of {Card.LONG_SUITS[Card.SUITS.index(self.suit)]}'
	def values(self) -> tuple[int,...]:
		if self.rank == 'A':
			return (1,11)
		if self.rank in ('K', 'Q', 'J', 'T'):
			return (10,)
		else:
			return (int(self.rank),)

def main():
	croft_and_jessen = House()


if __name__ == "__main__":
	main()