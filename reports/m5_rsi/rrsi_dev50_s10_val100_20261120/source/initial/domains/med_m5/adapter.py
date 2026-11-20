"""The online coordinator binds the current completed prefix at each checkpoint.
Do not invoke offline rrsi.py baseline/run with future questions in evolve_ids().
"""
from m5rrsi.domain import MedM5Domain
# Instance is constructed by m5rrsi.search.OfficialSearch with trusted runtime/scorer.
