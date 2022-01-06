import random


def test():
    L = sorted([random.randint(0, i) for i in range(1000000)])


if __name__ == "__main__":
    import timeit

    print(timeit.timeit("test()", setup="from __main__ import test", number=1))
