import cProfile
from pstats import Stats


def profile(func):
    pr = cProfile.Profile()
    pr.enable()

    func()

    pr.disable()
    stats = Stats(pr)
    stats.sort_stats("time").print_stats(10)
