import random


def test():
    """Stupid test function"""
    L = [random.randint(0, i) for i in range(1000000)]
    L.sort()


if __name__ == "__main__":
    import timeit

    print(timeit.timeit("test()", setup="from __main__ import test", number=1))
